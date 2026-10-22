"""Negative controls for coverage accounting and source-bound native observations."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
SPEC = importlib.util.spec_from_file_location("probe_amd64_semantics", ROOT / "tools/probe_amd64_semantics.py")
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class SemanticsSurveyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogue = json.loads(probe.CATALOGUE.read_text())

    def projected(self, case):
        return dict(id=case["id"], bytes=case["bytes"], error=None,
                    consumedBytes=case["bytes"], length=len(case["bytes"]) // 2,
                    decodable=True, effects=copy.deepcopy(case.get("expectedEffects", {
                        "uses": [], "mayDefs": [], "mustDefs": []})),
                    semantic=dict(status="projected", gaps=[], backend="bap-x86-legacy",
                                  helperSha256="a" * 64, fallback=None))

    def native(self):
        rows = []
        for i, case in enumerate(self.catalogue["cases"]):
            row = self.projected(case)
            row["address"] = f"0x{0x401000+i*32:016x}"
            rows.append(row)
        return dict(schema="ariadne.amd64-semantics-native-probe/v1",
                    catalogueSha256="c" * 64, target="windows-amd64",
                    helperSha256="a" * 64, decoderSha256="d" * 64, rows=rows)

    def test_family_survey_has_all_architectural_subsets_and_actual_bytes(self):
        cases = probe.validate_catalogue(self.catalogue)
        self.assertEqual(len(self.catalogue["families"]), 49)
        self.assertEqual(len(cases), 171)
        self.assertEqual(cases["data-transfer-1"]["bytes"], "4889d8")
        self.assertEqual(cases["flags-1"]["bytes"], "f8")
        self.assertEqual(cases["interrupt-exception-3"]["bytes"], "0f0b")
        self.assertEqual(cases["virtualization-1"]["bytes"], "0f01d8")
        self.assertEqual(cases["x87-data-1"]["bytes"], "d9e8")

    def test_inventory_only_never_reuses_historical_passes(self):
        report = probe.summarize(self.catalogue)
        self.assertEqual(report["statusCounts"], {"unexercised": 171})
        self.assertFalse(report["probeComplete"])
        self.assertFalse(report["fullAmd64Support"])
        self.assertEqual(report["expectationMismatches"], [])
        self.assertTrue(all(r["expectedEffectsMatch"] is None for r in report["rows"]))

    def test_projection_does_not_establish_full_isa_coverage(self):
        native = self.native()
        rows = probe.bind_native(self.catalogue, "c" * 64, native)
        report = probe.summarize(self.catalogue, rows)
        self.assertEqual(report["statusCounts"], {"supported-projection": 171})
        self.assertTrue(report["probeComplete"])
        self.assertFalse(report["fullAmd64Support"])
        self.assertFalse(report["exhaustiveEncodingCoverage"])
        self.assertEqual(report["independentExpectations"], 9)

    def test_unknown_control_missing_lift_and_errors_never_count_as_supported(self):
        case = self.catalogue["cases"][0]
        projected = self.projected(case)
        for status in ("opaque-ordinary", "opaque-call-return"):
            row = copy.deepcopy(projected)
            row["semantic"]["status"] = status
            self.assertEqual(probe.classify(case, row), "conservative-unknown")
        for gap, want in (("empty lift is not an admitted no-op", "missing-producer-lift"),
                          ("unmodeled architectural namespace/type: ZMM0", "unsupported-state"),
                          ("unmodeled BIL control/special/loop semantics", "unsupported-control-or-semantics")):
            row = copy.deepcopy(projected)
            row["decodable"] = False
            row["semantic"].update(status="opaque-unsupported", gaps=[gap])
            self.assertEqual(probe.classify(case, row), want)
        self.assertEqual(probe.classify(case, {"error": "helper failed"}), "query-error")

    def test_independent_mov_oracle_detects_lost_source_and_unsound_kill(self):
        case = self.catalogue["cases"][0]
        row = self.projected(case)
        row["effects"]["uses"] = []
        report = probe.summarize(self.catalogue, {case["id"]: row})
        self.assertEqual(report["expectationMismatches"], [case["id"]])
        store = next(c for c in self.catalogue["cases"] if c["id"] == "scalar-memory-2")
        row = self.projected(store)
        row["effects"]["mustDefs"] = ["memory:any"]
        report = probe.summarize(self.catalogue, {store["id"]: row})
        self.assertEqual(report["expectationMismatches"], [store["id"]])

    def test_prefix_or_trailing_bytes_cannot_be_reported_as_supported_case(self):
        case = self.catalogue["cases"][0]
        row = self.projected(case)
        row["consumedBytes"] = "48"
        row["length"] = 1
        self.assertEqual(probe.classify(case, row), "encoding-disagreement")

    def test_native_identity_membership_and_fallback_are_bound(self):
        alterations = [lambda n: n.update(catalogueSha256="0" * 64),
                       lambda n: n["rows"].pop(),
                       lambda n: n["rows"].append(copy.deepcopy(n["rows"][0])),
                       lambda n: n["rows"][0].update(bytes="90"),
                       lambda n: n["rows"][0].update(address="0x0000000000401001"),
                       lambda n: n["rows"][0]["semantic"].update(fallback="llvm"),
                       lambda n: n["rows"][0]["semantic"].update(helperSha256="0" * 64)]
        for alter in alterations:
            native = self.native()
            alter(native)
            with self.assertRaises((ValueError, IndexError)):
                probe.bind_native(self.catalogue, "c" * 64, native)

    def test_catalogue_rejects_duplicate_ids_unrepresented_families_and_false_completeness(self):
        alterations = [lambda c: c["cases"].append(copy.deepcopy(c["cases"][0])),
                       lambda c: c.update(exhaustiveEncodingCoverage=True),
                       lambda c: c["families"].append(dict(c["families"][0], id="no-representative")),
                       lambda c: c["cases"][0].update(bytes="00" * 16)]
        for alter in alterations:
            catalogue = copy.deepcopy(self.catalogue)
            alter(catalogue)
            with self.assertRaises(ValueError):
                probe.validate_catalogue(catalogue)

    def test_duplicate_json_and_nan_do_not_hide_metadata(self):
        for text in ('{"schema": "wrong", "schema": "right"}', '{"x": NaN}'):
            with self.assertRaises(ValueError):
                probe.strict_json(text)


if __name__ == "__main__":
    unittest.main()
