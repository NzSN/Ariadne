"""Independent workload-binding rejection cases; no native tools run here."""
import copy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import real_capture_workload as case


class RealCaptureBindings(unittest.TestCase):
    def setUp(self):
        self.pin = case.load_case()
        query = self.pin["query"]
        producer, seed = query["producer_va"], query["seed_va"]
        decoded = [f"0x{0x1000 + i:016x}" for i in range(27)] + [producer, seed]
        self.report = {
            "identity": {"artifact_sha256": self.pin["capture"]["sha256"], "platform": "windows"},
            "query": {"entries": [query["entry_va"]], "seeds": [seed]},
            "analysis": {"decoded": decoded, "edges": list(range(31)), "slice": [producer, seed],
                         "missing_slice_seeds": [], "reaching": [{"before": seed, "definitions": [
                             {"loc": f"gpr:r8:{i}", "site": producer, "origin": "instruction"}
                             for i in range(8)]}]},
            "preparation": {"sites": [{"va": va, "byte_source": "captured", "bytes_hex":
                                        "4c8b4108" if va == producer else "458a10" if va == seed else "90"}
                                       for va in decoded]},
        }

    def test_known_capture_and_all_byte_origins(self):
        case.validate_report(self.report, self.pin)

    def test_rejects_identity_root_seed_byte_and_origin_changes(self):
        def mutate(report, index):
            if index == 0: report["identity"]["platform"] = "linux"
            if index == 1: report["identity"]["artifact_sha256"] = "0" * 64
            if index == 2: report["query"]["entries"] = report["query"]["seeds"]
            if index == 3: report["analysis"]["missing_slice_seeds"] = report["query"]["seeds"]
            if index == 4: report["analysis"]["slice"] = report["query"]["seeds"]
            if index == 5: report["preparation"]["sites"][-2]["bytes_hex"] = "90"
            if index == 6: report["preparation"]["sites"][0]["byte_source"] = "file"
            if index == 7: report["analysis"]["reaching"][0]["definitions"].pop()
        for index in range(8):
            with self.subTest(index=index):
                report = copy.deepcopy(self.report)
                mutate(report, index)
                with self.assertRaises(ValueError): case.validate_report(report, self.pin)

    def test_manifest_cannot_relabel_inspected_capture_or_entry(self):
        original = (case.ROOT / case.CASE_RELATIVE).read_text()
        for field, key, value in [("capture", "sha256", "0" * 64),
                                  ("query", "entry_va", self.pin["query"]["seed_va"])]:
            altered = json.loads(original)
            altered[field][key] = value
            read = Path.read_text
            def text(path, *args, **kwargs):
                return json.dumps(altered) if path == case.ROOT / case.CASE_RELATIVE else read(path, *args, **kwargs)
            with patch.object(Path, "read_text", text), self.assertRaises(ValueError):
                case.load_case()


if __name__ == "__main__":
    unittest.main()
