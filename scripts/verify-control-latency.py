"""Briefly mute or pause Soloist; measure private-monitor response, not acoustic latency."""
import argparse
import array
import asyncio
import json
import math
import os
from pathlib import Path
import subprocess
import time
import websockets
from observe import STATE


async def api(command, wanted):
    if (STATE / "ws.addr").read_text().strip() != "127.0.0.1":
        raise ValueError("Non-loopback endpoint")
    port = int((STATE / "ws.port").read_text().strip())
    if not 1 <= port <= 65535:
        raise ValueError("Invalid port")
    async with websockets.connect(f"ws://127.0.0.1:{port}", open_timeout=3,
                                  close_timeout=1, max_size=1024 * 1024) as ws:
        await ws.send(json.dumps(dict(type="command", **command)))
        while True:
            event = json.loads(await ws.recv())
            if event.get("type") == "error":
                raise RuntimeError("Control rejected")
            if event.get("type") == wanted:
                return event


async def request(command, wanted="command_result"):
    return await asyncio.wait_for(api(command, wanted), timeout=6)


async def main(pause=False):
    root = Path(__file__).resolve().parents[1]
    pulse = Path((STATE / "audio.path").read_text().strip())
    environment = {"PATH": os.defpath, "PULSE_SERVER": "unix:" + str(pulse / "native"),
                   "PULSE_COOKIE": str(pulse / "cookie")}
    streams = json.loads(subprocess.check_output(
        ["/opt/homebrew/bin/pactl", "-f", "json", "list", "sink-inputs"],
        env=environment, timeout=5, stderr=subprocess.DEVNULL))
    active = [stream for stream in streams if not stream.get("corked", True)]
    if len(active) != 1:
        raise RuntimeError("Expected one private playback stream")
    sinks = json.loads(subprocess.check_output(
        ["/opt/homebrew/bin/pactl", "-f", "json", "list", "sinks"],
        env=environment, timeout=5, stderr=subprocess.DEVNULL))
    sink = next(sink for sink in sinks if sink["index"] == active[0]["sink"])
    initial = await request({"command": "get_state"}, "playback_state")
    volume = initial.get("volume")
    if type(volume) not in (int, float) or not 0 < volume <= 100 or initial.get("status") != "playing":
        raise RuntimeError("Requires playing state and nonzero volume")
    process = await asyncio.create_subprocess_exec(
        "/opt/homebrew/bin/parec", "--raw", "--format=float32le", "--rate=44100",
        "--channels=2", "--latency-msec=20", "--device=" + str(sink["monitor_source"]),
        env=environment, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
    levels = []

    async def collect():
        while True:
            block = await process.stdout.readexactly(441 * 2 * 4)
            samples = array.array("f", block)
            if not all(math.isfinite(value) for value in samples):
                raise RuntimeError("Non-finite PCM")
            rms = math.sqrt(sum(value * value for value in samples) / len(samples))
            levels.append((time.monotonic(), rms))

    reader = asyncio.create_task(collect())
    restore_needed = False
    result = {"microphone_used": False, "audio_saved": False,
              "control": "pause" if pause else "volume_to_zero",
              "scope": "Command dispatch to private PulseAudio output monitor; excludes physical device/acoustic latency",
              "stream_buffer_latency_usec": active[0].get("buffer_latency_usec"),
              "sink_latency_usec": active[0].get("sink_latency_usec")}
    try:
        await asyncio.sleep(1.5)
        if reader.done():
            await reader
        baseline = sorted(level for _, level in levels[-100:])
        if len(baseline) < 50 or baseline[len(baseline) // 2] < 1e-7:
            raise RuntimeError("Insufficient non-silent baseline")
        threshold = max(1e-10, baseline[len(baseline) // 2] * 0.005)
        index = len(levels)
        sent = time.monotonic()
        restore_needed = True
        await request({"command": "pause"} if pause else {"command": "set_volume", "volume": 0})
        result["command_ack_ms"] = round((time.monotonic() - sent) * 1000, 1)
        quiet = 0
        while time.monotonic() - sent < 8:
            if reader.done():
                await reader
            while index < len(levels):
                arrived, rms = levels[index]
                quiet = quiet + 1 if rms <= threshold else 0
                index += 1
                if quiet >= 5:
                    result["silence_monitor_response_ms"] = round((levels[index - 5][0] - sent) * 1000, 1)
                    result["silence_observed"] = True
                    break
            if result.get("silence_observed"):
                break
            await asyncio.sleep(0.01)
        if not result.get("silence_observed"):
            result["silence_observed"] = False
            result["measurement_inconclusive"] = True
            # A suspended sink may stop monitor samples instead of sending
            # zero PCM. Absence of data cannot establish an audible deadline.
            result["note"] = "No measured silence transition; monitor suspension or playback failure must be checked separately"
    except Exception as error:
        result["error_type"] = type(error).__name__
    finally:
        if restore_needed:
            try:
                await request({"command": "play"} if pause else {"command": "set_volume", "volume": volume})
                result["original_state_restore_acknowledged"] = True
            except Exception as error:
                result["original_state_restore_acknowledged"] = False
                result["restore_error_type"] = type(error).__name__
        reader.cancel()
        await asyncio.gather(reader, return_exceptions=True)
        if process.returncode is None:
            process.terminate()
        try:
            await asyncio.wait_for(process.wait(), timeout=3)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
    result["passed"] = bool(result.get("silence_observed") and result.get("original_state_restore_acknowledged"))
    output = root / ("build/pause-latency-verification.json" if pause else "build/volume-latency-verification.json")
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    controls = parser.add_mutually_exclusive_group(required=True)
    controls.add_argument("--exercise-volume-to-zero", action="store_true",
                        help="Temporarily mute the running receiver and restore its original volume")
    controls.add_argument("--exercise-pause", action="store_true",
                         help="Temporarily pause the running receiver, then resume")
    args = parser.parse_args()
    try:
        raise SystemExit(asyncio.run(main(args.exercise_pause)))
    except Exception as error:
        print(json.dumps({"passed": False, "error_type": type(error).__name__}))
        raise SystemExit(1)
