# Unshaky Linux

Keep a shaky keyboard usable on Linux. Unshaky Linux filters unintended repeated
keystrokes and stays in your desktop panel, with per-key thresholds, a live
blocked-keystroke console, and an optional start-at-login setting.

Inspired by **[Unshaky](https://github.com/aahung/Unshaky)**, the original macOS
utility by **[Xinhong Liu (@aahung)](https://github.com/aahung)** and its
contributors. Their work and explanation of keyboard bounce made this project
possible. See [Credits](CREDITS.md) for attribution and the original MIT notice.

## Why I built this

I installed Ubuntu on my **2018 MacBook Pro**, which has the butterfly keyboard
problem: a single physical press can produce two letters.

I wanted to keep using this MacBook with Ubuntu beyond Apple's support
lifecycle. Installing Linux gives the computer another useful life, but it does
not fix the keyboard's physical defects. Anyone taking the same route with an
affected MacBook may run into the same double-keystroke problem.

The original Unshaky addresses this on macOS. I wanted the same practical idea
on Ubuntu: a small utility that stays in the top bar, filters keyboard bounce,
and can start automatically when I log in. This repository is the Linux version
built for that need.

## Features

- A persistent GTK/Ayatana panel indicator with enable, pause, settings, and quit.
- A default **40 ms** debounce threshold and individual `KEY_*` overrides.
- A live console showing blocked keys, device names, timing, and thresholds.
- The latest 1,000 blocked events kept in memory; no keystroke log files.
- Optional aggressive mode for chains of repeated bounce events.
- Optional **Start at login** using XDG Autostart.
- An evdev/uinput backend designed for both Wayland and X11.
- Periodic keyboard discovery and reconnection; one instance per user.
- A detached update launcher: closing the terminal does not stop the filter.

## Status and compatibility

This is an early project, confirmed working on the original **2018 MacBook Pro
running Ubuntu with GNOME/Wayland and the Apple T2 keyboard driver**. During real
use, two unintended `KEY_C` presses at **13.60 ms** and **13.67 ms** after release
were successfully blocked with the default 40 ms threshold.

The test suite has **29 passing tests**, including the original diagram's event
sequence across key codes 1–255. Physical keyboard acquisition, monotonic clock
configuration, and device release have also been checked on that machine.

The installer targets Ubuntu/Debian systems with `apt`, `systemd-udev`, and
GNOME. Other distributions and desktops need their own dependency and panel
integration setup. X11 support is part of the design; it has not received the
same hands-on validation as this Wayland setup.

## Install

Clone this repository, then run the installer as your normal user through sudo:

```bash
git clone https://github.com/maurodam/unshaky-linux.git
cd unshaky-linux
sudo ./install.sh
```

Open **Unshaky Linux** from your applications menu. The installer provides:

- System Python dependencies, GTK3, Ayatana AppIndicator, and the GNOME extension.
- Application files in `/opt/unshaky-linux` and a `/usr/local/bin/unshaky-linux` launcher.
- A desktop entry, a dedicated `unshaky` group, udev rules, and keyboard/uinput access.
- ACLs for the installing user on existing keyboard devices, so access also works
  in the current session without waiting for a fresh group login.

If the GNOME AppIndicator extension was newly installed, you may need to log out
and back in for the icon to appear. Enable `ubuntu-appindicators@ubuntu.com` in
GNOME Extensions if necessary. A desktop with AppIndicator support is required
for the panel menu; its location depends on your desktop configuration.

## Configure

1. Open the indicator menu and check for **ACTIVE · 1 keyboard(s) connected**.
   **Enable filter** expresses your preference; **ACTIVE** confirms a keyboard
   has actually been acquired. **NOT OPERATIONAL** means filtering is unavailable.
2. Open **Settings…** and start with **40 ms**. Increase only as needed: a long
   threshold can also block an intentional double letter.
3. Add per-key overrides if needed, for example `KEY_C=60, KEY_SPACE=0`.
   A value of `0` disables debounce for that key; allowed values are 0–500 ms.
4. Enable **Start at login** if desired.

The default device name is:

```text
Apple Inc. Apple Internal Keyboard / Trackpad
```

Despite the shared name, the trackpad is excluded: the backend selects only
input devices with the A, Z, and Space key capabilities. On another keyboard,
enter its exact name or leave the field empty to select all accessible keyboards.
Restart the application after changing the device name.

**Aggressive mode** extends the exclusion window from the release of each
rejected press. It can help with repeated bounce chains, but may also block
closely spaced intentional repetitions. It is off by default.

Start at login runs the application **after desktop sign-in**, not at boot or
on the login screen. Closing settings or the console keeps the filter running.
Choose **Quit** to stop it.

### Blocked-keystroke console

Choose **Blocked keystrokes…** from the panel menu. The console updates once per
second and shows local time, Linux key name/code, keyboard, elapsed time since
release, and the threshold used to reject the press.

**Follow new events** controls automatic scrolling. **Clear log** removes the
history without resetting the session's blocked counter. Only the latest 1,000
blocked presses are retained, in memory, and they disappear when the application
exits. Accepted keystrokes are not logged.

## Update and restart

From your existing checkout:

```bash
git pull --ff-only
./update.sh
```

The script requests sudo for installation, preserves your settings and login
preference, stops your previous instance after a successful install, and starts
the application in a separate session. You can then close the terminal.

## How filtering works

The backend exclusively grabs the physical keyboard and forwards accepted input
through a virtual keyboard created with `uinput`.

For each key on each device:

1. A normal key-down and key-up pass through immediately.
2. If another key-down arrives less than the threshold after the last accepted
   key-up, that press is rejected.
3. The rejected press's matching key-up is also rejected.
4. A later press outside the window passes through normally.

Accepted input is not delayed until the threshold expires. Held-key repetition
is generated by the virtual keyboard using the original device's initial repeat
settings. Events queued before the exclusive grab are drained to avoid replaying
input that the desktop already received from the physical keyboard.

This follows the core idea of the original
[ShakyPressPreventer](https://github.com/aahung/Unshaky/blob/master/Unshaky/ShakyPressPreventer.m).
The Linux implementation uses Python, GTK, `python-evdev`, and Linux `KEY_*` codes;
it does not use Cocoa or macOS `CGEventTap` APIs. The macOS-specific Cmd+Space and
sub-5 ms text-expansion exceptions are not reproduced: this filter handles raw
hardware events and also rejects physical bounce below 5 ms.

## Permissions and recovery

Keyboard access is sensitive. The dedicated group and per-user ACLs permit
reading keyboard events and creating virtual input. Other programs running as
that user can use the same access. The GUI runs as your normal user; the
installer does not grant world-writable `0666` access to devices.

If you need to stop the filter from a terminal or SSH session:

```bash
pkill -u "$(id -u)" -f '^/usr/bin/python3 -m unshaky_linux$'
```

Closing the physical device's file descriptor releases the exclusive grab. On a
normal exit, held virtual keys are released before the virtual keyboard is
removed. The compositor may take a moment to remove the virtual device.

To uninstall, quit the application first, then run:

```bash
sudo ./uninstall.sh
```

Reboot afterward to restore device permissions. Your settings in
`~/.config/unshaky-linux/config.json` are kept. The uninstaller removes the login
entry from the default `~/.config/autostart` location; if you use a custom
`XDG_CONFIG_HOME`, remove that custom autostart entry separately.

## Known limitations

- Physical Caps Lock/Num Lock LEDs are not synchronized from the virtual device.
- Desktop settings tied to a device name may need to be applied to the virtual keyboard.
- Hotplug, suspend/resume, shortcuts, layouts, held-key repeat, and Apple T2 special
  keys need broader testing across hardware and desktop environments.
- An input-buffer overflow releases the device and schedules reconnection. A
  keyboard with currently held keys is left alone until the keys are released.
- The program does not supervise or restart itself after a crash.
- This is a software workaround for keyboard bounce, not a repair of the hardware.

## Development and tests

Install the runtime dependencies with the installer, or install `python3-evdev`
separately to run the complete backend test suite. Then, from the repository root:

```bash
/usr/bin/python3 -m unittest discover -s tests -v
/usr/bin/python3 -m compileall -q unshaky_linux
bash -n install.sh uninstall.sh update.sh
```

Backend tests use simulated devices constrained to the real `InputDevice` API.
They cover rejected down/up pairs, intentional repetitions, aggressive mode,
threshold boundaries, permissions, acquisition failures, draining queued input,
and forwarding only accepted cycles. Filter and history tests require no device
access; backend tests are skipped if `python3-evdev` is missing.

Timestamp configuration calls Linux `EVIOCSCLOCKID` directly because the Ubuntu
`python-evdev` version does not expose `InputDevice.set_clockid()`.

For hands-on testing, check ordinary typing, intentional double letters,
held-key repeat, modifiers, pause/resume, reconnect, exit, and a new desktop login.
Report your distribution, desktop, session type, keyboard, threshold, and the
observed behavior when opening an issue. Avoid sharing sensitive typed content.

## Credits and license

**Thank you to Xinhong Liu (@aahung) and all contributors to
[the original Unshaky project](https://github.com/aahung/Unshaky).** The original
project deserves credit for the idea, debounce behavior, and clear explanation
of how the keyboard issue can be addressed in software.

This is an independent Linux implementation, not an official release of the
original macOS project. Original artwork and macOS application assets are not
included.

Unshaky Linux is distributed under the **MIT License**. The original notice,
`Copyright (c) 2018 _sam`, is preserved alongside the Linux project's notice in
[LICENSE](LICENSE). See [CREDITS.md](CREDITS.md) for the source reference.

Other components used by this project include
[python-evdev](https://python-evdev.readthedocs.io/en/latest/),
[PyGObject/GTK](https://pygobject.gnome.org/), and
[Ayatana AppIndicator](https://github.com/AyatanaIndicators/libayatana-appindicator).
They retain their respective licenses and are installed as system dependencies.
