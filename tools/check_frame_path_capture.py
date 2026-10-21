#!/usr/bin/env python3
"""Independent, capture-bound observer for the original dump03958 F4 question.

Run on the qualification host, not on the memory-constrained coordinator:
  python3 tools/check_frame_path_capture.py --native native.json --rust rust.json \
      --dump original.dmp --output observer.json

Only one report is parsed at a time. The dump is hashed sequentially and read
with bounded seek/read operations. Recovery is a Python least closure of the
Source/CanDecode/LocalEdges/DecodeObligations/Visit rules in Specs/Ariadne.tla;
neither an Ariadne executable nor a published recovery result supplies it.

Normalized summaries and BAP admission are premises, not an independent ISA or
BIL proof. This observer checks capture mappings, bytes, activation bindings,
the complete recovered local topology, preserved gaps, and every actual listed
path. It does not independently interpret Windows unwind programs, reproduce
the enumerator's scheduling/counters, establish feasibility or executed history,
or qualify F4's other validation tiers. BFS measures represented reachability;
its result is never substituted for an enumerated path.

--diagnostic-allow-empty retains all checks but permits zero paths and explicitly
fails the positive gate. It alone permits omission of --rust; that records parity
as unexercised. Distinct report files do not prove which backend ran: execution
ownership requires the separate driver receipts. --expected-report-sha256 pins
the raw native report, not its timing-normalized digest.

The accepted input profile is the exact emitted Rust v7 artifacts, identified
by their recorded raw file digests. Scope, chain and path hashes below retain
the emitted Rust struct-member order. Reordered/reserialized JSON is outside
this observer profile; general report replay belongs to its separate validator.
Normalized-request pins and report parity use compact, sorted-member JSON.
--self-test uses tiny constructed inputs only.
"""

import argparse
from bisect import bisect_left
from collections import Counter, defaultdict, deque
import gc
import hashlib
import json
from pathlib import Path
import re
import struct
import sys
import tempfile


DUMP_SHA256 = "9be21e47453fec954857db52db7dfe3b8c5a5c6a49369d39a10eb701de9624ab"
# Canonical encode_request bytes in the retained S6 manifest:
# the explicit input reports, which are validated against the live capture.
S6_NORMALIZED_SHA256 = {
    0: "9de5f240615225de915605c7af0b76c31dbc67ba9d82061522b77c2328c22a4f",
    1: "6b5afebea31cff34103ddb38e4bf795ce63660eb9eb375804aff8a340a4bed22",
}
MEMORY_PREMISE = "FrozenCapturedControlData"
BASE_PREMISES = [
    "Structural alternatives under captured frame, decoded-control and unwind/Windows ABI premises; no executed history or selected writer",
    "Opaque summary steps retain unknown callee interiors; an incomplete path list never excludes a memory writer",
]
THREAD = 23668
ROOTS = {0: 0x7FF77443D960, 1: 0x7FF7744033A0}
ACTIVE_CALL = 0x7FF774404108
CALL_BYTES = "e853980300"
RETURN_PC = 0x7FF77440410D
RETURN_SLOT = 0xBEA89FA928
FAULT_PC = 0x7FF77443DD6E
STACKS = {0: 0xBEA89FA890, 1: 0xBEA89FA930}
CHUNK = 1024 * 1024
U64_LIMIT = 1 << 64
EDGE_ORDER = {k: i for i, k in enumerate(
    ("next", "taken", "fallthrough", "jump", "indirect", "summary", "call"))}
REASON_ORDER = {k: i for i, k in enumerate(
    ("Unavailable", "DecodeFailed", "IndirectTargets", "CallTargets"))}
BUDGET_GAPS = {"path-step-budget", "scanned-edge-budget", "loop-visit-budget",
               "frontier-byte-budget"}


class Rejected(ValueError):
    """An independent observation failed; never downgraded to a warning."""


def require(condition, message):
    if not condition:
        raise Rejected(message)


def va(value):
    require(isinstance(value, str) and re.fullmatch(r"0x[0-9a-f]{16}", value),
            f"noncanonical virtual address: {value!r}")
    return int(value, 16)


def address(value):
    return f"0x{value:016x}"


def natural(value, label):
    require(type(value) is int and value >= 0, f"invalid {label}")
    return value


def digest(value):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value),
            "invalid SHA-256")
    return value


def blob(value):
    require(isinstance(value, str) and re.fullmatch(r"(?:[0-9a-f]{2})*", value),
            "noncanonical evidence bytes")
    return bytes.fromhex(value)


def file_hash(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK), b""):
            result.update(chunk)
    return result.hexdigest()


def json_hash(value, *, canonical=False):
    """No serialized copy of a large report is retained."""
    result = hashlib.sha256()
    encoder = json.JSONEncoder(ensure_ascii=False, separators=(",", ":"),
                               sort_keys=canonical, allow_nan=False)
    for text in encoder.iterencode(value):
        for offset in range(0, len(text), CHUNK):
            result.update(text[offset:offset + CHUNK].encode("utf-8"))
    return result.hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON member {key}")
        result[key] = value
    return result


def load_report(path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream, object_pairs_hook=unique_object,
                         parse_constant=lambda text: (_ for _ in ()).throw(
                             Rejected(f"nonfinite JSON number {text}")))


def parity_hash(report):
    # Only this exact top-level field is ignored. Nested timing is evidence.
    natural(report["elapsed_ms"], "elapsed_ms")
    return json_hash({key: value for key, value in report.items() if key != "elapsed_ms"},
                     canonical=True)


def distinct_parity_inputs(native, rust):
    """Equal bytes are allowed; reusing the same filesystem object is not."""
    require(native.resolve() != rust.resolve() and not native.samefile(rust),
            "native/Rust parity inputs refer to the same artifact (path or inode)")


def node(row):
    require(set(row) == {"frame", "site"}, "invalid path-node fields")
    return natural(row["frame"], "frame index"), va(row["site"])


def edge(row):
    require(set(row) == {"src", "dst", "kind"}, "invalid path-edge fields")
    require(row["kind"] in EDGE_ORDER, "unknown edge kind")
    return node(row["src"]), node(row["dst"]), row["kind"]


def edge_key(row):
    return row[0], row[1], EDGE_ORDER[row[2]]


def address_set(values, label):
    parsed = [va(value) for value in values]
    require(parsed == sorted(set(parsed)), f"noncanonical address set: {label}")
    return set(parsed)


