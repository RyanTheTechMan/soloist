"""Test the private guest argument loader using public synthetic data only."""
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ELFUSE = ROOT / "vendor/elfuse/build/elfuse"
FIXTURE = ROOT / "build/private-argument.elf"
PUBLIC = b"public-fixture-value"


def run(path, expected, flags=()):
    command = [str(ELFUSE), "--no-rosetta", "--clear-env", *flags,
               "--append-arg-file", str(path), "--", str(FIXTURE)]
    assert PUBLIC.decode() not in " ".join(command)
    result = subprocess.run(command, env={"PATH": os.defpath},
                            capture_output=True, timeout=10)
    assert (result.returncode == 0) == expected, "Unexpected argument-loader status"
    assert PUBLIC not in result.stdout + result.stderr, "Argument appeared in diagnostics"


with tempfile.TemporaryDirectory(prefix="soloist-argument-test-") as directory:
    path = Path(directory) / "argument"
    for payload, mode, accepted in (
        (PUBLIC, 0o600, True), (PUBLIC + b"\r\n", 0o600, True),
        (PUBLIC, 0o644, False), (b"", 0o600, False),
        (b"\r\n", 0o600, False), (PUBLIC + b"\0", 0o600, False),
        (b"x" * 4097, 0o600, False),
    ):
        path.write_bytes(payload)
        path.chmod(mode)
        run(path, accepted)
    path.write_bytes(PUBLIC)
    path.chmod(0o600)
    link = Path(directory) / "symlink"
    link.symlink_to(path)
    run(link, False)
    run(path, False, ("--verbose",))
    run(path, False, ("--gdb", "12345"))
    run(Path(directory), False)
    run(Path(directory) / "missing", False)
    fifo = Path(directory) / "fifo"
    os.mkfifo(fifo, 0o600)
    run(fifo, False)
print("PASS: 13 private-argument cases; synthetic value absent from host argv and logs")
