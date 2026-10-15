#!/usr/bin/env python3
"""Independent finite reference for scoped terminal and MOVAPS guard admission.

No Rust/native matcher or lifter is loaded. UD1 extents are generated from a
ModR/M/SIB grammar, MOVAPS effects are tested by concrete bit-vector execution,
and guard facts use a product-graph BFS. Synthetic receipt identities here are
not the runtime wire format. These finite controls are not an ISA proof or a
mechanically checked refinement of the implementation.
"""

import argparse
from collections import deque
from copy import deepcopy
import hashlib
import itertools
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
SCOPE = "local-normal-completion/v1"
PROPERTIES = {name: False for name in ("jump", "conditional", "indirect", "call", "return", "control")}
RAW = None
GRAMMAR = None
LAYOUTS = None


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def grammar():
    """Enumerate encoding prefixes and required opaque displacement extents.

    This assembles each grammar production instead of using the production
    scanner's cursor/remaining-byte algorithm. Address-size 67 is optional;
    operand/address values do not provide exception effects.
    """
    productions = []
    for prefix in (b"", b"\x67"):
        for mod, reg, rm in itertools.product(range(4), range(8), range(8)):
            marker = prefix + b"\x0f\xb9" + bytes([(mod << 6) | (reg << 3) | rm])
            if mod == 3:
                productions.append((marker, 0))
            elif rm == 4:
                for scale, index, base in itertools.product(range(4), range(8), range(8)):
                    sib = bytes([(scale << 6) | (index << 3) | base])
                    displacement = 4 if mod == 2 or (mod == 0 and base == 5) else 1 if mod == 1 else 0
                    productions.append((marker + sib, displacement))
            else:
                displacement = 4 if mod == 2 or (mod == 0 and rm == 5) else 1 if mod == 1 else 0
                productions.append((marker, displacement))
    return productions


def ud1_extent(data):
    return any(data[:length] in LAYOUTS and len(data) == length + LAYOUTS[data[:length]]
               for length in (3, 4, 5) if length <= len(data))


def fixture(name):
    if name == "movaps-store":
        source = fixture("movaps-load")
        source["bytes"] = "0f29b42440020000"
        source["bap"].update(bytes=source["bytes"], opcode="MOVAPSmr",
                             bil=json.loads((ROOT / "tests/bap/fixtures/vector/movaps-bil.json").read_text()))
        source["reference"].update(bytes=source["bytes"], opcode="MOVAPSmr")
        return source
    row = RAW[name]
    reference = row.get("reference", {})
    return {"site": row["site"], "bytes": reference.get("bytes_hex", row["raw_bap"]["bytes"]),
            "capture_complete": True, "capture_conflict": False, "source_kind": "captured",
            "bap": deepcopy(row["raw_bap"]),
            "reference": {"bytes": reference.get("bytes_hex", row["raw_bap"]["bytes"]),
                          "site": reference.get("va", row["site"]),
                          "length": reference.get("length", row["raw_bap"]["length"]),
                          "opcode": reference.get("opcode", row["raw_bap"]["opcode"]),
                          "control": reference.get("control", "stop")}}


def mutate(value, recipes):
    for row in recipes:
        cursor = value
        for key in row["path"][:-1]:
            cursor = cursor[key]
        key = row["path"][-1]
        if row.get("action") == "delete":
            del cursor[key]
        elif row.get("action") == "append":
            cursor[key].append(deepcopy(row["value"]))
        else:
            cursor[key] = deepcopy(row["value"])


