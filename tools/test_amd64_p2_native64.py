"""Actual-source geometry and mode/size/owner mutation controls."""
import copy
import unittest

import amd64_p2_native64 as native
import amd64_p2_constraints as p2


class Native64InventoryControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = native.entry.read(native.INPUT)
        cls.fixture = native.entry.read(native.INPUT.parent/"p2-native64-source-excerpt.json")
        cls.pages = {p["pdfPage"]:p for p in cls.fixture["pages"]}

    def test_all_21_default_rows_use_physical_geometry_not_cell_order(self):
        rows = native.parse_b5(self.pages[655])
        self.assertEqual(len(rows),21)
        self.assertEqual(rows[-1]["mnemonic"],"RET")
        self.assertEqual(rows[-2]["mnemonic"],"PUSHF, PUSHFD, PUSHFQ")
        page = copy.deepcopy(self.pages[655])
        page["cells"].reverse()
        self.assertEqual([(r["mnemonic"],r["opcode"]) for r in native.parse_b5(page)],
                         [(r["mnemonic"],r["opcode"]) for r in rows])

    def test_default_row_omission_duplicate_and_wrong_column_fail(self):
        for attack in ("row", "duplicate", "rsp", "column", "word"):
            page = copy.deepcopy(self.pages[655])
            if attack == "row":
                page["cells"] = [c for c in page["cells"] if c["id"] != "pdf:655:cell:92"]
            elif attack == "duplicate":
                page["cells"].append(copy.deepcopy(page["cells"][92]))
            elif attack in ("rsp", "word"):
                cell = page["cells"][92 if attack == "rsp" else 91]
                cell["wordBoxes"][0]["text"] = "no" if attack == "rsp" else "CA,"
                cell["wordBoxesSha256"] = native.digest(cell["wordBoxes"])
            else:
                cell = page["cells"][91]
                for w in cell["wordBoxes"]:
                    w["rect"][0] += 60
                    w["rect"][2] += 60
                cell["wordBoxesSha256"] = native.digest(cell["wordBoxes"])
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                native.parse_b5(page)

    def test_no_rex_list_keeps_six_other_system_entries_separate(self):
        rows = native.parse_b5(self.pages[655])
        relation = native.no_rex_relation(rows,p2.NO_REX)
        self.assertEqual(len(relation["default64"]),21)
        self.assertEqual(relation["otherFixedOrSystemEntries"],native.SYSTEM_NO_REX)
        for attack in (p2.NO_REX[:-1],p2.NO_REX+["LGDT"], ["LGDT" if n=="ENTER" else n for n in p2.NO_REX]):
            with self.assertRaises(ValueError): native.no_rex_relation(rows,attack)

    def test_table_continuation_replays_all_six_notes_and_merged_words(self):
        for number in (628,640):
            result = native.parse_b1(self.pages[number],self.pack["sizeTableHeadings"][str(number)])
            self.assertEqual(len(result["sourceBands"]),4)
            note_starts = [w["text"] for w in result["notes"] if w["rect"][0]<85 and w["text"] in {f"{n}." for n in range(1,7)}]
            self.assertEqual(note_starts,[f"{n}." for n in range(1,7)])
            observations = [w for r in result["sourceBands"] for w in r["sourceWords"]]
            self.assertEqual(len(observations),len({(w["sourceCell"],w["wordIndex"]) for w in observations}))
        result = native.parse_b1(self.pages[640],self.pack["sizeTableHeadings"]["640"])
        move = result["sourceBands"][0]
        # This actual PDF cell merges the 32-bit result and 64-bit immediate
        # columns. Word geometry must keep them apart.
        self.assertIn("results to 64 bits.",move["physicalColumns"][3])
        self.assertIn("is sign-extended",move["physicalColumns"][4])
        self.assertNotIn("is sign-extended",move["physicalColumns"][3])

    def test_omitted_heading_note_and_swapped_source_identity_fail(self):
        for attack in ("heading", "note", "identity", "geometry"):
            page = copy.deepcopy(self.pages[628])
            headings = copy.deepcopy(self.pack["sizeTableHeadings"]["628"])
            if attack == "heading": headings.pop()
            elif attack == "identity": headings[0]["id"] = headings[1]["id"]
            else:
                cell = page["cells"][56]
                if attack == "note":
                    page["cells"].remove(cell)
                else:
                    cell["wordBoxes"][0]["rect"][0] += 1
            with self.subTest(attack=attack), self.assertRaises(ValueError): native.parse_b1(page,headings)

    def test_instruction_owned_qualifications_replay_actual_clauses(self):
        clauses = {p["pdfPage"]:p for p in self.fixture["instructionClausePages"]}
        rows = native.parse_b5(self.pages[655])
        result = native.qualify_default64(self.pack["default64Qualifications"],clauses,rows,self.fixture["instructionSourceEntries"])
        self.assertEqual(len(result),21)
        by_name = {r["mnemonic"]:r for r in result}
        self.assertEqual(by_name["LOOP"]["properties"]["countBits"],"address-size:64-or-32;separate-from-operand-size")
        self.assertIn("32-bit-sign-extended-to-default-64",by_name["PUSH imm32"]["properties"]["immediateEncoding"])

    def test_operand_counter_immediate_size_confusion_and_owner_swap_fail(self):
        pages = {p["pdfPage"]:p for p in self.fixture["instructionClausePages"]}
        rows = native.parse_b5(self.pages[655])
        for attack in ("count", "immediate", "definite-write", "owner", "clause", "row", "text", "extra"):
            q = copy.deepcopy(self.pack["default64Qualifications"])
            by_name = {r["mnemonic"]:r for r in q}
            if attack == "count": by_name["LOOP"]["properties"]["countBits"] = "operand-size"
            elif attack == "immediate": by_name["PUSH imm32"]["properties"]["immediateEncoding"] = "64-bit-immediate"
            elif attack == "definite-write": q[0]["properties"]["definiteGprWrites"] = ["rax"]
            elif attack == "owner": q[0]["owner"] = "amd-entry:0032"
            elif attack == "clause": by_name["PUSH imm32"]["clauses"].pop()
            elif attack == "row": q.pop()
            elif attack == "text": q[0]["clauses"][0]["text"] = "64-bit host"
            else: q[0]["constraintsComplete"] = True
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                native.qualify_default64(q,pages,rows,self.fixture["instructionSourceEntries"])

    def test_instruction_section_extent_is_checked_separately(self):
        entries = copy.deepcopy(self.fixture["instructionSourceEntries"])
        entries[0]["pdfEndPage"] += 1
        with self.assertRaises(ValueError):
            native.qualify_default64(self.pack["default64Qualifications"],
                {p["pdfPage"]:p for p in self.fixture["instructionClausePages"]},
                native.parse_b5(self.pages[655]),entries)

    def test_actual_full_source_is_required_for_assessment(self):
        with self.assertRaisesRegex(ValueError,"actual source page differs"):
            native.assess(list(self.pages.values()),p2.NO_REX,self.fixture["instructionSourceEntries"])

    def test_mode_tables_preserve_all_forms_and_reassigned_encoding_meaning(self):
        for name,(page,_,_,expected) in native.MODE_TABLES.items():
            actual = native.parse_mode_table(self.pages[page],name)
            self.assertEqual([(r["mnemonic"],r["opcode"]) for r in actual],expected)
            self.assertTrue(all(not r["encodingDomainComplete"] for r in actual))
        reassigned = native.parse_mode_table(self.pages[654],"reassigned64")
        self.assertIn("EVEX",reassigned[2]["description"])
        self.assertIn("VEX",reassigned[3]["description"])
        # Old BOUND/LDS operations are unavailable; EVEX/VEX remain in scope.
        self.assertEqual(reassigned[2]["disposition"],"reassigned-encoding;old-operation-unavailable")

    def test_mode_table_row_omission_or_far_call_overgeneralization_fail(self):
        page = copy.deepcopy(self.pages[653])
        page["cells"] = [c for c in page["cells"] if c["id"] != "pdf:653:cell:25"]
        with self.assertRaises(ValueError): native.parse_mode_table(page,"invalid64")
        page = copy.deepcopy(self.pages[653])
        cell = page["cells"][24]
        cell["text"] = "CALL"
        cell["wordBoxes"] = [dict(cell["wordBoxes"][0],text="CALL")]
        cell["wordBoxesSha256"] = native.digest(cell["wordBoxes"])
        with self.assertRaises(ValueError): native.parse_mode_table(page,"invalid64")


if __name__ == "__main__":
    unittest.main()
