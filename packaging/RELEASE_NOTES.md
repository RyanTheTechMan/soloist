Local preview for Apple Silicon macOS 27. The package includes the compatibility
runtime and its libraries. Download the official Linux ARM64 Soloist executable
from [Spotify's Downloads and updates page](https://developer.spotify.com/documentation/soloist/reference/downloads-and-updates)
and supply your own developer API key separately. The launcher installs a
private copy of the selected executable and shows its expected build expiry.
It defaults to Spotify Connect only; local WebSocket control is opt-in and
loopback-only.

This app is ad-hoc signed and not notarized. The graphical setup has an unresolved
first-run file access issue; the bundled command-line setup is the verified path.
The local control API has no authentication; never expose it beyond this Mac.

The release is a draft for review of licensing, signing, privacy, and setup
behavior. See the bundled QUICKSTART.md and repository docs/PACKAGING.md.
