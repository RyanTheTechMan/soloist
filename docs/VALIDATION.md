# Validation checkpoint — 2026-09-12

Scope: Apple Silicon macOS 27 beta, official Linux ARM64 Soloist 1.3.8.36,
elfuse base `4023647491db64adc43de76284206d8ab81ff6e3` plus the included patch.
This records local observations, not a compatibility certification.

## Observed working

- Credential-free startup and version output through the hardware-assisted runtime.
- Connect authentication, stored-session restoration, local API activation/play.
- Engine-reported FLAC at 44,100 Hz and a native stereo float32 audio stream.
- Private output monitor: 126,997 frames; RMS 0.03027, peak 0.12851;
  non-silent samples. No microphone was used and no audio payload was saved.
- User-confirmed steady audible playback and working song skips.
- Startup integrity comparison: 20,478,304 executable bytes from the main ELF
  and initial dynamic loader matched their files before execution and after exit.
  Authenticated playback passed preflight; its post-exit comparison was not
  completed. This is not continuous monitoring or coverage of later dlopen images.
- No Soloist instruction modifications or per-version code offsets were used.

## Tests

- Upstream multiple-vCPU tests: 5/5.
- ELF-header tests: 54/54, including eight new dynamic-tag assertions.
- Owned Linux fixtures: x18/TLS, syscalls, procfs readlink, absolute futex clocks,
  IPv4 multicast and explicitly empty IPv4/IPv6 error queues.
- Private argument-file validation: 13 cases.
- Executable-memory checker negative tests under ASan/UBSan.
- Four credential-free HTTPS checks: native macOS and Linux curl against two
  fixed Spotify URLs, with certificate verification enabled.

## Problems at the initial checkpoint (updates below)

- After approximately seven minutes of playback/skips, CPU reached about 99%
  of one core and the local API stopped returning events. A host sample showed
  a worker cycling through timerfd_settime and epoll_pwait. Cause/fix pending.
- Earlier idle CPU dropped from about 199% to 0.5% after the futex deadline fix;
  one early playback snapshot was 2.7%. These are not sustained energy results.
- Native audio buffering measured approximately 1.9 seconds; audible control
  latency and underrun behavior need controlled measurement.
- Source bit depth is unknown. Float32 output does not establish 24-bit source
  or bit-perfect delivery to the audio device. FLAC playback is not AI DJ proof.
- AI DJ, mixing, extended reconnects, sleep/wake, audio-device changes, other
  macOS releases and the full upstream Linux/QEMU test matrix are unverified.
- IPv4 multicast currently supports the eight-byte ip_mreq, not interface-index
  membership requests. ICMP error queues are explicitly empty, not complete
  Linux ICMP delivery. Futex behavior during host wall-clock jumps needs testing.
- Initial text relocations and writable/executable segments are rejected by
  integrity mode. Later-loaded library coverage remains incomplete.

The prior instruction-patched experimental loader is not included and its
playback/bit-depth evidence does not certify this compatibility runtime.

## Follow-up: timer rearm fix and remaining pause stall

The original notes above describe the initial checkpoint. The following work
is subsequent; the backend is still not certified stable.

- Reproduced a timerfd defect without Soloist: after expiration, rearming without
  reading left stale kqueue readiness behind. Linux resets unread expirations on
  settime; updating the existing kqueue timer did not. The fixture failed at its
  stale-readiness assertion on the committed baseline (exit 6).
- The host adapter now removes/drains the old timer before rearming and rounds
  nonzero nanoseconds upward to microseconds. The fixture passes 32 cycles across
  realtime/monotonic and absolute/relative modes. No Soloist instructions changed.
- Added a separate edge-triggered epoll MOD/eventfd fixture: 32 cycles pass on
  the existing epoll adapter; no speculative epoll change was made.
- In an approximately ten-minute API/CPU sampling run, CPU was generally 3–4%
  during playback between track changes. Pause/resume and skips initially worked.
  After a later pause, API events stopped at low CPU (around 0.25%). This run
  **failed** stability validation; absence of the high-CPU loop is not a full fix.
- The stalled process still completed WebSocket handshakes, but did not send
  auth/playback events. Its private PulseAudio server responded to inspection;
  the stream was corked. Host samples showed waiting threads, not the prior
  timerfd_settime busy loop. Root cause remains open.
