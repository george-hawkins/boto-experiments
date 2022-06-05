import json
from os.path import isfile

# This file exists on Amazon Linux 2 and Ubuntu instances.
_INSTANCE_DATA = "/run/cloud-init/instance-data.json"

# Use to provide canned values when running locally.
_CANNED_INSTANCE_DATA = "canned-instance-data.json"


def is_aws():
    return isfile(_INSTANCE_DATA)


def _get_instance_data():
    return _INSTANCE_DATA if is_aws() else _CANNED_INSTANCE_DATA


# See https://cloudinit.readthedocs.io/en/latest/topics/instancedata.html
def _get_ec2_v1_metadata():
    with open(_get_instance_data(), "r") as read_file:
        return json.load(read_file)["v1"]


def get_instance_id():
    return _get_ec2_v1_metadata()["instance-id"]


def get_region():
    return _get_ec2_v1_metadata()["region"]
