#!/usr/bin/env python3
"""Independent finite oracle for guarded target composition.

Table arithmetic uses Python signed byte conversion plus modular integer
addition. Guard checking traverses explicit (node,residue) product vertices,
not the production register solver or its node-wise fixed-point worklist.
Receipts use this oracle's own canonical JSON identity: they are synthetic
binding checks, not runtime/native serialization compatibility evidence.
No Rust, BAP, OCaml or model tool is loaded by this program.
"""

import argparse
from collections import deque
from copy import deepcopy
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TOP = frozenset(range(16))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def table_result(case):
    source = case["input"]
    payload = bytes.fromhex(source["bytes"])
    modulus = 1 << source["address_width"]
    available = []
    residuals = []
    for index in source["indices"]:
        if index in source["conflicting_indices"]:
            residuals.append([index, "conflict"])
            continue
        start = index * 4
        chunk = payload[start:start + 4]
        if len(chunk) != 4:
            residuals.append([index, "missing-bytes"])
            continue
        offset = int.from_bytes(chunk, "little", signed=True)
        target = (source["base"] + offset) % modulus
        available.append([index, offset, target])
    complete = (source["memory_premise"] and source["incoming_covered"]
                and not residuals and source["inspected_all_indices"])
    return {"entries": available,
            "targets": sorted({entry[2] for entry in available}),
            "complete": complete, "residuals": residuals,
            "missing_code_endpoints": sorted({entry[2] for entry in available}
                                             - set(source["code_available"]))}


def guard_result(graph):
    """Exhaustive finite product-graph reachability, preserving every edge."""
    roots = graph["scope"]["roots"]
    known = set()
    queue = deque((node, residue) for node in roots for residue in graph["entry_residues"])
    queue.extend((node, residue) for node in graph["barriers"] for residue in TOP)
    edges = graph["original"] + graph["pending"] + graph["augmentation"]
    adjacency = {}
    for source, target in edges:
        adjacency.setdefault(source, []).append(target)
    exhausted = False
    while queue:
        state = queue.popleft()
        if state in known:
            continue
        if len(known) == graph["product_budget"]:
            exhausted = True
            break
        known.add(state)
        node, residue = state
        transfer = graph["transfers"][str(node)]
        if transfer["kind"] == "identity":
            outputs = [residue]
        elif transfer["kind"] == "add":
            outputs = [(residue + transfer["delta"]) % 16]
        else:
            outputs = TOP
        for target in adjacency.get(node, []):
            queue.extend((target, output) for output in outputs)
    residues = sorted(residue for node, residue in known if node == graph["guard"])
    verdict = ("budget-stop" if exhausted else
               "unknown" if not graph["covered"] or graph["barriers"] else
               "unreached" if not residues else
               "aligned" if residues == [0] else
               "misaligned" if 0 not in residues else "unknown")
    normal = verdict == "aligned"
    final = edges if normal else graph["original"] + graph["augmentation"]
    return {"guard_residues": residues, "verdict": verdict,
            "normal_store": normal, "final_edges": sorted(final),
            "product_states": len(known)}


def frontier_result(case):
    """Enumerate arbitrary register inputs at a cut, never create a root.

    Every reverse-prefix context must entail the admitted table index range.
    This finite bit-vector truth table is deliberately independent of symbolic
    expression recovery; native/Rust path-prefix checks are separate evidence.
    """
    source = case["input"]
    indices = set()
    for context in source["contexts"]:
        for register in range(1 << source["register_width"]):
            index = register & context["mask"]
            if context["upper_guard"] is None or index <= context["upper_guard"]:
                indices.add(index)
    bounded = indices.issubset(set(source["table_indices"]))
    roots_unchanged = source["roots"] == source["original_roots"]
    complete = bounded and roots_unchanged and source["all_prefixes_covered"]
    return {"indices": sorted(indices), "complete": complete,
            "roots": source["roots"], "frontier_is_root": source["frontier"] in source["roots"],
            "unknown_indices": sorted(indices - set(source["table_indices"])),
            "uncovered_prefix": not source["all_prefixes_covered"]}


