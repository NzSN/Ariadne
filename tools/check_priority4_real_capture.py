#!/usr/bin/env python3
"""Qualify the pinned Windows workload using a matching PE entry witness.

The PE is evidence for entry boundaries only. The investigator CLI receives
only captured dump bytes. This checker is not an image-reader extension.
"""
import argparse
from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import sys

from check_priority1_real_capture import (CheckFailure, check, digest, number,
                                         read_at, streams_of, unpack)
from measure_priority4 import source_hashes

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "evidence/Ariadne/priority-4-real-capture-case.json"


def raw_evidence(data, case):
    streams = streams_of(data)
    check(all(kind in streams for kind in (4, 5, 6, 7)), "required stream missing")
    check(unpack(streams[7], "<H", 0)[0] == 9 and
          unpack(streams[7], "<I", 20)[0] == 2, "expected Windows AMD64")
    modules = streams[4]
    count = unpack(modules, "<I", 0)[0]
    start = len(modules) - count * 108
    check(start in (4, 8), "unexpected module layout")
    wanted = case["companion"]
    matches = []
    for i in range(count):
        offset = start + i * 108
        base, size, _, stamp = unpack(modules, "<QIII", offset)
        if base != number(wanted["module_base"]):
            continue
        cv_size, cv_rva = unpack(modules, "<II", offset + 76)
        cv = read_at(data, cv_rva, cv_size)
        check(cv[:24].hex() == wanted["rsds_hex"], "dump RSDS mismatch")
        check(size == number(wanted["image_size"]) and
              stamp == number(wanted["timestamp"]), "dump image identity mismatch")
        matches.append(base)
    check(len(matches) == 1, "expected one matched module")
    exception = streams[6]
    thread, = unpack(exception, "<I", 0)
    code, = unpack(exception, "<I", 8)
    context_size, context_rva = unpack(exception, "<II", 160)
    context = read_at(data, context_rva, context_size)
    flags, = unpack(context, "<I", 48)
    rip, = unpack(context, "<Q", 248)
    capture = case["capture"]
    check(thread == capture["exception_thread"] and
          code == number(capture["exception_code"]), "exception identity mismatch")
    check(flags & 0x100001 == 0x100001 and
          rip == number(case["query"]["seed_va"]), "invalid exception RIP")
    memory = streams[5]
    count, = unpack(memory, "<I", 0)
    start = len(memory) - count * 16
    index = capture["code_stream_entry"]
    check(start in (4, 8) and index < count, "invalid capture descriptor")
    va, size, file_offset = unpack(memory, "<QII", start + index * 16)
    check(va == number(capture["code_range_start"]) and
          va + size == number(capture["code_range_end_exclusive"]) and
          file_offset == number(capture["code_file_offset"]), "capture identity mismatch")
    return va, read_at(data, file_offset, size)


