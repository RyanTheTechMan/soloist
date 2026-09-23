# Standalone local macOS package

The small AppKit launcher is setup/Start/Stop UI for the runtime, not a music
client. Its nested helper freezes the existing Python supervisor/control tools
and bundles elfuse, a production Linux library sysroot, a CA store and private
macOS PulseAudio dependencies. Running it does not require a compiler, Homebrew,
Python installation or a checkout. The official Soloist executable and user's
API key are deliberately separate inputs. After selection, the executable
is installed under private Application Support storage, never into the bundle.
The graphical app stores the key in macOS Keychain.
See [Quick start](../packaging/QUICKSTART.md).

This local ad-hoc-signed preview targets Apple Silicon/macOS 27. Public signing,
notarization, redistribution-license review and API access control remain gates.
Windows/Linux packaging and mobile engines are not implemented here.
Graphical setup still has an unresolved first-run file-access/picker test; the verified
fallback is the bundled command-line interface, not a system-privacy workaround.

## Build from source

First complete the source setup from the README to build the pinned runtime and
cache the locked production Linux packages. On the tested host use full Xcode
27 and Python 3.13. The builder uses local ARM64 Homebrew PulseAudio libraries;
their exact installed versions are recorded, but Homebrew itself is not locked.
For a public-source build without any Soloist or key file, use
`python scripts/setup.py --build-only` after installing the source dependencies.

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
`scripts/build-package.py --version 1.2.3` sets the bundle, manifest and bundled
helper to the same release version.

## GitHub Actions and local Git handoff

`.github/workflows/macos-package.yml` runs from a fresh checkout on the Xcode 27
ARM64 runner. It installs the named build dependencies, fetches the pinned
elfuse revision and checksum-locked Debian libraries, builds without Soloist or
account credentials, runs account-free tests, and audits the bundle both before
and after ZIP extraction. It uploads a macOS app ZIP, tracked-source ZIP and
SHA256SUMS as build artifacts. A push to `main`, pull request, or manual run with
an empty `release_tag` only builds these artifacts.

To prepare a GitHub Release after adding your own remote, open Actions → Build
macOS runtime → Run workflow and enter a tag such as `v0.1.0`. A passing run
creates a **draft** release at the selected commit with the three files. Review
signing, first-run setup, included libraries and their redistribution terms
before publishing. This workflow does not access a Soloist executable or API key,
and does not publish a public release automatically. Hosted CI execution is not
verified until you push the repository and run it; the current checks are local.

This folder already has independent local Git history. For a portable source
copy with history and without ignored build products, vendor checkout, session
state or credentials, clone it into the location you want:

```sh
git clone --no-local --no-hardlinks /path/to/soloist-macos-runtime /path/to/new-folder
git -C /path/to/new-folder remote remove origin
```

Copying the entire working directory in Finder would also copy ignored private
state and cached binaries. The clean clone contains only committed files. The
two-repository design still leaves any future music client independent of this
compatibility runtime.

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
`describe`, `credential`, `configure`, `installation`, `run`, `endpoint`, `status`
and `control`. `describe`
reports integration version 1 and supported command names. Receiver lifecycle
belongs to its caller; closing the launcher stops its receiver. The optional
Run on login setting uses macOS ServiceManagement for the main app, not a
global system service. Auto start on launch is a separate app preference. No
hosted fork backend is installed.

Packaged state/cache defaults to `~/Library/Application Support/Soloist Runtime/`.
Development runs retain their repository-local profile. An absolute
`SOLOIST_RUNTIME_HOME` overrides the CLI profile for isolated tests. No runtime
writes belong in the application bundle. `configure` atomically copies the
user-selected executable to private profile storage after validating its
architecture and version, and records its expected 90-day expiry. The GUI
stores the user's key in macOS Keychain through the packaged helper and
configures `credential_store: keyring`; it does not put the key in preferences,
configuration JSON, logs or host argv. At runtime the key is passed through an
inherited, already-unlinked private descriptor. The legacy `--api-key-file`
option remains available for source/CLI use. `installation` reports
build and expiry metadata without account data. Spotify receives authentication
requests on startup.

Packaged `run` and the launcher default to Spotify Connect with local WebSocket
off. `run --websocket on` enables a loopback-only, unauthenticated API for
same-Mac clients. The launcher's preference checkbox provides the same opt-in. Local
health checking falls back to the private audio process when WebSocket is off;
the richer API responsiveness check requires it to be on.

The launcher persists a Spotify Connect device name and an optional CoreAudio
output UID in app preferences. Without a selected UID, the private PulseAudio
server maps macOS's default output device by CoreAudio object ID, rather than
using its first detected sink. The receiver checks for changes to the preferred
or system-default output during health checks and moves its stream when needed.
`audio outputs` and `audio select [--uid UID]` expose the same output controls to
other local clients without changing the system-wide audio device.

The control endpoint remains unauthenticated loopback preview API. Packaging
does not make it safe to expose to browsers or a LAN. See [local control](LOCAL_CONTROL.md)
and [release gates](RELEASE_READINESS.md). The future client/runtime must preserve
local control across Internet loss without assuming that every offline engine
command will succeed.
