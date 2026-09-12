"""Read-only soak/recovery telemetry; no credentials, metadata or audio saved."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import re
import time
import websockets
from observe import STATE, safe_event


def cpu_seconds(pid):
    raw = subprocess.check_output(["ps", "-p", str(pid), "-o", "time="],
                                  text=True, timeout=3).strip()
    fields = raw.split(":")
    return sum(float(value) * 60 ** index for index, value in enumerate(reversed(fields)))


def memory_kib(pid):
    return int(subprocess.check_output(["ps", "-p", str(pid), "-o", "rss="],
                                       text=True, timeout=3).strip())


def audio_state():
    root = Path((STATE / "audio.path").read_text().strip())
    result = subprocess.run(["/opt/homebrew/bin/pactl", "-f", "json", "list", "sink-inputs"],
                            env={"PATH": os.defpath, "PULSE_SERVER": "unix:" + str(root / "native"),
                                 "PULSE_COOKIE": str(root / "cookie")},
                            capture_output=True, timeout=3, check=True)
    streams = json.loads(result.stdout)
    active = [stream for stream in streams if stream.get("corked") is False]
    row = {"audio_server_responsive": True, "active_audio_streams": len(active)}
    if len(active) == 1:
        for key in ("buffer_latency_usec", "sink_latency_usec"):
            value = active[0].get(key)
            if type(value) in (int, float) and 0 <= value < 10 ** 10:
                row[key] = value
        spec = active[0].get("sample_specification", "")
        if isinstance(spec, str) and re.fullmatch(r"[a-z0-9]{1,16} \d{1,2}ch \d{4,6}Hz", spec):
            row["output_sample_specification"] = spec
    return row


async def sample():
    if (STATE / "ws.addr").read_text().strip() != "127.0.0.1":
        raise ValueError("Non-loopback endpoint")
    port = int((STATE / "ws.port").read_text().strip())
    if not 1 <= port <= 65535:
        raise ValueError("Invalid port")
    start = time.monotonic()
    async with websockets.connect(f"ws://127.0.0.1:{port}", open_timeout=3,
                                  close_timeout=1, max_size=1024 * 1024) as ws:
        await ws.send(json.dumps({"type": "command", "command": "get_auth_state"}))
        await ws.send(json.dumps({"type": "command", "command": "get_state"}))
        while True:
            event = json.loads(await ws.recv())
            if isinstance(event, dict) and event.get("type") == "auth_state" and event.get("logged_in") is False:
                return dict(safe_event(event), api_response_ms=round((time.monotonic() - start) * 1000, 1))
            if isinstance(event, dict) and event.get("type") == "playback_state":
                return dict(safe_event(event), api_response_ms=round((time.monotonic() - start) * 1000, 1))


async def main(seconds, interval, allow_recovery=False, label="stability"):
    pid = int((STATE / "receiver.pid").read_text().strip())
    start = last_time = time.monotonic()
    last_cpu = cpu_seconds(pid)
    wall_start = time.time()
    output = Path(__file__).resolve().parents[1] / "build" / (label + "-verification.json")
    output.parent.mkdir(exist_ok=True)
    journal = output.with_suffix(".jsonl")
    if journal.exists():
        raise SystemExit("Report already exists; choose a new --label to preserve earlier evidence")
    journal.touch(mode=0o600)
    rows = []
    consecutive_failures = 0
    while time.monotonic() - start < seconds:
        await asyncio.sleep(min(interval, seconds - (time.monotonic() - start)))
        now = time.monotonic()
        row = {"elapsed_seconds": round(now - start, 1),
               "wall_elapsed_seconds": round(time.time() - wall_start, 1)}
        try:
            current_pid = int((STATE / "receiver.pid").read_text().strip())
            if current_pid != pid:
                if not allow_recovery:
                    raise ValueError("Receiver changed")
                row["receiver_restarted"] = True
                pid = current_pid
                last_cpu, last_time = cpu_seconds(pid), now
            cpu = cpu_seconds(pid)
            if now > last_time:
                row["cpu_percent_one_core"] = round((cpu - last_cpu) * 100 / (now - last_time), 2)
            last_cpu, last_time = cpu, now
            row["resident_memory_kib"] = memory_kib(pid)
            row.update(await asyncio.wait_for(sample(), timeout=6))
            row["api_responsive"] = True
            consecutive_failures = 0
        except Exception as error:
            row["api_responsive"] = False
            row["error_type"] = type(error).__name__
            consecutive_failures += 1
        try:
            row.update(audio_state())
        except Exception as error:
            row["audio_server_responsive"] = False
            row["audio_error_type"] = type(error).__name__
        rows.append(row)
        print(json.dumps(row), flush=True)
        with journal.open("a") as stream:
            stream.write(json.dumps(row) + "\n")
        if consecutive_failures >= 3 and not allow_recovery:
            break
    consecutive_high = longest_high = 0
    for row in rows:
        consecutive_high = consecutive_high + 1 if row.get("cpu_percent_one_core", 0) >= 80 else 0
        longest_high = max(longest_high, consecutive_high)
    result = {"duration_seconds": round(time.monotonic() - start, 1), "samples": rows,
              "requested_duration_seconds": seconds,
              "stopped_after_three_api_failures": consecutive_failures >= 3 and not allow_recovery,
              "recovery_observation_mode": allow_recovery,
              "all_api_samples_responsive": all(row["api_responsive"] for row in rows),
              "three_consecutive_high_cpu_samples": longest_high >= 3,
              "scope": "API, CPU, RSS and output-buffer snapshots; not acoustic continuity, underrun counts or source bit depth"}
    result["passed"] = result["all_api_samples_responsive"] and longest_high < 3
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "samples"}), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--interval", type=int, default=10)
    parser.add_argument("--allow-recovery", action="store_true", help="Keep observing across API failures/restarts")
    parser.add_argument("--label", default="stability", help="Unique local report name")
    args = parser.parse_args()
    if not 30 <= args.seconds <= 86400 or not 2 <= args.interval <= 60:
        parser.error("seconds must be 30..86400 and interval 2..60")
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,40}", args.label):
        parser.error("label must contain 1..40 ASCII letters, digits, underscores or hyphens")
    raise SystemExit(asyncio.run(main(args.seconds, args.interval, args.allow_recovery, args.label)))
