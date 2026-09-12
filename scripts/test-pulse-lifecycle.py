"""Compare native and Linux libpulse lifecycle callbacks using silence and no account."""
import json
import os
from pathlib import Path
import subprocess
import sys
from native_audio import native_audio
from paths import ROOT, RUNTIME


def run(*command):
    subprocess.run(command, check=True)


def main():
    build = ROOT / "build"
    source = ROOT / "probes/pulse-lifecycle.c"
    sysroot = build / "sysroot"
    build.mkdir(exist_ok=True)
    rust = subprocess.check_output(["rustc", "--print", "sysroot"], text=True).strip()
    linker = Path(rust) / "lib/rustlib/aarch64-apple-darwin/bin/gcc-ld/ld.lld"
    run("xcrun", "clang", "-O1", "-Wall", "-Wextra", "-Werror", str(source),
        "-L/opt/homebrew/lib", "-lpulse", "-o", str(build / "pulse-lifecycle-macos"))
    run("xcrun", "clang", "--target=aarch64-linux-gnu", "-O1", "-ffreestanding",
        "-fno-stack-protector", "-Wall", "-Wextra", "-Werror", "-c", str(source),
        "-o", str(build / "pulse-lifecycle.o"))
    run("xcrun", "clang", "--target=aarch64-linux-gnu", "-c",
        str(ROOT / "probes/libc-start.S"), "-o", str(build / "libc-start.o"))
    run(str(linker), "-e", "_start", "-z", "max-page-size=65536", "--dynamic-linker",
        "/lib/ld-linux-aarch64.so.1", "--allow-shlib-undefined",
        str(build / "libc-start.o"), str(build / "pulse-lifecycle.o"),
        str(sysroot / "usr/lib/aarch64-linux-gnu/libc.so.6"),
        str(sysroot / "usr/lib/aarch64-linux-gnu/libpulse.so.0"),
        "-o", str(build / "pulse-lifecycle.elf"))
    rows = []
    with native_audio() as environment:
        pulse = Path(environment["PULSE_RUNTIME_PATH"]).resolve()
        for latency in (0, 100):
            for backend in ("macos", "linux"):
                clean = {"PATH": os.defpath, "PULSE_SERVER": "unix:" + str(pulse / "native"),
                         "PULSE_COOKIE": str(pulse / "cookie")}
                if latency:
                    clean["PULSE_LATENCY_MSEC"] = str(latency)
                command = [str(build / "pulse-lifecycle-macos")]
                if backend == "linux":
                    command = [str(RUNTIME), "--no-rosetta", "--clear-env", "--sysroot", str(sysroot)]
                    for key, value in clean.items():
                        command.extend(["--env", key + "=" + value])
                    command.extend(["--", str(build / "pulse-lifecycle.elf")])
                row = {"backend": backend, "latency_ms": latency, "credentials_used": False}
                try:
                    result = subprocess.run(command, env=clean, capture_output=True, timeout=15)
                    row.update(exit_status=result.returncode, passed=result.returncode == 0)
                except subprocess.TimeoutExpired:
                    row.update(timed_out=True, passed=False)
                rows.append(row)
                print(json.dumps(row), flush=True)
    (build / "pulse-lifecycle-verification.json").write_text(json.dumps(rows, indent=2) + "\n")
    return 0 if all(row["passed"] for row in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
