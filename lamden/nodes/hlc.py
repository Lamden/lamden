from lamden.hlcpy import HLC
from lamden.logger.base import get_logger

class HLC_Clock():
    def __init__(self, processing_delay=3):
        self.hlc_clock = HLC()
        self.hlc_clock.sync()

        self.processing_delay = processing_delay

        self.log = get_logger("HLC_CLOCK")

    def get_new_hlc_timestamp(self):
        self.hlc_clock.sync()
        return str(self.hlc_clock)

    def timestamp_to_hlc(self, timestamp):
        return HLC.from_str(timestamp)

    def merge_hlc_timestamp(self, event_timestamp):
        self.hlc_clock.merge(self.timestamp_to_hlc(event_timestamp))

    def check_timestamp_age(self, timestamp):
        # Convert timestamp to HLC clock then to nanoseconds
        temp_hlc = self.timestamp_to_hlc(timestamp)
        timestamp_nanoseconds, _ = temp_hlc.tuple()

        # sync out clock and then get its nanoseconds
        self.hlc_clock.sync()
        internal_nanoseconds, _ = self.hlc_clock.tuple()

        # Return the difference
        return internal_nanoseconds - timestamp_nanoseconds

    def get_nanos(self, timestamp):
        # Convert timestamp to HLC clock then to nanoseconds
        temp_hlc = self.timestamp_to_hlc(timestamp)
        timestamp_nanoseconds, _ = temp_hlc.tuple()
        return timestamp_nanoseconds

    def check_expired(self, timestamp):
        age = self.check_timestamp_age(timestamp)
        return age >= (self.processing_delay * 1000000000)