def terminal(source):
    try:
        data = bytes.fromhex(source["bytes"])
    except ValueError:
        return None, "invalid-byte-encoding"
    reference, bap = source["reference"], source["bap"]
    if (not source["capture_complete"] or source["capture_conflict"]
            or source["source_kind"] != "captured" or bap["va"] != source["site"]
            or reference["site"] != source["site"]):
        return None, "capture-or-site-binding"
    if (reference["bytes"] != source["bytes"] or reference["length"] != len(data)
            or reference["control"] != "stop"):
        return None, "reference-span-or-control"
    if bap["status"] != "decoded" or bap["properties"] != PROPERTIES:
        return None, "pinned-bap-status-or-control"
    if data == b"\xcc":
        rule, exception, opcode = "int3", 3, "INT3"
        if bap["bil"] != [{"kind": "exception", "number": 3}]:
            return None, "terminal-source-ast"
        if reference["opcode"] != "INT3":
            return None, "terminal-reference-opcode"
        consumed = data
    elif data == b"\x0f\x0b":
        rule, exception, opcode = "ud2", 6, "TRAP"
        if bap["bil"] != [] or reference["opcode"] != "TRAP":
            return None, "terminal-source-ast-or-reference"
        consumed = data
    elif ud1_extent(data):
        rule, exception, opcode = "ud1", 6, "UD2B"
        if bap["bil"] != [] or reference["opcode"] not in ("UD1Lm", "UD1Lr"):
            return None, "terminal-source-ast-or-reference"
        consumed = b"\x67\x0f\xb9" if data[0] == 0x67 else b"\x0f\xb9"
    else:
        return None, "unsupported-terminal-encoding"
    if (bap["opcode"] != opcode or bap["length"] != len(consumed)
            or bap["bytes"] != consumed.hex()):
        return None, "pinned-bap-consumed-extent"
    return {"rule": rule, "exception": exception, "normal_successors": [],
            "exception_exit": True, "resumption_outside_scope": True,
            "effects": "opaque-may-all-must-none", "scope": SCOPE,
            "bap_extent_disagreement": consumed != data}, "recognized"


def assembled_movaps(operation, bank, displacement):
    if operation not in ("load", "store") or not 0 <= bank < 16 or not -(1 << 31) <= displacement < (1 << 31):
        raise ValueError("unsupported MOVAPS description")
    prefix = b"\x44" if bank >= 8 else b""
    opcode = b"\x0f\x28" if operation == "load" else b"\x0f\x29"
    mod = 0 if displacement == 0 else 1 if -128 <= displacement <= 127 else 2
    suffix = b"" if mod == 0 else displacement.to_bytes(1 if mod == 1 else 4, "little", signed=True)
    return prefix + opcode + bytes([(mod << 6) | ((bank % 8) << 3) | 4, 0x24]) + suffix


def var_name(var):
    name = var["name"]
    width = 0 if name == "mem" else 256 if name.startswith("YMM") else 64
    expected = {"name": name, "index": 0, "virtual": False,
                "width": width, "type": "mem" if name == "mem" else "imm"}
    if var != expected or (name not in ("mem", "RSP") and name not in {f"YMM{i}" for i in range(16)}):
        raise ValueError("unmodeled variable")
    return name


def evaluate(expr, state, reads):
    kind = expr["kind"]
    if kind == "var":
        name = var_name(expr["var"])
        return state[name], expr["var"]["width"]
    if kind == "int":
        number, width = expr["value"].split(":")
        width = int(width.rstrip("us"))
        return int(number, 0) % (1 << width), width
    if kind == "load":
        if expr["mem"] != {"kind": "var", "var": {"name": "mem", "index": 0,
                "virtual": False, "width": 0, "type": "mem"}}:
            raise ValueError("load memory identity")
        address, _ = evaluate(expr["addr"], state, reads)
        reads.append((address, expr["width"]))
        return state["mem"].get((address, expr["width"]), 0), expr["width"]
    if kind == "store":
        if expr["mem"] != {"kind": "var", "var": {"name": "mem", "index": 0,
                "virtual": False, "width": 0, "type": "mem"}}:
            raise ValueError("store memory identity")
        address, _ = evaluate(expr["addr"], state, reads)
        value, width = evaluate(expr["value"], state, reads)
        if width != expr["width"]:
            raise ValueError("store width")
        memory = deepcopy(state["mem"])
        memory[address, width] = value
        return memory, 0
    if kind == "extract":
        value, _ = evaluate(expr["arg"], state, reads)
        width = expr["hi"] - expr["lo"] + 1
        return (value >> expr["lo"]) % (1 << width), width
    if kind == "concat":
        left, lw = evaluate(expr["lhs"], state, reads)
        right, rw = evaluate(expr["rhs"], state, reads)
        return (left << rw) | right, lw + rw
    if kind == "cast":
        value, width = evaluate(expr["arg"], state, reads)
        output = expr["width"]
        if expr["op"] == 1:
            value >>= width - output
        elif expr["op"] == 2 and value & (1 << (width - 1)):
            value -= 1 << width
        elif expr["op"] not in (0, 2, 3):
            raise ValueError("unsupported cast")
        return value % (1 << output), output
    if kind == "binop":
        left, lw = evaluate(expr["lhs"], state, reads)
        right, rw = evaluate(expr["rhs"], state, reads)
        if lw != rw:
            raise ValueError("operator width")
        op = expr["op"]
        if op == 5:
            return int(left == right), 1
        if op == 4:
            return int(left != right), 1
        if op == 8:
            return left & right, lw
        if op == 18:
            return (left + right) % (1 << lw), lw
        raise ValueError("unsupported operator")
    raise ValueError("unsupported expression")


