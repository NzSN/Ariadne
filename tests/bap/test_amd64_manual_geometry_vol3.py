"""Actual Vol3 page recovery plus attacks on every accepted source shape."""
from collections import Counter
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import amd64_manual_geometry as geometry
import amd64_manual_gap_vol3 as recovery

FIXTURES = ROOT / "tests/bap/fixtures/manual-geometry/vol3"


def fixture(page):
    return json.loads((FIXTURES / f"{page}.json").read_text())


def context(item):
    layout = [""] * item["pdfPage"]
    layout[-1] = item["layoutPage"]
    tables, rows, groups = geometry.table_geometry(item["baseline"], layout,
        [dict(pdfPage=item["pdfPage"], cells=item["cells"])])
    records = geometry.legacy_dispositions(item["publication"], item["baseline"], layout, tables, rows, groups)
    return dict(publication=item["publication"], baseline=item["baseline"], layout_pages=layout,
                tables=tables, rows=rows, groups_by_page=groups, records=records, funcs=vars(geometry))


def analyze(item):
    return recovery.resolve_all(context(item))


def cell(item, identity):
    return next(value for value in item["cells"] if value["id"] == identity)


def shift(value, axis, amount):
    value["rect"][axis] += amount
    value["rect"][axis + 2] += amount


class Vol3RecoveryControls(unittest.TestCase):
    def test_all_actual_remaining_obligations_have_source_owned_dispositions(self):
        counts = Counter()
        for path in FIXTURES.glob("*.json"):
            item = json.loads(path.read_text())
            c = context(item)
            patches = recovery.resolve_all(c)
            unresolved = {record["ordinal"]: record for record in c["records"] if record["disposition"] == "unresolved"}
            self.assertEqual(set(patches), set(unresolved), path.name)
            source_ids = {value["id"] for value in item["cells"]}
            owners = {entry["id"] for entry in item["baseline"]["entries"]}
            for ordinal, patch in patches.items():
                self.assertTrue(set(unresolved[ordinal]["cells"]) <= set(patch["cells"]))
                self.assertTrue(set(patch["cells"]) <= source_ids)
                self.assertIn(patch["entryId"], owners)
                self.assertIn(patch["entryId"], patch["evidence"]["originalEntryIds"])
                self.assertNotIn("oldGapId", patch)
                self.assertNotIn("legacySource", patch)
                counts[patch["rule"]] += 1
        self.assertEqual(sum(counts.values()), 145)
        self.assertEqual(counts["centered-cmov-width-group/v2"], 60)
        self.assertEqual(counts["centered-setcc-alias-group/v2"], 34)
        self.assertEqual(counts["single-head-wrapped-opcode/v2"], 5)
        self.assertEqual(counts["encoding-constraint-prose/v2"], 9)

    def test_integrated_geometry_dispositions_keep_source_identity_and_apply_recovery(self):
        for page in (200, 211, 272, 317, 378, 544):
            c = context(fixture(page))
            result = geometry.dispositions(c["publication"], c["baseline"], c["layout_pages"],
                                           c["tables"], c["rows"], c["groups_by_page"])
            for old, current in zip(c["records"], result):
                self.assertEqual(old["oldGapId"], current["oldGapId"])
                self.assertEqual(old["originalGap"], current["originalGap"])
                self.assertEqual(old["legacySource"], current["legacySource"])
                self.assertNotEqual(current["disposition"], "unresolved")

    def test_pass_does_not_modify_input_or_override_existing_dispositions(self):
        c = context(fixture(200))
        before = copy.deepcopy({key: value for key, value in c.items() if key != "funcs"})
        patches = recovery.resolve_all(c)
        self.assertEqual(before, {key: value for key, value in c.items() if key != "funcs"})
        selected = next(iter(patches))
        c["records"][selected]["disposition"] = "resolved-cell"
        self.assertNotIn(selected, recovery.resolve_all(c))
        c["publication"] = "26568"
        self.assertEqual(recovery.resolve_all(c), {})

    def test_cmov_needs_all_widths_centered_unique_opcode_and_isolated_cluster(self):
        for attack in ("missing-width", "wrong-width", "off-center", "duplicate-opcode", "intervening", "spacing", "column", "owner"):
            item = fixture(200)
            opcode = cell(item, "pdf:200:cell:28")
            first = cell(item, "pdf:200:cell:25")
            if attack == "missing-width":
                item["cells"].remove(first)
            elif attack == "wrong-width":
                first["text"] = first["text"].replace("16", "8")
            elif attack == "off-center":
                shift(opcode, 1, 2)
            elif attack == "duplicate-opcode":
                duplicate = copy.deepcopy(opcode)
                duplicate["id"] = "attack-opcode"
                item["cells"].append(duplicate)
            elif attack == "intervening":
                extra = copy.deepcopy(first)
                extra.update(id="attack-foreign", text="unknown operand", rect=[69, 436, 170, 449.65])
                item["cells"].append(extra)
            elif attack == "spacing":
                shift(first, 1, -3)
            elif attack == "column":
                shift(opcode, 0, -30)
            else:
                item["baseline"]["entries"][0]["title"] = "SETcc"
            patches = analyze(item)
            self.assertFalse(any("pdf:200:cell:26" in p["evidence"].get("headCells", []) for p in patches.values()), attack)

    def test_set_aliases_need_one_centered_opcode_per_complete_group(self):
        for attack in ("missing-alias", "duplicate-head", "different-operand", "off-center", "too-close", "foreign-opcode"):
            item = fixture(378)
            head = cell(item, "pdf:378:cell:42")
            opcode = cell(item, "pdf:378:cell:44")
            if attack == "missing-alias":
                item["cells"].remove(head)
            elif attack == "duplicate-head":
                cell(item, "pdf:378:cell:43")["text"] = head["text"]
            elif attack == "different-operand":
                head["text"] = head["text"].replace("mem8", "mem16")
            elif attack == "off-center":
                shift(opcode, 1, 2)
            elif attack == "too-close":
                shift(cell(item, "pdf:378:cell:37"), 1, 5)
            else:
                extra = copy.deepcopy(opcode)
                extra.update(id="attack-foreign", text="0F 95 /0")
                shift(extra, 1, 3)
                item["cells"].append(extra)
            self.assertFalse(any("pdf:378:cell:44" in p["evidence"].get("encodingCells", []) for p in analyze(item).values()), attack)

    def test_all_wrapped_fragments_are_retained_literally(self):
        for page, literal in ((211, "0F C7 /1 m128"), (291, "REX.W 0F 3B F9 /r"), (293, "66 0F 3B F8 /r")):
            patches = analyze(fixture(page))
            self.assertTrue(patches)
            self.assertEqual({p["evidence"]["literalEncoding"] for p in patches.values()}, {literal})
            self.assertTrue(all(len(p["evidence"]["encodingCells"]) == 2 for p in patches.values()))

    def test_wrapped_encoding_rejects_missing_or_displaced_fragment_and_new_head(self):
        for attack in ("omission", "duplicate", "displaced", "foreign-head", "changed-byte"):
            item = fixture(211)
            fragment = cell(item, "pdf:211:cell:41")
            if attack == "omission":
                item["cells"].remove(fragment)
            elif attack == "duplicate":
                extra = copy.deepcopy(fragment)
                extra["id"] = "attack-duplicate"
                item["cells"].append(extra)
            elif attack == "displaced":
                shift(fragment, 0, 3)
            elif attack == "changed-byte":
                cell(item, "pdf:211:cell:40")["text"] = "0F C7 /2"
            else:
                extra = copy.deepcopy(fragment)
                extra.update(id="attack-head", text="CMPXCHG8B mem64", rect=[69, 620, 168, 633.65])
                item["cells"].append(extra)
            self.assertEqual(analyze(item), {}, attack)

    def test_literal_alternate_prefix_is_explicit_and_does_not_accept_arbitrary_slashes(self):
        item = fixture(544)
        patches = analyze(item)
        self.assertEqual(len(patches), 1)
        self.assertEqual(next(iter(patches.values()))["evidence"]["literalEncoding"], "F2/F3 0F 01 D9")
        for replacement in ("F2/F4 0F 01 D9", "F2/F3 0F 01", "F2/F3 0F 01 D9 /r"):
            changed = copy.deepcopy(item)
            cell(changed, "pdf:544:cell:27")["text"] = replacement
            self.assertEqual(analyze(changed), {})

    def test_explicit_encodings_refuse_intrusion_across_named_column_boundaries(self):
        item = fixture(211)
        cell(item, "pdf:211:cell:31")["rect"][2] = 225
        self.assertEqual(analyze(item), {})
        item = fixture(544)
        extra = copy.deepcopy(cell(item, "pdf:544:cell:26"))
        extra.update(id="attack-foreign-column", text="UNKNOWN", rect=[130, 406.2494, 185, 419.8994])
        item["cells"].append(extra)
        self.assertEqual(analyze(item), {})

    def test_all_material_preserves_unparsed_constraint_status_and_complete_region(self):
        total = 0
        for page in (178, 205, 213, 266, 272, 274, 289, 317, 392, 433):
            patches = analyze(fixture(page))
            self.assertTrue(patches, page)
            for patch in patches.values():
                self.assertEqual(patch["disposition"], "non-encoding-material")
                self.assertIs(patch["constraintsParsed"], False)
                self.assertIs(patch["evidence"]["constraintsParsed"], False)
                self.assertTrue(set(patch["evidence"]["anchorCells"]) <= set(patch["cells"]))
                total += 1
        self.assertEqual(total, 45)

    def test_material_cannot_ignore_changed_source_removed_anchor_or_wrong_owner(self):
        for page in (178, 205, 213, 266, 272, 274, 289, 317, 392, 433):
            original = fixture(page)
            proof = next(iter(analyze(original).values()))["evidence"]
            for attack in ("missing-start", "wrong-owner", "injected-opcode"):
                item = copy.deepcopy(original)
                start = cell(item, proof["anchorCells"][0])
                if attack == "missing-start":
                    item["cells"].remove(start)
                elif attack == "wrong-owner":
                    item["baseline"]["entries"][0]["title"] = "UNKNOWN"
                else:
                    extra = copy.deepcopy(start)
                    extra.update(id="attack-encoding", text="0F FF /r")
                    shift(extra, 1, 3)
                    item["cells"].append(extra)
                self.assertEqual(analyze(item), {}, (page, attack))


if __name__ == "__main__":
    unittest.main()
