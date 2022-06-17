import json
from os.path import isfile
from pathlib import Path

# This file exists on both Amazon Linux 2 and Ubuntu EC2 instances.
_INSTANCE_DATA = "/run/cloud-init/instance-data.json"

# Use to provide canned values when running locally.
_CANNED_INSTANCE_DATA = {
    "instance-id": "i-0c146a607fb0a8e64",
    "region": "eu-central-1"
}


def is_aws():
    return isfile(_INSTANCE_DATA)


# See https://cloudinit.readthedocs.io/en/latest/topics/instancedata.html
def _get_ec2_v1_metadata():
    return json.loads(Path(_INSTANCE_DATA ).read_text())["v1"] if is_aws() else _CANNED_INSTANCE_DATA


def get_instance_id():
    return _get_ec2_v1_metadata()["instance-id"]


def get_region():
    return _get_ec2_v1_metadata()["region"]
