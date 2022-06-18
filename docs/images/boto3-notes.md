Boto3 notes
===========

This page contains miscellaneous notes made while using [Boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html) for the first time.

Get the region locally or on EC2
--------------------------------

In the end I went for a different approach to getting the current region (see `ec2_metadata.py`) but you can do it using the class `IMDSRegionProvider` (that does the Python equivalent of `curl http://instance-data/`).

```
import boto3

session = boto3.session.Session()
current_region = session.region_name

if current_region is None:
    from botocore.utils import IMDSRegionProvider
    import botocore.session

    imds_region_provider = IMDSRegionProvider(session=botocore.session.get_session())
    current_region=imds_region_provider.provide()

print(current_region)
```

All `session.region_name` does is get the `region` value from `~/.aws/config` or `AWS_DEFAULT_REGION`.

On an EC2 instance with no `~/.aws/config`, it'll return `None`.

In that situation, `IMDSRegionProvider` will do the equivalent of `curl http://instance-data/latest/meta-data/placement/availability-zone/` (and removes the trailing zone character to get the region, e.g. `eu-central-1c` becomes `eu-central-1`).

Write to an existing bucket from on EC2
---------------------------------------

For an instance that's got the necessary IAM role (as described above):

```
import boto3
from botocore.config import Config

# As of Boto3 1.23.8, the default `defaults_mode` is still `legacy`.
# See https://docs.aws.amazon.com/sdkref/latest/guide/feature-smart-config-defaults.html
config = Config(defaults_mode="standard")
s3_resource = boto3.resource("s3", config=config)

# This is a bucket I created previously.
bucket = s3_resource.Bucket(name="97e1721f-caf9-4729-9aa2-e62ab5c3991c")

obj = bucket.Object("my_first_file")

obj.put(Body="foo bar")

print("Success")
```

DynamoDB filtering
------------------

Deleting items that match a filter:

```
items = table.scan(FilterExpression=Attr("in_progress").eq(1), ConsistentRead=True)["Items"]
for i in items:
    table.delete_item(Key={"filler": 0, "frame": i["frame"]})
```

You can filter for something but there's no way to just say "return me the first item that matches the filter". The `Limit` parameter limits the number of items _before_ the filtering is applied - i.e. there might be many rows that would match your filter criteria but if you set `Limit` to 1 it might choose 1 row that didn't match and then, once your filter was applied, you'd get no row back.

Spot instance configuration
---------------------------

The documentation for the _instance market options_ that are used to configure a spot request aren't very well documented - the best description seems to be in the boto3 API reference documentation for [`run_instances`](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.run_instances).

```
InstanceMarketOptions={
    'MarketType': 'spot',
    'SpotOptions': {
        'MaxPrice': 'string',
        'SpotInstanceType': 'one-time'|'persistent',
        'BlockDurationMinutes': 123,
        'ValidUntil': datetime(2015, 1, 1),
        'InstanceInterruptionBehavior': 'hibernate'|'stop'|'terminate'
    }
}
```

`MaxPrice` defaults to the on-demand price if not specified. `SpotInstanceType` defaults to `one-time`, `BlockDuration` is deprecated, `ValidUntil` can't be used with `one-time` and `InstanceInterruptionBehavior` defaults to and has to be `terminate` for `one-time`.

So simply specifying `MarketType` is enough if you just want `one-time` behavior and are happy to pay the on-demand price in the worst case.

The documentation doesn't say that `SpotInstanceType` defaults to `one-time` but you can see this is the case, if you e.g. just specify `MarketType=spot` and nothing else, and then look at the _Spot Requests_ in the EC2 dashboard - there you see "Persistence: one-time".

