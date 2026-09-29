#!/usr/bin/env python3
"""Qualify one external Chromium minidump against an independently matched build.

This is an acceptance checker for the pinned Priority 1 case, not a general
minidump reader. Ariadne's reader still receives only the dump's captured bytes.
"""

import argparse
from collections import deque
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "docs/Ariadne/priority-1-real-capture-case.json"


class CheckFailure(Exception):
    pass


def check(condition, reason):
    if not condition:
        raise CheckFailure(reason)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def number(value):
    return int(value, 16) if isinstance(value, str) else value


def read_at(data, offset, size):
    check(0 <= offset <= len(data) and 0 <= size <= len(data) - offset,
          "raw minidump range outside artifact")
    return data[offset:offset + size]


def unpack(data, fmt, offset):
    return struct.unpack(fmt, read_at(data, offset, struct.calcsize(fmt)))


def streams_of(data):
    check(data[:4] == b"MDMP", "minidump signature changed")
    count, directory = unpack(data, "<II", 8)
    check(count <= 1024, "unexpected stream count")
    out = {}
    for i in range(count):
        kind, size, offset = unpack(data, "<III", directory + i * 12)
        check(kind not in out, f"duplicate stream type {kind}")
        out[kind] = read_at(data, offset, size)
    return out


def utf16(data, offset):
    (length,) = unpack(data, "<I", offset)
    check(length <= 65536 and length % 2 == 0, "invalid module name length")
    return read_at(data, offset + 4, length).decode("utf-16-le")


def raw_capture_evidence(data, case):
    streams = streams_of(data)
    check(4 in streams and 5 in streams and 6 in streams,
          "required module, memory or exception stream missing")
    check(9 not in streams, "unexpected Memory64 stream in pinned case")

    modules = streams[4]
    (count,) = unpack(modules, "<I", 0)
    start = len(modules) - count * 108
    check(start in (4, 8), "module list has unexpected layout")
    wanted = case["companion"]
    matches = []
    for i in range(count):
        offset = start + i * 108
        base, size, _, _, name_rva = unpack(modules, "<QIIII", offset)
        name = utf16(data, name_rva)
        if Path(name).name != wanted["module_basename"]:
            continue
        cv_size, cv_rva = unpack(modules, "<II", offset + 76)
        matches.append((base, size, name, read_at(data, cv_rva, cv_size)))
    check(len(matches) == 1, "expected exactly one matching Chromium module")
    base, size, name, codeview = matches[0]
    check(base == number(wanted["module_base"]), "module base changed")
    # Crashpad's little-endian CodeViewRecordBuildID signature appears as LEpB.
    check(codeview == b"LEpB" + bytes.fromhex(wanted["build_id"]),
          "dump CodeView build ID does not match companion")

    exception = streams[6]
    thread, = unpack(exception, "<I", 0)
    code, = unpack(exception, "<I", 8)
    context_size, context_rva = unpack(exception, "<II", 160)
    context = read_at(data, context_rva, context_size)
    flags, = unpack(context, "<I", 48)
    rip, = unpack(context, "<Q", 248)
    expected = case["capture"]
    check(thread == expected["exception_thread"], "exception thread changed")
    check(code == number(expected["exception_code"]), "exception code changed")
    check(flags & 1 and rip == number(expected["rip"]), "exception RIP invalid or changed")
    check(base <= rip < base + size, "RIP is outside matched module")

    memory = streams[5]
    (count,) = unpack(memory, "<I", 0)
    start = len(memory) - count * 16
    check(start in (4, 8), "memory list has unexpected layout")
    index = expected["code_stream_entry"]
    check(index < count and expected["code_stream"] == 5,
          "captured-code descriptor missing")
    capture_start, capture_size, capture_offset = unpack(
        memory, "<QII", start + index * 16)
    check(capture_start == number(expected["code_range_start"]),
          "captured code start changed")
    check(capture_start + capture_size == number(expected["code_range_end_exclusive"]),
          "captured code end changed")
    check(capture_offset == number(expected["code_file_offset"]),
          "captured code file offset changed")
    read_at(data, capture_offset, capture_size)
    return {
        "base": base, "module_size": size, "module_name": name,
        "rip": rip, "code_start": capture_start, "code_end": capture_start + capture_size,
        "code_file_offset": capture_offset,
    }


def run_tool(args, **kwargs):
    result = subprocess.run(args, text=True, capture_output=True, timeout=120, **kwargs)
    check(result.returncode == 0,
          f"{' '.join(map(str, args[:2]))} exited {result.returncode}: "
          f"{result.stderr[-600:]}")
    return result.stdout


