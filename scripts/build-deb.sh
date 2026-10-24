#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then
    echo "Usage: $0 VERSION (for example 0.1.0 or v0.1.0)" >&2
    exit 1
fi
version=${1#v}
# Keep tag names safe for both Debian metadata and output paths.
if [[ ! $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo 'Version must contain three numbers, for example 0.1.0.' >&2
    exit 1
fi
source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
build_dir=$(mktemp -d)
trap 'rm -rf -- "$build_dir"' EXIT
package_dir="$build_dir/package"
install -d "$package_dir/DEBIAN" "$package_dir/opt/unshaky-linux/unshaky_linux" \
    "$package_dir/usr/bin" "$package_dir/usr/share/applications" \
    "$package_dir/usr/lib/udev/rules.d" "$package_dir/usr/lib/modules-load.d" \
    "$package_dir/usr/share/doc/unshaky-linux" "$source_dir/dist"
install -m 644 "$source_dir"/unshaky_linux/*.py "$package_dir/opt/unshaky-linux/unshaky_linux/"
install -m 755 "$source_dir/packaging/debian/launcher" "$package_dir/usr/bin/unshaky-linux"
install -m 644 "$source_dir/packaging/debian/unshaky-linux.desktop" "$package_dir/usr/share/applications/"
install -m 644 "$source_dir/packaging/debian/70-unshaky-linux.rules" "$package_dir/usr/lib/udev/rules.d/"
printf 'uinput\n' > "$package_dir/usr/lib/modules-load.d/unshaky-linux.conf"
install -m 644 "$source_dir/LICENSE" "$package_dir/usr/share/doc/unshaky-linux/copyright"
install -m 644 "$source_dir/README.md" "$source_dir/CREDITS.md" "$package_dir/usr/share/doc/unshaky-linux/"
for script in postinst postrm; do
    install -m 755 "$source_dir/packaging/debian/$script" "$package_dir/DEBIAN/"
done
cat > "$package_dir/DEBIAN/control" <<EOF
Package: unshaky-linux
Version: $version
Section: utils
Priority: optional
Architecture: all
Maintainer: Unshaky Linux maintainers <maurodam@users.noreply.github.com>
Depends: python3, python3-evdev, python3-gi, gir1.2-gtk-3.0, gir1.2-ayatanaappindicator3-0.1, udev, kmod, passwd
Recommends: gnome-shell-extension-appindicator
Installed-Size: $(du -sk "$package_dir/opt" "$package_dir/usr" | awk '{total += $1} END {print total}')
Homepage: https://github.com/maurodam/unshaky-linux
Description: Filter unintended repeated keyboard presses on Linux
 GTK panel utility with per-key debounce thresholds and an evdev/uinput backend.
 Supports desktop sessions with AppIndicator integration.
EOF
# Normalize modes independently of the invoking user's umask.
find "$package_dir" -type d -exec chmod 755 {} +
find "$package_dir" -type f -exec chmod 644 {} +
chmod 755 "$package_dir/usr/bin/unshaky-linux" "$package_dir/DEBIAN/postinst" "$package_dir/DEBIAN/postrm"
output="$source_dir/dist/unshaky-linux_${version}_all.deb"
dpkg-deb --root-owner-group --build "$package_dir" "$output"
(cd "$source_dir/dist" && sha256sum "${output##*/}" > "${output##*/}.sha256")
