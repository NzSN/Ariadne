#!/usr/bin/env python3
"""Independent raw-capture observer for the original finite R6 Windows case.

Run full-artifact checks on the qualification host:
  python3 tools/check_target_resolution_capture.py --dump original.dmp \
      --resolution target-resolution.json --output observer.json

The input is the bare emitted ariadne.indirect-target-resolution/v1 Report.
The original dump identity, 58-entry signed-32 table and independent 45-target
fixture are fixed here. File hashing is streamed, dump reads use seek/read,
and only one resolution report is parsed. --self-test uses tiny synthetic dumps.

Only the generic Capture minidump reader is reused from the F4 observer. Its
capture-specific entrypoint and graph/path logic are never called. This tool
independently reconstructs bytes, holes/conflicts, signed-offset arithmetic and
receipt/entry bindings. It does not evaluate BIL, prove incoming-state coverage,
replay the core, infer branch feasibility, or establish historical execution.
The report contains path roots but no request slice-seed field: the exact query
and backend execution remain bound by the separate qualification-driver receipts.
"""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import tempfile

from check_frame_path_capture import Capture


SCHEMA = "ariadne.r6-capture-observer/v1"
ARTIFACT_SHA256 = "5fea4ca614706fe0040ed3231efee0edf9ce4004a51d902bb581025b48bade08"
ARTIFACT_BYTES = 1305482568
ENTRY = 0x7FF640079640
SEED = 0x7FF640079670
DISPATCH = 0x7FF64007968B
TABLE_BASE = 0x7FF64791EF58
ENTRY_COUNT = 58
TARGET_COUNT = 45
MEMORY_PREMISE = "FrozenCapturedControlData"
U64_LIMIT = 1 << 64
CHUNK = 1024 * 1024
FIXTURE = "tests/bap/fixtures/target-resolution-table.json"
SOURCE_FILES = (
    "tools/check_target_resolution_capture.py",
    "tools/check_frame_path_capture.py",
    "src/bap/target_resolution.rs",
    "src/input/minidump.rs",
    "src/input/address_space.rs",
    "src/input/materialize.rs",
    "Specs/AriadneTargetResolution.tla",
    FIXTURE,
)


class Rejected(ValueError):
    """Capture or source-receipt check failed."""


def require(condition, message):
    if not condition:
        raise Rejected(message)


def address(value):
    return f"0x{value:016x}"


def va(value):
    require(isinstance(value, str) and re.fullmatch(r"0x[0-9a-f]{16}", value),
            f"noncanonical virtual address: {value!r}")
    return int(value, 16)


def natural(value, name):
    require(type(value) is int and 0 <= value < U64_LIMIT, f"invalid {name}")
    return value


def blob(value):
    require(isinstance(value, str) and re.fullmatch(r"(?:[0-9a-f]{2})*", value),
            "noncanonical captured byte encoding")
    return bytes.fromhex(value)


def digest(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value),
            "invalid source digest")
    return value


def stream_hash(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK), b""):
            result.update(chunk)
    return result.hexdigest()


def json_identity(value):
    result, length = hashlib.sha256(), 0
    encoder = json.JSONEncoder(ensure_ascii=False, sort_keys=True,
                               separators=(",", ":"), allow_nan=False)
    for text in encoder.iterencode(value):
        for start in range(0, len(text), CHUNK):
            part = text[start:start + CHUNK].encode("utf-8")
            result.update(part)
            length += len(part)
    return {"canonical_sha256": result.hexdigest(), "compact_bytes": length}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON member: {key}")
        result[key] = value
    return result


def invalid_constant(text):
    raise Rejected(f"nonfinite JSON number: {text}")


def load_json(path):
    with path.open(encoding="utf-8") as source:
        return json.load(source, object_pairs_hook=unique_object, parse_constant=invalid_constant)


def signature(path):
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def contributor(row):
    require(set(row) == {"stream", "entry", "file_offset"}, "invalid contributor fields")
    return (natural(row["stream"], "stream"), natural(row["entry"], "entry"),
            natural(row["file_offset"], "file offset"))


def contributor_set(rows):
    values = [contributor(row) for row in rows]
    require(len(values) == len(set(values)), "duplicate capture contributor")
    return set(values)


def contributor_rows(values):
    return [{"stream": stream, "entry": entry, "file_offset": offset}
            for stream, entry, offset in sorted(values)]


