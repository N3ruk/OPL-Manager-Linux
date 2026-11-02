# Third-party credits and licenses

The application's own code is GPL-3.0-or-later; bundled components and data keep their respective licenses.

- **OPL Manager for Windows**, by danielb: https://oplmanager.com/. Inspiration for this independent native Linux client. No affiliation is claimed. No Windows executables, libraries, tools or artwork are distributed.
- **PCSX2 GameIndex**: https://github.com/PCSX2/pcsx2/blob/master/bin/resources/GameIndex.yaml. `assets/games.json` contains only serials, titles and regions. The exact database source is retained in `licenses/pcsx2/GameIndex.yaml`, with its source hash in `assets/GameIndex-source.sha256`. PCSX2 is GPL-3.0-or-later; its database credits SonyIndex, SerialStation, PSX Data Center, Redump and PCSX2 contributors. [PCSX2 source/license](https://github.com/PCSX2/pcsx2).
- **Open PS2 Loader**: https://github.com/ps2homebrew/Open-PS2-Loader. Filesystem/index/ZSO/VMC interoperability references. VMC layout follows the format used by pc/genvmc (jimmikaelkael; AFL-3.0 reference). No OPL or genvmc executable is included or run.
- **OPL Manager API V6**: https://oplmanager.com/API/V6/OplManagerService.asmx. Optional user-requested artwork lookups/downloads use its anonymous ServiceStatus session identifier. Artwork is not bundled and remains owned by its rights holders.
- **xlenore/ps2-covers**: https://github.com/xlenore/ps2-covers. Optional cover fallback; no image collection is redistributed. Artwork and trademarks belong to their owners.
- **CPython 3.12.16** / python-build-standalone: PSF and component licenses. https://github.com/astral-sh/python-build-standalone/releases/tag/20261026 and https://www.python.org/downloads/source/. Notices in `licenses/python/`.
- **PyQt6 6.7.1 / PyQt6-sip 13.8.0**: GPL-3.0 for this GPL application, https://www.riverbankcomputing.com/software/pyqt/download. **Qt 6.7.3**: LGPL-3.0/GPL and component licenses, https://download.qt.io/archive/qt/6.7/6.7.3/single/. Dynamically linked and replaceable after extraction. Notices accompany the installed Python distributions and `licenses/qt/`.
- **Pillow 11.3.0**: HPND and bundled image-library licenses, https://github.com/python-pillow/Pillow/tree/11.3.0. Notices in the Pillow distribution and `licenses/pillow/`.
- **LZ4**: BSD-2-Clause, https://github.com/lz4/lz4. Ubuntu desktop libraries and DejaVu fonts retain their upstream licenses; package copyright notices are included inside the AppImage under `usr/share/opl-manager-linux/licenses/ubuntu/`. Corresponding Ubuntu source packages: https://archive.ubuntu.com/ubuntu/pool/.
- **AppImage type2-runtime**: MIT, https://github.com/AppImage/type2-runtime. Notice: `licenses/AppImage-runtime.txt`. Build tool appimagetool is not installed as an application dependency.

The AppImage ships CPython, Qt, Pillow, LZ4 and support libraries. The DEB ships the same standalone application runtime. No proprietary game assets, firmware, BIOS or game images are included. PlayStation/PS2 are Sony trademarks; the project is independent and unofficial.
