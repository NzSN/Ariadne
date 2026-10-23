"""Actual bounded source adjudications and resealed proof-damage controls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import amd64_source_authority as authority


def fixture():
    manifest = json.loads(authority.INPUT.read_text())
    cells, records, checked = {}, [], {}
    for issue in manifest["issues"]:
        cells.update({cell["id"]: copy.deepcopy(cell) for cell in issue["oldCells"]})
        for expected in issue["oldRecords"]:
            records.append(dict(oldGapId=expected["oldGapId"], ordinal=expected["ordinal"],
                originalGap=copy.deepcopy(expected["originalGap"]), disposition="source-conflict",
                cells=[cell["id"] for cell in issue["oldCells"]],
                evidence=dict(headCells=expected["headCells"][:], encodingCells=expected["encodingCells"][:])))
        for references in issue["anchors"].values():
            for reference in references:
                checked.setdefault(reference["source"], {})[reference["cell"]["id"]] = copy.deepcopy(reference["cell"])
    old = dict(manifest["oldSource"], content=dict(sourceCells=list(cells.values()), oldGapDispositions=records))
    return manifest, {old["publication"]: old}, checked


def damage_anchor(manifest, checked, issue_id, role, change):
    issue = next(item for item in manifest["issues"] if item["id"] == issue_id)
    reference = issue["anchors"][role][0]
    change(reference["cell"])
    checked[reference["source"]][reference["cell"]["id"]] = copy.deepcopy(reference["cell"])


class SourceAuthorityControls(unittest.TestCase):
    def test_seven_actual_conflicts_have_scoped_computed_adjudications(self):
        manifest, old, checked = fixture()
        snapshot = copy.deepcopy((manifest, old, checked))
        result = authority._adjudicate(manifest, old, checked)
        self.assertEqual(len(result), 7)
        resolutions = [item["resolution"] for item in result.values()]
        self.assertEqual(resolutions.count("corrected-in-publisher-revision"), 3)
        self.assertEqual(resolutions.count("adjudicated-by-publisher-encoding-map"), 3)
        self.assertEqual(resolutions.count("adjudicated-by-explicit-publisher-field-constraints"), 1)
        for item in result.values():
            self.assertTrue(item["sourceAuthorityBound"])
            self.assertTrue(item["originalSourceRetained"])
            self.assertFalse(item["corpusAdoption"])
            self.assertFalse(item["legalDomainComplete"])
            self.assertFalse(item["constraintsParsed"])
            self.assertTrue(item["evidenceCells"])
        self.assertEqual(snapshot, (manifest, old, checked))

    def test_adjudication_rejects_missing_duplicate_and_changed_old_records(self):
        for attack in ("missing", "duplicate", "literal", "ordinal", "disposition", "row"):
            with self.subTest(attack=attack):
                manifest, old, checked = fixture()
                records = old["26568"]["content"]["oldGapDispositions"]
                if attack == "missing":
                    records.pop()
                elif attack == "duplicate":
                    records.append(copy.deepcopy(records[0]))
                elif attack == "literal":
                    records[0]["originalGap"]["sourceText"] = "xmm2,"
                elif attack == "ordinal":
                    records[0]["ordinal"] += 1
                elif attack == "disposition":
                    records[0]["disposition"] = "resolved-cell"
                else:
                    records[0]["evidence"]["encodingCells"] = []
                with self.assertRaises(ValueError):
                    authority._adjudicate(manifest, old, checked)

    def test_missing_or_changed_new_source_cells_are_rejected(self):
        for attack in ("missing", "text", "geometry", "duplicate-anchor"):
            manifest, old, checked = fixture()
            reference = manifest["issues"][0]["anchors"]["newHead"][0]
            actual = checked[reference["source"]][reference["cell"]["id"]]
            if attack == "missing":
                del checked[reference["source"]][reference["cell"]["id"]]
            elif attack == "text":
                actual["text"] = "VADDPD ymm1 {k}{z}, ymm2,"
            elif attack == "geometry":
                actual["rect"][1] += 10
            else:
                manifest["issues"][0]["anchors"]["newHead"].append(copy.deepcopy(reference))
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                authority._adjudicate(manifest, old, checked)

    def test_resealed_revision_row_with_wrong_opcode_or_moved_columns_is_rejected(self):
        for attack in ("opcode", "baseline", "column"):
            manifest, old, checked = fixture()
            if attack == "opcode":
                change = lambda cell: cell.update(text="0F 38 CC /r")
            elif attack == "baseline":
                change = lambda cell: cell["rect"].__setitem__(1, cell["rect"][1] + 6)
            else:
                change = lambda cell: cell.update(rect=[50, cell["rect"][1], 90, cell["rect"][3]])
            damage_anchor(manifest, checked, "sha256msg2-mnemonic", "newOpcode", change)
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                authority._adjudicate(manifest, old, checked)

    def test_opcode_map_requires_exact_map_prefix_nibbles_name_and_geometry(self):
        for issue_id in ("vpmovmskb-mnemonic", "vpmadcswd-mnemonic"):
            for role, bad in (("mapTitle", "Unrelated encoding map"), ("mapLow", "x5"),
                              ("mapHigh", "Ax"), ("mapPrefix", "10"), ("mapName", "FOREIGN")):
                manifest, old, checked = fixture()
                damage_anchor(manifest, checked, issue_id, role, lambda cell: cell.update(text=bad))
                with self.subTest(issue=issue_id, role=role), self.assertRaises(ValueError):
                    authority._adjudicate(manifest, old, checked)
            manifest, old, checked = fixture()
            damage_anchor(manifest, checked, issue_id, "mapName", lambda cell: cell.update(rect=[10, cell["rect"][1], 30, cell["rect"][3]]))
            with self.subTest(issue=issue_id, role="moved-column"), self.assertRaises(ValueError):
                authority._adjudicate(manifest, old, checked)

    def test_field_reconstruction_requires_specific_vvvv_exception_and_ymm_length_rule(self):
        for role, bad in (("vvvvConstraint", "VEX.vvvv ! = 1110b."),
                          ("lengthRule", "L=1 specifies 128-bit vector length."),
                          ("newFieldHeader", "W.L.vvvv.pp"),
                          ("newHead", "VPMOVZXWD xmm1, xmm2/mem64")):
            manifest, old, checked = fixture()
            damage_anchor(manifest, checked, "vpmovzxwd-vex-field", role, lambda cell: cell.update(text=bad))
            with self.subTest(role=role), self.assertRaises(ValueError):
                authority._adjudicate(manifest, old, checked)

    def test_unchanged_literals_and_authority_are_not_promoted_to_corpus_adoption(self):
        manifest, old, checked = fixture()
        result = authority._adjudicate(manifest, old, checked)
        malformed = [item for item in result.values() if item["issueId"] == "vpmovzxwd-vex-field"][0]
        self.assertEqual(malformed["correction"]["replacement"], "X.1111.1.01")
        self.assertTrue(any(cell["text"] == "X.1323r33111." for cell in old["26568"]["content"]["sourceCells"]))
        self.assertTrue(all(record["disposition"] == "source-conflict" for record in old["26568"]["content"]["oldGapDispositions"]))

    def test_unreviewed_or_resealed_input_cannot_self_assert_authority(self):
        for attack in ("flag", "url", "hash", "omission"):
            manifest, _, _ = fixture()
            if attack == "flag":
                manifest["corpusAdoption"] = True
            elif attack == "url":
                manifest["sources"][0]["officialUrl"] = "https://example.com/fake.pdf"
            elif attack == "hash":
                manifest["sources"][0]["pdf"]["sha256"] = "0" * 64
            else:
                manifest["issues"].pop()
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                authority._manifest(manifest)

    def test_missing_selected_runtime_products_are_not_a_passing_tier(self):
        manifest, old, _ = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                authority.validate_adjudications(old, dict(manifest=manifest, root=Path(temporary) / "absent"))

    def test_source_paths_cannot_escape_or_follow_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("../outside.pdf", "/tmp/outside.pdf"):
                with self.assertRaises(ValueError):
                    authority._local(root, name)
            (root / "link.pdf").symlink_to(root / "target.pdf")
            with self.assertRaises(ValueError):
                authority._local(root, "link.pdf")

    def test_dependency_closure_binds_fixture_and_geometry_recovery(self):
        sources = authority.authority_sources()
        self.assertIn("tools/amd64_source_authority.py", sources)
        self.assertIn("tests/bap/fixtures/source-authority/adjudications-v1.json", sources)
        self.assertIn("tools/amd64_manual_gap_vol4.py", sources)
        self.assertIn("tools/amd64_manual_outline.js", sources)


if __name__ == "__main__":
    unittest.main()
