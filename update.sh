#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -eq 0 ]]; then
    echo 'Run this script as your normal user: ./update.sh' >&2
    exit 1
fi
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
sudo -- "$source_dir/install.sh"
# Restart only this user's application after installation succeeds.
pkill -u "$(id -u)" -f '^/usr/bin/python3 -m unshaky_linux$' || true
for attempt in {1..30}; do
    if ! pgrep -u "$(id -u)" -f '^/usr/bin/python3 -m unshaky_linux$' >/dev/null; then
        /usr/bin/python3 - <<'LAUNCH'
import subprocess
import time
process = subprocess.Popen(
    ['/usr/local/bin/unshaky-linux'], stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
time.sleep(1)
if process.poll() is not None:
    raise SystemExit('Startup failed: run unshaky-linux in a terminal to read the error.')
print('Unshaky Linux started. You can close this terminal.')
LAUNCH
        exit 0
    fi
    sleep 0.1
done
echo 'Quit the previous Unshaky Linux instance, then reopen it from the applications menu.' >&2
exit 1