def raw_prefix(capture, start, requested):
    """Compute the exact unambiguous prefix from every overlapping mapping."""
    require(0 <= start < U64_LIMIT and 0 <= requested <= CHUNK,
            "raw prefix outside observer bound")
    data = bytearray()
    spans = []
    for index in range(requested):
        current = start + index
        if current >= U64_LIMIT:
            return bytes(data), spans, [], "AddressOverflow"
        ranges = capture.overlaps(current, current + 1)
        if not ranges:
            return bytes(data), spans, [], f"NotCaptured({current})"
        contributors = {(stream, entry, offset + current - base)
                        for base, _end, offset, stream, entry in ranges}
        require(len(contributors) == len(ranges), "duplicate raw capture mapping")
        values = {capture.read(offset, 1) for _stream, _entry, offset in contributors}
        if len(values) != 1:
            return bytes(data), spans, contributor_rows(contributors), f"ConflictingCapture({current})"
        data.extend(next(iter(values)))
        previous = spans[-1] if spans else None
        expected_next = ({(stream, entry, offset + previous["length"])
                          for stream, entry, offset in contributor_set(previous["contributors"])}
                         if previous else set())
        if previous is not None and expected_next == contributors:
            previous["length"] += 1
        else:
            spans.append({"address": address(current), "length": 1,
                          "contributors": contributor_rows(contributors)})
    return bytes(data), spans, [], "RequestedLength"


def span_identity(spans):
    result = []
    for span in spans:
        require(set(span) == {"address", "length", "contributors"}, "invalid capture span fields")
        length = natural(span["length"], "span length")
        require(length > 0, "empty capture span")
        result.append((va(span["address"]), length, frozenset(contributor_set(span["contributors"]))))
    return result


def check_data_read(capture, row):
    require(set(row) == {"address", "requested", "bytes_hex", "spans", "conflict_sources", "stop"},
            "invalid DataRead fields")
    start, requested = va(row["address"]), natural(row["requested"], "requested bytes")
    require(requested in (4, 8), "data receipt is outside relative32/pointer64 profile")
    expected = blob(row["bytes_hex"])
    require(len(expected) <= requested, "data prefix exceeds requested length")
    actual, spans, conflict, stop = raw_prefix(capture, start, requested)
    require(expected == actual, f"data-read bytes differ from original capture at {address(start)}")
    require(span_identity(row["spans"]) == span_identity(spans),
            f"data-read contributor spans differ at {address(start)}")
    require(contributor_set(row["conflict_sources"]) == contributor_set(conflict),
            f"conflicting contributor evidence differs at {address(start)}")
    require(row["stop"] == stop, f"data-read hole/conflict stop differs at {address(start)}")
    return start, requested, len(actual), len(conflict)


def relative_targets(table, base):
    require(len(table) % 4 == 0, "relative table has partial entry")
    offsets = [entry[0] for entry in struct.iter_unpack("<i", table)]
    targets = [((base + offset) % U64_LIMIT) for offset in offsets]
    return offsets, targets


def check_dispatch(row, expected):
    require(va(row["site"]) == DISPATCH, "original dispatch changed")
    require(row["complete"] is False, "original partial dispatch was promoted to complete")
    require(row["targets"] == expected, "emitted dispatch targets differ from independently read table")
    require(row["unresolved"], "original dispatch residual alternatives were removed")


