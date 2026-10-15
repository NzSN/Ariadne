#!/usr/bin/env python3
"""Independent finite MOVAPS admission oracle; no Rust/BAP evaluator is loaded.

Reachability is ordinary breadth-first search of a product graph whose vertices
are (semantic instruction VA, RSP residue).  There is no node-wise residue
worklist or dependence on the implementation's fixed-point algorithm.  Typed
transfers, source identities and closure declarations are synthetic premises,
not independently proved x86 semantics.  --check compares the whole frozen JSON;
--write deliberately regenerates it.  Neither mode builds or invokes model tools.
"""

import argparse
from collections import deque
from copy import deepcopy
import hashlib
import json
from pathlib import Path


TOP = list(range(16))
POLICY = "windows-amd64-normal-call-entry/v1"
MODEL = "ariadne.predicate-admission/v1"
BYTES = "0f29b42440020000"
ROOT = 0x1000
GUARD = 0x1100
EXIT = 0x1200


def digest(value):
    """A deterministic synthetic identity, independent of runtime codecs."""
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                    separators=(",", ":")).encode()).hexdigest()


def bindings():
    return {"snapshot": "fixture-snapshot-a", "artifact_hash": "fixture-artifact-a",
            "query": "fixture-query-a", "thread": "fixture-thread-a",
            "frame": "physical-frame-a", "platform": "windows-amd64",
            "policy": POLICY, "model": MODEL, "checker": "python-product-graph/v1",
            "helper": "fixture-pinned-helper", "runtime": "fixture-pinned-runtime",
            "decoder": "fixture-independent-control", "limits_policy": "finite-fixture/v1"}


def shape():
    return {"bytes": BYTES, "original_bil_hash": "fixture-reviewed-original-bil",
            "normal_bil_hash": "fixture-reviewed-normal-bil",
            "removed_ast_paths": ["statements/1/else/0"],
            "address_base": "RSP", "displacement": 0x240, "width": 128,
            "exception": 13, "reviewed": True}


def node(va, kind="identity", constant=0, epoch=1):
    transfer = {"kind": kind, "source_hash": f"fixture-transfer-{va:x}-{kind}"}
    if kind in ("add", "subtract"):
        transfer["constant"] = constant
    if kind == "pending-certified-identity":
        transfer["certificate"] = {
            "rule": "reviewed-movaps-rsp-identity/v1", "independent": True,
            "source_bytes": BYTES, "source_bil_hash": shape()["original_bil_hash"],
            "relation_digest": digest([[r, r] for r in TOP]), "epoch": epoch}
    return {"node": va, "transfer": transfer}


def root(va=ROOT, anchor="root-a", frame="physical-frame-a"):
    return {"node": va, "anchor": anchor, "frame": frame,
            "entry_kind": "function-entry"}


def premise(r, residues, origin="captured-register", **changes):
    result = {"root": r["anchor"], "node": r["node"], "frame": r["frame"],
              "snapshot": "fixture-snapshot-a", "query": "fixture-query-a",
              "thread": "fixture-thread-a", "origin": origin, "version": 1,
              "validated": True, "residues": residues}
    if origin == "explicit-abi-assumption":
        result["policy"] = POLICY
    result.update(changes)
    return result


def edge(source, target, kind="local"):
    return {"from": source, "to": target, "kind": kind}


def graph(nodes=None, roots=None, premises=None, edges=None, guards=None, epoch=1):
    return {"bindings": bindings(), "epoch": epoch,
            "nodes": nodes if nodes is not None else [node(GUARD, "pending-havoc")],
            "roots": roots if roots is not None else [root(GUARD)],
            "premises": premises if premises is not None else [],
            "edges": edges if edges is not None else [],
            "guards": guards if guards is not None else [{"node": GUARD, **shape()}],
            "coverage": {"closed": True, "barriers": [],
                         "exclusions": ["local-call-summary-scope", "external-reentry-not-certified"]},
            "limits": {"product_states": 4096, "transfer_evaluations": 16384}}


def seeded(residues, origin="captured-register"):
    g = graph()
    g["premises"] = [premise(g["roots"][0], residues, origin)]
    return g


