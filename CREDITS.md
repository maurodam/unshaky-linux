# Credits

## Original inspiration: Unshaky

- **Project:** [aahung/Unshaky](https://github.com/aahung/Unshaky)
- **Author:** Xinhong Liu, [@aahung](https://github.com/aahung)
- **Contributors:** [Unshaky contributors](https://github.com/aahung/Unshaky/graphs/contributors)
- **License:** [MIT](https://github.com/aahung/Unshaky/blob/master/LICENSE)
- **Original copyright notice:** `Copyright (c) 2018 _sam`

Unshaky Linux was inspired by Unshaky's approach to the double-keystroke problem
on Apple's butterfly keyboards. Credit for the original macOS project, its
core debounce idea, and its explanation of rejecting a repeated key-down and
its matching key-up belongs to the original author and contributors.

The reference source studied for this implementation is
[`ShakyPressPreventer.m` at commit `057fb5415b4cb3bba0c9ea8a6f10af5a86860395`](https://github.com/aahung/Unshaky/blob/057fb5415b4cb3bba0c9ea8a6f10af5a86860395/Unshaky/ShakyPressPreventer.m).
The original MIT copyright and permission notice is retained in this repository's
[LICENSE](LICENSE).

This repository contains a separate Linux implementation. It does not bundle
the original macOS application's source tree, icons, or other artwork, and does
not imply endorsement by or affiliation with the original project.

## Linux implementation

Maintained by **[Damiano Mauro (@maurodam)](https://github.com/maurodam)**.
Created to keep a 2018 MacBook Pro with a faulty butterfly keyboard usable after
installing Ubuntu, with a persistent desktop indicator and optional login startup.

## Runtime dependencies

Thanks also to the maintainers and contributors of:

- [python-evdev](https://python-evdev.readthedocs.io/en/latest/), for Linux input access.
- [PyGObject](https://pygobject.gnome.org/) and [GTK](https://www.gtk.org/), for the interface.
- [Ayatana AppIndicator](https://github.com/AyatanaIndicators/libayatana-appindicator), for the panel menu.
- [Ubuntu AppIndicators](https://github.com/ubuntu/gnome-shell-extension-appindicator), for GNOME integration.

Dependencies are installed separately and retain their own licenses.
