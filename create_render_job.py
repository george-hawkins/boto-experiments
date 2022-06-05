import argparse
import os
import sys
import tempfile
from pathlib import Path

from uuid import uuid4

from basics import BotoBasics, get_s3_uri
from cloud_watch_logger import CloudWatchLogger
from config import get_config
from frame_table import FramesTable
from pack import pack_blend_file

basics = BotoBasics()
job_id = uuid4()


def name(s):
    return f"render-job-{s}-{job_id}"


config = get_config("create_render_job.ini")

blender = f"{config['blender_home']}/blender"


# Returns a copy of the original .blend file with all resources packed into it.
def get_packed_blend_file(original_blend_file):
    fd, path = tempfile.mkstemp()
    os.close(fd)
    pack_blend_file(blender, original_blend_file, path)
    return path


def get_frame_iter(args):
    if args.frames is not None:
        return [int(s.strip()) for s in args.frames.split(',')]
    elif args.end is not None:
        start = args.start if args.start is not None else 1
        return range(start, args.end + 1)
        pass
    else:
        raise RuntimeError("either --end or --frames must be specified")


def main():
    # See https://docs.python.org/3/howto/argparse.html
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, help="start frame (inclusive)")
    parser.add_argument("--end", type=int, help="end frame (inclusive)")
    parser.add_argument("--frames", help="comma separated list of frame numbers")
    parser.add_argument("blend_file", help="the .blend file to be rendered")
    args = parser.parse_args()

    group_name = name("log-group")
    stream_name = Path(__file__).stem
    logger = CloudWatchLogger(basics, group_name, stream_name)

    print(f"Listen for log output with 'aws logs tail {group_name} --follow'")

    frame_iter = get_frame_iter(args)
    packed_blend_file = get_packed_blend_file(args.blend_file)

    bucket_name = name("bucket")
    bucket = basics.create_bucket(bucket_name)
    s3_blend_file = bucket.Object("packed.blend")

    s3_blend_file.upload_file(packed_blend_file)

    os.unlink(packed_blend_file)

    logger.info(f"uploaded {get_s3_uri(s3_blend_file)}")
    result_dir = bucket.Object("frames")
    logger.info(f"to sync results use 'aws s3 sync {get_s3_uri(result_dir)} {result_dir.key}'")

    db_name = name("dynamodb")
    frames_table = FramesTable(basics, db_name)

    frames_table.create(frame_iter)

    logger.info(f"created DynamoDB table {db_name}")

    sys.exit(0)

    # Create a bucket and copy .blend file to "packed.blend" there.
    # Create log group and log frame count and bucket name.
    # Create DB
    # Create results directory on bucket.
    # Launch spot fleet
    # Sync results to local
    # Delete bucket (and DB if not done by fleet).


if __name__ == "__main__":
    main()
