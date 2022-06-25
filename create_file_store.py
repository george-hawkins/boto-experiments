from uuid import uuid4

from boto_basics import BotoBasics, get_s3_uri

basics = BotoBasics()


def main():
    bucket_name = f"render-job-file-store-{uuid4()}"
    bucket = basics.create_bucket(bucket_name)

    print(f"Created {get_s3_uri(bucket)}")
    print(f"To copy files there use 'aws s3 cp <filename> {get_s3_uri(bucket)}'")


if __name__ == "__main__":
    main()
