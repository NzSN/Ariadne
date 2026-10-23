"""Portable negative controls for the separately pinned REP LODS producer."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("lods_build", ROOT / "native/bap/source-coverage/lods_build.py")
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)
sys.path.insert(0, str(ROOT / "tools"))
import check_bap_lods_oracle as oracle


def observations():
    before, after = {}, {}
    for code in build.CASES:
        row = dict(schema="ariadne.bap-source-lods-observation/v1", bytes=code,
                   production=False, status="missing-semantics")
        before[code] = copy.deepcopy(row)
        if code in build.CODES:
            row.update(status="lifted", wellTyped=True, length=len(code) // 2)
        elif code in build.TRAILING:
            row.update(status="trailing-bytes", wellTyped=True, length=(len(code) - 2) // 2)
        after[code] = row
    return before, after


class LodsSourceControls(unittest.TestCase):
    def test_four_form_transition_and_unchanged_baselines(self):
        before, after = observations()
        result = build.verify_transition(before, after)
        self.assertEqual(result["newTypedForms"], 4)
        self.assertEqual(result["unchangedBaselineObservations"], 10)

    def test_source_gap_type_extent_and_baseline_tampering_are_rejected(self):
        for which, code, field, value in (
                ("before", "f3ac", "status", "lifted"),
                ("after", "66f3ad", "wellTyped", False),
                ("after", "f348ad", "length", 2),
                ("after", "67f3ad", "status", "lifted"),
                ("after", "f3ac90", "status", "lifted"),
                ("after", "f3a4", "bilText", "changed source semantics")):
            before, after = observations()
            (before if which == "before" else after)[code][field] = value
            with self.subTest(which=which, code=code, field=field), self.assertRaises(ValueError):
                build.verify_transition(before, after)

    def test_source_observation_count_order_and_identity_are_bound(self):
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

    def test_independent_lods_equations_preserve_partial_and_zero_count_state(self):
        # The reference equations operate on elements, independently of BIL.
        for code, width in oracle.CODES.items():
            case = dict(family="lods", elementBits=width, repeatCondition="count")
            for count in (0, 1, 4):
                for direction in (0, 1):
                    registers, memory = oracle.scenario_recipe(
                        case, count, direction, 1, "source-wrap", "equal", 0xA51234879BCD0123)
                    actual, actual_memory = oracle.expected_recipe(case, registers, memory)
                    self.assertEqual(actual["RCX"], 0)
                    self.assertEqual(actual["RDI"], registers["RDI"].n)
                    self.assertEqual(actual_memory, memory)
                    for flag in ("CF", "PF", "AF", "ZF", "SF", "OF", "DF"):
                        self.assertEqual(actual[flag], registers[flag].n)
                    if count == 0:
                        self.assertEqual(actual["RAX"], registers["RAX"].n)
                        self.assertEqual(actual["RSI"], registers["RSI"].n)
                    elif width < 32:
                        self.assertEqual(actual["RAX"] >> width, registers["RAX"].n >> width)
                    elif width == 32:
                        self.assertEqual(actual["RAX"] >> 32, 0)

    def test_actual_capi_cast_enum_is_separate_from_numeric_equivalence(self):
        oracle.verify_capi_casts("f3ad", [{"kind": "cast", "op": 3, "width": 64}])
        for operator in (0, 1, 2):
            with self.assertRaises(ValueError):
                oracle.verify_capi_casts("f3ad", [{"kind": "cast", "op": operator, "width": 64}])
        with self.assertRaises(ValueError):
            oracle.verify_capi_casts("f348ad", [{"kind": "cast", "op": 3, "width": 64}])


if __name__ == "__main__":
    unittest.main()
