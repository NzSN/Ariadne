#!/usr/bin/env python3
"""Freeze/check L0 loop evidence without calling Ariadne's matcher or helpers.

The fixtures are a projection of retained, source-bound JSON. This script checks
inventory and ordinary graph/arithmetic facts; it does not prove loop closure.
"""

import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EVIDENCE = Path("evidence/Ariadne/guarded-target-resolution/20261014")
PROBE = EVIDENCE / "artifacts/dump-20261014T121127"
FRAME = PROBE / "frame-1"
DUMP_SHA256 = "9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab"
CANDIDATE_SHA256 = "50b54d681fe01f9488da4cf2c90948afe52cb2ab13dad2e960bad55648122a3f"
ARCHIVE_SHA256 = "94f0881ee74fab8aa0364a485becc6db4aa7fea045833065be094f1848eab87c"
MASK64 = (1 << 64) - 1


def va(value):
    return f"0x{value:016x}"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load(relative):
    path = ROOT / relative
    with gzip.open(path, "rt") if path.suffix == ".gz" else path.open() as source:
        return json.load(source)


def identity(relative):
    path = ROOT / relative
    raw = path.read_bytes()
    result = {"path": relative.as_posix(), "sha256": digest(raw), "bytes": len(raw)}
    if path.suffix == ".gz":
        expanded = gzip.decompress(raw)
        result["uncompressed_sha256"] = digest(expanded)
        result["uncompressed_bytes"] = len(expanded)
    return result


def edges_of(instructions):
    """Read the normalized local-control fields; call targets are not local."""
    edges = []
    for source, instruction in sorted(instructions.items()):
        if instruction["kind"] in ("ordinary", "conditional", "call"):
            edges.extend({"src": source, "dst": target, "taken": False}
                         for target in instruction["fall"])
        if instruction["kind"] in ("conditional", "jump", "indirect"):
            edges.extend({"src": source, "dst": target, "taken": True}
                         for target in instruction["targets"])
    return sorted(edges, key=lambda edge: (edge["src"], edge["dst"], edge["taken"]))


def reach(start, adjacency):
    seen, pending = {start}, [start]
    while pending:
        for target in adjacency[pending.pop()]:
            if target not in seen:
                seen.add(target)
                pending.append(target)
    return seen


def scc_inventory(dispatch, instructions, edges):
    forward, backward = collections.defaultdict(list), collections.defaultdict(list)
    for edge in edges:
        forward[edge["src"]].append(edge["dst"])
        backward[edge["dst"]].append(edge["src"])
    nodes = reach(dispatch, forward) & reach(dispatch, backward)
    incoming = [edge for edge in edges if edge["src"] not in nodes and edge["dst"] in nodes]
    outgoing = [edge for edge in edges if edge["src"] in nodes and edge["dst"] not in nodes]
    return {
        "scope": "Maximal SCC of represented local candidate edges; not an invariant region.",
        "nodes": len(nodes),
        "internal_edges": sum(edge["src"] in nodes and edge["dst"] in nodes for edge in edges),
        "incoming_edges": incoming,
        "outgoing_edges": outgoing,
        "rdx_may_def_sites": sum(any(location.startswith("gpr:rdx:")
                                     for location in instructions[node]["may_defs"]) for node in nodes),
        "call_sites": sum(instructions[node]["kind"] == "call" for node in nodes),
        "memory_may_def_sites": sum("memory:any" in instructions[node]["may_defs"] for node in nodes),
    }


def check_legacy_assets():
    manifest = json.loads((HERE / "legacy-manifest.json").read_text())
    assert manifest["archive"]["sha256"] == ARCHIVE_SHA256
    record_info = manifest["qualified_source_record"]
    record_path = ROOT / record_info["path"]
    assert digest(record_path.read_bytes()) == record_info["sha256"]
    source_hashes = json.loads(record_path.read_text())
    assert len(source_hashes) == record_info["source_count"] == 711
    assert len(manifest["assets"]) == 5
    for asset in manifest["assets"]:
        raw = (HERE / asset["asset"]).read_bytes()
        assert len(raw) == asset["bytes"]
        assert digest(raw) == asset["sha256"] == source_hashes[asset["source"]]
        assert asset["asset"].endswith((".rs.txt", ".ml.txt", ".tla.txt"))
    return manifest


