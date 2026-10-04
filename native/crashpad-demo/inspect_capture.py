#!/usr/bin/env python3
"""Independently verify the controlled Windows x64 null-write demo capture.

This is a bounded raw-file oracle, not an instruction evaluator or a general
minidump validator. It does not invoke Ariadne, BAP, a debugger, or the demo.
Success qualifies this controlled capture only, not an I5 release gate.
"""

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import struct
import sys


U64_LIMIT = 1 << 64
MAX_STREAMS = 1024
MAX_ENTRIES = 131072
MAX_CAPTURES = 262144
MAX_CODE_EXTENT = 256
MAX_OVERLAPS = 64
STREAM_NAMES = {
    3: "ThreadList", 4: "ModuleList", 5: "MemoryList", 6: "Exception",
    7: "SystemInfo", 8: "ThreadExList", 9: "Memory64List", 15: "MiscInfo",
}
# Explicitly reviewed C7 /0, mod=00, r/m=000 or 001, imm32=5. No prefixes,
# displacement, SIB, register payload, or other instruction forms are admitted.
STORE_FORMS = {bytes.fromhex("c70005000000"): "rax",
               bytes.fromhex("c70105000000"): "rcx"}


class InspectionError(Exception):
    """The supplied files do not establish this controlled-case contract."""


def require(condition, message):
    if not condition:
        raise InspectionError(message)


def checked_end(start, size, label):
    require(0 <= start < U64_LIMIT and 0 <= size < U64_LIMIT,
            f"{label}: invalid unsigned 64-bit range")
    require(start + size <= U64_LIMIT, f"{label}: address range overflows")
    return start + size


def hex_address(value):
    return f"0x{value:x}"


class BinaryFile:
    def __init__(self, path):
        self.path = path.resolve(strict=True)
        self.file = self.path.open("rb")
        self.initial_stat = os.fstat(self.file.fileno())
        self.size = self.initial_stat.st_size

    def close(self):
        self.file.close()

    def bounds(self, offset, size, label):
        end = checked_end(offset, size, label)
        require(end <= self.size,
                f"{label}: file range [{offset}, {end}) exceeds {self.size} bytes")

    def read(self, offset, size, label):
        self.bounds(offset, size, label)
        require(size <= 16 * 1024 * 1024, f"{label}: bounded read limit exceeded")
        self.file.seek(offset)
        data = self.file.read(size)
        require(len(data) == size, f"{label}: file changed or read was truncated")
        return data

    def unpack(self, fmt, offset, label):
        return struct.unpack(fmt, self.read(offset, struct.calcsize(fmt), label))

    def identity(self):
        self.file.seek(0)
        digest = hashlib.sha256()
        while chunk := self.file.read(1024 * 1024):
            digest.update(chunk)
        current = os.fstat(self.file.fileno())
        require((current.st_size, current.st_mtime_ns, current.st_ctime_ns) ==
                (self.initial_stat.st_size, self.initial_stat.st_mtime_ns,
                 self.initial_stat.st_ctime_ns),
                f"input changed during inspection: {self.path}")
        return {"path": str(self.path), "size_bytes": self.size,
                "sha256": digest.hexdigest()}


@dataclass(frozen=True)
class Stream:
    kind: int
    size: int
    offset: int


@dataclass(frozen=True)
class Capture:
    address: int
    size: int
    offset: int
    source: str
    index: int


