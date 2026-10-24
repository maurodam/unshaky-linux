#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 || -z ${SUDO_USER:-} || ${SUDO_USER} == root ]]; then
    echo 'Quit Unshaky Linux, then run: sudo ./uninstall.sh' >&2
    exit 1
fi
user_home=$(getent passwd "$SUDO_USER" | cut -d: -f6)
rm -f /usr/local/bin/unshaky-linux /usr/share/applications/unshaky-linux.desktop
rm -f /etc/udev/rules.d/70-unshaky-linux.rules /etc/udev/rules.d/99-unshaky-linux.rules /etc/modules-load.d/unshaky-linux.conf
rm -rf /opt/unshaky-linux
rm -f "$user_home/.config/autostart/unshaky-linux.desktop"
gpasswd -d "$SUDO_USER" unshaky || true
for node in /dev/input/event* /dev/uinput; do
    [[ -e "$node" ]] || continue
    setfacl -x "u:${SUDO_USER}" "$node" 2>/dev/null || true
done
udevadm control --reload-rules
printf 'Application removed. Reboot to restore device permissions. User settings have been kept.\n'
