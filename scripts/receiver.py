"""Supervised HVF Soloist receiver. No API key in host argv; filtered logs only."""
import argparse
import asyncio
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import signal
import tempfile
import threading
import time
import websockets

from paths import BUNDLED, STATE, CACHE, RUNTIME, SYSROOT, CERTIFICATES, configured_path
from lifecycle import Exit, retry_delay, run_child
PUBLIC_ERRORS = set()
from native_audio import native_audio


def report(raw, secret):
    line = re.sub(r"\x1b\[[0-9;]*m", "", raw.replace(secret, b"[redacted]").decode(errors="replace"))
    if re.fullmatch(r"INTEGRITY: executable-byte (preflight|exit comparison) passed \(\d+ bytes\)", line):
        print(line, flush=True)
    for phrase, label in (
        ("logged in as ", "signed in (identity withheld)"),
        ("mdns created successfully", "device discovery ready"),
        ("Failed to initialize mdns", "multicast discovery initialization failed"),
        ("zeroconf: received addUser", "Connect pairing request received"),
        ("pairing complete, credentials stored", "pairing complete"),
        ("Using PulseAudio", "native PulseAudio output selected"),
        ("login failed", "login failed"),
        ("session_auth_info_not_found", "session auth-info lookup failed"),
        ("certificate verify failed", "TLS certificate verification failed"),
        ("first message received, connection established", "cloud WebSocket established"),
        ("became active device", "receiver active"),
        ("no longer active device", "receiver inactive"),
        ("Failed to create decompressor", "audio decoder failed"),
        ("websocket: received error:", "cloud WebSocket error"),
        ("API key", "engine mentioned API-key configuration (details withheld)"),
        ("client-token: Forbidden", "client-token service returned Forbidden"),
        ("client-token: unexpected response", "unexpected client-token response"),
        ("client-token: unparsable", "unparseable client-token response"),
        ("decryption failed or bad record mac", "TLS record verification failed"),
        ("No valid session info after login completion", "session info missing after login"),
        ("Invalid user credentials", "server reported invalid user credentials"),
        ("Forced logout received for session:", "server requested logout"),
    ):
        if phrase in line:
            print("RECEIVER:", label, flush=True)
    for phrase, label in (
        ("Session creation from stored credentials failed", "stored-session failure"),
        ("Session creation via Connect failed", "Connect-session failure"),
        ("Connect session creation failed", "Connect-session failure"),
        ("ConnectZeroconfLoginProtocol::login: failed", "zeroconf login failure"),
        ("client-token: cannot fulfill a request", "client-token request failure"),
        ("client-token: network request error", "client-token network failure"),
        ("client-token: non-succesful HTTP status code returned", "client-token HTTP failure"),
        ("websocket: received error:", "cloud WebSocket failure"),
    ):
        if phrase not in line:
            continue
        suffix = line.split(phrase, 1)[1].removeprefix(", error:").lstrip(": ")
        details = [suffix] if suffix in PUBLIC_ERRORS else []
        for marker in ("category: ", "msg: "):
            if marker in suffix:
                candidate = suffix.split(marker, 1)[1].split(", ", 1)[0].strip()
                if candidate in PUBLIC_ERRORS:
                    details.append(marker + candidate)
        for field, value in re.findall(r"\b(error|status|value|code)[:= ]+(-?\d{1,6})\b", suffix):
            details.append(field + "=" + value)
        for name in ("Timeout", "Connection refused", "Connection reset", "Network is unreachable",
                     "Forbidden", "Unauthorized", "Bad Request", "SSL", "certificate",
                     "login5_http_transport_error", "login5_unknown_backend_error"):
            if name in suffix:
                details.append(name)
        print("RECEIVER:", label, "; ".join(details), flush=True)
    for pattern in (
        r"Started ZeroConf service on port (\d+) path (/[A-Za-z0-9/_-]*)",
        r"\bcodec:\s*(flac|vorbis|ogg|aac|mp3)\b",
        r"\bsample rate:\s*(\d+) Hz",
        r"\bsample format:\s*([a-zA-Z0-9-]{1,32})",
    ):
        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            print("RECEIVER:", match[0], flush=True)


