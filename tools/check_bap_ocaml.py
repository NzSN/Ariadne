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
import tarfile
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
                 "tools/check_bap_core_a0.py", "docs/Ariadne/bap-analysis-core-design.md"]:
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
        code, output = run("a0-contract-probe", ["python3", "tools/check_bap_core_a0.py", "--stage1-record", stage1_path])
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
    evidence = ROOT / "evidence/Ariadne"
    destination = evidence / "bap-ocaml-qualification.json"
    shutil.copyfile(work / "report.json", destination)
    artifacts = {str(p.relative_to(work)): p for p in work.iterdir() if p.is_file()}
    for name in before:
        if (name.startswith("native/bap-core/") or name.startswith("src/bap/core_")
                or name.startswith("Specs/") or name in ("tests/bap/core_bootstrap.rs",
                    "tools/check_bap_ocaml.py", "tools/check_bap_ocaml_mutations.py",
                    "tools/bap_ocaml_controls.py", "Cargo.toml", "Cargo.lock")):
            artifacts["sources/" + name] = ROOT / name
    for directory, label in [(mutation_path.parent, "mutations"), (stage1_path.parent, "stage1")]:
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix in (".log", ".diff", ".json") and not any(
                    part in path.parts for part in ("rust-sut", "rust-build")):
                artifacts[label + "/" + str(path.relative_to(directory))] = path
    # Preserve nested reports/traces, not just their original temporary paths.
    pending = [stage1_path.parent]
    visited = set()
    while pending:
        directory = pending.pop()
        if directory in visited:
            continue
        visited.add(directory)
        for path in directory.rglob("*"):
            relative = path.relative_to(directory)
            if not path.is_file() or set(relative.parts) & {"sut", "rust-sut", "rust-build", "target", ".git"}:
                continue
            if path.suffix in (".log", ".json", ".csv", ".txt", ".diff", ".itf", ".tla", ".cfg"):
                artifacts["regression-artifacts/" + directory.name + "/" + str(relative)] = path
            if path.suffix == ".log":
                for line in path.read_text(errors="replace").splitlines():
                    if line.startswith("Report: /tmp/ariadne-"):
                        report_path = Path(line[8:])
                        if report_path.is_file():
                            pending.append(report_path.parent)
    for path in [ROOT / "target/bap-core-sdk/sdk-manifest.json", ROOT / "target/bap-core-sdk/installed.export",
                 ROOT / "target/bap-core-sdk/repository-snapshot.tar.gz", ROOT / "tmp/bap-setup/bap-source.tar.gz"]:
        artifacts["locked-inputs/" + path.name] = path
    for directory in ("bap-core-native", "bap-core-native-clean", "bap-core-sdk-smoke"):
        for name in ("ariadne-bap-core", "sdk-smoke", "manifest.json", "report.json", "build.log", "run.log", "ldd.log"):
            path = ROOT / "target" / directory / name
            if path.is_file():
                artifacts[directory + "/" + name] = path
    for path in (ROOT / "target/bap-core-sdk/logs").glob("*.log"):
        artifacts["sdk-logs/" + path.name] = path
    archive = evidence / "bap-ocaml-evidence.tar.gz"
    inventory = {name: {"sha256": sha(path), "bytes": path.stat().st_size,
                        "originalPath": str(path)} for name, path in sorted(artifacts.items())}
    with tarfile.open(archive, "w:gz") as tar:
        for name, path in sorted(artifacts.items()):
            tar.add(path, arcname=name, recursive=False)
    with tarfile.open(archive) as tar:
        if set(tar.getnames()) != set(inventory):
            raise RuntimeError("archive entry mismatch")
        for name, row in inventory.items():
            if hashlib.sha256(tar.extractfile(name).read()).hexdigest() != row["sha256"]:
                raise RuntimeError("archive hash mismatch: " + name)
    manifest = {"archiveSha256": sha(archive), "entries": inventory, "verified": True}
    (evidence / "bap-ocaml-evidence-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Report:", work / "report.json", flush=True)
    raise SystemExit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
