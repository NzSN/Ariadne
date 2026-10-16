#!/usr/bin/env python3
"""Check hand-derived Stage 5.1 expectations against independent set equations.

This checker never invokes Ariadne, imports its producer, regenerates expected
results, or runs a graph-discovery worklist. The frozen JSON contains explicit
prefixes and edge/gap/stop expectations. We check the Ariadne.tla conservation
laws for each supplied prefix, including least-VA schedule legality. Local
negative controls demonstrate observer sensitivity; they are not compiled-SUT
mutation qualification. Concrete capture/proof parsing remains outside scope.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
U64_MAX = (1 << 64) - 1
LOCAL_KINDS = {"next", "taken", "fallthrough", "jump", "indirect", "summary"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def instruction_edges(insn):
    """Finite typed-edge relation, not a recovery or graph traversal routine."""
    site, kind = insn["address"], insn["kind"]
    fall, targets = insn["fall"], insn["targets"]
    return {
        "ordinary": {(site, dst, "next") for dst in fall},
        "conditional": ({(site, dst, "fallthrough") for dst in fall}
                        | {(site, dst, "taken") for dst in targets}),
        "jump": {(site, dst, "jump") for dst in targets},
        "indirect": {(site, dst, "indirect") for dst in targets},
        "call": ({(site, dst, "summary") for dst in fall}
                 | {(site, dst, "call") for dst in targets}),
        "return": set(), "stop": set(),
    }[kind]


def products(starts, instructions):
    return {edge for address in starts for edge in instruction_edges(instructions[address])}


def check_recovery(case):
    inp, out = case["input"], case["expected"]
    addresses = set(inp["addresses"])
    roots = set(inp["entry_points"])
    captured, decodable = set(inp["captured"]), set(inp["decodable"])
    table = {insn["address"]: insn for insn in inp["instructions"]}
    require(len(table) == len(inp["instructions"]), "duplicate input instruction")
    require(set(table) == addresses and roots <= addresses, "input address domain")
    require(captured <= addresses and decodable <= addresses, "source domain")
    require(set(inp["slice_seeds"]) <= addresses, "slice seed domain")
    for insn in table.values():
        require(set(insn["fall"]) | set(insn["targets"]) <= addresses, "edge endpoint domain")
        require(type(insn["complete"]) is bool, "invalid completeness premise")
        if insn["kind"] in {"ordinary", "conditional", "call"}:
            require(len(insn["fall"]) == 1, "missing/ambiguous continuation")
        if insn["kind"] in {"conditional", "jump"}:
            require(len(insn["targets"]) == 1, "missing/ambiguous direct target")
    if out.get("request_status") == "invalid_request":
        require(not roots and out["invalid_field"] == "entry_points", "wrong invalid-request control")
        return
    require(bool(roots), "a prepared core request requires at least one root")
    order = out["visited_order"]
    visited, decoded = set(out["visited"]), set(out["decoded"])
    require(len(order) == len(set(order)) and set(order) == visited, "attempts are not unique")
    require(visited <= addresses and visited == set(order), "visited domain")
    require(decoded == visited & captured & decodable, "attempted/decoded admission mismatch")
    edges = {(edge["src"], edge["dst"], edge["kind"]) for edge in out["edges"]}
    require(len(edges) == len(out["edges"]), "duplicate expected edge")
    require(edges == products(decoded, table), "missing or fabricated typed edge")
    discovered = roots | {dst for _, dst, kind in edges if kind in LOCAL_KINDS}
    require(set(out["pending"]) == discovered - visited, "lost/fabricated pending frontier")
    require(set(out["pending"]).isdisjoint(visited), "visited requeued")
    for index, address in enumerate(order):
        prior = set(order[:index])
        successful_prefix = prior & captured & decodable
        prefix_edges = products(successful_prefix, table)
        eligible = (roots | {dst for _, dst, kind in prefix_edges if kind in LOCAL_KINDS}) - prior
        require(bool(eligible) and address == min(eligible), "illegal deterministic Visit prefix")
    obligations = {(item["site"], item["reason"]) for item in out["obligations"]}
    require(len(obligations) == len(out["obligations"]), "duplicate expected obligation")
    failures = {(a, "unavailable" if a not in captured else "decode-failed")
                for a in visited - decoded}
    residuals = {(a, "indirect-targets" if table[a]["kind"] == "indirect" else "call-targets")
                 for a in decoded if table[a]["kind"] in {"indirect", "call"}
                 and not table[a]["complete"]}
    require(obligations == failures | residuals, "lost/fabricated obligation")
    provenance = {item["address"]: item["source"] for item in out["provenance"]}
    require(len(provenance) == len(out["provenance"]), "duplicate provenance")
    require(provenance == {a: "captured" if a in decoded else "unavailable" for a in addresses},
            "wrong provenance")
    require(type(inp["max_visits"]) is int and inp["max_visits"] >= 0, "invalid producer limit")
    require(len(order) <= inp["max_visits"], "producer visit overrun")
    deadline = inp["deadline_before_visit"]
    require(deadline is None or (type(deadline) is int and deadline >= 0), "invalid deadline receipt")
    require(deadline is None or len(order) <= deadline, "producer deadline overrun")
    # Stop priority: drain first, then exhausted visits, then recorded deadline.
    if not out["pending"]:
        stop = "drained"
    elif len(order) == inp["max_visits"]:
        stop = "visit_limit"
    elif deadline is not None and len(order) == deadline:
        stop = "deadline"
    else:
        raise ValueError("prefix stopped without a declared boundary")
    require(out["stop_reason"] == stop, "forged or misprioritized stop")
    require(out["recovery_status"] == ("drained" if stop == "drained" else "work_stopped"),
            "drain status contradicts work receipt")
    require(out["phase"] == "recover", "FinishRecovery was executed")
    require(out["recovery_visits"] == len(order), "wrong Visit counter")
    for counter in ("finish_recovery_actions", "dataflow_actions", "slice_actions"):
        require(out[counter] == 0, f"forbidden {counter}")


def check_link(case):
    item = case["input"]
    require(item["child_entry_decoded"] is (item["child_entry_status"] == "decoded"),
            "child entry decoding premise contradicts endpoint status")
    admitted = all((
        item["caller_frame"] == item["child_frame"] + 1,
        item["caller_reached"], item["caller_decoded"], item["captured"],
        item["opcode"] == "e8", item["instruction_size"] == 5,
        item["saved_return"] == item["instruction_va"] + 5,
        item["decoded_continuation"] == item["saved_return"],
        item["decoded_target"] == item["child_entry"],
        item["child_entry_valid"], item["child_entry_decoded"], item["matching_candidates"] == 1,
    ))
    require(case["expected_link"] is admitted, "CALL admission disagrees with independent evidence")


def check_limit(case):
    parts = case.get("required_parts", [case.get("required", 0)])
    require(all(type(value) is int and 0 <= value <= U64_MAX for value in parts), "bad size input")
    total = sum(parts)
    admitted = total <= U64_MAX and total <= case["host_capacity"]
    require(case["expected_trusted"] is admitted, "host limit bypass or unchecked sum")


def check_admission(case):
    item = case["input"]
    if not item["identity_valid"] or not item["proofs_valid"]:
        status, preserved = "invalid", False
    elif not item["host_verifier_finished"]:
        status, preserved = "verification_stopped", False
    elif not item["prepared"]:
        status, preserved = "unavailable", item["independent_neighbor_prepared"]
    else:
        status, preserved = "available", item["independent_neighbor_prepared"]
    require(case["expected_status"] == status, "invalid/unavailable/verifier status conflated")
    require(case["expected_neighbor_preserved"] is preserved, "wrong independent frame survival")


def check(data):
    require(data["schema"] == "ariadne.frame-structure-oracle/v1", "wrong oracle schema")
    for family, observer in (("recovery_cases", check_recovery), ("link_cases", check_link),
                             ("limit_cases", check_limit), ("admission_cases", check_admission)):
        names = [case["name"] for case in data[family]]
        require(len(names) == len(set(names)), f"duplicate {family} name")
        for case in data[family]:
            try:
                observer(case)
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError(f"{family}/{case['name']}: {error}") from error


def negative_controls(data):
    """Mutate supplied expectations and require independent observers to fail."""
    controls = []

    def control(name, family, case_name, edit):
        candidate = copy.deepcopy(data)
        row = next(row for row in candidate[family] if row["name"] == case_name)
        edit(row)
        try:
            check(candidate)
        except ValueError as error:
            controls.append({"name": name, "rejected": True, "reason": str(error)})
        else:
            raise ValueError(f"negative control {name} escaped")

    control("missing-edge", "recovery_cases", "diamond-both-arms",
            lambda row: row["expected"]["edges"].pop())
    control("missing-frontier", "recovery_cases", "straight-prefix",
            lambda row: row["expected"].update(pending=[]))
    control("forged-drained", "recovery_cases", "straight-prefix",
            lambda row: row["expected"].update(stop_reason="drained", recovery_status="drained"))
    def add_illegal_visit(row):
        out = row["expected"]
        out["visited_order"].append(30)
        out["visited"].append(30)
        out["decoded"].append(30)
        out["recovery_visits"] = 3
        next(item for item in out["provenance"] if item["address"] == 30)["source"] = "captured"

    control("visit-after-drain", "recovery_cases", "slice-seed-is-not-root", add_illegal_visit)
    control("candidate-edge-promotion", "recovery_cases", "final-unknown-guard-excludes-candidate",
            lambda row: row["expected"]["edges"].append({"src": 20, "dst": 30, "kind": "next"}))
    control("unreached-call-accepted", "link_cases", "unreached-call",
            lambda row: row.update(expected_link=True))
    control("host-cap-ignored", "limit_cases", "proof_bytes-4",
            lambda row: row.update(expected_trusted=True))
    control("finish-recovery-executed", "recovery_cases", "straight-exact-budget",
            lambda row: row["expected"].update(finish_recovery_actions=1, phase="dataflow"))
    return controls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check frozen literal expectations (the default)")
    parser.add_argument("--candidate", type=Path, default=HERE / "frame_structure_oracle.json")
    parser.add_argument("--output", type=Path, help="Write observer results and exact fixture identity")
    args = parser.parse_args()
    raw = args.candidate.read_bytes()
    data = json.loads(raw)
    check(data)
    controls = negative_controls(data)
    counts = {family: len(data[family]) for family in
              ("recovery_cases", "link_cases", "limit_cases", "admission_cases")}
    result = {"schema": "ariadne.frame-structure-oracle-check/v1", "fixture_sha256": hashlib.sha256(raw).hexdigest(),
              "counts": counts, "negative_controls": controls,
              "scope": "Independent finite fixture-observer validation; no compiled-SUT or ISA qualification"}
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Frame-structure oracle PASS: {counts}; {len(controls)} negative controls rejected")


if __name__ == "__main__":
    main()
