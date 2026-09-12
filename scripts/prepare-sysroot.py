"""Fetch verified Debian ARM64 library payloads; never install packages on macOS.

HTTPS authenticates the Debian index; package SHA256/size are verified against
that index. This is not an independent OpenPGP Release-signature verification.
Only data archives are extracted. No maintainer script is executed.
"""
import argparse
import hashlib
import io
import json
import lzma
import re
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
SYSROOT = BUILD / "sysroot"
CACHE = BUILD / "debs"
MIRROR = "https://deb.debian.org/debian/"
INDEX = "dists/trixie/main/binary-arm64/Packages.xz"
PACKAGES = {"libc6", "libgcc-s1", "libatomic1", "gcc-14-base"}


def download(url, destination):
    subprocess.run(
        ["curl", "--fail", "--location", "--proto", "=https", "--tlsv1.2",
         "--silent", "--show-error", "--max-time", "180", url,
         "--output", str(destination)], check=True)


def data_archive(blob):
    if not blob.startswith(b"!<arch>\n"):
        raise ValueError("Not a Debian ar archive")
    offset = 8
    while offset + 60 <= len(blob):
        header = blob[offset:offset + 60]
        if header[58:] != b"`\n":
            raise ValueError("Invalid ar member")
        size = int(header[48:58])
        if size < 0 or offset + 60 + size > len(blob):
            raise ValueError("Truncated ar member")
        name = header[:16].decode("ascii").strip().rstrip("/")
        if name.startswith("data.tar."):
            return blob[offset + 60:offset + 60 + size]
        offset += 60 + size + size % 2
    raise ValueError("Missing Debian data archive")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", action="store_true", help="Include PulseAudio client libraries and their dependencies")
    parser.add_argument("--network-test", action="store_true", help="Include Linux curl for credential-free HTTPS tests")
    parser.add_argument("--refresh-lock", action="store_true", help="Regenerate the selected package lock from the cached/downloaded index")
    args = parser.parse_args()
    lock_path = ROOT / ("sysroot-network-test-packages.json" if args.network_test else "sysroot-packages.json")
    requested = PACKAGES | ({"libpulse0"} if args.audio else set()) | ({"curl"} if args.network_test else set())
    CACHE.mkdir(parents=True, exist_ok=True)
    SYSROOT.mkdir(exist_ok=True)
    if not args.refresh_lock and lock_path.exists() and requested <= {entry["Package"] for entry in json.loads(lock_path.read_text())["packages"]}:
        lock = json.loads(lock_path.read_text())
    else:
        index_path = BUILD / "Packages.xz"
        if not index_path.exists():
            download(MIRROR + INDEX, index_path)
        index_blob = index_path.read_bytes()
        index = {}
        for stanza in lzma.decompress(index_blob).decode().split("\n\n"):
            fields = dict(line.split(": ", 1) for line in stanza.splitlines()
                          if line and not line.startswith(" ") and ": " in line)
            if "Package" in fields:
                index[fields["Package"]] = fields
        selected, pending = set(), list(requested)
        while pending:
            package = pending.pop()
            if package in selected:
                continue
            fields = index[package]
            selected.add(package)
            for dependency in (fields.get("Depends", "") + "," + fields.get("Pre-Depends", "")).split(","):
                if not dependency.strip():
                    continue
                alternatives = [re.split(r"[\s:(]", part.strip())[0] for part in dependency.split("|")]
                available = next((name for name in alternatives if name in index), None)
                if available is None:
                    raise ValueError("Cannot resolve dependency of " + package)
                pending.append(available)
        entries = [{key: index[package][key] for key in
                    ("Package", "Version", "Architecture", "Filename", "Size", "SHA256")}
                   for package in selected]
        lock = {"mirror": MIRROR, "index": INDEX,
                "index_sha256": hashlib.sha256(index_blob).hexdigest(),
                "packages": sorted(entries, key=lambda entry: entry["Package"])}
        lock_path.write_text(json.dumps(lock, indent=2) + "\n")
    if lock["mirror"] != MIRROR:
        raise ValueError("Unexpected package origin")
    for entry in lock["packages"]:
        relative = Path(entry["Filename"])
        if relative.is_absolute() or ".." in relative.parts or relative.parts[0] != "pool":
            raise ValueError("Invalid package path")
        if entry["Architecture"] not in ("arm64", "all"):
            raise ValueError("Wrong package architecture")
        archive = CACHE / relative.name
        if not archive.exists():
            download(MIRROR + relative.as_posix(), archive)
        blob = archive.read_bytes()
        if len(blob) != int(entry["Size"]) or hashlib.sha256(blob).hexdigest() != entry["SHA256"]:
            raise ValueError("Package integrity failure: " + entry["Package"])
        with tarfile.open(fileobj=io.BytesIO(data_archive(blob)), mode="r:*") as payload:
            payload.extractall(SYSROOT, filter="data")
        print("Verified and extracted", entry["Package"], entry["Version"], flush=True)
    # Debian's usr-merged layout, local aliases only. Never replace host paths.
    for alias in ("lib", "bin", "sbin"):
        path = SYSROOT / alias
        if not path.exists() and not path.is_symlink():
            path.symlink_to("usr/" + alias)
    print("Library sysroot:", SYSROOT)


if __name__ == "__main__":
    main()
