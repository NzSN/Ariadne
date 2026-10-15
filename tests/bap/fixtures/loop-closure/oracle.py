#!/usr/bin/env python3
"""Independent finite concrete oracle for local loop-target induction.

This does not load Rust, native code, a BIL matcher or a model checker. It
enumerates original one-step transitions over four-bit scalar values and
checks the proposed assertions by set inclusion. Captured table entries are
signed 32-bit byte strings; target addition is reduced to the finite word.
The indexed table is a synthetic array, not a four-bit physical memory map.
Cryptographic bindings below are this oracle's synthetic format, not runtime
wire-compatibility evidence. Finite checking is not a universal refinement.
"""

import argparse
from collections import deque
from copy import deepcopy
import hashlib
import itertools
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
WORDS = tuple(range(16))
BASE = 12
BOUND = 9
INDICES = tuple(range(BOUND + 1))
OFFSETS = (-3, -2, -1, 4, -3, -2, -1, -3, -2, -1)
NODES = tuple(range(9))
INTERNAL = ((0, 1), (1, 2), (2, 3), (3, 4), (4, 5),
            (5, 1), (5, 6), (6, 7), (7, 8), (8, 0))
EXITS = ((2, 9), (8, 9), (8, 10), (8, 11))
TARGETS = tuple(sorted({(BASE + offset) % 16 for offset in OFFSETS}))


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def original(case):
    """Build source facts first; proof claims do not control these facts."""
    change = case.get("source", {})
    return {
        "scope": {"snapshot": "finite-snapshot", "activation": 1,
                  "roots": [15], "memory_premise":
                  change.get("memory_premise", True)},
        "epoch": change.get("epoch", 0),
        "entry_base": change.get("entry_base", BASE),
        "entrances": [[13, 3]] + change.get("extra_entrances", []),
        "root_inside": change.get("root_inside", False),
        "internal": [list(edge) for edge in INTERNAL],
        "exits": [list(edge) for edge in EXITS],
        "guard": change.get("guard", "unsigned-above"),
        "flag_clobber": change.get("flag_clobber", False),
        "selector_clobber": change.get("selector_clobber", False),
        "backedge_base_clobber": change.get("backedge_base_clobber", False),
        "effects": change.get("effects", []),
        "missing_indices": change.get("missing_indices", []),
        "conflicting_indices": change.get("conflicting_indices", []),
        "table_bytes": [offset.to_bytes(4, "little", signed=True).hex()
                        for offset in OFFSETS],
        # Deliberately retained and never used as target/closure evidence.
        "input_complete": change.get("input_complete", False),
    }


def assertions(shared_selector=False):
    """Explicit concrete sets, not a symbolic/interval production algorithm."""
    result = {}
    for node in NODES:
        selectors = (INDICES if node == 6 else
                     tuple(sorted({offset % 16 for offset in OFFSETS}))
                     if node == 7 else TARGETS if node == 8 else WORDS)
        if shared_selector and node == 4:
            selectors = (3,)
        result[node] = {
            (BASE, pointer, selector, flag)
            for pointer in WORDS for selector in selectors
            for flag in ((int(selector > BOUND),) if node == 5 else (0, 1))
        }
    return result


def receipt(source, case):
    change = case.get("receipt", {})
    edges = source["internal"] + source["exits"]
    if change.get("omit_exit"):
        edges = [edge for edge in edges if edge != [2, 9]]
    if change.get("omit_target"):
        edges = [edge for edge in edges if edge != [8, 0]]
    return {
        "source_digest": digest(source),
        "scope": deepcopy(source["scope"]),
        "epoch": change.get("epoch", source["epoch"]),
        "entrances": [[13, 3]],
        "edges": edges,
        "targets": list(TARGETS) if not change.get("omit_target")
                   else [target for target in TARGETS if target != 0],
        "shared_selector": change.get("shared_selector", False),
        "table_sign": change.get("table_sign", "signed"),
        "table_slots": list(INDICES),
        "iteration_values_equal": change.get("iteration_values_equal", False),
    }


