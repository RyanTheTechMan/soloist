"""Portable repository paths; private installation choices stay in state/."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BUNDLED = bool(getattr(sys, "frozen", False))
BUNDLE_CONTENTS = Path(getattr(sys, "_MEIPASS", ROOT)).parent
PAYLOAD = BUNDLE_CONTENTS / "Resources/payload"
DEFAULT_DATA = Path.home() / "Library/Application Support/Soloist Runtime" if BUNDLED else ROOT
DATA = Path(os.environ.get("SOLOIST_RUNTIME_HOME", DEFAULT_DATA)).expanduser()
if not DATA.is_absolute():
    raise ValueError("SOLOIST_RUNTIME_HOME must be an absolute directory")
DATA = DATA.resolve()
STATE = DATA / "state"
CACHE = DATA / "cache"
VENDOR = ROOT / "vendor/elfuse"
RUNTIME = BUNDLE_CONTENTS / "MacOS/elfuse" if BUNDLED else VENDOR / "build/elfuse"
SYSROOT = PAYLOAD / "sysroot" if BUNDLED else ROOT / "build/sysroot"
PULSE = BUNDLE_CONTENTS / "Frameworks/pulseaudio" if BUNDLED else Path("/opt/homebrew/opt/pulseaudio/bin/pulseaudio")
PACTL = BUNDLE_CONTENTS / "Frameworks/pactl" if BUNDLED else Path("/opt/homebrew/bin/pactl")
PAREC = BUNDLE_CONTENTS / "Frameworks/parec" if BUNDLED else Path("/opt/homebrew/bin/parec")
PULSE_MODULES = BUNDLE_CONTENTS / "Frameworks" if BUNDLED else Path("/opt/homebrew/opt/pulseaudio/lib/pulseaudio/modules")
CERTIFICATES = SYSROOT / "etc/ssl/certs/ca-certificates.crt"
CONFIG = STATE / "installation.json"
VERSION = "0.1.0-dev"


def configured_path(name, override=None):
    settings = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
    value = override or settings.get(name)
    if not value:
        raise SystemExit("Configure the official executable/key files first, or supply --" + name.replace("_", "-"))
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_file():
        raise SystemExit("Expected a regular file for " + name)
    return path