def prologue(seeded_entry=True):
    vas = [ROOT + i * 8 for i in range(10)]
    nodes = [node(va, "push8") for va in vas[:8]]
    nodes += [node(vas[8], "subtract", 0x258), node(vas[9], "pending-havoc")]
    g = graph(nodes=nodes, roots=[root()],
              edges=[edge(a, b) for a, b in zip(vas, vas[1:])],
              guards=[{"node": vas[9], **shape()}])
    if seeded_entry:
        g["premises"] = [premise(g["roots"][0], [8], "explicit-abi-assumption")]
    return g


def validate(g):
    """Check premise/point contracts separately from absence of reached states."""
    ids = [n["node"] for n in g["nodes"]]
    if len(ids) != len(set(ids)) or any(not isinstance(v, int) or v < 0 or v >= 1 << 64 for v in ids):
        return "invalid-node"
    if any(e["from"] not in ids or e["to"] not in ids or
           e["kind"] not in ("local", "summary", "call") for e in g["edges"]):
        return "invalid-edge"
    roots = {r["anchor"]: r for r in g["roots"]}
    if len(roots) != len(g["roots"]) or any(r["node"] not in ids for r in roots.values()):
        return "invalid-root"
    for p in g["premises"]:
        if p["root"] not in roots:
            return "premise-not-root"
        r = roots[p["root"]]
        for field in ("snapshot", "query", "thread"):
            if p[field] != g["bindings"][field]:
                return f"premise-{field}"
        if p["node"] != r["node"]:
            return "premise-point"
        if p["frame"] != r["frame"]:
            return "premise-frame"
        if p["version"] != 1 or not p["validated"]:
            return "invalid-premise-origin"
        if not p["residues"]:
            return "empty-premise"
        if any(not isinstance(v, int) or isinstance(v, bool) or v not in TOP for v in p["residues"]):
            return "invalid-residue"
        if p["origin"] == "explicit-abi-assumption":
            if (g["bindings"]["platform"] != "windows-amd64" or
                    g["bindings"]["policy"] != POLICY or p.get("policy") != POLICY or
                    r["entry_kind"] != "function-entry" or set(p["residues"]) != {8}):
                return "premise-policy"
        elif p["origin"] not in ("captured-register", "derived-captured-unwind"):
            return "invalid-premise-origin"
    for r in roots.values():
        constraints = [set(p["residues"]) for p in g["premises"] if p["root"] == r["anchor"]]
        if constraints and not set.intersection(*constraints):
            return "inconsistent-premises"
    for guard in g["guards"]:
        if guard["node"] not in ids:
            return "invalid-guard-node"
        if {key: guard[key] for key in shape()} != shape():
            return "unsupported-guard-shape"
    for n in g["nodes"]:
        t = n["transfer"]
        if t["kind"] not in ("identity", "add", "subtract", "push8", "havoc",
                              "opaque-call", "memory-loaded-rsp", "unsupported-write",
                              "pending-havoc", "pending-certified-identity"):
            return "invalid-transfer"
        if t["kind"] in ("add", "subtract") and not 0 <= t["constant"] < 1 << 64:
            return "invalid-transfer-constant"
        if t["kind"] == "pending-certified-identity":
            expected = node(n["node"], t["kind"], epoch=g["epoch"])["transfer"]["certificate"]
            if t["certificate"] != expected or not any(q["node"] == n["node"] for q in g["guards"]):
                return "invalid-pending-transfer-certificate"
    if any(b["node"] not in ids for b in g["coverage"]["barriers"]):
        return "invalid-barrier"
    return None


def relation(transfer, residue):
    """Outgoing product-graph arcs from one residue, never a joined node set."""
    kind = transfer["kind"]
    if kind in ("identity", "pending-certified-identity"):
        return [residue]
    if kind == "add":
        return [(residue + transfer["constant"]) & 15]
    if kind == "subtract":
        return [(residue - transfer["constant"]) & 15]
    if kind == "push8":
        return [(residue - 8) & 15]
    return TOP


def root_states(g):
    pairs = set()
    for r in g["roots"]:
        constraints = [set(p["residues"]) for p in g["premises"] if p["root"] == r["anchor"]]
        values = set.intersection(*constraints) if constraints else set(TOP)
        pairs.update((r["node"], v) for v in values)
    return pairs


