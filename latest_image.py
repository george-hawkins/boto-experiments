from collections import Counter
from time import sleep

from boto_basics import BotoBasics
from datetime import datetime, timezone
from pathlib import Path

# It takes about 30s for a typical instance to start (go from "pending" to "running" and a similar amount of
# time to go from "running" to "shutting-down" to "terminated" - so 15s is a reasonable polling interval.
_POLLING_INTERVAL = 15

basics = BotoBasics()


def main():
    # TODO: move these values into .ini.
    image = basics.get_latest_image("amzn2-ami-graphics-hvm-*")
    instance_type = "g4dn.xlarge"
    # image = basics.get_latest_image("amzn2-ami-kernel-*-hvm-*-x86_64-gp2")
    # instance_type = "t2.micro"

    # 'Z' is valid for UTC but `fromisoformat` can't handle it - the `datetime` documentation
    # recommends the 3rd party dateutil for more complete ISO-8601 handling.
    created = datetime.fromisoformat(image["CreationDate"].replace("Z", "+00:00"))
    delta = datetime.now(timezone.utc) - created
    image_id = image["ImageId"]

    print(f"Using image {image['Description']} ({image['Name']})")
    print(f"Image created: {created} ({delta.days} days ago)")

    # TODO: pass in "user_data" filename.
    user_data = Path("user_data").read_text()
    instance_count = 1
    security_group_name = "RenderJobWorkerSecurityGroup"
    iam_instance_profile = "RenderJobWorkerProfile5"

    # TODO: name will be the same for all workers - so the best you can do is include the job-id.
    job_id = "66589e20-e257-4f3a-b9f8-3f7d7a82aadf"
    instance_name = f"render-worker-{job_id}"

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

    prev_states = {}

    while True:
        descriptions = basics.describe_instances(instance_ids)
        states = {description["InstanceId"]: description["State"]["Name"] for description in descriptions}
        if states != prev_states:
            prev_states = states
            states_counter = Counter(states.values())
            print(f"{datetime.now()} Instances: {dict(states_counter)}")
            terminated = states_counter["terminated"]
            if terminated == instance_count:
                print("All instances have been terminated")
                break

        sleep(_POLLING_INTERVAL)


if __name__ == "__main__":
    main()
