import json

from mypy_boto3_s3.service_resource import Bucket

_WORKER_FILES = "worker_files.json"


def _load_file_list():
    with open(_WORKER_FILES, "r") as read_file:
        return json.load(read_file)


def upload_worker_files(bucket: Bucket):
    for filename in _load_file_list():
        bucket.upload_file(filename, filename)