def solve(g):
    error = validate(g)
    if error:
        return {"status": "rejected", "error": error, "facts": [],
                "product_states": [], "guards": []}
    transfers = {n["node"]: n["transfer"] for n in g["nodes"]}
    successors = {va: [] for va in transfers}
    for e in g["edges"]:
        if e["kind"] in ("local", "summary"):
            successors[e["from"]].append(e["to"])
    for values in successors.values():
        values.sort()
    # Unknown incoming is an uncertainty injection, never a discovery root.
    starts = root_states(g)
    starts.update((b["node"], r) for b in g["coverage"]["barriers"] for r in TOP)
    queue = deque(sorted(starts))
    reached = set()
    # Zero work is an unavailable proof, including a leaf whose predicate
    # would otherwise require no outgoing product-graph arc evaluations.
    # Keep this policy separate from the BFS's incidental scheduling/counts.
    limited = any(g["limits"][counter] == 0
                  for counter in ("product_states", "transfer_evaluations"))
    evaluations = 0
    while queue and not limited:
        pair = queue.popleft()
        if pair in reached:
            continue
        if len(reached) >= g["limits"]["product_states"]:
            limited = True
            break
        reached.add(pair)
        va, residue = pair
        for successor in successors[va]:
            if evaluations >= g["limits"]["transfer_evaluations"]:
                limited = True
                break
            evaluations += 1
            queue.extend((successor, out) for out in relation(transfers[va], residue)
                         if (successor, out) not in reached)
        if limited:
            break
    complete = not limited and g["coverage"]["closed"]
    # Track barrier influence by unlabelled graph reachability, separately from
    # residue reachability, to prevent missing incoming coverage being certified.
    tainted = set(b["node"] for b in g["coverage"]["barriers"])
    queue = deque(sorted(tainted))
    while queue:
        va = queue.popleft()
        for successor in successors[va]:
            if successor not in tainted:
                tainted.add(successor)
                queue.append(successor)
    guards = []
    residuals = {"proved-aligned": "alignment-fault-refuted-under-premises",
                 "proved-misaligned": "normal-refuted-alignment-fault-possible",
                 "unknown": "normal-or-alignment-fault",
                 "unreached": "unreached-no-truth-claim",
                 "incomplete": "incomplete-no-truth-claim"}
    for q in g["guards"]:
        values = sorted(r for va, r in reached if va == q["node"])
        addresses = sorted({(r + q["displacement"]) & 15 for r in values})
        closed = complete and q["node"] not in tainted
        if not complete:
            verdict = "incomplete"
        elif not values:
            verdict = "unreached"
        elif not closed:
            verdict = "unknown"
        elif addresses == [0]:
            verdict = "proved-aligned"
        elif 0 not in addresses:
            verdict = "proved-misaligned"
        else:
            verdict = "unknown"
        admit = verdict == "proved-aligned"
        guards.append({"node": q["node"], "residues": values,
                       "address_residues": addresses, "coverage_closed": closed,
                       "verdict": verdict, "admit_normal": admit,
                       "residual": residuals[verdict], "completed_normal_store": admit,
                       "normal_may_defs": ["memory:any"] if admit else [],
                       "normal_must_defs": [], "old_memory_origin_preserved": True,
                       "fault_completed_normal_store": False})
    return {"status": "incomplete" if not complete else "complete", "error": None,
            "facts": [{"node": va, "residues": sorted(r for n, r in reached if n == va)}
                      for va in sorted(transfers)],
            "product_states": [{"node": va, "residue": r} for va, r in sorted(reached)],
            "guards": guards}


def identity(g, report):
    intent = {key: g[key] for key in ("bindings", "roots", "premises", "limits")}
    intent["seeds"] = [q["node"] for q in g["guards"]]
    candidate = {key: g[key] for key in ("nodes", "edges", "guards", "coverage")}
    request = {"snapshot": g["bindings"]["snapshot"], "roots": g["roots"],
               "selections": [{"node": q["node"], "admit_normal": q["admit_normal"]}
                              for q in report["guards"]]}
    return {"intent_id": digest(intent), "graph_hash": digest(candidate),
            "request_hash": digest(request), "epoch": g["epoch"]}


