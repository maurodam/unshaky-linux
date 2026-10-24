"""Debounce physical key cycles without delaying accepted input."""


class Debouncer:
    def __init__(self):
        self.released = {}
        self.blocked = set()
        self.down = set()
        self.dismissed = 0

    def accept(self, code, value, timestamp, delay_ms, aggressive=False):
        if value == 1:
            if code in self.down or code in self.blocked:
                return False
            last = self.released.get(code)
            # evdev timestamps have microsecond precision. Avoid floating-point
            # subtraction rejecting a press exactly at the configured boundary.
            elapsed_us = None if last is None else round((timestamp - last) * 1_000_000)
            if delay_ms and elapsed_us is not None and 0 <= elapsed_us < delay_ms * 1000:
                self.blocked.add(code)
                self.dismissed += 1
                return False
            self.down.add(code)
            return True
        if value == 0:
            if code in self.blocked:
                self.blocked.remove(code)
                if aggressive:
                    self.released[code] = timestamp
                return False
            if code not in self.down:
                return False
            self.down.remove(code)
            self.released[code] = timestamp
            return True
        return code in self.down and code not in self.blocked
