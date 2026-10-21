#!/usr/bin/env python3
"""Run and retain OQ0-OQ6 for the bounded OCaml recovery foundation."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import check_bap_semantics as stage1
import check_bap_ocaml_mutations as mutations
from bap_ocaml_controls import native_controls, sdk_controls

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sources():
    result = stage1.sources()
    result.update(mutations.sources())
    for name in ["tools/check_bap_ocaml.py", "tools/bap_ocaml_controls.py",
                 "tools/check_bap_core_a0.py",
                 "docs/Ariadne/bap-analysis-core-design.md"]:
        result[name] = sha(ROOT / name)
    return dict(sorted(result.items()))


def read_report(output):
    paths = [line[8:] for line in output.splitlines() if line.startswith("Report: ")]
    if not paths:
        raise RuntimeError("missing nested report")
    path = Path(paths[-1])
    return path, json.loads(path.read_text())


def tool_identities():
    tools = {}
    for name in ("cargo", "rustc", "python3"):
        path = shutil.which(name)
        if name in ("cargo", "rustc"):
            path = subprocess.check_output(["rustup", "which", name], text=True).strip()
        if not path:
            raise RuntimeError("missing qualification tool: " + name)
        tools[name] = {"path": str(Path(path).resolve()), "sha256": sha(path)}
    tools["rustc"]["version"] = subprocess.check_output(["rustc", "-vV"], text=True)
    return tools


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage1-record", type=Path)
    parser.add_argument("--mutation-record", type=Path)
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix="ariadne-bap-ocaml-"))
    before = sources()
    tools_before = tool_identities()
    gates, nested = [], {}
    print("OCaml qualification artifacts:", work, flush=True)

    def run(name, command, timeout=1800, env=None):
        print("Gate:", name, flush=True)
        start = time.monotonic()
        result = subprocess.run([str(x) for x in command], cwd=ROOT, text=True,
                                capture_output=True, timeout=timeout, env=env)
        output = result.stdout + result.stderr
        (work / (name + ".log")).write_text(output)
        gates.append({"gate": name, "command": [str(x) for x in command],
                      "exitCode": result.returncode, "seconds": time.monotonic() - start})
        return result.returncode, output

    baseline = ROOT / "tmp/bap-ocaml-qualification/baseline.json"
    baseline_record = json.loads(baseline.read_text())
    baseline_a0 = ROOT / "tmp/bap-ocaml-qualification/refreshed-a0.json"
    if (not baseline_record["stage1PrerequisiteVerified"]
            or sha(ROOT / baseline_record["stage1Record"]) != baseline_record["stage1RecordSha256"]
            or sha(baseline_a0) != baseline_record["refreshedA0RecordSha256"]):
        raise RuntimeError("OQ0 entry evidence mismatch")
    shutil.copyfile(baseline, work / "entry-baseline.json")
    shutil.copyfile(baseline_a0, work / "entry-a0.json")
    sdk_ok, _ = run("sdk-inventory", ["python3", "native/bap-core/setup-sdk.py", "--check"])
    smoke_env = {**os.environ, "OCAMLPATH": "/unusable-ambient-ocaml",
                 "OCAMLLIB": "/unusable-ambient-ocaml", "CAML_LD_LIBRARY_PATH": "/unusable-ambient-ocaml"}
    smoke_ok, _ = run("sdk-smoke", ["python3", "native/bap-core/check-sdk.py"], env=smoke_env)
    if sdk_ok or smoke_ok:
        raise RuntimeError("SDK prerequisite failed; see " + str(work))
    nested["sdkIdentityControls"] = sdk_controls(work)
    builds = []
    for directory in ("bap-core-native", "bap-core-native-clean"):
        output = ROOT / "target" / directory
        if directory.endswith("-clean") and output.exists():
            shutil.rmtree(output)
        code, _ = run(directory, ["python3", "native/bap-core/build.py", "--output", output])
        if code:
            raise RuntimeError("helper build failed")
        builds.append(json.loads((output / "manifest.json").read_text()))
    nested["nativeControls"] = native_controls(work)
    code, _ = run("native-rust-transport", ["cargo", "test", "--offline", "--locked", "--test",
                    "bap_core_bootstrap", "--", "--ignored", "--nocapture"])
    if code:
        raise RuntimeError("native state/transport acceptance failed")
    if args.mutation_record:
        record = json.loads(args.mutation_record.read_text())
        if not record.get("passed") or not record.get("sourcesStable") or record.get("sourceHashes") != mutations.sources():
            raise RuntimeError("stale mutation record")
        mutation_path = args.mutation_record
    else:
        code, output = run("bootstrap-mutations", ["python3", "tools/check_bap_ocaml_mutations.py"])
        mutation_path, record = read_report(output)
        if code or not record["passed"]:
            raise RuntimeError("bootstrap mutations failed")
    nested["mutations"] = record
    for name, command in [
        ("root-format", ["cargo", "fmt", "--all", "--", "--check"]),
        ("package-format", ["cargo", "fmt", "--package", "ariadne-analysis", "--", "--check"]),
        ("root-tests", ["cargo", "test", "--offline", "--locked"]),
        ("core-only-tests", ["cargo", "test", "--offline", "--locked", "--no-default-features"]),
        ("root-clippy", ["cargo", "clippy", "--offline", "--locked", "--all-features", "--all-targets", "--", "-D", "warnings"]),
        ("rust-layout", ["python3", "tools/check_rust_layout.py"]),
        ("documentation", ["python3", "tools/check_doc_links.py"]),
    ]:
        run(name, command)
    if args.stage1_record:
        record = json.loads(args.stage1_record.read_text())
        if not record.get("sourcesStable") or record.get("sourceHashes") != stage1.sources():
            raise RuntimeError("stale Stage 1 record")
        stage1.validate_workload_bindings(record["records"]["workload"])
        stage1_path = args.stage1_record
        gates.append({"gate": "stage1-regressions", "exitCode": 0 if record.get("passed") else 1,
                      "retainedRecord": str(stage1_path), "sha256": sha(stage1_path),
                      "reuse": "complete source/tool inventories verified; failed gates remain failed"})
    else:
        code, output = run("stage1-regressions", ["python3", "tools/check_bap_semantics.py"], timeout=7200)
        stage1_path, record = read_report(output)
    nested["stage1"] = record
    if record.get("passed") and record.get("stage1ExitPassed"):
        code, output = run("a0-contract-probe", ["python3", "tools/check_bap_core_a0.py", "tools/run_output.py", "--stage1-record", stage1_path])
        if code:
            nested["a0Probe"] = {"passed": False, "reason": "current probe failed; see gate log"}
        else:
            _, nested["a0Probe"] = read_report(output)
    else:
        nested["a0Probe"] = {"passed": False, "unexercised": True,
                             "reason": "current full Stage 1 prerequisite failed; entry probe preserved separately"}
        gates.append({"gate": "a0-contract-probe", "exitCode": 1,
                      "blockedBy": "current Stage 1 prerequisite"})
    stable = before == sources() and tools_before == tool_identities()
    all_passed = stable and all(gate["exitCode"] == 0 for gate in gates)
    report = {"schema": "ariadne.bap-ocaml-qualification/v1", "recordedUtc": datetime.now(timezone.utc).isoformat(),
              "passed": all_passed, "sourcesStable": stable, "sourceHashes": before,
              "tools": tools_before,
              "sdkQualified": True, "helperBuildQualified": True,
              "nativeStateExchangeQualified": True, "transportLifecycleQualified": True,
              "bootstrapMutationChecksPassed": nested["mutations"]["passed"],
              "a0ExitPassed": all_passed, "stage2Qualified": False,
              "capabilities": builds[0]["handshake"]["operations"], "builds": builds,
              "binaryReproducible": builds[0]["helper_sha256"] == builds[1]["helper_sha256"],
              "gates": gates, "records": nested,
              "remaining": ["A1 complete recovery/phase boundary", "A2 definitions and slicing",
                            "A3 stateflow", "A4 generated replay", "A5 broad mutation/product integration", "A6 adoption"],
              "scope": "Normalized recovery Init and single Visit only; production analysis remains Rust."}
    (work / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Report:", work / "report.json", flush=True)
    raise SystemExit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
