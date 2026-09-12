"""Read-only public capability snapshot. No identities or music metadata."""
import asyncio
import json
from client_api import request

PUBLIC_ACTIONS = {"pause", "play", "seek", "seek_forward", "seek_backward",
                  "skip_next", "skip_prev", "add_to_queue", "shuffle", "set_repeat"}


async def main():
    state = await request("get_state")
    actions = state.get("available_actions", {})
    if not isinstance(actions, dict):
        actions = {}
    result = {"advertised_documented_actions": sorted(PUBLIC_ACTIONS.intersection(actions)),
              "other_action_count": len(set(actions) - PUBLIC_ACTIONS),
              "dj_init_command_documented": False,
              "dj_next_segment_command_documented": False,
              "mix_or_crossfade_command_documented": False,
              "source_bit_depth_exposed_by_documented_api": False,
              "scope": "Public API only; not a test of Connect AI DJ or audible mixing"}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
