from collections import Counter
from time import sleep

from boto_basics import BotoBasics
from datetime import datetime, timezone
from pathlib import Path

from config import get_config
from frame_table import FramesTable

# It takes about 30s for a typical instance to start (go from "pending" to "running" and a similar amount of
# time to go from "running" via "shutting-down" to "terminated"). So 15s seems a reasonable polling interval.
_POLLING_INTERVAL = 15

basics = BotoBasics()


def _get_latest_image_id(image_name_pattern):
    image = basics.get_latest_image(image_name_pattern)

    # Python's `fromisoformat` can handle '+00:00' but not 'Z'. Their documentation
    # suggests the 3rd party `dateutil` if you need complete ISO-8601 handling.
    created = datetime.fromisoformat(image["CreationDate"].replace("Z", "+00:00"))
    delta = datetime.now(timezone.utc) - created
    print(f"Using image {image['Description']} ({image['Name']})")
    print(f"Image created: {created} ({delta.days} days ago)")

    return image["ImageId"]


def _create_instances(
    instance_count,
    instance_name,
    image_name_pattern,
    instance_type,
    security_group_name,
    iam_instance_profile,
    user_data_filename
):
    image_id = _get_latest_image_id(image_name_pattern)

    user_data = Path(user_data_filename).read_text()

    # TODO: can I create the instance without any public IP at all?
    # Answer: no - it needs an IP to access the internet - otherwise you'd have to set up some form of VPN
    # (that does have a public IP) that can mediate between your instance and the public internet.
    # So if I got rid of the pip access I could probably get rid of the public IP as I wouldn't need public
    # internet access for anything else.

    instances = basics.create_instances(
        name=instance_name,
        image_id=image_id,
        instance_type=instance_type,
        security_group_name=security_group_name,
        iam_instance_profile=iam_instance_profile,
        user_data=user_data,
        count=instance_count,
        spot=True
    )
    instance_ids = [instance.instance_id for instance in instances]
    basics.wait_instances_exist(instance_ids)

    return instance_ids


# Monitor the instances, track their progress processing the frames and terminate them once completed.
def _manage_instances(instance_ids, frames_table):
    check_remaining = True
    prev_states = {}

    while True:
        descriptions = basics.describe_instances(instance_ids)
        states = {description["InstanceId"]: description["State"]["Name"] for description in descriptions}
        if states != prev_states:
            prev_states = states
            states_counter = Counter(states.values())
            print(f"{datetime.now()} Instances: {dict(states_counter)}")

            terminated = states_counter["terminated"]
            if terminated == len(instance_ids):
                print("All instances have been terminated")
                break

        if check_remaining and frames_table.get_remaining() == 0:
            check_remaining = False
            # At the end, some instances will be rendering frames that other workers have already completed.
            # Terminate these instances rather than waiting for them to complete their now redundant work.
            running = [instance_id for instance_id, state in states.items() if state == "running"]
            print(f"all frames have been rendered - terminating {len(running)} instances that are still running")
            basics.terminate_instances(running)

        sleep(_POLLING_INTERVAL)


def _download_results(bucket, output_dir):
    Path(output_dir).mkdir(exist_ok=True)

    keys = basics.list_objects(bucket.name, "frames")
    for key in keys:
        obj = bucket.Object(key)
        filename = key.split("/")[-1]
        obj.download_file(f"{output_dir}/{filename}")
        print(f"Downloaded {filename}")


def _delete_resources():
    # TODO: cleanup once done.
    pass


config = get_config("settings.ini")


def main():
    instance_count = config.getint("instance_count")
    instance_type = config.get("instance_type")
    image_name_pattern = config.get("image_name_pattern")
    security_group_name = config.get("security_group_name")
    iam_instance_profile = config.get("iam_instance_profile")

    job_id = "bb9138ab-8e5b-4a84-94f5-132de68a010d"
    user_data_filename = "user_data"
    output_dir = f"frames-{job_id}"

    # TODO: name will be the same for all workers - so the best you can do is include the job-id.
    instance_name = f"render-worker-{job_id}"

    def name(s):
        return f"render-job-{s}-{job_id}"

    db_name = name("dynamodb")
    frames_table = FramesTable(basics, db_name)
    bucket_name = name("bucket")
    bucket = basics.get_bucket(bucket_name)

    # ------------------------------------------------------------------

    instance_ids = _create_instances(
        instance_count,
        instance_name,
        image_name_pattern,
        instance_type,
        security_group_name,
        iam_instance_profile,
        user_data_filename
    )

    _manage_instances(instance_ids, frames_table)

    print(f"Saving frames to {output_dir}")
    _download_results(bucket, output_dir)

    # TODO: maybe this should be called at the level above, i.e. the level at which `bucket` etc. were created.
    _delete_resources()


if __name__ == "__main__":
    main()