def request_fingerprint(request):
    """Bind the supplied normalized effects too; no effect inference is done."""
    locations = request["locations"]
    require(all(isinstance(item, str) for item in locations)
            and locations == sorted(set(locations)), "noncanonical location domain")
    location_set = set(locations)
    rows = []
    previous = -1
    for row in request["instructions"]:
        site = va(row["address"])
        require(site > previous, "noncanonical instruction ordering")
        previous = site
        for field in ("uses", "may_defs", "must_defs"):
            values = row[field]
            require(all(isinstance(item, str) for item in values)
                    and values == sorted(set(values)) and set(values) <= location_set,
                    f"noncanonical instruction effect set {field}")
        require(set(row["must_defs"]) <= set(row["may_defs"]), "must-def outside may-def")
        rows.append({"va": row["address"], "kind": row["kind"].capitalize(),
                     "fall": [va(item) for item in row["fall"]],
                     "targets": [va(item) for item in row["targets"]],
                     "complete": row["targets_complete"], "uses": row["uses"],
                     "may": row["may_defs"], "must": row["must_defs"]})
    payload = {"snapshot": request["snapshot"], "locations": locations,
               "input": "Dump", "instructions": rows}
    for output, source in (("addresses", "addresses"), ("entries", "entry_points"),
                           ("seeds", "slice_seeds"), ("captured", "captured"),
                           ("file", "file_backed"), ("fallback", "trusted_fallback"),
                           ("decodable", "decodable")):
        payload[output] = [va(item) for item in request[source]]
    return json_hash(payload, canonical=True)


def recover(request, frame, frame_index):
    """Least local closure, independent of Rust's traversal and dataflow."""
    require(request["input_kind"] == "dump", "original input must be a dump")
    sets = {key: address_set(request[key], key) for key in (
        "addresses", "entry_points", "slice_seeds", "captured", "file_backed",
        "trusted_fallback", "decodable")}
    domain = sets["addresses"]
    require(sets["entry_points"], "empty entry roots")
    require(all(values <= domain for values in sets.values()), "address domain mismatch")
    require(not sets["file_backed"] and not sets["trusted_fallback"],
            "original capture-only contract changed")
    rows = {}
    for row in request["instructions"]:
        site = va(row["address"])
        require(site not in rows, "duplicate instruction")
        fall = address_set(row["fall"], "fall")
        targets = address_set(row["targets"], "targets")
        kind = row["kind"]
        require(kind in {"ordinary", "conditional", "jump", "indirect", "call",
                         "return", "stop"}, "unknown instruction kind")
        require(type(row["targets_complete"]) is bool, "nonboolean completeness")
        require(fall <= domain and targets <= domain, "successor outside domain")
        require(len(fall) == (1 if kind in {"ordinary", "conditional", "call"} else 0),
                "continuation cardinality changed")
        require(kind not in {"ordinary", "return", "stop"} or not targets,
                "terminal/ordinary target set changed")
        require(kind not in {"conditional", "jump"} or len(targets) == 1,
                "direct target cardinality changed")
        rows[site] = (kind, fall, targets, row["targets_complete"])
    require(set(rows) == domain, "instruction domain mismatch")
    pending = list(sets["entry_points"])
    visited, decoded, local_edges, obligations = set(), set(), set(), set()
    while pending:
        site = pending.pop()
        if site in visited:
            continue
        visited.add(site)
        if site not in sets["captured"]:
            obligations.add((site, "Unavailable"))
            continue
        if site not in sets["decodable"]:
            obligations.add((site, "DecodeFailed"))
            continue
        decoded.add(site)
        kind, fall, targets, complete = rows[site]
        if not complete and kind in {"indirect", "call"}:
            obligations.add((site, "IndirectTargets" if kind == "indirect" else "CallTargets"))
        destinations = []
        if kind == "ordinary":
            destinations = [(target, "next") for target in fall]
        elif kind == "conditional":
            destinations = ([(target, "taken") for target in targets]
                            + [(target, "fallthrough") for target in fall])
        elif kind in {"jump", "indirect"}:
            destinations = [(target, kind) for target in targets]
        elif kind == "call":
            destinations = [(target, "summary") for target in fall]
        for target, edge_kind in destinations:
            local_edges.add((site, target, edge_kind))
            if target not in visited:
                pending.append(target)
    low = va(frame["function_begin"]) if frame["function_begin"] is not None else 0
    high = va(frame["function_end"]) if frame["function_end"] is not None else U64_LIMIT
    require(low < high, "empty function extent")
    published_nodes = {site for site in decoded if low <= site < high}
    published_edges = {((frame_index, source), (frame_index, target), kind)
                       for source, target, kind in local_edges
                       if source in published_nodes and target in published_nodes}
    obligations = sorted(obligations, key=lambda pair: (pair[0], REASON_ORDER[pair[1]]))
    gaps = [f"{address(site)}:recovery:{reason}" for site, reason in obligations]
    gaps += [f"{address(site)}:missing-seed" for site in sorted(sets["slice_seeds"] - decoded)]
    gaps += [f"Obligation {{ site: {site}, reason: {reason} }}" for site, reason in obligations]
    if any(low <= source < high and not low <= target < high
           for source, target, _kind in local_edges):
        gaps.append("local-edge-outside-frame-function")
    return {"nodes": published_nodes, "edges": published_edges, "gaps": gaps,
            "rows": rows, "sets": sets, "visited": len(visited),
            "decoded": len(decoded), "obligations": len(obligations)}


