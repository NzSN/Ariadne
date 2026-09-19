#!/usr/bin/env python3
"""Explicitly generate and check the private replay corpus; never runs the SUT."""

import json
import os
from pathlib import Path
import shutil

from projection import project
from tools import (FIXTURES, MBT, ORACLE_FILES, ROOT, mirrors_tools, prepare_model,
                   resolve, run, sha256, work_directory, write_json)


def integer(value):
    if type(value) is not int or value < 0:
        raise ValueError(f"expected a nonnegative model VA, got {value!r}")
    return {"#bigint": str(value)}


def record(value, integer_fields, string_fields):
    if not isinstance(value, dict) or set(value) != set(integer_fields) | set(string_fields):
        raise ValueError(f"invalid model record shape: {value!r}")
    result = {key: integer(value[key]) for key in integer_fields}
    for key in string_fields:
        if not isinstance(value[key], str):
            raise ValueError(f"expected string at {key}")
        result[key] = value[key]
    return result


def model_set(values, convert):
    if not isinstance(values, list):
        raise ValueError("TLC JSON set must be an array")
    return {"#set": [convert(value) for value in values]}


def address_map(values, convert):
    # TLC exports functions with domain 1..n as arrays, other integer domains
    # as objects. The model declares these two fields as address-keyed functions.
    if isinstance(values, list):
        entries = enumerate(values, 1)
    elif isinstance(values, dict):
        if any(not key.isdecimal() or str(int(key)) != key for key in values):
            raise ValueError("noncanonical TLC address map key")
        entries = sorted((int(key), value) for key, value in values.items())
    else:
        raise ValueError("invalid TLC address map")
    return {"#map": [[integer(key), convert(value)] for key, value in entries]}


def string(value):
    if not isinstance(value, str):
        raise ValueError("expected model string")
    return value


def convert_trace(path, var_types, fixture):
    raw = json.loads(path.read_text())
    variables = sorted(var_types)
    if sorted(raw["vars"]) != variables:
        raise ValueError("TLC variables differ from Apalache's type evidence")
    converters = {
        "phase": string, "action_taken": string, "fixture_id": string,
        "parameters": lambda value: record(value, (), ("fixture",)),
        "pending": lambda value: model_set(value, integer),
        "visited": lambda value: model_set(value, integer),
        "decoded": lambda value: model_set(value, integer),
        "slice": lambda value: model_set(value, integer),
        "provenance": lambda value: address_map(value, string),
        "edges": lambda value: model_set(value, lambda e: record(e, ("src", "dst"), ("kind",))),
        "obligations": lambda value: model_set(value, lambda o: record(o, ("site",), ("reason",))),
        "reaching": lambda value: address_map(value, lambda ds: model_set(ds,
            lambda d: record(d, ("site",), ("loc", "origin")))),
    }
    states = []
    for expected_index, (index, state) in enumerate(raw["counterexample"]["state"], 1):
        if index != expected_index or set(state) != set(variables):
            raise ValueError("noncontiguous trace or inconsistent model state")
        if state["parameters"] != {"fixture": fixture} or state["fixture_id"] != fixture:
            raise ValueError("unexpected fixture parameter")
        states.append({"#meta": {"index": index - 1},
                       **{key: converters[key](state[key]) for key in variables}})
    if not states or states[0]["action_taken"] != "init" or states[-1]["phase"] != "done":
        raise ValueError("trace does not cover initialization through completion")
    return {"#meta": {"format": "ITF", "varTypes": var_types}, "vars": variables,
            "param_vars": [], "params": [], "states": states}


