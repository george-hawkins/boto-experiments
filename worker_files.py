import json
from pathlib import Path

from mypy_boto3_s3.service_resource import Bucket

_WORKER_FILES = "worker_files.json"


def upload_worker_files(bucket: Bucket):
    filenames = json.loads(Path(_WORKER_FILES).read_text())
    for filename in filenames:
        bucket.upload_file(filename, filename)
