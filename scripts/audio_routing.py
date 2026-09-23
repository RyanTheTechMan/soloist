"""Route the private PulseAudio stream to a CoreAudio device by stable UID."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

import coreaudio_devices
from paths import PACTL, STATE


class AudioRoutingError(RuntimeError):
    """Only fixed, non-private diagnostics should be raised here."""


def available_outputs():
    return coreaudio_devices.outputs()


def save_preference(uid):
    if len(uid) > 512 or any(ord(char) < 32 for char in uid):
        raise AudioRoutingError("Audio output UID is invalid")
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = STATE / "audio-output.uid"
    descriptor, temporary = tempfile.mkstemp(prefix=".audio-output-", dir=STATE)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(uid)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_preference():
    path = STATE / "audio-output.uid"
    return path.read_text() if path.is_file() else ""


def choose_output(devices, requested_uid):
    requested = next((item for item in devices if item["uid"] == requested_uid), None) if requested_uid else None
    default = next((item for item in devices if item["is_default"]), None)
    if requested:
        return requested, False
    if default:
        return default, bool(requested_uid)
    raise AudioRoutingError("No macOS default audio output is available")


def private_environment():
    hint = STATE / "audio.path"
    root = Path(hint.read_text().strip()).resolve(strict=True)
    temporary = Path("/private/tmp")
    if not root.is_relative_to(temporary) or not root.name.startswith("soloist-pulse-"):
        raise AudioRoutingError("Private audio server path is invalid")
    if root.stat().st_uid != os.getuid() or root.stat().st_mode & 0o077:
        raise AudioRoutingError("Private audio server permissions are invalid")
    if not (root / "native").is_socket():
        raise AudioRoutingError("Private audio server is not running")
    return {"PATH": os.defpath, "PULSE_RUNTIME_PATH": str(root),
            "PULSE_STATE_PATH": str(root), "PULSE_COOKIE": str(root / "cookie"),
            "PULSE_SERVER": "unix:" + str(root / "native")}


def pactl(environment, *args):
    result = subprocess.run([str(PACTL), *args], env=environment,
                            capture_output=True, timeout=5)
    if result.returncode != 0:
        raise AudioRoutingError("Private audio server did not accept the output change")
    return result.stdout


def sink_for_object(environment, object_id):
    modules = pactl(environment, "list", "short", "modules").decode("utf-8", "replace").splitlines()
    module_id = None
    for line in modules:
        fields = line.split("\t", 3)
        if len(fields) >= 3 and fields[1] == "module-coreaudio-device":
            match = re.search(r"(?:^| )object_id=(\d+)(?: |$)", fields[2])
            if match and int(match.group(1)) == object_id:
                module_id = int(fields[0])
                break
    if module_id is None:
        raise AudioRoutingError("Selected macOS output has no private audio sink")
    sinks = json.loads(pactl(environment, "-f", "json", "list", "sinks"))
    sink = next((item for item in sinks if item.get("owner_module") == module_id), None)
    if not sink:
        raise AudioRoutingError("Selected macOS output has no private audio sink")
    return sink


def route(environment, requested_uid="", devices=None):
    devices = available_outputs() if devices is None else devices
    target, fallback = choose_output(devices, requested_uid)
    try:
        sink = sink_for_object(environment, target["id"])
    except AudioRoutingError:
        if not requested_uid or fallback:
            raise
        default, _ = choose_output(devices, "")
        if default["id"] == target["id"]:
            raise
        target = default
        fallback = True
        sink = sink_for_object(environment, target["id"])
    pactl(environment, "set-default-sink", sink["name"])
    inputs = json.loads(pactl(environment, "-f", "json", "list", "sink-inputs"))
    for item in inputs:
        if item.get("sink") != sink["index"]:
            pactl(environment, "move-sink-input", str(item["index"]), sink["name"])
    return {"uid": target["uid"], "name": target["name"],
            "object_id": target["id"], "fallback_to_default": fallback}
