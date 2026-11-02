# Build and test

[Español](es/BUILD.md) · [Home](../README.md)

## Requirements

Building the AppImage requires x86_64 Linux, Python 3.10+, `bwrap` with working user namespaces, `tar`, `dpkg-deb` and Internet access for the first download. No host `sudo` or global pip installation is used. `packaging/prepare_rootfs.py` creates an isolated Ubuntu Base 22.04 root and installs build libraries only there. The official base archive is SHA256-verified.

```sh
python3 packaging/prepare_rootfs.py
python3 packaging/build.py
```

Outputs are written to `dist/`: DEB, AppImage, source archive and `SHA256SUMS`. Both formats use the same bundled application runtime. The script packages only the public application/resources/docs; local working notes and old build products are excluded.

## Runtime

The amd64 DEB bundles all application dependencies and declares only `libc6 (>= 2.35)` from the system. APT checks that requirement. No Python/Qt packages are needed from the distribution. It installs the application to `/opt/opl-manager-linux`, a command in `/usr/bin`, an icon and a menu entry.

AppImage includes standalone CPython 3.12.16, PyQt6 6.7.1, Qt 6.7.3, Pillow 11.3.0, LZ4, required desktop support libraries, certificates and DejaVu fonts. Build downloads are pinned in `packaging/toolchain-lock.json` and `packaging/requirements-appimage.txt`. Download mismatches stop the build. Libraries resolve against Ubuntu 22.04, not the build host. glibc, the kernel, display server and GPU drivers remain system components. Runtime libraries stay dynamic and replaceable after extraction. AppImage requires glibc 2.35+ and supports extraction without FUSE.

## Checks

```sh
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
QT_QPA_PLATFORM=offscreen ./dist/OPL-Manager-Linux-1.0.0-x86_64.AppImage --appimage-extract-and-run --self-test
./dist/OPL-Manager-Linux-1.0.0-x86_64.AppImage --appimage-extract-and-run --version
(cd dist && sha256sum -c SHA256SUMS)
```

`--self-test` creates a temporary synthetic library and exercises ISO identification, indexes, LZ4 conversion, Pillow, VMC and Qt themes. It does not load your real library or contact a PS2/artwork server. `QT_QPA_PLATFORM=offscreen` checks Qt rendering without a visible desktop; Xvfb additionally checks the X11 plugin. GitHub Actions installs/tests/purges the DEB inside its disposable Ubuntu runner. It never installs the package on your workstation.

Third-party notices are in [THIRD_PARTY.md](../THIRD_PARTY.md). Exact runtime bits are pinned, but APT repositories and archive timestamps can change; byte-for-byte reproducibility across dates is not claimed.
