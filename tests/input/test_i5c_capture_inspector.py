#!/usr/bin/env python3
"""Tiny synthetic raw-file/corruption controls; never native acceptance."""
import hashlib
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

NATIVE = Path(__file__).resolve().parents[2] / "native/crashpad-demo"
sys.path.insert(0, str(NATIVE))
import inspect_i5c as oracle


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


class Fixture:
    """Small independently packed PE/minidump and synthetic producer receipts."""
    def __init__(self, directory, recipe="upper", mode="partial"):
        self.root = directory
        self.capture = directory / "capture"
        self.capture.mkdir()
        self.build_dir = directory / "build"
        self.build_dir.mkdir()
        self.build_path = self.build_dir / "build.json"
        self.inputs_path = self.build_dir / "build-inputs.json"
        self.source = self.build_dir / "source"
        self.demo_sources = self.source / "examples/ariadne_demo"
        self.demo_sources.mkdir(parents=True)
        demo_hashes = {}
        for name in ["BUILD.gn", "crash_demo.cc", "fault.cc", "bap_workload.asm",
                     "zero_base_offset.asm", "address_wrap.asm"]:
            shutil.copyfile(NATIVE / name, self.demo_sources / name)
            demo_hashes[name] = sha(NATIVE / name)
        tool_hashes = {}
        for name in ["clang-cl.exe", "lld-link.exe", "llvm-ml.exe", "gn.exe", "ninja.exe"]:
            path = (self.build_dir / "tools" / name if name in ("gn.exe", "ninja.exe") else
                    self.source / "third_party/windows/clang/win-amd64/bin" / name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"synthetic-not-executable-" + name.encode())
            tool_hashes[name] = sha(path)
        tool_hashes["python.exe"] = "0" * 64
        self.inputs = {
            "schema": "ariadne.crashpad-demo-build-inputs/v1", "crashpadBranch": "nzsn",
            "crashpadRevision": oracle.CRASHPAD_REVISION,
            "gnRevision": "5e19d2fb166fbd4f6f32147fbb2f497091a54ad8",
            "windowsClang": {"archive": "clang-llvmorg-20-init-17108-g29ed6000-2.tar.xz",
                             "sha256": "1c71efd923a91480480d4f31c2fd5f1369e01e14f15776a9454abbce0bc13548"},
            "demoSourceHashes": demo_hashes,
            "sourceHashes": {p.relative_to(self.source).as_posix(): sha(p)
                             for p in self.source.rglob("*") if p.is_file()},
            "buildOnlyAdjustments": {"preparationScriptSha256": sha(NATIVE / "prepare.py")}}
        write_json(self.inputs_path, self.inputs)
        (self.build_dir / "source.tar.gz").write_bytes(b"synthetic archive identity; never extracted")
        self.binaries = self.source / "out/Release"
        self.binaries.mkdir(parents=True)
        profile, base, disp, encoding, index, conclusion = oracle.RECIPES[recipe]
        self.entry = 0x140001000
        reviewed = bytes.fromhex(encoding + "c3")
        self.pe_data = bytearray(0x400)
        self.pe_data[:2] = b"MZ"
        struct.pack_into("<I", self.pe_data, 0x3c, 0x80)
        self.pe_data[0x80:0x84] = b"PE\0\0"
        struct.pack_into("<HHIIIHH", self.pe_data, 0x84, 0x8664, 1, 0x12345678, 0, 0, 240, 0)
        struct.pack_into("<H", self.pe_data, 0x98, 0x20b)
        struct.pack_into("<Q", self.pe_data, 0x98 + 24, 0x140000000)
        struct.pack_into("<II", self.pe_data, 0x98 + 56, 0x2000, 0x200)
        struct.pack_into("<8sIIIIIIHHI", self.pe_data, 0x188,
                         b".text\0\0\0", 0x200, 0x1000, 0x200, 0x200, 0, 0, 0, 0, 0x60000020)
        self.pe_data[0x200:0x300] = reviewed + b"\x90" * (256 - len(reviewed))
        (self.binaries / "ariadne_crash_demo.exe").write_bytes(self.pe_data)
        for name in ("crashpad_handler.exe", "crashpad_database_util.exe"):
            (self.binaries / name).write_bytes(b"synthetic-" + name.encode())
        self.build = {
            "schema": "ariadne.crashpad-demo-windows-build/v1", "passed": True, "architecture": "x64",
            "sourcesStable": True, "stableGnRegeneration": True, "unsupportedArm64Rejected": True,
            "crashpadRevision": oracle.CRASHPAD_REVISION,
            "buildScriptSha256": sha(NATIVE / "build_windows.py"), "toolHashes": tool_hashes,
            "buildOnlyAdjustments": self.inputs["buildOnlyAdjustments"],
            "inputs": {"inputsSha256": sha(self.inputs_path),
                       "sourceArchiveSha256": sha(self.build_dir / "source.tar.gz")},
            "binaryDirectory": str(self.binaries),
            "binaryHashes": {p.name: sha(p) for p in self.binaries.iterdir()}}
        write_json(self.build_path, self.build)
        self.build_sha = sha(self.build_path)
        shutil.copyfile(self.binaries / "ariadne_crash_demo.exe", self.capture / "ariadne_crash_demo.exe")
        self.witness = {
            "schema_version": 1, "process_id": 41, "fault_function_entry": hex(self.entry),
            "expected_data_address": "0x8", "expected_access": "write", "expected_width_bytes": 4,
            "expected_store_value": 5, "dump_mode": mode,
            "integration_profile": "ariadne-crashpad-" + profile + "-v1",
            "expected_code_extent": {"address": hex(self.entry), "size_bytes": 256},
            "explicit_code_range_registered": True,
            "address_wrap": {"recipe": recipe, "expected_rcx": oracle.hx(base), "expected_rdx": oracle.hx(0),
                             "displacement": disp, "instruction_bytes": encoding,
                             "expected_conclusion": conclusion}}
        write_json(self.capture / "witness.json", self.witness)
        self.dump = bytearray(32 + 6 * 12)
        streams = []

        def allocate(size):
            offset = len(self.dump)
            self.dump.extend(b"\0" * size)
            return offset

        def stream(kind, size):
            offset = allocate(size)
            streams.append((kind, size, offset))
            return offset

        system = stream(7, 56)
        struct.pack_into("<H", self.dump, system, 9)
        struct.pack_into("<I", self.dump, system + 20, 2)
        self.misc = stream(15, 24)
        struct.pack_into("<III", self.dump, self.misc, 24, 1, 41)
        self.exception = stream(6, 168)
        self.modules = stream(4, 112)
        self.threads = stream(3, 52)
        self.memory = stream(9 if mode == "full" else 5, 48 if mode == "full" else 36)
        self.context = allocate(1232)
        self.code_offset = allocate(256)
        self.dump[self.code_offset:self.code_offset + 256] = self.pe_data[0x200:0x300]
        name_bytes = b"ariadne_crash_demo.exe".decode().encode("utf-16-le")
        name_rva = allocate(4 + len(name_bytes))
        struct.pack_into("<I", self.dump, name_rva, len(name_bytes))
        self.dump[name_rva + 4:] = name_bytes
        struct.pack_into("<IIIIQQII", self.dump, self.exception,
                         7, 0, 0xc0000005, 0, 0, self.entry, 2, 0)
        struct.pack_into("<QQ", self.dump, self.exception + 40, 1, 8)
        struct.pack_into("<II", self.dump, self.exception + 160, 1232, self.context)
        struct.pack_into("<I", self.dump, self.context + 48, 0x100003)
        struct.pack_into("<QQ", self.dump, self.context + 128, base, 0)
        struct.pack_into("<Q", self.dump, self.context + 248, self.entry)
        struct.pack_into("<I", self.dump, self.modules, 1)
        struct.pack_into("<QIIII", self.dump, self.modules + 4, 0x140000000, 0x2000, 0, 0x12345678, name_rva)
        struct.pack_into("<I", self.dump, self.threads, 1)
        struct.pack_into("<I", self.dump, self.threads + 4, 7)
        struct.pack_into("<II", self.dump, self.threads + 4 + 40, 1232, self.context)
        if mode == "full":
            struct.pack_into("<QQQQ", self.dump, self.memory, 1, self.code_offset, self.entry, 256)
        else:
            struct.pack_into("<IQII", self.dump, self.memory, 1, self.entry, 256, self.code_offset)
        struct.pack_into("<IIIIIIQ", self.dump, 0, 0x504d444d, 0xa793, 6, 32, 0, 0, 2 if mode == "full" else 0)
        for i, row in enumerate(streams):
            struct.pack_into("<III", self.dump, 32 + i * 12, *row)
        (self.capture / "capture.dmp").write_bytes(self.dump)
        self.record = {
            "schema": "ariadne.crashpad-demo-capture/v1", "captureCreated": True,
            "mode": mode, "profile": profile, "integrationProfile": self.witness["integration_profile"],
            "processId": 41, "exitCode": "0xc0000005", "uploadsEnabled": False,
            "crashpadRevision": oracle.CRASHPAD_REVISION, "buildRecordSha256": self.build_sha,
            "buildInputsSha256": sha(self.inputs_path),
            "sourceArchiveSha256": sha(self.build_dir / "source.tar.gz"), "addressWrapRecipe": recipe,
            "childEnvironment": {"policy": "minimal-windows/v1", "keys": oracle.ENVIRONMENT_KEYS},
            "handlerSha256": self.build["binaryHashes"]["crashpad_handler.exe"]}
        self.refresh_capture()

    def refresh_capture(self):
        write_json(self.capture / "witness.json", self.witness)
        (self.capture / "capture.dmp").write_bytes(self.dump)
        self.record.update(dump={"sha256": sha(self.capture / "capture.dmp"), "bytes": len(self.dump)},
                           witnessSha256=sha(self.capture / "witness.json"),
                           executableSha256=sha(self.capture / "ariadne_crash_demo.exe"))
        write_json(self.capture / "capture.json", self.record)

    def inspect(self):
        return oracle.inspect(self.capture, self.build_path, self.build_sha)


class InspectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_eight_exact_cases_and_payload_role(self):
        for recipe in oracle.RECIPES:
            for mode in ("partial", "full"):
                with self.subTest(recipe=recipe, mode=mode):
                    directory = self.root / (recipe + mode)
                    directory.mkdir()
                    result = Fixture(directory, recipe, mode).inspect()
                    self.assertTrue(result["passed"])
                    self.assertEqual(result["case"], recipe + "-" + mode)
                    self.assertEqual(result["arithmetic"]["quotient"], 1 if recipe in ("upper", "indexed") else 0)
                    self.assertEqual(result["arithmetic"]["effective_address"], oracle.hx(8))
                    self.assertFalse(result["instruction"]["payload_contributes_to_address"])
                    self.assertEqual(result["instruction"]["immediate_payload"], 5)
                    if recipe == "negative":
                        self.assertEqual(result["arithmetic"]["wide_sum_decimal"], "8")
                    if recipe == "indexed":
                        self.assertEqual(result["expectedConclusion"], "unknown")
                        self.assertFalse(result["arithmetic"]["question_admitted_shape"])

    def test_existing_frozen_inventory_matches_exact_eight_recipes(self):
        frozen = json.loads((NATIVE.parents[1] / "tests/input/fixtures/i5c/owned-captures.json").read_text())
        self.assertEqual(len(frozen["cases"]), 8)
        self.assertEqual({row["case"] for row in frozen["cases"]},
                         {name + "-" + mode for name in oracle.RECIPES for mode in ("partial", "full")})
        for row in frozen["cases"]:
            profile, base, disp, code, index, answer = oracle.RECIPES[row["name"]]
            self.assertEqual((row["rcx"], row["rdx"], row["code"], row["expected"]),
                             (oracle.hx(base), oracle.hx(0), code, answer))
            self.assertEqual((row["decoded_receipt"]["base"], row["decoded_receipt"]["index"],
                              row["decoded_receipt"]["signed_displacement"]), ("rcx", index, disp))

    def test_native_preparation_windows_inventory_separators(self):
        f = Fixture(self.root)
        f.inputs["sourceHashes"] = {key.replace("/", "\\"): value
                                   for key, value in f.inputs["sourceHashes"].items()}
        write_json(f.inputs_path, f.inputs)
        f.build["inputs"]["inputsSha256"] = sha(f.inputs_path)
        write_json(f.build_path, f.build)
        f.build_sha = sha(f.build_path)
        f.record.update(buildRecordSha256=f.build_sha, buildInputsSha256=sha(f.inputs_path))
        f.refresh_capture()
        self.assertTrue(f.inspect()["passed"])

    def test_raw_observation_corruptions_rejected_even_with_rebound_dump_digest(self):
        changes = {
            "missing-integer": lambda f: struct.pack_into("<I", f.dump, f.context + 48, 0x100001),
            "missing-control": lambda f: struct.pack_into("<I", f.dump, f.context + 48, 0x100002),
            "other-architecture": lambda f: struct.pack_into("<I", f.dump, f.context + 48, 0x400003),
            "wrong-rcx": lambda f: struct.pack_into("<Q", f.dump, f.context + 128, 8),
            "wrong-rdx": lambda f: struct.pack_into("<Q", f.dump, f.context + 136, 1),
            "wrong-rip": lambda f: struct.pack_into("<Q", f.dump, f.context + 248, f.entry + 1),
            "read-not-write": lambda f: struct.pack_into("<Q", f.dump, f.exception + 40, 0),
            "wrong-inaccessible-byte": lambda f: struct.pack_into("<Q", f.dump, f.exception + 48, 5),
            "wrong-parameter-count": lambda f: struct.pack_into("<I", f.dump, f.exception + 32, 3),
            "wrong-process": lambda f: struct.pack_into("<I", f.dump, f.misc + 8, 42),
            "wrong-thread": lambda f: struct.pack_into("<I", f.dump, f.threads + 4, 8),
            "wrong-ret": lambda f: f.dump.__setitem__(f.code_offset + 7, 0x90),
            "wrong-payload": lambda f: f.dump.__setitem__(f.code_offset + 3, 4),
            "code-hole": lambda f: struct.pack_into("<I", f.dump, f.memory + 12, 1),
            "wrong-full-flag": lambda f: struct.pack_into("<Q", f.dump, 24, 2),
            "wrong-module-time": lambda f: struct.pack_into("<I", f.dump, f.modules + 4 + 16, 1),
        }
        for name, change in changes.items():
            with self.subTest(name=name):
                directory = self.root / name
                directory.mkdir()
                f = Fixture(directory)
                change(f)
                f.refresh_capture()
                with self.assertRaises(oracle.InspectionError):
                    f.inspect()

    def test_conflicting_contributors_rejected(self):
        f = Fixture(self.root)
        extra = len(f.dump)
        f.dump.append(0x90)
        struct.pack_into("<I", f.dump, f.memory, 2)
        struct.pack_into("<QII", f.dump, f.memory + 20, f.entry, 1, extra)
        f.refresh_capture()
        with self.assertRaisesRegex(oracle.InspectionError, "conflicting"):
            f.inspect()

    def test_witness_corruptions_rejected(self):
        changes = {
            "entry": lambda w: w.update(fault_function_entry="0x140001001"),
            "base-intent": lambda w: w["address_wrap"].update(expected_rcx=oracle.hx(8)),
            "unsigned-disp": lambda w: w["address_wrap"].update(displacement=248),
            "instruction": lambda w: w["address_wrap"].update(instruction_bytes="c70105000000"),
            "conclusion": lambda w: w["address_wrap"].update(expected_conclusion="unknown"),
            "bool-width": lambda w: w.update(expected_width_bytes=True),
            "extent": lambda w: w["expected_code_extent"].update(size_bytes=6),
        }
        for name, change in changes.items():
            with self.subTest(name=name):
                directory = self.root / name
                directory.mkdir()
                f = Fixture(directory)
                change(f.witness)
                f.refresh_capture()
                with self.assertRaises(oracle.InspectionError):
                    f.inspect()

    def test_build_authentication_source_and_archive_corruptions(self):
        for name in ("independent-digest", "source", "archive", "capture-digest", "environment"):
            with self.subTest(name=name):
                directory = self.root / name
                directory.mkdir()
                f = Fixture(directory)
                if name == "independent-digest":
                    f.build_sha = "0" * 64
                elif name == "source":
                    (f.demo_sources / "address_wrap.asm").write_bytes(b"changed")
                elif name == "archive":
                    (f.build_dir / "source.tar.gz").write_bytes(b"changed")
                elif name == "capture-digest":
                    f.record["witnessSha256"] = "0" * 64
                else:
                    f.record["childEnvironment"] = {"policy": "inherited"}
                write_json(f.capture / "capture.json", f.record)
                with self.assertRaises(oracle.InspectionError):
                    f.inspect()

    def test_pe_comparison_rejects_rebound_wrong_binary(self):
        f = Fixture(self.root)
        f.pe_data[0x200] = 0x90
        (f.binaries / "ariadne_crash_demo.exe").write_bytes(f.pe_data)
        (f.capture / "ariadne_crash_demo.exe").write_bytes(f.pe_data)
        f.build["binaryHashes"]["ariadne_crash_demo.exe"] = sha(f.binaries / "ariadne_crash_demo.exe")
        write_json(f.build_path, f.build)
        f.build_sha = sha(f.build_path)
        f.record["buildRecordSha256"] = f.build_sha
        f.refresh_capture()
        with self.assertRaisesRegex(oracle.InspectionError, "executable PE"):
            f.inspect()

    def test_existing_output_preserved(self):
        output = self.root / "existing.json"
        output.write_bytes(b"retained")
        with patch.object(sys, "argv", ["inspect_i5c.py", "--capture", str(self.root),
                           "--build", str(self.root / "missing.json"),
                           "--expected-build-sha256", "0" * 64, "--output", str(output)]):
            self.assertEqual(oracle.main(), 1)
        self.assertEqual(output.read_bytes(), b"retained")

    def test_duplicate_witness_key_rejected(self):
        f = Fixture(self.root)
        path = f.capture / "witness.json"
        path.write_text(path.read_text().replace('"process_id": 41', '"process_id": 41, "process_id": 41'))
        f.record["witnessSha256"] = sha(path)
        write_json(f.capture / "capture.json", f.record)
        with self.assertRaisesRegex(oracle.InspectionError, "duplicate"):
            f.inspect()

    def test_failed_publication_retains_no_partial_result(self):
        output = self.root / "inspection.json"
        with patch.object(oracle.os, "link", side_effect=OSError("injected publication failure")):
            with self.assertRaisesRegex(OSError, "injected"):
                oracle.publish_new(output, {"passed": True})
        self.assertFalse(output.exists())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_publication_is_complete_and_never_overwrites(self):
        output = self.root / "inspection.json"
        oracle.publish_new(output, {"passed": True})
        self.assertEqual(json.loads(output.read_text()), {"passed": True})
        with self.assertRaises(FileExistsError):
            oracle.publish_new(output, {"passed": False})
        self.assertEqual(json.loads(output.read_text()), {"passed": True})

    def test_postcommit_cleanup_failure_is_committed_cli_success(self):
        f = Fixture(self.root)
        output = self.root / "inspection.json"
        stderr, stdout = io.StringIO(), io.StringIO()
        argv = ["inspect_i5c.py", "--capture", str(f.capture), "--build", str(f.build_path),
                "--expected-build-sha256", f.build_sha, "--output", str(output)]
        with patch.object(sys, "argv", argv), redirect_stderr(stderr), redirect_stdout(stdout):
            with patch.object(oracle.os, "unlink", side_effect=OSError("injected cleanup failure")):
                self.assertEqual(oracle.main(), 0)
        self.assertTrue(json.loads(output.read_text())["passed"])
        self.assertIn("publication committed; temporary cleanup warning:", stderr.getvalue())
        self.assertIn("inspection PASS:", stdout.getvalue())
        self.assertEqual(len(list(self.root.glob(".i5c-inspection-*.tmp"))), 1)

    def test_precommit_link_and_cleanup_failure_preserves_original_cli_failure(self):
        f = Fixture(self.root)
        output = self.root / "inspection.json"
        stderr, stdout = io.StringIO(), io.StringIO()
        argv = ["inspect_i5c.py", "--capture", str(f.capture), "--build", str(f.build_path),
                "--expected-build-sha256", f.build_sha, "--output", str(output)]
        with patch.object(sys, "argv", argv), redirect_stderr(stderr), redirect_stdout(stdout):
            with patch.object(oracle.os, "link", side_effect=OSError("original injected link failure")):
                with patch.object(oracle.os, "unlink", side_effect=OSError("secondary cleanup failure")):
                    self.assertEqual(oracle.main(), 1)
        self.assertFalse(output.exists())
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("publication not committed; temporary cleanup warning:", stderr.getvalue())
        self.assertIn("I5c inspection FAILED: original injected link failure", stderr.getvalue())
        self.assertEqual(len(list(self.root.glob(".i5c-inspection-*.tmp"))), 1)


if __name__ == "__main__":
    unittest.main()
