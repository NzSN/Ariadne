#!/usr/bin/env python3
"""Negative raw-file regressions; fabricated files are not native acceptance."""

import copy
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest


DEMO = Path(__file__).resolve().parents[1] / "native" / "crashpad-demo"
sys.path.insert(0, str(DEMO))
SPEC = importlib.util.spec_from_file_location("crashpad_workload_inspector", DEMO / "inspect_workload.py")
INSPECTOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSPECTOR)
BASE, ENTRY, INPUT_ADDRESS = 0x140000000, 0x140001000, 0x140002000
TIMESTAMP, PROCESS_ID = 123456, 42


def reviewed_fixture_code():
    # Use the admitted recipe only to construct a positive fixture. Tests below
    # change transport bytes, labels, and declarations to exercise rejection.
    recipe, labels = INSPECTOR.instruction_recipe()
    starts, code = [], bytearray()
    for instruction in recipe:
        starts.append(len(code))
        code.extend(instruction["encodings"][0])
    starts.append(len(code))
    for start, instruction in zip(starts, recipe):
        if "target" in instruction:
            code[start + 1] = (starts[labels[instruction["target"]]] - start - 2) & 255
    return bytes(code), {name: ENTRY + starts[index] for name, index in labels.items()}


def pe_fixture(code):
    data = bytearray(1024)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", data, 0x84, 0x8664, 1, TIMESTAMP, 0, 0, 240, 0)
    optional = 0x98
    struct.pack_into("<H", data, optional, 0x20B)
    struct.pack_into("<Q", data, optional + 24, BASE)
    struct.pack_into("<II", data, optional + 56, 0x3000, 512)
    struct.pack_into("<8sIIIIIIHHI", data, optional + 240,
                     b".text", 512, 0x1000, 512, 512, 0, 0, 0, 0, 0x60000020)
    data[512:512 + len(code)] = code
    return data


def dump_fixture(code, labels, *, code_size=None, conflict=False,
                 altered_inputs=False, mode="partial"):
    data = bytearray(32 + 5 * 12)
    streams = []

    def append(payload):
        offset = len(data)
        data.extend(payload)
        return offset

    def stream(kind, payload):
        offset = append(payload)
        streams.append((kind, len(payload), offset))

    context = bytearray(1232)
    struct.pack_into("<I", context, 48, 0x00100003)
    registers = [0] * 17
    registers[10], registers[11], registers[16] = INPUT_ADDRESS, INSPECTOR.EXPECTED_CHECKSUM, labels["fault"]
    struct.pack_into("<17Q", context, 120, *registers)
    context_offset = append(context)
    system = bytearray(56)
    struct.pack_into("<H", system, 0, 9)
    struct.pack_into("<II", system, 20, 2, 0)
    stream(7, system)
    stream(15, struct.pack("<6I", 24, 1, PROCESS_ID, 0, 0, 0))
    exception = bytearray(168)
    struct.pack_into("<IIIIQQII", exception, 0, 7, 0, 0xC0000005, 0, 0, labels["fault"], 2, 0)
    struct.pack_into("<QQ", exception, 40, 1, 0)
    struct.pack_into("<II", exception, 160, len(context), context_offset)
    stream(6, exception)
    name = "C:\\test\\ariadne_crash_demo.exe".encode("utf-16-le")
    name_offset = append(struct.pack("<I", len(name)) + name)
    modules = bytearray(112)
    struct.pack_into("<I", modules, 0, 1)
    struct.pack_into("<QIIII", modules, 4, BASE, 0x3000, 0, TIMESTAMP, name_offset)
    stream(4, modules)
    inputs = list(INSPECTOR.INPUTS)
    if altered_inputs:
        inputs[0] += 1
    payloads = [(ENTRY, code[:code_size]), (INPUT_ADDRESS, struct.pack("<8Q", *inputs))]
    if conflict:
        payloads.append((ENTRY + 300, bytes((code[300] ^ 1,))))
    if mode == "full":
        payload_offset = append(b"".join(payload for _, payload in payloads))
        memory = struct.pack("<QQ", len(payloads), payload_offset)
        memory += b"".join(struct.pack("<QQ", va, len(payload)) for va, payload in payloads)
        stream(9, memory)
    else:
        memory = struct.pack("<I", len(payloads))
        for va, payload in payloads:
            offset = append(payload)
            memory += struct.pack("<QII", va, len(payload), offset)
        stream(5, memory)
    struct.pack_into("<IIIIIIQ", data, 0, 0x504D444D, 0xA793, len(streams), 32, 0, 0, 2 if mode == "full" else 0)
    for index, item in enumerate(streams):
        struct.pack_into("<III", data, 32 + index * 12, *item)
    return data


