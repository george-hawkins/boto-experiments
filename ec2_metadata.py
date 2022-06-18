import json
from os.path import isfile
from pathlib import Path

import botocore.session

# This file exists on both Amazon Linux 2 and Ubuntu EC2 instances.
_INSTANCE_DATA = "/run/cloud-init/instance-data.json"

_CANNED_INSTANCE_DATA = None


def _create_canned_instance_data(region):
    return {
        "instance-id": "i-0c146a607fb0a8e64",
        "region": region
    }


# Use to provide canned values when running locally.
def _get_canned_instance_data():
    global _CANNED_INSTANCE_DATA
    if _CANNED_INSTANCE_DATA is None:
        region = botocore.session.get_session().get_config_variable("region")
        if region is None:
            raise RuntimeError("cannot determine region")
        _CANNED_INSTANCE_DATA = _create_canned_instance_data(region)
    return _CANNED_INSTANCE_DATA


def is_aws():
    return isfile(_INSTANCE_DATA)


# See https://cloudinit.readthedocs.io/en/latest/topics/instancedata.html
def _get_ec2_v1_metadata():
    return json.loads(Path(_INSTANCE_DATA).read_text())["v1"] if is_aws() else _get_canned_instance_data()


def get_instance_id():
    return _get_ec2_v1_metadata()["instance-id"]


def get_region():
    return _get_ec2_v1_metadata()["region"]
