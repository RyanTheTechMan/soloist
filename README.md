# Soloist macOS compatibility runtime

Run Spotify's official **Linux ARM64 Soloist executable, unchanged**, on Apple
Silicon macOS. This is an experimental compatibility backend, not a music-player
frontend and not a Fastpotify fork. A frontend can use Soloist's local API.

Built on [elfuse](https://github.com/sysprog21/elfuse): Apple's
Hypervisor.framework executes ARM64 instructions in virtual CPUs while a host
process implements Linux syscalls. There is **no guest Linux kernel or OS image**.
This is hardware-assisted virtualization, not native Mach-O execution.

No Soloist instruction rewriting, binary-specific offsets, private Apple
entitlements, SIP changes, or authentication bypasses are used. The repository
contains integration source and an elfuse patch, **not Soloist, account keys,
session data, or music**. It is unofficial and not endorsed by Spotify.

## Status

Authenticated playback and song skipping have worked with Soloist 1.3.8.36.
The engine reported FLAC at 44.1 kHz and produced audible, non-silent output.
Source bit depth and end-to-end bit-perfect output remain unverified.

**This is a development preview, not a stable one-click release.** A later
playback run developed approximately one CPU core of sustained usage and an
unresponsive local API. Native audio buffering also measured about 1.9 seconds.
These are outstanding bugs. AI DJ, extended reconnect reliability and future
Soloist versions are not validated. See [validation notes](docs/VALIDATION.md).

## Set up

Requirements:

- Apple Silicon Mac. Currently tested on macOS 27 beta only; other macOS versions
  are unverified. Intel Macs, Windows and Linux hosts are not supported here yet.
- Apple's Command Line Tools (`xcode-select --install`) or full Xcode.
- [Homebrew](https://brew.sh/) in its standard ARM64 location, `/opt/homebrew`.
- Python 3.12 or newer. If needed: `brew install python`.
- Internet access for the pinned runtime source, Linux libraries and Spotify.

1. Download the **Linux ARM64/AArch64** archive from
   [Spotify's official Soloist downloads page](https://developer.spotify.com/documentation/soloist/reference/downloads-and-updates)
   and extract it. Keep the resulting `soloist` executable outside this
   repository. Do not use the x86-64 download.
2. Obtain your own Soloist API key and meet Spotify's account requirements,
   including Premium, as described in the
   [authentication guide](https://developer.spotify.com/documentation/soloist/concepts/authentication).
   Save the key alone in a private file outside the repository using an editor.
   Restrict its permissions: `chmod 600 "/path/to/soloist.api"`.
   Never paste the key into a command argument or commit it.
3. Open a terminal in this repository and run:

```sh
python3 scripts/setup.py --install-deps \
  --soloist "/path/to/extracted/soloist" \
  --api-key-file "/path/to/soloist.api"
python3 scripts/run-receiver.py
```

Replace the two paths. Setup installs missing Homebrew `binutils`,
`pulseaudio` and `ca-certificates`, fetches pinned elfuse source, applies the
compatibility patch, builds and signs the runtime, prepares the library sysroot,
and verifies credential-free Soloist startup. Omit `--install-deps` to reject
missing dependencies instead of installing them. Setup does not copy or download
Soloist and does not send your key during its startup test.

Select **Soloist macOS Lab** in Spotify Connect on the same network for initial
authentication, then play a normal song. Permit local-network access if macOS
asks. Stored credentials support later sessions. Initial pairing still needs
Spotify's supported authentication flow; this layer does not replace it.

The receiver runs for 15 minutes by default, then shuts down; Ctrl-C also stops
it. Use `--seconds 1800` for a 30-minute test. This deliberate bounded mode
remains while stability is being investigated. No login item or background
system service is installed.

Private executable/key paths are saved in ignored `state/installation.json`.
Subsequent runs need only `python3 scripts/run-receiver.py`. To change the
official executable, rerun setup with its new path. Compatibility with a new
version must still be tested; no version-specific binary patch is required.

## Optional local controls

These tools use Soloist's
[documented local WebSocket API](https://developer.spotify.com/documentation/soloist/reference/websocket-api),
not a browser engine or the Spotify desktop app for decoding.

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/observe.py --seconds 10
.venv/bin/python scripts/control.py activate
.venv/bin/python scripts/control.py play
.venv/bin/python scripts/control.py skip_next
.venv/bin/python scripts/control.py pause
```

Run these in another terminal while the receiver is running. A command being
accepted is not proof that playback started. The receiver and observation tool
report bounded status fields without account identity or track metadata.

## Security and packaging boundaries

- The sysroot is a Linux library environment, **not a filesystem sandbox**.
  Only run trusted official executables.
- The WebSocket API is loopback-only but has no built-in client authentication
  or origin validation. Other local applications and browser-origin requests
  remain a concern; a finished app needs a deliberate access-control design.
- The API key is passed from an owner-only file into guest argv, not host argv.
  It still exists in process memory and is not hidden from privileged debugging.
  The runtime rejects verbose syscall tracing and GDB with private arguments.
- Audio uses a private playback-only PulseAudio process and Unix socket, with no
  TCP audio listener, microphone input, or global daemon. It exits with the receiver.
- Build products, fetched third-party source/libraries, credentials, state and
  caches are ignored. Do not distribute a ZIP of the working directory.
  A source-only archive can be made from committed files with
  `git archive --format=zip --output=soloist-macos-runtime-source.zip HEAD`.
- Spotify's executable must be obtained separately from its official page.
  Review upstream licenses before distributing a prebuilt runtime or sysroot;
  see [third-party notices](THIRD_PARTY_NOTICES.md).

Setup currently builds locally. A signed, self-contained runtime bundle that
needs only the official executable and the user's key is the intended packaging
direction, but is **not delivered by this source preview**.

## Development and tests

The elfuse base is pinned in `scripts/setup.py`; our Linux ABI changes are in
`patches/elfuse-soloist.patch`. The fetched/patched checkout lives in ignored
`vendor/elfuse`. Setup refuses to overwrite a mismatched revision or patch.
After changing the patch, preserve or move that checkout aside before rebuilding.

```sh
bash scripts/test.sh
make -C vendor/elfuse test-multi-vcpu test-elf-headers-host
python3 scripts/prepare-sysroot.py --audio --network-test
python3 scripts/test-https.py
```

Fixture tests additionally need an ARM64 Rust toolchain's bundled `ld.lld`
(on PATH via `rustc`) and Xcode's ASan/UBSan runtime. Rust is not needed to run
Soloist or for the normal setup command. If CLT lacks sanitizers, select your
full Xcode using `DEVELOPER_DIR` for the test command.

With playback active, `python3 scripts/verify-audio.py` measures the private
audio server's output monitor without a microphone or saving audio. The optional
`probe-audio-library.sh` checks Linux PulseAudio loading and a silent write.
`probe-direct.sh` is a historical owned-code x18 diagnostic, not a Soloist loader.

Normal setup uses the smaller `sysroot-packages.json`; optional HTTPS tests use
`sysroot-network-test-packages.json`. Packages are fetched over HTTPS and verified
against pinned sizes/SHA256s; only package data is extracted, never maintainer
scripts. Independent OpenPGP Release verification is not implemented. Rebuilding
requires these pinned downloads to remain available or an existing local cache.
