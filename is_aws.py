import urllib.request

# Instances running Amazon AMIs use Amazon DNS servers that resolve 'instance_data' to 169.254.169.254.
# But instances based on Ubuntu etc. do not.
_instance_data_ip = "169.254.169.254"

# noinspection HttpUrlsUsage
_metadata_url = f"http://{_instance_data_ip}/latest/meta-data"


def is_aws():
    try:
        with urllib.request.urlopen(f"{_metadata_url}/instance-id") as response:
            return response.status < 300
            pass
    except IOError:
        # Assume the error is a result of not being within the AWS environment.
        return False
