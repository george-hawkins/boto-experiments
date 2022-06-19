from boto_basics import BotoBasics
from boto_basics import create_key_schema_element as table_key
from boto_basics import create_attribute_definition as table_attr

from boto3.dynamodb.conditions import Attr


class FramesTable:
    _MAX_IN_PROGRESS = 4

    def __init__(self, basics: BotoBasics, name):
        self._basics = basics
        self._table = basics.get_table(name)
        self._in_progress = 0

    def create(self, r):
        # The unsorted "HASH" part of the key is mandatory, but we really only want the optional sorted "RANGE" part.
        self._table = self._basics.create_table(
            self._table.table_name,
            [table_key("filler", "HASH"), table_key("frame", "RANGE")],
            [table_attr("filler", "N"), table_attr("frame", "N")]
        )
        with self._table.batch_writer() as batch:
            for frame in r:
                batch.put_item({
                    "filler": 0,
                    "frame": frame,
                    "in_progress": 0
                })

    def delete(self):
        self._basics.delete_table(self._table)

    def get_remaining(self):
        return self._table.scan(Select="COUNT", ConsistentRead=True)["Count"]

    def delete_frame(self, num):
        self._table.delete_item(Key={"filler": 0, "frame": num})

    def _acquire(self, num, current):
        try:
            # I'm not sure why even literals, like 1, have to be specified as `ExpressionAttributeValues`.
            self._table.update_item(
                Key={"filler": 0, "frame": num},
                UpdateExpression="ADD in_progress :one",
                ConditionExpression="in_progress = :current",
                ExpressionAttributeValues={":one": 1, ":current": current}
            )
            return True
        except self._basics.dynamodb_exceptions.ConditionalCheckFailedException:
            # If the conditional check failed then someone else beat you to updating the value.
            return False

    def get_frame(self):
        while self._in_progress < self._MAX_IN_PROGRESS:
            items = self._table.scan(
                FilterExpression=Attr("in_progress").eq(self._in_progress),
                ConsistentRead=True
            )["Items"]
            for i in items:
                frame = i["frame"]
                if self._acquire(i["frame"], i["in_progress"]):
                    return frame
            self._in_progress += 1
        return None