def check_path_entries(resolutions, reads):
    """Check concrete entry/read arithmetic; BIL/path feasibility stays a premise."""
    counted_entries = 0
    table_indices = set()
    roots = set()
    for row in resolutions:
        site = va(row["site"])
        require(type(row["complete"]) is bool, "nonboolean completeness")
        unresolved = row["unresolved"]
        require(all(isinstance(item, str) for item in unresolved)
                and unresolved == sorted(set(unresolved)), "noncanonical unresolved alternatives")
        row_targets = [va(value) for value in row["targets"]]
        require(row_targets == sorted(set(row_targets)), "noncanonical target set")
        witnessed = set()
        words = set()
        for path in row["paths"]:
            root = va(path["root"])
            roots.add(root)
            require(root == ENTRY and not path.get("frontier", False),
                    "R6 original single-entry path root changed or local frontier added")
            reverse = [va(value) for value in path["reverse_path"]]
            directions = path["reverse_edges"]
            require(len(reverse) == len(directions) and all(type(value) is bool for value in directions),
                    "reverse-path receipt shape changed")
            require(len(reverse) == len(set(reverse)) and site not in reverse,
                    "cycle in initial-profile path receipt")
            require((reverse[-1] if reverse else site) == root, "reverse-path root binding changed")
            word = tuple(zip(reverse, directions))
            require(word not in words, "duplicate reverse-path receipt")
            words.add(word)
            form, base = path["form"], va(path["base"])
            require(form in ("relative32", "pointer64"), "unsupported R6 path form")
            width = 4 if form == "relative32" else 8
            indices = [va(value) for value in path["indices"]]
            require(indices == sorted(set(indices)), "noncanonical index set")
            if form == "pointer64":
                require(indices == [0], "pointer slot must have index zero")
            seen = set()
            for entry in path["entries"]:
                index = va(entry["index"])
                require(index in indices and index not in seen, "entry index absent or duplicated")
                seen.add(index)
                slot = (base + index * 4) % U64_LIMIT if width == 4 else base
                require(va(entry["slot"]) == slot, "entry storage address arithmetic changed")
                raw = blob(entry["bytes_hex"])
                require(len(raw) == width, "table/pointer entry is partial")
                receipt = reads.get((slot, width))
                require(receipt is not None and receipt["bytes_hex"] == entry["bytes_hex"]
                        and receipt["stop"] == "RequestedLength"
                        and not receipt["conflict_sources"], "entry has no matching complete read receipt")
                target = ((base + int.from_bytes(raw, "little", signed=True)) % U64_LIMIT
                          if width == 4 else int.from_bytes(raw, "little"))
                require(va(entry["target"]) == target, "signed table/pointer target arithmetic changed")
                witnessed.add(target)
                counted_entries += 1
                if site == DISPATCH:
                    require(form == "relative32" and base == TABLE_BASE and index < ENTRY_COUNT,
                            "original dispatch table form/base/domain changed")
                    table_indices.add(index)
            if row["complete"]:
                require(seen == set(indices) and not unresolved,
                        "complete row omits indices or retains unresolved alternatives")
        require(witnessed == set(row_targets), "published targets differ from concrete entry witnesses")
    return {"entry_witnesses": counted_entries, "table_indices": table_indices, "path_roots": roots}


def check_transfers(capture, transfers):
    seen, checked_bytes = set(), 0
    for transfer in transfers:
        site = va(transfer["site"])
        require(site not in seen, "duplicate transfer site")
        seen.add(site)
        expected = blob(transfer["bytes_hex"])
        require(1 <= len(expected) <= 15, "transfer byte extent outside AMD64 instruction prefix")
        actual, _spans, conflicts, stop = raw_prefix(capture, site, len(expected))
        require(actual == expected and stop == "RequestedLength" and not conflicts,
                f"transfer bytes differ from original capture at {address(site)}")
        require(isinstance(transfer["ast"], str), "transfer AST is not text")
        require(hashlib.sha256(transfer["ast"].encode("utf-8")).hexdigest()
                == digest(transfer["ast_sha256"]), "transfer AST hash changed")
        checked_bytes += len(expected)
    return seen, checked_bytes