def conditional_write_result(case):
    """Enumerate one decrement and test its branch condition exactly once.

    The finite word is a contract representative, not an ISA step proof. The
    wrong result deliberately substitutes the register-writing expression into
    a condition that is already expressed in the post-transfer state.
    """
    width = case["input"]["width"]
    modulus = 1 << width
    upper = case["input"]["later_upper_bound"]
    correct = set()
    double_applied = set()
    inputs = []
    for before in range(modulus):
        after = (before - 1) % modulus
        if after != 0 and after <= upper:
            correct.add(after)
            inputs.append(before)
        if (after - 1) % modulus != 0 and after <= upper:
            double_applied.add(after)
    return {"correct_indices": sorted(correct),
            "incorrect_double_applied_indices": sorted(double_applied),
            "correct_source_inputs": inputs,
            "wrongly_included_indices": sorted(double_applied - correct),
            "wrongly_excluded_indices": sorted(correct - double_applied)}


def infeasible_context_result(case):
    """Enumerate guard pairs; share a load only under an explicit stable identity.

    A finite contradiction may close one incoming context before the table base
    is known. Changed addresses/register definitions, unknown writes and mutable
    memory create independent symbols. No observed historical index is assumed.
    """
    source = case["input"]
    same_symbol = (source["first_address_identity"] == source["second_address_identity"]
                   and source["index_definition_unchanged"]
                   and source["frozen_control_data"]
                   and source["nonunknown_symbolic_subject"]
                   and not source["unknown_memory_write"]
                   and not source["cycle_has_opaque_call"])
    domain = range(1 << source["load_width"])
    feasible = 0
    indices = set()
    for first in domain:
        seconds = [first] if same_symbol else domain
        for second in seconds:
            if first > source["backedge_bound"] and second <= source["exit_bound"]:
                feasible += 1
                indices.add(second)
    contradiction = feasible == 0
    may_cut = contradiction and source["prefix_replayed"]
    return {"same_symbol_justified": same_symbol,
            "feasible_assignments": feasible,
            "possible_indices": sorted(indices),
            "universally_infeasible": contradiction,
            "may_cut_without_known_table_base": may_cut,
            "receipt_form": "infeasible" if may_cut else None,
            "complete_with_all_other_prefixes_covered": may_cut and source["all_prefixes_covered"],
            "roots": source["roots"], "frontier_is_root": source["frontier"] in source["roots"]}


def graph_receipts(graph):
    """Acyclic identities: source/scope, candidate seal, receipts, then final."""
    result = guard_result(graph)
    graph_hash = digest(graph)
    binding = {"scope": deepcopy(graph["scope"]), "epoch": graph["epoch"],
               "graph": graph_hash, "source": graph["source_hash"]}
    target = {**deepcopy(binding), "kind": "target", "targets": graph["targets"],
              "complete": graph["target_complete"]}
    guard = {**deepcopy(binding), "kind": "guard", "verdict": result["verdict"],
             "residues": result["guard_residues"]}
    final = {"scope": graph["scope"], "edges": result["final_edges"],
             "normal_store": result["normal_store"],
             "target_proof": digest(target), "guard_proof": digest(guard)}
    return {"graph": deepcopy(graph), "target": target, "guard": guard,
            "final": final, "final_digest": digest(final)}


def validate_receipts(envelope, expected_graph):
    if "target" not in envelope or "guard" not in envelope:
        return "missing-proof"
    if envelope["graph"] != expected_graph:
        return "candidate-binding"
    graph = envelope["graph"]
    if set(graph["scope"]["premises"]) != {
            "FrozenCapturedControlData", "WindowsNormalCallEntry"}:
        return "premise-binding"
    if graph["scope"]["roots"] != [1] or graph["scope"]["seeds"] != [6]:
        return "immutable-scope"
    expected = graph_receipts(graph)
    for family in ("target", "guard"):
        if envelope[family] != expected[family]:
            return f"{family}-binding"
    if envelope["final"] != expected["final"]:
        return "final-transformation"
    if envelope["final_digest"] != digest(envelope["final"]):
        return "final-digest"
    return "accepted"


