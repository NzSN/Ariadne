"""Portable admission/transition controls for the separate AMD address32 producer."""
import copy
import importlib.util
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "rep_address_build", ROOT / "native/bap/source-coverage/rep_address_build.py")
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


def observations():
    before, after = {}, {}
    wrong = {"67f3a4", "6766f3a5", "67f3a5", "67f348a5"}
    for code in build.CASES:
        row = dict(schema="ariadne.bap-source-rep-address-observation/v1", bytes=code,
                   production=False, status="missing-semantics")
        if code in wrong:
            row.update(status="lifted", wellTyped=True, length=len(code) // 2,
                       bilText="incorrect original full64 count/address")
        before[code] = copy.deepcopy(row)
        if code in build.CODES:
            row.update(status="lifted", wellTyped=True, length=len(code) // 2,
                       bilText="typed address32 body")
        elif code in build.TRAILING:
            row.update(status="trailing-bytes", wellTyped=True, length=(len(code) - 2) // 2)
        after[code] = row
    return before, after


class RepAddressSourceControls(unittest.TestCase):
    def test_transition_counts_both_corrected_and_new_forms(self):
        before, after = observations()
        result = build.verify_transition(before, after)
        self.assertEqual(result["newTypedForms"], 28)
        self.assertEqual(result["correctedTypedForms"], 4)
        self.assertEqual(result["typedForms"], 32)
        self.assertEqual(result["unchangedBaselineObservations"], 28)

    def test_source_gap_type_extent_and_baseline_tampering_are_rejected(self):
        for which, code, field, value in (
                ("before", "f3ac", "status", "lifted"),
                ("before", "67f3a4", "status", "missing-semantics"),
                ("after", "6766f3ad", "wellTyped", False),
                ("after", "67f348ad", "length", 3),
                ("after", "6767f3ad", "status", "lifted"),
                ("after", "67f3ac90", "status", "lifted"),
                ("after", "f3a4", "bilText", "changed default semantics"),
                ("after", "67f3a4", "bilText", "incorrect original full64 count/address")):
            before, after = observations()
            (before if which == "before" else after)[code][field] = value
            with self.subTest(which=which, code=code, field=field), self.assertRaises(ValueError):
                build.verify_transition(before, after)

    def test_observation_count_order_and_identity_are_bound(self):
        before, _ = observations()
        rows = list(before.values())
        encoded = lambda items: "\n".join(json.dumps(row) for row in items)
        self.assertEqual(build.bind_observations(encoded(rows)), before)
        for changed in (rows[:-1], rows + rows[:1], rows[::-1]):
            with self.assertRaises(ValueError):
                build.bind_observations(encoded(changed))
        changed = copy.deepcopy(rows)
        changed[0]["production"] = True
        with self.assertRaises(ValueError):
            build.bind_observations(encoded(changed))

    def test_runtime_whitelist_exactly_matches_source_case_contract(self):
        self.assertEqual(len(set(build.CODES)), 32)
        self.assertEqual(len(build.ADDRESS32), 28)
        self.assertFalse(set(build.CODES) & set(build.NEGATIVES))
        self.assertFalse(set(build.CODES) & set(build.BASELINES))
        self.assertFalse(set(build.CODES) & set(build.TRAILING))
        source = (ROOT / "native/bap/source-coverage/rep_address_lift.ml").read_text()
        declaration = re.search(r"let codes = \[(.*?)\]", source).group(1)
        self.assertEqual(set(re.findall(r'"([0-9a-f]+)"', declaration)), set(build.CODES))



if __name__ == "__main__":
    unittest.main()
