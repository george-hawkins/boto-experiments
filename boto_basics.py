import sys
from typing import List, Optional, Dict

import boto3
import botocore.session
from botocore.config import Config
from timeit import default_timer as timer

# boto3-stubs type annotations - https://mypy-boto3.readthedocs.io/en/latest/
from mypy_boto3_ec2 import EC2Client
from mypy_boto3_ec2.service_resource import EC2ServiceResource, Instance
from mypy_boto3_s3 import S3Client
from mypy_boto3_s3.service_resource import S3ServiceResource
from mypy_boto3_s3.type_defs import CreateBucketConfigurationTypeDef
from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table
from mypy_boto3_dynamodb.type_defs import AttributeDefinitionTypeDef, KeySchemaElementTypeDef
from mypy_boto3_logs import CloudWatchLogsClient

from ec2_metadata import is_aws, get_region

# A tuple avoid the risk of users mutating the value.
INSTANCE_STATES = ("pending", "running", "shutting-down", "stopped", "stopping", "terminated")


# https://stackoverflow.com/a/952952/245602
def _flatten(xss):
    return [x for xs in xss for x in xs]


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


# These "s3://..." URIs just seem to be an aws-cli thing - they're not used in boto.
def get_s3_uri(item):
    name = type(item).__name__
    if name == 's3.Bucket':
        return f"s3://{item.name}"
    elif name == 's3.Object':
        return f"s3://{item.bucket_name}/{item.key}"
    else:
        raise RuntimeError(f"unexpected type {type(item)}")


