"""Audit a local app without authentication, playback, or printing secret values."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def audit(app, engine=None, key=None):
    app = app.resolve(strict=True)
    helper = app / "Contents/Helpers/runtime-cli.app/Contents"
    manifest = json.loads((app / "Contents/Resources/manifest.json").read_text())
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    forbidden_hash = hashlib.sha256(engine.read_bytes()).hexdigest() if engine else None
    secret = key.read_bytes().strip() if key else None
    if key and (not secret or len(secret) > 4096):
        raise ValueError("Choose a valid nonempty key file for the private exclusion check")
    hashes = {}
    links = {}
    native_count = 0
    count = 0
    for path in app.rglob("*"):
        if path.is_symlink():
            if not path.resolve(strict=True).is_relative_to(app):
                raise ValueError("Bundle contains an external symlink")
            if path.is_relative_to(helper):
                links[str(path.relative_to(helper))] = str(path.readlink())
            continue
        if not path.is_file():
            continue
        count += 1
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest == forbidden_hash or (secret and secret in data):
            raise ValueError("Private input exclusion check failed; details withheld")
        if path.is_relative_to(helper) and "_CodeSignature" not in path.parts:
            hashes[str(path.relative_to(helper))] = digest
        if path.name in ("installation.json", "last-exit.json", "ws.port", "ws.addr", "soloist"):
            raise ValueError("Unexpected installation or engine payload")
        if data[:4] in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"):
            native_count += 1
            output = subprocess.check_output(["otool", "-L", str(path)], text=True)
            for line in output.splitlines()[1:]:
                dependency = line.strip().split(" (", 1)[0]
                if not dependency.startswith(("@loader_path/", "@rpath/", "@executable_path/", "/usr/lib/", "/System/Library/")):
                    raise ValueError("Nonportable native dependency")
            load_commands = subprocess.check_output(["otool", "-l", str(path)], text=True)
            if "/opt/homebrew/" in load_commands:
                raise ValueError("Native load commands still reference Homebrew")
    if hashes != manifest["files"] or links != manifest["symlinks"]:
        raise ValueError("Payload manifest mismatch")
    return {"passed": True, "regular_files": count, "native_binaries": native_count,
            "payload_hashes_checked": len(hashes), "symlinks_checked": len(links),
            "official_engine_exclusion_checked": engine is not None,
            "private_key_exclusion_checked": key is not None,
            "playback_tested": False, "notarization_tested": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", type=Path)
    parser.add_argument("--soloist", type=Path)
    parser.add_argument("--api-key-file", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(audit(args.app, args.soloist, args.api_key_file), indent=2))
    except Exception as error:
        print(json.dumps({"passed": False, "error_type": type(error).__name__,
                          "message": str(error) if type(error) is ValueError else "Audit failed; private details withheld"}))
        raise SystemExit(1)
