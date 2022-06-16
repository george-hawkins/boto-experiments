from boto_basics import BotoBasics
from mypy_boto3_logs.type_defs import InputLogEventTypeDef
from datetime import datetime, timezone


class CloudWatchLogger:
    _MAX_RETRIES = 2

    def __init__(self, basics: BotoBasics, group_name, stream_name):
        self._basics = basics
        self._group_name = group_name
        self._stream_name = stream_name
        self._sequence = None
        basics.create_log_group(group_name)
        basics.create_log_stream(group_name, stream_name)

    # To tail these entries, use 'aws logs tail <group-name> --follow'.
    def info(self, message):
        # datatime.utcnow() doesn't do what you might expect - https://stackoverflow.com/a/61049837/245602
        millis = int(datetime.now(timezone.utc).timestamp() * 1000)
        event = InputLogEventTypeDef(timestamp=millis, message=message)
        retries = 0
        while retries <= self._MAX_RETRIES:
            try:
                self._sequence = self._basics.put_log_event(self._group_name, self._stream_name, event, self._sequence)
                return
            except self._basics.logs_exceptions.InvalidSequenceTokenException as e:
                self._sequence = e.response["expectedSequenceToken"]
                retries += 1
