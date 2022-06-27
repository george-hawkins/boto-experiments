from collections import Counter
from time import sleep

from botocore.utils import parse_timestamp

from datetime import datetime, timezone
from pathlib import Path

from boto_basics import BotoBasics
from log_retriever import LogsRetriever

# It takes about 30s for a typical instance to start (go from "pending" to "running" and a similar amount of
# time to go from "running" via "shutting-down" to "terminated"). So 10s seems a reasonable polling interval.
_POLLING_INTERVAL = 10


def _get_latest_image_id(basics, image_name_pattern):
    image = basics.get_latest_image(image_name_pattern)

    # For some requests botocore handles the parsing to datetime for others you have to do it yourself.
    created = parse_timestamp(image["CreationDate"])
    delta = datetime.now(timezone.utc) - created
    print(f"Using image {image['Description']} ({image['Name']})")
    print(f"Image created: {created} ({delta.days} days ago)")

    return image["ImageId"]


def create_instances(
    basics: BotoBasics,
    instance_count,
    instance_name,
    image_name_pattern,
    instance_type,
    security_group_name,
    key_name,
    iam_instance_profile,
    user_data_filename
):
    image_id = _get_latest_image_id(basics, image_name_pattern)

    user_data = Path(user_data_filename).read_text()

    instances = basics.create_instances(
        name=instance_name,
        image_id=image_id,
        instance_type=instance_type,
        security_group_name=security_group_name,
        key_name=key_name,
        iam_instance_profile=iam_instance_profile,
        user_data=user_data,
        count=instance_count,
        spot=True
    )

    availability_zone = {instance.placement["AvailabilityZone"] for instance in instances}

    assert len(availability_zone) == 1, f"expected one availability zone, found {availability_zone}"

    availability_zone = next(iter(availability_zone))

    print(f"Availability zone: {availability_zone}")

    instance_ids = [instance.instance_id for instance in instances]
    basics.wait_instances_exist(instance_ids)

    return instance_ids, availability_zone


def _report_price_guesstimate(
    basics: BotoBasics,
    instance_type,
    instance_count,
    availability_zone,
    start_time,
    end_time
):
    running_time = end_time - start_time
    total_time = running_time * instance_count
    total_secs = total_time.total_seconds()
    total_mins = total_time.total_seconds() / 60

    spot_price_history = basics.describe_spot_price_history(instance_type, availability_zone, start_time, end_time)
    spot_price_history = [(item["Timestamp"], float(item["SpotPrice"])) for item in spot_price_history]
    prices = {item[1] for item in spot_price_history}

    # This probably almost never happens - if it does then the price calculation needs to be made smarter.
    if len(prices) > 1:
        print(f"Prices changed over the time period - the price history is {spot_price_history}")

    # For the moment, always use the worst price, rather than trying something more complex.
    max_price = max(prices)

    price = max_price * total_secs / 3600

    print(f"{instance_count} instances ran for ([days, ] h:m:s): {str(running_time)}")
    print(f"The spot price during this period was at most US${max_price:.2f} per hour")
    print(f"At that price, the total of {total_mins:.3f} minutes of EC2 instance time costs US${price:.2f}")


# Monitor the instances, track their progress and terminate them once completed.
def monitor_and_terminate(basics: BotoBasics, group_name, instance_type, instance_ids, availability_zone, is_finished):
    start_time = datetime.now()

    retriever = LogsRetriever()

    check_is_finished = True
    prev_states = {}

    while True:
        # Poll for log events from the workers and print them before anything else otherwise, the timestamps
        # of these already occurred remote events will mix oddly with local timestamps generated below.
        log_events = retriever.get_log_events(basics, group_name)
        for event in log_events:
            local_datetime = retriever.to_local_datetime_str(event["timestamp"])
            print(f"{local_datetime} {event['logStreamName']} {event['message']}")

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

        sleep(_POLLING_INTERVAL)

    _report_price_guesstimate(basics, instance_type, len(instance_ids), availability_zone, start_time, datetime.now())
