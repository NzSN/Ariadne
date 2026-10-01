#!/usr/bin/env python3
"""Explicit Stage E witness/binding generation or read-only freshness checking."""

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from tools import ROOT, mirrors_tools, run, sha256, write_json  # noqa: E402
from generate import address_map, integer, model_set, record, string  # noqa: E402

MODELS = {"MachineStateReplay": "machine_state", "LLVMIRReplay": "llvm_ir"}
SPEC_FILES = ["AriadneTypes.tla", "AriadneMachineCommon.tla", "AriadneMachineState.tla",
              "AriadneMachineStateExample.tla", "AriadneLLVMIR.tla", "AriadneLLVMIRExample.tla"]


def sources():
    return [ROOT / "Specs" / name for name in SPEC_FILES] + [
        HERE / "prepare.py", ROOT / "mbt/tools.py", ROOT / "mbt/generate.py",
        *sorted((HERE / "model").glob("*.tla")),
        *sorted(HERE.glob("*.interface.json")),
    ]


def prepare_model(work):
    directory = work / "model"
    directory.mkdir(parents=True, exist_ok=True)
    for source in [ROOT / "Specs" / name for name in SPEC_FILES] + list((HERE / "model").glob("*.tla")):
        shutil.copyfile(source, directory / source.name)
    return directory


def project(trace):
    """Losslessly expose the integer-address state map as typed wire rows."""
    projected = deepcopy(trace)
    source_type = trace["#meta"]["varTypes"]["statesAt"]
    if "".join(source_type.split()) != "(Int->Set(Str))":
        raise ValueError(f"unexpected statesAt type: {source_type}")
    projected["#meta"]["varTypes"]["statesAt"] = "Set({ states: Set(Str), va: Int })"
    for state in projected["states"]:
        rows, seen = [], set()
        mapping = state["statesAt"]
        if not isinstance(mapping, dict) or set(mapping) != {"#map"}:
            raise ValueError("statesAt must be a strict ITF map")
        for pair in mapping["#map"]:
            if not isinstance(pair, list) or len(pair) != 2:
                raise ValueError("invalid map pair")
            key, value = pair
            if not isinstance(key, dict) or set(key) != {"#bigint"}:
                raise ValueError("address must be an ITF integer")
            address = key["#bigint"]
            if not isinstance(address, str) or not address.isdecimal() or str(int(address)) != address or address in seen:
                raise ValueError("noncanonical or duplicate address")
            seen.add(address)
            rows.append({"va": key, "states": value})
        state["statesAt"] = {"#set": rows}
    restored = deepcopy(projected)
    restored["#meta"]["varTypes"]["statesAt"] = source_type
    for state in restored["states"]:
        state["statesAt"] = {"#map": [[row["va"], row["states"]] for row in state["statesAt"]["#set"]]}
    if restored != trace:
        raise ValueError("state-map projection changed information")
    return projected


