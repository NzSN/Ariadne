"""Independent accounting attacks against finite samples masquerading as coverage."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import amd64_coverage as coverage
import amd64_inventory_xed as xed
import amd64_manual_inventory as manual
import probe_amd64_semantics as probe


def fixture():
    def source(pattern, mode="unspecified"):
        return dict(iclass="CLC", iform="CLC", pattern=pattern, operands="",
                    isa_set="I86", space="legacy", mode_restriction=mode, easz="aszall")
    rows = xed.normalize([source("0xF8"), source("0xF8 REX2=1"), source("0xF8", "not64")])
    inventory = dict(schema=xed.SCHEMA, records=rows, recordsSha256=xed.digest(rows),
                     counts=xed.summarize(rows), selectedInputs=[], preparedInputSha256={},
                     operandWidths={}, scope={"unit": "symbolic test templates"})
    material = {key: inventory[key] for key in ("selectedInputs", "preparedInputSha256", "operandWidths", "scope")}
    lock = dict(normalized=dict(recordsSha256=xed.digest(rows), counts=xed.summarize(rows),
                                inputsAndScopeSha256=xed.digest(material)))
    subsets = sorted(probe.SUBSETS)
    catalogue = dict(schema=probe.SCHEMA, exhaustiveEncodingCoverage=False,
                     architecturalSubsets=subsets, profile="test-finite",
                     sourcePolicy="BAP projection only", encodingSource="independent exact test bytes",
                     scope="five exact bytes, no form expansion", references=[dict(id="amd")],
                     families=[dict(id=name, subset=name, reference="amd") for name in subsets],
                     cases=[dict(id="case-" + str(index), family=name, mode="long-64",
                                 assembly="clc", bytes=f"{0xf8 + index:02x}",
                                 expectedEffects=dict(uses=[], mayDefs=["CF"], mustDefs=["CF"]),
                                 expectationBasis="independent test expectation")
                            for index, name in enumerate(subsets)])
    return inventory, lock, catalogue


def publication(xed_inventory):
    # Source-row fixture intentionally keeps two unknown lines as visible gaps.
    chapter = "3 General-Purpose Instruction Reference"
    header = f"{'Mnemonic':<32}{'Opcode':<16}Description"
    text = "\n".join([header, f"{'CLC':<32}{'F8':<16}Clear carry.",
                       "unparsed source line", "another unknown line", "Related Instructions"])
    outline = dict(pages=1, outline=[dict(title=chapter, pdfPage=1,
                                        children=[dict(title="CLC", uri="#CLC", pdfPage=1)]),
                                     dict(title="Appendix", pdfPage=2)])
    content = manual.extract(text, outline, [chapter])
    comparison = dict(xedRecordsSha256=xed_inventory["recordsSha256"],
                      rows=manual.reconcile(content["rows"], xed_inventory))
    result = dict(schema=manual.SCHEMA, publication="24594", revision="test",
                  sourceProvenance=dict(officialByteIdentity="matches-repository-official-source-pin"),
                  pdfSha256="a" * 64, layoutTextSha256="b" * 64, outlineSha256="c" * 64,
                  scope=dict(unit="physical rows"), content=content, contentSha256=manual.digest(content),
                  counts=manual.counts(content), xedComparison=comparison)
    pin = {key: result[key] for key in ("publication", "revision", "sourceProvenance", "pdfSha256",
                                       "layoutTextSha256", "outlineSha256", "contentSha256", "counts")}
    pin.update(scopeSha256=manual.digest(result["scope"]), xedRecordsSha256=xed_inventory["recordsSha256"],
               xedComparisonSha256=manual.digest(comparison))
    return result, dict(schema="ariadne.amd-manual-inventory-lock/v1", documents=[pin])


def native_survey(catalogue, catalogue_sha="d" * 64, status="projected"):
    observations = {}
    for index, case in enumerate(catalogue["cases"]):
        observations[case["id"]] = dict(id=case["id"], bytes=case["bytes"],
            address=f"0x{0x401000 + index * 32:016x}", error=None,
            decodable=True, consumedBytes=case["bytes"], length=len(case["bytes"]) // 2,
            effects=case["expectedEffects"], semantic=dict(status=status, backend="bap-x86-legacy",
                                                         fallback=None, helperSha256="e" * 64))
    value = probe.summarize(catalogue, observations)
    value.update(catalogueSha256=catalogue_sha, sourceSha256={"src/test.rs": "f" * 64},
                 sourceStable=True, nativeRequested=True, operationalFailure=None,
                 nativeTools=dict(decoderSha256="a" * 64, helperSha256="e" * 64))
    return value


class CoverageAccountingControls(unittest.TestCase):
    def setUp(self):
        self.xed, self.lock, self.catalogue = fixture()
        self.manual, self.manual_lock = publication(self.xed)
        self.catalogue_sha = "d" * 64
        self.survey = native_survey(self.catalogue)

    def report(self, **kwargs):
        arguments = dict(xed=self.xed, xed_lock=self.lock, manuals=[self.manual],
                         manual_lock=self.manual_lock, catalogue=self.catalogue,
                         catalogue_sha=self.catalogue_sha)
        arguments.update(kwargs)
        return coverage.report(**arguments)

    def associations(self):
        return dict(schema=coverage.ASSOCIATIONS, xedRecordsSha256=self.xed["recordsSha256"],
                    catalogueSha256=self.catalogue_sha, associations=[dict(
                        formId=self.xed["records"][0]["id"], caseId="case-0", bytes="f8")])

    def test_default_has_exact_domains_and_no_support_credit_from_name_matches(self):
        result = self.report()
        self.assertEqual(result["counts"]["longModeCandidates"], 2)
        self.assertEqual(result["counts"]["longModeExcluded"], 1)
        self.assertEqual(result["counts"]["unboundLongModeCandidates"], 2)
        self.assertEqual(result["counts"]["exactByteStatus"], {"unexercised": 5})
        self.assertEqual(result["counts"]["manualGaps"], 2)
        self.assertTrue(all(row["nameOnlyManualCandidates"] for row in result["formWorklist"]))
        self.assertTrue(all(row["associationStatus"] == "absent" for row in result["formWorklist"]))
        self.assertFalse(result["fullAmd64Support"])

    def test_all_supported_samples_and_candidate_associations_never_close_forms(self):
        associations = self.associations()
        associations["associations"].append(dict(formId=self.xed["records"][1]["id"], caseId="case-0", bytes="f8"))
        result = self.report(survey=self.survey, current_sources=self.survey["sourceSha256"],
                             associations=associations)
        self.assertEqual(result["counts"]["exactByteStatus"], {"supported": 5})
        self.assertEqual(result["counts"]["unboundLongModeCandidates"], 0)
        self.assertEqual(result["counts"]["authoritativeBoundForms"], 0)
        self.assertFalse(result["fullAmd64Support"])
        unmet = {gate["id"] for gate in result["gates"] if not gate["satisfied"]}
        self.assertTrue({"complete-vendor-encoding-legality", "authoritative-form-to-byte-bindings",
                         "exhaustive-concrete-encoding-domains", "manual-transcription-gap-free"} <= unmet)

    def test_opaque_missing_and_unexercised_are_distinct_from_support(self):
        for native_status, expected in (("opaque-ordinary", "opaque"), ("unknown", "missing")):
            survey = native_survey(self.catalogue, status=native_status)
            result = self.report(survey=survey, current_sources=survey["sourceSha256"])
            self.assertEqual(result["counts"]["exactByteStatus"], {expected: 5})
            self.assertFalse(result["fullAmd64Support"])

    def test_forged_survey_totals_status_and_old_passing_flags_are_rejected(self):
        for key, value in (("fullAmd64Support", True), ("statusCounts", {"supported-projection": 50000}),
                           ("probeComplete", False), ("exhaustiveEncodingCoverage", True)):
            survey = copy.deepcopy(self.survey)
            survey[key] = value
            with self.assertRaisesRegex(ValueError, "completion claims"):
                self.report(survey=survey, current_sources=survey["sourceSha256"])
        survey = copy.deepcopy(self.survey)
        survey["accepted"] = True
        with self.assertRaisesRegex(ValueError, "survey fields"):
            self.report(survey=survey, current_sources=survey["sourceSha256"])

    def test_survey_missing_duplicate_reordered_or_wrong_bytes_are_rejected(self):
        for attack in ("missing", "duplicate", "order", "bytes"):
            survey = copy.deepcopy(self.survey)
            if attack == "missing":
                survey["rows"].pop()
            elif attack == "duplicate":
                survey["rows"][-1] = survey["rows"][0]
            elif attack == "order":
                survey["rows"].reverse()
            else:
                survey["rows"][0]["observation"]["bytes"] = "90"
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                self.report(survey=survey, current_sources=survey["sourceSha256"])

    def test_source_catalogue_helper_and_semantic_fallback_identity_must_match(self):
        for attack in ("source", "catalogue", "helper", "fallback", "stable"):
            survey = copy.deepcopy(self.survey)
            current = copy.deepcopy(survey["sourceSha256"])
            if attack == "source":
                current["src/test.rs"] = "0" * 64
            elif attack == "catalogue":
                survey["catalogueSha256"] = "0" * 64
            elif attack == "helper":
                survey["rows"][0]["observation"]["semantic"]["helperSha256"] = "0" * 64
            elif attack == "fallback":
                survey["rows"][0]["observation"]["semantic"]["fallback"] = "llvm"
            else:
                survey["sourceStable"] = False
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                self.report(survey=survey, current_sources=current)

    def test_candidate_associations_require_exact_bytes_and_both_identities(self):
        for attack in ("bytes", "case", "form", "excluded", "catalogue", "inventory", "duplicate", "authority"):
            value = self.associations()
            row = value["associations"][0]
            if attack == "bytes":
                row["bytes"] = "90"
            elif attack == "case":
                row["caseId"] = "absent"
            elif attack == "form":
                row["formId"] = "xed:absent"
            elif attack == "excluded":
                row["formId"] = self.xed["records"][2]["id"]
            elif attack in ("catalogue", "inventory"):
                value["catalogueSha256" if attack == "catalogue" else "xedRecordsSha256"] = "0" * 64
            elif attack == "duplicate":
                value["associations"].append(copy.deepcopy(row))
            else:
                row["encodingLegalityVerified"] = True
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                self.report(associations=value)

    def test_same_mnemonic_and_iform_remain_two_separate_form_obligations(self):
        result = self.report(associations=self.associations())
        self.assertEqual([row["associationStatus"] for row in result["formWorklist"]], ["candidate-only", "absent"])
        self.assertEqual(result["formWorklist"][0]["associatedCases"][0]["bytes"], "f8")
        self.assertEqual(result["formWorklist"][1]["associatedCases"], [])

    def test_missing_duplicate_and_rehashed_template_rows_fail_pin(self):
        for rows in (self.xed["records"][:-1], self.xed["records"] + self.xed["records"][:1]):
            value = copy.deepcopy(self.xed)
            value["records"] = xed.normalize([row["source"] for row in rows])
            value["counts"] = xed.summarize(value["records"])
            value["recordsSha256"] = xed.digest(value["records"])
            with self.assertRaises(ValueError):
                self.report(xed=value)

    def test_manual_omissions_duplicate_publications_and_false_legality_fail(self):
        for attack in ("row", "gap", "comparison", "duplicate"):
            document = copy.deepcopy(self.manual)
            if attack == "row":
                document["content"]["rows"] = []
            elif attack == "gap":
                document["content"]["gaps"] = []
            elif attack == "comparison":
                document["xedComparison"]["rows"][0]["encodingLegalityReconciled"] = True
            else:
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    self.report(manuals=[document, document])
                continue
            document["contentSha256"] = manual.digest(document["content"])
            document["counts"] = manual.counts(document["content"])
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                self.report(manuals=[document])

    def test_absent_manuals_are_explicit_obligations_not_an_empty_success(self):
        result = self.report(manuals=[])
        self.assertEqual(result["missingManualPublications"], ["24594"])
        self.assertEqual(result["counts"]["manualRows"], 0)
        self.assertEqual(result["counts"]["manualGaps"], 0)
        self.assertEqual(result["counts"]["pinnedManualRows"], 1)
        self.assertEqual(result["counts"]["pinnedManualGaps"], 2)
        self.assertFalse(result["fullAmd64Support"])
        self.assertFalse(next(g["satisfied"] for g in result["gates"] if g["id"] == "manual-transcription-gap-free"))

    def test_duplicate_catalogue_references_and_cases_fail(self):
        for key in ("references", "cases"):
            catalogue = copy.deepcopy(self.catalogue)
            catalogue[key].append(copy.deepcopy(catalogue[key][0]))
            with self.assertRaises(ValueError):
                self.report(catalogue=catalogue)
        catalogue = dict(self.catalogue, fullAmd64Support=True)
        with self.assertRaisesRegex(ValueError, "unsupported completion claim"):
            self.report(catalogue=catalogue)

    def test_worklists_deterministic_and_association_input_order_does_not_change_rows(self):
        value = self.associations()
        value["associations"].append(dict(formId=self.xed["records"][0]["id"], caseId="case-1", bytes="f9"))
        first = self.report(associations=value)
        value["associations"].reverse()
        second = self.report(associations=value)
        self.assertEqual(first["formWorklist"], second["formWorklist"])
        self.assertEqual(first["manualGapWorklist"], second["manualGapWorklist"])
        self.assertEqual(json.dumps(self.report(), sort_keys=True), json.dumps(self.report(), sort_keys=True))

    def test_strict_cli_writes_report_then_returns_unmet_gate_status(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            paths = {}
            for name, value in (("xed", self.xed), ("manual", self.manual), ("catalogue", self.catalogue),
                                ("manual-lock", self.manual_lock)):
                path = base / (name + ".json")
                path.write_text(json.dumps(value))
                paths[name] = path
            with patch.object(coverage.inventory, "load_lock", return_value=self.lock), \
                    patch.object(coverage.manual, "LOCK", paths["manual-lock"]):
                code = coverage.main(["--xed", str(paths["xed"]), "--manual", str(paths["manual"]),
                    "--catalogue", str(paths["catalogue"]), "--output", str(base / "result"), "--require-full"])
            self.assertEqual(code, 2)
            self.assertFalse(json.loads((base / "result/report.json").read_text())["fullAmd64Support"])

    def test_strict_json_rejects_duplicate_keys_and_nonfinite_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            for value in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', '[]', 'null'):
                path.write_text(value)
                with self.assertRaises(ValueError):
                    coverage.read_json(path)


if __name__ == "__main__":
    unittest.main()
