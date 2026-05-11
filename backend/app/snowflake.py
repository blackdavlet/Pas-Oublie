import os
import time
import threading
from datetime import datetime, timezone


EPOCH = int(datetime(2023, 5, 29, 9, 40, 0, tzinfo=timezone.utc).timestamp() * 1000) #1685353200000

MACHINE_ID_BITS = 10
SEQUENCE_BITS = 12

MAX_MACHINE_ID = (1 << MACHINE_ID_BITS) - 1
MAX_SEQUENCE = (1 << SEQUENCE_BITS) - 1

MACHINE_ID_SHIFT = SEQUENCE_BITS
TIMESTAMP_SHIFT = MACHINE_ID_BITS + SEQUENCE_BITS

MACHINE_ID = int(os.environ.get("MACHINE_ID", 1)) & MAX_MACHINE_ID

_sequence = 0
_last_timestamp = -1
_lock = threading.Lock()

def _current_ms() -> int:
    return int(time.time() * 1000)

def generate_id() -> int:
    global _sequence, _last_timestamp

    with _lock:
        now = _current_ms()

        if now == _last_timestamp:
            _sequence = (_sequence + 1) & MAX_SEQUENCE
            if _sequence == 0:
                while now <= _last_timestamp:
                    now = _current_ms()

        else:
            _sequence = 0

        _last_timestamp = now

        return (
            ((now - EPOCH) << TIMESTAMP_SHIFT) |
            (MACHINE_ID << MACHINE_ID_SHIFT) |
            _sequence
        )


