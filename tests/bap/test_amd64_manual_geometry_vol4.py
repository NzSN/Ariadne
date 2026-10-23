"""Actual Vol4 fragments and hostile geometry/ownership controls."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import amd64_manual_geometry as geometry
import amd64_manual_gap_vol4 as recovery

FIXTURES = ROOT / "tests/bap/fixtures/manual-geometry/vol4"


def fixture(name):
    return json.loads((FIXTURES / (name + ".json")).read_text())


def context(item):
    layout = [""] * max(map(int, item["layoutPages"]))
    for page, text in item["layoutPages"].items():
        layout[int(page) - 1] = text
    pages = [dict(pdfPage=int(page), cells=cells) for page, cells in item["cells"].items()]
    tables, rows, groups = geometry.table_geometry(item["baseline"], layout, pages)
    return dict(publication=item["publication"], baseline=item["baseline"], layout_pages=layout,
                tables=tables, rows=rows, groups_by_page=groups, records=item["records"], funcs=vars(geometry))


def recover(item):
    return recovery.resolve_all(context(item))


def cell(item, identifier):
    return next(cell for cells in item["cells"].values() for cell in cells if cell["id"] == identifier)


def translate(source, dx=0, dy=0):
    for obj in [source] + source.get("wordBoxes", []):
        obj["rect"] = [value + (dx if index % 2 == 0 else dy) for index, value in enumerate(obj["rect"])]


class Vol4RecoveryControls(unittest.TestCase):
    def test_all_minimized_actual_cases_receive_source_backed_dispositions(self):
        count = 0
        for path in sorted(FIXTURES.glob("*.json")):
            item = json.loads(path.read_text())
            before = copy.deepcopy(item)
            result = recover(item)
            self.assertEqual(set(result), {record["ordinal"] for record in item["records"]}, path.name)
            self.assertEqual(item, before, path.name)
            for record in item["records"]:
                patch = result[record["ordinal"]]
                self.assertTrue(set(record["cells"]) <= set(patch["cells"]))
                self.assertFalse(patch["constraintsParsed"])
                self.assertFalse(patch["evidence"]["encodingGrammarValidated"])
                self.assertFalse(patch["evidence"]["authoritativeBindingEstablished"])
            count += len(result)
        self.assertGreater(count, 50)

    def test_literal_source_defects_are_conflicts_without_invented_corrections(self):
        for name, expected in (("malformed", {1, 2, 574}), ("conflicts", {542, 543, 744, 1603})):
            result = recover(fixture(name))
            self.assertEqual({key for key, value in result.items() if value["disposition"] == "source-conflict"}, expected)
        malformed = recover(fixture("malformed"))
        self.assertEqual(malformed[1]["evidence"]["literalConflicts"][0]["text"], "xmmVGETEXPPD2,")
        self.assertEqual(malformed[574]["evidence"]["literalConflicts"][0]["text"], "X.1323r33111.")
        self.assertIsNone(malformed[1]["evidence"]["correction"])

    def test_aesenc_overlay_retains_disputed_historical_outline_owner(self):
        item = fixture("aesenc")
        result = recover(item)
        self.assertEqual(item["baseline"]["entries"][0]["title"], "AESDECLAST VAESDECLAST")
        for patch in result.values():
            self.assertEqual(patch["evidence"]["ownership"]["kind"], "literal-heading-or-prototype-overlay")
            self.assertTrue(patch["evidence"]["ownershipEvidenceCells"])
            self.assertNotIn("entryId", patch)

    def test_missing_wrong_duplicate_or_superseded_heading_cannot_own_aesenc(self):
        for attack in ("missing", "wrong", "duplicate", "superseded"):
            item = fixture("aesenc")
            heads = [source for source in item["cells"]["103"]
                     if source["text"] in {"AESENC", "VAESENC"} and source["rect"][1] < 140]
            if attack == "missing":
                item["cells"]["103"] = [source for source in item["cells"]["103"] if source not in heads]
            elif attack == "wrong":
                for source in heads:
                    source["text"] = "UNRELATED"
                    source["wordBoxes"][0]["text"] = "UNRELATED"
            elif attack == "duplicate":
                for source in heads:
                    duplicate = copy.deepcopy(source)
                    duplicate["id"] += ":duplicate"
                    translate(duplicate, dy=-30)
                    item["cells"]["103"].append(duplicate)
            else:
                extra = copy.deepcopy(heads[-1])
                extra.update(id="attack-heading", text="UNRELATED")
                extra["wordBoxes"][0]["text"] = "UNRELATED"
                translate(extra, dy=40)
                # Isolate the adversarial heading from prose, so the competing
                # source heading cannot disappear as an overprinted line.
                item["cells"]["103"] = [source for source in item["cells"]["103"]
                                         if abs(source["rect"][1] - extra["rect"][1]) > 12]
                item["cells"]["103"].append(extra)
            self.assertEqual(recover(item), {}, attack)

    def test_previous_section_heading_cannot_correct_current_mnemonic(self):
        item = fixture("conflicts")
        previous = copy.deepcopy(next(source for source in item["cells"]["807"] if source["text"] == "SHA256MSG2"))
        previous.update(id="prior-section", pdfPage=805, text="SHA256MSG1")
        previous["wordBoxes"][0]["text"] = "SHA256MSG1"
        item["cells"]["805"] = [previous]
        item["layoutPages"]["805"] = "SHA256MSG1"
        result = recover(item)
        self.assertEqual(result[744]["disposition"], "source-conflict")
        self.assertEqual(result[744]["evidence"]["ownership"]["conflictingHeadings"], ["SHA256MSG2"])

    def test_foreign_material_anywhere_before_encoding_column_breaks_row(self):
        for x in (90, 180, 230):
            item = fixture("malformed")
            head = cell(item, "pdf:78:cell:42")
            item["cells"]["78"].append(dict(id="attack-foreign", pdfPage=78, text="UNKNOWN",
                rect=[x, head["rect"][1] + 4, x + 20, head["rect"][1] + 12], wordBoxes=[]))
            result = recover(item)
            self.assertNotIn(1, result, x)
            self.assertNotIn(2, result, x)

    def test_moved_or_duplicate_prefix_cannot_recover_vector_row(self):
        for attack in ("moved", "duplicate", "missing"):
            item = fixture("aesenc")
            prefix = cell(item, "pdf:104:cell:15")
            self.assertEqual(prefix["text"], "C4")
            if attack == "moved":
                translate(prefix, dx=220)
            elif attack == "duplicate":
                duplicate = copy.deepcopy(prefix)
                duplicate["id"] = "duplicate-prefix"
                item["cells"]["104"].append(duplicate)
            else:
                item["cells"]["104"].remove(prefix)
            self.assertNotIn(22, recover(item), attack)

    def test_merged_legacy_words_must_stay_in_named_opcode_column(self):
        item = fixture("fused")
        source = cell(item, "pdf:567:cell:28")
        words = source["wordBoxes"]
        start = next(i for i, word in enumerate(words) if word["text"] == "66")
        end = next(i for i, word in enumerate(words[start:], start) if word["text"] == "/r")
        for word in words[start:end + 1]:
            word["rect"][0] += 130
            word["rect"][2] += 130
        self.assertNotIn(493, recover(item))

    def test_superscript_drift_does_not_attach_to_another_mnemonic(self):
        item = fixture("legacy")
        marker = cell(item, "pdf:530:cell:20")
        translate(marker, dx=15)
        self.assertNotIn(475, recover(item))

    def test_centered_encoding_with_competing_previous_head_is_refused(self):
        item = fixture("wrapped")
        head = cell(item, "pdf:1628:cell:24")
        extra = copy.deepcopy(head)
        extra["id"] = "competing-prior-head"
        translate(extra, dy=-15)
        item["cells"]["1628"].append(extra)
        self.assertNotIn(1985, recover(item))

    def test_wrapped_opcode_fragments_remain_in_exact_encoding_evidence(self):
        item = fixture("wrapped")
        result = recover(item)
        for ordinal, identifier in ((314, "pdf:382:cell:17"), (315, "pdf:382:cell:20")):
            self.assertIn(identifier, result[ordinal]["evidence"]["encodingCells"])
            moved = copy.deepcopy(item)
            translate(cell(moved, identifier), dx=40)
            self.assertNotIn(ordinal, recover(moved))

    def test_semantic_table_region_cannot_dispose_new_opcode_material(self):
        ctx = context(fixture("semantic"))
        record = next(record for record in ctx["records"] if record["ordinal"] == 48)
        table = next(table for table in ctx["baseline"]["tables"] if table["id"] == record["originalGap"]["table"])
        for text in ("VZEROUPPER C5 F8 77", "NEWOP 0F AA /r", "Mnemonic Opcode Encoding"):
            source = dict(id="foreign-encoding", pdfPage=134, text=text, rect=[100, 701, 400, 712])
            group = dict(text=text, cells=[source], y=701, ambiguous=False)
            self.assertIsNone(recovery._material(ctx, record, group, table), text)

    def test_resolved_records_and_other_volumes_are_not_changed(self):
        item = fixture("aesenc")
        item["publication"] = "26569"
        self.assertEqual(recover(item), {})
        item["publication"] = "26568"
        for record in item["records"]:
            record["disposition"] = "resolved-cell"
        self.assertEqual(recover(item), {})


if __name__ == "__main__":
    unittest.main()
