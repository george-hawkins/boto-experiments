import sys

import boto3
import botocore.session
from botocore.config import Config
from timeit import default_timer as timer

# boto3-stubs type annotations - https://mypy-boto3.readthedocs.io/en/latest/
from mypy_boto3_dynamodb.type_defs import AttributeDefinitionTypeDef, KeySchemaElementTypeDef
from mypy_boto3_s3.service_resource import S3ServiceResource
from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table
from mypy_boto3_s3.type_defs import CreateBucketConfigurationTypeDef
from mypy_boto3_logs.client import CloudWatchLogsClient

from is_aws import is_aws


def _show_time(name, f):
    start = timer()
    result = f()
    diff = timer() - start
    print(f"{name} took {diff:.2f}s")
    return result


def create_key_schema_element(name, key_type):
    return KeySchemaElementTypeDef(AttributeName=name, KeyType=key_type)


def create_attribute_definition(name, attr_type):
    return AttributeDefinitionTypeDef(AttributeName=name, AttributeType=attr_type)


class BotoBasics:
    def __init__(self):
        self._botocore_session = botocore.session.get_session()
        self._set_region(self._botocore_session)

        self._session = boto3.session.Session(botocore_session=self._botocore_session)

        # As of Boto3 1.23.8, the default `defaults_mode` is still `legacy`.
        # See https://docs.aws.amazon.com/sdkref/latest/guide/feature-smart-config-defaults.html
        # noinspection PyArgumentList
        self._config = Config(defaults_mode="standard")
        self._s3_resource = None
        self._dynamodb = None
        self._logs = None

        # Dynamodb tables and other entities are created in the current region by default.
        # However, for whatever reason, you must specify the region for buckets.
        self._bucket_config = CreateBucketConfigurationTypeDef(LocationConstraint=self._session.region_name)

    @staticmethod
    def _set_region(botocore_session):
        # On a box with `~/.aws/config`, this picks up the `region` value from there.
        region = botocore_session.get_config_variable("region")

        if region is None:
            if not is_aws():
                sys.exit("cannot determine region")

            from botocore.utils import IMDSRegionProvider

            # Do the equivalent of `curl http://instance-data/latest/meta-data/placement/availability-zone/`
            region_provider = IMDSRegionProvider(session=botocore_session)
            botocore_session.set_config_variable("region", region_provider.provide())

    def _get_or_create_client(self, field, name):
        return field if field is not None else self._session.client(name, config=self._config)

    def _get_or_create_resource(self, field, name):
        return field if field is not None else self._session.resource(name, config=self._config)

    def _get_s3_resource(self):
        self._s3_resource: S3ServiceResource = self._get_or_create_resource(self._s3_resource, "s3")
        return self._s3_resource

    def create_bucket(self, name):
        return self._get_s3_resource().create_bucket(Bucket=name, CreateBucketConfiguration=self._bucket_config)

    # If you have large numbers of buckets then it would be much better to filter by tag (you can't filter by name).
    # See https://stackoverflow.com/a/36044264/245602
    def list_buckets(self):
        return self._get_s3_resource().buckets.all()

    def _get_dynamodb(self):
        self._dynamodb: DynamoDBServiceResource = self._get_or_create_resource(self._dynamodb, "dynamodb")
        return self._dynamodb

    @property
    def dynamodb_exceptions(self):
        return self._get_dynamodb().meta.client.exceptions

    # Creating a table can take 20s.
    def create_table(self, name, schema, defs):
        print(f"Creating table {name}...")
        table = self._get_dynamodb().create_table(
            TableName=name,
            KeySchema=schema,
            AttributeDefinitions=defs,
            BillingMode="PAY_PER_REQUEST"
        )
        _show_time("table creation", lambda: table.wait_until_exists())
        return table

    @staticmethod
    def delete_table(table: Table):
        print(f"Deleting table {table.table_name}...")
        table.delete()
        _show_time("table deletion", lambda: table.wait_until_not_exists())

    def list_tables(self):
        return self._get_dynamodb().tables.all()

    def get_table(self, name):
        return self._get_dynamodb().Table(name)

    def _get_logs(self):
        self._logs: CloudWatchLogsClient = self._get_or_create_client(self._logs, "logs")
        return self._logs

    @property
    def logs_exceptions(self):
        return self._get_logs().exceptions

    def _create_resource(self, f, fail_if_exists=False):
        try:
            f()
        except self.logs_exceptions.ResourceAlreadyExistsException as e:
            if fail_if_exists:
                raise e

    def create_log_group(self, name, retention_in_days=1, fail_if_exists=False):
        def create():
            self._get_logs().create_log_group(logGroupName=name)
            # The default is to retain log entries forever.
            self._get_logs().put_retention_policy(logGroupName=name, retentionInDays=retention_in_days)
        self._create_resource(create, fail_if_exists)

    def list_log_groups(self, prefix):
        return self._get_logs().describe_log_groups(logGroupNamePrefix=prefix)["logGroups"]

    def delete_log_group(self, name):
        self._get_logs().delete_log_group(logGroupName=name)

    def create_log_stream(self, group_name, stream_name, fail_if_exists=False):
        self._create_resource(
            lambda: self._get_logs().create_log_stream(logGroupName=group_name, logStreamName=stream_name),
            fail_if_exists
        )

    def put_log_event(self, group_name, stream_name, log_event, sequence_token):
        kwargs = {}
        # For the first message of a new stream, the sequence_token argument must be completely absent.
        if sequence_token is not None:
            kwargs["sequenceToken"] = sequence_token
        return self._get_logs().put_log_events(
            logGroupName=group_name,
            logStreamName=stream_name,
            logEvents=[log_event],
            **kwargs
        )["nextSequenceToken"]
