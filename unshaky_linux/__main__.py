import fcntl
import json
import os
from pathlib import Path
import signal
import sys
import gi

gi.require_version('Gtk', '3.0')
gi.require_version('AyatanaAppIndicator3', '0.1')
from gi.repository import Gtk, GLib, AyatanaAppIndicator3 as Indicator
from evdev import ecodes
from .backend import Worker

CONFIG = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'unshaky-linux'
AUTOSTART = CONFIG.parent / 'autostart/unshaky-linux.desktop'
DEFAULT = {'enabled': True, 'delay_ms': 40, 'keys': {}, 'aggressive': False,
           'device_name': 'Apple Inc. Apple Internal Keyboard / Trackpad'}


def desktop_entry():
    return ('[Desktop Entry]\nType=Application\nName=Unshaky Linux\n'
            'Comment=Filter unintended repeated keystrokes\n'
            'Exec=/usr/local/bin/unshaky-linux\nIcon=input-keyboard\nTerminal=false\n'
            'X-GNOME-Autostart-enabled=true\n')


class App:
    def __init__(self):
        CONFIG.mkdir(parents=True, exist_ok=True)
        self.lock = open(CONFIG / 'app.lock', 'w')
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            sys.exit('Unshaky Linux is already running.')
        self.config = DEFAULT.copy()
        try:
            raw = json.loads((CONFIG / 'config.json').read_text())
            assert isinstance(raw['enabled'], bool)
            assert isinstance(raw['delay_ms'], int) and 0 <= raw['delay_ms'] <= 500
            assert isinstance(raw['device_name'], str)
            assert isinstance(raw['keys'], dict)
            assert isinstance(raw.get('aggressive', False), bool)
            assert all(k.isdigit() and isinstance(v, int) and 0 <= v <= 500
                       for k, v in raw['keys'].items())
            self.config.update(raw)
        except FileNotFoundError:
            pass
        except (ValueError, KeyError, TypeError, AssertionError):
            sys.exit('Invalid configuration: ' + str(CONFIG / 'config.json'))
        self.worker = Worker(self.config.copy())
        self.log_window = None
        self.log_revision = -1
        self.worker.start()
        self.indicator = Indicator.Indicator.new('unshaky-linux', 'input-keyboard',
                                                  Indicator.IndicatorCategory.HARDWARE)
        self.indicator.set_status(Indicator.IndicatorStatus.ACTIVE)
        menu = Gtk.Menu()
        self.state = Gtk.MenuItem(label='Starting filter…')
        self.state.set_sensitive(False)
        menu.append(self.state)
        enabled = Gtk.CheckMenuItem(label='Enable filter')
        enabled.set_active(self.config['enabled'])
        enabled.connect('toggled', self.toggle)
        menu.append(enabled)
        settings = Gtk.MenuItem(label='Settings…')
        settings.connect('activate', self.settings)
        menu.append(settings)
        console = Gtk.MenuItem(label='Blocked keystrokes…')
        console.connect('activate', self.console)
        menu.append(console)
        auto = Gtk.CheckMenuItem(label='Start at login')
        auto.set_active(AUTOSTART.exists())
        auto.connect('toggled', self.autostart)
        menu.append(auto)
        quit_item = Gtk.MenuItem(label='Quit')
        quit_item.connect('activate', self.quit)
        menu.append(quit_item)
        menu.show_all()
        self.indicator.set_menu(menu)
        GLib.timeout_add_seconds(1, self.update)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.quit)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.quit)

    def save(self):
        temp = CONFIG / 'config.tmp'
        temp.write_text(json.dumps(self.config, indent=2) + '\n')
        temp.replace(CONFIG / 'config.json')
        self.worker.config = self.config.copy()

    def toggle(self, item):
        self.config['enabled'] = item.get_active()
        self.save()

    def autostart(self, item):
        if item.get_active():
            AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
            AUTOSTART.write_text(desktop_entry())
        else:
            AUTOSTART.unlink(missing_ok=True)

    def update(self):
        operational = self.worker.is_alive() and bool(self.worker.devices)
        state = 'ACTIVE' if operational and self.config['enabled'] else (
            'PAUSED' if operational else 'NOT OPERATIONAL')
        self.state.set_label(f'{state} · {self.worker.status} · {self.worker.count()} blocked')
        self.indicator.set_icon_full('input-keyboard' if operational else
                                     'dialog-error', 'Unshaky Linux: ' + state)
        self.indicator.set_label('' if operational else 'Error', 'Error')
        self.refresh_console()
        return True

    def console(self, *_):
        if self.log_window is None:
            self.log_window = Gtk.Window(title='Unshaky Linux — Blocked keystrokes')
            self.log_window.set_default_size(1000, 420)
            self.log_window.connect('delete-event', self.hide_console)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, margin=12)
            self.log_window.add(box)
            note = Gtk.Label(label='Blocked presses only · latest 1000 events in memory · no log files')
            note.set_xalign(0)
            note.set_line_wrap(True)
            box.pack_start(note, False, False, 0)
            self.log_store = Gtk.ListStore(str, str, str, str, str, str)
            self.log_view = Gtk.TreeView(model=self.log_store)
            for index, title in enumerate(('Local time', 'Key', 'Code', 'Keyboard',
                                            'Since release (ms)', 'Threshold (ms)')):
                column = Gtk.TreeViewColumn(title, Gtk.CellRendererText(), text=index)
                column.set_resizable(True)
                self.log_view.append_column(column)
            scroll = Gtk.ScrolledWindow()
            scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            scroll.add(self.log_view)
            box.pack_start(scroll, True, True, 0)
            bar = Gtk.Box(spacing=12)
            self.log_label = Gtk.Label()
            bar.pack_start(self.log_label, False, False, 0)
            self.log_follow = Gtk.CheckButton(label='Follow new events')
            self.log_follow.set_active(True)
            bar.pack_start(self.log_follow, False, False, 0)
            clear = Gtk.Button(label='Clear log')
            clear.connect('clicked', self.clear_console)
            bar.pack_end(clear, False, False, 0)
            box.pack_start(bar, False, False, 0)
        self.log_window.show_all()
        self.refresh_console()
        self.log_window.present()

    def hide_console(self, *_):
        self.log_window.hide()
        return True

    def clear_console(self, *_):
        self.worker.log.clear()
        self.refresh_console()

    def refresh_console(self):
        if self.log_window is None or not self.log_window.get_visible():
            return
        revision, rows = self.worker.log.snapshot()
        if revision == self.log_revision:
            return
        self.log_store.clear()
        for row in rows:
            self.log_store.append(row)
        self.log_label.set_text(f'{len(rows)} events · clearing the log does not reset the counter')
        self.log_revision = revision
        if rows and self.log_follow.get_active():
            self.log_view.scroll_to_cell(Gtk.TreePath.new_from_indices([len(rows) - 1]),
                                         None, True, 1.0, 0.0)

    def settings(self, *_):
        dialog = Gtk.Dialog(title='Unshaky Linux', buttons=(
            'Cancel', Gtk.ResponseType.CANCEL, 'Save', Gtk.ResponseType.OK))
        dialog.set_default_size(540, 360)
        grid = Gtk.Grid(column_spacing=12, row_spacing=12, margin=18)
        dialog.get_content_area().add(grid)
        grid.attach(Gtk.Label(label='Default threshold (ms)'), 0, 0, 1, 1)
        delay = Gtk.SpinButton.new_with_range(0, 500, 5)
        delay.set_value(self.config['delay_ms'])
        grid.attach(delay, 1, 0, 1, 1)
        grid.attach(Gtk.Label(label='Keyboard (exact name)'), 0, 1, 1, 1)
        name = Gtk.Entry(text=self.config['device_name'])
        grid.attach(name, 1, 1, 1, 1)
        grid.attach(Gtk.Label(label='Empty name: all keyboards. Restart after changing the name.'), 0, 2, 2, 1)
        grid.attach(Gtk.Label(label='Per-key overrides: KEY_A=60, KEY_SPACE=0'), 0, 3, 2, 1)
        overrides = Gtk.Entry(text=', '.join(
            f'{ecodes.KEY.get(int(k), k)}={v}' for k, v in self.config['keys'].items()))
        grid.attach(overrides, 0, 4, 2, 1)
        error = Gtk.Label(label='0 disables filtering. Start at 40 ms. Accepted presses are not logged.')
        error.set_line_wrap(True)
        grid.attach(error, 0, 5, 2, 1)
        aggressive = Gtk.CheckButton(label='Aggressive mode: extend the window after each rejected key cycle')
        aggressive.set_active(self.config.get('aggressive', False))
        grid.attach(aggressive, 0, 6, 2, 1)
        dialog.show_all()
        while dialog.run() == Gtk.ResponseType.OK:
            try:
                keys = {}
                for part in overrides.get_text().split(','):
                    if not part.strip():
                        continue
                    key, value = part.strip().split('=')
                    code = ecodes.ecodes[key.strip()]
                    value = int(value)
                    if not key.strip().startswith('KEY_') or not 0 <= value <= 500:
                        raise ValueError()
                    keys[str(code)] = value
            except (KeyError, ValueError):
                error.set_text('Invalid format. Example: KEY_A=60, KEY_SPACE=0. Range: 0–500.')
                continue
            self.config.update(delay_ms=delay.get_value_as_int(), keys=keys,
                               device_name=name.get_text().strip(), aggressive=aggressive.get_active())
            self.save()
            break
        dialog.destroy()

    def quit(self, *_):
        self.worker.stop_event.set()
        self.worker.join(timeout=3)
        Gtk.main_quit()
        return False


if __name__ == '__main__':
    app = App()
    Gtk.main()
