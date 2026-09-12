# Soloist Runtime - local macOS preview

1. Download and extract the **Linux ARM64** executable from
   [Spotify's official Soloist download page](https://developer.spotify.com/documentation/soloist/reference/downloads-and-updates).
2. Save your Soloist developer API key alone in an owner-only file (`chmod 600
   /path/to/soloist.api`). Keep both files outside the application bundle.
3. Open **Soloist Runtime.app**, choose those two files, and click **Start**.
4. Select **Soloist Runtime** in Spotify Connect to authenticate and play.

Close the app or click Stop to shut down the receiver. No login item or global
audio daemon is installed. This package contains the compatibility runtime and
its dependencies; it does not require Homebrew, Python, Xcode or a music client
to run. Initial pairing still uses Spotify's supported flow and your account.

This first local preview is Apple Silicon/macOS 27 only and ad-hoc signed, not
notarized. It is not a public release or an iOS/Windows package. Do not disable
Gatekeeper, SIP or other system security to run it.

Graphical first-run testing is incomplete. A path entered directly from the
Documents folder stalled at a macOS file-access authorization request, and the
first file-picker test could not select the executable. Command-line setup was
verified. Do not grant Full Disk Access as a workaround. If setup waits, check
for a macOS file-access prompt or stop it; unresolved picker/permission behavior
remains a release gate.

Paths to your supplied files and engine session state live in
`~/Library/Application Support/Soloist Runtime/`, not inside the app. Retain the
chosen executable/key files there or elsewhere on your Mac; moving them requires
choosing their new paths. They are not copied or uploaded by setup. Spotify
receives authentication requests when the receiver is started.

## Without the launcher, or from another application

Use the bundled command-line executable:

```sh
"Soloist Runtime.app/Contents/Helpers/runtime-cli.app/Contents/MacOS/runtime-cli" describe
"Soloist Runtime.app/Contents/Helpers/runtime-cli.app/Contents/MacOS/runtime-cli" doctor --audio --soloist /path/to/soloist
"Soloist Runtime.app/Contents/Helpers/runtime-cli.app/Contents/MacOS/runtime-cli" configure --soloist /path/to/soloist --api-key-file /path/to/soloist.api
"Soloist Runtime.app/Contents/Helpers/runtime-cli.app/Contents/MacOS/runtime-cli" run
```

`status`, `endpoint` and `control` are available while running. `run --help`
shows test-duration, buffer and recovery options. `SOLOIST_RUNTIME_HOME` can
select a different absolute data directory for isolated CLI integration tests.
The graphical launcher uses the default profile.

The local WebSocket API is currently unauthenticated and loopback-only. **Do not
expose it to browsers, a LAN or the Internet.** Finishing its access-control
design is a release gate, not something that packaging automatically solves.

The manifest records library versions and payload checksums. Bundled license
notices are under `Contents/Resources/Licenses`. Redistribution compliance and
Developer ID signing/notarization need separate review before any public release.
