#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 || -z ${SUDO_USER:-} || ${SUDO_USER} == root ]]; then
    echo 'Run from your user session: sudo ./install.sh' >&2
    exit 1
fi
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
apt-get update
apt-get install -y acl python3 python3-evdev python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 gnome-shell-extension-appindicator
getent group unshaky >/dev/null || groupadd --system unshaky
usermod -aG unshaky "$SUDO_USER"
install -d -m 755 /opt/unshaky-linux
cp -R "$source_dir/unshaky_linux" /opt/unshaky-linux/
chown -R root:root /opt/unshaky-linux
chmod -R go-w /opt/unshaky-linux
cat > /usr/local/bin/unshaky-linux <<'LAUNCHER'
#!/bin/sh
cd /opt/unshaky-linux || exit 1
export PYTHONPATH=/opt/unshaky-linux
exec /usr/bin/python3 -m unshaky_linux "$@"
LAUNCHER
chmod 755 /usr/local/bin/unshaky-linux
rm -f /etc/udev/rules.d/99-unshaky-linux.rules
cat > /etc/udev/rules.d/70-unshaky-linux.rules <<'RULES'
SUBSYSTEM=="input", KERNEL=="event*", ENV{ID_INPUT_KEYBOARD}=="1", GROUP="unshaky", MODE="0660", TAG+="uaccess"
SUBSYSTEM=="misc", KERNEL=="uinput", GROUP="unshaky", MODE="0660", TAG+="uaccess", OPTIONS+="static_node=uinput"
RULES
printf 'uinput\n' > /etc/modules-load.d/unshaky-linux.conf
modprobe uinput
udevadm control --reload-rules
udevadm trigger --subsystem-match=input
udevadm trigger --subsystem-match=misc
udevadm settle
# Apply access to the already running login session without requiring new groups.
for node in /dev/input/event*; do
    [[ -e "$node" ]] || continue
    if udevadm info --query=property --name="$node" | grep -qx 'ID_INPUT_KEYBOARD=1'; then
        setfacl -m "u:${SUDO_USER}:rw" "$node"
    fi
done
setfacl -m "u:${SUDO_USER}:rw" /dev/uinput
cat > /usr/share/applications/unshaky-linux.desktop <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Unshaky Linux
Comment=Filter unintended repeated keystrokes
Exec=/usr/local/bin/unshaky-linux
Icon=input-keyboard
Terminal=false
Categories=Utility;Accessibility;
DESKTOP
printf '\nInstallation complete. Device permissions also apply to the current session.\nOpen Unshaky Linux from the applications menu. Enable Start at login from its indicator.\n'
