#!/usr/bin/env python3
"""Remote-only, isolated native combined-admission implementation mutations.

Credit requires a passing original, a named original rejection, a successfully
built mutant, and that mutant admitting the same named negative. Redundant
surviving checks and compile failures are recorded without mutation credit.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
CONTROLS = ROOT / "tests/bap/composition_native_controls.py"
spec = importlib.util.spec_from_file_location("combined_controls", CONTROLS)
controls = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controls)


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ordered(value, keys):
    return {key: value[key] for key in keys}


def typed_guard(report):
    activation = lambda row: ordered(row, ["thread_id", "frame_activation"])
    root = lambda row: ordered(row, ["site", "function_entry", "anchor_sha256"])
    producer = lambda row: ordered(row, ["helper_sha256", "runtime_sha256", "decoder_sha256", "projection"])
    limits = lambda row: ordered(row, ["max_sites", "max_edges", "max_residue_updates", "max_transfer_evaluations", "max_closure_rounds", "max_evidence_bytes", "max_elapsed_ms"])
    control = lambda row: ordered(row, ["kind", "fall", "targets", "complete"])
    transfer = lambda row: ordered(row, ["site", "bytes_sha256", "ast_sha256", "rule", "relation", "relation_sha256"])
    fact = lambda row: ordered(row, ["site", "residues"])
    decision = lambda row: ordered(row, ["site", "verdict", "input_residues", "address_residues", "original_ast_sha256", "normal_ast", "normal_ast_sha256", "removed_statement_paths", "residual", "receipt_sha256"])
    def premise(row):
        result = ordered(row, ["origin", "snapshot", "query_scope_sha256", "root", "point", "activation", "policy", "evidence_sha256", "rsp_residues", "rsp_value"])
        result["activation"] = activation(result["activation"])
        return result
    def site(row):
        result = ordered(row, ["site", "bytes_hex", "ast", "control", "opaque"])
        result["control"] = control(result["control"])
        return result
    result = ordered(report, ["schema", "profile", "checker_sha256", "input", "intent_id", "candidate_graph_sha256", "transfers", "facts", "guards", "stop", "final_request_sha256"])
    source = report["input"]
    result["input"] = ordered(source, ["snapshot", "artifact_sha256", "query_scope_sha256", "preparation_sha256", "platform", "roots", "seeds", "activation", "premises", "producer", "policy", "model_version", "model_sha256", "limits", "candidate_epoch", "closure_complete", "barriers", "sites"])
    result["input"].update(roots=list(map(root, source["roots"])), activation=activation(source["activation"]), premises=list(map(premise, source["premises"])), producer=producer(source["producer"]), limits=limits(source["limits"]), sites=list(map(site, source["sites"])))
    result.update(transfers=list(map(transfer, report["transfers"])), facts=list(map(fact, report["facts"])), guards=list(map(decision, report["guards"])))
    return result


def typed_digest(value):
    return hashlib.sha256(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def rebind_guard(wire):
    """Refresh binding fields for unchanged guard semantics after direct relabel.

    The chosen relabel keeps the same successor and scalar transfer, so facts,
    transfer relations, verdict and selected effect AST remain independently
    replayable. This is not a helper that constructs new semantic facts.
    """
    report = wire["guard_admission"]
    typed = typed_guard(report)
    source = typed["input"]
    edges = []
    for row in source["sites"]:
        control = row["control"]
        kind = control["kind"]
        fall_kind = "fallthrough" if kind == "conditional" else "summary" if kind == "call" else "next"
        edges.extend(dict(src=row["site"], dst=target, kind=fall_kind)
                     for target in control["fall"])
        if kind in ("conditional", "jump", "indirect"):
            edge_kind = "taken" if kind == "conditional" else kind
            edges.extend(dict(src=row["site"], dst=target, kind=edge_kind)
                         for target in control["targets"])
    report["candidate_graph_sha256"] = typed_digest([
        "ariadne-guard-candidate/v1", source["roots"], source["candidate_epoch"],
        source["closure_complete"], source["barriers"], source["sites"], edges])
    report["final_request_sha256"] = controls.digest(wire["normalized"])
    for decision in report["guards"]:
        without = copy.deepcopy(decision)
        without["receipt_sha256"] = ""
        without = ordered(without, ["site", "verdict", "input_residues", "address_residues", "original_ast_sha256", "normal_ast", "normal_ast_sha256", "removed_statement_paths", "residual", "receipt_sha256"])
        decision["receipt_sha256"] = typed_digest([
            "ariadne-guard-receipt/v1", report["checker_sha256"], report["intent_id"],
            report["candidate_graph_sha256"], source["candidate_epoch"], source["model_version"],
            source["model_sha256"], source["premises"], source["limits"], typed["transfers"],
            typed["facts"], report["stop"], report["final_request_sha256"], without])
    semantic = wire["capture"]["semantic_profile"]
    marker = ":bap-guard-admission-v1:"
    at = semantic.index(marker) + len(marker)
    wire["capture"]["semantic_profile"] = semantic[:at] + typed_digest(typed_guard(report)) + semantic[at + 64:]


def pair_ast_change(wire):
    transfer = next(row for row in wire["target_resolution"]["transfers"] if json.loads(row["ast"]))
    transfer["ast"] += " "
    transfer["ast_sha256"] = hashlib.sha256(transfer["ast"].encode()).hexdigest()
    row = next(row for row in wire["capture"]["sites"] if row["address"] == transfer["site"])
    row["ast_sha256"] = transfer["ast_sha256"]


def pair_epoch_change(wire):
    wire["composition"]["candidate_epoch"] += 1


def direct_relabel(wire):
    controls.mutate_indirect_relabel(wire)
    rebind_guard(wire)


def variants():
    return [
        ("disable-original-binder", "register-jump-direct-relabel", direct_relabel,
         "    validate_original_control site source original;", "    ();"),
        ("disable-paired-source-binding", "paired-source-ast-change", pair_ast_change,
         'require (get transfer "bytes_hex"=get source "bytes_hex" &&\n      get transfer "ast"=get source "ast" &&\n      string transfer "ast_sha256"=Guard.Sha256.digest(string source "ast"))',
         "require true"),
        ("disable-pending-effects-check", "pending-memory-effect", controls.mutate_pending,
         'require (S.mem site candidate_input.decodable && instruction.kind="ordinary" &&\n        S.equal instruction.fall (S.singleton next) && S.is_empty instruction.targets &&\n        instruction.complete && S.is_empty instruction.uses && S.is_empty instruction.may &&\n        S.is_empty instruction.must)', "require true"),
        ("disable-epoch-binding", "paired-epoch-change", pair_epoch_change,
         'get report "candidate_epoch"=get input "candidate_epoch"', "true"),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--helper", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "target/native-composition-mutants")
    parser.add_argument("--drop-derived-builds", action="store_true")
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(ROOT / "target"):
        raise SystemExit("mutant output must remain isolated under target/")
    out.mkdir(parents=True, exist_ok=True)
    baseline = json.loads(args.input.read_text())
    error, code = controls.invoke(args.helper, baseline)
    if error is not None or code:
        raise SystemExit(f"original passing control failed: {error}; exit={code}")
    original = (ROOT / "native/bap-core/composition.ml").read_text()
    rows = []
    for name, case, mutate, old, new in variants():
        private = out / name
        private.mkdir(parents=True, exist_ok=True)
        source = private / "source"
        source.mkdir(exist_ok=True)
        for path in (ROOT / "native/bap-core").glob("*.ml"):
            shutil.copyfile(path, source / path.name)
        if original.count(old) != 1:
            raise SystemExit(f"mutation selector did not match exactly once: {name}")
        (source / "composition.ml").write_text(original.replace(old, new, 1))
        altered = copy.deepcopy(baseline)
        mutate(altered)
        controls.seal(altered)
        encoded = json.dumps(altered, sort_keys=True, separators=(",", ":"))
        (private / "case-input.json").write_text(encoded + "\n")
        negative_error, negative_code = controls.invoke(args.helper, altered)
        row = dict(mutant=name, case=case, original_control_pass=True,
                   original_negative_error=negative_error, original_negative_exit=negative_code,
                   case_sha256=hashlib.sha256(encoded.encode()).hexdigest(),
                   original_source_sha256=hashlib.sha256(original.encode()).hexdigest(),
                   mutant_source_sha256=file_hash(source / "composition.ml"), credited=False)
        if not isinstance(negative_error, dict) or negative_error.get("kind") != "semantic":
            row["outcome"] = "original-negative-not-rejected"
            rows.append(row)
            (out / "validation.json").write_text(json.dumps(rows, indent=2) + "\n")
            continue
        build = private / "build"
        command = ["python3", str(ROOT / "native/bap-core/build.py"),
                   "--source-dir", str(source), "--output", str(build)]
        result = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        (private / "build.log").write_text(result.stdout)
        row.update(build_command=command, build_exit=result.returncode)
        if result.returncode:
            row["outcome"] = "compile-failure-no-credit"
        else:
            helper = build / "ariadne-bap-core"
            row["helper_sha256"] = file_hash(helper)
            row["manifest_sha256"] = file_hash(build / "manifest.json")
            shutil.copyfile(build / "manifest.json", private / "manifest.json")
            passing_error, passing_code = controls.invoke(helper, baseline)
            error, code = controls.invoke(helper, altered)
            row.update(mutant_control_error=passing_error, mutant_control_exit=passing_code,
                       mutant_negative_error=error, mutant_negative_exit=code)
            row["credited"] = passing_error is None and passing_code == 0 and error is None and code == 0
            row["outcome"] = "behavioral-kill" if row["credited"] else "survived-or-invalid-control-no-credit"
        rows.append(row)
        (out / "validation.json").write_text(json.dumps(rows, indent=2) + "\n")
        print(f"{name}: {row['outcome']}", flush=True)
        if args.drop_derived_builds and build.exists():
            shutil.rmtree(build)
    record = dict(schema="ariadne.native-composition-mutations/v1",
                  passing_original_helper_sha256=file_hash(args.helper),
                  input_sha256=file_hash(args.input), runner_sha256=file_hash(Path(__file__)),
                  controls_sha256=file_hash(CONTROLS),
                  attempted=len(rows), credited=sum(row["credited"] for row in rows),
                  rows=rows)
    (out / "validation.json").write_text(json.dumps(record, indent=2) + "\n")
    print(f"native source campaign: {record['credited']}/{record['attempted']} behavioral kills", flush=True)


if __name__ == "__main__":
    main()
