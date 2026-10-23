"""Pinned Volume 5 excerpts: source recovery and destructive geometry controls."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import amd64_manual_geometry as geometry
import amd64_manual_gap_vol5 as recovery

FIXTURES = ROOT / "tests/bap/fixtures/manual-geometry/vol5"


def fixture(name):
    return json.loads((FIXTURES / (name + ".json")).read_text())


def context(item):
    layout = [""] * max(page["pdfPage"] for page in item["pages"])
    for page in item["pages"]:
        layout[page["pdfPage"] - 1] = page["layoutPage"]
    tables, rows, groups = geometry.table_geometry(item["baseline"], layout, item["pages"])
    legacy = getattr(geometry, "legacy_dispositions", geometry.dispositions)
    records = legacy(item["publication"], item["baseline"], layout, tables, rows, groups)
    for record, ordinal in zip(records, item["gapOrdinals"]):
        record["ordinal"] = ordinal
        record["oldGapId"] = geometry.old_gap_id(item["publication"], ordinal, record["originalGap"])
    return dict(publication=item["publication"], baseline=item["baseline"], layout_pages=layout,
                tables=tables, rows=rows, groups_by_page=groups, records=records, funcs=vars(geometry))


def cell(item, text):
    return next(c for p in item["pages"] for c in p["cells"] if c["text"] == text)


def remove(item, target):
    for page in item["pages"]:
        if target in page["cells"]:
            page["cells"].remove(target)
            return


def translate(target, dy):
    target["rect"][1] += dy
    target["rect"][3] += dy


def duplicate(item, target, **changes):
    extra = copy.deepcopy(target)
    extra.update(id="attack:" + target["id"], **changes)
    item["pages"][0]["cells"].append(extra)
    return extra


class Volume5RecoveryControls(unittest.TestCase):
    def test_missing_occurrence_cannot_bind_two_layout_lines_to_one_cell(self):
        cells = [dict(id=text, text=text, rect=[10, y, 25, y + 2])
                 for text, y in (("before", 0), ("repeat", 10), ("after", 20))]
        matched = recovery.source_matches(geometry.physical_lines(cells),
                                          ["before", "repeat", "repeat", "after"], geometry.exact_source_line)
        self.assertEqual(set(matched), {0, 3})

    def test_staggered_and_whole_line_matches_cannot_reuse_a_source_cell(self):
        cells = [dict(id=text, text=text, rect=[x, y, x + 15, y + 2])
                 for text, x, y in (("before", 10, 0), ("left", 10, 10), ("right", 40, 13), ("after", 10, 30))]
        matched = recovery.source_matches(geometry.physical_lines(cells),
                                          ["before", "left  right", "left", "after"], geometry.exact_source_line)
        self.assertEqual(set(matched), {0, 3})

    def test_actual_62_gap_excerpts_recover_without_mutating_source(self):
        total = 0
        for path in sorted(FIXTURES.glob("*.json")):
            with self.subTest(fixture=path.stem):
                item = fixture(path.stem)
                data = context(item)
                snapshot = copy.deepcopy({key: value for key, value in data.items() if key != "funcs"})
                self.assertTrue(all(record["disposition"] == "unresolved" for record in data["records"]))
                patches = recovery.resolve_all(data)
                self.assertEqual(set(patches), set(item["gapOrdinals"]))
                known = {c["id"] for page in item["pages"] for c in page["cells"]}
                for record in data["records"]:
                    patch = patches[record["ordinal"]]
                    self.assertTrue(set(record["cells"]) <= set(patch["cells"]) <= known)
                    self.assertTrue(patch["evidence"]["sourceCells"])
                    self.assertTrue(patch["evidence"]["anchorCells"])
                    self.assertFalse({"originalGap", "legacySource", "ordinal", "oldGapId"} & set(patch))
                    if patch["disposition"] == "non-encoding-material":
                        self.assertIs(patch["constraintsParsed"], False)
                self.assertEqual(snapshot, {key: value for key, value in data.items() if key != "funcs"})
                total += len(patches)
        self.assertEqual(total, 62)

    def test_scope_and_already_disposed_records_are_not_promoted(self):
        data = context(fixture("movq"))
        data["publication"] = "24594"
        self.assertEqual(recovery.resolve_all(data), {})
        data["publication"] = "26569"
        data["records"][0]["disposition"] = "non-encoding-material"
        self.assertNotIn(data["records"][0]["ordinal"], recovery.resolve_all(data))
        data["records"][1]["legacySource"]["textSha256"] = "0" * 64
        self.assertNotIn(data["records"][1]["ordinal"], recovery.resolve_all(data))

    def test_owned_diagram_requires_label_bits_and_uninterrupted_material(self):
        for attack in ("missing", "foreign", "duplicate", "moved", "bits", "opcode", "note"):
            with self.subTest(attack=attack):
                item = fixture("movq")
                label = cell(item, "movq-64.eps")
                if attack == "missing":
                    remove(item, label)
                elif attack == "foreign":
                    label["text"] = "movd-64.eps"
                elif attack == "duplicate":
                    duplicate(item, label)
                elif attack == "moved":
                    translate(label, -260)
                elif attack == "bits":
                    item["pages"][0]["cells"] = [c for c in item["pages"][0]["cells"]
                                                 if not c["text"].split()[0].isdecimal()]
                else:
                    duplicate(item, label, text="0F AA /r" if attack == "opcode" else "Note: unparsed condition",
                              rect=[100, 510, 220, 519])
                self.assertEqual(recovery.resolve_all(context(item)), {})

    def test_decimal_encoding_false_positives_require_owned_diagram_fence(self):
        for name, label in (("packsswb", "packsswb-64.eps"), ("punpckhbw", "punpckhbw-64.eps")):
            item = fixture(name)
            self.assertTrue(any(gap["kind"] == "encoding-cell-without-mnemonic" for gap in item["baseline"]["gaps"]))
            remove(item, cell(item, label))
            self.assertEqual(recovery.resolve_all(context(item)), {})

    def test_psraw_repeats_need_unique_neighbor_bounded_cell_assignment(self):
        item = fixture("psraw")
        patches = recovery.resolve_all(context(item))
        self.assertEqual(patches[342]["evidence"]["sourceCells"], ["pdf:207:cell:37"])
        self.assertEqual(patches[343]["evidence"]["sourceCells"], ["pdf:207:cell:38", "pdf:207:cell:39"])
        self.assertEqual(patches[348]["evidence"]["sourceCells"], ["pdf:207:cell:47"])
        source = next(c for c in item["pages"][0]["cells"] if c["id"] == "pdf:207:cell:37")
        extra = duplicate(item, source)
        translate(extra, 4)
        # Both source cells now fit between the same independent layout anchors.
        self.assertNotIn(342, recovery.resolve_all(context(item)))

    def test_immediate_field_table_requires_caption_columns_and_complete_values(self):
        for attack in ("caption", "foreign", "missing-value", "duplicate", "moved"):
            with self.subTest(attack=attack):
                item = fixture("pextrw")
                caption = cell(item, "Table 1-1. Immediate-Byte Operand Encoding for 64-Bit PEXTRW")
                if attack == "caption":
                    remove(item, caption)
                elif attack == "foreign":
                    caption["text"] = caption["text"].replace("PEXTRW", "PINSRW")
                elif attack == "missing-value":
                    remove(item, cell(item, "63–48"))
                elif attack == "duplicate":
                    duplicate(item, cell(item, "Value of Bit Field"))
                else:
                    translate(cell(item, "63–48"), -5)
                self.assertEqual(recovery.resolve_all(context(item)), {})

    def test_x87_stack_requires_owned_before_after_and_eight_unique_rows(self):
        for attack in ("missing", "foreign", "duplicate", "index", "moved"):
            with self.subTest(attack=attack):
                item = fixture("fdecstp")
                before = cell(item, "Before FDECSTP")
                if attack == "missing":
                    remove(item, before)
                elif attack == "foreign":
                    before["text"] = "Before FINCSTP"
                elif attack == "duplicate":
                    duplicate(item, cell(item, "num3"))
                elif attack == "index":
                    cell(item, "num8")["text"] = "num7"
                else:
                    translate(before, 4)
                self.assertEqual(recovery.resolve_all(context(item)), {})

    def test_x87_result_tables_do_not_absorb_missing_headers_new_notes_or_encodings(self):
        for name in ("fist", "fisttp"):
            for attack in ("missing", "duplicate", "note", "opcode", "moved"):
                with self.subTest(fixture=name, attack=attack):
                    item = fixture(name)
                    title = cell(item, "Storing Numbers as Integers")
                    if attack == "missing":
                        remove(item, title)
                    elif attack == "duplicate":
                        duplicate(item, cell(item, "ST(0)"))
                    elif attack == "moved":
                        translate(cell(item, "ST(0)"), 5)
                    else:
                        duplicate(item, title, text="Note: source obligation" if attack == "note" else "D9 F6",
                                  rect=[100, title["rect"][1] + 40, 230, title["rect"][3] + 40])
                    patches = recovery.resolve_all(context(item))
                    self.assertFalse(any(patch["rule"] == "owned-x87-integer-result-table/v2" for patch in patches.values()))

    def test_footer_requires_bottom_geometry_publisher_and_owned_title(self):
        for attack in ("missing", "foreign", "moved", "duplicate"):
            with self.subTest(attack=attack):
                item = fixture("publisher-footer")
                publisher = cell(item, "[AMD Public Use]")
                if attack == "missing":
                    remove(item, publisher)
                elif attack == "foreign":
                    cell(item, "PSHUFW")["text"] = "FOREIGN"
                elif attack == "moved":
                    translate(publisher, -100)
                else:
                    duplicate(item, publisher)
                self.assertEqual(recovery.resolve_all(context(item)), {})

    def test_numeric_reference_requires_actual_owned_caption_and_printed_page(self):
        for attack in ("caption", "foreign", "page"):
            with self.subTest(attack=attack):
                item = fixture("pfacc-reference")
                target = cell(item, "Table 1-4. Numeric Range for PFACC Results")
                if attack == "caption":
                    remove(item, target)
                elif attack == "foreign":
                    target["text"] = target["text"].replace("PFACC", "PFADD")
                else:
                    cell(item, "93")["text"] = "94"
                self.assertNotIn(150, recovery.resolve_all(context(item)))

    def test_repeated_fnstenv_operand_binds_only_its_explicit_centered_opcode(self):
        item = fixture("fnstenv")
        patch = recovery.resolve_all(context(item))[510]
        self.assertEqual(patch["disposition"], "justified-continuation")
        self.assertEqual(patch["evidence"]["sourceCells"], ["pdf:336:cell:40"])
        self.assertEqual(patch["evidence"]["headCells"], ["pdf:336:cell:39"])
        self.assertEqual(patch["evidence"]["encodingCells"], ["pdf:336:cell:41"])
        for attack in ("missing", "moved", "duplicate-operand", "foreign"):
            with self.subTest(attack=attack):
                item = fixture("fnstenv")
                opcode = cell(item, "D9 /6")
                if attack == "missing":
                    remove(item, opcode)
                elif attack == "moved":
                    translate(opcode, -3)
                elif attack == "duplicate-operand":
                    operand = next(c for c in item["pages"][0]["cells"] if c["id"] == "pdf:336:cell:40")
                    duplicate(item, operand)
                else:
                    item["baseline"]["entries"][0]["title"] = "FLDENV"
                self.assertEqual(recovery.resolve_all(context(item)), {})


if __name__ == "__main__":
    unittest.main()
