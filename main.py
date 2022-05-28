import sys

from basics import BotoBasics
from cloud_watch_logger import CloudWatchLogger
from frame_table import FramesTable

basics = BotoBasics()

frames_table = FramesTable(basics, "Foo")


# Frame processing stub that "succeeds" 50% of the time.
def process_frame(num):
    from random import random
    success = random() < 0.5
    if success:
        frames_table.delete_frame(num)
        print(f"processed {num}")


def main():
    logger = CloudWatchLogger(basics, "foo-group", "foo-stream")
    from random import random
    logger.info("blah " + str(random()))
    logger.info("blah " + str(random()))
    logger.info("blah " + str(random()))
    sys.exit(0)

    frames_table.create(range(16))

    while True:
        num = frames_table.get_frame()
        if num is None:
            break
        print(num)
        process_frame(num)

    frames_table.delete()

    print("xxx")
    # bucket_name = str(uuid.uuid4())
    # bucket = basics.create_bucket(bucket_name)
    # obj = bucket.Object("xyz")
    # obj.put(Body="blah blah")
    # print(bucket_name)
    # ---
    # # A delete succeeds even if it doesn't match a row.
    # table.delete_item(Key={"filler": 0, "frame": 7})
    # row_count = table.scan(Select="COUNT", ConsistentRead=True)["Count"]
    # print(row_count)
    # # ---
    # # There's no way to just say "return me the first item that matches the filter", the `Limit` parameter
    # # limits the number of items _before_ filtering is applied.
    # items = table.scan(FilterExpression=Attr("in_progress").eq(1), ConsistentRead=True)["Items"]
    # print(items)
    # # ---
    # for i in items:
    #     table.delete_item(Key={"filler": 0, "frame": i["frame"]})


if __name__ == "__main__":
    main()
