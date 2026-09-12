"""Credential-free Soloist startup and executable-byte checkpoint verification."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time

from paths import ROOT, RUNTIME, configured_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soloist")
    args = parser.parse_args()
    ENGINE = configured_path("soloist", args.soloist)
    before = hashlib.sha256(ENGINE.read_bytes()).hexdigest()
    started = time.monotonic()
    result = subprocess.run(
        [str(RUNTIME), "--no-rosetta", "--clear-env", "--verbose",
         "--sysroot", str(ROOT / "build/sysroot"), "--", str(ENGINE), "--version"],
        env={"PATH": os.defpath, "ELFUSE_VERIFY_TEXT": "1"},
        capture_output=True, text=True, timeout=30,
    )
    elapsed_ms = round((time.monotonic() - started) * 1000, 1)
    after = hashlib.sha256(ENGINE.read_bytes()).hexdigest()
    checkpoints = re.findall(r"executable-byte (preflight|exit comparison) passed \((\d+) bytes\)", result.stderr)
    version = next((line for line in result.stdout.splitlines()
                    if re.fullmatch(r"soloist [0-9.]+ build \d+ \(\d+\) \(g[0-9a-f]+\) \(linux/aarch64\)", line)), None)
    passed = result.returncode == 0 and before == after and version is not None and len(checkpoints) == 2
    report = {
        "passed": passed, "guest_exit_status": result.returncode,
        "version": version, "elapsed_ms": elapsed_ms,
        "engine_file_sha256": before, "engine_file_unchanged": before == after,
        "executable_byte_checks": [{"stage": stage, "bytes": int(size)} for stage, size in checkpoints],
        "account_credentials_used": False, "playback_tested": False,
        "scope": "Main ELF and initial dynamic loader, before execution and after exit; not continuous monitoring or dlopen-library coverage",
    }
    print(json.dumps(report, indent=2))
    (ROOT / "build/startup-verification.json").write_text(json.dumps(report, indent=2) + "\n")
    if not passed:
        raise SystemExit("Startup verification failed; raw diagnostic output intentionally withheld")


if __name__ == "__main__":
    main()