def main():
    work = work_directory("generate")
    print(f"Generation logs: {work}", flush=True)
    model = prepare_model(work)
    mirrors, compiler, _ = mirrors_tools()
    apalache = os.environ.get("APALACHE_MC", "apalache-mc")
    tlc = os.environ.get("TLC", "tlc")
    version = run([apalache, "version"]).stdout.strip()
    type_root = work / "types"
    run([apalache, f"--out-dir={type_root}", "check", "--cinit=PipelineConstants",
         "--init=Init", "--next=Next", "--inv=TypeWitness", "--length=0",
         "--no-deadlock", model], expected=(12,), log=work / "types.log")
    candidates = sorted(type_root.rglob("violation*.itf.json"))
    if not candidates:
        raise RuntimeError("Apalache emitted no typed initialization witness")
    type_witness = json.loads(candidates[0].read_text())
    var_types = type_witness["#meta"]["varTypes"]
    corpus = work / "corpus"
    corpus.mkdir()
    write_json(corpus / "raw-type-evidence.json", type_witness)
    write_json(corpus / "type-evidence.json", project(type_witness))
    trace_counts = {}
    for fixture in FIXTURES:
        config = model.parent / f"{fixture}.cfg"
        config.write_text(f'SPECIFICATION Spec\nCONSTANT Fixture = "{fixture}"\n'
                          'INVARIANT Safety\nPROPERTY Terminates\nCHECK_DEADLOCK FALSE\n')
        common = [tlc, "-workers", "1", "-noGenerateSpecTE", "-config", config]
        checked = run([*common, "-metadir", work / f"states-{fixture}", model],
                      log=work / f"{fixture}-safety.log")
        if "Model checking completed. No error has been found." not in checked.stdout:
            raise RuntimeError(f"TLC did not confirm safety/liveness for {fixture}")
        config.write_text(f'INIT Init\nNEXT Next\nCONSTANT Fixture = "{fixture}"\n'
                          'INVARIANTS Safety TraceComplete\nCHECK_DEADLOCK FALSE\n')
        raw = work / f"{fixture}.tlc.json"
        witness = run([*common, "-metadir", work / f"witness-{fixture}",
                       "-dumpTrace", "json", raw, model], expected=(12,),
                      log=work / f"{fixture}-witness.log")
        if "Invariant TraceComplete is violated" not in witness.stdout:
            raise RuntimeError(f"{fixture} failed for something other than the expected completion witness")
        trace = convert_trace(raw, var_types, fixture)
        raw_path = corpus / f"{fixture}.raw.json"
        projected_path = corpus / f"{fixture}.itf.json"
        write_json(raw_path, trace)
        write_json(projected_path, project(trace))
        write_json(corpus / f"{fixture}.projection.json", {
            "schema": "ariadne.mbt-address-map-projection/v1",
            "rawSha256": sha256(raw_path), "projectedSha256": sha256(projected_path),
            "projectionSha256": sha256(MBT / "projection.py"),
            "rawVariables": trace["vars"], "projectedVariables": trace["vars"],
            "roundTripChecked": True,
        })
        trace_counts[fixture] = len(trace["states"])
        print(f"{fixture}: safety and fair termination passed; {len(trace['states'])} witness states", flush=True)
    lock = corpus / "AriadneReplay.lock.json"
    resolve(compiler, model, corpus / "type-evidence.json", lock, work / "resolve.log")
    for fixture in FIXTURES:
        run([compiler, "preflight", "--lock", lock, "--trace", corpus / f"{fixture}.itf.json",
             "--require-all-actions", "--diagnostics", "json"], log=work / f"{fixture}-preflight.log")
    manifest = {
        "schema": "ariadne.mbt-corpus/v1",
        "oracleSources": {path: sha256(ROOT / path) for path in ORACLE_FILES},
        "artifacts": {path.name: sha256(path) for path in sorted(corpus.iterdir())},
        "traceStates": trace_counts,
        "generation": {"command": "python3 mbt/generate.py", "apalache": version,
                       "tlc": run([tlc, "-help"], expected=(0, 1)).stdout.splitlines()[4:8],
                       "mirrorsRevision": run(["git", "rev-parse", "HEAD"], cwd=mirrors).stdout.strip(),
                       "compilerSha256": sha256(compiler),
                       "typeEvidence": "Apalache length-0 TypeWitness counterexample (expected exit 12)",
                       "traces": "TLC checked safety/termination, then TraceComplete counterexample (expected exit 12)"},
    }
    write_json(corpus / "manifest.json", manifest)
    destination = MBT / "corpus"
    destination.mkdir(exist_ok=True)
    for artifact in corpus.iterdir():
        shutil.copyfile(artifact, destination / artifact.name)
    print(f"Checked corpus published to {destination}", flush=True)


if __name__ == "__main__":
    main()
