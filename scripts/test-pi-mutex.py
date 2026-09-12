"""Build/run an owned Linux PI-mutex fixture; a wall timeout detects lost wakeups."""
import os
from pathlib import Path
import subprocess
from paths import ROOT, RUNTIME


def main():
    build = ROOT / "build"
    sysroot = build / "sysroot"
    rust = subprocess.check_output(["rustc", "--print", "sysroot"], text=True).strip()
    linker = Path(rust) / "lib/rustlib/aarch64-apple-darwin/bin/gcc-ld/ld.lld"
    for source, output in ((ROOT / "probes/pi-mutex-contention.c", build / "pi-mutex-contention.o"),
                           (ROOT / "probes/libc-start.S", build / "libc-start.o")):
        subprocess.run(["xcrun", "clang", "--target=aarch64-linux-gnu", "-O1",
                        "-ffreestanding", "-fno-stack-protector", "-Wall", "-Wextra", "-Werror",
                        "-c", str(source), "-o", str(output)], check=True)
    binary = build / "pi-mutex-contention.elf"
    subprocess.run([str(linker), "-e", "_start", "-z", "max-page-size=65536",
                    "--dynamic-linker", "/lib/ld-linux-aarch64.so.1", "--allow-shlib-undefined",
                    str(build / "libc-start.o"), str(build / "pi-mutex-contention.o"),
                    str(sysroot / "usr/lib/aarch64-linux-gnu/libc.so.6"), "-o", str(binary)], check=True)
    try:
        result = subprocess.run([str(RUNTIME), "--no-rosetta", "--clear-env", "--sysroot",
                                 str(sysroot), "--", str(binary)], timeout=10,
                                env={"PATH": os.defpath, "ELFUSE_VERIFY_TEXT": "1"})
        return result.returncode
    except subprocess.TimeoutExpired:
        print("FAIL: PI mutex fixture exceeded 10 seconds (possible lost wakeup)")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