class Minidump:
    def __init__(self, raw):
        self.raw = raw
        header = raw.unpack("<IIIIIIQ", 0, "minidump header")
        signature, version, count, directory, checksum, timestamp, flags = header
        require(signature == 0x504D444D, "not a little-endian MDMP minidump")
        require(version & 0xFFFF == 0xA793, "unsupported minidump version")
        require(0 < count <= MAX_STREAMS, "invalid or excessive stream count")
        raw.bounds(directory, count * 12, "stream directory")
        self.header = {"version": hex_address(version), "checksum": checksum,
                       "timestamp": timestamp, "flags": hex_address(flags),
                       "mini_dump_with_full_memory": bool(flags & 2)}
        self.streams = {}
        self.captures = []
        for index in range(count):
            kind, size, offset = raw.unpack("<III", directory + 12 * index,
                                            "stream directory entry")
            require(kind not in self.streams, f"duplicate stream type {kind}")
            raw.bounds(offset, size, f"stream {kind}")
            self.streams[kind] = Stream(kind, size, offset)
        require(8 not in self.streams,
                "ThreadExList capture descriptors are outside this controlled profile")

    def stream(self, kind, minimum):
        require(kind in self.streams, f"missing required {STREAM_NAMES[kind]} stream")
        stream = self.streams[kind]
        require(stream.size >= minimum,
                f"{STREAM_NAMES[kind]} stream is shorter than {minimum} bytes")
        return stream

    def location(self, offset, label):
        size, data_offset = self.raw.unpack("<II", offset, label)
        self.raw.bounds(data_offset, size, label)
        return size, data_offset

    def string(self, offset, label):
        size, = self.raw.unpack("<I", offset, label)
        require(size <= 32768 and size % 2 == 0,
                f"{label}: invalid or excessive UTF-16 length")
        result = self.raw.read(offset + 4, size, label).decode("utf-16-le")
        require("\0" not in result, f"{label}: embedded NUL")
        return result

    def system(self):
        stream = self.stream(7, 56)
        architecture, = self.raw.unpack("<H", stream.offset, "processor architecture")
        platform, csd_rva = self.raw.unpack("<II", stream.offset + 20, "system platform")
        require(architecture == 9, "SystemInfo does not identify AMD64")
        require(platform == 2, "SystemInfo does not identify Windows NT")
        if csd_rva:
            self.string(csd_rva, "system CSD string")
        return {"processor_architecture": architecture, "platform_id": platform,
                "architecture": "AMD64", "platform": "Windows NT"}

    def process_id(self):
        # Pinned Crashpad 7a884c25 MinidumpFileWriter always adds MiscInfo;
        # MinidumpMiscInfoWriter::InitializeFromSnapshot always calls SetProcessID.
        stream = self.stream(15, 24)
        size, flags, process_id = self.raw.unpack("<III", stream.offset, "MiscInfo")
        require(size == stream.size, "MiscInfo SizeOfInfo disagrees with its directory")
        require(flags & 1, "MiscInfo process ID is not marked valid")
        require(process_id != 0, "MiscInfo process ID is zero")
        return process_id

    def exception(self):
        stream = self.stream(6, 168)
        thread_id, alignment, code, flags, chain, site, count, unused = self.raw.unpack(
            "<IIIIQQII", stream.offset, "exception record")
        require(alignment == 0 and unused == 0, "nonzero exception alignment fields")
        require(code == 0xC0000005, "exception is not EXCEPTION_ACCESS_VIOLATION")
        require(flags in (0, 1), f"unsupported exception flags {hex_address(flags)}")
        require(chain == 0, "nested exception chain is outside the controlled profile")
        require(count == 2, f"expected exactly two access-violation parameters, got {count}")
        access, address = self.raw.unpack("<QQ", stream.offset + 40, "exception parameters")
        require(access == 1 and address == 0,
                f"exception does not report a write to zero: access={access}, address={hex_address(address)}")
        context_size, context_offset = self.location(stream.offset + 160, "exception context")
        require(1232 <= context_size <= 65536,
                f"unsupported AMD64 exception context size {context_size}")
        context_flags, = self.raw.unpack("<I", context_offset + 48, "AMD64 context flags")
        require(context_flags & 0x00FF0000 == 0x00100000,
                "exception context flags do not identify AMD64")
        require(context_flags & 3 == 3, "exception context lacks CONTROL or INTEGER validity")
        values = self.raw.unpack("<17Q", context_offset + 120, "AMD64 integer/control registers")
        registers = dict(zip(("rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi",
                              "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15", "rip"), values))
        require(registers["rip"] == site, "exception RIP disagrees with ExceptionAddress")
        return {"thread_id": thread_id, "code": hex_address(code), "flags": flags,
                "chain": hex_address(chain), "instruction_address": hex_address(site),
                "parameter_count": count, "access_parameter": access,
                "data_address": hex_address(address),
                "context": {"file_offset": context_offset, "size_bytes": context_size,
                            "flags": hex_address(context_flags),
                            "registers": {key: hex_address(value) for key, value in registers.items()}}}, registers

    def module(self, entry, site):
        stream = self.stream(4, 4)
        count, = self.raw.unpack("<I", stream.offset, "module count")
        require(0 < count <= MAX_ENTRIES and 4 + count * 108 <= stream.size,
                "invalid or excessive module list")
        matches = []
        containing = []
        for index in range(count):
            offset = stream.offset + 4 + 108 * index
            base, size, checksum, timestamp, name_offset = self.raw.unpack("<QIIII", offset, "module")
            end = checked_end(base, size, "module virtual range")
            name = self.string(name_offset, "module name")
            self.location(offset + 76, "module CodeView record")
            self.location(offset + 84, "module miscellaneous record")
            if base <= entry < end or base <= site < end:
                containing.append(index)
            if name.replace("\\", "/").rsplit("/", 1)[-1].lower() == "ariadne_crash_demo.exe":
                matches.append({"index": index, "name": name, "base_address": base,
                                "size_of_image": size, "timestamp": timestamp, "checksum": checksum})
        require(len(matches) == 1, "expected exactly one ariadne_crash_demo.exe module")
        module = matches[0]
        require(containing == [module["index"]], "entry/fault has absent or ambiguous module ownership")
        base, size = module["base_address"], module["size_of_image"]
        require(base <= entry < base + size and base <= site < base + size,
                "entry and fault site must both lie in the demo module")
        return module

    def add_capture(self, address, size, offset, source, index):
        checked_end(address, size, f"{source} virtual range")
        self.raw.bounds(offset, size, f"{source} payload")
        if size:
            require(len(self.captures) < MAX_CAPTURES, "capture descriptor limit exceeded")
            self.captures.append(Capture(address, size, offset, source, index))

    def memory(self, exception_thread_id):
        for kind in (5, 9):
            if kind not in self.streams:
                continue
            stream = self.stream(kind, 4 if kind == 5 else 16)
            if kind == 5:
                count, = self.raw.unpack("<I", stream.offset, "MemoryList count")
                header_size = 4
            else:
                count, payload = self.raw.unpack("<QQ", stream.offset, "Memory64List header")
                header_size = 16
                self.raw.bounds(payload, 0, "Memory64List base RVA")
            require(count <= MAX_ENTRIES and header_size + count * 16 <= stream.size,
                    f"invalid or excessive {STREAM_NAMES[kind]} descriptors")
            for index in range(count):
                offset = stream.offset + header_size + 16 * index
                if kind == 5:
                    address, size, data_offset = self.raw.unpack("<QII", offset, "MemoryList descriptor")
                else:
                    address, size = self.raw.unpack("<QQ", offset, "Memory64List descriptor")
                    data_offset = payload
                    payload = checked_end(payload, size, "Memory64List payload cursor")
                self.add_capture(address, size, data_offset, STREAM_NAMES[kind], index)
        require(5 in self.streams or 9 in self.streams, "no MemoryList or Memory64List stream")
        if 3 in self.streams:
            stream = self.stream(3, 4)
            count, = self.raw.unpack("<I", stream.offset, "thread count")
            require(count <= MAX_ENTRIES and 4 + count * 48 <= stream.size, "invalid thread list")
            thread_ids = set()
            for index in range(count):
                offset = stream.offset + 4 + 48 * index
                thread_id, = self.raw.unpack("<I", offset, "thread ID")
                require(thread_id not in thread_ids, "duplicate thread ID")
                thread_ids.add(thread_id)
                address, size, data_offset = self.raw.unpack("<QII", offset + 24, "thread stack")
                self.add_capture(address, size, data_offset, "ThreadList.stack", index)
                self.location(offset + 40, "thread context")
            require(exception_thread_id in thread_ids, "exception thread is absent from ThreadList")

    def read_code(self, address, size):
        require(0 < size <= MAX_CODE_EXTENT, "code read exceeds controlled window limit")
        end = checked_end(address, size, "code window")
        cells = [dict() for _ in range(size)]
        contributors = []
        for capture in self.captures:
            start, stop = max(address, capture.address), min(end, capture.address + capture.size)
            if start >= stop:
                continue
            offset = capture.offset + start - capture.address
            data = self.raw.read(offset, stop - start, "captured code bytes")
            contributor = {"source": capture.source, "descriptor_index": capture.index,
                           "address": hex_address(start), "size_bytes": stop - start,
                           "file_offset": offset}
            contributor_index = len(contributors)
            contributors.append(contributor)
            for index, value in enumerate(data, start - address):
                require(sum(len(items) for items in cells[index].values()) < MAX_OVERLAPS,
                        "code window exceeds capture overlap limit")
                cells[index].setdefault(value, []).append(contributor_index)
        holes = [hex_address(address + i) for i, values in enumerate(cells) if not values]
        conflicts = [{"address": hex_address(address + i),
                      "values": {f"{value:02x}": indexes for value, indexes in values.items()}}
                     for i, values in enumerate(cells) if len(values) > 1]
        require(not holes, f"captured code window has {len(holes)} missing bytes; first addresses: {holes[:16]}")
        require(not conflicts, f"captured code window has conflicting overlapping bytes: {conflicts[:16]}")
        data = bytes(next(iter(values)) for values in cells)
        return data, {"address": hex_address(address), "size_bytes": size,
                      "bytes_hex": data.hex(), "fully_captured": True,
                      "holes": [], "conflicts": [], "contributors": contributors}