def receipt(g, report=None):
    report = solve(g) if report is None else report
    assert report["status"] == "complete"
    assert any(q["admit_normal"] for q in report["guards"])
    return {**identity(g, report), "bindings": deepcopy(g["bindings"]),
            "premises": deepcopy(g["premises"]), "roots": deepcopy(g["roots"]),
            "transfers": deepcopy(g["nodes"]), "coverage": deepcopy(g["coverage"]),
            "source_guards": deepcopy(g["guards"]), "facts": deepcopy(report["facts"]),
            "selections": deepcopy(report["guards"])}


def replay(g, proof):
    """Independently check a supplied overapproximation without trusting verdicts.

    Inclusion checks are deliberately not fact equality: a safe larger set is
    accepted when it still proves alignment.  Every candidate-only predecessor
    participates, including edges absent from a published normal request.
    """
    if validate(g):
        return False
    current = solve(g)
    if current["status"] != "complete":
        return False
    if any(proof.get(k) != v for k, v in identity(g, current).items()):
        return False
    for field, source in (("bindings", "bindings"), ("premises", "premises"),
                          ("roots", "roots"), ("transfers", "nodes"),
                          ("coverage", "coverage"), ("source_guards", "guards")):
        if proof.get(field) != g[source]:
            return False
    facts = {f["node"]: set(f["residues"]) for f in proof["facts"]}
    if len(facts) != len(proof["facts"]) or set(facts) != {n["node"] for n in g["nodes"]}:
        return False
    if any(not values <= set(TOP) for values in facts.values()):
        return False
    if any(r not in facts[va] for va, r in root_states(g)):
        return False
    if any(facts[b["node"]] != set(TOP) for b in g["coverage"]["barriers"]):
        return False
    transfers = {n["node"]: n["transfer"] for n in g["nodes"]}
    for e in g["edges"]:
        if e["kind"] in ("local", "summary"):
            if any(not set(relation(transfers[e["from"]], r)) <= facts[e["to"]]
                   for r in facts[e["from"]]):
                return False
    selections = {q["node"]: q for q in proof["selections"]}
    if len(selections) != len(proof["selections"]) or set(selections) != {q["node"] for q in g["guards"]}:
        return False
    for q in g["guards"]:
        selected = selections[q["node"]]
        if selected["admit_normal"]:
            if (not g["coverage"]["closed"] or not selected["coverage_closed"] or
                    not facts[q["node"]] or
                    {(r + q["displacement"]) & 15 for r in facts[q["node"]]} != {0} or
                    selected["verdict"] != "proved-aligned" or
                    not selected["completed_normal_store"] or
                    selected["normal_may_defs"] != ["memory:any"] or
                    selected["normal_must_defs"] or selected["fault_completed_normal_store"] or
                    not selected["old_memory_origin_preserved"]):
                return False
    # Require a real selection and the same decisions/effect scope as the graph
    # proof.  Node facts may overapproximate, the claimed effect cannot change.
    return proof["selections"] == current["guards"] and any(q["admit_normal"] for q in proof["selections"])