class Capture:
    """Minimal independent minidump directory/capture index, backed by seek/read."""

    def __init__(self, path):
        self.stream = path.open("rb")
        self.size = path.stat().st_size
        self.checked_bytes = 0
        self.checked_receipts = 0
        self.streams, self.ranges, self.threads, self.modules = {}, [], {}, []
        header = self.read(0, 32)
        require(header[:4] == b"MDMP", "not a minidump")
        count, directory = struct.unpack_from("<II", header, 8)
        require(count <= 65536, "directory observer bound exceeded")
        for index in range(count):
            kind, size, offset = struct.unpack("<III", self.read(directory + 12 * index, 12))
            require(offset + size <= self.size, "stream outside artifact")
            if kind in {3, 4, 5, 6, 7, 9, 16}:
                require(kind not in self.streams, "duplicate supported minidump stream")
                self.streams[kind] = (offset, size)
        for kind in (3, 4, 5):
            if kind not in self.streams:
                continue
            offset, size = self.streams[kind]
            count = struct.unpack("<I", self.read(offset, 4))[0]
            stride = {3: 48, 4: 108, 5: 16}[kind]
            padding = size - count * stride
            require(padding in (4, 8), "invalid minidump list shape")
            require(count <= 2_000_000, "list observer bound exceeded")
            for index in range(count):
                row = self.read(offset + padding + index * stride, stride)
                if kind == 3:
                    tid = struct.unpack_from("<I", row)[0]
                    require(tid not in self.threads, "duplicate dump thread")
                    self.threads[tid] = row
                    base, length, backing = struct.unpack_from("<QII", row, 24)
                    self.add_range(base, length, backing, kind, index)
                elif kind == 5:
                    base, length, backing = struct.unpack("<QII", row)
                    self.add_range(base, length, backing, kind, index)
                else:
                    base, length, checksum, timestamp = struct.unpack_from("<QIII", row)
                    self.modules.append({"base": address(base), "size": length,
                                         "timestamp": timestamp, "checksum": checksum})
        if 9 in self.streams:
            offset, size = self.streams[9]
            count, backing = struct.unpack("<QQ", self.read(offset, 16))
            require(16 + 16 * count == size and count <= 2_000_000,
                    "invalid memory64 list or observer bound")
            for index in range(count):
                base, length = struct.unpack("<QQ", self.read(offset + 16 + 16 * index, 16))
                self.add_range(base, length, backing, 9, index)
                backing += length
        self.ranges.sort()
        self.starts = [row[0] for row in self.ranges]
        self.max_ends = []
        largest = 0
        for row in self.ranges:
            largest = max(largest, row[1])
            self.max_ends.append(largest)

    def read(self, offset, length):
        require(0 <= offset <= self.size and 0 <= length <= CHUNK,
                "raw read outside observer bound")
        require(offset + length <= self.size, "raw read outside artifact")
        self.stream.seek(offset)
        result = self.stream.read(length)
        require(len(result) == length, "short artifact read")
        return result

    def add_range(self, base, length, offset, stream, entry):
        require(base + length <= U64_LIMIT and offset + length <= self.size,
                "invalid capture mapping")
        if length:
            self.ranges.append((base, base + length, offset, stream, entry))

    def overlaps(self, low, high):
        index = bisect_left(self.starts, high) - 1
        found = []
        while index >= 0 and self.max_ends[index] > low:
            row = self.ranges[index]
            if row[1] > low:
                found.append(row)
            index -= 1
        return found

    def match_hex(self, offset, expected_hex):
        for start in range(0, len(expected_hex), 2 * CHUNK):
            expected = blob(expected_hex[start:start + 2 * CHUNK])
            require(self.read(offset + start // 2, len(expected)) == expected,
                    f"source bytes differ at file offset {offset + start // 2:#x}")
            self.checked_bytes += len(expected)

    def check_spans(self, start, bytes_hex, spans, *, exact=False):
        require(len(bytes_hex) % 2 == 0, "odd evidence byte string")
        end = start + len(bytes_hex) // 2
        require(end <= U64_LIMIT, "evidence address overflow")
        cursor = start
        for span in spans:
            low, length = va(span["va"]), natural(span["length"], "span length")
            high = low + length
            require(length > 0 and high <= U64_LIMIT, "empty or overflowing span")
            if exact:
                require(low == cursor and high <= end, "noncontiguous receipt spans")
            if high <= cursor or low >= end:
                continue
            require(low <= cursor, "uncovered evidence bytes")
            part_end = min(high, end)
            observed = self.overlaps(cursor, part_end)
            require(observed, "published bytes are not captured")
            require(all(base <= cursor and limit >= part_end
                        for base, limit, *_ in observed), "span crosses contributor boundary")
            actual = {(stream, entry, offset + cursor - base)
                      for base, _limit, offset, stream, entry in observed}
            listed = {(natural(c["stream"], "capture stream"),
                       natural(c["entry"], "capture entry"),
                       va(c["file_offset"]) + cursor - low)
                      for c in span["contributors"]}
            require(len(listed) == len(span["contributors"]) and listed == actual,
                    "capture contributors/mappings changed or conflicting source omitted")
            segment = bytes_hex[2 * (cursor - start):2 * (part_end - start)]
            for _stream, _entry, offset in sorted(actual):
                self.match_hex(offset, segment)
            cursor = part_end
        require(cursor == end, "capture spans do not cover source bytes")
        self.checked_receipts += 1

    def close(self):
        self.stream.close()


def check_activation(graph, chain):
    index = graph["frame"]
    frame = chain["frames"][index]
    proof = graph["guard_admission"]
    inputs = proof["report"]["input"]
    activation = {"thread_id": THREAD,
                  "frame_activation": f'{chain["chain_id"]}:{index}:{frame["sp"]}'}
    require(inputs["activation"] == activation, "wrong frame activation")
    require(inputs["snapshot"] == chain["snapshot_id"]
            and inputs["artifact_sha256"] == chain["artifact_sha256"],
            "guard source belongs to another capture")
    require(len(inputs["roots"]) == 1
            and inputs["roots"][0]["site"] == graph["entry"]
            and inputs["roots"][0]["function_entry"] is True, "wrong guard entry root")
    premises = inputs["premises"]
    require(len(premises) == 1, "normal-call premise missing or added")
    premise = premises[0]
    require(premise["origin"] == "abi_normal_call"
            and premise["policy"] == "windows-amd64-normal-call-entry/v1"
            and premise["activation"] == activation
            and premise["snapshot"] == chain["snapshot_id"]
            and premise["root"] == graph["entry"]
            and premise["point"] == graph["entry"]
            and premise["query_scope_sha256"] == inputs["query_scope_sha256"]
            and premise["rsp_residues"] == 1 << 8 and premise["rsp_value"] is None,
            "normal-call premise binding changed or additional alignment hypothesis introduced")


def rust_debug_string(value):
    # Scope is the emitted source diagnostic strings, not arbitrary Rust values.
    # Rust Debug and JSON agree on this explicitly admitted ASCII vocabulary.
    require(isinstance(value, str)
            and all(32 <= ord(char) < 127 or char in "\n\r\t" for char in value),
            "source premise diagnostic outside emitted ASCII profile")
    return json.dumps(value, ensure_ascii=False)


def expected_source_premises(graphs):
    """Reconstruct every append_guard_premises entry from retained sources."""
    result = list(BASE_PREMISES)
    for graph in graphs:
        index = graph["frame"]
        proof = graph["guard_admission"]
        guard = proof["report"]
        inputs = guard["input"]
        normal = inputs.get("normal_flow")
        require(isinstance(normal, dict) and normal["scope"] == "local-normal-completion/v1"
                and normal["kind"] == "local_normal_completion",
                "original local-normal-flow premise omitted or changed")
        result.append(f'frame-{index}: normal-flow-scope {normal["scope"]}; exception-exit; '
                      'exception-resumption-outside-local-scope; exceptional effects unsupported')
        composition, target = proof.get("composition"), proof.get("target_resolution")
        require(isinstance(composition, dict) and isinstance(target, dict),
                "original composed target premise omitted")
        require(target["memory_premise"] == MEMORY_PREMISE,
                "frozen captured-control-data premise omitted or changed")
        result.append(f'frame-{index}: composition {composition["profile"]} proof '
                      f'{composition["binding_sha256"]}; target profile {target["profile"]}; '
                      f'premise {target["memory_premise"]}: captured control data is interpreted '
                      'as frozen; no historical memory stability or executed path is inferred')
        for row in target["resolutions"]:
            unresolved = row["unresolved"]
            require(unresolved == sorted(set(unresolved)), "noncanonical unresolved target set")
            reason = "{" + ", ".join(rust_debug_string(item) for item in unresolved) + "}"
            require(type(row["complete"]) is bool, "nonboolean target completeness")
            complete = "true" if row["complete"] else "false"
            result.append(f'frame-{index}: indirect {row["site"]}: {len(row["targets"])} targets; '
                          f'complete={complete}; unresolved={reason}')
        stop = "None" if target["stop"] is None else f'Some({rust_debug_string(target["stop"])})'
        result.append(f"frame-{index}: target resolution stopped: {stop}")
        for premise in inputs["premises"]:
            result.append(f'frame-{index}: assumed {premise["policy"]}: entry RSP mod 16 = 8 '
                          f'at {premise["point"]}; activation {premise["activation"]["frame_activation"]}; '
                          f'evidence {premise["evidence_sha256"]}')
        for decision in guard["guards"]:
            verdict = decision["verdict"]
            require(verdict in {"aligned", "misaligned", "unknown", "unreached"},
                    "unknown guard verdict")
            result.append(f'frame-{index}: guard {decision["site"]} {verdict.capitalize()}; '
                          f'{decision["residual"]}; proof {decision["receipt_sha256"]}')
        if guard["stop"] is not None:
            result.append(f'frame-{index}: guard admission stopped: {guard["stop"]}')
    return result


def check_source_premises(report, graphs):
    expected = expected_source_premises(graphs)
    require(report["premises"] == expected,
            "generated source premise omitted, changed or additional hypothesis introduced")
    return len(expected)


def check_chain(chain, capture):
    expected_snapshot = f"minidump-captured-amd64-v1:{DUMP_SHA256}"
    require(chain["artifact_sha256"] == DUMP_SHA256
            and chain["snapshot_id"] == expected_snapshot and chain["thread_id"] == THREAD,
            "original capture/thread scope changed")
    require(chain["profile"] == "captured-windows-amd64-unwind-v1", "unwind profile changed")
    require(len(chain["frames"]) >= 2, "physical frame 1 unavailable")
    seed = chain["seed"]
    require(seed["artifact_sha256"] == DUMP_SHA256
            and seed["snapshot_id"] == expected_snapshot
            and seed["thread_id"] == THREAD and seed["artifact_bytes"] == capture.size
            and seed["platform"] == "windows-amd64", "frame seed identity changed")
    thread = capture.threads.get(THREAD)
    require(thread is not None and blob(seed["thread_record_hex"]) == thread,
            "frame seed thread record differs from original dump")
    context_kind = 3
    context_size, context_offset = struct.unpack_from("<II", thread, 40)
    if 6 in capture.streams:
        offset, size = capture.streams[6]
        require(size == 168, "invalid exception stream")
        exception = capture.read(offset, size)
        if struct.unpack_from("<I", exception)[0] == THREAD:
            context_kind = 6
            context_size, context_offset = struct.unpack_from("<II", exception, 160)
    require(context_size >= 1232 and seed["context_stream"] == context_kind
            and seed["context_offset"] == context_offset, "captured context descriptor changed")
    require(len(seed["context_hex"]) == 2464, "frame context extent changed")
    capture.match_hex(context_offset, seed["context_hex"])
    context = capture.read(context_offset, 1232)
    require(struct.unpack_from("<Q", context, 248)[0] == FAULT_PC
            and struct.unpack_from("<Q", context, 152)[0] == STACKS[0],
            "original fault context PC/SP changed")
    require(seed["modules"] == capture.modules, "frame seed module table changed")
    require(chain["frames"][0]["return_slot"] == address(RETURN_SLOT)
            and chain["frames"][0]["return_pc"] == address(RETURN_PC),
            "captured return anchor changed")
    for index in (0, 1):
        frame = chain["frames"][index]
        require(frame["index"] == index and va(frame["sp"]) == STACKS[index]
                and va(frame["pc"]) == (FAULT_PC if index == 0 else RETURN_PC)
                and va(frame["function_begin"]) == ROOTS[index],
                f"physical frame {index} anchor changed")
    require(STACKS[1] == RETURN_SLOT + 8, "return stack continuation mismatch")
    found_return = False
    requested = 0
    for receipt in chain["reads"]:
        start = va(receipt["address"])
        length = natural(receipt["requested"], "unwind requested bytes")
        require(len(receipt["bytes_hex"]) // 2 <= length, "unwind receipt exceeds request")
        capture.check_spans(start, receipt["bytes_hex"], receipt["spans"], exact=True)
        requested += length
        if start <= RETURN_SLOT and RETURN_SLOT + 8 <= start + len(receipt["bytes_hex"]) // 2:
            offset = 2 * (RETURN_SLOT - start)
            require(int.from_bytes(blob(receipt["bytes_hex"][offset:offset + 16]), "little")
                    == RETURN_PC, "captured return slot differs from continuation")
            found_return = True
    require(found_return, "return-slot read receipt missing")
    # A failed budget request is charged before its receipt is added; report that
    # accounting boundary without claiming to independently replay the unwinder.
    require(requested <= chain["read_bytes"], "unwind read accounting below receipts")
    saved = chain["chain_id"]
    digest(saved)
    chain["chain_id"] = ""
    try:
        require(json_hash(chain) == saved, "frame-chain binding changed")
    finally:
        chain["chain_id"] = saved
    return {"reads": len(chain["reads"]), "receipt_requested_bytes": requested,
            "reported_charged_bytes": chain["read_bytes"], "return_slot_verified": True}


def compare_graph(graph, recovered):
    actual_nodes = [va(n["evidence"]["va"]) for n in graph["nodes"]]
    require(actual_nodes == sorted(recovered["nodes"]), "published recovered node domain changed")
    actual_edges = [edge(e) for e in graph["edges"]]
    require(actual_edges == sorted(recovered["edges"], key=edge_key),
            "published recovered typed edges changed")
    require(graph["gaps"] == recovered["gaps"], "published recovery gaps dropped or changed")


def check_graph(graph, chain, capture):
    index = graph["frame"]
    frame = chain["frames"][index]
    require(index in ROOTS and va(graph["entry"]) == ROOTS[index], "original graph root changed")
    identity = graph["identity"]
    require(identity["snapshot_id"] == chain["snapshot_id"]
            and identity["artifact_sha256"] == DUMP_SHA256, "graph capture identity changed")
    digest(identity["query_id"])
    digest(identity["request_sha256"])
    check_activation(graph, chain)
    proof = graph["guard_admission"]
    request = proof["normalized"]
    require(request["snapshot"] == chain["snapshot_id"]
            and request["entry_points"] == [graph["entry"]], "normalized root/snapshot changed")
    normalized_sha = json_hash(request, canonical=True)
    require(normalized_sha == S6_NORMALIZED_SHA256[index],
            f"frame {index} normalized request differs from pinned S6 source")
    require(proof["target_resolution"]["memory_premise"] == MEMORY_PREMISE,
            "frozen captured-control-data premise changed")
    recovered = recover(request, frame, index)
    require(request_fingerprint(request) == identity["request_sha256"],
            "normalized request fingerprint changed")
    compare_graph(graph, recovered)
    sources = {va(s["va"]): s for s in proof["sites"]}
    require(len(sources) == len(proof["sites"]) and set(sources) == recovered["sets"]["addresses"],
            "complete capture source domain changed")
    for site, source in sources.items():
        require(type(source["captured"]) is bool, "nonboolean captured marker")
        require(len(source["bytes_hex"]) <= 30, "instruction evidence exceeds AMD64 extent")
        blob(source["bytes_hex"])
        if source["bytes_hex"]:
            require(source["captured"], "instruction bytes lack captured provenance")
            capture.check_spans(site, source["bytes_hex"], source["spans"])
        if site in recovered["sets"]["captured"]:
            require(source["captured"] and source["bytes_hex"],
                    "normalized captured instruction lacks captured bytes")
    raw_sites = proof["report"]["input"]["sites"]
    raw_domain = set()
    for raw in raw_sites:
        site = va(raw["site"])
        require(site not in raw_domain and site in sources, "raw proof site domain changed")
        raw_domain.add(site)
        require(raw["bytes_hex"] == sources[site]["bytes_hex"], "raw proof source bytes changed")
        if raw["bytes_hex"]:
            require(hashlib.sha256(raw["ast"].encode()).hexdigest() == sources[site]["ast_sha256"],
                    "raw proof AST hash changed")
    for published in graph["nodes"]:
        site = va(published["evidence"]["va"])
        source = sources[site]
        require(published["evidence"] == source, "published node differs from full source evidence")
        kind, fall, targets, _complete = recovered["rows"][site]
        require(published["call"] == (kind == "call")
                and published["fall"] == [address(v) for v in sorted(fall)]
                and published["targets"] == [address(v) for v in sorted(targets)],
                "published node control differs from normalized request")
        require(va(frame["function_begin"]) <= site
                and site + len(source["bytes_hex"]) // 2 <= va(frame["function_end"]),
                "published instruction crosses function extent")
    summary = {"frame": index, "visited": recovered["visited"],
               "decoded_before_function_filter": recovered["decoded"],
               "nodes": len(recovered["nodes"]), "edges": len(recovered["edges"]),
               "obligations": recovered["obligations"], "source_gaps": len(recovered["gaps"]),
               "source_sites": len(sources), "query_id": identity["query_id"],
               "request_sha256": identity["request_sha256"],
               "pinned_s6_normalized_sha256": S6_NORMALIZED_SHA256[index],
               "source_digests": {key: json_hash(proof[key], canonical=True)
                                  for key in ("normalized", "sites", "report", "composition",
                                              "target_resolution") if key in proof}}
    return recovered, summary


def compose(graphs, recovered):
    caller = graphs[1]
    candidates = []
    for published in caller["nodes"]:
        evidence = published["evidence"]
        raw = blob(evidence["bytes_hex"])
        if not (published["call"] and evidence["captured"] and len(raw) == 5 and raw[0] == 0xE8):
            continue
        site = va(evidence["va"])
        continuation = site + 5
        target = (continuation + int.from_bytes(raw[1:], "little", signed=True)) % U64_LIMIT
        if (continuation == RETURN_PC and target == ROOTS[0]
                and published["fall"] == [address(continuation)]
                and published["targets"] == [address(target)]):
            candidates.append(published)
    require(len(candidates) == 1, "missing or ambiguous E8 captured activation")
    active = candidates[0]["evidence"]
    require(va(active["va"]) == ACTIVE_CALL and active["bytes_hex"] == CALL_BYTES,
            "original active-call encoding changed")
    start, end = (1, ACTIVE_CALL), (0, FAULT_PC)
    require(ACTIVE_CALL in recovered[1]["nodes"]
            and ROOTS[0] in recovered[0]["nodes"]
            and FAULT_PC in recovered[0]["nodes"], "captured endpoints not independently recovered")
    edges = set(recovered[0]["edges"])
    edges.update(e for e in recovered[1]["edges"] if e[0] != start)
    edges.add((start, (0, ROOTS[0]), "call"))
    gaps = set()
    for index, graph in graphs.items():
        gaps.update(f"frame-{index}:{gap}" for gap in recovered[index]["gaps"])
        for published in graph["nodes"]:
            source = published["evidence"]
            gaps.update(f'frame-{index}:{source["va"]}:{gap}' for gap in source["gaps"])
    return start, end, edges, gaps


def check_paths(report, start, end, edges, required_gaps, allow_empty):
    paths = report["paths"]
    count = natural(report["returned_count"], "returned_count")
    require(count == len(paths), "returned path count differs from actual listing")
    require((0 if allow_empty else 1) <= count < report["question"]["np"] == 10,
            "strict positive F4 path count 1..9 was not met")
    limits = report["limits"]
    gaps = report["gaps"]
    require(gaps == sorted(set(gaps)), "listing gaps are not canonical")
    require(required_gaps <= set(gaps), "source gap dropped from listing")
    require(set(gaps) - required_gaps <= BUDGET_GAPS, "unexplained listing gap")
    seen = set()
    lengths = []
    for path in paths:
        nodes = [node(n) for n in path["nodes"]]
        steps = [edge(e) for e in path["edges"]]
        require(nodes and nodes[0] == start and nodes[-1] == end, "wrong listed path endpoints")
        require(len(steps) + 1 == len(nodes), "listed path step count changed")
        require(len(nodes) <= limits["max_path_steps"], "listed path exceeds step limit")
        require(max(Counter(nodes).values()) <= limits["max_node_visits"],
                "listed path exceeds loop-visit limit")
        for index, step in enumerate(steps):
            require(step in edges and step[:2] == (nodes[index], nodes[index + 1]),
                    "listed step is not an independently recovered typed edge")
        require(sum(step[2] == "call" for step in steps) == 1
                and steps[0] == (start, (0, ROOTS[0]), "call"),
                "listed path crosses a different activation")
        require(path["contains_opaque_summary"] is any(s[2] == "summary" for s in steps),
                "opaque-summary marker changed")
        identity = tuple(steps)
        require(identity not in seen, "duplicate typed path")
        seen.add(identity)
        expected_id = json_hash([report["scope_id"], [path["nodes"], path["edges"]]])
        require(path["path_id"] == expected_id, "listed path binding changed")
        lengths.append(len(steps))
    for key in ("available", "truncated", "enumeration_exhausted"):
        require(type(report[key]) is bool, f"nonboolean {key}")
    require(report["available"], "original captured frame path query is unavailable")
    exhausted = report["enumeration_exhausted"]
    stopped = report["truncated"] or report["stop_reason"] != "frontier-exhausted"
    if stopped:
        require(not exhausted and report["coverage"] == "partial",
                "cutoff credited as exhaustive or complete")
    if gaps:
        require(report["coverage"] == "partial", "source gaps credited as complete coverage")
    if exhausted:
        require(report["frontier_count"] == 0 and not report["truncated"]
                and report["stop_reason"] == "frontier-exhausted",
                "invalid exhausted-enumeration claim")
    require(report["coverage"] == ("complete_within_declared_scope"
                                    if exhausted and not gaps else "partial"),
            "coverage claim does not preserve uncertainty")
    counters = report["counters"]
    for counter, limit in (("expanded_states", "max_search_states"),
                           ("scanned_edges", "max_scanned_edges"),
                           ("peak_frontier_bytes", "max_frontier_bytes"),
                           ("retained_path_bytes", "max_output_bytes")):
        require(natural(counters[counter], counter) <= limits[limit], "search counter exceeds limit")
    require(counters["expanded_states"] >= count, "paths exceed expanded states")
    require(any("no executed history or selected writer" in p for p in report["premises"])
            and any("incomplete path list never excludes a memory writer" in p
                    for p in report["premises"]), "candidate/history boundary premise removed")
    return {"returned_count": count, "listed_edge_lengths": lengths,
            "positive_gate_passed": count > 0,
            "coverage": report["coverage"], "stop_reason": report["stop_reason"],
            "truncated": report["truncated"], "enumeration_exhausted": exhausted,
            "required_source_gaps": len(required_gaps), "listing_gaps": len(gaps),
            "exhaustive_paths_credited": False, "candidate_exclusions_credited": False}


def bfs(start, end, edges, max_nodes, max_edges):
    outgoing = defaultdict(list)
    for source, target, _kind in sorted(edges, key=edge_key):
        outgoing[source].append(target)
    distance = {start: 0}
    queue = deque([start])
    scanned = 0
    while queue:
        current = queue.popleft()
        if current == end:
            return {"connection": "found", "shortest_edges": distance[current],
                    "shortest_nodes": distance[current] + 1,
                    "visited": len(distance), "scanned_edges": scanned, "cutoff": False}
        for target in outgoing[current]:
            if scanned >= max_edges or (target not in distance and len(distance) >= max_nodes):
                return {"connection": "unknown_observer_budget", "shortest_edges": None,
                        "visited": len(distance), "scanned_edges": scanned, "cutoff": True}
            scanned += 1
            if target not in distance:
                distance[target] = distance[current] + 1
                queue.append(target)
    return {"connection": "absent_in_represented_graph", "shortest_edges": None,
            "visited": len(distance), "scanned_edges": scanned, "cutoff": False}


def observe(report, capture, allow_empty, max_bfs_nodes, max_bfs_edges):
    require(report["schema"] == "ariadne.frame-paths/v7", "expected independent graph-policy v7")
    require(report["question"] == {"from_frame": 1, "to_frame": 0, "np": 10},
            "original physical frame 1-to-0/NP=10 question changed")
    inputs, limits = report["input"], report["limits"]
    for key, value in limits.items():
        natural(value, key)
    policy = inputs["graph_limits"]
    require(set(policy) == {"max_graph_nodes", "max_graph_edges"}, "graph policy fields changed")
    for key, value in policy.items():
        natural(value, key)
    require(json_hash([inputs, report["question"], limits]) == report["scope_id"],
            "report scope binding changed")
    chain = inputs["chain"]
    unwind = check_chain(chain, capture)
    graphs = {g["frame"]: g for g in inputs["graphs"]}
    require(len(graphs) == len(inputs["graphs"]) and set(graphs) == {0, 1},
            "original graph activation domain changed")
    premise_count = check_source_premises(report, inputs["graphs"])
    recovered, summaries = {}, []
    for index, graph in sorted(graphs.items()):
        recovered[index], summary = check_graph(graph, chain, capture)
        summaries.append(summary)
    total_nodes = sum(len(r["nodes"]) for r in recovered.values())
    total_edges = sum(len(r["edges"]) for r in recovered.values())
    require(total_nodes <= policy["max_graph_nodes"]
            and total_edges <= policy["max_graph_edges"], "source graph exceeds admission policy")
    start, end, edges, gaps = compose(graphs, recovered)
    listing = check_paths(report, start, end, edges, gaps, allow_empty)
    connection = bfs(start, end, edges, max_bfs_nodes, max_bfs_edges)
    if listing["returned_count"]:
        require(connection["connection"] == "found", "positive listing lacks independent BFS confirmation")
        require(all(length >= connection["shortest_edges"] for length in listing["listed_edge_lengths"]),
                "listed path is shorter than independently computed minimum")
    return {"schema": "ariadne.frame-path-capture-observer/v1", "checks_passed": True,
            "positive_gate_passed": listing["positive_gate_passed"],
            "independent_capture_gate_passed": listing["positive_gate_passed"],
            "f4_qualified": False,
            "qualification_boundary": "This observer is one finite evidence tier, not overall F4 acceptance.",
            "input_profile": "exact-emitted-rust-frame-paths-v7-artifacts/v1",
            "binding_hash_profile": "Emitted Rust struct-member order; reordered JSON is outside this profile.",
            "diagnostic_allow_empty": allow_empty, "scope_id": report["scope_id"],
            "snapshot_id": chain["snapshot_id"], "chain_id": chain["chain_id"],
            "thread_id": THREAD, "question": report["question"],
            "graph_admission_limits": policy, "search_limits": limits,
            "source_graph_nodes": total_nodes, "source_graph_edges": total_edges,
            "preserved_source_premises": premise_count,
            "composed_edges": len(edges), "frames": summaries, "unwind_capture_checks": unwind,
            "capture_checked_bytes_with_contributors": capture.checked_bytes,
            "capture_checked_receipts": capture.checked_receipts,
            "listing": listing, "independent_bfs": connection,
            "input_canonical_sha256": json_hash(inputs, canonical=True),
            "boundaries": ["Normalized BAP summaries/admission remain trusted premises.",
                           "All supplied frame-read bytes checked; unwind instructions not independently interpreted.",
                           "Exact DFS order, deadline and resource-counter replay belong to public-API validation.",
                           "Backend execution ownership requires separate driver receipts; equal files do not prove ownership.",
                           "BFS witnesses never replace paths actually listed by the product.",
                           "No feasibility, executed history, writer exclusion or root-cause claim."]}


def self_test():
    """Small corruption controls; no original capture, compiler or subprocess."""
    accepted, rejected = [], []

    def rejects(label, action):
        try:
            action()
        except Rejected:
            rejected.append(label)
        else:
            raise Rejected(f"self-test corruption accepted: {label}")

    def n(frame, site):
        return {"frame": frame, "site": address(site)}

    def e(source, target, kind):
        return {"src": source, "dst": target, "kind": kind}

    request = {"input_kind": "dump", "addresses": list(map(address, [1, 2, 3, 9])),
               "entry_points": [address(1)], "slice_seeds": [address(3)],
               "captured": list(map(address, [1, 2, 3, 9])),
               "file_backed": [], "trusted_fallback": [],
               "decodable": list(map(address, [1, 2, 3, 9])),
               "instructions": [
                   {"address": address(1), "kind": "call", "fall": [address(2)],
                    "targets": [address(9)], "targets_complete": False},
                   {"address": address(2), "kind": "indirect", "fall": [],
                    "targets": [address(3)], "targets_complete": False},
                   {"address": address(3), "kind": "return", "fall": [],
                    "targets": [], "targets_complete": True},
                   {"address": address(9), "kind": "return", "fall": [],
                    "targets": [], "targets_complete": True}]}
    recovered = recover(request, {"function_begin": address(1), "function_end": address(10)}, 0)
    require(recovered["nodes"] == {1, 2, 3}, "self-test followed callee as a local root")
    require(recovered["obligations"] == 2, "self-test lost incomplete-target obligations")
    graph = {"nodes": [{"evidence": {"va": address(i)}} for i in (1, 2, 3)],
             "edges": [e(n(0, 1), n(0, 2), "summary"), e(n(0, 2), n(0, 3), "indirect")],
             "gaps": list(recovered["gaps"])}
    compare_graph(graph, recovered)
    accepted.append("local_recovery_with_context_call_and_unresolved_targets")
    graph["edges"][0]["kind"] = "next"
    rejects("invalid_typed_graph_edge", lambda: compare_graph(graph, recovered))
    graph["edges"][0]["kind"] = "summary"
    graph["gaps"].pop()
    rejects("dropped_source_recovery_gap", lambda: compare_graph(graph, recovered))
    chain = {"chain_id": "a" * 64, "frames": [{"sp": address(STACKS[0])}],
             "snapshot_id": "test", "artifact_sha256": DUMP_SHA256}
    activation = {"thread_id": THREAD, "frame_activation": f'{chain["chain_id"]}:0:{address(STACKS[0])}'}
    premise = {"origin": "abi_normal_call", "policy": "windows-amd64-normal-call-entry/v1",
               "activation": activation.copy(), "snapshot": "test", "root": address(ROOTS[0]),
               "point": address(ROOTS[0]), "query_scope_sha256": "b" * 64,
               "rsp_residues": 1 << 8, "rsp_value": None, "evidence_sha256": "e" * 64}
    guarded = {"frame": 0, "entry": address(ROOTS[0]), "guard_admission": {"report": {"input": {
        "activation": activation.copy(), "snapshot": "test", "artifact_sha256": DUMP_SHA256,
        "query_scope_sha256": "b" * 64,
        "roots": [{"site": address(ROOTS[0]), "function_entry": True}], "premises": [premise]}}}}
    check_activation(guarded, chain)
    accepted.append("activation_binding")
    guarded["guard_admission"]["report"]["input"]["activation"]["thread_id"] += 1
    rejects("wrong_activation", lambda: check_activation(guarded, chain))
    guarded["guard_admission"]["report"]["input"]["activation"]["thread_id"] = THREAD
    source_guard = guarded["guard_admission"]["report"]
    source_guard["input"]["normal_flow"] = {
        "scope": "local-normal-completion/v1", "kind": "local_normal_completion", "terminals": []}
    source_guard["guards"] = [{"site": address(ROOTS[0]), "verdict": "unknown",
                               "residual": "guard-not-admitted", "receipt_sha256": "c" * 64}]
    source_guard["stop"] = "work-limit"
    guarded["guard_admission"]["composition"] = {"profile": "test-composition", "binding_sha256": "d" * 64}
    guarded["guard_admission"]["target_resolution"] = {
        "profile": "test-target", "memory_premise": MEMORY_PREMISE, "stop": "work-limit",
        "resolutions": [{"site": address(ROOTS[0]), "targets": [address(ROOTS[0] + 8)],
                         "complete": False, "unresolved": ["capture-hole"]}]}
    source_report = {"premises": BASE_PREMISES + [
        "frame-0: normal-flow-scope local-normal-completion/v1; exception-exit; exception-resumption-outside-local-scope; exceptional effects unsupported",
        f'frame-0: composition test-composition proof {"d" * 64}; target profile test-target; premise FrozenCapturedControlData: captured control data is interpreted as frozen; no historical memory stability or executed path is inferred',
        f'frame-0: indirect {address(ROOTS[0])}: 1 targets; complete=false; unresolved={{"capture-hole"}}',
        'frame-0: target resolution stopped: Some("work-limit")',
        f'frame-0: assumed windows-amd64-normal-call-entry/v1: entry RSP mod 16 = 8 at {address(ROOTS[0])}; activation {activation["frame_activation"]}; evidence {"e" * 64}',
        f'frame-0: guard {address(ROOTS[0])} Unknown; guard-not-admitted; proof {"c" * 64}',
        "frame-0: guard admission stopped: work-limit",
    ]}
    check_source_premises(source_report, [guarded])
    accepted.append("all_source_premises_and_rust_debug_encodings")
    omitted = source_report["premises"].pop(2)
    rejects("omitted_normal_flow_premise", lambda: check_source_premises(source_report, [guarded]))
    source_report["premises"].insert(2, omitted)
    source_report["premises"].append("additional alignment hypothesis")
    rejects("added_listing_hypothesis", lambda: check_source_premises(source_report, [guarded]))
    source_report["premises"].pop()
    source_guard["input"]["premises"].append(premise.copy())
    rejects("added_source_hypothesis", lambda: check_activation(guarded, chain))
    source_guard["input"]["premises"].pop()
    guarded["guard_admission"]["target_resolution"]["memory_premise"] = "HistoricalStableMemory"
    rejects("changed_frozen_control_data_premise", lambda: check_source_premises(source_report, [guarded]))
    guarded["guard_admission"]["target_resolution"]["memory_premise"] = MEMORY_PREMISE
    start, end = (1, ACTIVE_CALL), (0, FAULT_PC)
    nodes = [n(1, ACTIVE_CALL), n(0, ROOTS[0]), n(0, FAULT_PC)]
    steps = [e(nodes[0], nodes[1], "call"), e(nodes[1], nodes[2], "summary")]
    report = {"scope_id": "a" * 64, "question": {"np": 10}, "returned_count": 1,
              "paths": [{"nodes": nodes, "edges": steps, "contains_opaque_summary": True}],
              "limits": {"max_path_steps": 8, "max_node_visits": 2, "max_search_states": 10,
                         "max_scanned_edges": 20, "max_frontier_bytes": 4096, "max_output_bytes": 4096},
              "gaps": ["source-gap"], "available": True, "truncated": True,
              "enumeration_exhausted": False, "coverage": "partial", "frontier_count": 1,
              "stop_reason": "search-state-budget", "counters": {"expanded_states": 10,
              "scanned_edges": 2, "peak_frontier_bytes": 200, "retained_path_bytes": 500},
              "premises": ["no executed history or selected writer",
                           "incomplete path list never excludes a memory writer"]}
    report["paths"][0]["path_id"] = json_hash([report["scope_id"], [nodes, steps]])
    typed = {edge(item) for item in steps}
    check = lambda: check_paths(report, start, end, typed, {"source-gap"}, False)
    check()
    accepted.append("actual_typed_path_with_opaque_summary")
    steps[1]["kind"] = "next"
    rejects("invalid_listed_typed_edge", check)
    steps[1]["kind"] = "summary"
    report["paths"].append(report["paths"][0])
    report["returned_count"] = 2
    rejects("duplicate_typed_path", check)
    report["paths"].pop()
    report["returned_count"] = 0
    rejects("dropped_count", check)
    report["returned_count"] = 1
    report["gaps"] = []
    rejects("dropped_listing_source_gap", check)
    report["gaps"] = ["source-gap"]
    report["paths"][0]["contains_opaque_summary"] = False
    rejects("removed_opaque_summary_marker", check)
    report["paths"][0]["contains_opaque_summary"] = True
    report["enumeration_exhausted"] = True
    rejects("cutoff_credited_exhaustive", check)
    report["enumeration_exhausted"] = False
    report["paths"] = []
    report["returned_count"] = 0
    rejects("empty_positive_gate", check)
    require(not check_paths(report, start, end, typed, {"source-gap"}, True)["positive_gate_passed"],
            "diagnostic empty result credited positive")
    require(bfs(start, end, typed, 10, 10)["shortest_edges"] == 2, "BFS distance control")
    accepted.append("empty_diagnostic_keeps_failed_positive_gate_and_independent_bfs")
    # A real tiny minidump MemoryList: header, directory, descriptor, four bytes.
    raw = bytearray(68)
    struct.pack_into("<4sIIIIIQ", raw, 0, b"MDMP", 0xA793, 1, 32, 0, 0, 0)
    struct.pack_into("<III", raw, 32, 5, 20, 44)
    struct.pack_into("<IQII", raw, 44, 1, 0x1000, 4, 64)
    raw[64:68] = b"ABCD"
    with tempfile.TemporaryDirectory(prefix="frame-path-observer-") as directory:
        path = Path(directory) / "tiny.dmp"
        path.write_bytes(raw)
        rejects("same_file_parity", lambda: distinct_parity_inputs(path, path))
        symlink = Path(directory) / "symlink.dmp"
        symlink.symlink_to(path)
        rejects("symlink_same_artifact_parity", lambda: distinct_parity_inputs(path, symlink))
        hardlink = Path(directory) / "hardlink.dmp"
        hardlink.hardlink_to(path)
        rejects("hardlink_same_inode_parity", lambda: distinct_parity_inputs(path, hardlink))
        independent_copy = Path(directory) / "equal-bytes-distinct-file.dmp"
        independent_copy.write_bytes(raw)
        distinct_parity_inputs(path, independent_copy)
        accepted.append("equal_bytes_distinct_files_are_valid_parity_inputs")
        capture = Capture(path)
        try:
            spans = [{"va": address(0x1000), "length": 4,
                      "contributors": [{"stream": 5, "entry": 0, "file_offset": address(64)}]}]
            capture.check_spans(0x1000, "41424344", spans, exact=True)
            accepted.append("raw_minidump_mapping_and_bytes")
            rejects("changed_source_bytes", lambda: capture.check_spans(0x1000, "41424345", spans))
            spans[0]["contributors"][0]["file_offset"] = address(63)
            rejects("changed_capture_mapping", lambda: capture.check_spans(0x1000, "41424344", spans))
        finally:
            capture.close()
    return {"schema": "ariadne.frame-path-capture-observer-self-test/v1", "passed": True,
            "accepted_controls": accepted, "rejected_corruptions": rejected,
            "original_capture_exercised": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("native", "rust", "dump", "output"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--expected-report-sha256")
    parser.add_argument("--diagnostic-allow-empty", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--max-bfs-nodes", type=int, default=1_000_000)
    parser.add_argument("--max-bfs-edges", type=int, default=4_000_000)
    args = parser.parse_args()
    if not args.self_test:
        for name in ("native", "dump", "output"):
            if getattr(args, name) is None:
                parser.error("--native, --dump and --output are required")
        if args.rust is None and not args.diagnostic_allow_empty:
            parser.error("--rust is required unless --diagnostic-allow-empty is selected")
    if args.output and any(path is not None and (path.resolve() == args.output.resolve()
                           or (args.output.exists() and path.exists() and args.output.samefile(path)))
                           for path in (args.native, args.rust, args.dump)):
        parser.error("output must not overwrite an input artifact")
    result = {"parity_checked": False}
    exit_code = 0
    try:
        if args.self_test:
            result = self_test()
        else:
            require(args.max_bfs_nodes > 0 and args.max_bfs_edges > 0, "invalid observer BFS bounds")
            if args.rust is None:
                result["parity_unexercised_reason"] = (
                    "No Rust report supplied in diagnostic mode; native/Rust equality is unexercised.")
            else:
                result["parity_unexercised_reason"] = "Report comparison has not completed."
                distinct_parity_inputs(args.native, args.rust)
            root = Path(__file__).resolve().parent.parent
            source_paths = ("tools/check_frame_path_capture.py", "Specs/Ariadne.tla",
                            "Specs/AriadneMachineCommon.tla", "Specs/AriadneFramePaths.tla",
                            "src/investigation/frame_paths.rs", "src/investigation/frame_unwind.rs",
                            "src/investigation/validate.rs", "src/investigation/model.rs",
                            "src/input/minidump.rs", "src/input/address_space.rs",
                            "src/bap/guard_admission.rs", "src/bap/target_resolution.rs",
                            "src/bap/terminal_control.rs")
            result["observer_and_contract_source_sha256"] = {
                relative: file_hash(root / relative) for relative in source_paths}
            artifacts = {name: {"path": str(path.resolve()), "bytes": path.stat().st_size,
                                "sha256": file_hash(path)}
                         for name, path in (("native", args.native), ("rust", args.rust), ("dump", args.dump))
                         if path is not None}
            result["artifacts"] = artifacts
            require(artifacts["dump"]["sha256"] == DUMP_SHA256, "not the original dump03958 artifact")
            if args.expected_report_sha256 is not None:
                require(artifacts["native"]["sha256"] == digest(args.expected_report_sha256),
                        "trusted native report digest mismatch")
            native = load_report(args.native)
            parity = parity_hash(native)
            capture = Capture(args.dump)
            try:
                result.update(observe(native, capture, args.diagnostic_allow_empty,
                                      args.max_bfs_nodes, args.max_bfs_edges))
            finally:
                capture.close()
            del native
            gc.collect()
            if args.rust is not None:
                rust = load_report(args.rust)
                require(parity_hash(rust) == parity, "native/Rust reports differ beyond top-level elapsed_ms")
                del rust
                gc.collect()
                result["parity_checked"] = True
                result.pop("parity_unexercised_reason", None)
                result["native_rust_equal_except_top_level_elapsed_ms"] = True
            else:
                result["independent_capture_gate_passed"] = False
            result["timing_normalized_report_sha256"] = parity
            result["expected_raw_native_sha256"] = args.expected_report_sha256
    except (Rejected, KeyError, IndexError, TypeError, ValueError, OSError, struct.error) as error:
        result.update({"checks_passed": False, "positive_gate_passed": False,
                       "independent_capture_gate_passed": False, "f4_qualified": False,
                       "error": f"{type(error).__name__}: {error}"})
        exit_code = 1
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
