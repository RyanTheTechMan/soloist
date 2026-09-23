"""Standalone runtime entry point. No compiler, Homebrew or Python required when packaged."""
import argparse
import asyncio
import contextlib
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile

import client_api
import credentials
import receiver
from native_audio import native_audio
from observe import safe_event
from paths import BUNDLED, CONFIG, DATA, ENGINE, PACTL, RUNTIME, STATE, SYSROOT, VERSION


class ConfigurationError(ValueError):
    """Only fixed, credential-safe messages may use this exception."""


def validate_engine(path):
    path = path.expanduser().resolve(strict=True)
    if not path.is_file():
        raise ConfigurationError("Choose a regular official Soloist executable")
    with path.open("rb") as stream:
        header = stream.read(20)
    if len(header) != 20 or header[:6] != b"\x7fELF\x02\x01" or int.from_bytes(header[18:20], "little") != 183:
        raise ConfigurationError("Choose the extracted Linux ARM64 Soloist executable, not the archive or x86 build")
    return path


def engine_metadata(engine):
    """Inspect an official build without account credentials or starting playback."""
    process = subprocess.run([str(RUNTIME), "--no-rosetta", "--clear-env", "--sysroot", str(SYSROOT),
                              "--", str(engine), "--version"], capture_output=True, timeout=20,
                             env={"PATH": os.defpath, "ELFUSE_VERIFY_TEXT": "1"})
    output = process.stdout + process.stderr
    version = re.search(rb"\bsoloist (\d+(?:\.\d+){1,4})\b", output)
    built = re.search(rb"\bbuild (\d{10})\b", output)
    if process.returncode != 0 or not version or not built or not all(
        marker in output for marker in (b"INTEGRITY: executable-byte preflight passed",
                                  b"INTEGRITY: executable-byte exit comparison passed")):
        raise ConfigurationError("Soloist version check failed; choose a current official Linux ARM64 build")
    build_time = datetime.fromtimestamp(int(built.group(1)), timezone.utc)
    expires = build_time + timedelta(days=90)
    return {"soloist_version": version.group(1).decode("ascii"),
            "build_at": build_time.isoformat().replace("+00:00", "Z"),
            "expected_expiry_at": expires.isoformat().replace("+00:00", "Z")}