class BotoBasics:
    def __init__(self):
        self._botocore_session = botocore.session.get_session()
        self._set_region(self._botocore_session)

        self._session = boto3.session.Session(botocore_session=self._botocore_session)

        # As of Boto3 1.23.8, the default `defaults_mode` is still `legacy`.
        # See https://docs.aws.amazon.com/sdkref/latest/guide/feature-smart-config-defaults.html
        # noinspection PyArgumentList
        self._config = Config(defaults_mode="standard")
        self._ec2_resource = None
        self._s3_resource = None
        self._dynamodb_resource = None
        self._logs_client = None

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

            botocore_session.set_config_variable("region", get_region())

    def _get_or_create_client(self, field, name):
        return field if field is not None else self._session.client(name, config=self._config)

    def _get_or_create_resource(self, field, name):
        return field if field is not None else self._session.resource(name, config=self._config)

    def _get_ec2_client(self) -> EC2Client:
        return self._get_ec2_resource().meta.client

    def get_latest_image(self, name_pattern):
        images = self._get_ec2_client().describe_images(Filters=[{"Name": "name", "Values": [name_pattern]}])["Images"]
        return sorted(images, key=lambda item: item["CreationDate"])[-1]

    def _get_ec2_resource(self) -> EC2ServiceResource:
        self._ec2_resource = self._get_or_create_resource(self._ec2_resource, "ec2")
        return self._ec2_resource

    def create_instances(
        self,
        name,
        image_id,
        instance_type,
        security_group_name,
        iam_instance_profile=None,
        user_data=None,
        count=1,
        min_count=1,
        key_name=None,
        shutdown_behavior="terminate",
        spot=False
    ) -> List[Instance]:
        kwargs = {}
        if key_name is not None:
            kwargs["KeyName"] = key_name
        if iam_instance_profile is not None:
            kwargs["IamInstanceProfile"] = {"Name": iam_instance_profile}
        if spot:
            kwargs["InstanceMarketOptions"] = {"MarketType": "spot"}
        if user_data is not None:
            kwargs["UserData"] = user_data

        # Set the tag that's shown as the instance name in the EC2 dashboard.
        name_tag = {'ResourceType': 'instance', 'Tags': [{'Key': 'Name', 'Value': name}]}

        # noinspection PyTypeChecker
        return self._get_ec2_resource().create_instances(
            ImageId=image_id,
            InstanceType=instance_type,
            SecurityGroups=[security_group_name],
            InstanceInitiatedShutdownBehavior=shutdown_behavior,  # defaults to "stop" if not specified.
            TagSpecifications=[name_tag],
            MaxCount=count,
            MinCount=min_count,
            **kwargs
        )

    # Waits up to 200s (after which point it throws an exception) for the instances to come into existence.
    # Only once the instances exist can you call other methods like `describe_instances` (otherwise they'll
    # throw `InvalidInstanceID.NotFound`). Typically, the request itself introduces enough delay that the
    # instances exist by the time its received and the call returns within milliseconds.
    def wait_instances_exist(self, instance_id):
        waiter = self._get_ec2_client().get_waiter("instance_exists")
        waiter.wait(InstanceIds=instance_id)

    def terminate_instances(self, instance_ids):
        self._get_ec2_client().terminate_instances(InstanceIds=instance_ids)

    # This returns simple dicts of name/value pairs whereas `create_instances` returns instances of `Instance`.
    def describe_instances(self, instance_ids=None, filters: Optional[Dict[str, list]] = None) -> List[dict]:
        kwargs = {}
        if instance_ids is not None:
            kwargs["InstanceIds"] = instance_ids
        if filters is not None:
            kwargs["Filters"] = [{"Name": name, "Values": values} for name, values in filters.items()]
        reservations = self._get_ec2_client().describe_instances(**kwargs)["Reservations"]
        return _flatten([reservation["Instances"] for reservation in reservations])

    # Much more light-weight than `describe_instances` - this just returns status information.
    # Unlike `describe_instance`, this method returns nothing if the instance is not in running state.
    def describe_instance_status(self, instance_ids) -> List[dict]:
        return self._get_ec2_client().describe_instance_status(InstanceIds=instance_ids)["InstanceStatuses"]

    @property
    def ec2_exceptions(self):
        return self._get_ec2_client().exceptions

    def _get_s3_resource(self) -> S3ServiceResource:
        self._s3_resource = self._get_or_create_resource(self._s3_resource, "s3")
        return self._s3_resource

    def _get_s3_client(self) -> S3Client:
        return self._get_s3_resource().meta.client

    def create_bucket(self, name):
        return self._get_s3_resource().create_bucket(Bucket=name, CreateBucketConfiguration=self._bucket_config)

    @staticmethod
    def delete_bucket(bucket):
        # You have to delete a bucket's contents before you can delete it.
        bucket.objects.all().delete()
        bucket.delete()

    def get_bucket(self, name):
        return self._get_s3_resource().Bucket(name)

    # If you have large numbers of buckets then it would be much better to filter by tag (you can't filter by name).
    # And/or use a paginator. See https://stackoverflow.com/a/36044264/245602
    def list_buckets(self):
        return self._get_s3_resource().buckets.all()

    # Uses a paginator, so it can handle even frame counts greater than 1000.
    def list_objects(self, bucket_name, subdirectory=None) -> List[str]:
        kwargs = {}
        if subdirectory is not None:
            kwargs["Prefix"] = subdirectory + "/"
        paginator = self._get_s3_client().get_paginator("list_objects_v2")
        iterator = paginator.paginate(Bucket=bucket_name, **kwargs)
        # If there are no objects the iterator returns a single item that contains no "Contents" key.
        contents = _flatten([i["Contents"] for i in iterator if "Contents" in i])
        return [obj["Key"] for obj in contents]

    def _get_dynamodb_resource(self) -> DynamoDBServiceResource:
        self._dynamodb_resource = self._get_or_create_resource(self._dynamodb_resource, "dynamodb")
        return self._dynamodb_resource

    @property
    def dynamodb_exceptions(self):
        return self._get_dynamodb_resource().meta.client.exceptions

    # Creating a table can take 20s.
    def create_table(self, name, schema, defs):
        print(f"Creating table {name}...")
        table = self._get_dynamodb_resource().create_table(
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
        return self._get_dynamodb_resource().tables.all()

    def get_table(self, name):
        return self._get_dynamodb_resource().Table(name)

    def _get_logs_client(self) -> CloudWatchLogsClient:
        self._logs_client = self._get_or_create_client(self._logs_client, "logs")
        return self._logs_client

    @property
    def logs_exceptions(self):
        return self._get_logs_client().exceptions

    def _create_log_entity(self, f, fail_if_exists):
        try:
            f()
        except self.logs_exceptions.ResourceAlreadyExistsException as e:
            if fail_if_exists:
                raise e

    def create_log_group(self, name, retention_in_days=1, fail_if_exists=False):
        def create():
            self._get_logs_client().create_log_group(logGroupName=name)
            # The default is to retain log entries forever.
            self._get_logs_client().put_retention_policy(logGroupName=name, retentionInDays=retention_in_days)
        self._create_log_entity(create, fail_if_exists)

    def list_log_groups(self, prefix):
        return self._get_logs_client().describe_log_groups(logGroupNamePrefix=prefix)["logGroups"]

    def delete_log_group(self, name):
        self._get_logs_client().delete_log_group(logGroupName=name)

    def create_log_stream(self, group_name, stream_name, fail_if_exists=False):
        self._create_log_entity(
            lambda: self._get_logs_client().create_log_stream(logGroupName=group_name, logStreamName=stream_name),
            fail_if_exists
        )

    def put_log_event(self, group_name, stream_name, log_event, sequence_token):
        kwargs = {}
        # For the first message of a new stream, the sequence_token argument must be completely absent.
        if sequence_token is not None:
            kwargs["sequenceToken"] = sequence_token
        return self._get_logs_client().put_log_events(
            logGroupName=group_name,
            logStreamName=stream_name,
            logEvents=[log_event],
            **kwargs
        )["nextSequenceToken"]

    def filter_log_events(self, group_name, start_time, next_token=None):
        kwargs = {}
        if next_token is not None:
            kwargs["nextToken"] = next_token
        return self._get_logs_client().filter_log_events(logGroupName=group_name, startTime=start_time, **kwargs)