def successors(source, node, state):
    """Interpret original source effects with fresh nondeterministic loads.

    A state is (base bank, object pointer, selector/offset/target, flag).
    The flag is produced at the compare and consumed at the branch, preserving
    the relevant same-iteration definition identity.
    """
    base, pointer, selector, flag = state
    if node == 0:
        base = (base + 1) % 16 if source["backedge_base_clobber"] else base
        return [(1, (base, fresh, selector, flag)) for fresh in WORDS]
    if node == 1:
        return [(2, state)]
    if node == 2:
        return [(3 if pointer else 9, state)]
    if node == 3:
        return [(4, (base, pointer, fresh, flag)) for fresh in WORDS]
    if node == 4:
        flags = (0, 1) if source["flag_clobber"] else (int(selector > BOUND),)
        return [(5, (base, pointer, selector, value)) for value in flags]
    if node == 5:
        if source["guard"] == "bypass":
            choices = (1, 6)
        elif source["guard"] == "wrong-polarity":
            choices = (6 if flag else 1,)
        elif source["guard"] == "signed":
            signed_selector = selector - 16 if selector >= 8 else selector
            choices = (1 if signed_selector > 9 else 6,)
        else:
            choices = (1 if flag else 6,)
        result = []
        for target in choices:
            value = ((selector + 1) % 16 if target == 6
                     and source["selector_clobber"] else selector)
            result.append((target, (base, pointer, value, flag)))
        return result
    if node == 6:
        if selector not in INDICES or selector in source["missing_indices"]:
            offsets = WORDS
        else:
            offsets = (int.from_bytes(bytes.fromhex(source["table_bytes"][selector]),
                                      "little", signed=True) % 16,)
        return [(7, (base, pointer, offset, flag)) for offset in offsets]
    if node == 7:
        return [(8, (base, pointer, (base + selector) % 16, flag))]
    if node == 8:
        return [(selector, state)]
    return []


def derive_table(source):
    entries = []
    residuals = []
    for index in INDICES:
        if index in source["missing_indices"]:
            residuals.append([index, "missing"])
            continue
        if index in source["conflicting_indices"]:
            residuals.append([index, "conflict"])
            continue
        raw = bytes.fromhex(source["table_bytes"][index])
        offset = int.from_bytes(raw, "little", signed=True)
        entries.append([index, offset, (BASE + offset) % 16])
    return entries, residuals


def verify(source, proof, budget):
    """Universal finite one-step checks; never trust fixed-point convergence."""
    if budget <= 0:
        return False, "work-budget", 0
    if proof["source_digest"] != digest(source) or proof["scope"] != source["scope"]:
        return False, "source-or-scope-binding", 0
    if proof["epoch"] != source["epoch"]:
        return False, "stale-epoch", 0
    if not source["scope"]["memory_premise"]:
        return False, "memory-premise", 0
    if source["effects"]:
        return False, "unsupported-original-effect", 0
    if sorted(proof["entrances"]) != sorted(source["entrances"]):
        return False, "entrance-inventory", 0
    if source["root_inside"]:
        return False, "uninitialized-region-root", 0
    if sorted(proof["edges"]) != sorted(source["internal"] + source["exits"]):
        return False, "edge-inventory", 0
    if proof["iteration_values_equal"]:
        return False, "unjustified-load-equality", 0
    entries, residuals = derive_table(source)
    if residuals:
        return False, "captured-table-unavailable", 0
    inv = assertions(proof["shared_selector"])
    work = 0
    # The earlier state is arbitrary; only the source reset establishes base.
    for pointer, selector, flag in itertools.product(WORDS, WORDS, (0, 1)):
        work += 1
        if work > budget:
            return False, "work-budget", work - 1
        if (source["entry_base"], pointer, selector, flag) not in inv[3]:
            return False, "entrance-initialization", work
    edge_set = {tuple(edge) for edge in proof["edges"]}
    for node in NODES:
        for state in sorted(inv[node]):
            for target, output in successors(source, node, state):
                work += 1
                if work > budget:
                    return False, "work-budget", work - 1
                if (node, target) not in edge_set:
                    return False, "uncovered-source-successor", work
                if target in inv and output not in inv[target]:
                    return False, "inductive-preservation", work
    if proof["table_sign"] != "signed" or proof["table_slots"] != list(INDICES):
        return False, "table-domain-or-arithmetic", work
    targets = sorted({entry[2] for entry in entries})
    if targets != proof["targets"]:
        return False, "target-inventory", work
    return True, "accepted", work