class PortableExecutable:
    def __init__(self, raw):
        self.raw = raw
        require(raw.read(0, 2, "DOS signature") == b"MZ", "executable lacks MZ signature")
        pe_offset, = raw.unpack("<I", 0x3C, "PE header offset")
        require(raw.read(pe_offset, 4, "PE signature") == b"PE\0\0", "invalid PE signature")
        machine, count, self.timestamp, _, _, optional_size, _ = raw.unpack(
            "<HHIIIHH", pe_offset + 4, "COFF header")
        require(machine == 0x8664, "executable is not AMD64")
        require(0 < count <= 96 and optional_size >= 112, "unsupported PE section/header count")
        optional = pe_offset + 24
        raw.bounds(optional, optional_size + count * 40, "PE optional and section headers")
        magic, = raw.unpack("<H", optional, "PE optional-header magic")
        require(magic == 0x20B, "executable is not PE32+")
        self.image_base, = raw.unpack("<Q", optional + 24, "PE preferred image base")
        self.image_size, headers_size = raw.unpack("<II", optional + 56, "PE image/header size")
        require(0 < headers_size <= self.image_size, "invalid PE header/image sizes")
        raw.bounds(0, headers_size, "PE headers")
        self.sections = []
        for index in range(count):
            offset = optional + optional_size + index * 40
            name, virtual_size, va, raw_size, raw_offset, _, _, _, _, characteristics = raw.unpack(
                "<8sIIIIIIHHI", offset, "PE section header")
            end = checked_end(va, max(virtual_size, raw_size), "PE section virtual range")
            require(headers_size <= va and end <= self.image_size, "PE section exceeds image or overlaps headers")
            raw.bounds(raw_offset, raw_size, "PE section file bytes")
            for prior in self.sections:
                require(end <= prior["rva"] or prior["end"] <= va, "overlapping PE virtual sections")
            self.sections.append({"name": name.rstrip(b"\0").decode("ascii", errors="replace"),
                                  "rva": va, "end": end, "raw_size": raw_size,
                                  "raw_offset": raw_offset, "executable": bool(characteristics & 0x20000000)})

    def code(self, rva, size):
        matches = [section for section in self.sections
                   if section["rva"] <= rva and rva + size <= section["end"]]
        require(len(matches) == 1, "entry-to-fault bytes do not map to one PE section")
        section = matches[0]
        require(section["executable"], "entry/fault PE section is not executable")
        relative = rva - section["rva"]
        require(relative + size <= section["raw_size"], "requested PE bytes include an unbacked virtual tail")
        offset = section["raw_offset"] + relative
        return self.raw.read(offset, size, "PE code bytes"), {
            "section": section["name"], "rva": hex_address(rva),
            "file_offset": offset, "size_bytes": size}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f"duplicate witness JSON key: {key}")
        result[key] = value
    return result


