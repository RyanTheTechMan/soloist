"""Offline tests for default and selected CoreAudio output routing."""
import json
from pathlib import Path
import tempfile
from unittest import TestCase, main
from unittest.mock import patch

import audio_routing
from native_audio import AudioEnvironment


DEVICES = [
    {"id": 246, "uid": "display-a", "name": "Display", "is_default": False},
    {"id": 203, "uid": "usb-m2", "name": "M2", "is_default": True},
]


class Tests(TestCase):
    def test_default_is_not_first_detected_device(self):
        selected, fallback = audio_routing.choose_output(DEVICES, "")
        self.assertEqual(selected["id"], 203)
        self.assertFalse(fallback)

    def test_remembered_uid_overrides_default(self):
        selected, fallback = audio_routing.choose_output(DEVICES, "display-a")
        self.assertEqual(selected["id"], 246)
        self.assertFalse(fallback)

    def test_unavailable_preference_uses_system_default(self):
        selected, fallback = audio_routing.choose_output(DEVICES, "disconnected")
        self.assertEqual(selected["id"], 203)
        self.assertTrue(fallback)

    def test_routes_existing_stream_using_coreaudio_object_id(self):
        calls = []
        def fake_pactl(_environment, *args):
            calls.append(args)
            if args == ("list", "short", "modules"):
                return b"2\tmodule-coreaudio-device\tobject_id=246 record=0 playback=1\t\n8\tmodule-coreaudio-device\tobject_id=203 record=0 playback=1\t\n"
            if args == ("-f", "json", "list", "sinks"):
                return json.dumps([{"name": "display", "owner_module": 2, "index": 0},
                                   {"name": "m2", "owner_module": 8, "index": 4}]).encode()
            if args == ("-f", "json", "list", "sink-inputs"):
                return json.dumps([{"index": 0, "sink": 0}]).encode()
            return b""
        with patch.object(audio_routing, "pactl", side_effect=fake_pactl):
            result = audio_routing.route({}, "", DEVICES)
        self.assertEqual(result["name"], "M2")
        self.assertIn(("set-default-sink", "m2"), calls)
        self.assertIn(("move-sink-input", "0", "m2"), calls)

    def test_live_preference_replaces_launch_choice(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(audio_routing, "STATE", Path(directory)):
            audio_routing.save_preference("")
            environment = AudioEnvironment()
            environment.requested_output_uid = ""
            environment.current_output_id = None
            choices = []
            def fake_route(_environment, uid, devices):
                selected, _ = audio_routing.choose_output(devices, uid)
                choices.append(selected["id"])
                return {"object_id": selected["id"], "name": selected["name"],
                        "fallback_to_default": False}
            with patch.object(audio_routing, "available_outputs", return_value=DEVICES), \
                    patch.object(audio_routing, "route", side_effect=fake_route):
                environment.refresh_route()
                audio_routing.save_preference("display-a")
                environment.refresh_route()
            self.assertEqual(choices, [203, 246])
            self.assertEqual((Path(directory) / "audio-output.uid").stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    main()
