#!/usr/bin/env python3
"""Run the owned demo once and retain its local Crashpad database and minidump."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True, help="build.json from build_windows.py")
    parser.add_argument("--output", type=Path, required=True, help="new capture directory")
    parser.add_argument("--mode", choices=["partial", "full"], default="partial")
    parser.add_argument("--profile", choices=["null-write", "bap-workload", "zero-base-offset", "zero-base-offset-indexed"],
                        default="null-write")
    parser.add_argument("--check-failures", action="store_true")
    parser.add_argument("--minimal-environment", action="store_true",
                        help="use only Windows system keys for the owned captured process")
    args = parser.parse_args()
    if sys.platform != "win32":
        parser.error("run using native Windows Python")
    build = json.loads(args.build.read_text())
    if not build["passed"] or build["architecture"] != "x64":
        parser.error("a successful native x64 build is required")
    binaries = Path(build["binaryDirectory"])
    for name, digest in build["binaryHashes"].items():
        if sha(binaries / name) != digest:
            raise RuntimeError(f"binary differs from build record: {name}")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    demo = binaries / "ariadne_crash_demo.exe"
    handler = binaries / "crashpad_handler.exe"
    utility = binaries / "crashpad_database_util.exe"
    database = output / "database"
    witness = output / "witness.json"
    failures = {}
    demo_environment = None
    environment_policy = {"policy": "inherited"}
    if args.profile != "null-write" or args.minimal_environment:
        # This owned partial dump is retained as test evidence. Do not copy
        # developer credentials or tokens into the captured process environment.
        windows = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        demo_environment = {
            "SystemRoot": str(windows),
            "WINDIR": str(windows),
            "TEMP": str(output),
            "TMP": str(output),
            "PATH": str(windows / "System32") + os.pathsep + str(windows),
        }
        environment_policy = {
            "policy": "minimal-windows/v1",
            "keys": sorted(demo_environment),
        }

    def expect_setup_failure(name, command, candidate_database, candidate_witness):
        result = subprocess.run([str(part) for part in command], cwd=output,
                                capture_output=True, timeout=30,
                                env=demo_environment)
        (output / f"{name}.log").write_bytes(result.stdout + result.stderr)
        if (result.returncode == 0 or (result.returncode & 0xffffffff) == 0xc0000005
                or candidate_witness.exists() or list(candidate_database.rglob("*.dmp"))):
            raise RuntimeError(f"{name} did not fail before the deliberate crash")
        failures[name] = {"exitCode": result.returncode, "noWitness": True, "noDump": True}

    if args.check_failures:
        for name, chosen_handler, mode in [
            ("missing-handler", output / "does-not-exist.exe", "partial"),
            ("invalid-mode", handler, "invalid"),
        ]:
            candidate_database = output / (name + "-database")
            candidate_witness = output / (name + "-witness.json")
            expect_setup_failure(name, [demo, chosen_handler, candidate_database,
                                       candidate_witness, mode, args.profile],
                                 candidate_database, candidate_witness)

        candidate_database = output / "invalid-profile-database"
        candidate_witness = output / "invalid-profile-witness.json"
        expect_setup_failure("invalid-profile",
                             [demo, handler, candidate_database,
                              candidate_witness, args.mode, "invalid"],
                             candidate_database, candidate_witness)

    command = [str(p) for p in [demo, handler, database, witness, args.mode, args.profile]]
    started = datetime.now(timezone.utc).isoformat()
    with (output / "demo.stdout.log").open("wb") as stdout, (output / "demo.stderr.log").open("wb") as stderr:
        process = subprocess.Popen(command, cwd=output, stdout=stdout,
                                   stderr=stderr, env=demo_environment)
        try:
            code = process.wait(timeout=60)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            raise RuntimeError("owned demo timed out; its process was terminated")
    if (code & 0xffffffff) != 0xc0000005:
        raise RuntimeError(f"expected Windows access violation exit, got 0x{code & 0xffffffff:08x}")
    observation = json.loads(witness.read_text())
    expected_profile = {
        "null-write": "ariadne-crashpad-null-write-v1",
        "bap-workload": "ariadne-crashpad-bap-workload-v1",
        "zero-base-offset": "ariadne-crashpad-zero-base-offset-v1",
        "zero-base-offset-indexed": "ariadne-crashpad-zero-base-offset-indexed-v1",
    }[args.profile]
    if (observation["process_id"] != process.pid
            or observation["dump_mode"] != args.mode
            or observation["integration_profile"] != expected_profile):
        raise RuntimeError("witness belongs to another process, mode, or profile")

    deadline = time.monotonic() + 30
    reports = []
    while time.monotonic() < deadline:
        reports = list(database.rglob("*.dmp"))
        if len(reports) == 1 and reports[0].stat().st_size >= 32:
            break
        time.sleep(0.2)
    if len(reports) != 1:
        raise RuntimeError(f"expected one Crashpad report, found {len(reports)}")
    dump = output / "capture.dmp"
    shutil.copyfile(reports[0], dump)
    if dump.read_bytes()[:4] != b"MDMP":
        raise RuntimeError("report is not a minidump")
    executable = output / demo.name
    shutil.copyfile(demo, executable)
    uploads = subprocess.run([str(utility), f"--database={database}", "--show-uploads-enabled"],
                             capture_output=True, timeout=30, check=True)
    (output / "uploads-enabled.log").write_bytes(uploads.stdout + uploads.stderr)
    if uploads.stdout.strip() != b"false":
        raise RuntimeError("database uploads are not disabled")
    details = subprocess.run([str(utility), f"--database={database}", "--show-pending-reports",
                              "--show-completed-reports", "--show-all-report-info"],
                             capture_output=True, timeout=30, check=True)
    (output / "database.log").write_bytes(details.stdout + details.stderr)
    result = {
        "schema": "ariadne.crashpad-demo-capture/v1",
        "recordedUtc": started,
        "captureCreated": True,
        "host": "native Windows",
        "mode": args.mode,
        "profile": args.profile,
        "integrationProfile": expected_profile,
        "childEnvironment": environment_policy,
        "processId": process.pid,
        "exitCode": f"0x{code & 0xffffffff:08x}",
        "uploadsEnabled": False,
        "buildRecordSha256": sha(args.build),
        "crashpadRevision": build["crashpadRevision"],
        "handlerSha256": sha(handler),
        "dump": {"path": str(dump), "sha256": sha(dump), "bytes": dump.stat().st_size},
        "witnessSha256": sha(witness),
        "executableSha256": sha(executable),
        "setupFailures": failures,
        "scope": "Owned demo crashed and Crashpad wrote a minidump. Raw exception/context/code verification is a separate check.",
    }
    (output / "capture.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"Capture created: {dump} ({dump.stat().st_size} bytes)", flush=True)
    print(f"Record: {output / 'capture.json'}", flush=True)


if __name__ == "__main__":
    main()
