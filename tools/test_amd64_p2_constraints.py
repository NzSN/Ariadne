"""P2 source ownership, fail-closed exits and independent address predicates."""
import contextlib
import copy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import amd64_p2_constraints as p2


class P2ConstraintControls(unittest.TestCase):
    def setUp(self):
        self.pack = p2.entry.read(p2.INPUT)

    def test_inventory_binds_accepted_editions_and_preserves_conflicts(self):
        self.assertEqual(len(p2.validate_structure(self.pack)), 810)
        self.assertEqual(len(self.pack["clauses"]), 31)
        self.assertEqual(len(self.pack["selectedSources"]), 5)
        self.assertEqual(len(self.pack["boundaries"]), 7)
        self.assertEqual(len(self.pack["context"]), 16)
        self.assertEqual(set(self.pack["referenceRules"]), {
            "prefix-note-4", "null-segment-prefix-exception", "mov64-displacement-exception", "segmented-memory-cross-volume"})
        self.assertEqual(self.pack["clauses"]["sib-source-table"]["parameters"]["baseCodes6and7"],
                         "source-conflict; not inferred from this table")
        self.assertNotEqual(self.pack["clauses"]["lock-vol1-source-set"]["parameters"]["mnemonics"],
                            self.pack["clauses"]["lock-vol3-source-set"]["parameters"]["mnemonics"])

    def test_omitted_notes_swapped_targets_diagram_relabel_and_scope_promotion_fail(self):
        for attack in ("note", "target", "diagram", "owner", "parameter-type", "pin", "scope", "boundary", "anchor", "fields", "context"):
            pack = copy.deepcopy(self.pack)
            if attack == "note":
                pack["clauses"].pop("segment-prefix-uai")
            elif attack == "target":
                pack["referenceRules"]["prefix-note-4"] = ["mov-moffset"]
            elif attack == "diagram":
                pack["clauses"]["gpr-diagram"]["kind"] = "architectural-rule"
            elif attack == "owner":
                pack["clauses"]["segment-bases"]["owner"] = "24593:5.10.2"
            elif attack == "parameter-type":
                pack["clauses"]["gpr-diagram"]["parameters"]["highBytesWithRex"] = 0
            elif attack == "pin":
                pack["inputs"][next(iter(pack["inputs"]))] = "0"*64
            elif attack == "scope":
                pack["selectedSources"].pop()
            elif attack == "boundary":
                pack["boundaries"].pop("null-selector-disagreement")
            elif attack == "anchor":
                pack["sourceCells"].pop(next(iter(pack["sourceCells"])))
            elif attack == "context":
                pack["context"]["24594/pdf:70:cell:23"] = dict(kind="heading-or-table-label", owner="24594:Figure1-6")
            else:
                pack["p2Complete"] = True
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                p2.validate_structure(pack)

    def test_actual_sources_cannot_be_omitted_or_replaced_with_metadata(self):
        with self.assertRaisesRegex(ValueError, "publication"):
            p2.actual_cells(self.pack, {"24592": [], "24594": []})
        with self.assertRaisesRegex(ValueError, "anchor omitted"):
            p2.actual_cells(self.pack, {"24592": [], "24593": [], "24594": []})
        pages = {"24592": [], "24593": [], "24594": [{"pdfPage": 1, "cells": []}, {"pdfPage": 1, "cells": []}]}
        with self.assertRaisesRegex(ValueError, "duplicate page"):
            p2.actual_cells(self.pack, pages)

    def test_source_anchor_text_rect_span_and_word_geometry_are_checked(self):
        key = "24593/pdf:233:cell:6"
        expected = self.pack["sourceCells"][key]
        cell = dict(expected, text="only bits 56:48 of the logical address when 4-level paging is enabled. No canonical checks are")
        validate = p2.extended.migration.paired.conversion.validate_anchor
        validate(expected, cell)
        for field in ("text", "rect", "wordSpan", "wordBoxesSha256", "unicodeSha256"):
            bad = copy.deepcopy(cell)
            if field in ("rect", "wordSpan"):
                bad[field][0] += 1
            else:
                bad[field] = "forged"
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate(expected, bad)
        cell["wordBoxes"] = []
        with self.assertRaisesRegex(ValueError, "physical word boxes"):
            p2.actual_cells(self.pack, {"24592": [], "24593": [{"pdfPage": 233, "cells": [cell]}], "24594": []})

    def test_uai_all_48bit_sign_and_upper_patterns_for_every_segment(self):
        # All 17 bits relevant to canonicality, independent string-bit oracle.
        # Low 47 bits do not affect this predicate.
        for pattern in range(1 << 17):
            address = pattern << 47
            bits = format(address, "064b")
            normal = all(b == bits[16] for b in bits[:16])
            tagged = all(b == bits[16] for b in bits[7:16])
            for segment in ("cs", "ds", "es", "ss", "fs", "gs"):
                self.assertEqual(p2.canonical_address(address, virtual_bits=48, segment=segment, uai_active=False), normal)
                self.assertEqual(p2.canonical_address(address, virtual_bits=48, segment=segment, uai_active=True),
                                 tagged if segment in ("ds", "es") else normal)

    def test_uai_all_57bit_sign_and_tag_patterns_and_implicit_exclusions(self):
        for pattern in range(256):
            address = pattern << 56
            bits = format(address, "064b")
            normal = all(b == bits[7] for b in bits[:7])
            for segment in ("cs", "ds", "es", "ss", "fs", "gs"):
                for active in (False, True):
                    self.assertEqual(p2.canonical_address(address, virtual_bits=57, segment=segment, uai_active=active),
                                     True if active and segment in ("ds", "es") else normal)
                    self.assertEqual(p2.canonical_address(address, virtual_bits=57, segment=segment, uai_active=active,
                                                         implicit_system=True), normal)
                    self.assertEqual(p2.canonical_address(address, virtual_bits=48, segment=segment, uai_active=active,
                                                         implicit_system=True), all(b == bits[16] for b in bits[:16]))

    def test_uai_preserves_address_and_does_not_clear_non_tag_noncanonical_bits(self):
        address = 0xfe00_8000_0000_0001
        self.assertFalse(p2.canonical_address(address, virtual_bits=48, segment="ds", uai_active=True))
        self.assertEqual(address, 0xfe00_8000_0000_0001)
        address = 0xfe00_0000_0000_0001
        self.assertTrue(p2.canonical_address(address, virtual_bits=48, segment="ds", uai_active=True))
        self.assertFalse(p2.canonical_address(address, virtual_bits=48, segment="cs", uai_active=True))

    def test_segment_base_arithmetic_keeps_captured_base_and_wraps_only_at_64(self):
        values = (0, 1, (1 << 32)-1, 1 << 32, (1 << 63)-1, 1 << 63, (1 << 64)-1)
        for base in values:
            for offset in values:
                total = base + offset
                expected = total if total < 1 << 64 else total - (1 << 64)
                self.assertEqual(p2.linear_address(offset, base), expected)
        self.assertEqual(p2.linear_address(0xffffffff, 0x100000000), 0x1ffffffff)

    def test_malformed_state_or_missing_architectural_premises_fail(self):
        standard = dict(address=0, virtual_bits=48, segment="ds", uai_active=False)
        for field, value in (("address", True), ("address", -1), ("address", 1 << 64), ("virtual_bits", True),
                             ("virtual_bits", 52), ("segment", "DS"), ("uai_active", 1), ("implicit_system", 0)):
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                p2.canonical_address(**dict(standard, **{field: value}))
        for args in ((True, 0), (0, None), (-1, 0), (0, 1 << 64), (0.0, 0)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                p2.linear_address(*args)

    def test_strict_exit_counts_concrete_obligations_even_with_forged_flags(self):
        result = dict(cellDispositions=[dict(currentState="unparsed"), dict(currentState="source-conflict"), dict(currentState="reviewed-clause-support")],
                      referenceDispositions=[dict(currentState="unresolved")], boundaries=copy.deepcopy(p2.BOUNDARIES),
                      inheritedBoundaries={"paired": {"example": {}}}, additionalSections=[dict(state="required-clause-review")],
                      sourceRegions=[dict(state="required-whole-region-clause-review")],
                      boundaryDispositions=[dict(id="p2:"+str(i),state="unresolved") for i in range(7)]+[dict(id="paired:example",state="unresolved")],
                      p2Complete=True, allRequiredConstraintsParsed=True)
        self.assertEqual(p2.incomplete_obligations(result), dict(cells=2, references=1, boundaries=7, inheritedBoundaries=1, addedSections=1, regions=1))

    def test_public_cli_replays_before_strict_incomplete_exit(self):
        result = dict(typedClauses=31, sourceAnchors=810, cellCounts={"unparsed": 1}, remainingArchitecturalReferences=["required"],
                      additionalSections=[{}], p2Complete=False)
        args = ["p2", "extract", "--old-cache", "old", "--publisher-cache", "new", "--baseline-root", "base", "--output", "target/p2", "--require-complete"]
        with patch("sys.argv", args), patch.object(p2, "reconstruct", return_value=result) as replay, contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                p2.main()
        self.assertEqual(error.exception.code, 2)
        replay.assert_called_once()

    def test_saved_output_is_compared_with_fresh_reconstruction(self):
        def fresh(old, new, baseline, output):
            output.mkdir()
            (output/"p2-constraints.json").write_text("actual source reconstruction\n")
            return {"p2Complete": False}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/"output"
            fresh(None, None, None, output)
            with patch.object(p2, "reconstruct", side_effect=fresh):
                p2.check(None, None, None, output)
                (output/"p2-constraints.json").write_text('{"p2Complete":true}')
                with self.assertRaisesRegex(ValueError, "differs from fresh source"):
                    p2.check(None, None, None, output)

    def test_public_reconstruction_executes_adoption_with_correct_output_and_baselines(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)/"new"
            with patch.object(p2.adoption, "reconstruct", side_effect=ValueError("actual source unavailable")) as replay:
                with self.assertRaisesRegex(ValueError, "actual source unavailable"):
                    p2.reconstruct(Path("old"), Path("publisher"), Path("baselines"), output)
            replay.assert_called_once_with(Path("old"), Path("publisher"), output/"source-adoption", baseline_root=Path("baselines"))
            self.assertFalse((output/"p2-constraints.json").exists())

    def test_h64_mode_proof_keeps_native_32bit_operands_and_requires_exact_notes(self):
        pages={}
        for side,page,a,b,n1,n2 in (("predecessor",340,29,39,75,76),("replacement",342,27,37,76,77)):
            values={a:"VMOVD reg32/mem32, xmm 1",b:"VMOVD reg32/mem32, xmm 2",
                    n1:"Note 1: These encodings are only available in 64-bit mode.",
                    n2:"Note 2: These encodings are only available in non-64-bit modes."}
            pages[side]=[dict(pdfPage=page,cells=[dict(id=f"pdf:{page}:cell:{i}",text=t) for i,t in values.items()])]
        self.assertTrue(p2.h64_movd_mode_proof(pages,["long-64"]))
        for scope in (["legacy-32"],["long-compatibility"],["host-64"],[],[64]):
            with self.subTest(scope=scope),self.assertRaises(ValueError):p2.h64_movd_mode_proof(pages,scope)
        for attack in ("swapped-notes","unmarked-row","operand-size-as-mode"):
            bad=copy.deepcopy(pages);cells={c["id"]:c for c in bad["replacement"][0]["cells"]}
            if attack=="swapped-notes":cells['pdf:342:cell:76']['text'],cells['pdf:342:cell:77']['text']=cells['pdf:342:cell:77']['text'],cells['pdf:342:cell:76']['text']
            elif attack=="unmarked-row":cells['pdf:342:cell:37']['text']='VMOVD reg32/mem32, xmm'
            else:cells['pdf:342:cell:77']['text']='Note 2: These encodings use 32-bit data.'
            with self.subTest(attack=attack),self.assertRaises(ValueError):p2.h64_movd_mode_proof(bad,["long-64"])

    def test_h64_recipe_is_specific_to_non64_movd_and_does_not_erase_gf(self):
        recipe=p2.RESOLUTIONS['paired:movd-store-opcode']
        self.assertEqual(recipe['state'],'excluded-selected-execution-mode')
        self.assertIn('paired:movd-64-vex-store-row',recipe['rules'])
        self.assertIn('h64-movd-mode-proof',recipe['checks'])
        self.assertNotIn('paired:gf-inverse-table',p2.RESOLUTIONS)
        self.assertEqual(p2.extended.migration.paired.RULES['movd-transfer']['parameters']['payloadBits'],32)


if __name__ == "__main__":
    unittest.main()
