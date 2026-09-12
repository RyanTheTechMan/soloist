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

**This is a development preview, not a stable one-click release.** The timer
rearm busy loop and a PI-mutex lost-wakeup bug behind pause/API stalls now have
generic runtime fixes and account-free regression tests. Soloist completed
two consecutive 30-cycle pause/resume runs with twelve skips after the mutex fix.
This does not establish that every hang is resolved. Native audio buffering
still measured about 1.9 seconds with the engine default. The user has also
confirmed seeking, volume controls and AI DJ working through Spotify Connect.
Graceful authenticated shutdown now completes the executable-byte exit check.
The supervisor supports unbounded operation and bounded crash/API recovery;
the user confirmed recovery after a short Wi-Fi interruption. Offline control
mutations, sleep/wake and output-device recovery tests are still pending.
Starting/controlling DJ through a future client's own API, extended reconnect
reliability and future Soloist versions remain unvalidated.
See [validation notes](docs/VALIDATION.md).

### Future client portability

The playback/control interface is separate from the macOS execution runtime.
Client-side models and API handling can be reused for future mobile clients,
but sharing ARM64 does not make this Hypervisor.framework runtime an iOS engine.
On-device iOS playback needs a separately supported execution/playback route.
Remote control of a desktop receiver is a different feature from local iPhone
playback; do not expose the unauthenticated local WebSocket endpoint to support it.
See [mobile feasibility](docs/MOBILE_FEASIBILITY.md) for the desktop-first decision,
Android possibilities and the separate iOS interpreter research question.

## Standalone local package

A local `.app` builder now bundles the runtime, production Linux libraries,
private macOS audio dependencies and frozen command-line controls. End users do
not need Homebrew, Python or a compiler. The separately supplied official Soloist
executable and API-key file stay outside the bundle. Packaged state is isolated
from the development receiver under Application Support.

Strict signatures, payload auditing, relocation, credential-free engine startup,
native audio startup and a bounded unpaired receiver run passed. The minimal
AppKit launcher's graphical setup still needs completion of a macOS file-access
permission test; do not treat this as a finished one-click release. No public
notarization or API access-control claim is made.
See [package build/integration instructions](docs/PACKAGING.md) and
[local quick start](packaging/QUICKSTART.md).

## Set up from source

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
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/setup.py --install-deps \
  --soloist "/path/to/extracted/soloist" \
  --api-key-file "/path/to/soloist.api"
.venv/bin/python scripts/run-receiver.py
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

The receiver runs until stopped by default. Ctrl-C requests normal Linux guest
shutdown, gives it 15 seconds to finish, then force-stops it if necessary.
Use `--seconds 1800` for a 30-minute run (30..86400 seconds are accepted).
No login item or background system service is installed.

Unexpected exits and three consecutive local API/audio-server health failures
can restart the receiver and its private audio server, using retained session
data. Retries are limited to three per launch with backoff; `--restart-limit 0`
disables them. Clean exits, explicit stop, duration completion and expired
Soloist builds do not trigger retries. Recovery does not issue activate/play
commands or reclaim playback from another device. Internet loss alone is not
treated as a local API failure; Soloist handles its own network reconnection.
This is implemented recovery policy, not proof that all real interruptions work.

`--audio-latency-ms 100` requests a smaller buffer through libpulse's supported
environment setting. After the PI-mutex fix, it passed 30 pause/resume cycles
with six skips and non-silent FLAC output. The measured stream buffer was
28–272 ms across the short tests, versus roughly 1.7 seconds with the engine
default on this Mac.
It remains optional pending longer underrun/device testing. The default `0`
leaves the engine's buffer choice unchanged. A requested buffer target is not
a guaranteed buffer size or physical audible-latency measurement.

Private executable/key paths are saved in ignored `state/installation.json`.
Subsequent runs need only `.venv/bin/python scripts/run-receiver.py`. To change the
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
.venv/bin/python scripts/control.py seek --position-ms 30000
.venv/bin/python scripts/control.py get_queue --limit 10
.venv/bin/python scripts/control.py set_shuffle --enabled on
.venv/bin/python scripts/control.py set_repeat_context --enabled off
.venv/bin/python scripts/capabilities.py
```

Run these in another terminal while the receiver is running. A command being
accepted is not proof that playback started. The receiver and observation tool
report bounded status fields without account identity or track metadata.
All documented query/control commands are now available from `control.py`.
Inputs are validated, login readiness is awaited, and mutations are never
silently retried after a lost connection. Queue output includes counts only.
This does not add undocumented DJ-init, DJ-next-segment or mixing commands.
See [release readiness](docs/RELEASE_READINESS.md) for the remaining client/API
and packaging work.

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

Source setup builds locally. The separate package builder creates a self-contained
local preview; public distribution and graphical first-run validation remain
unfinished. No build products or proprietary inputs belong in a source commit.

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
python3 scripts/test-pulse-lifecycle.py
python3 scripts/test-pi-mutex.py
python3 scripts/test-playback-cycles.py
```

Fixture tests additionally need an ARM64 Rust toolchain's bundled `ld.lld`
(on PATH via `rustc`) and Xcode's ASan/UBSan runtime. Rust is not needed to run
Soloist or for the normal setup command. If CLT lacks sanitizers, select your
full Xcode using `DEVELOPER_DIR` for the test command.

With playback active, `python3 scripts/verify-audio.py` measures the private
audio server's output monitor without a microphone or saving audio. The optional
`probe-audio-library.sh` checks Linux PulseAudio loading and a silent write.
`probe-direct.sh` is a historical owned-code x18 diagnostic, not a Soloist loader.

`verify-stability.py --seconds 600` samples the running receiver's API and interval
CPU, resident memory and private audio-buffer state, stopping after three
consecutive API failures. `--seconds 7200 --label soak-01` prepares a two-hour
test; do not call it passed until it actually finishes. `--allow-recovery` keeps
observing across receiver restarts and API failures for manual interruption tests.
Choose a new label for each run; a numeric-only JSONL journal preserves completed
samples if the test is interrupted. These are snapshots, not continuous underrun
or acoustic-dropout detection. The active control test
`verify-control-latency.py --exercise-volume-to-zero` briefly mutes and restores
the original volume; `--exercise-pause` pauses then requests resume. These measure
the private monitor, not a microphone or physical-device latency. A suspended
monitor can stop delivering PCM, which is an inconclusive silence measurement,
not a measured response time. JSON results remain in ignored `build/`.

`verify-playback-cycles.py --exercise-playback --cycles 30` actively tests
pause/resume and position movement, skipping every fifth cycle. It leaves
playback running on success and does not restore the previous queue position.
Use `--skip-every 0` to disable skips and `--label trial-name` to keep separate
numeric reports. Command acknowledgement, settled state and audio output are
separate evidence; this test does not measure codec or source bit depth.
`--pause-seconds 30` exercises output suspension, and `--deactivate-every 1`
also tests relinquishing/reclaiming the active Connect device each cycle.

Normal setup uses the smaller `sysroot-packages.json`; optional HTTPS tests use
`sysroot-network-test-packages.json`. Packages are fetched over HTTPS and verified
against pinned sizes/SHA256s; only package data is extracted, never maintainer
scripts. Independent OpenPGP Release verification is not implemented. Rebuilding
requires these pinned downloads to remain available or an existing local cache.
