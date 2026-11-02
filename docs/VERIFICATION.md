# Verification · 1.0.0

[Español](es/VERIFICATION.md)

The regression suite uses synthetic images and temporary libraries. It covers game identification, safe writes/renames, index records, conversion/cancellation, artwork parsing/download validation, CFG preservation, VMC layout, batch operations and theme persistence.

Package verification includes version checks, curated source contents, DEB metadata/dependencies, extracted-package checks and the packaged `--self-test`. The AppImage is checked with an isolated Ubuntu 22.04 userspace and an X11 virtual display, not just Python/Qt from the workstation. CI results are available under the repository's Actions tab.

Automated tests do not establish physical PS2 compatibility. No game, VMC or loader has been validated on a physical PS2 as part of this release. A service returning artwork does not guarantee every game/type is available. The application is an independent Linux client, not a claim of complete Windows feature parity.

## Release checks recorded on 2026-11-02

- **100 regression tests passed** in an isolated Ubuntu 22.04 environment.
- AppImage normal launch, FUSE-free execution, version and isolated self-test passed.
- AppImage self-test passed on pristine Ubuntu Base 22.04 without Python/Qt installed.
- Packaged Qt window/theme checks passed with offscreen and X11/Xvfb.
- Standalone DEB installation, version and self-test passed on pristine Ubuntu Base without Python/Qt. The launcher disables bytecode writes so removal does not leave runtime cache files in `/opt`.
- Tests use temporary data; no package was installed on the host workstation.
