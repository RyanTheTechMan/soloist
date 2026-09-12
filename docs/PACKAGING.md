# Standalone local macOS package

The small AppKit launcher is setup/Start/Stop UI for the runtime, not a music
client. Its nested helper freezes the existing Python supervisor/control tools
and bundles elfuse, a production Linux library sysroot, a CA store and private
macOS PulseAudio dependencies. Running it does not require a compiler, Homebrew,
Python installation or a checkout. The official Soloist executable and user's
API-key file are deliberately separate inputs. See [Quick start](../packaging/QUICKSTART.md).

This local ad-hoc-signed preview targets Apple Silicon/macOS 27. Public signing,
notarization, redistribution-license review and API access control remain gates.
Windows/Linux packaging and mobile engines are not implemented here.
Graphical setup has an unresolved first-run file-access/picker test; the verified
fallback is the bundled command-line interface, not a system-privacy workaround.

## Build from source

First complete the source setup from the README to build the pinned runtime and
cache the locked production Linux packages. On the tested host use full Xcode
27 and Python 3.13. The builder uses local ARM64 Homebrew PulseAudio libraries;
their exact installed versions are recorded, but Homebrew itself is not locked.

```sh
python3 -m venv build/package-venv
build/package-venv/bin/pip install -r packaging/requirements.txt
DEVELOPER_DIR=/path/to/Xcode.app/Contents/Developer \
  build/package-venv/bin/python scripts/build-package.py
build/package-venv/bin/python scripts/verify-package.py \
  "dist/Soloist Runtime.app" --soloist /path/to/soloist \
  --api-key-file /path/to/soloist.api
```

The last command checks signatures, payload checksums, internal symlinks, native
load commands and exclusion of the supplied engine/key; it does not authenticate
or play music. It never prints the key. Optional private inputs make those two
exclusion checks stronger. All generated outputs remain ignored. The builder
refuses to replace an existing app; use `--name "Soloist Runtime Trial"` to
preserve it. Build instructions are repeatable, not a bit-reproducibility claim.

The production sysroot is rebuilt from checksum-verified `.deb` entries in
`sysroot-packages.json`, never copied from a development sysroot. Package data
only is extracted; no maintainer scripts, dev fixtures or session state are
included. Native dependency install names are made bundle-relative and those
dependencies re-signed. Soloist is neither included nor modified in that process.
The elfuse helper retains its public Hypervisor entitlement.

`Contents/Resources/manifest.json` records the source revision/dirty flag,
dependency versions and hashes of the finalized helper payload. Linux copyright
files and additional native notices are included. Notices alone are not a claim
that public redistribution obligations, including source availability, are met.

## Client integration and writable data

The independent future client can locate the nested `runtime-cli` and use
`describe`, `configure`, `run`, `endpoint`, `status` and `control`. `describe`
reports integration version 1 and supported command names. Receiver lifecycle
belongs to its caller; closing the launcher stops its receiver. No login item,
system service or hosted fork backend is installed.

Packaged state/cache defaults to `~/Library/Application Support/Soloist Runtime/`.
Development runs retain their repository-local profile. An absolute
`SOLOIST_RUNTIME_HOME` overrides the CLI profile for isolated tests. No runtime
writes belong in the application bundle. Configuration stores paths, not a copy
of the executable or key. Spotify receives authentication requests on startup.

The control endpoint remains unauthenticated loopback preview API. Packaging
does not make it safe to expose to browsers or a LAN. See [local control](LOCAL_CONTROL.md)
and [release gates](RELEASE_READINESS.md). The future client/runtime must preserve
local control across Internet loss without assuming that every offline engine
command will succeed.
