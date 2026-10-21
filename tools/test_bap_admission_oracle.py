"""Fresh-lift transport controls, distinct from native semantic qualification."""
import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

import check_bap_admission_oracle as oracle


class FreshScalarLiftTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.contract = self.root / "contract.json"
        self.contract.write_text('{"input":"current"}')
        self.helper = self.root / "helper"
        self.helper.write_bytes(b"selected helper")
        self.cases = [{"name": "first", "bytes": "90"}, {"name": "second", "bytes": "c3"}]
        snapshot = hashlib.sha256(self.contract.read_bytes()).hexdigest()
        self.frames = [dict(schema="ariadne.bap-ready/v1", snapshot=snapshot,
                            target="windows-amd64", version="2.5.0-alpha", lifter="legacy")]
        self.frames.extend(dict(schema="ariadne.bap-site/v1", snapshot=snapshot, batch=0,
                                va=f"0x{0x401000+i*32:016x}", status="decoded", bytes=case["bytes"],
                                length=1, bil=[{"kind": "fixture"}]) for i, case in enumerate(self.cases))
        self.frames.append(dict(schema="ariadne.bap-batch/v1", batch=0, count=2))

    def run_lift(self, frames, code=0):
        wire = "\n".join(json.dumps(row) for row in frames) + "\n"
        process = SimpleNamespace(returncode=code, stdout=wire, stderr="controlled failure")
        with patch.object(oracle.subprocess, "run", return_value=process) as launch:
            result = oracle.fresh_lifts(self.cases, self.contract, self.helper, self.root)
        return result, launch.call_args, wire

    def test_current_contract_is_sent_and_raw_response_hash_is_returned(self):
        (rows, response_sha, helper_sha), call, wire = self.run_lift(self.frames)
        self.assertEqual(rows, self.frames[1:-1])
        self.assertEqual(response_sha, hashlib.sha256(wire.encode()).hexdigest())
        self.assertEqual(helper_sha, hashlib.sha256(self.helper.read_bytes()).hexdigest())
        self.assertIn("batch 0 2\n0x0000000000401000 90\n", call.kwargs["input"])
        self.assertEqual(call.args[0][0], str(self.helper))

    def test_wrong_identity_order_extent_and_completion_are_rejected(self):
        changes = [lambda f: f[0].update(snapshot="0" * 64),
                   lambda f: f[0].update(version="unreviewed"),
                   lambda f: f[1].update(va=f[2]["va"]),
                   lambda f: f[1].update(bytes="cc"),
                   lambda f: f[1].update(length=True),
                   lambda f: f[1].update(batch=False),
                   lambda f: f[1].update(bil=[]),
                   lambda f: f[-1].update(count=1),
                   lambda f: f.pop()]
        for change in changes:
            frames = copy.deepcopy(self.frames)
            change(frames)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.run_lift(frames)

    def test_native_failure_and_duplicate_json_cannot_use_cached_results(self):
        with self.assertRaises(RuntimeError):
            self.run_lift(self.frames, code=2)
        wire = json.dumps(self.frames[0]).replace('"snapshot":', '"snapshot":"wrong","snapshot":')
        wire += "\n" + "\n".join(json.dumps(row) for row in self.frames[1:])
        process = SimpleNamespace(returncode=0, stdout=wire, stderr="")
        with patch.object(oracle.subprocess, "run", return_value=process), self.assertRaises(ValueError):
            oracle.fresh_lifts(self.cases, self.contract, self.helper, self.root)


if __name__ == "__main__":
    unittest.main()