def witness_fixture(labels):
    return {"schema_version": 1, "integration_profile": INSPECTOR.PROFILE,
            "expected_data_address": "0x0", "expected_access": "write",
            "expected_width_bytes": 4, "expected_store_value": 5,
            "explicit_code_range_registered": True, "explicit_input_range_registered": True,
            "dump_mode": "partial", "process_id": PROCESS_ID,
            "fault_function_entry": hex(ENTRY),
            "expected_code_extent": {"address": hex(ENTRY), "size_bytes": labels["end"] - ENTRY},
            "workload": {**{name: INSPECTOR.address(labels[name]) for name in ("entry", "producer", "fault", "end")},
                         "expectedDecodedStarts": 98, "inputs": list(INSPECTOR.INPUTS),
                         "inputsAddress": INSPECTOR.address(INPUT_ADDRESS), "expectedChecksum": "0x4bea2"}}


class InspectorTests(unittest.TestCase):
    def setUp(self):
        self.code, self.labels = reviewed_fixture_code()
        self.witness = witness_fixture(self.labels)

    def inspect(self, *, witness=None, code=None, pe_code=None, **dump_options):
        code = self.code if code is None else code
        witness = self.witness if witness is None else witness
        with tempfile.TemporaryDirectory() as directory:
            raw_files = []
            try:
                for name, payload in (("capture.dmp", dump_fixture(code, self.labels, **dump_options)),
                                      ("witness.json", json.dumps(witness).encode()),
                                      ("demo.exe", pe_fixture(code if pe_code is None else pe_code))):
                    path = Path(directory) / name
                    path.write_bytes(payload)
                    raw_files.append(INSPECTOR.BinaryFile(path))
                return INSPECTOR.inspect(*raw_files)
            finally:
                for raw in raw_files:
                    raw.close()

    def test_valid_partial_and_full_fabricated_captures(self):
        for mode in ("partial", "full"):
            with self.subTest(mode=mode):
                witness = copy.deepcopy(self.witness)
                witness["dump_mode"] = mode
                result = self.inspect(witness=witness, mode=mode)
                self.assertTrue(result["passed"])
                self.assertEqual(result["independently_decoded_starts"], 98)
                self.assertEqual(result["function_boundaries"]["producer"], INSPECTOR.address(ENTRY + 369))
                self.assertEqual(result["checksum_oracle"]["checksum"], "0x4bea2")

    def test_missing_code_byte_rejected(self):
        with self.assertRaisesRegex(INSPECTOR.InspectionError, "missing bytes"):
            self.inspect(code_size=len(self.code) - 1)

    def test_conflict_beyond_original_256_byte_limit_rejected(self):
        with self.assertRaisesRegex(INSPECTOR.InspectionError, "conflicting overlapping bytes"):
            self.inspect(conflict=True)

    def test_wrong_producer_boundary_rejected(self):
        self.witness["workload"]["producer"] = INSPECTOR.address(self.labels["producer"] + 1)
        with self.assertRaisesRegex(INSPECTOR.InspectionError, "producer.*boundary"):
            self.inspect()

    def test_wrong_checksum_rejected(self):
        self.witness["workload"]["expectedChecksum"] = "0x4bea3"
        with self.assertRaisesRegex(INSPECTOR.InspectionError, "witness checksum"):
            self.inspect()

    def test_changed_input_capture_rejected(self):
        with self.assertRaisesRegex(INSPECTOR.InspectionError, "captured input bytes"):
            self.inspect(altered_inputs=True)

    def test_wrong_loop_target_rejected_even_with_matching_pe(self):
        code = bytearray(self.code)
        code[321] += 1  # JNE's signed displacement; opcode is at offset 320.
        with self.assertRaisesRegex(INSPECTOR.InspectionError, "short branch target"):
            self.inspect(code=bytes(code))

    def test_pe_mismatch_in_tail_rejected(self):
        pe_code = bytearray(self.code)
        pe_code[-1] = 0x90
        with self.assertRaisesRegex(INSPECTOR.InspectionError, "full workload extent differs"):
            self.inspect(pe_code=bytes(pe_code))

    def test_wrong_fault_site_rejected(self):
        self.witness["workload"]["fault"] = INSPECTOR.address(self.labels["fault"] + 1)
        with self.assertRaisesRegex(INSPECTOR.InspectionError, "RIP disagrees"):
            self.inspect()


if __name__ == "__main__":
    unittest.main()
