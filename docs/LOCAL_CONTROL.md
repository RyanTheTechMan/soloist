# Local control independent of Internet connectivity

Requirement from the Wi-Fi recovery test: a future client on the same Mac must
control the local Soloist receiver and retain the current song's information
when Wi-Fi or Spotify connectivity is lost. This document is a client contract
and validation plan, not an implemented music UI or an offline-playback claim.

## Connection and display behavior

- Use the receiver's local API directly, not the official Spotify client's
  connection or a cloud round-trip as the path for local playback controls.
  Loopback communication on the same Mac does not require its Wi-Fi interface.
  Before release, finish the local API access-control work; loopback alone is
  not authentication. Do not expose the current unauthenticated API to the LAN.
- Keep receiver reachability, Soloist session authentication, active-device state
  and Spotify/network connectivity separate. Do not interpret `logged_in` as a
  network-reachability measurement or disable all controls on a Wi-Fi event.
- Maintain a local event subscription and a current playback-state model. Retain
  previously received current-item metadata and artwork already available to the
  client; do not clear them simply because a cloud request fails. Match cached
  metadata to item identity so a new unknown track never displays the old title.
- Drive controls from actual session state, advertised actions and command
  results. Soloist's documented commands require an authenticated session; do
  not pretend it is authenticated or bypass that requirement if it logs out.
- If the local receiver itself becomes unreachable, mark the last snapshot stale.
  Do not fabricate live progress or successful controls. On reconnection, obtain
  fresh authentication, playback and queue state before treating it as current.
- Do not replay ambiguous mutations after reconnecting: a skip could already
  have happened. Do not queue stale play, seek or volume commands for later
  surprise execution, and do not automatically reclaim another active device.

This applies to a client and receiver on the same Mac. A phone remotely
controlling the Mac still needs a communication path to it. It is distinct from
on-device mobile playback or supported offline downloads. Continued audio during
a short outage may be buffered/cached audio; it does not establish that uncached
tracks can load, authentication lasts indefinitely, or DJ can fetch new segments.

## Next verification

Coordinate another bounded user-controlled Wi-Fi-off interval. Keep tests local
so they do not depend on a tool/cloud connection remaining usable during it.

1. Record a baseline: authenticated active receiver, current item and playback
   position, original volume and original paused/playing state. Keep identities
   and metadata in memory only, not in diagnostic reports.
2. While Wi-Fi is off, query local auth/state and verify the current-item model
   is still available. Distinguish verified interface state from loss of all
   Internet routes if another network interface remains connected.
3. Test pause/resume and temporarily reduce then restore volume, checking actual
   state changes rather than just command acknowledgements. Restore the original
   state; do not activate another device, replace the queue or raise volume above
   the initial value. Use private audio monitoring where appropriate, never a mic.
4. Test seeking within available audio separately. Treat skipping to uncached
   content and loading new DJ segments as network-dependent/unverified until
   their actual behavior is measured.
5. Reconnect Wi-Fi and verify state reconciliation without duplicate commands,
   receiver replacement or lost local controls. Record failures and limitations.

Reference: [Soloist's documented local WebSocket API](https://developer.spotify.com/documentation/soloist/reference/websocket-api).