def contract_cases():
    cases = []

    def add(name, g, witness=None):
        expected = solve(g)
        if witness:
            for key, value in witness.items():
                actual = expected if key == "error" else expected["guards"][0]
                assert actual[key] == value, (name, key, actual[key], value)
        cases.append({"name": name, "input": g, "expected": expected})

    add("aligned-prologue-abi", prologue(), {"residues": [0], "admit_normal": True})
    add("same-prologue-unseeded", prologue(False), {"residues": TOP, "verdict": "unknown"})
    add("unseeded-root", graph(), {"residues": TOP, "admit_normal": False})
    for residue in TOP:
        add(f"direct-residue-{residue:02}", seeded([residue]),
            {"residues": [residue], "verdict": "proved-aligned" if residue == 0 else "proved-misaligned"})
    add("direct-top", seeded(TOP), {"residues": TOP, "verdict": "unknown"})
    for name, changes, error in [
            ("wrong-snapshot", {"snapshot": "fixture-snapshot-b"}, "premise-snapshot"),
            ("wrong-query", {"query": "fixture-query-b"}, "premise-query"),
            ("wrong-thread", {"thread": "fixture-thread-b"}, "premise-thread"),
            ("wrong-point", {"node": ROOT}, "premise-point"),
            ("wrong-frame-activation", {"frame": "recursive-frame-b"}, "premise-frame"),
            ("premise-is-not-a-root", {"root": "slice-seed-only"}, "premise-not-root"),
            ("unvalidated-premise", {"validated": False}, "invalid-premise-origin"),
            ("wrong-origin-version", {"version": 2}, "invalid-premise-origin"),
            ("empty-premise", {"residues": []}, "empty-premise"),
            ("invalid-residue", {"residues": [16]}, "invalid-residue")]:
        g = seeded([0])
        g["premises"][0].update(changes)
        add(name, g, {"error": error})
    g = seeded([8], "explicit-abi-assumption")
    g["bindings"]["policy"] = "not-opted-in"
    add("wrong-abi-policy", g, {"error": "premise-policy"})
    g = seeded([8], "explicit-abi-assumption")
    g["bindings"]["platform"] = "linux-amd64"
    add("wrong-abi-platform", g, {"error": "premise-policy"})
    g = seeded([8], "explicit-abi-assumption")
    g["roots"][0]["entry_kind"] = "resume-point"
    add("abi-resume-is-not-entry", g, {"error": "premise-policy"})
    g = seeded([0])
    g["premises"].append(premise(g["roots"][0], [8]))
    add("conflicting-premises", g, {"error": "inconsistent-premises"})
    g = seeded([0, 8])
    g["premises"].append(premise(g["roots"][0], [0]))
    add("consistent-premise-intersection", g, {"residues": [0], "admit_normal": True})
    a, b = root(ROOT), root(ROOT + 8, "root-b")
    joined = graph(nodes=[node(ROOT), node(ROOT + 8), node(GUARD, "pending-havoc")],
                   roots=[a, b], premises=[premise(a, [0]), premise(b, [8])],
                   edges=[edge(ROOT, GUARD), edge(ROOT + 8, GUARD)])
    add("mixed-roots", joined, {"residues": [0, 8], "verdict": "unknown"})
    g = deepcopy(joined)
    g["premises"].pop()
    add("additional-unseeded-root", g, {"residues": TOP, "verdict": "unknown"})
    for kind in ("havoc", "opaque-call", "memory-loaded-rsp", "unsupported-write"):
        g = graph(nodes=[node(ROOT, kind), node(GUARD, "pending-havoc")],
                  roots=[a], premises=[premise(a, [0])],
                  edges=[edge(ROOT, GUARD, "summary" if kind == "opaque-call" else "local")])
        add(kind, g, {"residues": TOP, "verdict": "unknown"})
    g = graph(nodes=[node(ROOT, "opaque-call"), node(GUARD, "pending-havoc"), node(EXIT)],
              roots=[a], premises=[premise(a, [0])],
              edges=[edge(ROOT, GUARD, "call"), edge(ROOT, EXIT, "summary")])
    add("call-edge-visible-not-followed", g, {"residues": [], "verdict": "unreached"})
    for kind, expected in [("pending-havoc", TOP), ("pending-certified-identity", [0])]:
        g = graph(nodes=[node(GUARD, kind)], edges=[edge(GUARD, GUARD)])
        g["premises"] = [premise(g["roots"][0], [0])]
        add(f"loop-{kind}", g, {"residues": expected,
                                "admit_normal": kind == "pending-certified-identity"})
    g = graph(nodes=[node(ROOT, "add", 1), node(GUARD, "pending-certified-identity")],
              roots=[a], premises=[premise(a, [0])],
              edges=[edge(ROOT, GUARD), edge(GUARD, ROOT)])
    add("loop-changing-rsp", g, {"residues": TOP, "verdict": "unknown"})
    for kind in ("pending-havoc", "pending-certified-identity"):
        second = GUARD + 8
        g = graph(nodes=[node(GUARD, kind), node(second, "pending-havoc")],
                  edges=[edge(GUARD, second)], guards=[{"node": GUARD, **shape()}, {"node": second, **shape()}])
        g["premises"] = [premise(g["roots"][0], [0])]
        add(f"two-guards-{kind}", g, {"residues": [0], "admit_normal": True})
        assert cases[-1]["expected"]["guards"][1]["residues"] == (TOP if kind == "pending-havoc" else [0])
    g = seeded([0])
    g["coverage"]["barriers"] = [{"node": GUARD, "reason": "unresolved-indirect-reentry"}]
    add("unresolved-incoming-barrier", g, {"residues": TOP, "coverage_closed": False, "verdict": "unknown"})
    g = graph(nodes=[node(ROOT), node(GUARD, "pending-havoc"), node(EXIT)],
              roots=[a], premises=[premise(a, [0])], edges=[edge(ROOT, EXIT)])
    add("unreached-guard-no-vacuous-proof", g, {"residues": [], "admit_normal": False, "verdict": "unreached"})
    g = seeded([0])
    g["limits"]["product_states"] = 0
    add("zero-budget", g, {"residues": [], "verdict": "incomplete", "admit_normal": False})
    g = prologue()
    g["limits"]["transfer_evaluations"] = 0
    add("zero-transfer-budget", g, {"residues": [], "verdict": "incomplete"})
    # These independent witnesses explicitly prevent a zero counter from
    # proving either alignment at a reached leaf or unreachability elsewhere.
    for counter, label in (("product_states", "product-state"),
                           ("transfer_evaluations", "transfer")):
        g = seeded([0])
        assert not g["edges"]
        g["limits"][counter] = 0
        add(f"zero-{label}-budget-aligned-leaf", g,
            {"residues": [], "verdict": "incomplete", "admit_normal": False})
        assert cases[-1]["expected"]["status"] == "incomplete"
        a = root(ROOT)
        g = graph(nodes=[node(ROOT), node(GUARD, "pending-havoc")],
                  roots=[a], premises=[premise(a, [0])], edges=[])
        g["limits"][counter] = 0
        add(f"zero-{label}-budget-unreached-guard", g,
            {"residues": [], "verdict": "incomplete", "admit_normal": False})
        assert cases[-1]["expected"]["status"] == "incomplete"
    g = seeded([0])
    g["coverage"]["closed"] = False
    add("prefix-not-closed", g, {"residues": [0], "verdict": "incomplete", "admit_normal": False})
    return cases


