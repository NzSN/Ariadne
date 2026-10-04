#!/usr/bin/env python3
"""Build the prepared demo on native Windows with pinned Clang and installed SDK."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log, cwd, env, timeout=600, expected=0):
    result = subprocess.run([str(part) for part in command], cwd=cwd, env=env,
                            capture_output=True, timeout=timeout)
    output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
    log.write_text(output, encoding="utf-8")
    if result.returncode != expected:
        raise RuntimeError(f"Command failed ({result.returncode}); see {log}\n{output[-6000:]}")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cipd", required=True, type=Path)
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("run this script using native Windows Python")
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    work = args.output.resolve()
    inputs = json.loads((args.prepared / "build-inputs.json").read_text())
    identity = {"sourceArchiveSha256": sha(args.prepared / "source.tar.gz"),
                "inputsSha256": sha(args.prepared / "build-inputs.json")}
    if work.exists():
        if json.loads((work / "owner.json").read_text()) != identity:
            parser.error("existing output belongs to different inputs; choose a new directory")
    else:
        work.mkdir(parents=True)
        (work / "owner.json").write_text(json.dumps(identity, indent=2) + "\n")
        for name in ["source.tar.gz", "build-inputs.json", "tools.ensure"]:
            shutil.copyfile(args.prepared / name, work / name)
        with tarfile.open(work / "source.tar.gz") as archive:
            archive.extractall(work, filter="data")
    source = work / "source"
    for name, digest in inputs["sourceHashes"].items():
        if sha(source / name) != digest:
            raise RuntimeError(f"prepared source changed: {name}")

    environment = dict(os.environ)
    tools = work / "tools"
    print("Installing pinned GN and Ninja packages", flush=True)
    run([args.cipd, "ensure", "-root", tools, "-ensure-file", work / "tools.ensure"],
        work / "tools.log", work, environment)
    environment["PATH"] = str(tools) + os.pathsep + environment["PATH"]
    gn = tools / "gn.exe"
    ninja = tools / "ninja.exe"
    gn_command = [gn, "gen", "out/Release", "--root-target=//examples/ariadne_demo",
                  f"--script-executable={sys.executable}",
                  '--args=is_debug=false target_cpu="x64" mini_chromium_is_clang=true']
    print("Generating the x64 Clang/Windows SDK build", flush=True)
    run(gn_command, work / "gn.log", source, environment)
    ninja_digest = sha(source / "out/Release/build.ninja")
    run(gn_command, work / "gn-repeat.log", source, environment)
    if sha(source / "out/Release/build.ninja") != ninja_digest:
        raise RuntimeError("GN regeneration changed build.ninja")

    rejected = subprocess.run(
        [str(gn), "gen", "out/UnsupportedArm64", "--root-target=//examples/ariadne_demo",
         f"--script-executable={sys.executable}",
         '--args=is_debug=false target_cpu="arm64" mini_chromium_is_clang=true'],
        cwd=source, env=environment, capture_output=True, timeout=120)
    rejected_output = (rejected.stdout + rejected.stderr).decode("utf-8", errors="replace")
    (work / "arm64-rejection.log").write_text(rejected_output, encoding="utf-8")
    rejection_reasons = ("only installed x86/x64",
                         "The controlled workload requires Windows x64.")
    if rejected.returncode == 0 or not any(reason in rejected_output for reason in rejection_reasons):
        raise RuntimeError("unsupported ARM64 configuration was not explicitly rejected")

    print("Building demo, handler, and database utility", flush=True)
    run([ninja, "-C", "out/Release", "-j", str(args.jobs), "ariadne_crash_demo",
         "crashpad_handler", "crashpad_database_util"],
        work / "build.log", source, environment, timeout=1200)
    binaries = {name: sha(source / "out/Release" / name) for name in [
        "ariadne_crash_demo.exe", "crashpad_handler.exe", "crashpad_database_util.exe"]}
    for name, digest in inputs["sourceHashes"].items():
        if sha(source / name) != digest:
            raise RuntimeError(f"source changed during build: {name}")
    environment_file = source / "out/Release/environment.amd64"
    toolchain_environment = environment_file.read_bytes().decode("utf-8")
    sdk_versions = sorted(set(re.findall(r"Windows Kits\\10\\Include\\([^\\;]+)", toolchain_environment, re.IGNORECASE)))
    msvc_versions = sorted(set(re.findall(r"VC\\Tools\\MSVC\\([^\\;]+)", toolchain_environment, re.IGNORECASE)))
    result = {
        "schema": "ariadne.crashpad-demo-windows-build/v1",
        "passed": True,
        "recordedUtc": datetime.now(timezone.utc).isoformat(),
        "host": platform.platform(),
        "buildScriptSha256": sha(Path(__file__).resolve()),
        "inputs": identity,
        "crashpadRevision": inputs["crashpadRevision"],
        "buildOnlyAdjustments": inputs["buildOnlyAdjustments"],
        "architecture": "x64",
        "compiler": "fork-pinned Clang with installed Windows SDK/MSVC libraries",
        "windowsSdkVersions": sdk_versions,
        "msvcLibraryVersions": msvc_versions,
        "toolchainEnvironmentSha256": sha(environment_file),
        "sourcesStable": True,
        "stableGnRegeneration": True,
        "unsupportedArm64Rejected": True,
        "toolHashes": {"gn.exe": sha(gn), "ninja.exe": sha(ninja),
                       "python.exe": sha(sys.executable),
                       "clang-cl.exe": sha(source / "third_party/windows/clang/win-amd64/bin/clang-cl.exe"),
                       "lld-link.exe": sha(source / "third_party/windows/clang/win-amd64/bin/lld-link.exe"),
                       "llvm-ml.exe": sha(source / "third_party/windows/clang/win-amd64/bin/llvm-ml.exe")},
        "gnVersion": run([gn, "--version"], work / "gn-version.log", work, environment).strip(),
        "ninjaVersion": run([ninja, "--version"], work / "ninja-version.log", work, environment).strip(),
        "clangVersion": run([source / "third_party/windows/clang/win-amd64/bin/clang-cl.exe", "--version"],
                            work / "clang-version.log", work, environment).strip(),
        "binaryHashes": binaries,
        "binaryDirectory": str(source / "out/Release"),
        "scope": "Native Windows x64 build only; capture must be exercised separately.",
    }
    (work / "build.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"Build PASS: {work / 'build.json'}", flush=True)


if __name__ == "__main__":
    main()
