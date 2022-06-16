import time
from collections import defaultdict
from datetime import datetime, timezone

from boto_basics import BotoBasics


# Derived from https://github.com/aws/aws-cli/blob/v2/awscli/customizations/logs/tail.py
class LogsRetriever:
    _START_OFFSET = 60  # Look at most 60s into the past when making the initial request for log entries.

    def __init__(self):
        self._next_token = None
        self.event_ids_per_timestamp = defaultdict(set)

        self._start_time = int((time.time() - self._START_OFFSET) * 1000)

    @staticmethod
    def to_datetime(millis_timestamp):
        return datetime.fromtimestamp(millis_timestamp / 1000.0, timezone.utc)

    @staticmethod
    def to_local_datetime_str(millis_timestamp, timespec="milliseconds"):
        dt = LogsRetriever.to_datetime(millis_timestamp)
        # This rather complicated conversion switches from UTC to local time and then drops the '+02:00' portion.
        return dt.astimezone(None).replace(tzinfo=None).isoformat(" ", timespec)

    def get_log_events(self, basics: BotoBasics, group_name):
        log_events = []

        response = basics.filter_log_events(group_name, self._start_time, self._next_token)

        for event in response["events"]:
            # Filter out event IDs that have already been seen.
            if event["eventId"] not in self.event_ids_per_timestamp[event["timestamp"]]:
                self.event_ids_per_timestamp[event["timestamp"]].add(event["eventId"])
                log_events.append(event)

        # Keep only IDs of the events with the newest timestamp.
        newest_timestamp = None
        if len(self.event_ids_per_timestamp) != 0:
            newest_timestamp = max(self.event_ids_per_timestamp.keys())
            ids = self.event_ids_per_timestamp[newest_timestamp]
            self.event_ids_per_timestamp = defaultdict(set, {newest_timestamp: ids})

        if "nextToken" in response:
            self._next_token = response["nextToken"]
        else:
            # Remove nextToken and update startTime for the next request with the timestamp of the newest event.
            if newest_timestamp is not None:
                self._start_time = newest_timestamp
            self._next_token = None

        return log_events
