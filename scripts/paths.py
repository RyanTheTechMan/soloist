"""Portable repository paths; private installation choices stay in state/."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor/elfuse"
RUNTIME = VENDOR / "build/elfuse"
CONFIG = ROOT / "state/installation.json"


def configured_path(name, override=None):
    settings = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
    value = override or settings.get(name)
    if not value:
        raise SystemExit("Run scripts/setup.py first, or supply --" + name.replace("_", "-"))
    path = Path(value).expanduser().resolve(strict=True)
    if not path.is_file():
        raise SystemExit("Expected a regular file for " + name)
    return path
