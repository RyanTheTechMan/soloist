"""Documented commands, login readiness and bounded local I/O.

Acknowledgement means dispatch, not playback. Never retry a mutation following
a transport failure: the server may already have applied it (especially skip).
"""
import asyncio
import json
from pathlib import Path
import re
import websockets

STATE = Path(__file__).resolve().parents[1] / "state"
QUERY_EVENTS = {"get_auth_state": "auth_state", "get_state": "playback_state",
                "get_queue": "queue_changed"}
FIELDS = {"get_auth_state": (), "get_state": (), "get_queue": ("limit",),
          "activate": (), "deactivate": (), "play": ("uri",), "pause": (),
          "skip_next": (), "skip_prev": (), "seek": ("position_ms",),
          "set_volume": ("volume",), "set_shuffle": ("enabled",),
          "set_repeat_context": ("enabled",), "set_repeat_track": ("enabled",),
          "add_to_queue": ("uri",)}


def command(name, **fields):
    if not isinstance(name, str) or name not in FIELDS or set(fields) - set(FIELDS[name]):
        raise ValueError("Unknown command or unsupported fields")
    required = set(FIELDS[name]) if name not in ("play", "get_queue") else set()
    if required - set(fields):
        raise ValueError("Missing required command field")
    for field, value in fields.items():
        if field == "enabled":
            if type(value) is not bool:
                raise ValueError("enabled must be a boolean")
        elif field == "uri":
            kinds = "track" if name == "add_to_queue" else "track|album|playlist|episode"
            if not isinstance(value, str) or not re.fullmatch(r"spotify:(" + kinds + r"):[A-Za-z0-9]{1,64}", value):
                raise ValueError("Expected a documented playable Spotify URI")
        else:
            maximum = {"volume": 100, "position_ms": 2147483647, "limit": 10000}[field]
            if type(value) is not int or not 0 <= value <= maximum:
                raise ValueError(field + " must be an integer from 0 to " + str(maximum))
    return {"type": "command", "command": name, **fields}


def endpoint(state=STATE):
    if (state / "ws.addr").read_text().strip() != "127.0.0.1":
        raise ValueError("Refusing non-loopback API")
    port = int((state / "ws.port").read_text().strip())
    if not 1 <= port <= 65535:
        raise ValueError("Invalid API port")
    return f"ws://127.0.0.1:{port}"


async def request(name, *, timeout=8, **fields):
    message = command(name, **fields)
    async with asyncio.timeout(timeout):
        async with websockets.connect(endpoint(), open_timeout=3, close_timeout=1,
                                      max_size=1024 * 1024) as ws:
            if name != "get_auth_state":
                while True:
                    event = json.loads(await ws.recv())
                    if isinstance(event, dict) and event.get("type") == "auth_state" and event.get("logged_in") is True:
                        break
            await ws.send(json.dumps(message))
            while True:
                event = json.loads(await ws.recv())
                if not isinstance(event, dict):
                    continue
                if event.get("type") == "error":
                    raise RuntimeError("Server rejected command; details withheld")
                if name in QUERY_EVENTS and event.get("type") == QUERY_EVENTS[name]:
                    return event
                if event.get("type") == "command_result" and event.get("command") == name:
                    return event
