"""Reject inconsistent replacement pins and bundled input substitutions."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import investigation_windows_case as contract


class WindowsCaseTests(unittest.TestCase):
    def setUp(self):
        self.case = contract.load_case()

    def test_case_and_canonical_identity(self):
        contract.validate_case(self.case)
        self.assertEqual(contract.case_digest(self.case),
                         contract.case_digest(dict(reversed(list(self.case.items())))))

    def test_policy_size_question_and_case_identity_cannot_change(self):
        changes = [("schema", None, "ariadne-priority-4-real-capture-case-v1"),
                   ("id", None, "other"), ("expectations", "decodedStarts", 2),
                   ("expectations", "windowsBudgetMs", None),
                   ("expectations", "windowsBudgetMs", 9000),
                   ("expectations", "timingPolicy", "unlimited"),
                   ("query", "memory_access_index", True),
                   ("query", "memory_access_index", 1)]
        for outer, inner, value in changes:
            case = copy.deepcopy(self.case)
            if inner is None:
                case[outer] = value
            else:
                case[outer][inner] = value
            with self.subTest(outer=outer, inner=inner), self.assertRaises(ValueError):
                contract.validate_case(case)

    def test_original_capture_cannot_substitute_for_active_pin(self):
        with tempfile.TemporaryDirectory() as folder:
            wrong = Path(folder) / "original.dmp"
            wrong.write_bytes(b"other capture")
            with self.assertRaisesRegex(ValueError, "override"):
                contract.materialize(self.case, Path(folder) / "inputs", wrong)

    def test_bundle_and_inspection_digests_are_required(self):
        for section in ("inputArchive", "independentInspection"):
            case = copy.deepcopy(self.case)
            case[section]["sha256"] = "0" * 64
            with tempfile.TemporaryDirectory() as folder, self.subTest(section=section):
                with self.assertRaisesRegex(ValueError, "digest|inspection changed"):
                    contract.materialize(case, Path(folder) / "inputs")

    def test_producer_query_cannot_disagree_with_independent_witness(self):
        case = copy.deepcopy(self.case)
        case["query"]["producer_va"] = "0x0000000000000001"
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "witness"):
                contract.materialize(case, Path(folder) / "inputs")

    def test_full_bundle_materializes_without_image_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / "inputs"
            dump = contract.materialize(self.case, directory)
            self.assertEqual(contract.sha(dump), self.case["capture"]["sha256"])
            self.assertEqual(contract.sha(directory / "ariadne_crash_demo.exe"),
                             self.case["companion"]["sha256"])

    def test_unsafe_archive_member_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            case = copy.deepcopy(self.case)
            archive = root / contract.ARCHIVE_RELATIVE
            archive.parent.mkdir(parents=True)
            data = b"unexpected"
            with tarfile.open(archive, "w:gz") as bundle:
                member = tarfile.TarInfo("../escape")
                member.size = len(data)
                bundle.addfile(member, io.BytesIO(data))
            case["inputArchive"]["sha256"] = contract.sha(archive)
            case["inputArchive"]["entries"] = {"../escape": hashlib.sha256(data).hexdigest()}
            inspection = root / contract.INSPECTION_RELATIVE
            inspection.write_bytes((contract.ROOT / contract.INSPECTION_RELATIVE).read_bytes())
            with patch.object(contract, "ROOT", root), self.assertRaisesRegex(ValueError, "unsafe"):
                contract.materialize(case, root / "inputs")
            self.assertFalse((root / "escape").exists())


if __name__ == "__main__":
    unittest.main()
