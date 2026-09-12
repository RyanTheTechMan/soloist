"""Opt-in pause/resume/skip regression; saves numeric state, never music or identity."""
import argparse
import asyncio
import json
import time
import websockets
from observe import STATE
from paths import ROOT


def endpoint():
    if (STATE / "ws.addr").read_text().strip() != "127.0.0.1":
        raise ValueError("Non-loopback endpoint")
    port = int((STATE / "ws.port").read_text().strip())
    if not 1 <= port <= 65535:
        raise ValueError("Invalid port")
    return f"ws://127.0.0.1:{port}"


async def exchange(command):
    async with websockets.connect(endpoint(), open_timeout=3, close_timeout=1,
                                  max_size=1024 * 1024) as ws:
        await ws.send(json.dumps({"type": "command", "command": command}))
        while True:
            event = json.loads(await ws.recv())
            if not isinstance(event, dict):
                continue
            if event.get("type") == "error":
                raise RuntimeError("Server error; detail withheld")
            if command == "get_state" and event.get("type") == "playback_state":
                return event
            if event.get("type") == "command_result" and event.get("command") == command:
                # Soloist's documented result has no success field. Rejections
                # use an error event; this is only a dispatch acknowledgement.
                return None


async def request(command):
    return await asyncio.wait_for(exchange(command), timeout=6)


async def wait_state(status, timeout=15, previous_item=None, active=True):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = await request("get_state")
        changed = previous_item is None or state.get("item", {}).get("uri") != previous_item
        status_matches = status is None or state.get("status") == status
        if changed and status_matches and state.get("is_active") is active:
            return state
        await asyncio.sleep(0.2)
    raise TimeoutError("Playback state did not settle")


async def transition(command, status):
    previous_item = None
    if command == "skip_next":
        previous_item = (await request("get_state")).get("item", {}).get("uri")
        if not previous_item:
            raise RuntimeError("Cannot verify a skip without a current item")
    start = time.monotonic()
    await request(command)
    ack_ms = round((time.monotonic() - start) * 1000, 1)
    state = await wait_state(status, previous_item=previous_item)
    return state, {"command": command, "ack_ms": ack_ms,
                   "state_ms": round((time.monotonic() - start) * 1000, 1)}


async def main(args):
    rows = []
    start = time.monotonic()
    phase = "activate"
    failure = None
    try:
        await request("activate")
        phase = "initial_play"
        await transition("play", "playing")
        for cycle in range(1, args.cycles + 1):
            row = {"cycle": cycle}
            phase = "pause"
            _, row["pause"] = await transition("pause", "paused")
            await asyncio.sleep(args.pause_seconds)
            phase = "resume"
            state, row["resume"] = await transition("play", "playing")
            initial_position = state["position"]["position_ms"]
            await asyncio.sleep(1.2)
            phase = "position_progress"
            state = await wait_state("playing")
            # Track completion can reset position, so require movement, not a
            # positive delta. This is state evidence, not an audio measurement.
            row["position_changed"] = state["position"]["position_ms"] != initial_position
            if not row["position_changed"]:
                raise RuntimeError("Playback position did not advance")
            if args.skip_every and cycle % args.skip_every == 0:
                phase = "skip"
                _, row["skip"] = await transition("skip_next", "playing")
                await asyncio.sleep(1)
            if args.deactivate_every and cycle % args.deactivate_every == 0:
                phase = "deactivate"
                await request("deactivate")
                await wait_state(None, active=False)
                phase = "reactivate"
                await request("activate")
                _, row["reactivate"] = await transition("play", "playing")
                row["inactive_then_playing_verified"] = True
            row["passed"] = True
            rows.append(row)
            print(json.dumps(row), flush=True)
    except Exception as error:
        failure = {"phase": phase, "cycle": len(rows) + 1,
                   "error_type": type(error).__name__}
        print(json.dumps({"failure": failure}), flush=True)
    result = {"passed": failure is None and len(rows) == args.cycles,
              "requested_cycles": args.cycles, "completed_cycles": len(rows),
              "duration_seconds": round(time.monotonic() - start, 1),
              "failure": failure, "cycles": rows,
              "scope": "Local API pause/resume and position progress; not audible, codec or bit-depth proof",
              "audio_saved": False}
    output = ROOT / "build" / (args.label + "-playback-cycles.json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "cycles"}), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exercise-playback", action="store_true",
                        help="Required: this changes playback and leaves it playing if successful")
    parser.add_argument("--cycles", type=int, default=10)
    parser.add_argument("--skip-every", type=int, default=5, help="0 disables skips")
    parser.add_argument("--deactivate-every", type=int, default=0,
                        help="Opt-in: relinquish/reclaim the active device every N cycles")
    parser.add_argument("--pause-seconds", type=float, default=0.5,
                        help="0.5..60; use 30 to exercise native output suspension")
    parser.add_argument("--label", default="default")
    args = parser.parse_args()
    if not args.exercise_playback:
        parser.error("--exercise-playback is required")
    if not 1 <= args.cycles <= 100 or not 0 <= args.skip_every <= 100:
        parser.error("cycles must be 1..100 and skip-every 0..100")
    if not 0 <= args.deactivate_every <= 100:
        parser.error("deactivate-every must be 0..100")
    if not 0.5 <= args.pause_seconds <= 60:
        parser.error("pause-seconds must be 0.5..60")
    if not args.label.isascii() or not args.label.replace("-", "").isalnum() or len(args.label) > 40:
        parser.error("label must be 1..40 ASCII letters, digits or hyphens")
    raise SystemExit(asyncio.run(main(args)))
