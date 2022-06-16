from collections import Counter
from time import sleep

from boto_basics import BotoBasics
from datetime import datetime, timezone
from pathlib import Path

from log_retriever import LogsRetriever

# It takes about 30s for a typical instance to start (go from "pending" to "running" and a similar amount of
# time to go from "running" via "shutting-down" to "terminated"). So 10s seems a reasonable polling interval.
_POLLING_INTERVAL = 10

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


def create_instances(
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


# Monitor the instances, track their progress and terminate them once completed.
def monitor_and_terminate(group_name, instance_ids, is_finished):
    retriever = LogsRetriever()

    check_is_finished = True
    prev_states = {}

    while True:
        # Check if all instances have terminated - if so exit the loop.
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

        # Check if the job is finished - if so initiate the termination of still running instances.
        if check_is_finished and is_finished():
            check_is_finished = False
            # Aggressively terminate any instances that are not yet aware that ongoing work is redundant.
            running = [instance_id for instance_id, state in states.items() if state == "running"]
            print(f"Terminating {len(running)} instances that are still running")
            basics.terminate_instances(running)

        # Poll for log events from the workers.
        log_events = retriever.get_log_events(basics, group_name)
        for event in log_events:
            local_datetime = retriever.to_local_datetime_str(event['timestamp'])
            print(f"{local_datetime} {event['logStreamName']} {event['message']}")

        sleep(_POLLING_INTERVAL)
