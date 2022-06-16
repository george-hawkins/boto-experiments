import json
from pathlib import Path
from string import Template

from mypy_boto3_s3.service_resource import Bucket

from boto_basics import get_s3_uri
from frames_table import FramesTable

USER_DATA = "user_data"

_START_JOB = "start_job"
_WORKER_FILES = "worker_files.json"


def create_worker_files(job_id, bucket_name, file_store, blender_archive, samples, motion_blur):
    def substitute(filename, **kwargs):
        template = Template(Path(f"{filename}.template").read_text())
        # With `safe_substitution`, you don't have to escape things starting with '$' that aren't being replaced.
        content = template.safe_substitute(kwargs)
        Path(filename).write_text(content)

    motion_blur_condition = "enable" if motion_blur else "disable"
    substitute(
        _START_JOB,
        file_store=file_store,
        blender_archive=blender_archive,
        samples=samples,
        motion_blur_condition=motion_blur_condition,
        render_job_id=job_id
    )
    substitute(USER_DATA, bucket_name=bucket_name)


def upload_worker_files(bucket: Bucket):
    filenames = json.loads(Path(_WORKER_FILES).read_text())
    for filename in filenames:
        bucket.upload_file(filename, filename)
    print(f"Uploaded job files to {get_s3_uri(bucket)}")


def create_db_table(basics, table_name, frames):
    frames_table = FramesTable(basics, table_name)
    frames_table.create(frames)
    print(f"Created DynamoDB table {table_name}")
    return frames_table


def _download_objects(bucket, keys, output_dir):
    for key in keys:
        obj = bucket.Object(key)
        filename = key.split("/")[-1]
        obj.download_file(f"{output_dir}/{filename}")
        print(f"Downloaded {filename}")


def download_results(basics, job_id, bucket, remote_dir):
    output_dir = f"results/{job_id}"
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    keys = basics.list_objects(bucket.name, remote_dir)
    _download_objects(bucket, keys, output_dir)

    print(f"Downloaded all results to {output_dir}")
