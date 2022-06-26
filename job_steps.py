import json
from pathlib import Path
from string import Template

from mypy_boto3_s3.service_resource import Bucket

from boto_basics import get_s3_uri
from frames_table import FramesTable

USER_DATA = "user_data"

_START_JOB = "start_job"
_WORKER_FILES = "json_files/worker_files.json"
_TEMPORARY_FILES = "json_files/temporary_files.json"


def _substitute(filename, **kwargs):
    template = Template(Path(f"templates/{filename}").read_text())
    # With `safe_substitution`, you don't have to escape things starting with '$' that aren't being replaced.
    content = template.safe_substitute(kwargs)
    Path(filename).write_text(content)


def create_worker_files(job_id, bucket_name, file_store, blender_archive, samples, motion_blur):
    motion_blur_condition = "enable" if motion_blur else "disable"
    _substitute(
        _START_JOB,
        file_store=file_store,
        blender_archive=blender_archive,
        samples=samples,
        motion_blur_condition=motion_blur_condition,
        render_job_id=job_id
    )
    _substitute(USER_DATA, bucket_name=bucket_name)


def delete_temporary_files():
    filenames = json.loads(Path(_TEMPORARY_FILES).read_text())
    for filename in filenames:
        Path(filename).unlink(missing_ok=True)
    print("Deleted temporary files")


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

    return len(keys)


def download_results(basics, job_id, bucket, remote_dir):
    output_dir = f"results/{job_id}"
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    keys = basics.list_objects(bucket.name, remote_dir)
    count = _download_objects(bucket, keys, output_dir)

    print(f"Downloaded {count} files to {output_dir}")

    return count
