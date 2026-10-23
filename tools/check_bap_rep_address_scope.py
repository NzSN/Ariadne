#!/usr/bin/env python3
"""Assess raw pinned BAP/LLVM address-override REP lifts without admitting them.

This executable assessment retains fresh typed ASTs and concrete counterexamples
under ignored target/. It changes no producer, profile, dependency lock or SDK.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess

from amd64_rep_recipes import RECIPES, load_recipes
from check_bap_admission_oracle import Value
from check_bap_bit_count_oracle import BANKS, FLAGS
from check_bap_repeated_string_oracle import LoopEvaluator, expected_recipe
from i5a_native_contract import strict_json

ROOT = Path(__file__).resolve().parents[1]
MASK32 = (1 << 32) - 1
MASK64 = (1 << 64) - 1


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def variants(case):
    code = case["bytes"]
    repeat = "f2" if "f2" in code else "f3"
    return {"default-address-baseline": code,
            "address-67": "67" + code,
            "lock-67": "f067" + code,
            "segment-fs-67": "6467" + code,
            "duplicate-67": "6767" + code,
            "duplicate-repeat-67": "67" + repeat + code,
            "reordered-67": code.replace(repeat, repeat + "67", 1),
            "extra-rex-67": "6740" + code,
            "trailing-instruction-67": "67" + code + "90"}


def fresh_bap(cases, target, helper, runtime, snapshot):
    request = f"ARIADNE-BAP-LIFT 1 {target} {snapshot}\nbatch 0 {len(cases)}\n"
    request += "".join(f'0x{0x401000 + index * 32:016x} {case["bytes"]}\n'
                       for index, case in enumerate(cases))
    env = {**os.environ, "LD_LIBRARY_PATH": str(runtime / "usr/local/lib") + ":" + str(runtime / "usr/lib/x86_64-linux-gnu"),
           "XDG_STATE_HOME": str(runtime / "state"), "XDG_CACHE_HOME": str(runtime / "cache")}
    result = subprocess.run([str(helper), str(runtime / "usr/local/lib/bap")], input=request,
                            capture_output=True, text=True, env=env, timeout=120)
    require(result.returncode == 0, "fresh BAP scope probe failed: " + result.stderr)
    rows = [strict_json(line) for line in result.stdout.splitlines()]
    require(len(rows) == len(cases) + 2, "BAP scope probe frame count")
    require(rows[0] == dict(schema="ariadne.bap-ready/v1", snapshot=snapshot, target=target,
                            version="2.5.0-alpha", lifter="legacy"), "BAP ready identity")
    require(rows[-1] == {"schema": "ariadne.bap-batch/v1", "batch": 0, "count": len(cases)}, "BAP batch identity")
    for index, (case, row) in enumerate(zip(cases, rows[1:-1])):
        require(row["schema"] == "ariadne.bap-site/v1" and row["snapshot"] == snapshot
                and row["batch"] == 0 and row["va"] == f"0x{0x401000 + index * 32:016x}"
                and case["bytes"].startswith(row["bytes"])
                and row["length"] * 2 == len(row["bytes"]), "BAP response byte/extent identity")
    return rows[1:-1]


def fresh_llvm(cases, target, helper, library):
    argument = "--protocol=2-checked" + ("-linux" if target == "linux-amd64" else "")
    request = "".join(f'{0x401000 + index * 32} {case["bytes"]}\n' for index, case in enumerate(cases))
    result = subprocess.run([str(helper), argument], input=request, capture_output=True, text=True,
                            env={**os.environ, "LD_LIBRARY_PATH": str(library.parent)}, timeout=120)
    require(result.returncode == 0, "fresh LLVM scope probe failed: " + result.stderr)
    lines = result.stdout.splitlines()
    header = "ariadne-llvm-mc 20.1.2 protocol 2" + (" target x86_64-unknown-linux-gnu" if target == "linux-amd64" else "")
    require(len(lines) == len(cases) + 1 and lines[0] == header, "LLVM ready/row identity")
    rows = []
    for index, line in enumerate(lines[1:]):
        words = line.split()
        address, status, length, control, destination = words[-5:]
        require(words[0] == "v2" and int(address) == 0x401000 + index * 32, "LLVM address identity")
        rows.append(dict(opcode=words[1], status=status, length=int(length), control=control,
                         destination=destination, record=line))
    return rows


def registers(count=1, direction=0):
    state = {name: Value(0xA51234879BCD0123, 64) for name in BANKS}
    state.update({name: Value(1, 1) for name in FLAGS})
    state.update(RCX=Value(count, 64), RSI=Value(0x7000, 64), RDI=Value(0x8000, 64), DF=Value(direction, 1))
    return state


def loop_entry(bil, state):
    evaluator = LoopEvaluator(state, {})
    for statement in bil:
        if statement["kind"] == "while":
            return evaluator.expr(statement["condition"]).n
        evaluator.statements([statement])
    raise ValueError("nonempty repeated-string lift has no loop")


def memory_for(state, size):
    memory = {0x1234: 0x45}
    for name in ("RSI", "RDI"):
        for address in (state[name].n, state[name].n & MASK32):
            for lane in range(size):
                memory[(address + lane) & MASK64] = ((address >> 32) + lane * 19 + 0x61) & 255
    return memory


def expected32(case, state, memory):
    # AMD normal-completion premise. At low count zero, AMD Ryzen 7950X
    # preserves upper register lanes; Intel Core 5 220H differs. This equation
    # must not be advertised as a vendor-independent x86 zero-count contract.
    if state["RCX"].n & MASK32 == 0:
        return {name: value.n for name, value in state.items()}, memory.copy()
    # Normal-completion test states use exactly one low-32 count. Effective
    # addresses truncate before the element access; byte lanes stay contiguous.
    narrowed = state.copy()
    narrowed["RCX"] = Value(state["RCX"].n & MASK32, 64)
    for name in ("RSI", "RDI"):
        narrowed[name] = Value(state[name].n & MASK32, 64)
    result, result_memory = expected_recipe(case, narrowed, memory)
    for name, used in (("RSI", case["family"] in {"movs", "lods", "cmps"}),
                      ("RDI", case["family"] in {"movs", "stos", "cmps", "scas"})):
        result[name] = result[name] & MASK32 if used else state[name].n
    return result, result_memory


def counterexamples(case, bil):
    zero_low = registers(1 << 32)
    actual_condition = loop_entry(bil, zero_low)
    findings = [dict(scenario="high-count-low32-zero", expectedLoopEntry=False,
                     actualLoopEntry=bool(actual_condition), mismatch=bool(actual_condition))]
    size = case["elementBits"] // 8
    for scenario in ("high-index-bits", "forward-index-wrap", "backward-index-wrap"):
        state = registers(direction=int(scenario == "backward-index-wrap"))
        if scenario == "high-index-bits":
            state["RSI"], state["RDI"] = Value(0x123400007000, 64), Value(0x567800008000, 64)
        else:
            pointer = 0 if state["DF"].n else (1 << 32) - size
            state["RSI"], state["RDI"] = Value(pointer, 64), Value(pointer, 64)
        memory = memory_for(state, size)
        wanted, wanted_memory = expected32(case, state, memory)
        actual = LoopEvaluator(state, memory.copy())
        actual.statements(bil)
        differences = {name: dict(expected=value, actual=actual.values[name].n)
                       for name, value in wanted.items() if actual.values[name].n != value}
        memory_differs = actual.memory != wanted_memory
        findings.append(dict(scenario=scenario, mismatch=bool(differences) or memory_differs,
                             differingRegisters=differences, memoryDiffers=memory_differs))
    return findings


def architectural_vars(value):
    output = set()
    if isinstance(value, dict):
        if set(value) == {"name", "index", "virtual", "width", "type"} and not value["virtual"]:
            output.add((value["name"], value["width"], value["type"]))
        for child in value.values():
            output |= architectural_vars(child)
    elif isinstance(value, list):
        for child in value:
            output |= architectural_vars(child)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bap-helper", type=Path, default=ROOT / "target/ariadne-bap-lift")
    parser.add_argument("--bap-runtime", type=Path, default=ROOT / "tmp/bap-setup/stable")
    parser.add_argument("--llvm-helper", type=Path, default=ROOT / "target/ariadne-llvm-mc")
    parser.add_argument("--llvm-library", type=Path, default=ROOT / "target/resume-llvm20/usr/lib/x86_64-linux-gnu/libLLVM.so.20.1")
    args = parser.parse_args()
    output = args.output.resolve()
    require(output.is_relative_to(ROOT / "target") and output != ROOT / "target", "output must be ignored target child")
    output.mkdir(parents=True, exist_ok=False)
    recipes = load_recipes()["cases"]
    cases = [dict(recipe=case["name"], variant=name, bytes=code)
             for case in recipes for name, code in variants(case).items()]
    require(len(cases) == 252, "finite scope corpus size")
    runtime = args.bap_runtime.resolve()
    lock_path = ROOT / "native/bap/toolchain.lock.json"
    lock = strict_json(lock_path.read_text())
    for relative, digest in lock["files"].items():
        require(sha(runtime / relative) == digest, "BAP runtime pin differs: " + relative)
    snapshot = hashlib.sha256(json.dumps(cases, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    rows, summaries = [], []
    for target in ("windows-amd64", "linux-amd64"):
        bap = fresh_bap(cases, target, args.bap_helper.resolve(), runtime, snapshot)
        llvm = fresh_llvm(cases, target, args.llvm_helper.resolve(), args.llvm_library.resolve())
        for case, lifted, decoded in zip(cases, bap, llvm):
            row = dict(case, target=target, bap=lifted, llvm=decoded,
                       exactBothExtents=lifted["length"] == decoded["length"] == len(case["bytes"]) // 2)
            if case["variant"] == "address-67":
                recipe = next(recipe for recipe in recipes if recipe["name"] == case["recipe"])
                row["architecturalVariables"] = sorted(architectural_vars(lifted["bil"]))
                row["counterexamples"] = counterexamples(recipe, lifted["bil"]) if lifted["bil"] else []
                row["admissible"] = False
                summaries.append(dict(recipe=case["recipe"], target=target, bytes=case["bytes"],
                                      nonemptyBil=bool(lifted["bil"]), exactBothExtents=row["exactBothExtents"],
                                      counterexamples=len([item for item in row["counterexamples"] if item["mismatch"]])))
            rows.append(row)
    sources = [Path(__file__), RECIPES, ROOT / "tools/amd64_rep_recipes.py",
               ROOT / "tools/check_bap_repeated_string_oracle.py", ROOT / "tools/check_bap_bit_count_oracle.py",
               ROOT / "tools/check_bap_admission_oracle.py", ROOT / "native/bap/lift.cpp",
               ROOT / "native/llvm_mc/decode.cpp", ROOT / "src/bap/repeated_strings.rs",
               ROOT / "src/bap/lods_source.rs", ROOT / "native/bap/source-coverage/lods.patch"]
    report = dict(schema="ariadne.bap-rep-address-assessment/v1", assessmentCompleted=True,
                  implementationComplete=False, fullAcceptance=False, profilesBroadened=False,
                  scope="28 selected memory REP recipes with 67 plus seven hostile/scope-neighbor families and default baselines; both target labels. Expected equations use AMD normal-completion semantics, including zero-count upper-lane preservation, not Intel zero-count behavior. Raw BAP AST and independent LLVM decode are assessment evidence, not admitted semantics.",
                  corpusSha256=snapshot, rows=rows, addressOverrideSummary=summaries,
                  variantCounts=dict(Counter(row["variant"] for row in rows)),
                  toolHashes={"bapHelper": sha(args.bap_helper), "bapToolchainLock": sha(lock_path),
                              "llvmHelper": sha(args.llvm_helper), "llvmLibrary": sha(args.llvm_library)},
                  runtimeFiles=lock["files"], sourceHashes={str(path.relative_to(ROOT)): sha(path) for path in sources},
                  nextRequiredWork=["Address-size-aware upstream BAP loop count and implicit pointer lifter support, including zero count and 32-bit wrap.",
                                    "A separately pinned producer with actual nonempty LODS address-override BIL.",
                                    "Exact-prefix recipe admission, independent numeric/source mutation controls and host/native consumer replay before any new profile."],
                  manualBasis={"source": "amd-24594-r3.38", "sha256": "e18bd39ad0ca19d2eb9b9ea25c2635144c5ab368e5d6fbdc7a08345515ea1aee",
                               "section": "1.2.3 Address-Size Override Prefix, Table 1-4; 1.2.6 Repeat Prefixes", "pdfPages": [51, 52, 54]})
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(dict(assessmentCompleted=True, implementationComplete=False, rawObservations=len(rows),
                         addressOverrideForms=len(summaries), concreteMismatches=sum(row["counterexamples"] for row in summaries))))


if __name__ == "__main__":
    main()