def concrete_reachable(source):
    """Finite product-state enumeration; repeated nodes do not lose state."""
    queue = deque((3, (source["entry_base"], pointer, selector, flag))
                  for pointer, selector, flag in itertools.product(WORDS, WORDS, (0, 1)))
    visited = set()
    dispatch_targets = set()
    while queue:
        node, state = queue.popleft()
        if node not in NODES or (node, state) in visited:
            continue
        visited.add((node, state))
        if node == 8:
            dispatch_targets.add(state[2])
        queue.extend(successors(source, node, state))
    return {"states": len(visited), "dispatch_targets": sorted(dispatch_targets)}


def fresh_loop_witness(source):
    """One checked path has pointer 1/selector 3 then pointer 2/selector 2."""
    if source["entry_base"] != BASE:
        return False
    wanted = [(3, (BASE, 1, 0, 0)), (4, (BASE, 1, 3, 0)),
              (5, (BASE, 1, 3, 0)), (6, (BASE, 1, 3, 0)),
              (7, (BASE, 1, 4, 0)), (8, (BASE, 1, 0, 0)),
              (0, (BASE, 1, 0, 0)), (1, (BASE, 2, 0, 0)),
              (2, (BASE, 2, 0, 0)), (3, (BASE, 2, 0, 0)),
              (4, (BASE, 2, 2, 0)), (5, (BASE, 2, 2, 0)),
              (6, (BASE, 2, 2, 0)), (7, (BASE, 2, 15, 0)),
              (8, (BASE, 2, 11, 0))]
    return all(next_state in successors(source, node, state)
               for (node, state), next_state in zip(wanted, wanted[1:]))


def run_case(case):
    source = original(case)
    proof = receipt(source, case)
    if case.get("receipt", {}).get("wrong_scope"):
        proof["scope"]["activation"] += 1
    if case.get("receipt", {}).get("wrong_source"):
        proof["source_digest"] = "0" * 64
    accepted, reason, work = verify(source, proof, case.get("budget", 200000))
    entries, residuals = derive_table(source)
    result = {"accepted": accepted, "reason": reason,
              "known_targets": sorted({entry[2] for entry in entries}),
              "fresh_loop_witness": fresh_loop_witness(source),
              "work": work, "read_residuals": residuals}
    if case.get("enumerate_reachable", False):
        result["reachable"] = concrete_reachable(source)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    corpus = json.loads((HERE / "oracle-cases.json").read_text())
    results = []
    for case in corpus["cases"]:
        result = run_case(case)
        if args.check:
            for name, expected in case["expected"].items():
                if result.get(name) != expected:
                    raise SystemExit(f'{case["name"]}: {name}: '
                                     f'{result.get(name)!r} != {expected!r}')
        results.append({"name": case["name"], **result})
    arithmetic = []
    for case in corpus["arithmetic_cases"]:
        offset = int.from_bytes(bytes.fromhex(case["bytes_hex"]), "little", signed=True)
        target = (case["base"] + offset) % (1 << case["address_width"])
        result = {"name": case["name"], "signed_offset": offset, "target": target}
        if args.check and (offset != case["expected_offset"]
                           or target != case["expected_target"]):
            raise SystemExit(f'{case["name"]}: signed arithmetic mismatch')
        arithmetic.append(result)
    report = {"schema": "ariadne.loop-target-closure.finite-oracle/v1",
              "cases": results, "arithmetic_cases": arithmetic,
              "source_sha256": digest(corpus),
              "scope": "four-bit concrete induction; no runtime/native compatibility claim"}
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"cases": len(results),
                      "arithmetic_cases": len(arithmetic),
                      "accepted": sum(result["accepted"] for result in results),
                      "checked": args.check, "scope": report["scope"]}))


if __name__ == "__main__":
    main()