def observe(capture, report, fixture):
    require(report["schema"] == "ariadne.indirect-target-resolution/v1"
            and report["profile"] == "captured-indirect-targets/v1", "outside original R6 report profile")
    require(report["artifact_sha256"] == ARTIFACT_SHA256
            and report["snapshot"] == f"minidump-captured-amd64-v1:{ARTIFACT_SHA256}",
            "resolution report belongs to another capture")
    require(report["memory_premise"] == MEMORY_PREMISE, "frozen captured-control-data premise changed")
    digest(report["graph_sha256"])
    require(fixture["schema"] == "ariadne.target-resolution-table-oracle/v1"
            and fixture["snapshot_sha256"] == ARTIFACT_SHA256
            and va(fixture["table_base"]) == TABLE_BASE and fixture["entry_count"] == ENTRY_COUNT,
            "independent table fixture scope changed")
    expected = fixture["unique_targets"]
    parsed = [va(value) for value in expected]
    require(parsed == sorted(set(parsed)) and len(parsed) == TARGET_COUNT,
            "independent fixture must contain exactly 45 sorted unique targets")
    table, table_spans, conflict, stop = raw_prefix(capture, TABLE_BASE, ENTRY_COUNT * 4)
    require(len(table) == ENTRY_COUNT * 4 and not conflict and stop == "RequestedLength",
            "original 58-entry table is not fully/unambiguously captured")
    offsets, targets_by_index = relative_targets(table, TABLE_BASE)
    targets = [address(value) for value in sorted(set(targets_by_index))]
    require(targets == expected, "independently reconstructed targets differ from fixed fixture")
    resolutions = report["resolutions"]
    sites = [va(row["site"]) for row in resolutions]
    require(len(sites) == len(set(sites)), "duplicate resolution site")
    dispatches = [row for row in resolutions if va(row["site"]) == DISPATCH]
    require(len(dispatches) == 1, "original dispatch resolution is missing or duplicated")
    dispatch = dispatches[0]
    check_dispatch(dispatch, targets)
    reads, checked_bytes, requested_bytes, partial_reads, conflict_reads = {}, 0, 0, 0, 0
    for receipt in report["data_reads"]:
        start, requested, length, conflicts = check_data_read(capture, receipt)
        require((start, requested) not in reads, "duplicate captured data-read receipt")
        reads[start, requested] = receipt
        checked_bytes += length
        requested_bytes += requested
        partial_reads += int(length != requested)
        conflict_reads += int(conflicts != 0)
    require(requested_bytes <= report["limits"]["max_read_bytes"], "read receipts exceed declared byte budget")
    for index in range(ENTRY_COUNT):
        receipt = reads.get((TABLE_BASE + 4 * index, 4))
        require(receipt is not None and receipt["bytes_hex"] == table[4 * index:4 * index + 4].hex(),
                f"original table slot {index} read receipt omitted or changed")
    witnesses = check_path_entries(resolutions, reads)
    require(witnesses["table_indices"] == set(range(ENTRY_COUNT)),
            "original dispatch entry witnesses do not cover all 58 captured slots")
    transfers, transfer_bytes = check_transfers(capture, report["transfers"])
    require(DISPATCH in transfers, "dispatch transfer instruction bytes are absent")
    require(witnesses["path_roots"] == {ENTRY}, "original entry has no bound path receipt")
    report_identity = json_identity(report)
    require(report_identity["compact_bytes"] <= report["limits"]["max_evidence_bytes"],
            "resolution report exceeds declared compact evidence budget")
    return {
        "schema": SCHEMA, "passed": True,
        "artifact_sha256": ARTIFACT_SHA256, "artifact_bytes": ARTIFACT_BYTES,
        "entry": address(ENTRY), "seed": address(SEED), "dispatch": address(DISPATCH),
        "table_base": address(TABLE_BASE), "entry_count": ENTRY_COUNT,
        "targets": targets, "target_count": len(targets), "complete": False,
        "memory_premise": MEMORY_PREMISE, "unresolved": dispatch["unresolved"],
        "table_bytes_sha256": hashlib.sha256(table).hexdigest(),
        "table_bytes_hex": table.hex(), "table_signed_offsets": offsets,
        "table_targets_by_index": [address(value) for value in targets_by_index],
        "table_capture_spans": table_spans,
        "checked_receipts": len(reads) + len(transfers),
        "checked_bytes": checked_bytes + transfer_bytes,
        "checked_data_read_receipts": len(reads), "checked_data_read_bytes": checked_bytes,
        "requested_data_read_bytes": requested_bytes,
        "checked_partial_read_receipts": partial_reads, "checked_conflicting_read_receipts": conflict_reads,
        "checked_transfer_receipts": len(transfers), "checked_transfer_bytes": transfer_bytes,
        "independent_table_bytes": len(table), "checked_entry_witnesses": witnesses["entry_witnesses"],
        "seed_transfer_present": SEED in transfers,
        "query_binding": "Entry checked against all path roots; seed selection and backend ownership require the separate driver request/execution receipts.",
        "resolution_schema": report["schema"], "resolution_profile": report["profile"],
        "resolution_graph_sha256": report["graph_sha256"],
        "resolution_content_identity": report_identity, "resolution_stop": report["stop"],
        "boundaries": [
            "All emitted control-data prefixes, spans, overlap contributors and hole/conflict stops checked against the original raw dump.",
            "Signed-32 table and pointer arithmetic checked independently; supplied BIL and incoming-state/path coverage remain trusted premises.",
            "Transfer instruction-prefix bytes and AST hashes checked; no independent decoder, instruction semantics or unwind proof.",
            "The bare report does not encode slice seeds; exact query identity and backend execution remain separate driver-receipt obligations.",
            "The 45 captured destinations do not establish exhaustive incoming coverage, branch feasibility, executed history, historical memory stability or root cause.",
            "This observer is one finite evidence tier and does not independently qualify the aggregate R6 gate.",
        ],
    }


