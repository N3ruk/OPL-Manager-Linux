# Usage and troubleshooting

[Español](es/USAGE.md) · [Home](../README.md)

## Libraries and files

Select the OPL root or DVD/CD/POPS. The app associates media folders with their common root, handles lowercase folder names, and offers to create missing DVD/CD/ART/CFG/CHT/VMC/POPS folders. Standalone images are listed but are not moved into media folders. Inspect warnings before renaming, converting or indexing.

Classic names allow a title of up to 32 encoded bytes. Modern names avoid that classic-title restriction, but the selected index profile still has filename limits. Operations reject collisions and unsafe paths. VCD IDs come from filenames; their internal structure is not inspected. UL entries are read from `ul.cfg`; ambiguous or incomplete parts cannot be hashed.

## Automatic indexes

Loading, restoring or refreshing a library atomically updates each existing CD/DVD `games.bin`, independent of visible filters. The default **OPL legacy · 92bytes/juego** profile stores 64 filename bytes; a manual 160-byte filename profile produces 188-byte records. The next automatic update returns to 92-byte records. Match the profile to your loader.

Indexes have no header. They contain the actual filename, verified game ID, exact extension, media and naming format, and physical size in MiB. VCD/UL are excluded. Empty folders receive empty indexes, unchanged indexes are not rewritten, and unverified IDs or oversized names block incomplete publication. Writes are atomic per file, not across both media directories; errors identify indexes already written. A server with an already-open image may need reopening to see changes; the application does not control it.

```sh
./opl-manager-linux --library '/path/to/OPL' --generate-games-bin
./opl-manager-linux --library '/path/to/OPL' --generate-games-bin --index-name-bytes 160
```

## Artwork, CFG and VMC

Artwork previews do not write to ART. Select a variant and download explicitly; batch download skips existing artwork unless replacement is selected. Missing types are reported rather than replaced with unrelated images. Output PNG sizes: COV 140×200, COV2 242×344, ICO 64×64, LAB 18×240, LGO 300×125, BG 640×480, SCR/SCR2 250×188; indexed up to 256 colors.

CFG controls and advanced text are synchronized. Unknown keys, comments and custom values are retained; saved text uses CRLF and a `.bak` copy. External edits are detected. CHT is a text editor, not a complete POPStarter cheat wizard. VMC files contain formatted 512-byte pages without ECC/spare, at 8–64 MiB; existing cards are never overwritten. Assign a card to a slot and save CFG.

## Conversion and checksums

ISO/ZSO conversion retains the original, checks destinations and publishes only completed output; cancellation removes temporary output. CRC32/MD5/SHA-1/SHA-256 report file identity, not verified dump quality. Back up important library metadata before intentional editing.

## Troubleshooting and removal

- AppImage without FUSE: add `--appimage-extract-and-run`.
- No desktop: the GUI needs a graphical session. `QT_QPA_PLATFORM=offscreen` is for automated tests, not interactive use.
- Missing DEB dependencies: install the local package through APT on a compatible distribution.
- Artwork unavailable: check network/service availability and whether the game ID has that artwork. Library browsing works offline.
- Index rejected: inspect ID/name/permission warnings. Do not truncate filenames to conceal the issue.
- Reset theme/library: close the app and edit or remove `~/.config/opl-manager-linux/settings.json`.
- Remove DEB: `sudo apt purge opl-manager-linux`. Remove AppImage: delete its file. Neither removes your games or library data.
