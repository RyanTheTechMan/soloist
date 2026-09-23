"""Build a local, relocatable macOS ARM64 runtime app; never bundle Soloist or state."""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile

from paths import ROOT, RUNTIME

NATIVE_ROOT = Path("/opt/homebrew/opt/pulseaudio")
MODULES = ("module-native-protocol-unix.so", "module-coreaudio-detect.so",
           "module-coreaudio-device.so", "module-suspend-on-idle.so")


def run(*command, **kwargs):
    return subprocess.run([str(value) for value in command], check=True, **kwargs)


def dependencies(binary):
    output = subprocess.check_output(["otool", "-L", str(binary)], text=True)
    return [line.strip().split(" (", 1)[0] for line in output.splitlines()[1:]]


def collect_native(destination):
    destination.mkdir()
    modules = NATIVE_ROOT / "lib/pulseaudio/modules"
    pending = [NATIVE_ROOT / "bin" / name for name in ("pulseaudio", "pactl", "parec")]
    pending.extend(modules / name for name in MODULES)
    copied = {}
    packages = {}
    while pending:
        source = pending.pop().resolve(strict=True)
        if source.name in copied:
            if copied[source.name] != source:
                raise RuntimeError("Native library basename collision")
            continue
        copied[source.name] = source
        shutil.copy2(source, destination / source.name)
        parts = source.parts
        if len(parts) > 5 and parts[:4] == ("/", "opt", "homebrew", "Cellar"):
            packages[parts[4]] = {"version": parts[5], "root": str(Path(*parts[:6]))}
        for dependency in dependencies(source):
            if dependency.startswith("/opt/homebrew/"):
                pending.append(Path(dependency))
            elif not dependency.startswith(("/usr/lib/", "/System/Library/")):
                raise RuntimeError("Unexpected native dependency: " + dependency)
    for name, source in copied.items():
        target = destination / name
        target.chmod(target.stat().st_mode | 0o200)
        for dependency in dependencies(source):
            if dependency.startswith("/opt/homebrew/"):
                replacement = "@loader_path/" + Path(dependency).resolve().name
                run("install_name_tool", "-change", dependency, replacement, target,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if name.endswith(".dylib"):
            run("install_name_tool", "-id", "@loader_path/" + name, target,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        load_commands = subprocess.check_output(["otool", "-l", str(target)], text=True)
        for old_path in re.findall(r"\bpath (/opt/homebrew/[^\n]+) \(offset \d+\)", load_commands):
            run("install_name_tool", "-delete_rpath", old_path, target,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        run("codesign", "--force", "--sign", "-", target,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if any(value.startswith("/opt/homebrew/") for value in dependencies(target)):
            raise RuntimeError("Unrelocated dependency")
    return packages


def production_sysroot(destination):
    spec = importlib.util.spec_from_file_location("sysroot_builder", ROOT / "scripts/prepare-sysroot.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    lock = json.loads((ROOT / "sysroot-packages.json").read_text())
    destination.mkdir()
    for entry in lock["packages"]:
        relative = Path(entry["Filename"])
        if relative.is_absolute() or ".." in relative.parts or relative.parts[0] != "pool":
            raise ValueError("Invalid locked package path")
        if entry["Architecture"] not in ("arm64", "all"):
            raise ValueError("Invalid package architecture")
        archive = ROOT / "build/debs" / relative.name
        if not archive.is_file():
            raise RuntimeError("Run scripts/prepare-sysroot.py --audio before packaging")
        data = archive.read_bytes()
        if len(data) != int(entry["Size"]) or hashlib.sha256(data).hexdigest() != entry["SHA256"]:
            raise RuntimeError("Production package checksum failed")
        with tarfile.open(fileobj=io.BytesIO(module.data_archive(data)), mode="r:*") as payload:
            payload.extractall(destination, filter="data")
    for name in ("lib", "bin", "sbin"):
        (destination / "usr" / name).mkdir(parents=True, exist_ok=True)
        if not (destination / name).exists():
            (destination / name).symlink_to("usr/" + name)
    certificates = destination / "etc/ssl/certs/ca-certificates.crt"
    certificates.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2("/opt/homebrew/etc/ca-certificates/cert.pem", certificates)
    return lock


def licenses(destination, packages):
    destination.mkdir()
    shutil.copy2(ROOT / "vendor/elfuse/LICENSE", destination / "elfuse-LICENSE")
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", destination / "THIRD_PARTY_NOTICES.md")
    for name, package in packages.items():
        source = Path(package["root"])
        notice = destination / name
        notice.mkdir()
        for path in source.rglob("*"):
            if path.is_file() and (path.name.upper().startswith(("LICENSE", "COPYING", "NOTICE", "AUTHORS"))):
                relative = path.relative_to(source)
                output = notice / relative
                output.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, output)
        receipt = source / "INSTALL_RECEIPT.json"
        if receipt.is_file():
            data = json.loads(receipt.read_text())
            package["homebrew_source"] = data.get("source", {}).get("spec", "stable")
        package.pop("root")
    # This records what is bundled, not a claim that notices alone satisfy
    # every redistribution obligation. Public release remains a separate gate.
    (destination / "native-versions.json").write_text(json.dumps(packages, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="Soloist Runtime", help="Local output app basename")
    parser.add_argument("--version", default="0.1.0", help="Package version as MAJOR.MINOR.PATCH")
    args = parser.parse_args()
    if not args.name or any(value in args.name for value in ("/", "\\", "..")):
        parser.error("Choose a simple app basename")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", args.version):
        parser.error("Version must be MAJOR.MINOR.PATCH")
    output = ROOT / "dist" / (args.name + ".app")
    if output.exists():
        parser.error("Output already exists; choose another --name to preserve the previous build")
    (ROOT / "build").mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="package-", dir=ROOT / "build"))
    run(sys.executable, "-m", "PyInstaller", "--onedir", "--windowed", "--noupx", "--target-arch", "arm64",
        "--osx-bundle-identifier", "local.soloistcompat.helper",
        "--name", "runtime-cli", "--distpath", work / "frozen", "--workpath", work / "freeze-work",
        "--specpath", work, "--copy-metadata", "websockets",
        "--hidden-import", "keyring.backends.macOS", "--paths", ROOT / "scripts",
        ROOT / "scripts/runtime_cli.py")
    app = work / (args.name + ".app")
    contents = app / "Contents"
    helpers = contents / "Helpers"
    helpers.mkdir(parents=True)
    helper = helpers / "runtime-cli.app"
    shutil.copytree(work / "frozen/runtime-cli.app", helper, symlinks=True)
    payload = helper / "Contents/Resources/payload"
    payload.mkdir()
    (payload / "version.txt").write_text(args.version + "\n")
    shutil.copy2(RUNTIME, helper / "Contents/MacOS/elfuse")
    # Linux payload is added after freezing: never let a Mach-O packager process
    # it as native code, and never copy the development sysroot or saved state.
    lock = production_sysroot(payload / "sysroot")
    native = collect_native(work / "native")
    for path in (work / "native").iterdir():
        shutil.move(path, helper / "Contents/Frameworks" / path.name)
    # Homebrew's parec is an argv[0]-selected alias of pacat.
    if not (helper / "Contents/Frameworks/parec").exists():
        (helper / "Contents/Frameworks/parec").symlink_to("pacat")
    resources = contents / "Resources"
    resources.mkdir()
    licenses(resources / "Licenses", native)
    shutil.copy2(ROOT / "packaging/QUICKSTART.md", resources / "QUICKSTART.md")
    run("codesign", "--force", "--sign", "-", helper)
    manifest = {"version": args.version, "platform": "macos-arm64", "soloist_included": False,
                "source_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
                "source_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
                "signing": "local-ad-hoc-not-notarized", "native_packages": native,
                "linux_packages": lock["packages"],
                "symlinks": {str(path.relative_to(helper / "Contents")): str(path.readlink())
                             for path in sorted((helper / "Contents").rglob("*")) if path.is_symlink()},
                "files": {str(path.relative_to(helper / "Contents")): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in sorted((helper / "Contents").rglob("*"))
                          if path.is_file() and not path.is_symlink() and "_CodeSignature" not in path.parts}}
    (resources / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    macos = contents / "MacOS"
    macos.mkdir()
    run("xcrun", "clang", "-fobjc-arc", "-Wall", "-Wextra", "-Werror", "-arch", "arm64",
        "-mmacosx-version-min=27.0", "-framework", "AppKit",
        "-framework", "ServiceManagement", ROOT / "packaging/launcher.m",
        "-o", macos / "SoloistRuntime")
    info = {"CFBundleExecutable": "SoloistRuntime", "CFBundleIdentifier": "local.soloistcompat.runtime",
            "CFBundleName": "Soloist Runtime", "CFBundleDisplayName": "Soloist Runtime",
            "CFBundlePackageType": "APPL", "CFBundleVersion": args.version,
            "CFBundleShortVersionString": args.version,
            "LSMinimumSystemVersion": "27.0", "NSHighResolutionCapable": True,
            "NSLocalNetworkUsageDescription": "Discover and pair your local Spotify Connect receiver."}
    with (contents / "Info.plist").open("wb") as stream:
        plistlib.dump(info, stream)
    run("codesign", "--force", "--sign", "-", app)
    run("codesign", "--verify", "--deep", "--strict", app)
    output.parent.mkdir(exist_ok=True)
    shutil.move(app, output)
    print("Built local preview:", output)
    print("Soloist, API keys, sessions and playback caches were not packaged.")
    print("Public redistribution/notarization and local API hardening are still separate release gates.")


if __name__ == "__main__":
    main()