def tiny_dump(path, ranges):
    """Synthetic MemoryList dump with explicit overlapping ranges."""
    metadata_end = 44 + 4 + 16 * len(ranges)
    raw = bytearray(metadata_end)
    struct.pack_into("<4sIIIIIQ", raw, 0, b"MDMP", 0xA793, 1, 32, 0, 0, 0)
    struct.pack_into("<III", raw, 32, 5, 4 + 16 * len(ranges), 44)
    struct.pack_into("<I", raw, 44, len(ranges))
    for index, (base, data) in enumerate(ranges):
        struct.pack_into("<QII", raw, 48 + 16 * index, base, len(data), len(raw))
        raw.extend(data)
    path.write_bytes(raw)


def self_test():
    accepted, rejected = [], []

    def rejects(label, action):
        try:
            action()
        except ValueError:
            rejected.append(label)
        else:
            raise Rejected(f"self-test corruption accepted: {label}")

    def receipt(capture, start, length):
        raw, spans, conflicts, stop = raw_prefix(capture, start, length)
        return {"address": address(start), "requested": length, "bytes_hex": raw.hex(),
                "spans": spans, "conflict_sources": conflicts, "stop": stop}

    offsets, targets = relative_targets(struct.pack("<iiii", -3, 1, 1, 7), 2)
    require(offsets == [-3, 1, 1, 7] and targets == [U64_LIMIT - 1, 3, 3, 9],
            "signed offsets, modulo arithmetic or duplicate preservation failed")
    accepted.append("independent_signed32_wrap_and_duplicates")
    with tempfile.TemporaryDirectory(prefix="ariadne-r6-observer-") as directory:
        path = Path(directory) / "tiny.dmp"
        data = struct.pack("<iiii", -1, 0, 1, -1)
        tiny_dump(path, [(TABLE_BASE, data), (TABLE_BASE, data),
                         (0x2000, struct.pack("<Q", 0xFEDCBA9876543210)), (DISPATCH, b"\xff\xe0")])
        capture = Capture(path)
        try:
            read = receipt(capture, TABLE_BASE, 4)
            check_data_read(capture, read)
            require(len(read["spans"][0]["contributors"]) == 2, "agreeing overlaps were discarded")
            accepted.append("raw_mapping_and_all_agreeing_overlap_contributors")
            omitted = copy.deepcopy(read)
            omitted["spans"][0]["contributors"].pop()
            rejects("dropped_overlap_contributor", lambda: check_data_read(capture, omitted))
            changed = copy.deepcopy(read)
            changed["bytes_hex"] = "00000000"
            rejects("changed_source_bytes", lambda: check_data_read(capture, changed))
            changed = copy.deepcopy(read)
            changed["spans"][0]["contributors"][0]["file_offset"] += 1
            rejects("changed_storage_offset", lambda: check_data_read(capture, changed))
            changed = copy.deepcopy(read)
            changed["stop"] = f"NotCaptured({TABLE_BASE + 4})"
            rejects("forged_missing_read_stop", lambda: check_data_read(capture, changed))
            pointer = receipt(capture, 0x2000, 8)
            check_data_read(capture, pointer)
            path_row = {"root": address(ENTRY), "reverse_path": [address(ENTRY)],
                        "reverse_edges": [False], "form": "relative32", "base": address(TABLE_BASE),
                        "indices": [address(0)], "entries": [{"index": address(0),
                        "slot": address(TABLE_BASE), "bytes_hex": data[:4].hex(),
                        "target": address(TABLE_BASE - 1)}]}
            row = {"site": address(DISPATCH), "complete": False, "targets": [address(TABLE_BASE - 1)],
                   "paths": [path_row], "unresolved": ["unanchored-incoming-state"]}
            check_path_entries([row], {(TABLE_BASE, 4): read})
            check_dispatch(row, [address(TABLE_BASE - 1)])
            accepted.append("entry_read_binding_and_partial_dispatch")
            wrong = copy.deepcopy(row)
            wrong["paths"][0]["entries"][0]["target"] = address(TABLE_BASE + 0xFFFFFFFF)
            rejects("unsigned_instead_of_signed_target", lambda: check_path_entries([wrong], {(TABLE_BASE, 4): read}))
            rejects("missing_entry_read_receipt", lambda: check_path_entries([row], {}))
            wrong = copy.deepcopy(row)
            wrong["complete"] = True
            rejects("promoted_original_completeness", lambda: check_dispatch(wrong, row["targets"]))
            wrong = copy.deepcopy(row)
            wrong["targets"] = []
            rejects("dropped_target", lambda: check_dispatch(wrong, row["targets"]))
            pointer_row = {"site": address(0x3000), "complete": False,
                           "targets": [address(0xFEDCBA9876543210)], "unresolved": ["unknown"],
                           "paths": [{"root": address(ENTRY), "reverse_path": [address(ENTRY)],
                           "reverse_edges": [False], "form": "pointer64", "base": address(0x2000),
                           "indices": [address(0)], "entries": [{"index": address(0),
                           "slot": address(0x2000), "bytes_hex": pointer["bytes_hex"],
                           "target": address(0xFEDCBA9876543210)}]}]}
            check_path_entries([pointer_row], {(0x2000, 8): pointer})
            accepted.append("independent_little_endian_pointer64")
            transfer = {"site": address(DISPATCH), "bytes_hex": "ffe0", "ast": "[]",
                        "ast_sha256": hashlib.sha256(b"[]").hexdigest()}
            check_transfers(capture, [transfer])
            accepted.append("transfer_prefix_and_ast_digest_binding")
            transfer["bytes_hex"] = "ffe1"
            rejects("changed_transfer_prefix", lambda: check_transfers(capture, [transfer]))
        finally:
            capture.close()
        tiny_dump(path, [(0x1000, b"ABCD"), (0x1000, b"ABXD"), (0x2000, b"XY")])
        capture = Capture(path)
        try:
            conflict = receipt(capture, 0x1000, 4)
            require(conflict["bytes_hex"] == "4142" and len(conflict["conflict_sources"]) == 2,
                    "first conflict prefix was not preserved")
            check_data_read(capture, conflict)
            accepted.append("partial_prefix_and_all_conflicting_contributors")
            changed = copy.deepcopy(conflict)
            changed["conflict_sources"].pop()
            rejects("omitted_conflicting_contributor", lambda: check_data_read(capture, changed))
            changed = copy.deepcopy(conflict)
            changed["bytes_hex"] = "41424344"
            changed["stop"] = "RequestedLength"
            changed["conflict_sources"] = []
            rejects("conflict_promoted_to_full_read", lambda: check_data_read(capture, changed))
            hole = receipt(capture, 0x2000, 4)
            check_data_read(capture, hole)
            require(hole["stop"] == f"NotCaptured({0x2002})", "hole stop not observed")
            accepted.append("explicit_capture_hole")
            hole["bytes_hex"] += "0000"
            hole["stop"] = "RequestedLength"
            rejects("hole_zero_filled", lambda: check_data_read(capture, hole))
        finally:
            capture.close()
    return {"schema": "ariadne.r6-capture-observer-self-test/v1", "passed": True,
            "accepted_controls": accepted, "rejected_corruptions": rejected,
            "original_capture_exercised": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dump", "resolution", "output"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if not args.self_test and any(getattr(args, key) is None for key in ("dump", "resolution", "output")):
        parser.error("--dump, --resolution and --output are required")
    if args.output and any(path is not None and (args.output.resolve() == path.resolve()
                           or (args.output.exists() and path.exists() and args.output.samefile(path)))
                           for path in (args.dump, args.resolution)):
        parser.error("output must not overwrite an input artifact")
    result = {"schema": SCHEMA, "passed": False}
    code = 0
    try:
        if args.self_test:
            result = self_test()
        else:
            root = Path(__file__).resolve().parent.parent
            inputs = {"dump": args.dump, "resolution": args.resolution, "fixture": root / FIXTURE}
            identities = {name: signature(path) for name, path in inputs.items()}
            require(args.dump.stat().st_size == ARTIFACT_BYTES, "original dump byte length differs")
            result["source_sha256"] = {relative: stream_hash(root / relative) for relative in SOURCE_FILES}
            result["artifacts"] = {name: {"path": str(path.resolve()), "bytes": path.stat().st_size,
                                          "sha256": stream_hash(path)} for name, path in inputs.items()}
            require(result["artifacts"]["dump"]["sha256"] == ARTIFACT_SHA256,
                    "not the original dump048B artifact")
            fixture = load_json(inputs["fixture"])
            report = load_json(args.resolution)
            capture = Capture(args.dump)
            try:
                result.update(observe(capture, report, fixture))
            finally:
                capture.close()
            require(all(signature(path) == identities[name] for name, path in inputs.items()),
                    "input artifact changed while observation was running")
    except (ValueError, KeyError, IndexError, TypeError, OSError, struct.error) as error:
        result.update({"schema": SCHEMA, "passed": False, "error": f"{type(error).__name__}: {error}"})
        code = 1
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return code


if __name__ == "__main__":
    sys.exit(main())