def evolution_cases():
    initial = graph(nodes=[node(ROOT), node(ROOT + 8), node(GUARD, "pending-havoc")],
                    roots=[root(ROOT), root(ROOT + 8, "root-b")],
                    edges=[edge(ROOT, GUARD)])
    initial["premises"] = [premise(initial["roots"][0], [0]), premise(initial["roots"][1], [8])]
    proof = receipt(initial)
    incoming = deepcopy(initial)
    incoming["epoch"] = 2
    incoming["edges"].append(edge(ROOT + 8, GUARD))
    initial_root = deepcopy(initial)
    initial_root["roots"].pop()
    initial_root["premises"].pop()
    proof_root = receipt(initial_root)
    cases = []
    for name, before, after, old in [("late-incoming-edge", initial, incoming, proof),
                                     ("late-root-and-incoming", initial_root, incoming, proof_root)]:
        old_ok = replay(after, old)
        assert not old_ok and solve(before)["guards"][0]["admit_normal"]
        assert solve(after)["guards"][0]["residues"] == [0, 8]
        cases.append({"name": name, "initial": before, "final": after,
                      "expected_initial": solve(before), "expected_final": solve(after),
                      "initial_receipt": old, "old_receipt_accepted": old_ok})
    epoch = seeded([0])
    old = receipt(epoch)
    changed = deepcopy(epoch)
    changed["epoch"] = 2
    assert not replay(changed, old)
    cases.append({"name": "epoch-only-invalidates-receipt", "initial": epoch, "final": changed,
                  "expected_initial": solve(epoch), "expected_final": solve(changed),
                  "initial_receipt": old, "old_receipt_accepted": False})
    return cases


