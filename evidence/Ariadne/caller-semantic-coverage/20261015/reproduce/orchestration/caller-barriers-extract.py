#!/usr/bin/env python3
"""Extract four source-bound barrier shapes on remote WSL, without analysis."""
import argparse
import collections
import gzip
import hashlib
import json
from pathlib import Path

DUMP = "9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab"
SHAPES = [("int3", "0x00007ff77440b30d", "INT3"),
          ("ud2", "0x00007ff77440b753", "TRAP"),
          ("ud1", "0x00007ff77440b0e0", "UD1Lm"),
          ("movaps-load", "0x00007ff7744035c9", "MOVAPSrm")]


def sha(path):
    result = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def stored(run, name):
    path = run / name
    return path if path.exists() else Path(str(path) + ".gz")


def load(run, name):
    path = stored(run, name)
    with gzip.open(path, "rt") if path.suffix == ".gz" else path.open() as source:
        return json.load(source)


def number(value):
    text = str(value)
    return int(text, 16) if text.startswith("0x") else int(text, 10)


def prefix(source, site, spans, length=15):
    result = bytearray()
    for at in range(number(site), number(site) + length):
        contributors = []
        for span in spans:
            low = number(span["va"])
            if low <= at < low + span["length"]:
                for contributor in span["contributors"]:
                    source.seek(number(contributor["file_offset"]) + at - low)
                    value = source.read(1)
                    if len(value) != 1:
                        raise ValueError("captured contributor extends beyond dump")
                    contributors.append(value)
        if not contributors:
            raise ValueError("retained capture spans do not cover 15-byte prefix")
        if len(set(contributors)) != 1:
            raise ValueError("captured contributor conflict")
        result.extend(contributors[0])
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path,
                        default=Path("/loop-work/evidence/dump-20261015T051409"))
    parser.add_argument("--dump", type=Path,
                        default=Path("/work/frame-paths-dump03958-20261013/original.dmp"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    if sha(args.dump) != DUMP:
        raise SystemExit("original dump identity differs")
    provenance = {}
    for name in ("source-binding.json", "source-manifest.json", "run-result.json",
                 "frame-1/outcome.json", "frame-1/guard-report.json",
                 "frame-1/minidump-rust.json"):
        path = stored(args.run, name)
        provenance[name] = {"path": str(path), "bytes": path.stat().st_size,
                            "sha256": sha(path)}
    guard = load(args.run, "frame-1/guard-report.json")
    selected = {site for _, site, _ in SHAPES}
    sources = {row["site"]: row for row in guard["input"]["sites"] if row["site"] in selected}
    metadata = {key: guard["input"][key] for key in
                ("snapshot", "artifact_sha256", "candidate_epoch", "producer",
                 "query_scope_sha256", "barriers", "roots", "premises")}
    guard_stop = guard["stop"]
    del guard
    report = load(args.run, "frame-1/minidump-rust.json")
    captures = {row["va"]: row for row in report["capture_sources"] if row["va"] in selected}
    prepared = {row["va"]: row for row in report["preparation"]["sites"]
                if row["va"] in selected}
    all_barriers = set(metadata["barriers"])
    inventory = collections.Counter(row["opcode"] for row in report["preparation"]["sites"]
                                    if row["va"] in all_barriers)
    identity = report["identity"]
    del report
    if metadata["artifact_sha256"] != DUMP:
        raise SystemExit("guard artifact differs")
    if inventory != {"INT3": 27, "TRAP": 1, "UD1Lm": 1, "MOVAPSrm": 1}:
        raise SystemExit("frozen 30-barrier inventory differs: " + repr(inventory))
    cases = []
    with args.dump.open("rb") as dump:
        for name, site, opcode in SHAPES:
            source, capture, decoded = sources[site], captures[site], prepared[site]
            if decoded["opcode"] != opcode:
                raise SystemExit("reference opcode differs: " + site)
            ast = source["ast"]
            ast_sha = hashlib.sha256(ast.encode()).hexdigest()
            if ast_sha != capture["ast_sha256"]:
                raise SystemExit("retained BIL source identity differs: " + site)
            raw = prefix(dump, site, capture["spans"])
            if not raw.startswith(bytes.fromhex(decoded["bytes_hex"])):
                raise SystemExit("LLVM bytes differ from captured original prefix: " + site)
            bil_file = name + "-bil.json"
            (args.output / bil_file).write_text(json.dumps(json.loads(ast), indent=2) + "\n")
            cases.append({"id": name, "site": site, "expected_reference_opcode": opcode,
                          "captured_prefix": {"bytes_hex": raw.hex(), "length": len(raw),
                                              "sha256": hashlib.sha256(raw).hexdigest()},
                          "bap_original": source, "ast_sha256": ast_sha,
                          "bil_file": bil_file, "bil_file_sha256": sha(args.output / bil_file),
                          "capture": capture, "llvm_and_preparation": decoded,
                          "expected_feedback": "selected candidate guard barrier absent after correction",
                          "scope": "No claim of execution or aligned normal continuation."})
    fixture = {"schema": "ariadne.caller-barrier-reproduction/v1",
               "artifact_sha256": DUMP, "dump_path": str(args.dump),
               "origin_run": str(args.run), "origin_source_binding": load(args.run, "source-binding.json"),
               "origin_artifacts": provenance, "producer_identity": identity,
               "guard_input": metadata, "guard_stop": guard_stop,
               "barrier_inventory": dict(inventory), "cases": cases}
    (args.output / "four-shapes.json").write_text(json.dumps(fixture, indent=2) + "\n")
    print(json.dumps({"fixture": str(args.output / "four-shapes.json"), "cases": len(cases),
                      "barriers": sum(inventory.values()), "inventory": dict(inventory)}))


if __name__ == "__main__":
    main()
