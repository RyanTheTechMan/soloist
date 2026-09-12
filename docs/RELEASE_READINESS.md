# Backend release gates

The compatibility runtime is separate from a future music client. This list
tracks unfinished work; implementing a test harness does not pass its tests.

## Checkpoint and lifecycle

- Working playback/PI-mutex checkpoint: local commit `4002de9`.
- Host SIGINT/SIGTERM forwarding: implemented as opt-in ordinary Linux signal
  delivery on the runtime's non-vCPU signal thread. No Soloist code modifications.
- Clean stop: owned caught/default signal fixtures pass. A 30-second authenticated
  Soloist run exited normally, with preflight and post-exit text checks passing.
- Supervision: finite backoff/retry budget, graceful-stop deadline, crash and
  repeated local API/audio-server health failure handling. Offline policy tests
  pass. Real crash/audio-server recovery and adverse timing remain to validate.
- Stored session: restored on the subsequent live receiver launch; local activate
  and play succeeded, followed by non-silent private output samples.
- Short Wi-Fi interruption/reconnection: user reports uninterrupted current-song
  audio and automatic restoration of Spotify's player information on reconnection.
  Local command mutations during the outage, prolonged outages, sleep/wake and
  output-device changes remain pending. Never toggle connectivity or sleep the
  computer without coordination.

## Longer audio tests

- Soak telemetry now supports up to 24 hours and retains incremental numeric
  samples: API response, CPU, RSS, active streams, output format and buffering.
- Multi-hour completed playback, continuous underrun/dropout measurement, natural
  track-boundary/gapless measurement and energy comparisons remain pending.
- Source FLAC bit depth and end-to-end bit-perfect delivery remain unverified.
  A float32 output stream does not establish either.

## Future client's API

The command helper covers all currently documented local commands, waits for
login, validates field types and does not retry ambiguous mutations. Offline
tests cover validation, acknowledgement matching, readiness and private output.
Individual live tests for queue insertion, repeat and shuffle remain pending.
The future same-Mac client must retain local control and current-item state when
Spotify is unreachable. [Local-control requirements](LOCAL_CONTROL.md) separate
this design requirement from offline-command behavior not yet verified.

AI DJ through Spotify Connect is user-confirmed. As of this checkpoint, the
[official WebSocket command reference](https://developer.spotify.com/documentation/soloist/reference/websocket-api)
does not document DJ initialization, next DJ segment, crossfade or beat-mixing
controls. The observed public action list added no other actions. This is a
concrete local-API gap, not evidence that Soloist's internal player cannot do DJ.
Own-client DJ initiation and transition control need separate working prototypes;
do not invent command names or claim a regular skip is a DJ-segment command.

## Distribution and security

- Local relocatable bundle builder and audits are implemented: compatibility
  runtime, production library sysroot, frozen controls and private macOS playback
  dependencies. Engine/key exclusion, strict signatures, relocation, engine
  version/text integrity and native audio startup checks passed. See [packaging](PACKAGING.md).
- A small AppKit setup/Start/Stop launcher is implemented, but graphical
  first-run validation is incomplete: the test stalled at macOS Documents-folder
  authorization when passing paths directly. No privacy settings were changed.
  The file picker also left the executable unselectable in the first test.
  Command-line setup and a 30-second unpaired receiver run passed without a
  compiler, Python or Homebrew on PATH. No packaged authenticated playback claim.
- Audit dependency licenses/notices and version manifest; verify fresh install
  and a later official Soloist build without executable-specific offsets.
- Resolve local API access control. Loopback is not authentication. A proxy in
  front of an otherwise reachable unauthenticated upstream port is insufficient.
  Do not expose the current WebSocket API to a LAN, browser client or mobile app.
- Validate a production signing/notarization/distribution route separately from
  the current local ad-hoc signature. No publishing is authorized by this work.

The runtime itself is macOS ARM64/HVF only. Future mobile clients can share the
control model, but on-device iOS playback requires a different supported engine
route; it does not inherit macOS Hypervisor.framework support. Desktop-first is
the current priority; [mobile feasibility](MOBILE_FEASIBILITY.md) records the
alternatives without promising support or making it a desktop release gate.