def execute(statements, initial):
    state, reads, writes = deepcopy(initial), [], []
    for row in statements:
        if row["kind"] == "move":
            name = var_name(row["var"])
            value, width = evaluate(row["value"], state, reads)
            if width != row["var"]["width"]:
                raise ValueError("move width")
            state[name] = value
            writes.append(name)
        elif row["kind"] == "if":
            condition, _ = evaluate(row["condition"], state, reads)
            branch = row["yes"] if condition else row["no"]
            if branch:
                if branch != [{"kind": "exception", "number": 13}]:
                    raise ValueError("unreviewed exception arm")
                return state, reads, writes, 13
        else:
            raise ValueError("unreviewed statement")
    return state, reads, writes, None


def movaps(source, operation, bank=6, displacement=576):
    expected = assembled_movaps(operation, bank, displacement).hex()
    bap, reference = source["bap"], source["reference"]
    opcode = "MOVAPSrm" if operation == "load" else "MOVAPSmr"
    if (not source["capture_complete"] or source["capture_conflict"] or source["source_kind"] != "captured"
            or bap["va"] != source["site"] or reference["site"] != source["site"]
            or source["bytes"] != expected or reference["bytes"] != expected
            or bap["bytes"] != expected or reference["length"] != len(bytes.fromhex(expected))
            or bap["length"] != reference["length"] or bap["status"] != "decoded"
            or bap["properties"] != PROPERTIES or bap["opcode"] != opcode
            or reference["opcode"] != opcode):
        return False, "guard-bytes-or-source"
    bil = bap["bil"]
    if (len(bil) != 2 or bil[0].get("kind") != "move" or bil[1].get("kind") != "if"
            or bil[1]["yes"] != [] or bil[1]["no"] != [{"kind": "exception", "number": 13}]):
        return False, "guard-structure"
    bank_name = f"YMM{bank}"
    samples = (0, (1 << 255) | (0x123456789abcdef << 128) | 7)
    loaded = (1 << 127) | 0x112233445566778899aabbccddeeff
    try:
        for base, residue, old in itertools.product((0x10000000, (1 << 64) - 16), range(16), samples):
            rsp = base + residue
            address = (rsp + displacement) % (1 << 64)
            initial = {"RSP": rsp, bank_name: old, "mem": {(address, 128): loaded}}
            out, reads, writes, trap = execute(bil, initial)
            if trap != (None if address % 16 == 0 else 13):
                return False, "guard-predicate"
            if trap is not None:
                # A pre-exception BIL update is not a completed normal effect.
                continue
            if out["RSP"] != rsp:
                return False, "guard-rsp-effect"
            if operation == "load":
                wanted = (old & (((1 << 128) - 1) << 128)) | loaded
                if (writes != [bank_name] or out[bank_name] != wanted
                        or reads != [(address, 128)] or out["mem"] != initial["mem"]):
                    return False, "guard-load-effect"
            elif (writes != ["mem"] or reads or out[bank_name] != old
                  or out["mem"] != {(address, 128): old % (1 << 128)}):
                return False, "guard-store-effect"
    except (ValueError, KeyError, TypeError, OverflowError):
        return False, "guard-data-shape"
    return True, "recognized"


def flow(case):
    """Enumerate finite (node,RSP residue) vertices, excluding handler arcs."""
    initial = case.get("entry_residues", [8])
    if case.get("scope", SCOPE) != SCOPE or case.get("whole_machine_claim", False):
        return {"verdict": "rejected", "normal_effect": False, "reason": "invalid-normal-scope"}
    if case.get("offered_epoch", 1) != case.get("graph_epoch", 1):
        return {"verdict": "rejected", "normal_effect": False, "reason": "stale-epoch"}
    barriers = case.get("barriers", [])
    edges = [(0, 1), (1, 2), (2, 3)]
    if case.get("normal_terminal_successor", False):
        return {"verdict": "rejected", "normal_effect": False, "reason": "terminal-successor"}
    queue = deque((0, value) for value in initial)
    reached = set()
    budget = case.get("budget", 256)
    while queue:
        pair = queue.popleft()
        if pair in reached:
            continue
        if len(reached) >= budget:
            return {"verdict": "unavailable", "normal_effect": False, "reason": "work-budget"}
        reached.add(pair)
        node, residue = pair
        outputs = [(residue + case.get("prologue_delta", -8)) % 16] if node == 0 else [residue]
        for source, target in edges:
            if source == node:
                queue.extend((target, value) for value in outputs)
    values = {value for node, value in reached if node == 1}
    address_values = {(value + case.get("displacement", 576)) % 16 for value in values}
    verdict = ("unknown" if barriers else "unreached" if not values else
               "aligned" if address_values == {0} else
               "misaligned" if 0 not in address_values else "unknown")
    return {"verdict": verdict, "normal_effect": verdict == "aligned",
            "reason": "normal-completion-scope", "whole_machine_coverage": False,
            "handler_resumption_modeled": False}