def private_text(path, value):
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as output:
            output.write(value)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


async def api_health(state):
    # Local responsiveness is independent of Internet availability. An offline
    # account is not a reason to repeatedly restart or steal active playback.
    if (state / "ws.addr").read_text().strip() != "127.0.0.1":
        return False
    port = int((state / "ws.port").read_text().strip())
    if not 1 <= port <= 65535:
        return False
    async with websockets.connect(f"ws://127.0.0.1:{port}", open_timeout=2,
                                  close_timeout=1, max_size=1024 * 1024) as ws:
        async with asyncio.timeout(2):
            # Discard the automatic connect snapshot. Require a response to a
            # fresh query rather than merely a successful WebSocket handshake.
            while True:
                event = json.loads(await ws.recv())
                if isinstance(event, dict) and event.get("type") == "auth_state":
                    break
            await ws.send(json.dumps({"type": "command", "command": "get_auth_state"}))
            while True:
                event = json.loads(await ws.recv())
                if isinstance(event, dict) and event.get("type") == "auth_state":
                    return True


def run_session(args, state, cache, engine, key_path, secret, stop, deadline, attempt):
    sysroot = SYSROOT
    with native_audio() as audio_env:
        pulse_root = Path(audio_env["PULSE_RUNTIME_PATH"]).resolve()
        pulse_hint = state / "audio.path"
        pid_file = state / "receiver.pid"
        private_text(pulse_hint, str(pulse_root) + "\n")
        command = [str(RUNTIME), "--no-rosetta", "--clear-env", "--timeout", "10",
                   "--sysroot", str(sysroot), "--append-arg-file", str(key_path),
                   "--env", "PULSE_SERVER=unix:" + str(pulse_root / "native"),
                   "--env", "PULSE_COOKIE=" + str(pulse_root / "cookie"),
                   "--env", "SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt",
                   "--", str(engine), "-n", args.device_name, "-D", str(state),
                   "-C", str(cache), "-z", "100", "-w", "127.0.0.1:0", "-i", "5", "-v", "-k"]
        environment = {"PATH": os.defpath, "ELFUSE_VERIFY_TEXT": "1", "ELFUSE_FORWARD_TERMINATION": "1"}
        if args.audio_latency_ms:
            command[command.index("--"):command.index("--")] = [
                "--env", "PULSE_LATENCY_MSEC=" + str(args.audio_latency_ms)]
        integrity = {"preflight": False, "exit": False}
        def consume(raw):
            if re.fullmatch(rb"INTEGRITY: executable-byte preflight passed \(\d+ bytes\)", raw):
                integrity["preflight"] = True
            if re.fullmatch(rb"INTEGRITY: executable-byte exit comparison passed \(\d+ bytes\)", raw):
                integrity["exit"] = True
            report(raw, secret)
        child_pid = None
        def started(pid):
            nonlocal child_pid
            child_pid = pid
            private_text(pid_file, str(pid) + "\n")
            print("RECEIVER: started; recovery attempt", attempt, flush=True)
        try:
            result = run_child(command, environment, stop, deadline, consume, started=started,
                               health=lambda: audio_env.alive() and asyncio.run(api_health(state)))
            summary = dict(exit_code=result.code, reason=result.reason, forced=result.forced,
                           integrity=integrity, recovery_attempt=attempt)
            private_text(state / "last-exit.json", json.dumps(summary) + "\n")
            print("LIFECYCLE:", json.dumps(summary), flush=True)
            return result
        finally:
            if pid_file.exists() and pid_file.read_text().strip() == str(child_pid):
                pid_file.unlink()
            if pulse_hint.exists() and pulse_hint.read_text().strip() == str(pulse_root):
                pulse_hint.unlink()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=0, help="0 runs until stopped; otherwise 30..86400")
    parser.add_argument("--restart-limit", type=int, default=3, help="Finite recovery budget; 0 disables retries")
    parser.add_argument("--soloist", help="Official Linux ARM64 executable (never copied into source)")
    parser.add_argument("--api-key-file", help="Owner-only file containing your Soloist API key")
    parser.add_argument("--device-name", default="Soloist Runtime" if BUNDLED else "Soloist macOS Lab")
    parser.add_argument("--audio-latency-ms", type=int, default=0,
                        help="PulseAudio buffer target, 20..2000 ms; 0 uses the engine default")
    args = parser.parse_args(argv)
    if not 1 <= len(args.device_name) <= 64 or any(ord(char) < 32 for char in args.device_name):
        parser.error("device name must be 1..64 printable characters")
    if args.seconds != 0 and not 30 <= args.seconds <= 86400:
        parser.error("duration must be 0 or 30..86400 seconds")
    if not 0 <= args.restart_limit <= 10:
        parser.error("restart limit must be 0..10")
    if args.audio_latency_ms != 0 and not 20 <= args.audio_latency_ms <= 2000:
        parser.error("audio latency must be 0 or 20..2000 ms")
    state, cache = STATE, CACHE
    for path in (state, cache):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        path.chmod(0o700)
    lock = (state / "receiver.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    engine = configured_path("soloist", args.soloist)
    key_path = configured_path("api_key_file", args.api_key_file)
    if key_path.stat().st_uid != os.getuid() or key_path.stat().st_mode & 0o077:
        raise SystemExit("The API key file must be owned by you and inaccessible to other users (chmod 600)")
    global PUBLIC_ERRORS
    PUBLIC_ERRORS = {part.decode("ascii") for part in engine.read_bytes().split(b"\0")
                     if 3 <= len(part) <= 120 and all(32 <= value < 127 for value in part)}
    secret = key_path.read_bytes().strip()
    if not secret or len(secret) > 4096:
        raise SystemExit("Invalid key file length")
    if not BUNDLED:
        CERTIFICATES.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile("/opt/homebrew/etc/ca-certificates/cert.pem", CERTIFICATES)
    if not CERTIFICATES.is_file():
        raise RuntimeError("Missing bundled certificate store")
    stop = threading.Event()
    original_handlers = {number: signal.signal(number, lambda *_: stop.set())
                         for number in (signal.SIGINT, signal.SIGTERM)}
    deadline = time.monotonic() + args.seconds if args.seconds else None
    print("STARTUP: audio buffer target", args.audio_latency_ms or "engine default", flush=True)
    print("STARTUP: duration", args.seconds or "until stopped", "; bounded recovery enabled", flush=True)
    try:
        attempt = 0
        while not stop.is_set():
            try:
                result = run_session(args, state, cache, engine, key_path, secret, stop, deadline, attempt)
            except (OSError, RuntimeError):
                print("RECOVERY: receiver/audio startup failed; details withheld", flush=True)
                result = Exit(1, "startup", False)
            delay = retry_delay(result, attempt, args.restart_limit, stop.is_set())
            if deadline is not None and time.monotonic() >= deadline:
                delay = None
            if delay is None:
                if result.code == 10:
                    print("RECEIVER: official build expired; install a current official executable", flush=True)
                if result.reason in ("requested", "duration") and not result.forced:
                    return 0
                return result.code if result.code else (1 if result.reason == "health" else 0)
            print("RECOVERY: restarting receiver and private audio in", delay,
                  "seconds; saved session retained; no forced playback", flush=True)
            if stop.wait(delay):
                return 0
            attempt += 1
        return 0
    finally:
        for number, handler in original_handlers.items():
            signal.signal(number, handler)


if __name__ == "__main__":
    raise SystemExit(main())
