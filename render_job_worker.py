import argparse
import os

from boto_basics import BotoBasics, get_s3_uri
from cloud_watch_logger import CloudWatchLogger
from ec2_metadata import get_instance_id
from frame_table import FramesTable
from render import render_blend_file_frame

PACKED_BLEND_FILE = "packed.blend"

basics = BotoBasics()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blender-home", default="blender", help="root directory of Blender installation")
    parser.add_argument("--samples", required=True, help="number of samples to render for each picture")
    parser.add_argument("--render-job-id", required=True, help="render job UUID")
    args = parser.parse_args()

    blender = f"{args.blender_home}/blender"

    return blender, args.samples, args.render_job_id


def main():
    blender, samples, job_id = parse_args()

    def name(s):
        return f"render-job-{s}-{job_id}"

    group_name = name("log-group")
    stream_name = get_instance_id()
    logger = CloudWatchLogger(basics, group_name, stream_name)
    logger.info("job started")

    bucket_name = name("bucket")
    bucket = basics.get_bucket(bucket_name)

    db_name = name("dynamodb")
    frames_table = FramesTable(basics, db_name)

    while True:
        frame = frames_table.get_frame()
        if frame is None:
            break
        logger.info(f"rendering frame {frame}")
        output_file = render_blend_file_frame(blender, PACKED_BLEND_FILE, samples, frame)
        basename = os.path.basename(output_file)
        s3_output_file = bucket.Object(f"frames/{basename}")
        s3_output_file.upload_file(output_file)
        os.unlink(output_file)
        frames_table.delete_frame(frame)
        logger.info(f"completed and uploaded {get_s3_uri(s3_output_file)}")


if __name__ == "__main__":
    main()