def witness_address(value, label):
    require(isinstance(value, str) and value.startswith("0x"), f"{label} must be a hexadecimal string")
    try:
        address = int(value, 16)
    except ValueError as error:
        raise InspectionError(f"{label} is not hexadecimal") from error
    require(0 <= address < U64_LIMIT, f"{label} exceeds a 64-bit address")
    return address


def read_witness(raw):
    require(raw.size <= 16384, "witness exceeds 16 KiB limit")
    witness = json.loads(raw.read(0, raw.size, "witness").decode("utf-8"), object_pairs_hook=unique_object)
    require(isinstance(witness, dict), "witness must be a JSON object")
    expected = {"schema_version": 1, "expected_data_address": "0x0",
                "expected_access": "write", "expected_width_bytes": 4,
                "expected_store_value": 5,
                "integration_profile": "ariadne-crashpad-null-write-v1",
                "explicit_code_range_registered": True}
    for key, value in expected.items():
        require(type(witness.get(key)) is type(value) and witness[key] == value,
                f"witness {key} does not match the controlled-case contract")
    require(witness.get("dump_mode") in ("partial", "full"), "unsupported witness dump mode")
    process_id = witness.get("process_id")
    require(type(process_id) is int and 0 < process_id < (1 << 32), "invalid witness process_id")
    entry = witness_address(witness.get("fault_function_entry"), "fault_function_entry")
    extent = witness.get("expected_code_extent")
    require(isinstance(extent, dict), "missing expected_code_extent")
    require(witness_address(extent.get("address"), "code extent address") == entry,
            "witness code extent does not begin at the function entry")
    size = extent.get("size_bytes")
    require(type(size) is int and 0 < size <= MAX_CODE_EXTENT, "invalid witness code extent size")
    checked_end(entry, size, "witness code extent")
    return witness, entry, size