def convert_trace(raw, evidence, name):
    types = evidence["#meta"]["varTypes"]
    if set(raw["vars"]) != set(types):
        raise ValueError("TLC variables differ from Apalache type evidence")
    edges = lambda value: model_set(value, lambda row: record(row, ("src", "dst"), ("kind",)))
    str_edges = lambda value: model_set(value, lambda row: record(row, (), ("src", "dst", "kind")))
    converters = {key: string for key in ("phase", "action_taken", "snapshot_id", "artifact_id", "module_id", "function_id")}
    converters.update({
        "parameters": lambda value: record(value, (), ("fixture",)),
        "statesAt": lambda value: address_map(value, lambda states: model_set(states, string)),
        "structural_edges": edges, "feasible_edges": edges, "infeasible_edges": edges, "unknown_edges": edges,
        "not_reached": lambda value: model_set(value, integer),
        "terminals": lambda value: model_set(value, lambda row: record(row, ("site",), ("before", "after", "outcome"))),
        "obligations": lambda value: model_set(value, lambda row: record(row, ("site",) if name == "MachineStateReplay" else (), ("reason",) if name == "MachineStateReplay" else ("reason", "site"))),
        "slice": lambda value: model_set(value, string), "control_graph": str_edges,
        "call_graph": lambda value: model_set(value, lambda row: record(row, (), ("site", "callee", "kind"))),
        "dependency_preds": lambda value: {"#map": [[key, model_set(states, string)] for key, states in sorted(value.items())]},
    })
    states = []
    for expected, (index, state) in enumerate(raw["counterexample"]["state"], 1):
        if index != expected or set(state) != set(types):
            raise ValueError("invalid TLC state sequence")
        if state["parameters"] != {"fixture": name}:
            raise ValueError("unexpected replay parameters")
        states.append({"#meta": {"index": expected - 1}, **{key: converters[key](state[key]) for key in types}})
    if not states or states[0]["action_taken"] != "init" or states[-1]["phase"] != "done":
        raise ValueError("incomplete witness")
    return {"#meta": {"format": "ITF", "varTypes": types}, "vars": list(types), "params": [], "param_vars": [], "states": states}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    _, compiler, _ = mirrors_tools()
    work = HERE / ".work" / ("check" if args.check else "prepare")
    model_dir = prepare_model(work)
    manifest_path = HERE / "corpus/manifest.json"
    if args.check:
        manifest = json.loads(manifest_path.read_text())
        for relative, digest in manifest["oracleSources"].items():
            if sha256(ROOT / relative) != digest:
                raise RuntimeError(f"stale Stage E oracle source: {relative}; regenerate explicitly")
        for relative, digest in manifest["artifacts"].items():
            if sha256(HERE / relative) != digest:
                raise RuntimeError(f"changed Stage E artifact: {relative}")
    else:
        corpus = work / "corpus"
        corpus.mkdir(exist_ok=True)
        generated = work / "generated"
        artifacts, counts = {}, {}
        versions = {
            "apalache": run([os.environ.get("APALACHE_MC", "apalache-mc"), "version"]).stdout.strip(),
            "tlc": run([os.environ.get("TLC", "tlc"), "-help"], expected=(0, 1)).stdout.splitlines()[4:8],
        }
    for name, directory in MODELS.items():
        model = model_dir / f"{name}.tla"
        contract = HERE / f"{name}.interface.json"
        destination = HERE / "generated" / directory if args.check else generated / directory
        corpus_dir = HERE / "corpus" if args.check else corpus
        evidence = corpus_dir / f"{name}.types.json"
        lock = corpus_dir / f"{name}.lock.json"
        if not args.check:
            type_root = work / f"types-{name}"
            if type_root.exists():
                shutil.rmtree(type_root)
            run([os.environ.get("APALACHE_MC", "apalache-mc"), f"--out-dir={type_root}", "check",
                 "--init=Init", "--next=Next", "--inv=TypeWitness", "--length=0", "--no-deadlock", model],
                expected=(12,), log=work / f"{name}-types.log", timeout=180)
            witness = json.loads(sorted(type_root.rglob("violation*.itf.json"))[0].read_text())
            if len(witness["states"]) != 1 or witness["states"][0]["action_taken"] != "init":
                raise RuntimeError("type witness is not the expected initialization")
            write_json(corpus / f"{name}.raw-types.json", witness)
            write_json(evidence, project(witness) if name == "MachineStateReplay" else witness)
            cfg = model.with_suffix(".cfg")
            cfg.write_text("SPECIFICATION Spec\nINVARIANT Safety\nPROPERTY Terminates\nCHECK_DEADLOCK FALSE\n")
            tlc = os.environ.get("TLC", "tlc")
            result = run([tlc, "-workers", "1", "-noGenerateSpecTE", "-config", cfg, "-metadir", work / f"states-{name}", model], log=work / f"{name}-safety.log")
            if "Model checking completed. No error has been found." not in result.stdout:
                raise RuntimeError("TLC did not confirm safety/termination")
            cfg.write_text("INIT Init\nNEXT Next\nINVARIANTS Safety TraceComplete\nCHECK_DEADLOCK FALSE\n")
            raw_path = corpus / f"{name}.tlc.json"
            result = run([tlc, "-workers", "1", "-noGenerateSpecTE", "-config", cfg, "-metadir", work / f"witness-{name}", "-dumpTrace", "json", raw_path, model], expected=(12,), log=work / f"{name}-witness.log")
            if "Invariant TraceComplete is violated" not in result.stdout:
                raise RuntimeError("unexpected witness failure")
            trace = convert_trace(json.loads(raw_path.read_text()), witness, name)
            write_json(corpus / f"{name}.raw.json", trace)
            write_json(corpus / f"{name}.itf.json", project(trace) if name == "MachineStateReplay" else trace)
            counts[name] = len(trace["states"])
            run([compiler, "resolve", "--spec", model, "--contract", contract, "--evidence", evidence,
                 "--param-var", "parameters", "--lock", lock, "--diagnostics", "json"], log=work / f"{name}-resolve.log")
            run([compiler, "generate", "--lock", lock, "--target", "mirrorrust-v1", "--out", destination], log=work / f"{name}-generate.log")
        run([compiler, "check", "--spec", model, "--contract", contract, "--evidence", evidence,
             "--param-var", "parameters", "--lock", lock, "--target", "mirrorrust-v1", "--out", destination], log=work / f"{name}-check.log")
        run([compiler, "preflight", "--lock", lock, "--trace", corpus_dir / f"{name}.itf.json",
             "--require-all-actions", "--diagnostics", "json"], log=work / f"{name}-preflight.log")
        print(f"{name}: {'freshness checked' if args.check else 'witness and binding generated'}", flush=True)
    if not args.check:
        for base, prefix in [(corpus, "corpus"), (generated, "generated")]:
            for artifact in sorted(base.rglob("*")):
                if artifact.is_file() and artifact.name != "manifest.json":
                    relative = Path(prefix) / artifact.relative_to(base)
                    artifacts[str(relative)] = sha256(artifact)
        write_json(corpus / "manifest.json", {
            "schema": "ariadne.stage-e-mirrorrust-corpus/v1",
            "oracleSources": {str(path.relative_to(ROOT)): sha256(path) for path in sources()},
            "artifacts": artifacts, "traceStates": counts,
            "generation": {**versions, "compilerSha256": sha256(compiler), "scope": "two existing formal fixtures; no Rust SUT executed during generation"},
        })
        shutil.copytree(corpus, HERE / "corpus", dirs_exist_ok=True)
        shutil.copytree(generated, HERE / "generated", dirs_exist_ok=True)


if __name__ == "__main__":
    main()
