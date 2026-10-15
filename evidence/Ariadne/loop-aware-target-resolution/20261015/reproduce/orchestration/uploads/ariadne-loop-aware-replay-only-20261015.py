#!/usr/bin/env python3
"""Run the retained 330-observation corpus in the remote task checkout only.

The production replay tool fixes its Cargo directory at target/bap-core-replay.
This driver gives that name a task-owned alias to target/loop-aware-replay-build;
the setup wrapper maps it to /loop-work/replay-build, distinct from ordinary and
mutation builds. No production tool, corpus, model or source is rewritten.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def verify_sources(root, manifest):
    files = manifest["files"]
    if not files:
        raise RuntimeError("empty source manifest")
    for relative, expected in files.items():
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise RuntimeError(f"nonrelative source-manifest name: {relative}")
        if sha256(root / path) != expected:
            raise RuntimeError(f"qualified source changed: {relative}")
    return len(files)


def helper_identity(directory):
    manifest_path = directory / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    binary = directory / "ariadne-bap-core"
    digest = sha256(binary)
    if manifest.get("helper_sha256") != digest:
        raise RuntimeError("native helper does not match its build manifest")
    return {"path": str(binary), "sha256": digest,
            "manifest_sha256": sha256(manifest_path), "manifest": manifest}


def isolate_build(root):
    target = root / "target"
    selected = target / "loop-aware-replay-build"
    selected.mkdir(parents=True, exist_ok=True)
    fixed = target / "bap-core-replay"
    if fixed.is_symlink():
        if fixed.resolve() != selected.resolve():
            raise RuntimeError(f"existing replay alias points elsewhere: {fixed}")
    elif fixed.exists():
        raise RuntimeError(f"refusing to replace existing build directory: {fixed}")
    else:
        fixed.symlink_to("loop-aware-replay-build", target_is_directory=True)
    for name in ("loop-aware-build", "loop-aware-mutations-build"):
        other = target / name
        if other.exists() and other.resolve() == selected.resolve():
            raise RuntimeError(f"replay and {name} resolve to the same build directory")
    return {"tool_fixed_path": str(fixed), "selected_path": str(selected),
            "physical_path": str(selected.resolve())}


def selected_toolchain(root, path):
    record = json.loads(path.read_text())
    framework = Path(record["root"])
    if sha256(root / "mbt/mirrors-isfinite.patch") != record["patchSha256"]:
        raise RuntimeError("current compatibility patch differs from pinned toolchain")
    verified = {}
    for name, expected in record["binaries"].items():
        binary = framework / ".lake/build/bin" / name
        actual = sha256(binary)
        if actual != expected:
            raise RuntimeError(f"pinned framework binary changed: {name}")
        verified[name] = {"path": str(binary), "sha256": actual}
    for name in ("mirror", "model_interface_gen"):
        if name not in verified:
            raise RuntimeError(f"toolchain manifest omits required binary: {name}")
    return framework, {"record": record, "manifest_path": str(path),
                       "manifest_sha256": sha256(path), "verified": verified}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path,
                        default=Path("/home/nzsn/Repos/Ariadne-loop-aware-20261015"))
    parser.add_argument("--source-manifest", type=Path,
                        default=Path("/loop-work/source-manifest.json"))
    parser.add_argument("--toolchain-manifest", type=Path,
                        default=Path("/home/nzsn/Repos/Ariadne/target/mbt-work/toolchain.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not Path("/loop-work/source-manifest.json").is_file():
        raise SystemExit("Run inside the authorized remote loop-aware WSL task wrapper.")
    root = args.root.resolve()
    if not (root / "tools/check_bap_core_replay.py").is_file():
        raise SystemExit("Task checkout or existing replay tool is unavailable.")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or Path("/loop-work/evidence") / ("generated-replay-" + stamp)
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    print("Generated replay artifacts:", output, flush=True)
    started = time.monotonic()
    receipt = {"schema": "ariadne.loop-target-closure.core-stateflow-replay/v1",
               "passed": False, "source_manifest": str(args.source_manifest),
               "scope": "source-bound core/stateflow regression; not loop-proof or dump acceptance"}
    exit_code = 1
    try:
        manifest = json.loads(args.source_manifest.read_text())
        receipt["source_files"] = verify_sources(root, manifest)
        save(output / "source-manifest.json", manifest)
        receipt["source_manifest_sha256"] = sha256(args.source_manifest)
        receipt["driver_sha256"] = sha256(Path(__file__))
        helper_dir = root / "target/loop-aware-native"
        receipt["helper_before"] = helper_identity(helper_dir)
        receipt["build_isolation"] = isolate_build(root)
        framework, toolchain = selected_toolchain(root, args.toolchain_manifest)
        receipt["toolchain"] = toolchain
        env = {**os.environ, "CARGO_TARGET_DIR": str(root / "target/loop-aware-replay-build"),
               "CARGO_INCREMENTAL": "0", "CARGO_PROFILE_DEV_DEBUG": "0",
               "CARGO_BUILD_JOBS": "4", "MIRRORS_ROOT": str(framework),
               "ARIADNE_BAP_CORE_DIR": str(helper_dir), "TMPDIR": "/loop-work/tmp"}
        command = [sys.executable, "tools/check_bap_core_replay.py", "--helper-dir",
                   str(helper_dir), "--output", str(output / "campaign")]
        receipt["command"] = command
        receipt["environment"] = {key: env[key] for key in (
            "CARGO_TARGET_DIR", "CARGO_INCREMENTAL", "CARGO_PROFILE_DEV_DEBUG",
            "CARGO_BUILD_JOBS", "MIRRORS_ROOT", "ARIADNE_BAP_CORE_DIR", "TMPDIR")}
        save(output / "qualification.json", receipt)
        with (output / "replay.log").open("w") as log:
            result = subprocess.run(command, cwd=root, env=env, stdout=log,
                                    stderr=subprocess.STDOUT)
        receipt["tool_exit_code"] = result.returncode
        if result.returncode:
            raise RuntimeError("generated replay failed; see replay.log and campaign logs")
        campaign = json.loads((output / "campaign/result.json").read_text())
        if campaign.get("passed") is not True:
            raise RuntimeError("replay result did not declare a passing campaign")
        expected = {"core-good": ("passed", 168),
                    "machine-state-good": ("passed", 162),
                    "core-wrong-digest": ("rejected", 0),
                    "machine-state-wrong-digest": ("rejected", 0)}
        if set(campaign["reports"]) != set(expected):
            raise RuntimeError("replay family/control domain differs from the frozen campaign")
        for family, (status, count) in expected.items():
            row = campaign["reports"][family]
            if (row.get("analysisBackend") != "bap" or row.get("gatePassed") is not True
                    or row.get("status") != status or row.get("observationsDispatched") != count):
                raise RuntimeError(f"unexpected generated replay result: {family}")
        receipt["helper_after"] = helper_identity(helper_dir)
        if receipt["helper_after"] != receipt["helper_before"]:
            raise RuntimeError("helper or manifest changed during replay")
        if campaign["helperManifest"] != receipt["helper_after"]["manifest"]:
            raise RuntimeError("campaign helper identity differs from selected helper")
        verify_sources(root, manifest)
        if sha256(args.source_manifest) != receipt["source_manifest_sha256"]:
            raise RuntimeError("source-manifest bytes changed during replay")
        receipt["observations"] = 330
        receipt["wrong_digest_observations"] = 0
        receipt["reports"] = campaign["reports"]
        receipt["campaign_result_sha256"] = sha256(output / "campaign/result.json")
        receipt["passed"] = True
        exit_code = 0
    except Exception as error:
        receipt["failure"] = str(error)
        (output / "driver-error.log").write_text(traceback.format_exc())
        print("Replay failed:", error, flush=True)
    finally:
        receipt["seconds"] = time.monotonic() - started
        receipt["exit_code"] = exit_code
        save(output / "qualification.json", receipt)
        (output / "exit-code.txt").write_text(str(exit_code) + "\n")
    if (output / "replay.log").exists():
        print((output / "replay.log").read_text(errors="replace")[-7000:], flush=True)
    print("REPLAY PASS" if exit_code == 0 else "REPLAY FAIL", flush=True)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
