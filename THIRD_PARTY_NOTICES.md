# Third-party components

This repository contains runtime integration code and a patch against elfuse,
not Spotify Soloist or a Linux operating-system image.

- elfuse: https://github.com/sysprog21/elfuse, Apache-2.0. Base commit:
  `4023647491db64adc43de76284206d8ab81ff6e3`. The patch preserves existing source
  copyright headers; keep upstream LICENSE and notices with a packaged runtime.
- Debian ARM64 shared libraries are downloaded separately during setup. Package
  versions and checksums are pinned in the package lock files. Their license
  notices are extracted into the private sysroot's `usr/share/doc` directory.
  Preserve those notices if packaging the library sysroot for distribution.
- PulseAudio and dependencies are installed separately by Homebrew; they are
  not committed here. Native audio uses PulseAudio's CoreAudio output module.
- The optional Python control/observation tools use websockets (BSD-3-Clause).
- The packaged credential helper uses [keyring](https://github.com/jaraco/keyring)
  (MIT). Its macOS backend stores the user's API key in macOS Keychain. Keyring's
  installed `jaraco.classes`, `jaraco.context`, `jaraco.functools` and
  `more-itertools` dependencies are MIT-licensed. Linux and Windows keyring
  backends are a portability direction, not validated runtime targets yet.
- Spotify Soloist remains a separately obtained proprietary executable. Follow
  Spotify's official download and license instructions; do not bundle it into
  this repository or redistribute it with the compatibility runtime.
