"""Offline receiver health/privacy checks using an owned loopback fixture."""
import contextlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import websockets
import receiver


class Tests(unittest.IsolatedAsyncioTestCase):
    async def test_offline_account_can_be_locally_healthy(self):
        received = []
        async def serve(ws):
            await ws.send(json.dumps({"type": "auth_state", "logged_in": False}))
            received.append(json.loads(await ws.recv()))
            await ws.send(json.dumps({"type": "auth_state", "logged_in": False}))
            await ws.wait_closed()
        with tempfile.TemporaryDirectory(prefix="soloist-health-test-") as directory:
            state = Path(directory)
            async with websockets.serve(serve, "127.0.0.1", 0) as server:
                (state / "ws.addr").write_text("127.0.0.1")
                (state / "ws.port").write_text(str(server.sockets[0].getsockname()[1]))
                self.assertTrue(await receiver.api_health(state))
        self.assertEqual(received, [{"type": "command", "command": "get_auth_state"}])

    async def test_non_loopback_rejected(self):
        with tempfile.TemporaryDirectory(prefix="soloist-health-test-") as directory:
            state = Path(directory)
            (state / "ws.addr").write_text("0.0.0.0")
            self.assertFalse(await receiver.api_health(state))

    def test_arbitrary_integrity_line_is_withheld(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            receiver.report(b"INTEGRITY: synthetic-private-data", b"synthetic-key")
            receiver.report(b"INTEGRITY: executable-byte exit comparison passed (100 bytes)", b"synthetic-key")
        self.assertEqual(output.getvalue(), "INTEGRITY: executable-byte exit comparison passed (100 bytes)\n")

    def test_status_file_is_private_and_replaced(self):
        with tempfile.TemporaryDirectory(prefix="soloist-status-test-") as directory:
            path = Path(directory) / "status"
            receiver.private_text(path, "first")
            receiver.private_text(path, "second")
            self.assertEqual(path.read_text(), "second")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_websocket_is_optional_and_loopback_only(self):
        args = SimpleNamespace(device_name="Test Receiver", audio_latency_ms=100, websocket="off")
        fields = (Path("/state"), Path("/cache"), Path("/engine"), Path("/key"), Path("/pulse"))
        connect_only = receiver.soloist_command(args, *fields)
        self.assertNotIn("-w", connect_only)
        self.assertEqual(connect_only[-1], "-k")
        self.assertIn("PULSE_LATENCY_MSEC=100", connect_only)
        args.websocket = "on"
        enabled = receiver.soloist_command(args, *fields)
        self.assertEqual(enabled[enabled.index("-w") + 1], "127.0.0.1:0")
        self.assertEqual(enabled[-1], "-k")


if __name__ == "__main__":
    unittest.main()
