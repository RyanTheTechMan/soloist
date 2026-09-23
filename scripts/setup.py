"""Prepare the runtime around a separately downloaded official Soloist ELF."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from paths import ROOT, VENDOR, CONFIG

UPSTREAM = "https://github.com/sysprog21/elfuse.git"
REVISION = "4023647491db64adc43de76284206d8ab81ff6e3"


def run(*args, **kwargs):
    subprocess.run(args, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--soloist", type=Path)
    parser.add_argument("--api-key-file", type=Path)
    parser.add_argument("--build-only", action="store_true",
                        help="Build the public compatibility runtime without Soloist or credentials")
    parser.add_argument("--install-deps", action="store_true", help="Install missing Homebrew runtime build dependencies")
    args = parser.parse_args()
    if args.build_only:
        if args.soloist or args.api_key_file:
            parser.error("--build-only cannot be combined with private installation paths")
    elif not args.soloist:
        parser.error("--soloist is required unless --build-only is selected")
    if sys.version_info < (3, 12):
        parser.error("Python 3.12 or newer is required")
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        parser.error("This runtime currently supports Apple Silicon macOS only")
    if not args.build_only:
        engine = args.soloist.expanduser().resolve(strict=True)
        with engine.open("rb") as stream:
            header = stream.read(20)
        if len(header) != 20 or header[:6] != b"\x7fELF\x02\x01" or int.from_bytes(header[18:20], "little") != 183:
            parser.error("--soloist must be the official Linux ARM64 ELF executable, not the download archive")
    run("xcrun", "--find", "clang", stdout=subprocess.DEVNULL)
    brew = shutil.which("brew") or "/opt/homebrew/bin/brew"
    if not Path(brew).is_file():
        parser.error("Install Homebrew and Apple's Command Line Tools first; see README")
    prefix = subprocess.check_output([brew, "--prefix"], text=True).strip()
    if prefix != "/opt/homebrew":
        parser.error("This initial release requires the standard Apple Silicon Homebrew prefix /opt/homebrew")
    required = ("binutils", "pulseaudio", "ca-certificates")
    missing = [name for name in required if subprocess.run([brew, "list", "--versions", name], capture_output=True).returncode]
    if missing:
        if not args.install_deps:
            parser.error("Missing Homebrew dependencies: " + ", ".join(missing) + "; rerun with --install-deps")
        run(brew, "install", *missing, env=dict(os.environ, HOMEBREW_NO_AUTO_UPDATE="1", HOMEBREW_NO_INSTALL_CLEANUP="1"))
    ROOT.joinpath("vendor").mkdir(exist_ok=True)
    patch = ROOT / "patches/elfuse-soloist.patch"
    fingerprint = hashlib.sha256(patch.read_bytes()).hexdigest()
    stamp = VENDOR / ".soloist-runtime-patch"
    if not VENDOR.exists():
        run("git", "init", "-b", "main", str(VENDOR), stdout=subprocess.DEVNULL)
        run("git", "-C", str(VENDOR), "remote", "add", "origin", UPSTREAM)
        run("git", "-C", str(VENDOR), "fetch", "--depth=1", "origin", REVISION)
        run("git", "-C", str(VENDOR), "checkout", "--detach", "FETCH_HEAD")
    revision = subprocess.check_output(["git", "-C", str(VENDOR), "rev-parse", "HEAD"], text=True).strip()
    if revision != REVISION:
        parser.error("Vendor checkout is not at the pinned revision; refusing to overwrite it")
    if stamp.exists():
        if stamp.read_text().strip() != fingerprint:
            parser.error("Patch changed; preserve or move vendor/elfuse aside before rebuilding")
    else:
        run("git", "-C", str(VENDOR), "apply", "--check", str(patch))
        run("git", "-C", str(VENDOR), "apply", str(patch))
        stamp.write_text(fingerprint + "\n")
    run("make", "-C", str(VENDOR), "-j6", "elfuse")
    run(sys.executable, str(ROOT / "scripts/prepare-sysroot.py"), "--audio")
    if args.build_only:
        print("Public runtime build ready. Run: python3 scripts/build-package.py")
        return
    settings = json.loads(CONFIG.read_text()) if CONFIG.exists() else {}
    settings["soloist"] = str(engine)
    if args.api_key_file:
        key = args.api_key_file.expanduser().resolve(strict=True)
        info = key.stat()
        if not key.is_file() or info.st_uid != os.getuid() or info.st_mode & 0o077:
            parser.error("API-key file must be owned by you and have owner-only permissions")
        settings["api_key_file"] = str(key)
    CONFIG.parent.mkdir(mode=0o700, exist_ok=True)
    CONFIG.parent.chmod(0o700)
    CONFIG.write_text(json.dumps(settings, indent=2) + "\n")
    CONFIG.chmod(0o600)
    run(sys.executable, str(ROOT / "scripts/verify-startup.py"))
    print("Ready. Run: python3 scripts/run-receiver.py (supply --api-key-file if not configured).")


if __name__ == "__main__":
    main()