- Volume-to-zero test: 3.3 ms command acknowledgement and 14 ms response at the
  private monitor, with approximately 1.73 seconds still buffered. Volume can
  change at the output stage; this does not establish seek/skip latency or an
  acoustic response time. Original volume restoration was acknowledged.
- Pause test did not establish a silence transition and its resume request
  timed out. Monitor suspension can stop samples rather than emit silence, so
  the silence result itself is inconclusive; the API failure is a separate fact.
- A 100 ms PULSE_LATENCY_MSEC experiment did not establish working Soloist output
  after restart; the stream remained corked. The default remains unchanged (0).
- An owned PulseAudio fixture passed on native macOS and Linux/HVF, with default
  and 100 ms buffers: context/stream creation, 64 cork/uncork callbacks, silent
  writes, and shutdown. This narrows investigation but does not certify Soloist's
  more complex audio/control interaction. It uses no account or music.
- The focused suite, 5 vCPU tests, 54 ELF-header tests and four HTTPS checks pass.
  Authenticated runs were terminated by the wrapper/host, so their post-exit text
  comparison remains incomplete. elfuse's timeout is a stalled-vCPU watchdog,
  not a wall-clock execution limit; the parent owns the receiver duration limit.

References for the generic timer and audio semantics:

- [Linux timerfd semantics](https://man7.org/linux/man-pages/man2/timerfd_create.2.html)
- [Asio epoll reactor](https://github.com/boostorg/asio/blob/develop/include/boost/asio/detail/impl/epoll_reactor.ipp)
- [PulseAudio buffer configuration](https://github.com/pulseaudio/pulseaudio/blob/master/src/pulse/stream.c)

## Follow-up: PI mutex ownership handoff

- The low-CPU pause stall reproduced on both plain-futex wait backends. Switching
  away from Darwin address waits was not a fix; that diagnostic switch was removed.
- A bounded, numeric-only futex trace located blocked `FUTEX_LOCK_PI` callers.
  The old unlock path cleared the entire lock word and woke one waiter. That
  waiter could acquire without `FUTEX_WAITERS`, then unlock entirely in userspace,
  leaving the other queued waiters asleep. No guest buffers, account state or
  music were logged. Temporary tracing was removed from the shipped patch.
- The adapter now transfers ownership to a queued waiter under the bucket lock
  and preserves `FUTEX_WAITERS`. It also reasserts the flag when enqueueing after
  a racing owner replacement and keeps timeout flag cleanup under the queue lock.
  These are generic Linux ABI changes; no Soloist instructions were modified.
- The owned three-worker glibc PI-mutex fixture exceeded its 10-second wall limit
  before the fix. Afterward, all 192 contended acquisitions completed, with
  executable-byte checks passing before and after fixture execution. Additional
  checks cover owner rejection, recursive raw-lock rejection, trylock, a timed
  waiter's removal and final unlock. Actual priority boosting is not implemented;
  this is not complete real-time scheduling or PI/robust-futex certification.
- The short Soloist control test failed on resume in cycle 1 with bucket waits
  and cycle 2 with Darwin address waits. With ownership handoff fixed, 30 cycles
  and six skips completed in 66.8 seconds. Pause state took 15.8–32.7 ms and
  resume state 29.1–402.3 ms in that run. These are API/state measurements, not
  physical audio latencies. Source bit depth remains unverified.
- A subsequent private monitor captured 132,172 non-silent stereo frames at
  44,100 Hz. A pause/silence measurement remained inconclusive because no silence
  transition was captured, but the resume command was acknowledged rather than
  timing out. No microphone or saved music was used.
- Focused runtime tests, 5/5 vCPU checks, 54/54 ELF-header checks, all four
  PulseAudio lifecycle cases and all four credential-free HTTPS checks passed.
- A second 30-cycle run also passed (61.8 seconds), now explicitly waiting for
  the item identity to change after each skip rather than accepting any playing
  snapshot. Identities stay in memory and are not printed or saved.
- Two additional cycles with 30-second pauses resumed successfully; the private
  audio monitor verified non-silent output afterward. Five deactivate/activate
  cycles each verified the inactive state and subsequent playing state.
- Ten repeated owned PI fixture runs passed (1,920 contended acquisitions).
  Six offline control-harness tests passed, including the documented ack shape,
  withheld error details, stale skip snapshots and loopback validation.
- The exported patch applied to a fresh pinned-source archive, compiled, and
  passed the PI fixture with preflight/exit executable-byte comparisons.
- A complete 600-second run passed all 60 API/CPU samples, including the second
  30-cycle control run, long pauses and active-device handoffs. Median interval
  CPU was 3.745% of one core; the highest interval was 15.59%. Every API sample
  responded, with a maximum of 34.2 ms. This is ten-minute mixed-workload evidence,
  not overnight, sleep/wake, network interruption or audible-continuity certification.

Semantics: [Linux PI futexes](https://man7.org/linux/man-pages/man2/futex.2.html)
and [FUTEX_UNLOCK_PI](https://man7.org/linux/man-pages/man2/FUTEX_UNLOCK_PI.2const.html).

## Follow-up: optional smaller buffer

With the cleaned-up final runtime build (temporary futex diagnostics removed),
`--audio-latency-ms 100` restored the stored session and passed another 30
pause/resume cycles and six identity-verified skips in 62.0 seconds. The first
control attempt was made before stored-session login completed and was rejected;
after observing authenticated state, the complete test passed. This is distinct
from the prior after-login deadlock.

Soloist reported FLAC at 44,100 Hz. The private monitor captured 132,642 stereo
frames with non-silent output. The measured stream buffer was 272,352 us in the
audio check and 212,054 us in the volume check; sink latency was 170,666 us.
These values are not a guaranteed 100 ms buffer or a physical end-to-end latency.
Volume-to-zero was acknowledged in 4.6 ms, with the private monitor detecting
silence after 21.3 ms; restoring the original volume was acknowledged.
A further 30-second pause/resume passed and produced non-silent output; after
that resume the stream/sink measurements were 28,387/26,791 us. The variation
is another reason not to present the requested target as a fixed achieved delay.

The smaller buffer remains opt-in. Long-duration underruns, sleep/wake, real
network loss, audio-device changes, graceful authenticated shutdown/text-exit
comparison and source bit depth remain separate validation work.

## User listening checkpoint

The user subsequently confirmed play, pause, skipping, seeking and volume
control working well, and reported AI DJ also working well. This is user-observed
AI DJ operation through Spotify Connect, not an automated DJ test or proof that
the documented local API can initiate DJ and request the next DJ segment.

## Follow-up: graceful lifecycle and recovery instrumentation

- Optional host SIGINT/SIGTERM forwarding now uses the existing non-vCPU
  sigwait thread and normal Linux guest signal delivery. Signals are held until
  the guest is initialized; guest access is disabled before teardown. Soloist
  executable instructions remain untouched.
- Three owned Linux cases passed: caught SIGTERM, caught SIGINT and default
  SIGTERM termination. Each completed the post-exit executable comparison.
- A real 30-second run restored the stored account session and connected its
  cloud WebSocket, then stopped with exit code 0 without forced termination.
  Both preflight and exit comparisons passed for 20,478,304 executable bytes.
  This closes the prior authenticated post-exit-check gap for this run, not
  continuous monitoring or coverage of later-loaded libraries.
- Seven offline supervisor tests passed, including normal exit, requested stop,
  graceful duration completion, bounded kill fallback, three-strike health
  recovery, resetting the failure streak and bounded/no-retry exit policy.
- Subsequent unbounded receiver startup restored the saved session. Explicit
  local activation/play produced non-silent private output: 132,642 stereo
  frames at 44,100 Hz, float32, buffer 344,979 us and sink 170,666 us. No
  microphone or saved music was used. Source bit depth remains unverified.
- Five local client-helper tests and six existing playback-harness tests passed.
  All documented command shapes are accepted by validation; invalid values,
  unsupported commands, premature login and ambiguous mutation retries are
  covered. This is not live verification of every command.
- Four offline receiver tests passed: explicit health-query response with a
  logged-out account, non-loopback rejection, diagnostic filtering and atomic
  owner-only status files. Live state and queue queries also returned successfully.
- The exported patch applied to a fresh pinned-source archive, compiled and
  passed the owned PI fixture. The focused suite, 5/5 multiple-vCPU checks and
  54/54 ELF-header checks passed after the lifecycle change.
- The recovery monitor now records numeric API/CPU/RSS/audio-buffer snapshots
  across restarts. Real Wi-Fi, sleep/wake, output-device recovery and a completed
  multi-hour soak remain pending; no success is inferred from the new harness.
