"""Bounded HVF Soloist receiver. No API key in host argv; filtered logs only."""
import argparse
import fcntl
import os
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import time

from paths import ROOT, RUNTIME, configured_path
PUBLIC_ERRORS = set()
from native_audio import native_audio


def report(raw, secret):
    line = re.sub(r"\x1b\[[0-9;]*m", "", raw.replace(secret, b"[redacted]").decode(errors="replace"))
    if line.startswith("INTEGRITY:"):
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=900)
    parser.add_argument("--soloist", help="Official Linux ARM64 executable (never copied into source)")
    parser.add_argument("--api-key-file", help="Owner-only file containing your Soloist API key")
    args = parser.parse_args()
    if not 30 <= args.seconds <= 1800:
        parser.error("duration must be 30..1800 seconds")
    state = ROOT / "state"
    cache = ROOT / "cache"
    for path in (state, cache):
        path.mkdir(exist_ok=True, mode=0o700)
        path.chmod(0o700)
    lock = (state / "receiver.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    engine = configured_path("soloist", args.soloist)
    key_path = configured_path("api_key_file", args.api_key_file)
    global PUBLIC_ERRORS
    PUBLIC_ERRORS = {part.decode("ascii") for part in engine.read_bytes().split(b"\0")
                     if 3 <= len(part) <= 120 and all(32 <= value < 127 for value in part)}
    secret = key_path.read_bytes().strip()
    if not secret or len(secret) > 4096:
        raise SystemExit("Invalid key file length")
    sysroot = ROOT / "build/sysroot"
    certificates = sysroot / "etc/ssl/certs/ca-certificates.crt"
    certificates.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile("/opt/homebrew/etc/ca-certificates/cert.pem", certificates)
    with native_audio() as audio_env:
        # /tmp belongs to the Linux sysroot. Use the canonical Darwin host
        # location for this explicitly shared private socket, not a guest /run
        # symlink whose absolute target is resolved inside the Linux namespace.
        pulse_root = Path(audio_env["PULSE_RUNTIME_PATH"]).resolve()
        pulse_hint = state / "audio.path"
        pulse_hint.write_text(str(pulse_root) + "\n")
        pulse_hint.chmod(0o600)
        command = [str(RUNTIME),
                   "--no-rosetta", "--clear-env", "--timeout", str(args.seconds),
                   "--sysroot", str(sysroot),
                   "--append-arg-file", str(key_path),
                   "--env", "PULSE_SERVER=unix:" + str(pulse_root / "native"),
                   "--env", "PULSE_COOKIE=" + str(pulse_root / "cookie"),
                   "--env", "SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt",
                   "--", str(engine),
                   "-n", "Soloist macOS Lab", "-D", str(state), "-C", str(cache),
                   "-z", "100", "-w", "127.0.0.1:0", "-i", "5", "-v", "-k"]
        environment = {"PATH": os.defpath, "ELFUSE_VERIFY_TEXT": "1"}
        process = subprocess.Popen(command, env=environment, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        pid_file = state / "receiver.pid"
        pid_file.write_text(str(process.pid) + "\n")
        pid_file.chmod(0o600)
        print("RECEIVER: starting Soloist macOS Lab; duration", args.seconds, "seconds", flush=True)
        # Let elfuse's own timeout unwind the VM and perform the exit integrity
        # check. The parent deadline is only a backup for a stuck runtime.
        deadline = time.monotonic() + args.seconds + 10
        pending = b""
        timed_out = False
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while selector.get_map():
                    now = time.monotonic()
                    if now >= deadline and not timed_out:
                        timed_out = True
                        process.terminate()
                    if timed_out and now >= deadline + 15 and process.poll() is None:
                        process.kill()
                    for event, _ in selector.select(0.25):
                        block = os.read(event.fd, 8192)
                        if not block:
                            selector.unregister(event.fileobj)
                            continue
                        pending += block
                        while b"\n" in pending:
                            line, pending = pending.split(b"\n", 1)
                            report(line, secret)
                        if len(pending) > 1024 * 1024:
                            raise RuntimeError("Oversized diagnostic line; withheld")
            if pending:
                report(pending, secret)
            status = process.wait(timeout=15)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            if pid_file.exists() and pid_file.read_text().strip() == str(process.pid):
                pid_file.unlink()
            if pulse_hint.exists() and pulse_hint.read_text().strip() == str(pulse_root):
                pulse_hint.unlink()
        timed_out = timed_out or status == 124
        print("RECEIVER: exit", status, "duration limit" if timed_out else "", flush=True)
        return 124 if timed_out else status


if __name__ == "__main__":
    raise SystemExit(main())
