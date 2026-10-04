#!/usr/bin/env python3
"""Qualify A0 contracts and runtime facilities, never the Stage 2 analyzer."""
import hashlib
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone

import check_bap_semantics as stage1

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sources():
    names = ["tools/check_bap_core_a0.py", "tools/bap_core_contract.py",
             "tools/test_bap_core_contract.py", "native/bap-core/probe.cpp",
             "native/bap-core/build-probe.sh", "native/bap/toolchain.lock.json",
             "native/bap/setup.py", "src/engine.rs", "src/model.rs", "src/machine_state.rs",
             "Specs/Ariadne.tla", "Specs/AriadneMachineState.tla", "Specs/AriadneMachineCommon.tla",
             "Specs/AriadneTypes.tla", "docs/Ariadne/bap-analysis-core-design.md"]
    return {name: sha(ROOT / name) for name in names}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage1-record", type=Path,
                        default=ROOT / "evidence/Ariadne/bap-unlimited-validation.json")
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix="ariadne-bap-core-a0-"))
    before = sources()
    prerequisite_path = args.stage1_record.resolve()
    prerequisite = json.loads(prerequisite_path.read_text())
    if not (prerequisite["passed"] and prerequisite["sourcesStable"]
            and prerequisite["stage1ExitPassed"] and prerequisite["stage2PrerequisiteSatisfied"]
            and prerequisite["sourceHashes"] == stage1.sources()):
        raise SystemExit("Stage 1 prerequisite is absent or stale")
    stage1.validate_workload_bindings(prerequisite["records"]["workload"])
    runtime = ROOT / "tmp/bap-setup/stable"
    binary = ROOT / "target/bap-core-a0/ariadne-bap-core-probe"
    env = {**os.environ, "BAP_RUNTIME_ROOT": str(runtime),
           "LD_LIBRARY_PATH": f"{runtime}/usr/local/lib:{runtime}/usr/lib/x86_64-linux-gnu",
           "XDG_STATE_HOME": str(work / "state"), "XDG_CACHE_HOME": str(work / "cache")}
    gates = []

    def run(name, command):
        result = subprocess.run([str(arg) for arg in command], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=120)
        (work / f"{name}.stdout").write_text(result.stdout)
        (work / f"{name}.stderr").write_text(result.stderr)
        gates.append({"gate": name, "command": [str(arg) for arg in command], "exitCode": result.returncode})
        if result.returncode:
            raise RuntimeError(f"{name} failed; see {work}")
        return result.stdout

    run("contract-tests", ["python3", "-m", "unittest", "discover", "-s", "tools", "-p", "test_bap_core_contract.py"])
    run("native-build", ["bash", "native/bap-core/build-probe.sh", binary])
    probes = [json.loads(run(f"native-probe-{index}", [binary, runtime / "usr/local/lib/bap"])) for index in range(2)]
    if probes[0] != probes[1] or not all(p["passed"] for p in probes):
        raise RuntimeError("fresh-process capability observations differ")
    if probes[0]["parallelEdgeCount"] != 1 or probes[0]["graphNodeCounts"] != [0, 1, 2]:
        raise RuntimeError("pinned graph capability changed; review the contract")
    header = runtime / "usr/local/include/bap.h"
    header_text = header.read_text()
    capabilities = {name: name + "(" in header_text for name in
                    ("bap_blk_create", "bap_term_set_address", "bap_tidgraph_edge_insert",
                     "bap_project_empty", "bap_project_input_create", "bap_sub_builder_result")}
    sdk = {"runtimeCmiFiles": len(list(runtime.rglob("*.cmi"))),
           "runtimeCmxaFiles": len(list(runtime.rglob("*.cmxa"))),
           "ocamlCompiler": shutil.which("ocamlopt"),
           "compatibleCustomPassBuildQualified": False}
    record = dict(schema="ariadne.bap-core-a0/v1", recordedUtc=datetime.now(timezone.utc).isoformat(),
                  passed=before == sources(), sourcesStable=before == sources(), sourceHashes=before,
                  stage2Started=True, stage2Qualified=False, a0ContractChecksPassed=True,
                  nativeCapabilitiesPassed=True, a0ExitPassed=False,
                  stage1Prerequisite={"path": str(prerequisite_path),
                                      "sha256": sha(prerequisite_path), "completeSourceInventoryMatched": True,
                                      "workloadToolsMatched": True, "satisfied": True},
                  gates=gates, probes=probes, headerCapabilities=capabilities, sdk=sdk,
                  tools={"probe": sha(binary), "header": sha(header),
                         "bapLibrary": sha(runtime / "usr/local/lib/libbap.so.2.5.0"),
                         "compilerPath": shutil.which("g++"),
                         "compilerSha256": sha(shutil.which("g++"))},
                  implementedAlgorithms=[],
                  missing=["Compatible isolated OCaml SDK and actual custom-pass initialize/observe transport qualification.",
                           "A1 recovery, A2 definitions/slicing, A3 stateflow, A4 replay, A5 mutation/product integration and A6 adoption."],
                  scope="A0 contract and pinned native term/graph facilities only. No native analysis model replay or migrated solver is claimed.")
    (work / "report.json").write_text(json.dumps(record, indent=2) + "\n")
    print("Report:", work / "report.json")
    if not record["passed"]:
        raise SystemExit("A0 sources changed during checks")


if __name__ == "__main__":
    main()
