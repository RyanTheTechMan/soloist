"""Read-only loopback Soloist state observer; never print identities or tokens."""
import argparse
import asyncio
import json
import math
from pathlib import Path
import time
import websockets

STATE = Path(__file__).resolve().parents[1] / "state"


def safe_event(event):
    if not isinstance(event, dict):
        return None
    kind = event.get("type")
    if kind not in ("auth_state", "playback_state", "playback_changed",
                    "position_sync", "command_result", "error"):
        return None
    result = {"type": kind}
    for key in ("logged_in", "is_active", "success"):
        if isinstance(event.get(key), bool):
            result[key] = event[key]
    if event.get("status") in ("idle", "playing", "paused", "buffering"):
        result["status"] = event["status"]
    position = event.get("position", {})
    if isinstance(position, dict):
        for key in ("position_ms", "speed"):
            value = position.get(key)
            if type(value) in (int, float) and math.isfinite(value):
                result[key] = value
    if kind == "error":
        result["detail"] = "server error; free-form message withheld"
    return result


async def observe(seconds):
    if (STATE / "ws.addr").read_text().strip() != "127.0.0.1":
        raise SystemExit("Refusing non-loopback API")
    port = int((STATE / "ws.port").read_text().strip())
    if not 1 <= port <= 65535:
        raise SystemExit("Invalid API port")
    async with websockets.connect(f"ws://127.0.0.1:{port}", open_timeout=5,
                                  close_timeout=2, max_size=1024 * 1024) as ws:
        for command in ("get_auth_state", "get_state"):
            await ws.send(json.dumps({"type": "command", "command": command}))
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                raw = await asyncio.wait_for(ws.recv(), deadline - time.monotonic())
            except asyncio.TimeoutError:
                break
            try:
                event = safe_event(json.loads(raw))
            except (ValueError, TypeError):
                continue
            if event:
                print(json.dumps(event), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 60:
        parser.error("duration must be 1..60 seconds")
    asyncio.run(observe(args.seconds))
