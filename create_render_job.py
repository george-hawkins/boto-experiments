import argparse
import sys
from pathlib import Path
from string import Template

from uuid import uuid4

from boto_basics import BotoBasics, get_s3_uri
from cloud_watch_logger import CloudWatchLogger
from frame_table import FramesTable
from pack import pack_blend_file
from scene_attributes import get_scene_attributes
from worker_files import upload_worker_files

PACKED_BLEND_FILE = "packed.blend"
START_JOB = "start_job"
USER_DATA = "user_data"

basics = BotoBasics()
job_id = uuid4()


def name(s):
    return f"render-job-{s}-{job_id}"


def parse_args():
    # Start frame etc. are read from the .blend file - only use `--start` etc. if you want to override these.
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender-home", required=True, help="root directory of Blender installation")
    parser.add_argument("--start", type=int, help="start frame (inclusive)")
    parser.add_argument("--end", type=int, help="end frame (inclusive)")
    parser.add_argument("--step", type=int, help="step size from one frame to the next")
    parser.add_argument("--frames", help="comma separated list of frame numbers")
    parser.add_argument("--samples", help="number of samples to render for each picture")
    parser.add_argument("blend_file", help="the .blend file to be rendered")
    args = parser.parse_args()

    blender = f"{args.blender_home}/blender"
    blend_file = args.blend_file

    attrs = get_scene_attributes(blender, blend_file)

    samples = attrs["samples"] if args.samples is None else args.samples

    if args.frames is not None:
        # There seems to be no easy way to express this exclusivity with `ArgumentParser`.
        assert all(a is None for a in [args.start, args.end, args.step]), \
            "--frame cannot be used in combination with --start, --end or --step"
        frames = [int(s.strip()) for s in args.frames.split(',')]
    else:
        start = attrs["frame_start"]
        end = attrs["frame_end"]
        step = attrs["frame_step"]
        if args.start is not None:
            start = args.start
        if args.end is not None:
            end = args.end
        if args.step is not None:
            step = args.step
        frames = range(start, end + 1, step)

    return blender, blend_file, frames, samples


def frames_str(frames):
    if isinstance(frames, range):
        s = f"frames = {frames.start} to {frames.stop + 1} inclusive"
        return s if frames.step == 1 else f"{s}, steps = {frames.step}"
    else:
        return f"frames = {frames}"


def main():
    group_name = name("log-group")
    stream_name = Path(__file__).stem
    logger = CloudWatchLogger(basics, group_name, stream_name)

    print(f"Listen for log output with 'aws logs tail {group_name} --follow'")

    blender, blend_file, frames, samples = parse_args()

    logger.info(f".blend file = {blend_file}, {frames_str(frames)} and samples = {samples}")

    bucket_name = name("bucket")
    bucket = basics.create_bucket(bucket_name)

    def substitute(filename, **kwargs):
        template = Template(Path(f"{filename}.template").read_text())
        content = template.safe_substitute(kwargs)
        Path(filename).write_text(content)

    substitute(START_JOB, samples=samples, render_job_id=job_id)
    substitute(USER_DATA, render_job_id=job_id)

    pack_blend_file(blender, blend_file, PACKED_BLEND_FILE)

    upload_worker_files(bucket)

    logger.info(f"uploaded job files to {get_s3_uri(bucket)}")
    result_dir = bucket.Object("frames")
    logger.info(f"to sync results use 'aws s3 sync {get_s3_uri(result_dir)} {result_dir.key}'")

    db_name = name("dynamodb")
    frames_table = FramesTable(basics, db_name)

    frames_table.create(frames)

    logger.info(f"created DynamoDB table {db_name}")

    print("Job creation completed successfully")
    sys.exit(0)

    # Launch spot fleet.
    # Delete bucket etc. if not done by fleet.


if __name__ == "__main__":
    main()