def inspect(dump_raw, witness_raw, executable_raw):
    witness, entry, extent_size = read_witness(witness_raw)
    dump = Minidump(dump_raw)
    system = dump.system()
    process_id = dump.process_id()
    require(process_id == witness["process_id"], "dump process ID disagrees with witness")
    exception, registers = dump.exception()
    site = registers["rip"]
    require(entry <= site and site + 6 <= entry + extent_size,
            "fault instruction lies outside the witness code extent")
    module = dump.module(entry, site)
    require(entry + extent_size <= module["base_address"] + module["size_of_image"],
            "witness code extent crosses the demo module boundary")
    executable = PortableExecutable(executable_raw)
    require(module["timestamp"] == executable.timestamp, "dump module timestamp disagrees with supplied PE")
    require(module["size_of_image"] == executable.image_size, "dump module SizeOfImage disagrees with supplied PE")
    dump.memory(exception["thread_id"])
    full_memory = dump.header["mini_dump_with_full_memory"]
    require(full_memory == (witness["dump_mode"] == "full"), "minidump full-memory flag disagrees with witness mode")
    if full_memory:
        require(9 in dump.streams and 5 not in dump.streams,
                "pinned Crashpad full mode requires Memory64List without MemoryList")
    else:
        require(5 in dump.streams and 9 not in dump.streams,
                "pinned Crashpad partial mode requires MemoryList without Memory64List")
    code, capture = dump.read_code(entry, extent_size)
    fault_bytes = code[site - entry:site - entry + 6]
    require(fault_bytes in STORE_FORMS,
            f"unreviewed fault encoding at {hex_address(site)}: {code[site - entry:site - entry + 16].hex()}; "
            "inspect executable disassembly before expanding the admitted forms")
    register = STORE_FORMS[fault_bytes]
    require(registers[register] == 0,
            f"captured {register.upper()} is {hex_address(registers[register])}, expected zero")
    entry_rva = entry - module["base_address"]
    site_rva = site - module["base_address"]
    compared_size = site - entry + 6
    pe_bytes, pe_mapping = executable.code(entry_rva, compared_size)
    require(code[:compared_size] == pe_bytes,
            f"captured entry-to-fault bytes differ from supplied PE: captured={code[:compared_size].hex()}, PE={pe_bytes.hex()}")
    return {
        "schema": "ariadne.crashpad-demo-capture-inspection/v1", "passed": True,
        "scope": "Independent raw inspection of one controlled Windows AMD64 null-write capture; not I5 release qualification.",
        "inputs": {"dump": dump_raw.identity(), "witness": witness_raw.identity(),
                   "executable": executable_raw.identity()},
        "system": system, "process_id": process_id, "dump_header": dump.header,
        "requested_dump_mode": witness["dump_mode"],
        "memory_stream_types": [STREAM_NAMES[kind] for kind in (5, 9) if kind in dump.streams],
        "stream_inventory": [{"type": kind, "name": STREAM_NAMES.get(kind, "uninterpreted"),
                              "file_offset": stream.offset, "size_bytes": stream.size}
                             for kind, stream in dump.streams.items()],
        "exception": exception,
        "module": {**module, "base_address": hex_address(module["base_address"]),
                   "preferred_pe_image_base": hex_address(executable.image_base),
                   "entry_rva": hex_address(entry_rva), "fault_rva": hex_address(site_rva)},
        "query": {"entry_points": [hex_address(entry)], "slice_seeds": [hex_address(site)],
                  "fault_instruction": hex_address(site), "memory_access_index": 0},
        "fault_instruction": {"bytes_hex": fault_bytes.hex(), "size_bytes": 6,
                              "reviewed_form": f"mov dword ptr [{register}], 5",
                              "address_register": register, "captured_address_register_value": "0x0",
                              "access": "write", "width_bytes": 4, "store_value": 5},
        "code_capture": capture,
        "pe_comparison": {**pe_mapping, "captured_bytes_hex": code[:compared_size].hex(),
                          "pe_bytes_hex": pe_bytes.hex(), "equal": True},
        "independently_observed_premises": [
            "Windows NT AMD64 SystemInfo and valid exception CONTROL/INTEGER context",
            "Raw access-violation record reports a write to zero with no exception chain",
            "ExceptionAddress equals captured RIP; MiscInfo process ID equals witness process ID",
            "Witness entry and fault site belong to the named demo module and bounded code extent",
            "Module timestamp and SizeOfImage match the supplied PE; captured entry-to-fault bytes match its executable section",
            "Entire declared code extent is captured with no holes or conflicting contributors",
            f"Reviewed six-byte immediate store uses captured {register.upper()}=0, width 4, value 5",
            "Dump header and memory stream selection agree with the requested pinned-fork mode",
        ],
        "limits": [
            "Witness is an independent caller declaration, not authenticated proof of executed history",
            "Matching module metadata and compared code bytes do not prove whole-image identity",
            "Only the two explicitly listed store encodings are interpreted; preceding instructions are byte-compared only",
            "A full-memory flag and Memory64List do not establish completeness of all process memory",
            "Local source hashes record inspector inputs; they do not prove executable build provenance",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", required=True, type=Path)
    parser.add_argument("--witness", required=True, type=Path)
    parser.add_argument("--executable", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="new JSON file; existing files are rejected")
    args = parser.parse_args()
    files = []
    try:
        require(not os.path.lexists(args.output), f"output already exists: {args.output}")
        for path in (args.dump, args.witness, args.executable):
            files.append(BinaryFile(path))
        result = inspect(*files)
        local_sources = {}
        for path in (Path(__file__).resolve(), Path(__file__).with_name("crash_demo.cc"),
                     Path(__file__).with_name("fault.cc")):
            if path.is_file():
                source = BinaryFile(path)
                try:
                    local_sources[path.name] = source.identity()
                finally:
                    source.close()
        result["local_source_files"] = local_sources
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            output.write(json.dumps(result, indent=2) + "\n")
        print(f"Controlled capture inspection PASS: {args.output}")
    except (InspectionError, OSError, UnicodeError, ValueError, struct.error) as error:
        print(f"Capture inspection FAILED: {error}", file=sys.stderr)
        return 1
    finally:
        for raw in files:
            raw.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
