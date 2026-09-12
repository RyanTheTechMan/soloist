# Desktop first, mobile as a separate feasibility question

Assessment on 2026-09-12: finish the standalone desktop runtime first. Mobile
is not a prerequisite. This repository remains independent of a future music
client; neither a shared ARM64 instruction set nor reusable client models imply
that the macOS execution backend works on a phone.

## What can be shared

Keep a versioned runtime/control contract, playback state models, validation and
owned Linux compatibility fixtures independent of the user interface. A future
client can target a supported local engine without knowing how its CPU executes.
The current package reports its actual host support as macOS ARM64 only.
Windows requires its own execution/audio adapters and validation; Linux can use
the official Linux engine directly with suitable libraries and audio integration.

A mobile remote control for a desktop receiver is a distinct, plausible client
feature, not on-phone playback. It would need a reachable desktop and a designed,
authenticated transport. Do not expose today's unauthenticated loopback API.

## iOS and iPadOS: possible research, not a supported port

The present engine uses macOS Hypervisor.framework. Installed Xcode 27 beta SDK
inspection found the framework in macOS, not iPhoneOS or the Mac's iOSSupport
frameworks; `hv_vm_create` is marked macOS-only. This backend cannot simply be
linked into an ordinary iOS app. See [Apple Hypervisor documentation](https://developer.apple.com/documentation/hypervisor).

One candidate is an in-process interpreter plus Linux syscall translation,
without a guest Linux kernel and without changing Soloist's instructions.
[UTM SE](https://github.com/utmapp/UTM/blob/main/README.md) demonstrates ARM64
interpretation on iOS without JIT workarounds or jailbreaking. It explicitly
trades speed for compatibility. That is evidence for the technique, **not**
evidence that Soloist's authentication, lossless decoding or DJ will work within
a phone's real-time, battery and thermal limits. We have not built that backend.

An authorized native Soloist mobile library would be a preferable route if one
becomes available. Spotify's existing [iOS SDK](https://developer.spotify.com/documentation/ios)
instead delegates playback to the installed Spotify app; it does not satisfy
the independent Soloist playback requirement.

An [iPad app running on Apple Silicon macOS](https://developer.apple.com/documentation/apple-silicon/running-your-ios-apps-in-macos)
can help test client UI and API handling without a simulator. It cannot validate
real iPhone execution permissions, background audio, thermal limits or battery
use. Distribution eligibility also needs separate review; no App Store approval
is established by the interpreter example or by a successful local build.

## Android: more plausible, still unverified

My engineering assessment is that Android is the better first experiment for
on-device Soloist because it already uses a Linux kernel and commonly ARM64.
That does not remove Android's different C library, sandbox, audio integration,
background lifecycle or executable-packaging requirements.
[Android's documented execution restrictions](https://developer.android.com/about/versions/10/behavior-changes-10#execute-permission)
specifically prevent modern-target apps from directly executing files in their
writable app home. Desktop-style "select a downloaded executable and run it"
therefore is not a ready-made Android deployment design. A supported packaged
native route or interpreter would need investigation, including permission to
distribute any proprietary components. We will not rely on old target-SDK
loopholes, rooting, private entitlements or executable patches.

## A small future go/no-go test

If mobile is prioritized later, first run owned ARM64/TLS/threading fixtures on
a real device using a permitted execution backend. Then test the unchanged
official engine, authenticated playback, actual delivered codec and sustained
audio, followed by background playback, CPU, temperature and energy. Stop before
building a full client if that cannot meet an acceptable device budget.

No on-device iOS, iPadOS or Android execution, audio or energy result is claimed
at this checkpoint. Shared architecture is worth preserving; mobile support is
not worth promising before this experiment.