def pe_witness(data, wanted, query):
    check(data[:2] == b"MZ", "invalid PE signature")
    pe, = unpack(data, "<I", 0x3c)
    check(read_at(data, pe, 4) == b"PE\0\0", "invalid PE header")
    machine, count, stamp = unpack(data, "<HHI", pe + 4)
    optional_size, = unpack(data, "<H", pe + 20)
    optional = pe + 24
    check(machine == 0x8664 and unpack(data, "<H", optional)[0] == 0x20b,
          "expected AMD64 PE32+")
    check(0 < count <= 96 and optional_size >= 168, "invalid PE header bounds")
    check(stamp == number(wanted["timestamp"]) and
          unpack(data, "<I", optional + 56)[0] == number(wanted["image_size"]),
          "companion timestamp/image size mismatch")
    sections = []
    for i in range(count):
        size, va, raw_size, raw = unpack(data, "<IIII", optional + optional_size + i * 40 + 8)
        sections.append((va, raw_size, raw))

    def at_rva(rva, size):
        candidates = [raw + rva - va for va, length, raw in sections
                      if va <= rva and size <= length and rva - va <= length - size]
        check(len(candidates) == 1, "unmapped or ambiguous PE RVA")
        return read_at(data, candidates[0], size)

    debug_rva, debug_size = unpack(data, "<II", optional + 112 + 6 * 8)
    debug = at_rva(debug_rva, debug_size)
    check(debug_size % 28 == 0, "invalid debug directory")
    identities = []
    for i in range(debug_size // 28):
        kind, size, _, raw = unpack(debug, "<IIII", i * 28 + 12)
        if kind == 2:
            identities.append(read_at(data, raw, size)[:24].hex())
    check(wanted["rsds_hex"] in identities, "companion RSDS mismatch")
    table_rva, table_size = unpack(data, "<II", optional + 112 + 3 * 8)
    check(0 < table_size <= 12 * 1_000_000 and table_size % 12 == 0,
          "invalid runtime-function directory")
    table = at_rva(table_rva, table_size)
    begin = number(wanted["function_begin_rva"])
    end = number(wanted["function_end_rva"])
    seed = number(query["seed_rva"])
    matches = [unpack(table, "<III", i * 12) for i in range(table_size // 12)
               if unpack(table, "<II", i * 12) == (begin, end)]
    check(len(matches) == 1 and begin <= seed < end, "runtime-function witness mismatch")
    check(number(query["entry_rva"]) == begin, "entry is not the witnessed function start")
    return unpack(data, "<Q", optional + 24)[0], at_rva(begin, end - begin)


def forward_instructions(companion, image_base, case):
    begin = number(case["companion"]["function_begin_rva"])
    end = number(case["companion"]["function_end_rva"])
    result = subprocess.run(["objdump", "-d", "-w", "-z",
                             f"--adjust-vma=-{image_base}", f"--start-address={begin}",
                             f"--stop-address={end}", str(companion)],
                            capture_output=True, text=True, timeout=30, check=True)
    instructions = []
    for line in result.stdout.splitlines():
        match = re.match(r"\s*([0-9a-f]+):\s*((?:[0-9a-f]{2}\s+)+)", line)
        if match:
            instructions.append((int(match[1], 16), bytes.fromhex(match[2])))
    check(instructions and instructions[0][0] == begin and
          instructions[-1][0] + len(instructions[-1][1]) == end,
          "forward disassembly does not cover witnessed function")
    check(all(a + len(b) == c for (a, b), (c, _) in zip(instructions, instructions[1:])),
          "forward disassembly is not contiguous")
    return dict(instructions)


def qualify_report(report, case, instructions):
    query = case["query"]
    entry, seed, producer = (query[k] for k in ("entry_va", "seed_va", "producer_va"))
    check(report["identity"]["artifact_sha256"] == case["capture"]["sha256"] and
          report["identity"]["platform"] == "windows", "report identity mismatch")
    check(report["query"]["entries"] == [entry] and
          report["query"]["seeds"] == [seed] and report["query"]["exception_rip_seed"],
          "report query mismatch")
    analysis = report["analysis"]
    decoded = set(analysis["decoded"])
    check(seed in decoded and not analysis["missing_slice_seeds"], "seed not reached")
    sites = {site["va"]: site for site in report["preparation"]["sites"]}
    base = number(case["companion"]["module_base"])
    for va in decoded:
        site = sites[va]
        check(site["byte_source"] == "captured" and site["control"] is not None and
              instructions.get(number(va) - base) == bytes.fromhex(site["bytes_hex"]),
              "decoded site lacks captured forward-boundary evidence")
    check(len(decoded) >= 64, "fewer than 64 captured decoded instructions")
    successors = {}
    for edge in analysis["edges"]:
        if edge["kind"] != "call":
            successors.setdefault(edge["src"], set()).add(edge["dst"])
    def reached(start):
        visited, pending = set(), deque([start])
        while pending:
            va = pending.popleft()
            if va in visited:
                continue
            visited.add(va)
            pending.extend(successors.get(va, ()))
        return visited
    check(producer in reached(entry) and seed in reached(producer), "local route missing")
    check(number(producer) < number(seed) and producer in analysis["slice"] and
          sites[producer]["rule"] == "effects-v1:MOV64rm" and
          sites[seed]["rule"] == "effects-v1:MOV64mr", "reviewed producer/seed missing")
    before = next(row["definitions"] for row in analysis["reaching"] if row["before"] == seed)
    check(all(any(d["loc"] == f"gpr:rcx:{i}" and d["site"] == producer and
                  d["origin"] == "instruction" for d in before) for i in range(8)),
          "possible address-register origin missing")
    return {"decoded": len(decoded), "edges": len(analysis["edges"]),
            "slice": len(analysis["slice"]), "obligations": analysis["obligations"],
            "gaps": report["preparation"]["gaps"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("dump", "companion", "decoder", "cli", "report-dir", "validation-json"):
        parser.add_argument("--" + flag, type=Path, required=True)
    parser.add_argument("--case", type=Path, default=CASE)
    args = parser.parse_args()
    check(not args.report_dir.exists() and not args.validation_json.exists(),
          "output paths must be new")
    case = json.loads(args.case.read_text())
    before = source_hashes()
    record = {"schema": "ariadne-priority-4-real-capture-validation-v1", "passed": False,
              "recorded_utc": datetime.now(timezone.utc).isoformat(),
              "source_sha256": before, "case_manifest_sha256": digest(args.case),
              "dump_sha256": digest(args.dump), "companion_sha256": digest(args.companion),
              "tool_sha256": {"cli": digest(args.cli), "decoder": digest(args.decoder)},
              "entry_va": case["query"]["entry_va"], "seed_va": case["query"]["seed_va"]}
    try:
        check(record["dump_sha256"] == case["capture"]["sha256"] and
              args.dump.stat().st_size == case["capture"]["bytes"], "pinned dump mismatch")
        check(record["companion_sha256"] == case["companion"]["sha256"],
              "pinned companion mismatch")
        va, capture = raw_evidence(args.dump.read_bytes(), case)
        image_base, function = pe_witness(args.companion.read_bytes(), case["companion"],
                                         case["query"])
        entry = number(case["query"]["entry_va"])
        check(entry >= va and entry - va + len(function) <= len(capture) and
              function == capture[entry - va:entry - va + len(function)],
              "function bytes are not completely captured or differ")
        instructions = forward_instructions(args.companion, image_base, case)
        args.report_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([str(args.cli), str(args.dump), "--decoder", str(args.decoder),
                        "--entry", case["query"]["entry_va"], "--seed-exception-rip",
                        "--output-dir", str(args.report_dir)], check=True, timeout=120)
        report = json.loads((args.report_dir / "report.json").read_text())
        record["observations"] = qualify_report(report, case, instructions)
        text = (args.report_dir / "report.txt").read_text()
        dot = (args.report_dir / "report.dot").read_text()
        for field, expected in (("decoded", report["analysis"]["decoded"]),
                                ("data_slice", report["analysis"]["slice"])):
            match = re.search(rf"^{field}: \[(.*)\]$", text, re.MULTILINE)
            check(match is not None and re.findall(r"0x[0-9a-f]{16}", match[1]) == expected,
                  f"text {field} differs from JSON")
        dot_edges = {(f"0x{src}", f"0x{dst}", kind) for src, dst, kind in re.findall(
            r'n_([0-9a-f]{16}) -> n_([0-9a-f]{16}) \[label="([^"]+)"', dot)}
        check(dot_edges == {(edge["src"], edge["dst"], edge["kind"])
                            for edge in report["analysis"]["edges"]}, "DOT differs from JSON")
        subprocess.run(["dot", "-Tdot", str(args.report_dir / "report.dot"),
                        "-o", str(args.report_dir / "parsed.dot")], check=True, timeout=30)
        negative = subprocess.run([str(args.cli), str(args.dump), "--decoder", str(args.decoder),
                                   "--entry", case["query"]["seed_va"], "--seed-exception-rip",
                                   "--format", "json"], check=True, capture_output=True,
                                  text=True, timeout=120)
        check(case["query"]["producer_va"] not in
              json.loads(negative.stdout)["analysis"]["slice"],
              "seed-only run manufactured the earlier producer")
        check(before == source_hashes(), "source changed during qualification")
        check(record["dump_sha256"] == digest(args.dump) and
              record["companion_sha256"] == digest(args.companion) and
              record["tool_sha256"] == {"cli": digest(args.cli), "decoder": digest(args.decoder)},
              "artifact or tool changed during qualification")
        record.update(passed=True, source_stable=True, graphviz_parsed=True,
                      seed_only_negative_passed=True, report_identity=report["identity"],
                      forward_companion_instruction_matches=len(instructions),
                      report_sha256={name: digest(args.report_dir / name)
                                     for name in ("report.txt", "report.dot", "report.json")})
    except (CheckFailure, OSError, ValueError, subprocess.SubprocessError) as error:
        record["failure"] = str(error)
    args.validation_json.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print("Priority 4 real capture:", "PASS" if record["passed"] else "FAIL")
    print(args.validation_json)
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
