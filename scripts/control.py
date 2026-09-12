"""Minimal local Soloist backend control, independent of any frontend."""
import argparse
import asyncio
import json
import re
import time
import websockets
from observe import STATE, safe_event

COMMANDS = ("activate", "deactivate", "play", "pause", "skip_next", "skip_prev", "set_volume")


async def control(command):
    if (STATE / "ws.addr").read_text().strip() != "127.0.0.1":
        raise SystemExit("Refusing non-loopback API")
    port = int((STATE / "ws.port").read_text().strip())
    if not 1 <= port <= 65535:
        raise SystemExit("Invalid API port")
    accepted = False
    async with websockets.connect(f"ws://127.0.0.1:{port}", open_timeout=5,
                                  close_timeout=2, max_size=1024 * 1024) as ws:
        await ws.send(json.dumps(command))
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), deadline - time.monotonic())
            except asyncio.TimeoutError:
                break
            event = json.loads(raw)
            result = safe_event(event)
            if result:
                print(json.dumps(result), flush=True)
            if event.get("type") == "error":
                return 1
            if event.get("type") == "command_result" and event.get("command") == command["command"]:
                accepted = True
                print("CONTROL: dispatched; playback success requires subsequent state/audio evidence", flush=True)
    return 0 if accepted else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("--uri")
    parser.add_argument("--volume", type=int)
    args = parser.parse_args()
    command = {"type": "command", "command": args.command}
    if args.uri is not None:
        if args.command != "play" or not re.fullmatch(r"spotify:(track|album|playlist|episode):[A-Za-z0-9]+", args.uri):
            parser.error("--uri requires play and a playable Spotify URI")
        command["uri"] = args.uri
    if args.command == "set_volume":
        if args.volume is None or not 0 <= args.volume <= 100:
            parser.error("set_volume requires --volume 0..100")
        command["volume"] = args.volume
    elif args.volume is not None:
        parser.error("--volume requires set_volume")
    raise SystemExit(asyncio.run(control(command)))
