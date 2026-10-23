#!/usr/bin/env python3
"""Compare fresh source-built REP LODS BIL to independent element equations."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import subprocess

from check_bap_repeated_string_oracle import LoopEvaluator, expected_recipe, scenario_recipe
from i5a_native_contract import strict_json

ROOT = Path(__file__).resolve().parents[1]
CODES = {"f3ac": 8, "66f3ad": 16, "f3ad": 32, "f348ad": 64}
INPUTS = ((0, 1, 2, 4, 8), (0, 1), (0, 1),
          ("disjoint", "overlap-forward", "overlap-backward", "same-address", "source-wrap", "destination-wrap"),
          ("equal", "first-diff", "late-diff", "first-equal", "late-equal"),
          (0xA51234879BCD0123, 0x7FFFFFFFFFFFFF80, 0x8000800080008080))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_bil(code, bil, parameters):
    case = dict(family="lods", elementBits=CODES[code], repeatCondition="count")
    registers, memory = scenario_recipe(case, *parameters)
    wanted, wanted_memory = expected_recipe(case, registers, memory)
    evaluator = LoopEvaluator(registers, memory.copy())
    evaluator.statements(bil)
    for name, value in wanted.items():
        require(evaluator.values[name].n == value,
                f"{code} {parameters}: {name} got {evaluator.values[name].n}, expected {value}")
    require(evaluator.memory == wanted_memory, f"{code} {parameters}: complete memory differs")


def verify_capi_casts(code, bil):
    # Pinned bap.h: LOW=0,HIGH=1,SIGNED=2,UNSIGNED=3. Numeric evaluation
    # alone cannot distinguish LOW from UNSIGNED on a positive narrow value.
    casts = []

    def visit(value):
        if isinstance(value, dict):
            if value.get("kind") == "cast":
                casts.append((value.get("op"), value.get("width")))
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(bil)
    require(casts == ([(3, 64)] if code == "f3ad" else []), "LODS C API cast constructor mapping")


def run(runtime, manifest_sha256, executable_sha256, lifts_output=None):
    runtime = Path(runtime).resolve()
    manifest_path = runtime / "manifest.json"
    executable = runtime / "lods-lift"
    require(sha(manifest_path) == manifest_sha256, "explicit LODS manifest pin differs")
    require(sha(executable) == executable_sha256, "explicit LODS executable pin differs")
    manifest = strict_json(manifest_path.read_text())
    require(manifest["schema"] == "ariadne.bap-source-lods-build/v1"
            and manifest["profiles"] == ["bap-bit-provenance-v14"]
            and manifest["runtime_role"] == "lods-source"
            and manifest["executable"] == "lods-lift"
            and manifest["executable_sha256"] == executable_sha256
            and manifest["cases"] == sorted(CODES)
            and manifest["max_response_bytes"] == 65536, "LODS manifest contract")
    encoded = json.dumps(manifest["binding"], sort_keys=True, separators=(",", ":")).encode()
    require(hashlib.sha256(encoded).hexdigest() == manifest["build_id"], "LODS build binding identity")
    rows, lifts = [], []
    for target in ("windows-amd64", "linux-amd64"):
        for code in CODES:
            snapshot, va = "d" * 64, "0xffff800000401000"
            process = subprocess.run([str(executable), target, snapshot, va, code],
                                     capture_output=True, text=True, timeout=60)
            require(process.returncode == 0, "fresh LODS producer failed: " + process.stderr)
            require(len(process.stdout.encode()) <= 65536, "LODS response budget")
            row = strict_json(process.stdout)
            require(set(row) == {"schema", "build_id", "target", "snapshot", "va", "bytes", "length", "bil"}
                    and row["schema"] == "ariadne.bap-source-lods/v1" and row["build_id"] == manifest["build_id"]
                    and row["target"] == target and row["snapshot"] == snapshot and row["va"] == va
                    and row["bytes"] == code and type(row["length"]) is int
                    and row["length"] == len(code) // 2 and bool(row["bil"]), "fresh LODS response binding")
            verify_capi_casts(code, row["bil"])
            comparisons = 0
            for parameters in itertools.product(*INPUTS):
                check_bil(code, row["bil"], parameters)
                comparisons += 1
            rows.append(dict(target=target, bytes=code, comparisons=comparisons))
            lifts.append(row)
    # Runtime envelope refuses neighbor bytes before any AST is returned.
    refused = 0
    for code in ("ac", "ad", "66ad", "48ad", "f2ac", "f2ad", "f366ad", "67f3ad", "64f3ac",
                 "f349ad", "f3ac90", "f3f3ad", "F3AC", "f3", ""):
        process = subprocess.run([str(executable), "windows-amd64", "d" * 64, "0xffff800000401000", code],
                                 capture_output=True, text=True, timeout=60)
        require(process.returncode != 0 and not process.stdout, "out-of-scope LODS bytes accepted")
        refused += 1
    if lifts_output is not None:
        lifts_output = Path(lifts_output)
        lifts_output.parent.mkdir(parents=True, exist_ok=True)
        lifts_output.write_text(json.dumps(lifts, indent=2) + "\n")
    sources = [Path(__file__), ROOT / "tools/check_bap_repeated_string_oracle.py",
               ROOT / "tools/check_bap_bit_count_oracle.py", ROOT / "tools/check_bap_admission_oracle.py"]
    return dict(schema="ariadne.bap-lods-oracle/v1", passed=True, forms=4,
                comparisons=sum(row["comparisons"] for row in rows), rows=rows, refusedRuntimeNeighbors=refused,
                runtimeManifestSha256=manifest_sha256, runtimeExecutableSha256=executable_sha256,
                typedBilSha256=hashlib.sha256(json.dumps(lifts, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                oracleSources={str(path.relative_to(ROOT)): sha(path) for path in sources},
                scope="Four exact default-address REP LODS forms on both target labels; finite normal completion, zero counts, both directions, partial/zero/full accumulator writes, pointer wrap, all supplied GPR/flags and memory. No hardware exception, partial fault, restart, IO or full ISA qualification.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--executable-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lifts-output", type=Path)
    args = parser.parse_args()
    report = run(args.runtime, args.manifest_sha256, args.executable_sha256, args.lifts_output)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": True, "comparisons": report["comparisons"], "forms": report["forms"]}))


if __name__ == "__main__":
    main()
