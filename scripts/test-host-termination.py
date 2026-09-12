"""Account-free host-to-Linux lifecycle signal and post-exit integrity tests."""
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time
from paths import ROOT, RUNTIME


def main():
    build = ROOT / "build"
    sysroot = build / "sysroot"
    rust = subprocess.check_output(["rustc", "--print", "sysroot"], text=True).strip()
    linker = Path(rust) / "lib/rustlib/aarch64-apple-darwin/bin/gcc-ld/ld.lld"
    for name in ("host-termination.c", "libc-start.S"):
        subprocess.run(["xcrun", "clang", "--target=aarch64-linux-gnu", "-O1",
                        "-ffreestanding", "-fno-stack-protector", "-Wall", "-Wextra", "-Werror",
                        "-c", str(ROOT / "probes" / name), "-o", str(build / (name + ".o"))], check=True)
    binary = build / "host-termination.elf"
    subprocess.run([str(linker), "-e", "_start", "-z", "max-page-size=65536",
                    "--dynamic-linker", "/lib/ld-linux-aarch64.so.1", "--allow-shlib-undefined",
                    str(build / "libc-start.S.o"), str(build / "host-termination.c.o"),
                    str(sysroot / "usr/lib/aarch64-linux-gnu/libc.so.6"), "-o", str(binary)], check=True)
    for mode, number, expected in (("term", signal.SIGTERM, 0), ("int", signal.SIGINT, 0),
                                   ("default", signal.SIGTERM, 143)):
        command = [str(RUNTIME), "--no-rosetta", "--clear-env", "--sysroot", str(sysroot),
                   "--", str(binary), mode]
        environment = {"PATH": os.defpath, "ELFUSE_VERIFY_TEXT": "1", "ELFUSE_FORWARD_TERMINATION": "1"}
        with subprocess.Popen(command, env=environment, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT) as process:
            output = b""
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    deadline = time.monotonic() + 10
                    while b"READY\n" not in output:
                        if time.monotonic() > deadline or process.poll() is not None:
                            raise RuntimeError("Signal fixture did not become ready")
                        for key, _ in selector.select(0.1):
                            output += os.read(key.fd, 8192)
                process.send_signal(number)
                output += process.communicate(timeout=10)[0]
                if process.returncode != expected or b"INTEGRITY: executable-byte exit comparison passed" not in output:
                    print(output.decode(errors="replace"))
                    raise RuntimeError("Signal exit or executable comparison failed: " + str(process.returncode))
                print("PASS:", mode, "delivery, clean exit and executable-byte comparison")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
