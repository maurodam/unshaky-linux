"""Unprivileged evdev/uinput worker. Requires device permissions, never root GUI."""
import selectors
import fcntl
import struct
import threading
import time
from glob import glob
from evdev import InputDevice, UInput, ecodes as E
from .filter import Debouncer
from .eventlog import EventLog

PREFIX = 'Unshaky Linux: '


def set_monotonic_clock(dev):
    # Linux input.h: EVIOCSCLOCKID = _IOW('E', 0xa0, int).
    # python-evdev does not expose InputDevice.set_clockid().
    fcntl.ioctl(dev.fd, 0x400445A0, struct.pack('i', time.CLOCK_MONOTONIC))


class Worker(threading.Thread):
    def __init__(self, config):
        super().__init__(daemon=True)
        self.config = config
        self.stop_event = threading.Event()
        self.status = 'Waiting for keyboards'
        self.dismissed = 0
        self.devices = {}
        self.selector = selectors.DefaultSelector()
        self.log = EventLog()

    def accept_key(self, dev, debounce, event):
        config = self.config
        delay = config.get('keys', {}).get(str(event.code), config['delay_ms'])
        previous_count = debounce.dismissed
        accepted = debounce.accept(event.code, event.value, event.timestamp(),
                                   delay if config['enabled'] else 0,
                                   aggressive=config.get('aggressive', False))
        if debounce.dismissed > previous_count:
            self.log.append(E.KEY.get(event.code, str(event.code)), event.code, dev.name,
                            (event.timestamp() - debounce.released[event.code]) * 1000,
                            delay)
        return accepted

    def close_device(self, path):
        dev, ui, debounce = self.devices.pop(path)
        self.dismissed += debounce.dismissed
        try:
            self.selector.unregister(dev)
            for code in debounce.down:
                ui.write(E.EV_KEY, code, 0)
            ui.syn()
        except (OSError, ValueError):
            pass
        finally:
            ui.close()
            dev.close()  # Closing the fd also releases the exclusive grab.

    def scan(self):
        errors = []
        # evdev.list_devices() hides inaccessible nodes: report those failures instead.
        for path in glob('/dev/input/event*'):
            if path in self.devices:
                continue
            dev = ui = None
            try:
                dev = InputDevice(path)
                if dev.name.startswith(PREFIX):
                    continue
                keys = dev.capabilities().get(E.EV_KEY, [])
                if not {E.KEY_A, E.KEY_Z, E.KEY_SPACE}.issubset(keys):
                    continue
                match = self.config.get('device_name', '')
                if match and dev.name != match:
                    continue
                # Do not take ownership in the middle of a physical key cycle.
                if dev.active_keys():
                    continue
                set_monotonic_clock(dev)
                dev.grab()
                # Drop events queued before acquisition; replaying them duplicates input
                # that the compositor already received from the original keyboard.
                while True:
                    try:
                        list(dev.read())
                    except BlockingIOError:
                        break
                if dev.active_keys():
                    continue
                ui = UInput.from_device(dev, name=PREFIX + dev.name,
                                        filtered_types=(E.EV_SYN, E.EV_FF))
                # Mirror the hardware repeat settings to the virtual keyboard.
                if E.EV_REP in dev.capabilities():
                    ui.device.repeat = dev.repeat
                self.selector.register(dev, selectors.EVENT_READ)
                self.devices[path] = (dev, ui, Debouncer())
                dev = ui = None
            except (OSError, ValueError) as exc:
                errors.append(str(exc))
            finally:
                if ui is not None:
                    ui.close()
                if dev is not None:
                    dev.close()
        self.status = (f'{len(self.devices)} keyboard(s) connected' if self.devices else
                       'No accessible keyboard. Check permissions and the device name.')
        if errors and not self.devices:
            self.status = ('FILTER NOT OPERATIONAL: ' + errors[0] +
                           ' — run install.sh again or log out and back in.')

    def run(self):
        try:
            next_scan = 0
            while not self.stop_event.is_set():
                if time.monotonic() >= next_scan:
                    self.scan()
                    next_scan = time.monotonic() + 2
                for selected, _ in self.selector.select(0.2):
                    dev = selected.fileobj
                    _, ui, debounce = self.devices[dev.path]
                    try:
                        for event in dev.read():
                            if event.type == E.EV_SYN and event.code == E.SYN_DROPPED:
                                raise OSError('Input overflow: reconnect required')
                            if event.type == E.EV_KEY:
                                # The virtual device generates its own kernel repeats.
                                if event.value == 2:
                                    continue
                                if not self.accept_key(dev, debounce, event):
                                    continue
                            ui.write_event(event)
                    except OSError:
                        self.close_device(dev.path)
                        next_scan = time.monotonic() + 2
        except Exception as exc:
            self.status = f'Filter stopped: {exc}'
        finally:
            for path in list(self.devices):
                self.close_device(path)
            self.selector.close()

    def count(self):
        return self.dismissed + sum(item[2].dismissed for item in self.devices.values())
