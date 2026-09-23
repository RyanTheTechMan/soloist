# Soloist Runtime - local macOS preview

1. Download and extract the **Linux ARM64** executable from
   [Spotify's official Soloist download page](https://developer.spotify.com/documentation/soloist/reference/downloads-and-updates).
2. Save your own Soloist developer API key alone in an owner-only file (`chmod 600
   /path/to/soloist.api`). Do not put it in this source tree or app bundle.
3. Open **Soloist Runtime.app**, choose the extracted executable and API-key file,
   then click **Start**. The selected executable is copied into private
   Application Support storage after a credential-free version check. You may
   move or delete the downloaded original afterward; retain the API-key file.
4. Select **Soloist Runtime** in Spotify Connect to authenticate and play.

The launcher shows the installed version and expected expiry calculated from
Soloist's build timestamp plus its documented 90-day lifetime. Select a newer
official executable and click Start to replace an expiring or expired build.
Soloist's own expired-build exit code is authoritative. The **Get Soloist**
button opens the official downloads page; no Spotify archive or executable is
included in this package or its releases.

Connect-only mode is the default. Enable **local WebSocket control** before
starting if you want a trusted same-Mac client to use Soloist's documented API.
It binds only to `127.0.0.1` on an assigned port. The API has no client
authentication, so do not forward it to a browser, LAN or Internet endpoint.

Close the app or click Stop to shut down the receiver. No login item or global
audio daemon is installed. This package contains the compatibility runtime and
its dependencies; it does not require Homebrew, Python, Xcode or a music client
to run. Initial pairing still uses Spotify's supported flow and your account.

This first local preview is Apple Silicon/macOS 27 only and ad-hoc signed, not
notarized. It is not a public release or an iOS/Windows package. Do not disable
Gatekeeper, SIP or other system security to run it.

Graphical first-run file selection still needs on-device validation; the
command-line import has been tested with an official build. Do not grant Full
Disk Access as a workaround. If setup waits, check for a macOS file-access
prompt or stop it; file-picker/permission behavior remains a release gate.

The installed executable, its version/expiry metadata and engine session state
live in `~/Library/Application Support/Soloist Runtime/`, not inside the app.
The API-key file stays at the path you chose and is not copied or uploaded by
setup. Spotify receives authentication requests when the receiver starts.

## Without the launcher, or from another application

Use the bundled command-line executable:

```sh
"Soloist Runtime.app/Contents/Helpers/runtime-cli.app/Contents/MacOS/runtime-cli" describe
"Soloist Runtime.app/Contents/Helpers/runtime-cli.app/Contents/MacOS/runtime-cli" doctor --audio --soloist /path/to/soloist
"Soloist Runtime.app/Contents/Helpers/runtime-cli.app/Contents/MacOS/runtime-cli" configure --soloist /path/to/soloist --api-key-file /path/to/soloist.api
"Soloist Runtime.app/Contents/Helpers/runtime-cli.app/Contents/MacOS/runtime-cli" installation
"Soloist Runtime.app/Contents/Helpers/runtime-cli.app/Contents/MacOS/runtime-cli" run
```

Add `--websocket on` to `run` to enable `status`, `endpoint` and `control` while
running; packaged `run` defaults to Connect-only. `run --help`
shows test-duration, buffer and recovery options. `SOLOIST_RUNTIME_HOME` can
select a different absolute data directory for isolated CLI integration tests.
The graphical launcher uses the default profile.

The local WebSocket API is currently unauthenticated and loopback-only. **Do not
expose it to browsers, a LAN or the Internet.** Finishing its access-control
design is a release gate, not something that packaging automatically solves.

The manifest records library versions and payload checksums. Bundled license
notices are under `Contents/Resources/Licenses`. Redistribution compliance and
Developer ID signing/notarization need separate review before any public release.