def companion_evidence(companion, case, raw):
    wanted = case["companion"]
    notes = run_tool(["readelf", "-n", str(companion)])
    ids = re.findall(r"Build ID:\s*([0-9a-fA-F]+)", notes)
    check(wanted["build_id"] in ids, "companion ELF build ID changed")

    symbol = wanted["function_symbol"]
    producer = subprocess.Popen(
        ["readelf", "--wide", "--syms", str(companion)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        filtered = subprocess.run(["rg", "-F", symbol], stdin=producer.stdout,
                                  text=True, capture_output=True)
    finally:
        producer.stdout.close()
    stderr = producer.stderr.read()
    check(producer.wait() == 0, f"readelf symbol scan failed: {stderr[-400:]}")
    check(filtered.returncode == 0, "matched function symbol missing")
    rows = [line.split() for line in filtered.stdout.splitlines()]
    rows = [row for row in rows if len(row) >= 8 and row[3] == "FUNC"
            and row[7] == symbol]
    check(len(rows) == 1, "matched function symbol is ambiguous")
    value, size = int(rows[0][1], 16), int(rows[0][2])
    check(value == number(wanted["function_value"]) and size == wanted["function_size"],
          "matched function range changed")

    query = case["query"]
    entry_rva, seed_rva = number(query["entry_rva"]), number(query["seed_rva"])
    check(value < entry_rva < seed_rva < value + size,
          "entry/seed are outside the matched function")
    check(raw["base"] + entry_rva == number(query["entry_va"]),
          "entry VA does not equal module base plus RVA")
    check(raw["base"] + seed_rva == raw["rip"],
          "seed VA does not equal module base plus RVA")
    check(raw["base"] + value < raw["code_start"] <= number(query["entry_va"]),
          "function-start/capture boundary relationship changed")

    output = run_tool([
        "objdump", "-d", "-M", "intel",
        f"--start-address={value:#x}",
        f"--stop-address={seed_rva + len(bytes.fromhex(query['seed_bytes_hex'])):#x}",
        str(companion),
    ])
    instructions = []
    for line in output.splitlines():
        match = re.match(r"\s*([0-9a-fA-F]+):\s+(.*)", line)
        if not match:
            continue
        code = []
        for token in match.group(2).split():
            if not re.fullmatch(r"[0-9a-fA-F]{2}", token):
                break
            code.append(int(token, 16))
        if code:
            instructions.append((int(match.group(1), 16), bytes(code)))
    check(instructions and instructions[0][0] == value,
          "forward disassembly did not begin at trusted symbol")
    for (address, encoded), (next_address, _) in zip(instructions, instructions[1:]):
        check(address + len(encoded) == next_address,
              "forward disassembly is not contiguous")
    by_rva = dict(instructions)
    check(not any(raw["code_start"] <= raw["base"] + rva < number(query["entry_va"])
                  for rva in by_rva),
          "selected entry is not the first full forward boundary in capture")
    for kind in ("entry", "producer", "seed"):
        rva = number(query[f"{kind}_rva"])
        check(by_rva.get(rva) == bytes.fromhex(query[f"{kind}_bytes_hex"]),
              f"{kind} boundary or companion bytes changed")
    return by_rva


def verify_report(report, case, raw, data, companion_instructions):
    query = case["query"]
    identity = report["identity"]
    check(report["schema"] == "ariadne-minidump-report-v1", "report schema changed")
    check(identity["artifact_sha256"] == case["capture"]["sha256"],
          "report artifact identity changed")
    check(identity["platform"] == "linux" and
          identity["decoder_target"] == "x86_64-unknown-linux-gnu",
          "report platform/target changed")
    check(report["query"]["entries"] == [query["entry_va"]] and
          report["query"]["seeds"] == [query["seed_va"]] and
          report["query"]["exception_rip_seed"],
          "report entry/exception seed changed")
    check(report["input"]["exception"]["registers"]["rip"] == query["seed_va"],
          "report exception RIP changed")

    sites = {site["va"]: site for site in report["preparation"]["sites"]}
    reads = {read["va"]: read for read in report["input"]["reads"]}
    for kind, opcode, rule in (
        ("entry", "MOV32ri", "effects-v1:MOV32ri"),
        ("producer", "MOV64rm", "effects-v1:MOV64rm"),
        ("seed", "MOV32rm", "effects-v1:MOV32rm"),
    ):
        va = query[f"{kind}_va"]
        encoded = bytes.fromhex(query[f"{kind}_bytes_hex"])
        check(sites[va]["opcode"] == opcode and sites[va]["rule"] == rule and
              sites[va]["quality"] == "reviewed" and
              sites[va]["byte_source"] == "captured" and
              bytes.fromhex(sites[va]["bytes_hex"]) == encoded,
              f"{kind} decode/effect evidence changed")
        offset = raw["code_file_offset"] + number(va) - raw["code_start"]
        check(read_at(data, offset, len(encoded)) == encoded,
              f"{kind} bytes are not in captured descriptor")
        check(companion_instructions[number(query[f"{kind}_rva"])] == encoded,
              f"{kind} companion/capture bytes disagree")
        spans = reads[va]["spans"]
        check(len(spans) == 1 and len(spans[0]["contributors"]) == 1,
              f"{kind} does not have one unambiguous captured contributor")
        contributor = spans[0]["contributors"][0]
        check(contributor["stream"] == 5 and
              contributor["entry"] == case["capture"]["code_stream_entry"] and
              number(contributor["file_offset"]) == offset,
              f"{kind} report file offset changed")

    seed_site = sites[query["seed_va"]]
    memory = seed_site["operands"][1]
    check(memory["kind"] == "memory" and memory["base"]["bank"] == 3 and
          memory["base"]["width"] == 64 and memory["access_width"] == 32,
          "seed no longer reads memory through RBX")
    reaching = next(row["definitions"] for row in report["analysis"]["reaching"]
                    if row["before"] == query["seed_va"])
    for cell in range(8):
        check({"loc": f"gpr:rbx:{cell}", "origin": "instruction",
               "site": query["producer_va"]} in reaching,
              f"RBX byte {cell} lacks the captured producer before seed")
    sliced = set(report["analysis"]["slice"])
    check({query["entry_va"], query["upstream_va"],
           query["producer_va"], query["seed_va"]} <= sliced,
          "required predecessor chain absent from slice")
    check(not report["analysis"]["missing_slice_seeds"], "seed is missing")

    edges = report["analysis"]["edges"]
    successors = {}
    for edge in edges:
        if edge["local"]:
            successors.setdefault(edge["src"], set()).add(edge["dst"])
    frontier = deque([query["entry_va"]])
    visited = set()
    while frontier:
        current = frontier.popleft()
        if current in visited:
            continue
        visited.add(current)
        frontier.extend(successors.get(current, ()))
    check(query["seed_va"] in visited, "no local graph route from entry to seed")
    check(any(site["va"] == query["entry_va"] for site in report["preparation"]["sites"]),
          "entry missing from preparation")
    check(any(site["va"] == query["seed_va"] for site in report["preparation"]["sites"]),
          "seed missing from preparation")
    check(any(site["opcode"] == "CALL64pcrel32" and
              "unsupported_semantics" in site["issues"]
              for site in report["preparation"]["sites"]),
          "opaque-call uncertainty disappeared without review")
    return {"decoded": len(report["analysis"]["decoded"]),
            "slice": len(sliced), "local_edges": sum(e["local"] for e in edges),
            "obligations": report["analysis"]["obligations"]}


def source_hashes():
    paths = set()
    for directory in ("src", "input/src", "native/llvm_mc"):
        paths.update(p for p in (ROOT / directory).rglob("*") if p.is_file())
    paths.update(ROOT / p for p in (
        "Cargo.toml", "Cargo.lock", "input/Cargo.toml", "input/Cargo.lock",
        "tools/check_priority1_real_capture.py",
        "docs/Ariadne/priority-1-real-capture-case.json",
    ))
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", type=Path, required=True)
    parser.add_argument("--companion", type=Path, required=True)
    parser.add_argument("--decoder", type=Path, required=True)
    parser.add_argument("--cli", type=Path,
                        default=ROOT / "input/target/debug/ariadne-minidump")
    parser.add_argument("--case", type=Path, default=CASE)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--validation-json", type=Path, required=True)
    parser.add_argument("--dot", type=Path, default=Path(shutil.which("dot") or "dot"))
    args = parser.parse_args()
    check(not args.report_dir.exists(), "report directory must be new")
    check(not args.validation_json.exists(), "validation JSON must be new")
    case = json.loads(args.case.read_text())
    check(case["schema"] == "ariadne-priority-1-real-capture-case-v1",
          "unknown case manifest schema")
    before = source_hashes()
    record = {"schema": "ariadne-priority-1-validation-v1",
              "recorded_utc": datetime.now(timezone.utc).isoformat(),
              "case_manifest_sha256": digest(args.case), "source_sha256": before,
              "host": platform.platform(),
              "python": sys.version.split()[0],
              "paths": {"dump": str(args.dump), "companion": str(args.companion),
                        "decoder": str(args.decoder), "cli": str(args.cli),
                        "report_dir": str(args.report_dir)},
              "passed": False}
    try:
        dump_sha256 = digest(args.dump)
        companion_sha256 = digest(args.companion)
        decoder_sha256 = digest(args.decoder)
        cli_sha256 = digest(args.cli)
        record["tool_sha256"] = {"decoder": decoder_sha256, "cli": cli_sha256}
        check(dump_sha256 == case["capture"]["sha256"] and
              args.dump.stat().st_size == case["capture"]["bytes"],
              "dump identity changed")
        check(companion_sha256 == case["companion"]["sha256"],
              "companion binary identity changed")
        data = args.dump.read_bytes()
        raw = raw_capture_evidence(data, case)
        instructions = companion_evidence(args.companion, case, raw)
        query = case["query"]
        matched = 0
        for rva, encoded in instructions.items():
            if number(query["entry_rva"]) <= rva <= number(query["seed_rva"]):
                va = raw["base"] + rva
                offset = raw["code_file_offset"] + va - raw["code_start"]
                check(va + len(encoded) <= raw["code_end"] and
                      read_at(data, offset, len(encoded)) == encoded,
                      f"captured bytes differ from forward companion at {rva:#x}")
                matched += 1
        check(matched > 1, "no captured forward instruction sequence")
        record["forward_companion_instruction_matches"] = matched
        run_tool([str(args.cli), str(args.dump), "--decoder", str(args.decoder),
                  "--entry", query["entry_va"], "--seed-exception-rip",
                  "--output-dir", str(args.report_dir)])
        report = json.loads((args.report_dir / "report.json").read_text())
        record["observations"] = verify_report(report, case, raw, data, instructions)

        text_report = (args.report_dir / "report.txt").read_text()
        dot_report = (args.report_dir / "report.dot").read_text()
        for label, body in (("text", text_report), ("dot", dot_report)):
            for expected in (case["capture"]["sha256"], query["entry_va"],
                             query["seed_va"], query["producer_va"]):
                check(expected in body, f"{label} report omits {expected}")
        for field, expected in (("decoded", report["analysis"]["decoded"]),
                                ("data_slice", report["analysis"]["slice"])):
            match = re.search(rf"^{field}: \[(.*)\]$", text_report, re.MULTILINE)
            check(match is not None and
                  re.findall(r"0x[0-9a-f]{16}", match.group(1)) == expected,
                  f"text {field} disagrees with JSON")
        dot_edges = {
            ("0x" + src, "0x" + dst, kind)
            for src, dst, kind in re.findall(
                r'n_([0-9a-f]{16}) -> n_([0-9a-f]{16}) \[label="([^"]+)"',
                dot_report,
            )
        }
        json_edges = {(edge["src"], edge["dst"], edge["kind"])
                      for edge in report["analysis"]["edges"]}
        check(dot_edges == json_edges, "DOT edges disagree with JSON")
        check(args.dot.exists() or shutil.which(str(args.dot)) is not None,
              "Graphviz dot unavailable; DOT syntax gate not run")
        record["tool_sha256"]["graphviz_dot"] = digest(args.dot)
        dot_version = subprocess.run([str(args.dot), "-V"], text=True,
                                     capture_output=True, timeout=10)
        check(dot_version.returncode == 0, "Graphviz dot version check failed")
        record["graphviz_version"] = (dot_version.stdout + dot_version.stderr).strip()
        run_tool([str(args.dot), "-Tdot", str(args.report_dir / "report.dot"),
                  "-o", str(args.report_dir / "parsed.dot")])

        negative = run_tool([str(args.cli), str(args.dump), "--decoder",
                             str(args.decoder), "--entry", query["seed_va"],
                             "--seed-exception-rip", "--format", "json"])
        seed_only = json.loads(negative)
        check(seed_only["query"]["entries"] == [query["seed_va"]] and
              query["producer_va"] not in seed_only["analysis"]["slice"],
              "seed-only negative control manufactured predecessor")
        check(seed_only["analysis"]["slice"] == [query["seed_va"]],
              "seed-only slice changed")

        check(before == source_hashes(), "source changed during acceptance run")
        check(digest(args.dump) == dump_sha256 and
              digest(args.companion) == companion_sha256 and
              digest(args.decoder) == decoder_sha256 and
              digest(args.cli) == cli_sha256,
              "artifact or tool changed during acceptance run")
        record["report_sha256"] = {
            name: digest(args.report_dir / name)
            for name in ("report.txt", "report.dot", "report.json")
        }
        record["dump_sha256"] = case["capture"]["sha256"]
        record["companion_sha256"] = case["companion"]["sha256"]
        record["build_id"] = case["companion"]["build_id"]
        record["entry_va"] = query["entry_va"]
        record["seed_va"] = query["seed_va"]
        record["graphviz_parsed"] = True
        record["seed_only_negative_passed"] = True
        record["source_stable"] = True
        record["passed"] = True
    except (CheckFailure, OSError, KeyError, ValueError, UnicodeError, StopIteration,
            subprocess.TimeoutExpired) as error:
        record["failure"] = str(error)
    args.validation_json.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(f"Priority 1 acceptance: {'PASS' if record['passed'] else 'FAIL'}")
    print(f"Validation: {args.validation_json}")
    if not record["passed"]:
        print(record["failure"], file=sys.stderr)
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
