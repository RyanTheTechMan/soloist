"""Offline tests for the control regression harness; no receiver or account."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

spec = importlib.util.spec_from_file_location(
    "cycles", Path(__file__).with_name("verify-playback-cycles.py"))
cycles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cycles)


class Socket:
    def __init__(self, events):
        self.events = iter(events)
        self.sent = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *unused):
        pass

    async def send(self, value):
        self.sent.append(json.loads(value))

    async def recv(self):
        return json.dumps(next(self.events))


class Tests(unittest.IsolatedAsyncioTestCase):
    async def test_documented_ack_has_no_success_field(self):
        socket = Socket([{"type": "auth_state"},
                         {"type": "command_result", "command": "play"}])
        with patch.object(cycles, "endpoint", return_value="ws://127.0.0.1:12345"), \
                patch.object(cycles.websockets, "connect", return_value=socket):
            self.assertIsNone(await cycles.request("play"))
        self.assertEqual(socket.sent, [{"type": "command", "command": "play"}])

    async def test_error_detail_is_not_exposed(self):
        socket = Socket([{"type": "error", "message": "private synthetic detail"}])
        with patch.object(cycles, "endpoint", return_value="ws://127.0.0.1:12345"), \
                patch.object(cycles.websockets, "connect", return_value=socket):
            with self.assertRaisesRegex(RuntimeError, "^Server error; detail withheld$"):
                await cycles.request("play")

    async def test_skip_does_not_accept_stale_playing_snapshot(self):
        states = [{"status": "playing", "is_active": True, "item": {"uri": value}}
                  for value in ("synthetic-old", "synthetic-new")]
        request = AsyncMock(side_effect=states)
        with patch.object(cycles, "request", request), \
                patch.object(cycles.asyncio, "sleep", AsyncMock()):
            state = await cycles.wait_state("playing", previous_item="synthetic-old")
        self.assertEqual(request.await_count, 2)
        self.assertEqual(state["item"]["uri"], "synthetic-new")

    async def test_wrong_state_does_not_pass(self):
        with patch.object(cycles, "request", AsyncMock(return_value={"status": "paused"})), \
                patch.object(cycles.time, "monotonic", side_effect=[0, 0, 16]), \
                patch.object(cycles.asyncio, "sleep", AsyncMock()):
            with self.assertRaises(TimeoutError):
                await cycles.wait_state("playing", timeout=15)

    async def test_inactive_state_is_explicit(self):
        with patch.object(cycles, "request", AsyncMock(return_value={"is_active": False})):
            state = await cycles.wait_state(None, active=False)
        self.assertIs(state["is_active"], False)

    async def test_endpoint_rejects_non_loopback(self):
        with tempfile.TemporaryDirectory(prefix="soloist-endpoint-test-") as directory:
            state = Path(directory)
            (state / "ws.addr").write_text("0.0.0.0")
            with patch.object(cycles, "STATE", state):
                with self.assertRaises(ValueError):
                    cycles.endpoint()


if __name__ == "__main__":
    unittest.main()
