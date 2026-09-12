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

## Known problems and unverified claims

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