def receipt_cases():
    g = prologue()
    good = receipt(g)
    cases = [{"name": "valid-aligned-receipt", "input": g, "receipt": good, "accepted": True}]
    assert replay(g, good)
    for field in ("intent_id", "graph_hash", "request_hash", "epoch"):
        bad = deepcopy(good)
        bad[field] = 2 if field == "epoch" else "tampered"
        assert not replay(g, bad)
        cases.append({"name": f"tampered-{field}", "input": g, "receipt": bad, "accepted": False})
    for field in bindings():
        bad = deepcopy(good)
        bad["bindings"][field] = "tampered"
        assert not replay(g, bad)
        cases.append({"name": f"tampered-binding-{field}", "input": g, "receipt": bad, "accepted": False})
    for field in ("premises", "roots", "transfers", "coverage", "source_guards"):
        bad = deepcopy(good)
        bad[field] = {} if field == "coverage" else []
        assert not replay(g, bad)
        cases.append({"name": f"missing-{field}", "input": g, "receipt": bad, "accepted": False})
    for field, value in [("normal_must_defs", ["memory:any"]), ("normal_may_defs", []),
                         ("fault_completed_normal_store", True), ("old_memory_origin_preserved", False),
                         ("verdict", "unknown"), ("coverage_closed", False)]:
        bad = deepcopy(good)
        bad["selections"][0][field] = value
        assert not replay(g, bad)
        cases.append({"name": f"tampered-effect-{field}", "input": g, "receipt": bad, "accepted": False})
    for name, va in [("omitted-root-state", ROOT), ("omitted-candidate-predecessor-state", g["guards"][0]["node"])]:
        bad = deepcopy(good)
        next(f for f in bad["facts"] if f["node"] == va)["residues"] = []
        assert not replay(g, bad)
        cases.append({"name": name, "input": g, "receipt": bad, "accepted": False})
    bad = deepcopy(good)
    bad["facts"][-1]["residues"] = [0, 8]
    assert not replay(g, bad)
    cases.append({"name": "forged-all-aligned-verdict", "input": g, "receipt": bad, "accepted": False})
    # A disconnected node may have extra states: replay checks inclusion rather
    # than insisting a receipt contain the least fixed point.
    over = seeded([0])
    over["nodes"].append(node(EXIT))
    larger = receipt(over)
    next(f for f in larger["facts"] if f["node"] == EXIT)["residues"] = TOP
    assert replay(over, larger)
    cases.append({"name": "safe-overapproximation-at-disconnected-node", "input": over,
                  "receipt": larger, "accepted": True})
    return cases


def numeric_cases():
    # Compute expected residues from explicit 64-bit integer execution, whereas
    # product arcs above work directly on low-four-bit residues.
    constants = [*TOP, 0x240, 0x258, (1 << 64) - 1, 1 << 63, (1 << 64) - 16]
    cases = []
    mask = (1 << 64) - 1
    for kind in ("add", "subtract"):
        for r in TOP:
            for c in constants:
                # Multiple high bits independently check that low residues do
                # not depend on unrepresented full-width values.
                results = {((base + c if kind == "add" else base - c) & mask) % 16
                           for base in (r, (1 << 63) + r, mask - 15 + r)}
                assert len(results) == 1
                expected = sorted(results)
                assert relation({"kind": kind, "constant": c}, r) == expected
                cases.append({"kind": kind, "residue": r, "constant": c, "expected": expected})
    for r in TOP:
        for kind, expected in (("identity", [r]), ("push8", [(r - 8) % 16]), ("havoc", TOP)):
            assert relation({"kind": kind}, r) == expected
            cases.append({"kind": kind, "residue": r, "expected": expected})
    return cases


def contract():
    return {"schema": "ariadne.guard-admission-contract/v1", "model": MODEL,
            "oracle": "Independent BFS over explicit (semantic VA, residue) product vertices",
            "domain": TOP, "normal_admission": "nonempty, all aligned, all candidate incoming closed",
            "zero_work_budget_policy": "Either finite work counter being zero prevents completion and normal admission, including leaf and unreached guards",
            "scope": "Synthetic finite analysis contract; not lifting or architectural ISA qualification",
            "identity_scope": "Synthetic canonical JSON hashes; runtime/native codec hashes are separate evidence",
            "cases": contract_cases(), "evolution_cases": evolution_cases(),
            "receipt_cases": receipt_cases(), "numeric_cases": numeric_cases()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="compare all frozen expectations without writing")
    mode.add_argument("--write", action="store_true", help="deliberately regenerate frozen contract.json")
    args = parser.parse_args()
    data = contract()
    text = json.dumps(data, indent=2) + "\n"
    path = Path(__file__).with_name("contract.json")
    if args.write:
        path.write_text(text)
    else:
        if not path.exists() or path.read_text() != text:
            raise SystemExit("frozen independent guard contract differs; use --write only for a reviewed freeze")
    print(f"Independent guard oracle PASS: {len(data['cases'])} graph/premise cases, "
          f"{len(data['evolution_cases'])} closure histories, {len(data['receipt_cases'])} receipt cases, "
          f"{len(data['numeric_cases'])} finite transfer cases")


if __name__ == "__main__":
    main()
