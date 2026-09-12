"""Offline command, login readiness, no-retry and safe-output checks."""
import json
import unittest
from unittest.mock import patch
import client_api
from observe import safe_event


class Socket:
    def __init__(self, events):
        self.events = iter(events)
        self.sent = []
    async def __aenter__(self):
        return self
    async def __aexit__(self, *unused):
        pass
    async def recv(self):
        event = next(self.events)
        if isinstance(event, Exception):
            raise event
        return json.dumps(event)
    async def send(self, message):
        self.sent.append(json.loads(message))


class Tests(unittest.IsolatedAsyncioTestCase):
    def test_all_documented_commands(self):
        for name, fields in client_api.FIELDS.items():
            values = {"uri": "spotify:track:Synthetic", "volume": 5, "enabled": False,
                      "limit": 10, "position_ms": 30000}
            result = client_api.command(name, **{field: values[field] for field in fields})
            self.assertEqual(result["command"], name)

    def test_invalid_fields(self):
        for name, fields in (("seek", {"position_ms": -1}), ("seek", {"position_ms": True}),
                             ("set_volume", {"volume": 101}), ("set_volume", {"volume": float("nan")}),
                             ("set_shuffle", {"enabled": 1}), ("set_volume", {}),
                             ("play", {"uri": "https://example.invalid"}), ("pause", {"volume": 0}),
                             ("add_to_queue", {"uri": "spotify:album:Synthetic"}), ("start_dj", {})):
            with self.subTest(name=name), self.assertRaises(ValueError):
                client_api.command(name, **fields)

    async def test_waits_for_login_and_matching_ack(self):
        socket = Socket([{"type": "auth_state", "logged_in": False},
                         {"type": "auth_state", "logged_in": True},
                         {"type": "command_result", "command": "pause"},
                         {"type": "command_result", "command": "play"}])
        with patch.object(client_api, "endpoint", return_value="ws://127.0.0.1:1"), \
                patch.object(client_api.websockets, "connect", return_value=socket):
            result = await client_api.request("play")
        self.assertEqual(result["command"], "play")
        self.assertEqual(socket.sent, [client_api.command("play")])

    async def test_mutations_are_not_retried(self):
        socket = Socket([{"type": "auth_state", "logged_in": True}, OSError("synthetic")])
        with patch.object(client_api, "endpoint", return_value="ws://127.0.0.1:1"), \
                patch.object(client_api.websockets, "connect", return_value=socket) as connect:
            with self.assertRaises(OSError):
                await client_api.request("skip_next")
            self.assertEqual(connect.call_count, 1)
        self.assertEqual(socket.sent, [client_api.command("skip_next")])

    def test_safe_output(self):
        self.assertEqual(safe_event({"type": "queue_changed", "upcoming": [{"uri": "private"}]}),
                         {"type": "queue_changed", "upcoming_count": 1})
        self.assertNotIn("private", json.dumps(safe_event({"type": "error", "message": "private"})))


if __name__ == "__main__":
    unittest.main()
