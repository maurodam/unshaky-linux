"""Bounded, thread-safe session history of rejected key presses."""
from collections import deque
from datetime import datetime
from threading import Lock


class EventLog:
    def __init__(self, limit=1000):
        self.limit = limit
        self._rows = deque(maxlen=limit)
        self._lock = Lock()
        self._revision = 0

    def append(self, key, code, device, elapsed_ms, delay_ms):
        row = (datetime.now().astimezone().isoformat(timespec='milliseconds'),
               str(key), str(code), str(device), f'{elapsed_ms:.2f}', str(delay_ms))
        with self._lock:
            self._rows.append(row)
            self._revision += 1

    def snapshot(self):
        with self._lock:
            return self._revision, tuple(self._rows)

    def clear(self):
        with self._lock:
            self._rows.clear()
            self._revision += 1
