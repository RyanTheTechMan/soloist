"""Account-free configuration and bundle path isolation regression tests."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import runtime_cli


class Tests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="soloist-package-test-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()
        self.engine = self.root / "owned-header-fixture"
        header = bytearray(20)
        header[:6] = b"\x7fELF\x02\x01"
        header[18:20] = (183).to_bytes(2, "little")
        self.engine.write_bytes(header)
        self.key = self.root / "fixture.api"
        self.key.write_text("synthetic-test-key\n")
        self.key.chmod(0o600)

    def test_configuration_contains_only_paths_and_is_private(self):
        profile = self.root / "profile"
        state = profile / "state"
        config = state / "installation.json"
        with patch.multiple(runtime_cli, DATA=profile, STATE=state, CONFIG=config):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                runtime_cli.configure(self.engine, self.key)
        self.assertEqual(json.loads(config.read_text()), {
            "soloist": str(self.engine), "api_key_file": str(self.key)})
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(state.stat().st_mode & 0o777, 0o700)
        self.assertNotIn("synthetic-test-key", config.read_text() + output.getvalue())
        self.assertEqual(list(profile.iterdir()), [state])

    def test_wrong_engine_architecture_rejected(self):
        header = bytearray(self.engine.read_bytes())
        header[18:20] = (62).to_bytes(2, "little")
        self.engine.write_bytes(header)
        with self.assertRaises(runtime_cli.ConfigurationError):
            runtime_cli.validate_engine(self.engine)

    def test_public_key_file_rejected(self):
        self.key.chmod(0o644)
        with self.assertRaises(runtime_cli.ConfigurationError):
            runtime_cli.configure(self.engine, self.key)

    def test_invalid_key_contents_rejected_without_echo(self):
        for value in ("", "synthetic\nprivate", "synthetic\0private", "x" * 5000):
            self.key.write_text(value)
            with self.assertRaises(runtime_cli.ConfigurationError) as error:
                runtime_cli.configure(self.engine, self.key)
            self.assertEqual(str(error.exception), "API-key file must contain one nonempty key")

    def test_bundle_paths_are_relocatable_and_separate_from_profile(self):
        contents = self.root / "Moved App.app/Contents"
        profile = self.root / "private profile"
        code = (
            "import sys,json; sys.frozen=True; sys._MEIPASS=sys.argv[1]; "
            "import paths; print(json.dumps({name:str(getattr(paths,name)) "
            "for name in ['RUNTIME','SYSROOT','PULSE','STATE','CACHE']}))"
        )
        environment = dict(os.environ, PYTHONPATH=str(Path(__file__).parent),
                           SOLOIST_RUNTIME_HOME=str(profile))
        result = subprocess.run([sys.executable, "-c", code, str(contents / "Frameworks")],
                                env=environment, capture_output=True, text=True, check=True)
        values = json.loads(result.stdout)
        self.assertEqual(values["RUNTIME"], str(contents / "MacOS/elfuse"))
        self.assertEqual(values["SYSROOT"], str(contents / "Resources/payload/sysroot"))
        self.assertEqual(values["PULSE"], str(contents / "Frameworks/pulseaudio"))
        self.assertEqual(values["STATE"], str(profile / "state"))
        self.assertEqual(values["CACHE"], str(profile / "cache"))
        self.assertFalse(profile.exists())

    def test_relative_profile_rejected(self):
        result = subprocess.run([sys.executable, "-c", "import paths"],
                                env=dict(os.environ, PYTHONPATH=str(Path(__file__).parent),
                                         SOLOIST_RUNTIME_HOME="relative-profile"),
                                capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be an absolute directory", result.stderr)


if __name__ == "__main__":
    unittest.main()
