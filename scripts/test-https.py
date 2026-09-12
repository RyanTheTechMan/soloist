"""Credential-free Linux versus macOS HTTPS smoke test, not authentication."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SYSROOT = ROOT / "build/sysroot"
ELFUSE = ROOT / "vendor/elfuse/build/elfuse"
LINUX = [str(ELFUSE), "--no-rosetta", "--clear-env", "--sysroot", str(SYSROOT),
         "--", str(SYSROOT / "usr/bin/curl"),
         "--cacert", "/etc/ssl/certs/ca-certificates.crt"]
HOST = ["/usr/bin/curl"]
results = []
for url, expected in (("https://clienttoken.spotify.com/v1/clienttoken", 405),
                      ("https://www.spotify.com/robots.txt", 200)):
    for name, prefix in (("linux-hvf", LINUX), ("macos", HOST)):
        command = prefix + ["--max-time", "15", "--silent", "--show-error",
                            "--output", "/dev/null", "--write-out",
                            "%{http_code} %{size_download} %{time_total}", url]
        process = subprocess.run(command, env={"PATH": os.defpath},
                                 capture_output=True, timeout=20, text=True)
        fields = process.stdout.split()
        result = {"runtime": name, "url": url, "exit_status": process.returncode,
                  "tls_verification_enabled": True, "credentials_used": False}
        if len(fields) == 3:
            result.update(http_status=int(fields[0]), bytes=int(fields[1]), seconds=float(fields[2]))
        result["passed"] = process.returncode == 0 and result.get("http_status") == expected
        results.append(result)
        print(json.dumps(result), flush=True)
(ROOT / "build/https-verification.json").write_text(json.dumps(results, indent=2) + "\n")
raise SystemExit(0 if all(result["passed"] for result in results) else 1)
