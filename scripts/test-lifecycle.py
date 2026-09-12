"""Offline supervisor tests. Only owned subprocess fixtures are terminated."""
import os
import signal
import sys
import threading
import time
import unittest
from lifecycle import Exit, retry_delay, run_child


class LifecycleTests(unittest.TestCase):
    def run_fixture(self, source, **kwargs):
        output = []
        result = run_child([sys.executable, "-u", "-c", source], {"PATH": os.defpath},
                           kwargs.pop("stop", threading.Event()), kwargs.pop("deadline", None),
                           output.append, shutdown_grace=0.3, **kwargs)
        return result, output

    def test_clean_exit(self):
        result, output = self.run_fixture("print('owned fixture')")
        self.assertEqual(result, Exit(0, "exit", False))
        self.assertEqual(output, [b"owned fixture"])

    def test_duration_delivers_graceful_signal(self):
        source = "import signal,time,sys; signal.signal(signal.SIGTERM, lambda *_: sys.exit(0)); print('ready'); time.sleep(10)"
        result, output = self.run_fixture(source, deadline=time.monotonic() + 0.4)
        self.assertEqual(result, Exit(0, "duration", False))
        self.assertIn(b"ready", output)

    def test_stubborn_child_is_bounded(self):
        source = "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print('ready'); time.sleep(10)"
        result, _ = self.run_fixture(source, deadline=time.monotonic() + 0.4)
        self.assertEqual(result, Exit(-signal.SIGKILL, "duration", True))

    def test_explicit_stop(self):
        event = threading.Event()
        event.set()
        result, _ = self.run_fixture("import time; time.sleep(10)", stop=event)
        self.assertEqual(result.reason, "requested")

    def test_health_needs_three_failures(self):
        calls = []
        def health():
            calls.append(1)
            return False
        result, _ = self.run_fixture("import time; time.sleep(10)", health=health,
                                     startup_grace=0.1, health_interval=0.1)
        self.assertEqual(len(calls), 3)
        self.assertEqual(result.reason, "health")

    def test_healthy_sample_resets_failure_count(self):
        answers = iter((False, False, True, False, False, False))
        calls = []
        def health():
            calls.append(1)
            return next(answers)
        result, _ = self.run_fixture("import time; time.sleep(10)", health=health,
                                     startup_grace=0.1, health_interval=0.1)
        self.assertEqual(len(calls), 6)
        self.assertEqual(result.reason, "health")

    def test_retry_policy(self):
        for result in (Exit(0, "exit", False), Exit(10, "exit", False),
                       Exit(143, "requested", False), Exit(0, "duration", False)):
            self.assertIsNone(retry_delay(result, 0, 3, False))
        self.assertEqual(retry_delay(Exit(0, "health", False), 0, 3, False), 2)
        self.assertEqual(retry_delay(Exit(1, "exit", False), 2, 3, False), 8)
        self.assertIsNone(retry_delay(Exit(1, "exit", False), 3, 3, False))
        self.assertIsNone(retry_delay(Exit(1, "exit", False), 0, 3, True))


if __name__ == "__main__":
    unittest.main()
