"""Bounded read-only API/CPU sampling; no credentials, metadata or audio saved."""
import argparse
import asyncio
import json
from pathlib import Path
import subprocess
import time
import websockets
from observe import STATE, safe_event


def cpu_seconds(pid):
    raw = subprocess.check_output(["ps", "-p", str(pid), "-o", "time="],
                                  text=True, timeout=3).strip()
    fields = raw.split(":")
    return sum(float(value) * 60 ** index for index, value in enumerate(reversed(fields)))


async def sample():
    if (STATE / "ws.addr").read_text().strip() != "127.0.0.1":
        raise ValueError("Non-loopback endpoint")
    port = int((STATE / "ws.port").read_text().strip())
    if not 1 <= port <= 65535:
        raise ValueError("Invalid port")
    start = time.monotonic()
    async with websockets.connect(f"ws://127.0.0.1:{port}", open_timeout=3,
                                  close_timeout=1, max_size=1024 * 1024) as ws:
        await ws.send(json.dumps({"type": "command", "command": "get_state"}))
        while True:
            event = json.loads(await ws.recv())
            if isinstance(event, dict) and event.get("type") == "playback_state":
                return dict(safe_event(event), api_response_ms=round((time.monotonic() - start) * 1000, 1))


async def main(seconds, interval):
    pid = int((STATE / "receiver.pid").read_text().strip())
    start = last_time = time.monotonic()
    last_cpu = cpu_seconds(pid)
    rows = []
    consecutive_failures = 0
    while time.monotonic() - start < seconds:
        await asyncio.sleep(min(interval, seconds - (time.monotonic() - start)))
        now = time.monotonic()
        row = {"elapsed_seconds": round(now - start, 1)}
        try:
            if int((STATE / "receiver.pid").read_text().strip()) != pid:
                raise ValueError("Receiver changed")
            cpu = cpu_seconds(pid)
            row["cpu_percent_one_core"] = round((cpu - last_cpu) * 100 / (now - last_time), 2)
            last_cpu, last_time = cpu, now
            row.update(await asyncio.wait_for(sample(), timeout=6))
            row["api_responsive"] = True
            consecutive_failures = 0
        except Exception as error:
            row["api_responsive"] = False
            row["error_type"] = type(error).__name__
            consecutive_failures += 1
        rows.append(row)
        print(json.dumps(row), flush=True)
        if consecutive_failures >= 3:
            break
    consecutive_high = longest_high = 0
    for row in rows:
        consecutive_high = consecutive_high + 1 if row.get("cpu_percent_one_core", 0) >= 80 else 0
        longest_high = max(longest_high, consecutive_high)
    result = {"duration_seconds": round(time.monotonic() - start, 1), "samples": rows,
              "requested_duration_seconds": seconds,
              "stopped_after_three_api_failures": consecutive_failures >= 3,
              "all_api_samples_responsive": all(row["api_responsive"] for row in rows),
              "three_consecutive_high_cpu_samples": longest_high >= 3,
              "scope": "Read-only API and interval CPU checks, not audible continuity or overnight certification"}
    result["passed"] = result["all_api_samples_responsive"] and longest_high < 3
    output = Path(__file__).resolve().parents[1] / "build/stability-verification.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: value for key, value in result.items() if key != "samples"}), flush=True)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=600)
    parser.add_argument("--interval", type=int, default=10)
    args = parser.parse_args()
    if not 30 <= args.seconds <= 1800 or not 2 <= args.interval <= 60:
        parser.error("seconds must be 30..1800 and interval 2..60")
    raise SystemExit(asyncio.run(main(args.seconds, args.interval)))
