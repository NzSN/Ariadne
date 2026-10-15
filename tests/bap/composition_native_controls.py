#!/usr/bin/env python3
"""Exercise combined native admission with a valid, source-bound input envelope.

Run on the remote native build host. Recompute the outer pair seal after each
mutation so rejection exercises evidence replay rather than a stale outer hash.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def graph_digest(candidate, local_v3=False):
    roots = [int(value, 16) for value in candidate["entry_points"]]
    rows = [[row["address"], row["kind"].capitalize(), row["fall"], row["targets"],
             row["uses"], row["may_defs"], row["must_defs"]]
            for row in candidate["instructions"]]
    legacy = digest([roots, rows])
    return digest([legacy, [[row["address"], row["targets_complete"]]
                            for row in candidate["instructions"]]]) if local_v3 else legacy


def target_graph_digest(wire):
    return graph_digest(wire["composition"]["candidate"],
                        wire["target_resolution"]["schema"] ==
                        "ariadne.indirect-target-resolution/v3")


def seal(wire):
    report = wire["composition"]
    version = report["profile"].rsplit("/", 1)[-1]
    if version not in {"v1", "v2", "v3"}:
        raise ValueError("unknown composition generation")
    report["candidate_sha256"] = digest(report["candidate"])
    report["target_report_sha256"] = digest(wire["target_resolution"])
    report["guard_report_sha256"] = digest(wire["guard_admission"])
    report["final_request_sha256"] = digest(wire["normalized"])
    report["binding_sha256"] = digest([
        "ariadne-guarded-target-binding/" + version, report["snapshot"],
        report["artifact_sha256"], report["query_scope_sha256"],
        report["candidate_epoch"], report["model_version"], report["model_sha256"],
        report["checker_sha256"], report["candidate_sha256"],
        report["original_controls"], report["target_report_sha256"],
        report["guard_report_sha256"], report["final_request_sha256"],
    ])
    wire["capture"]["query_id"] = digest([
        "ariadne-guarded-target-analysis/" + version, report["binding_sha256"]])
    semantic = wire["capture"]["semantic_profile"]
    marker = ":" + report["profile"] + ":"
    prior = semantic.split(marker, 1)[0]
    target = wire["target_resolution"]
    wire["capture"]["semantic_profile"] = (
        prior + marker + report["binding_sha256"] + ":" + target["profile"] +
        ":" + target["memory_premise"])


def transport_query(wire):
    value = hashlib.sha256(b"ariadne.bap-core-query/v1\0")
    payload = json.dumps(wire, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode()
    for text in (wire["capture"]["snapshot"].encode(), b"recovery",
                 wire["composition"]["profile"].encode(), payload):
        value.update(len(text).to_bytes(8, "big"))
        value.update(text)
    return value.hexdigest()


def invoke(helper, wire, query_override=None):
    snapshot = wire["capture"]["snapshot"]
    query = query_override or transport_query(wire)
    request = dict(schema="ariadne.bap-core/v1", session="composition-controls",
                   snapshot=snapshot, query=query, family="recovery", sequence=0,
                   operation="initialize", payload=dict(
                       profile=wire["composition"]["profile"], input=wire))
    frame = json.dumps(request, sort_keys=True, separators=(",", ":")) + "\n"
    reset = {**request, "sequence": 1, "operation": "reset", "payload": {}}
    reset_frame = json.dumps(reset, sort_keys=True, separators=(",", ":")) + "\n"
    result = subprocess.run(
        [str(helper), "composition-controls", snapshot, query, "recovery",
         "--max-request-bytes", str(len(frame.encode()) + 1)],
        input=frame + reset_frame, text=True, capture_output=True, timeout=120)
    lines = result.stdout.splitlines()
    if len(lines) < 2:
        raise RuntimeError(f"native control produced no admission response: {result.stderr}")
    ready, response = map(json.loads, lines[:2])
    if wire["composition"]["profile"] not in ready["profiles"]:
        raise RuntimeError("helper lacks combined capability")
    if response.get("error") is None:
        if len(lines) != 3:
            raise RuntimeError("accepted control did not acknowledge clean reset")
        closed = json.loads(lines[2])
        if closed.get("error") is not None or closed.get("sequence") != 1:
            raise RuntimeError("accepted control rejected clean reset")
    return response.get("error"), result.returncode


def mutate_outputs(wire):
    for transfer in wire["target_resolution"]["transfers"]:
        if transfer["outputs"]:
            key = next(iter(transfer["outputs"]))
            width = transfer["outputs"][key]["width"]
            transfer["outputs"][key] = dict(width=width, kind=dict(
                kind="constant", value="0x0000000000000001"))
            return
    raise ValueError("fixture requires a nonempty scalar output transfer")


def mutate_ast_shape(wire):
    transfer = next(row for row in wire["target_resolution"]["transfers"]
                    if json.loads(row["ast"]))
    bil = json.loads(transfer["ast"])
    bil[0]["unrecognized_field"] = True
    encoded = json.dumps(bil, separators=(",", ":"), ensure_ascii=False)
    transfer["ast"] = encoded
    transfer["ast_sha256"] = hashlib.sha256(encoded.encode()).hexdigest()
    for source in wire["capture"]["sites"]:
        if source["address"] == transfer["site"]:
            source["ast_sha256"] = transfer["ast_sha256"]
    for source in wire["guard_admission"]["input"]["sites"]:
        if source["site"] == transfer["site"]:
            source["ast"] = encoded


def mutate_original(wire):
    rows = wire["composition"]["original_controls"]
    row = next(row for row in rows if row["control"]["kind"] != "indirect")
    row["control"]["complete"] = not row["control"]["complete"]


def mutate_raw_targets(wire):
    row = next(row for row in wire["composition"]["original_controls"]
               if row["control"]["kind"] == "indirect")
    resolution = next(item for item in wire["target_resolution"]["resolutions"]
                      if item["site"] == row["site"] and item["targets"])
    row["control"]["targets"] = [resolution["targets"][0]]


def mutate_indirect_relabel(wire):
    row = next(row for row in wire["composition"]["original_controls"]
               if row["control"]["kind"] == "indirect")
    site = row["site"]
    resolution = next(item for item in wire["target_resolution"]["resolutions"]
                      if item["site"] == site and item["targets"])
    targets = [resolution["targets"][0]]
    control = dict(kind="jump", fall=[], targets=targets, complete=True)
    row["control"] = copy.deepcopy(control)
    source = next(item for item in wire["guard_admission"]["input"]["sites"]
                  if item["site"] == site)
    source["control"] = copy.deepcopy(control)
    for request in (wire["normalized"], wire["composition"]["candidate"]):
        instruction = next(item for item in request["instructions"]
                           if item["address"] == site)
        instruction.update(kind="jump", fall=[], targets=targets,
                           targets_complete=True)
    wire["target_resolution"]["resolutions"] = [
        item for item in wire["target_resolution"]["resolutions"]
        if item["site"] != site]
    wire["target_resolution"]["graph_sha256"] = target_graph_digest(wire)


def mutate_pending(wire):
    site = wire["guard_admission"]["guards"][0]["site"]
    candidate = wire["composition"]["candidate"]
    row = next(row for row in candidate["instructions"] if row["address"] == site)
    row["may_defs"] = sorted(set(row["may_defs"] + ["memory:any"]))
    wire["target_resolution"]["graph_sha256"] = target_graph_digest(wire)


def mutate_expression(wire):
    resolution = next(row for row in wire["target_resolution"]["resolutions"] if row["paths"])
    path = resolution["paths"][0]
    path["expression"] = dict(width=64, kind=dict(
        kind="constant", value="0x0000000000000001"))


def mutate_epoch(wire):
    wire["composition"]["candidate_epoch"] += 1
    wire["guard_admission"]["input"]["candidate_epoch"] += 1


def mutate_drop_source(wire):
    wire["composition"]["original_controls"].pop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--helper", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    wire = json.loads(args.input.read_text())
    control, returncode = invoke(args.helper, wire)
    if control is not None or returncode:
        raise SystemExit(f"passing control failed: {control}; exit={returncode}")
    rows = [dict(case="original", passed=True, error=control, returncode=returncode)]
    larger = copy.deepcopy(wire)
    larger["target_resolution"]["limits"] = {
        key: 2**64 - 1 for key in larger["target_resolution"]["limits"]}
    seal(larger)
    error, returncode = invoke(args.helper, larger)
    passed = error is None and returncode == 0
    rows.append(dict(case="unsigned-resolver-budgets", passed=passed,
                     error=error, returncode=returncode))
    if not passed:
        args.output.write_text(json.dumps(rows, indent=2) + "\n")
        raise SystemExit(f"unsigned resolver budget control failed: {error}")
    mutations = [
        ("scalar-output-forgery", mutate_outputs),
        ("unknown-bil-field", mutate_ast_shape),
        ("original-control-change", mutate_original),
        ("raw-indirect-invented-targets", mutate_raw_targets),
        ("register-jump-direct-relabel", mutate_indirect_relabel),
        ("pending-memory-effect", mutate_pending),
        ("target-expression-forgery", mutate_expression),
        ("stale-epoch", mutate_epoch),
        ("missing-original-source", mutate_drop_source),
    ]
    for name, mutation in mutations:
        altered = copy.deepcopy(wire)
        mutation(altered)
        seal(altered)
        error, returncode = invoke(args.helper, altered)
        passed = isinstance(error, dict) and error.get("kind") == "semantic"
        rows.append(dict(case=name, passed=passed, error=error, returncode=returncode))
        if not passed:
            args.output.write_text(json.dumps(rows, indent=2) + "\n")
            raise SystemExit(f"behavioral mutation was admitted: {name}")
    error, returncode = invoke(args.helper, wire, query_override="0" * 64)
    passed = isinstance(error, dict) and error.get("kind") == "semantic"
    rows.append(dict(case="session-query-swap", passed=passed,
                     error=error, returncode=returncode))
    args.output.write_text(json.dumps(rows, indent=2) + "\n")
    if not passed:
        raise SystemExit("session query swap was admitted")
    print(f"native combined controls PASS ({len(rows)} cases)")


if __name__ == "__main__":
    main()
