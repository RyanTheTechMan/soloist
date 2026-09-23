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
from datetime import datetime, timedelta, timezone
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

    def test_selected_executable_is_copied_to_private_profile(self):
        profile = self.root / "profile"
        state = profile / "state"
        config = state / "installation.json"
        installed = profile / "engine/soloist"
        metadata = {"soloist_version": "1.2.3", "build_at": "2026-09-01T00:00:00Z",
                    "expected_expiry_at": "2026-11-30T00:00:00Z"}
        with patch.multiple(runtime_cli, DATA=profile, STATE=state, CONFIG=config, ENGINE=installed), \
                patch.object(runtime_cli, "engine_metadata", return_value=metadata):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                runtime_cli.configure(self.engine, self.key)
        self.assertEqual(json.loads(config.read_text()), {
            "soloist": str(installed), "api_key_file": str(self.key), **metadata})
        self.assertEqual(installed.read_bytes(), self.engine.read_bytes())
        self.assertEqual(installed.stat().st_mode & 0o777, 0o700)
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(state.stat().st_mode & 0o777, 0o700)
        self.assertEqual(installed.parent.stat().st_mode & 0o777, 0o700)
        self.assertNotIn("synthetic-test-key", config.read_text() + output.getvalue())
        self.assertTrue(json.loads(output.getvalue())["executable_copied"])
        self.engine.unlink()
        self.assertTrue(installed.is_file())

    def test_failed_inspection_does_not_replace_installed_build(self):
        profile = self.root / "profile"
        installed = profile / "engine/soloist"
        installed.parent.mkdir(parents=True)
        installed.write_bytes(b"previous")
        config = profile / "state/installation.json"
        with patch.multiple(runtime_cli, DATA=profile, STATE=config.parent, CONFIG=config, ENGINE=installed), \
                patch.object(runtime_cli, "engine_metadata", side_effect=runtime_cli.ConfigurationError("Version check failed")):
            with self.assertRaises(runtime_cli.ConfigurationError):
                runtime_cli.configure(self.engine, self.key)
        self.assertEqual(installed.read_bytes(), b"previous")
        self.assertFalse(config.exists())
        self.assertEqual(list(installed.parent.iterdir()), [installed])

    def test_version_metadata_and_expiry(self):
        sample = b"INTEGRITY: executable-byte preflight passed\nsoloist 1.3.8.36 build 1789106507 (linux/aarch64)\nINTEGRITY: executable-byte exit comparison passed\n"
        with patch.object(runtime_cli.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, sample, b"")):
            values = runtime_cli.engine_metadata(self.engine)
        built = datetime.fromtimestamp(1789106507, timezone.utc)
        self.assertEqual(values["soloist_version"], "1.3.8.36")
        self.assertEqual(values["build_at"], built.isoformat().replace("+00:00", "Z"))
        self.assertEqual(values["expected_expiry_at"], (built + timedelta(days=90)).isoformat().replace("+00:00", "Z"))

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
        version_file = contents / "Resources/payload/version.txt"
        version_file.parent.mkdir(parents=True)
        version_file.write_text("1.2.3\n")
        profile = self.root / "private profile"
        code = (
            "import sys,json; sys.frozen=True; sys._MEIPASS=sys.argv[1]; "
            "import paths; print(json.dumps({name:str(getattr(paths,name)) "
            "for name in ['RUNTIME','SYSROOT','PULSE','STATE','CACHE','VERSION']}))"
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
        self.assertEqual(values["VERSION"], "1.2.3")
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