def installation():
    if not CONFIG.is_file():
        return {"configured": False}
    settings = json.loads(CONFIG.read_text())
    result = {"configured": True, "executable_installed": Path(settings["soloist"]).is_file(),
              "credential_store": settings.get("credential_store", "external-file"),
              "soloist_version": settings.get("soloist_version"),
              "build_at": settings.get("build_at"),
              "expected_expiry_at": settings.get("expected_expiry_at")}
    if result["expected_expiry_at"]:
        expiry = datetime.fromisoformat(result["expected_expiry_at"].replace("Z", "+00:00"))
        seconds = (expiry - datetime.now(timezone.utc)).total_seconds()
        result["expired"] = seconds <= 0
        result["days_remaining"] = max(0, int(seconds // 86400))
    return result


def configure(engine, key=None, keychain=False):
    engine = validate_engine(engine)
    if keychain:
        credentials.load()
    else:
        key = key.expanduser().resolve(strict=True)
        info = key.stat()
        if not key.is_file() or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ConfigurationError("API-key file must be owned by you with owner-only permissions (chmod 600)")
        with key.open("rb") as stream:
            raw = stream.read(4098)
        secret = raw.strip()
        if len(raw) > 4097 or not secret or len(secret) > 4096 or b"\0" in secret or b"\n" in secret or b"\r" in secret:
            raise ConfigurationError("API-key file must contain one nonempty key")
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    DATA.chmod(0o700)
    STATE.mkdir(exist_ok=True, mode=0o700)
    STATE.chmod(0o700)
    ENGINE.parent.mkdir(exist_ok=True, mode=0o700)
    if ENGINE.parent.is_symlink() or ENGINE.is_symlink():
        raise ConfigurationError("Private installation location must not be a symlink")
    ENGINE.parent.chmod(0o700)
    copied = engine != ENGINE.resolve()
    temporary = None
    try:
        if copied:
            descriptor, temporary = tempfile.mkstemp(prefix=".soloist-", dir=ENGINE.parent)
            with os.fdopen(descriptor, "wb") as output, engine.open("rb") as source:
                shutil.copyfileobj(source, output)
                output.flush()
                os.fsync(output.fileno())
            os.chmod(temporary, 0o700)
            metadata = engine_metadata(Path(temporary))
            os.replace(temporary, ENGINE)
            temporary = None
        else:
            metadata = engine_metadata(ENGINE)
        settings = {"soloist": str(ENGINE), **metadata}
        if keychain:
            settings["credential_store"] = "keyring"
        else:
            settings["api_key_file"] = str(key)
        receiver.private_text(CONFIG, json.dumps(settings) + "\n")
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)
    print(json.dumps({**installation(), "executable_copied": copied, "key_copied": False}))


def doctor(engine=None, audio=False):
    result = {"runtime_version": VERSION, "packaged": BUNDLED,
              "host_supported": platform.system() == "Darwin" and platform.machine() == "arm64",
              "runtime_present": RUNTIME.is_file(), "sysroot_present": SYSROOT.is_dir(),
              "account_used": False, "playback_tested": False}
    if engine is not None:
        engine = validate_engine(engine)
        process = subprocess.run([str(RUNTIME), "--no-rosetta", "--clear-env", "--sysroot", str(SYSROOT),
                                  "--", str(engine), "--version"], capture_output=True, timeout=15,
                                 env={"PATH": os.defpath, "ELFUSE_VERIFY_TEXT": "1"})
        output = process.stdout + process.stderr
        result["engine_exit_code"] = process.returncode
        version = re.search(rb"\bsoloist (\d+(?:\.\d+){1,4})\b", output)
        result["soloist_version"] = version.group(1).decode("ascii") if version else None
        result["integrity_preflight"] = b"INTEGRITY: executable-byte preflight passed" in output
        result["integrity_exit"] = b"INTEGRITY: executable-byte exit comparison passed" in output
    if audio:
        with contextlib.redirect_stdout(sys.stderr), native_audio() as environment:
            sinks = subprocess.run([str(PACTL), "-f", "json", "list", "sinks"],
                                   env=environment, capture_output=True, timeout=5, check=True)
            result["native_audio_outputs"] = len(json.loads(sinks.stdout))
            result["microphone_enabled"] = False
    result["passed"] = result["host_supported"] and result["runtime_present"] and result["sysroot_present"]
    if engine is not None:
        result["passed"] &= process.returncode == 0 and bool(version) and result["integrity_preflight"] and result["integrity_exit"]
    if audio:
        result["passed"] &= result["native_audio_outputs"] > 0
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "run":
        return receiver.main(argv[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser("run", help="Start receiver; run --help shows receiver options")
    sub.add_parser("describe", help="Machine-readable integration capabilities, no credentials")
    sub.add_parser("endpoint", help="Local endpoint for a same-user client; preview has no API authentication")
    sub.add_parser("status", help="Safe current state, no song/account metadata")
    sub.add_parser("installation", help="Show installed build and expected expiry; no account data")
    setup = sub.add_parser("configure", help="Copy selected official executable into private app data")
    setup.add_argument("--soloist", type=Path, required=True)
    secret_source = setup.add_mutually_exclusive_group(required=True)
    secret_source.add_argument("--api-key-file", type=Path)
    secret_source.add_argument("--keychain", action="store_true")
    credential = sub.add_parser("credential", help="Manage the system credential store without argv secrets")
    credential.add_argument("action", choices=("status", "store"))
    check = sub.add_parser("doctor", help="Credential-free runtime and optional native audio check")
    check.add_argument("--soloist", type=Path)
    check.add_argument("--audio", action="store_true")
    control = sub.add_parser("control", help="Documented commands; acknowledgements are dispatch only")
    control.add_argument("command", choices=client_api.FIELDS)
    control.add_argument("--uri")
    control.add_argument("--volume", type=int)
    control.add_argument("--position-ms", type=int)
    control.add_argument("--limit", type=int)
    control.add_argument("--enabled", choices=("on", "off"))
    args = parser.parse_args(argv)
    if args.operation == "configure":
        configure(args.soloist, args.api_key_file, args.keychain)
    elif args.operation == "doctor":
        return doctor(args.soloist, args.audio)
    elif args.operation == "credential":
        if args.action == "store":
            if sys.stdin.isatty():
                from getpass import getpass
                secret = getpass("Soloist API key: ")
            else:
                secret = sys.stdin.buffer.read(4098)
            credentials.save(secret)
            print(json.dumps({"stored": True}))
        else:
            print(json.dumps({"stored": credentials.exists()}))
    elif args.operation == "installation":
        print(json.dumps(installation()))
    elif args.operation == "describe":
        print(json.dumps({"runtime_version": VERSION, "integration_version": 1,
                          "host_platforms": ["macos-arm64"], "packaged": BUNDLED,
                          "execution_backend": "elfuse-hvf", "guest_kernel": False,
                          "soloist_included": False, "configured": CONFIG.is_file(),
                          "local_api": "soloist-websocket", "local_api_security": "unauthenticated-loopback-preview",
                          "control_commands": sorted(client_api.FIELDS)}))
    elif args.operation == "endpoint":
        print(json.dumps({"integration_version": 1, "url": client_api.endpoint(),
                          "security": "unauthenticated-loopback-preview"}))
    elif args.operation == "status":
        print(json.dumps(safe_event(asyncio.run(client_api.request("get_auth_state")))))
        print(json.dumps(safe_event(asyncio.run(client_api.request("get_state")))))
    elif args.operation == "control":
        fields = {key: value for key, value in vars(args).items()
                  if key not in ("operation", "command") and value is not None}
        if "enabled" in fields:
            fields["enabled"] = fields["enabled"] == "on"
        event = asyncio.run(client_api.request(args.command, **fields))
        print(json.dumps(safe_event(event)))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        # Fixed validation messages are safe; arbitrary I/O/server text isn't.
        message = str(error) if type(error) in (ConfigurationError, credentials.CredentialError) else "Operation failed; private details withheld"
        print(json.dumps({"error_type": type(error).__name__, "message": message}), file=sys.stderr)
        raise SystemExit(1)