def run_case(case):
    family = case["family"]
    if family == "flow":
        return flow(case["input"])
    source = fixture(case.get("fixture", "int3"))
    mutate(source, case.get("changes", []))
    if family == "terminal":
        certificate, reason = terminal(source)
        if case.get("generation", 2) == 1:
            certificate, reason = None, "legacy-terminal-unsupported"
        if case.get("guarded", True) is False:
            certificate, reason = None, "guarded-profile-required"
        return {"recognized": certificate is not None, "reason": reason,
                "barrier": certificate is None, "certificate": certificate,
                "bap_extent_disagreement": certificate["bap_extent_disagreement"] if certificate else None}
    if family == "movaps":
        recognized, reason = movaps(source, case["operation"], case.get("bank", 6),
                                    case.get("displacement", 576))
        if case.get("generation", 2) == 1 and case["operation"] == "load":
            recognized, reason = False, "legacy-load-unsupported"
        if case.get("guarded", True) is False:
            recognized, reason = False, "guarded-profile-required"
        return {"recognized": recognized, "reason": reason,
                "normal_effect_before_proof": False}
    if family == "receipt":
        certificate, _ = terminal(source)
        expected = {"kind": "checked_normal_completion", "scope": SCOPE, "epoch": 1,
                    "snapshot": "snapshot-a", "query": "query-a", "activation": 1,
                    "source_sha256": digest(source), "certificate": certificate}
        offered = deepcopy(expected)
        mutate(offered, case.get("proof_changes", []))
        accepted = certificate is not None and offered == expected and case.get("generation", 2) == 2
        return {"accepted": accepted, "reason": "accepted" if accepted else "receipt-binding-or-version"}
    raise ValueError("unknown oracle family")


def main():
    global RAW, GRAMMAR, LAYOUTS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    raw_path = HERE / "raw-bap-observations.json"
    raw = json.loads(raw_path.read_text())
    RAW = {row["id"]: row for row in raw["cases"]}
    GRAMMAR = grammar()
    LAYOUTS = dict(GRAMMAR)
    corpus_path = HERE / "oracle-cases.json"
    corpus = json.loads(corpus_path.read_text())
    results = []
    for case in corpus["cases"]:
        result = run_case(case)
        if args.check:
            for name, expected in case["expected"].items():
                if result.get(name) != expected:
                    raise SystemExit(f'{case["name"]}: {name}: {result.get(name)!r} != {expected!r}')
        results.append({"name": case["name"], "family": case["family"], **result})
    # Every assembled ModR/M/SIB production is a positive length witness.
    # A missing displacement byte is a negative witness, never zero-filled.
    generated = 0
    truncated = 0
    for prefix, displacement in GRAMMAR:
        encoded = prefix + bytes([0x12] * displacement)
        if not ud1_extent(encoded):
            raise SystemExit("generated UD1 extent rejected")
        generated += 1
        if displacement:
            if ud1_extent(encoded[:-1]):
                raise SystemExit("truncated UD1 displacement accepted")
            truncated += 1
    report = {"schema": "ariadne.caller-coverage.finite-oracle/v1", "cases": results,
              "generated_ud1_extents": generated, "truncated_ud1_extents": truncated,
              "oracle_cases_sha256": digest(corpus), "raw_bap_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
              "scope": "finite source/normal-flow controls; synthetic receipts; no universal ISA/runtime theorem"}
    if args.output:
        args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"cases": len(results), "families": sorted({row["family"] for row in results}),
                      "generated_ud1_extents": generated, "truncated_ud1_extents": truncated,
                      "checked": args.check}))


if __name__ == "__main__":
    main()
