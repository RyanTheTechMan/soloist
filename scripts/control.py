"""Local Soloist controls; bounded dispatch acknowledgement, not playback proof."""
import argparse
import asyncio
import json
from client_api import FIELDS, QUERY_EVENTS, command, request
from observe import safe_event


async def control(name, fields):
    try:
        event = await request(name, **fields)
    except Exception as error:
        print("CONTROL: request failed (" + type(error).__name__ + "); details withheld; not retried")
        return 1
    print(json.dumps(safe_event(event)), flush=True)
    if name not in QUERY_EVENTS:
        print("CONTROL: dispatched; verify subsequent state/audio separately", flush=True)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=FIELDS)
    parser.add_argument("--uri")
    parser.add_argument("--volume", type=int)
    parser.add_argument("--position-ms", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--enabled", choices=("on", "off"))
    args = parser.parse_args()
    fields = {key: value for key, value in vars(args).items() if key != "command" and value is not None}
    if "enabled" in fields:
        fields["enabled"] = fields["enabled"] == "on"
    try:
        command(args.command, **fields)
    except ValueError as error:
        parser.error(str(error))
    raise SystemExit(asyncio.run(control(args.command, fields)))
