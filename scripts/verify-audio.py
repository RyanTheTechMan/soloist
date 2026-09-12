"""Measure only the private app audio monitor; no microphone or saved audio."""
import array
import json
import math
import os
from pathlib import Path
import selectors
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
pulse_root = Path((ROOT / "state/audio.path").read_text().strip())
environment = {"PATH": os.defpath, "PULSE_SERVER": "unix:" + str(pulse_root / "native"),
               "PULSE_COOKIE": str(pulse_root / "cookie")}


def listing(kind):
    result = subprocess.run(["/opt/homebrew/bin/pactl", "-f", "json", "list", kind],
                            env=environment, capture_output=True, timeout=5, check=True)
    return json.loads(result.stdout)


streams = listing("sink-inputs")
active = [stream for stream in streams if not stream.get("corked", True)]
if len(active) != 1:
    raise SystemExit("Expected exactly one active stream in the private audio server")
stream = active[0]
sink = next(sink for sink in listing("sinks") if sink["index"] == stream["sink"])
monitor = sink["monitor_source"]
command = ["/opt/homebrew/bin/parec", "--raw", "--format=float32le", "--rate=44100",
           "--channels=2", "--latency-msec=50", "--device=" + str(monitor)]
payload = bytearray()
process = subprocess.Popen(command, env=environment, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
try:
    deadline = time.monotonic() + 3
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ)
        while time.monotonic() < deadline and len(payload) < 2 * 1024 * 1024:
            for event, _ in selector.select(0.1):
                block = os.read(event.fd, 8192)
                if not block:
                    raise RuntimeError("Private audio monitor ended unexpectedly")
                payload.extend(block)
finally:
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
samples = array.array("f")
samples.frombytes(payload[:len(payload) // 4 * 4])
finite = [value for value in samples if math.isfinite(value)]
result = {
    "measurement": "private native playback monitor, not a source-bit-depth proof",
    "microphone_used": False, "audio_saved": False,
    "active_stream_sample_specification": stream.get("sample_specification"),
    "buffer_latency_usec": stream.get("buffer_latency_usec"),
    "sink_latency_usec": stream.get("sink_latency_usec"),
    "captured_frames": len(samples) // 2,
    "nonzero_samples": sum(value != 0 for value in finite),
    "peak": max((abs(value) for value in finite), default=0),
    "rms": math.sqrt(sum(value * value for value in finite) / max(1, len(finite))),
}
result["non_silent_pcm_verified"] = result["captured_frames"] > 44100 and result["rms"] > 1e-7
(ROOT / "build/audio-verification.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
raise SystemExit(0 if result["non_silent_pcm_verified"] else 1)
