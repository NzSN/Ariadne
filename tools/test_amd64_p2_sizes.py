"""Regression controls for source-specific size distinctions in Appendix B."""
import unittest

import amd64_p2_sizes as sizes


class B1SizeControls(unittest.TestCase):
    def test_every_reviewed_heading_has_an_explicit_family(self):
        pack = sizes.entry.read(sizes.INPUT)
        native = sizes.entry.read(sizes.native.INPUT)
        expected = [h for headings in native["sizeTableHeadings"].values() for h in headings]
        # The reviewed source headings and rules are two independently owned
        # inventories. A parser match count alone cannot supply this equality.
        self.assertEqual([r["heading"] for r in pack["rows"]], expected)
        self.assertEqual(len(expected), 172)
        for r in pack["rows"]:
            self.assertEqual(r["properties"], sizes.contract(r["heading"]["text"]))

    def test_descriptor_base_is_not_memory_footprint_or_selector_width(self):
        rule = sizes.contract("LGDT—Load Global Descriptor Table Register")
        self.assertEqual((rule["baseBits"], rule["limitBits"], rule["memoryBytes"]), (64, 16, 10))
        rule = sizes.contract("LLDT—Load Local Descriptor Table Register")
        self.assertEqual((rule["operandBits"], rule["descriptorBaseBits"]), ([16], 64))

    def test_mov_mixed_direction_and_offset_dimensions_are_separate(self):
        segment = sizes.contract("MOV—Move to/from Segment Registers")
        self.assertEqual((segment["loadOperandBits"], segment["storeRegisterBits"], segment["storeMemoryBits"]),
                         ([16], [16, 32, 64], 16))
        mov = sizes.contract("MOV—Move")
        self.assertEqual(mov["moffsetBits"], [64, 32])
        self.assertEqual(mov["immediate64"], "B8-BF-only")
        self.assertEqual(mov["c7Immediate64"], "sign-extended32")
        self.assertFalse(mov["byteOpcodesPromoted"])

    def test_near_selection_does_not_apply_to_far_or_stack_families(self):
        near = sizes.contract("CALL—Procedure Call Near")
        far = sizes.contract("CALL—Procedure Call Far")
        self.assertEqual(near["currentScope"]["selectedOperandBits"], 64)
        self.assertFalse(far["nearHypothesisApplies"])
        self.assertEqual(far["directImmediate"], "unavailable-native64")
        push = sizes.contract("PUSH—Push onto Stack")
        self.assertEqual(push["operandBits"], [16, 64])
        self.assertEqual(push["explicitNonStackAddressBits"], [64, 32])

    def test_io_data_counter_and_media_payload_are_separate(self):
        io = sizes.contract("REP INS—Repeat Input String")
        self.assertEqual(io["dataBits"], [8, 16, 32])
        self.assertEqual(io["stringCountAndPointerBits"], [64, 32])
        media = sizes.contract("MOVD—Move Doubleword or Quadword")
        self.assertEqual(media["gprPayloadBits"], [32, 64])
        self.assertIn("not16-bit", media["prefix66"])

    def test_instruction_exclusions_and_source_spellings_are_preserved(self):
        self.assertEqual(sizes.contract("LFS—Load FS Far Pointer")["offsetBits"], [16, 32])
        self.assertEqual(sizes.contract("BSWAP—Byte Swap")["operandBits"], [32, 64])
        self.assertEqual(sizes.contract("CDWE")["target"], "CBW, CWDE, CDQE")
        self.assertTrue(sizes.contract("CDWE")["sourceSpellingPreserved"])
        with self.assertRaises(ValueError): sizes.contract("MADEUP—Unreviewed Size Rule")

    def test_partial_tables_and_saved_complete_flags_cannot_pass(self):
        pack = sizes.entry.read(sizes.INPUT)
        with self.assertRaises(ValueError): sizes.assess(pack, [])
        with self.assertRaises(ValueError): sizes.assess(dict(pack, complete=True), [])


if __name__ == "__main__":
    unittest.main()
