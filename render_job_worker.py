import os

from boto_basics import BotoBasics, get_s3_uri
from cloud_watch_logger import CloudWatchLogger
from config import get_config
from ec2_metadata import get_instance_id
from frame_table import FramesTable
from render import render_blend_file_frame

basics = BotoBasics()

config = get_config("render_job_worker.ini")

blender = f"{config['blender_home']}/blender"
samples = config["samples"]

job_id = config["job_id"]


def name(s):
    return f"render-job-{s}-{job_id}"


def main():
    group_name = name("log-group")
    stream_name = get_instance_id()
    logger = CloudWatchLogger(basics, group_name, stream_name)

    # TODO: get rid of this copying - it's done externally.
    bucket_name = name("bucket")
    bucket = basics.get_bucket(bucket_name)
    blend_file = "packed.blend"
    bucket.download_file(Key=blend_file, Filename=blend_file)

    db_name = name("dynamodb")
    frames_table = FramesTable(basics, db_name)

    while True:
        frame = frames_table.get_frame()
        if frame is None:
            break
        logger.info(f"rendering frame {frame}")
        output_file = render_blend_file_frame(blender, blend_file, samples, frame)
        basename = os.path.basename(output_file)
        s3_output_file = bucket.Object(f"frames/{basename}")
        s3_output_file.upload_file(output_file)
        os.unlink(output_file)
        frames_table.delete_frame(frame)
        logger.info(f"completed and uploaded {get_s3_uri(s3_output_file)}")


if __name__ == "__main__":
    main()
