"""Private macOS playback server; no microphone, TCP listener or system daemon."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import audio_routing
from paths import PULSE, PACTL, PULSE_MODULES


class AudioEnvironment(dict):
    def alive(self):
        return self.process.poll() is None

    def refresh_route(self):
        self.requested_output_uid = audio_routing.read_preference()
        devices = audio_routing.available_outputs()
        target, _ = audio_routing.choose_output(devices, self.requested_output_uid)
        if target["id"] != self.current_output_id:
            selected = audio_routing.route(self, self.requested_output_uid, devices)
            self.current_output_id = selected["object_id"]
            print("AUDIO: routed to macOS output " + selected["name"] +
                  (" (selected device unavailable; using default)" if selected["fallback_to_default"] else ""),
                  flush=True)


@contextmanager
def native_audio(output_uid=""):
    with tempfile.TemporaryDirectory(prefix="soloist-pulse-", dir="/tmp") as directory:
        root = Path(directory)
        environment = AudioEnvironment(PATH=os.defpath)
        environment.update(PULSE_RUNTIME_PATH=directory, PULSE_STATE_PATH=directory,
                           PULSE_COOKIE=str(root / "cookie"),
                           PULSE_SERVER="unix:" + str(root / "native"))
        environment.requested_output_uid = output_uid
        environment.current_output_id = None
        audio_routing.save_preference(output_uid)
        command = [str(PULSE), "-p", str(PULSE_MODULES), "-n", "--daemonize=no",
                   "--use-pid-file=no", "--exit-idle-time=-1", "--disallow-module-loading=yes",
                   "--log-target=stderr", "--log-level=error", "--disable-shm=yes",
                   "--high-priority=no", "--realtime=no",
                   "-L", f"module-native-protocol-unix socket={root / 'native'} auth-cookie={root / 'cookie'}",
                   "-L", "module-coreaudio-detect record=no playback=yes",
                   "-L", "module-suspend-on-idle timeout=2"]
        with subprocess.Popen(command, env=environment, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL) as audio:
            environment.process = audio
            try:
                for _ in range(200):
                    if audio.poll() is not None:
                        raise RuntimeError("Private audio server failed to start")
                    if (root / "native").exists():
                        break
                    time.sleep(0.1)
                else:
                    raise RuntimeError("Private audio server startup timed out")
                for _ in range(30):
                    result = subprocess.run([str(PACTL), "-f", "json", "list", "sinks"],
                                            env=environment, capture_output=True, timeout=5)
                    if result.returncode == 0 and json.loads(result.stdout or b"[]"):
                        break
                    time.sleep(0.1)
                else:
                    raise RuntimeError("Private server has no CoreAudio output")
                environment.refresh_route()
                print("STARTUP: private native audio server ready (microphone disabled)", flush=True)
                yield environment
            finally:
                if audio.poll() is None:
                    audio.terminate()
                    try:
                        audio.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        audio.kill()
                        audio.wait()