def mutate(envelope, recipe):
    altered = deepcopy(envelope)
    cursor = altered
    path = recipe["path"]
    for name in path[:-1]:
        cursor = cursor[name]
    if recipe["action"] == "delete":
        del cursor[path[-1]]
    else:
        cursor[path[-1]] = recipe["value"]
    return altered


def captured_reference(contract):
    reference = contract["captured_reference"]
    path = ROOT / reference["path"]
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != reference["sha256"]:
        raise AssertionError("captured witness identity changed")
    witness = json.loads(raw)
    targets = set()
    entries = 0
    for table in witness["tables"]:
        base = int(table["base"], 16)
        local = set()
        for entry in table["entries"]:
            signed = entry["offset_i32"]
            assert -(1 << 31) <= signed < 1 << 31
            expected = (base + signed) % (1 << 64)
            assert expected == int(entry["target"], 16)
            assert len(bytes.fromhex(entry["captured_code_prefix_hex"])) == 15
            local.add(expected)
            entries += 1
        assert len(local) == table["distinct_targets"]
        targets.update(local)
    assert entries == reference["entries"] == witness["entry_count"]
    assert len(targets) == reference["targets"] == witness["all_distinct_targets"]
    assert len(witness["tables"]) == reference["tables"]
    return {"tables": len(witness["tables"]), "entries": entries,
            "targets": len(targets)}


def check(contract):
    numeric = contract["numeric_cases"]
    graphs = contract["graph_cases"]
    for case in numeric:
        actual = table_result(case)
        if actual != case["expected"]:
            raise AssertionError(f"{case['name']}: {actual} != {case['expected']}")
    for case in graphs:
        actual = guard_result(case["input"])
        if actual != case["expected"]:
            raise AssertionError(f"{case['name']}: {actual} != {case['expected']}")
    for case in contract["frontier_cases"]:
        actual = frontier_result(case)
        if actual != case["expected"]:
            raise AssertionError(f"{case['name']}: {actual} != {case['expected']}")
    for case in contract["conditional_write_cases"]:
        actual = conditional_write_result(case)
        if actual != case["expected"]:
            raise AssertionError(f"{case['name']}: {actual} != {case['expected']}")
    for case in contract["infeasible_context_cases"]:
        actual = infeasible_context_result(case)
        if actual != case["expected"]:
            raise AssertionError(f"{case['name']}: {actual} != {case['expected']}")
    bases = {case["name"]: case["input"] for case in graphs}
    for case in contract["receipt_cases"]:
        graph = bases[case["graph_case"]]
        envelope = graph_receipts(graph)
        if "mutation" in case:
            envelope = mutate(envelope, case["mutation"])
        actual = validate_receipts(envelope, graph)
        if actual != case["expected"]:
            raise AssertionError(f"{case['name']}: {actual} != {case['expected']}")
    # All five kinds of proof-relevant change invalidate both receipt families,
    # even where candidate destinations and edges do not change.
    base = graphs[0]["input"]
    old = graph_receipts(base)
    for case in contract["epoch_cases"]:
        revised = deepcopy(base)
        revised[case["field"]] = case["value"]
        revised["epoch"] += 1
        altered = deepcopy(old)
        altered["graph"] = revised
        actual = validate_receipts(altered, revised)
        assert actual == case["expected"], (case["name"], actual)
        for family in ("target", "guard"):
            assert altered[family] != graph_receipts(revised)[family]
    captured = captured_reference(contract)
    return {"schema": "ariadne.guarded-target-composition-oracle-result/v1",
            "numeric_cases": len(numeric), "graph_cases": len(graphs),
            "receipt_cases": len(contract["receipt_cases"]),
            "epoch_cases": len(contract["epoch_cases"]),
            "frontier_cases": len(contract["frontier_cases"]),
            "conditional_write_cases": len(contract["conditional_write_cases"]),
            "infeasible_context_cases": len(contract["infeasible_context_cases"]),
            "captured_reference": captured, "status": "pass"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    parser.add_argument("--contract", type=Path, default=HERE / "contract.json")
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text())
    print(json.dumps(check(contract), sort_keys=True))


if __name__ == "__main__":
    main()
