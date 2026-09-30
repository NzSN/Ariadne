"""Acceptance-barrier and bounded-measurement regressions, without external dumps."""
import argparse
import copy
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from check_priority1_real_capture import CheckFailure
from check_priority4_real_capture import pe_witness
from measure_priority4 import digest, qualifies, synthetic_runs


class Priority4Tests(unittest.TestCase):
    def test_pe_entry_requires_matching_identity_and_runtime_function(self):
        data = bytearray(1024)
        data[:2] = b"MZ"
        struct.pack_into("<I", data, 0x3c, 0x80)
        data[0x80:0x84] = b"PE\0\0"
        struct.pack_into("<HHI", data, 0x84, 0x8664, 1, 123)
        struct.pack_into("<H", data, 0x94, 240)
        optional = 0x98
        struct.pack_into("<H", data, optional, 0x20b)
        struct.pack_into("<Q", data, optional + 24, 0x140000000)
        struct.pack_into("<I", data, optional + 56, 0x2000)
        struct.pack_into("<IIII", data, optional + 240 + 8, 512, 0x1000, 512, 512)
        struct.pack_into("<II", data, optional + 136, 0x1100, 12)
        struct.pack_into("<III", data, 0x300, 0x1180, 0x1190, 0x11a0)
        struct.pack_into("<II", data, optional + 160, 0x1120, 28)
        struct.pack_into("<IIII", data, 0x320 + 12, 2, 24, 0x1140, 0x340)
        data[0x340:0x358] = b"RSDS" + b"\x01" * 16 + b"\x01\0\0\0"
        data[0x380:0x390] = b"\x90" * 15 + b"\xc3"
        wanted = {"timestamp": "0x7b", "image_size": "0x2000",
                  "rsds_hex": bytes(data[0x340:0x358]).hex(),
                  "function_begin_rva": "0x1180", "function_end_rva": "0x1190"}
        query = {"entry_rva": "0x1180", "seed_rva": "0x118f"}
        self.assertEqual(pe_witness(data, wanted, query),
                         (0x140000000, b"\x90" * 15 + b"\xc3"))
        for field in ("timestamp", "image_size", "rsds_hex", "function_begin_rva"):
            bad = copy.deepcopy(wanted)
            bad[field] = "0x1" if field != "rsds_hex" else "00" * 24
            with self.assertRaises(CheckFailure):
                pe_witness(data, bad, query)
        with self.assertRaises(CheckFailure):
            pe_witness(data, wanted, {**query, "entry_rva": "0x1181"})
        with self.assertRaises(CheckFailure):
            pe_witness(data[:800], wanted, query)

    def test_a_large_graph_cannot_qualify_without_the_same_source_and_query(self):
        with tempfile.TemporaryDirectory() as directory:
            dump = Path(directory) / "capture.dmp"
            dump.write_bytes(b"identity fixture")
            args = argparse.Namespace(dump=dump, entry="0x1000", seed="0x1010")
            tools = {"cli": "a", "decoder": "b"}
            sources = {"engine": "c"}
            identity = {"query_id": "d"}
            record = {"passed": True, "source_stable": True,
                      "dump_sha256": digest(dump), "entry_va": args.entry,
                      "seed_va": args.seed, "tool_sha256": tools,
                      "source_sha256": sources, "report_identity": identity,
                      "observations": {"decoded": 64, "slice": 2}}
            self.assertTrue(qualifies(record, args, identity, tools, sources))
            self.assertFalse(qualifies(None, args, identity, tools, sources))
            for field in ("dump_sha256", "source_sha256", "report_identity",
                          "tool_sha256", "entry_va", "seed_va", "passed"):
                bad = copy.deepcopy(record)
                bad[field] = "0x0" if field.endswith("va") else None
                self.assertFalse(qualifies(bad, args, identity, tools, sources), field)

    def test_later_timeout_retains_completed_sizes_and_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            args = argparse.Namespace(synthetic_sizes=(128, 512),
                                      synthetic_bench=Path("benchmark"), runs=5)
            completed = "workload,n,run\n" + "".join(
                f"{kind},128,{run}\n" for kind in ("linear", "loops", "joins", "calls", "dense")
                for run in range(5))
            warm = subprocess.CompletedProcess([], 0, stdout="", stderr="")
            measured = subprocess.CompletedProcess([], 0, stdout=completed, stderr="")
            timeout = subprocess.TimeoutExpired(["benchmark"], 180,
                                                output=b"workload,n,run\nlinear,512,0\n")
            with patch("measure_priority4.command", side_effect=[warm, measured, warm, timeout]):
                outcomes = synthetic_runs(args, output)
            self.assertEqual((output / "synthetic.csv").read_text(), completed)
            self.assertEqual([row["status"] for row in outcomes], ["complete", "timeout"])
            self.assertEqual(outcomes[1]["timeout_seconds"], 180)
            self.assertIn("linear,512,0", (output / outcomes[1]["partial_csv"]).read_text())
            self.assertEqual(json.loads((output / "synthetic-outcomes.json").read_text()), outcomes)


if __name__ == "__main__":
    unittest.main()
