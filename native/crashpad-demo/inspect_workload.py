#!/usr/bin/env python3
"""Inspect the controlled 98-instruction Windows Crashpad BAP workload.

This raw-file oracle admits one hand-reviewed AMD64 assembly recipe. It does
not run Ariadne, BAP, or the captured program, and does not infer an execution
history from the dump. A successful inspection is evidence for repinning this
controlled capture, not a workload performance or release qualification.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys

from inspect_capture import (BinaryFile, InspectionError, MAX_CODE_EXTENT,
                             Minidump, PortableExecutable, STREAM_NAMES,
                             U64_LIMIT, checked_end, require, unique_object,
                             witness_address)


PROFILE = "ariadne-crashpad-bap-workload-v1"
MAX_WORKLOAD_EXTENT = 1024
INPUTS = (3, 5, 8, 13, 21, 34, 55, 89)
EXPECTED_STARTS = 98
EXPECTED_CHECKSUM = 0x4BEA2


def address(value):
    return f"0x{value:016x}"


def canonical_address(value, label):
    require(isinstance(value, str) and re.fullmatch(r"0x[0-9a-f]{16}", value),
            f"{label} must be a canonical 16-digit lowercase hexadecimal address")
    return witness_address(value, label)


def checksum_oracle(inputs):
    """Compute the declared recipe in integers modulo 2**64, independently."""
    require(tuple(inputs) == INPUTS, "workload inputs differ from the fixed recipe")
    mask = U64_LIMIT - 1
    accumulator = inputs[0]
    for index, item in enumerate(inputs):
        accumulator = (accumulator + item) & mask
        accumulator = (~accumulator) & mask
        accumulator = (accumulator + index + 1) & mask
        spilled = accumulator
        accumulator = (3 * spilled + index) & mask
        accumulator = (accumulator + spilled) & mask
        accumulator = (accumulator + index + 3) & mask
    rounds = accumulator
    for item in inputs[:4]:
        accumulator = (accumulator + item) & mask
    loop = accumulator
    branch = "odd" if accumulator & 1 else "even"
    accumulator = (accumulator + (11 if branch == "odd" else 7)) & mask
    checksum = (accumulator + 17) & mask
    require(checksum == EXPECTED_CHECKSUM, "internal recipe checksum disagrees with reviewed constant")
    return {"arithmetic": "unsigned integers modulo 2**64",
            "after_rounds": hex(rounds), "after_loop": hex(loop),
            "branch_for_declared_inputs": branch, "checksum": hex(checksum),
            "producer_value_with_declared_checksum": hex((-checksum + checksum) & mask)}


def instruction_recipe():
    """Return explicit reviewed machine encodings, not decoder-derived facts.

    MOV/ADD/CMP register forms admit both equivalent opcode directions used by
    MASM and LLVM. Memory forms and short branch forms are fixed; branch target
    displacements are checked against recipe labels after boundary validation.
    No prefixes, padding, reordered instructions, or extra starts are admitted.
    """
    instructions = []
    labels = {}

    def label(name):
        labels[name] = len(instructions)

    def emit(text, *encodings):
        instructions.append({"text": text, "encodings": tuple(bytes.fromhex(item) for item in encodings)})

    def branch(text, opcode, target):
        instructions.append({"text": text, "encodings": (bytes((opcode, 0)),), "target": target})

    label("entry")
    emit("mov r10, rcx", "4989ca", "4c8bd1")
    emit("mov r11, rdx", "4989d3", "4c8bda")
    emit("mov rax, [r10]", "498b02")
    emit("mov r9d, 0", "41b900000000")
    for index in range(8):
        emit(f"mov r8, [r10+{8 * index}]", "4d8b02" if index == 0 else f"4d8b42{8 * index:02x}")
        emit("add rax, r8", "4c01c0", "4903c0")
        emit("not rax", "48f7d0")
        emit(f"lea rax, [rax+{index + 1}]", f"488d40{index + 1:02x}")
        emit("mov [rsp+8], rax", "4889442408")
        emit("mov r8, [rsp+8]", "4c8b442408")
        emit(f"lea rax, [r8+r8*2+{index}]", "4b8d0440" if index == 0 else f"4b8d4440{index:02x}")
        emit("add rax, r8", "4c01c0", "4903c0")
        emit(f"lea rax, [rax+{index + 3}]", f"488d40{index + 3:02x}")
    label("loop")
    emit("mov r8, [r10+r9*8]", "4f8b04ca")
    emit("add rax, r8", "4c01c0", "4903c0")
    emit("inc r9", "49ffc1")
    emit("mov r8d, 4", "41b804000000")
    emit("cmp r9, r8", "4d39c1", "4d3bc8")
    branch("jne loop", 0x75, "loop")
    emit("mov r8d, 1", "41b801000000")
    emit("test rax, r8", "4c85c0", "4985c0")
    branch("jne odd", 0x75, "odd")
    emit("lea rax, [rax+7]", "488d4007")
    branch("jmp join", 0xEB, "join")
    label("odd")
    emit("lea rax, [rax+11]", "488d400b")
    label("join")
    emit("mov [rsp+16], rax", "4889442410")
    emit("mov r8, [rsp+16]", "4c8b442410")
    emit("lea r8, [r8+17]", "4d8d4011")
    emit("not r8", "49f7d0")
    emit("inc r8", "49ffc0")
    emit("add r8, r11", "4d01d8", "4d03c3")
    emit("mov rax, r8", "4c89c0", "498bc0")
    label("producer")
    emit("mov rcx, rax", "4889c1", "488bc8")
    label("fault")
    emit("mov dword ptr [rcx], 5", "c70105000000")
    emit("ret", "c3")
    label("end")
    require(len(instructions) == EXPECTED_STARTS, "internal recipe instruction count changed")
    return instructions, labels


def inspect_instructions(code, entry, declared):
    recipe, label_indices = instruction_recipe()
    starts, facts = [], []
    offset = 0
    branches = []
    for instruction in recipe:
        starts.append(offset)
        alternatives = instruction["encodings"]
        size = len(alternatives[0])
        require(all(len(item) == size for item in alternatives), "internal inconsistent encoding lengths")
        actual = code[offset:offset + size]
        if "target" in instruction:
            require(len(actual) == size and actual[0] == alternatives[0][0],
                    f"unreviewed branch encoding at {address(entry + offset)}")
            displacement, = struct.unpack("b", actual[1:2])
            branches.append((offset + size + displacement, instruction["target"]))
        else:
            require(actual in alternatives,
                    f"unreviewed instruction at {address(entry + offset)}; expected {instruction['text']}, got {actual.hex()}")
        facts.append({"address": address(entry + offset), "offset": offset,
                      "size_bytes": size, "bytes_hex": actual.hex(),
                      "reviewed_instruction": instruction["text"]})
        offset += size
    require(offset == len(code), "declared code extent does not end exactly after the reviewed ret")
    starts_with_end = starts + [offset]
    labels = {name: entry + starts_with_end[index] for name, index in label_indices.items()}
    for actual_target, label in branches:
        require(entry + actual_target == labels[label], f"short branch target disagrees with recipe label {label}")
    for label in ("entry", "producer", "fault", "end"):
        require(declared[label] == labels[label], f"witness {label} does not match the independently decoded recipe boundary")
    return {"method": "exact reviewed AMD64 byte recipe with independently checked short-branch targets",
            "decoded_starts": len(starts), "independently_decoded_starts": len(starts),
            "labels": {name: address(value) for name, value in labels.items()},
            "instructions": facts}


def read_witness(raw):
    require(raw.size <= 16384, "witness exceeds 16 KiB limit")
    witness = json.loads(raw.read(0, raw.size, "witness").decode("utf-8"), object_pairs_hook=unique_object)
    require(isinstance(witness, dict), "witness must be a JSON object")
    expected = {"schema_version": 1, "expected_data_address": "0x0",
                "expected_access": "write", "expected_width_bytes": 4,
                "expected_store_value": 5, "integration_profile": PROFILE,
                "explicit_code_range_registered": True,
                "explicit_input_range_registered": True}
    for key, value in expected.items():
        require(type(witness.get(key)) is type(value) and witness[key] == value,
                f"witness {key} does not match the controlled workload contract")
    require(witness.get("dump_mode") in ("partial", "full"), "unsupported witness dump mode")
    require(type(witness.get("process_id")) is int and 0 < witness["process_id"] < (1 << 32),
            "invalid witness process_id")
    workload = witness.get("workload")
    require(isinstance(workload, dict), "missing workload declaration")
    labels = {name: canonical_address(workload.get(name), f"workload.{name}")
              for name in ("entry", "producer", "fault", "end")}
    entry, end = labels["entry"], labels["end"]
    require(entry < labels["producer"] < labels["fault"] < end, "unordered workload labels")
    require(0 < end - entry <= MAX_WORKLOAD_EXTENT, "invalid workload code extent")
    require(type(workload.get("expectedDecodedStarts")) is int
            and workload["expectedDecodedStarts"] == EXPECTED_STARTS, "workload must declare exactly 98 decoded starts")
    inputs = workload.get("inputs")
    require(isinstance(inputs, list) and all(type(item) is int for item in inputs)
            and tuple(inputs) == INPUTS, "witness inputs differ from the reviewed recipe")
    input_address = canonical_address(workload.get("inputsAddress"), "workload.inputsAddress")
    checked_end(input_address, 8 * len(INPUTS), "workload input range")
    require(workload.get("expectedChecksum") == hex(EXPECTED_CHECKSUM), "witness checksum differs from the independent recipe")
    require(witness_address(witness.get("fault_function_entry"), "fault_function_entry") == entry,
            "fault_function_entry disagrees with workload entry")
    extent = witness.get("expected_code_extent")
    require(isinstance(extent, dict), "missing expected_code_extent")
    require(witness_address(extent.get("address"), "code extent address") == entry
            and type(extent.get("size_bytes")) is int and extent["size_bytes"] == end - entry,
            "expected_code_extent must equal the exact workload entry/end range")
    return witness, labels, input_address


def captured_range(dump, start, size):
    """Compose bounded parser reads without relaxing hole/conflict checks."""
    require(0 < size <= MAX_WORKLOAD_EXTENT, "captured range exceeds workload limit")
    pieces, contributors = [], []
    for offset in range(0, size, MAX_CODE_EXTENT):
        data, record = dump.read_code(start + offset, min(size - offset, MAX_CODE_EXTENT))
        pieces.append(data)
        contributors.extend(record["contributors"])
    data = b"".join(pieces)
    return data, {"address": address(start), "size_bytes": size,
                  "bytes_hex": data.hex(), "sha256": hashlib.sha256(data).hexdigest(),
                  "fully_captured": True, "holes": [], "conflicts": [],
                  "contributors": contributors}


def inspect(dump_raw, witness_raw, executable_raw):
    witness, labels, input_address = read_witness(witness_raw)
    entry, site, end = labels["entry"], labels["fault"], labels["end"]
    dump = Minidump(dump_raw)
    system = dump.system()
    process_id = dump.process_id()
    require(process_id == witness["process_id"], "dump process ID disagrees with witness")
    exception, registers = dump.exception()
    require(registers["rip"] == site, "exception RIP disagrees with the declared fault label")
    require(registers["rcx"] == 0, "captured RCX is not zero")
    require(registers["rax"] == 0, "captured RAX disagrees with the reviewed final producer")
    require(registers["r10"] == input_address, "captured input-base R10 disagrees with witness")
    require(registers["r11"] == EXPECTED_CHECKSUM, "captured checksum R11 disagrees with recipe")
    module = dump.module(entry, site)
    require(end <= module["base_address"] + module["size_of_image"], "workload extent crosses demo module boundary")
    executable = PortableExecutable(executable_raw)
    require(module["timestamp"] == executable.timestamp, "dump module timestamp disagrees with supplied PE")
    require(module["size_of_image"] == executable.image_size, "dump module SizeOfImage disagrees with supplied PE")
    dump.memory(exception["thread_id"])
    full_memory = witness["dump_mode"] == "full"
    require(dump.header["mini_dump_with_full_memory"] == full_memory, "minidump flag disagrees with witness mode")
    require((9 in dump.streams and 5 not in dump.streams) if full_memory
            else (5 in dump.streams and 9 not in dump.streams), "memory stream selection disagrees with pinned Crashpad mode")
    code, code_capture = captured_range(dump, entry, end - entry)
    pe_code, pe_mapping = executable.code(entry - module["base_address"], end - entry)
    require(code == pe_code, "captured full workload extent differs from supplied PE")
    independent_decode = inspect_instructions(code, entry, labels)
    input_bytes, input_capture = captured_range(dump, input_address, len(INPUTS) * 8)
    require(input_bytes == struct.pack("<8Q", *INPUTS), "captured input bytes differ from the witness recipe")
    checksum = checksum_oracle(struct.unpack("<8Q", input_bytes))
    return {
        "schema": "ariadne.crashpad-bap-workload-inspection/v1", "passed": True,
        "integration_profile": PROFILE,
        "scope": "Independent raw-file inspection of one controlled Windows AMD64 Crashpad workload; not performance or release qualification.",
        "inputs": {"dump": dump_raw.identity(), "witness": witness_raw.identity(),
                   "executable": executable_raw.identity()},
        "system": system, "process_id": process_id, "dump_header": dump.header,
        "requested_dump_mode": witness["dump_mode"],
        "memory_stream_types": [STREAM_NAMES[kind] for kind in (5, 9) if kind in dump.streams],
        "exception": exception,
        "module": {**module, "base_address": address(module["base_address"]),
                   "preferred_pe_image_base": address(executable.image_base),
                   "entry_rva": address(entry - module["base_address"]),
                   "fault_rva": address(site - module["base_address"])},
        "query": {"entry_va": address(entry), "seed_va": address(site),
                  "producer_va": address(labels["producer"]), "entry_points": [address(entry)],
                  "slice_seeds": [address(site)], "memory_access_index": 0},
        "function_boundaries": {key: address(value) for key, value in labels.items()},
        "companion_metadata": {"module_timestamp": module["timestamp"],
                               "size_of_image": module["size_of_image"],
                               "pe_machine": "AMD64", "full_code_extent_matches": True},
        "independently_decoded_starts": independent_decode["decoded_starts"],
        "independent_decode": independent_decode,
        "code_capture": code_capture, "input_capture": input_capture,
        "pe_comparison": {**pe_mapping, "captured_bytes_hex": code.hex(),
                          "pe_bytes_hex": pe_code.hex(), "equal": True},
        "checksum_oracle": checksum,
        "producer_proof": {"address": address(labels["producer"]), "instruction": "mov rcx, rax",
                           "next_instruction": address(site), "captured_rax": address(registers["rax"]),
                           "captured_rcx": address(registers["rcx"]),
                           "kind": "reviewed local instruction semantics and crash-context observations; not an executed-history proof"},
        "fault_instruction": {"address": address(site), "bytes_hex": "c70105000000", "size_bytes": 6,
                              "reviewed_form": "mov dword ptr [rcx], 5", "address_register": "rcx",
                              "captured_address_register_value": "0x0", "access": "write",
                              "width_bytes": 4, "store_value": 5},
        "limits": [
            "Witness declares the controlled invocation; it does not authenticate an executed history.",
            "Matching PE metadata and full function bytes establish the compared extent, not whole-image identity.",
            "Checksum is an independent result for the fixed recipe and inputs, not a reconstruction of historical branches.",
            "Full-memory flags do not prove completeness of every process-memory read.",
            "Performance and BAP semantic qualification require separately retained analyzer runs.",
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
        sources = {}
        for name in ("inspect_workload.py", "inspect_capture.py", "crash_demo.cc", "bap_workload.asm"):
            path = Path(__file__).resolve().with_name(name)
            require(path.is_file(), f"missing required inspector/workload source: {path}")
            raw = BinaryFile(path)
            try:
                sources[name] = raw.identity()
            finally:
                raw.close()
        result["local_source_files"] = sources
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            output.write(json.dumps(result, indent=2) + "\n")
        print(f"Controlled workload inspection PASS: {args.output}")
    except (InspectionError, OSError, UnicodeError, ValueError, struct.error) as error:
        print(f"Workload inspection FAILED: {error}", file=sys.stderr)
        return 1
    finally:
        for raw in files:
            raw.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
