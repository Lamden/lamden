import threading
import time
import math

from datetime import datetime, timezone
from iso8601 import parse_date

VERSION = 1.0

def synchronized(fn):
    """Synchronization for object methods using self.lock"""

    def wrapper(self, *args, **kwargs):
        with self.lock:
            return fn(self, *args, **kwargs)
    return wrapper


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def nanos_to_iso8601(nanos: int) -> str:
    nanos_order = int(1e9)
    dt = datetime.fromtimestamp(nanos // nanos_order, tz=timezone.utc)
    return '{}.{:09.0f}Z'.format(
        dt.strftime('%Y-%m-%dT%H:%M:%S'),
        nanos % nanos_order)


def iso8601_to_nanos(s: str) -> int:
    last_dot = s.rindex('.')
    zone_sep = s.index('Z') if 'Z' in s else s.index('+')
    decimals_str = s[last_dot:zone_sep]
    s_clean = s.replace(decimals_str, '')
    dt = parse_date(s_clean)
    # rounding discards nothing, just to int
    seconds = round(dt.timestamp())
    decimals_str = decimals_str.replace('.', '').ljust(9, '0')
    full_str = str(seconds) + decimals_str
    return int(full_str)

class HLC:
    n_bits = 64
    n_bytes = int(n_bits / 8)
    millis_bits = 43
    logical_bits = 16
    compatibility_bits = 64 - millis_bits - logical_bits
    logical_mask = (1 << logical_bits) - 1
    millis_mask = ((1 << (millis_bits + logical_bits)) - 1) ^ logical_mask
    compatibility_mask = (1 << n_bits) - 1 ^ millis_mask ^ logical_mask
    byteorder = 'little'

    def __init__(self, nanos: int = 0, logical: int = 0):
        self.lock = threading.Lock()
        self._set(nanos, logical)

    @classmethod
    def get_nanoseconds(cls):
        return int(time.time() * 1000000000)

    @classmethod
    def from_now(cls):
        return cls(nanos=cls.get_nanoseconds())

    @classmethod
    def from_str(cls, s: str):
        spl = s.split('_')
        nanos = iso8601_to_nanos(spl[0])
        logical = int(spl[1]) if len(spl) > 1 else 0
        return cls(nanos, logical)

    @classmethod
    def from_bytes(cls, bs: bytes):
        """Bytes repesentation must have 64 bits (8 bytes) in little endian.
        Thier meaning 'from left' (smallest indices):
        5 bits empty (for compatibility), 43 bits for timestamp in millis, 16 bits for the logical.
        This keeps only millis precision as per standard.
        """
        assert len(bs) == cls.n_bytes
        number = int.from_bytes(bs, byteorder=cls.byteorder)
        millis_part = number & cls.millis_mask
        millis = millis_part >> cls.logical_bits
        logical = number & cls.logical_mask
        return cls(int(millis * 1e6), logical)

    def to_bytes(self):
        compatibility_part = self.compatibility_mask
        millis_part = self.millis << self.logical_bits
        number = compatibility_part | millis_part | self.logical
        return number.to_bytes(self.n_bytes, byteorder=self.byteorder)

    @property
    def nanos(self):
        return self._nanos

    @property
    def millis(self):
        return math.ceil(self._nanos / 1e6)

    @property
    def logical(self):
        return self._logical

    def set_nanos(self, nanos: int):
        "Takes unix epoch nanoseconds"
        self._set(nanos, 0)

    def _set(self, nanos: int, logical: int):
        if nanos / 1e6 >= 2**self.millis_bits:
            raise ValueError(
                'Time in milliseconds cannot be larger than 43 bits')
        if logical >= 2**self.logical_bits:
            raise ValueError('Logical time cannot be larger than 16 bits')
        self._nanos = nanos
        self._logical = logical

    def tuple(self):
        """Returns a tuple of <nanoseconds since unix epoch, logical clock>"""
        return self.nanos, self.logical

    def __str__(self):
        return '{}_{}'.format(nanos_to_iso8601(self.nanos), self.logical)

    def __repr__(self):
        return 'HLC(nanos={},logical={})'.format(self.nanos, self.logical)

    def __eq__(self, other):
        return self.tuple() == other.tuple()

    def __lt__(self, other):
        return self.tuple() < other.tuple()

    @synchronized
    def sync(self):
        "Used to refresh the clock"
        wall = HLC.from_now()
        cnanos, clogical = self.tuple()
        wnanos, _ = wall.tuple()
        nanos = max(cnanos, wnanos)
        if nanos == cnanos:
            logical = clogical + 1
        else:
            logical = 0
        self._set(nanos, logical)

    @synchronized
    def merge(self, event, sync: bool = True):
        "To be used on receiving an event"
        cnanos, clogical = self.tuple()
        enanos, elogical = event.tuple()
        wall = HLC.from_now()
        wnanos, _ = wall.tuple()
        nanos = max(cnanos, enanos, wnanos)
        if nanos == enanos and nanos == cnanos:
            logical = max(clogical, elogical) + 1
        elif nanos == cnanos:
            logical = clogical + 1
        elif nanos == enanos:
            logical = elogical + 1
        else:
            logical = 0
        self._set(nanos, logical)