def construct():
    check_legacy_assets()
    report = load(FRAME / "minidump-rust.json.gz")
    composition = load(FRAME / "composition-report.json.gz")
    targets = load(FRAME / "target-report.json")
    guard = load(FRAME / "guard-report.json.gz")
    assert report["composition"] == composition
    assert report["target_resolution"] == targets
    assert report["guard_admission"] == guard
    assert composition["artifact_sha256"] == DUMP_SHA256
    assert composition["candidate_sha256"] == CANDIDATE_SHA256
    assert composition["candidate_epoch"] == 610
    instructions = {row["address"]: row for row in composition["candidate"]["instructions"]}
    sites = {row["va"]: row for row in report["preparation"]["sites"]}
    captures = {row["va"]: row for row in report["capture_sources"]}
    originals = {row["site"]: row for row in guard["input"]["sites"]}
    transfers = {row["site"]: row for row in targets["transfers"]}
    resolutions = {row["site"]: row for row in targets["resolutions"]}
    reads = {(row["address"], row["requested"]): row for row in targets["data_reads"]}
    edges = edges_of(instructions)
    plans = [
        {"id": "da09", "dispatch": 0x7FF77440DA09, "body_begin": 0x7FF77440D9EB,
         "header": 0x7FF77440D9F7, "corridor_begin": 0x7FF77440D9D6,
         "base_initializer": 0x7FF77440D9E2, "ingress_jump": 0x7FF77440D9E9,
         "base": 0x7FF77BA909A8, "targets": [0x7FF77440A451, 0x7FF77440D9EB,
                                                0x7FF77440DA0C, 0x7FF77440DA19],
         "maximal_scc_nodes": 4694},
        {"id": "dadd", "dispatch": 0x7FF77440DADD, "body_begin": 0x7FF77440DABF,
         "header": 0x7FF77440DACB, "corridor_begin": 0x7FF77440DAAA,
         "base_initializer": 0x7FF77440DAB6, "ingress_jump": 0x7FF77440DABD,
         "base": 0x7FF77BA909D0, "targets": [0x7FF77440A5DF, 0x7FF77440DABF,
                                                0x7FF77440DAE0, 0x7FF77440DAED],
         "maximal_scc_nodes": 411},
    ]
    result = {}
    for plan in plans:
        dispatch = va(plan["dispatch"])
        body = {site for site in instructions if plan["body_begin"] <= int(site, 16) <= plan["dispatch"]}
        corridor = {site for site in instructions if plan["corridor_begin"] <= int(site, 16) < plan["body_begin"]}
        assert len(body) == 9 and len(corridor) == 5
        incoming = [edge for edge in edges if edge["src"] not in body and edge["dst"] in body]
        internal = [edge for edge in edges if edge["src"] in body and edge["dst"] in body]
        outgoing = [edge for edge in edges if edge["src"] in body and edge["dst"] not in body]
        assert incoming == [{"src": va(plan["ingress_jump"]), "dst": va(plan["header"]), "taken": True}]
        assert len(internal) == 10 and len(outgoing) == 4
        assert all(instructions[site]["kind"] != "call"
                   and "memory:any" not in instructions[site]["may_defs"]
                   and not any(location.startswith("gpr:rdx:")
                               for location in instructions[site]["may_defs"]) for site in body)
        source_rows = []
        for site in sorted(body | corridor):
            original, prepared, captured = originals[site], sites[site], captures[site]
            assert not original["opaque"] and captured["captured"]
            assert original["bytes_hex"] == prepared["bytes_hex"] == captured["bytes_hex"]
            assert digest(original["ast"].encode()) == captured["ast_sha256"]
            if site in transfers:
                assert transfers[site]["ast"] == original["ast"]
                assert transfers[site]["ast_sha256"] == captured["ast_sha256"]
            source_rows.append({
                "site": site, "bytes_hex": original["bytes_hex"],
                "bytes_sha256": digest(bytes.fromhex(original["bytes_hex"])),
                "length": prepared["length"], "opcode": prepared["opcode"],
                "decoder_record": prepared["decoder_record"],
                "ast": original["ast"], "ast_sha256": captured["ast_sha256"],
                "original_control": original["control"],
                "candidate_instruction": instructions[site],
                "capture_spans": captured["spans"],
                "legacy_transfer": None if site not in transfers else {
                    key: value for key, value in transfers[site].items() if key != "ast"},
            })
        initializer = originals[va(plan["base_initializer"])]
        init_bytes = bytes.fromhex(initializer["bytes_hex"])
        assert init_bytes[:3] == bytes.fromhex("488d15") and len(init_bytes) == 7
        decoded_base = (plan["base_initializer"] + len(init_bytes)
                        + int.from_bytes(init_bytes[3:], "little", signed=True)) & MASK64
        assert decoded_base == plan["base"]
        resolution = resolutions[dispatch]
        expected_targets = sorted(map(va, plan["targets"]))
        assert resolution["targets"] == expected_targets
        assert resolution["complete"] is False
        assert resolution["unresolved"] == ["cyclic-incoming-state"]
        table_paths = [path for path in resolution["paths"] if path["form"] == "relative32"]
        assert len(table_paths) == 1
        entries = table_paths[0]["entries"]
        assert table_paths[0]["base"] == va(plan["base"])
        assert len(entries) == 10 and [int(entry["index"], 16) for entry in entries] == list(range(10))
        table_reads = []
        for entry in entries:
            index = int(entry["index"], 16)
            assert entry["slot"] == va((plan["base"] + index * 4) & MASK64)
            raw = bytes.fromhex(entry["bytes_hex"])
            assert len(raw) == 4
            assert entry["target"] == va((plan["base"] + int.from_bytes(raw, "little", signed=True)) & MASK64)
            read = reads[(entry["slot"], 4)]
            assert read["bytes_hex"] == entry["bytes_hex"]
            assert read["stop"] == "RequestedLength" and not read["conflict_sources"]
            table_reads.append(read)
        assert sorted({entry["target"] for entry in entries}) == expected_targets
        assert entries[3]["target"] == va(plan["body_begin"])
        scc = scc_inventory(dispatch, instructions, edges)
        assert scc["nodes"] == plan["maximal_scc_nodes"]
        result[f"dump-{plan['id']}.json"] = {
            "schema": "ariadne.loop-closure-dump-region-fixture/v1",
            "id": plan["id"], "provenance": "dump-provenance.json",
            "scope": "Captured candidate local phase; loop closure is not yet proved by this fixture.",
            "dispatch": dispatch, "header": va(plan["header"]),
            "region_sites": sorted(body), "entrance_corridor_sites": sorted(corridor),
            "base_initializer": va(plan["base_initializer"]), "table_base": va(plan["base"]),
            "incoming_edges": incoming, "internal_edges": internal, "outgoing_edges": outgoing,
            "corridor_edges": [edge for edge in edges if edge["src"] in corridor],
            "corridor_incoming_edges": [edge for edge in edges if edge["src"] not in corridor and edge["dst"] in corridor],
            "sources": source_rows, "table_entries": entries, "table_reads": table_reads,
            "expected_targets": expected_targets, "legacy_resolution": resolution,
            "maximal_scc_inventory": scc,
        }
    records = [FRAME / name for name in ("minidump-rust.json.gz", "composition-report.json.gz",
                                        "guard-report.json.gz", "target-report.json")]
    records.extend([EVIDENCE / "artifacts/delivery/source-files.json",
                    EVIDENCE / "artifacts/delivery/tools.json",
                    EVIDENCE / "qualification.json",
                    EVIDENCE / "artifacts/validation-20261014T120753/passing-combined-wire.json"])
    result["dump-provenance.json"] = {
        "schema": "ariadne.loop-closure-dump-provenance/v1",
        "scope": "Retained 2026-10-14 qualified baseline, not fresh loop-closure qualification.",
        "snapshot": composition["snapshot"], "artifact_sha256": DUMP_SHA256,
        "candidate_epoch": composition["candidate_epoch"],
        "candidate_sha256": composition["candidate_sha256"],
        "query_scope_sha256": composition["query_scope_sha256"],
        "composition_binding_sha256": composition["binding_sha256"],
        "composition_checker_sha256": composition["checker_sha256"],
        "composition_model_sha256": composition["model_sha256"],
        "target_report_sha256": composition["target_report_sha256"],
        "guard_report_sha256": composition["guard_report_sha256"],
        "frame_entry_points": composition["candidate"]["entry_points"],
        "guard_producer": guard["input"]["producer"],
        "legacy_source_manifest": "legacy-manifest.json",
        "retained_artifacts": [identity(record) for record in records],
        "legacy_replay": {
            "wire": (EVIDENCE / "artifacts/validation-20261014T120753/passing-combined-wire.json").as_posix(),
            "dump_report": (FRAME / "minidump-rust.json.gz").as_posix(),
            "target_report": (FRAME / "target-report.json").as_posix(),
            "note": "Use retained complete inputs for legacy replay; compact regions are evidence projections, not standalone legacy composition requests.",
        },
    }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true", help="extract the compact JSON fixtures")
    mode.add_argument("--check", action="store_true", help="check frozen assets and exact fixture projection (default)")
    args = parser.parse_args()
    expected = construct()
    for name, value in expected.items():
        target = HERE / name
        if args.write:
            target.write_text(json.dumps(value, indent=2) + "\n")
        else:
            assert json.loads(target.read_text()) == value, f"fixture drift: {target}"
    print(json.dumps({"status": "pass", "legacy_sources": 5, "qualified_source_count": 711,
                      "regions": 2, "body_sites": 18, "corridor_sites": 10,
                      "captured_table_entries": 20, "expected_targets_per_region": 4,
                      "closure_proof": "not exercised"}, sort_keys=True))


if __name__ == "__main__":
    main()
