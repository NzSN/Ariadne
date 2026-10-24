"""Selected source claims and query kernels never imply production admission."""
import copy
from pathlib import Path
import tempfile
import unittest

import amd64_conversion_constraints as source


class ConversionConstraintControls(unittest.TestCase):
    def setUp(self):
        self.pack=source.entry.read(source.INPUT)

    def test_exact_reviewed_source_pack_keeps_22_claims_and_four_boundaries(self):
        anchors=source.validate_structure(self.pack)
        self.assertEqual(len(self.pack["clauses"]),22)
        self.assertEqual(len(self.pack["boundaries"]),4)
        self.assertEqual(anchors,set(self.pack["sourceCells"]))
        self.assertEqual(self.pack["owners"]["ph"]["pdfPage"],942)
        self.assertEqual(self.pack["owners"]["ps"]["pdfPage"],956)

    def test_missing_or_relabelled_rule_boundary_owner_and_source_fails(self):
        for attack in ("rule","parameters","boundary","owner","publisher","anchor","extra-anchor","entry-pin","scope-field"):
            pack=copy.deepcopy(self.pack)
            if attack=="rule":pack["clauses"].pop("ps-base-memory")
            elif attack=="parameters":pack["clauses"]["ps-base-memory"]["parameters"]["memoryLoad"]=True
            elif attack=="boundary":pack["boundaries"].pop("psx-rounding-er-scope")
            elif attack=="owner":pack["owners"]["ph"]=pack["owners"]["ps"]
            elif attack=="publisher":pack["publisherSource"]["pdfSha256"]="0"*64
            elif attack=="anchor":pack["sourceCells"].pop(next(iter(pack["sourceCells"])))
            elif attack=="extra-anchor":pack["sourceCells"]["foreign"]={}
            elif attack=="entry-pin":pack["entryReviewInput"]["sha256"]="0"*64
            else:pack["productionAdmission"]=True
            with self.subTest(attack=attack),self.assertRaises(ValueError):source.validate_structure(pack)

    def test_small_actual_f16c_anchor_checks_text_geometry_and_word_identity(self):
        expected=self.pack["sourceCells"]["pdf:945:cell:109"]
        actual={**copy.deepcopy(expected),"text":"F — F16C exception."}
        source.validate_anchor(expected,actual)
        for field in ("text","rect","wordSpan","unicodeSha256","wordBoxesSha256"):
            changed=copy.deepcopy(actual)
            if field=="text":changed[field]="F — a different exception."
            elif field in ("rect","wordSpan"):changed[field][0]+=1
            else:changed[field]="0"*64
            with self.subTest(field=field),self.assertRaises(ValueError):source.validate_anchor(expected,changed)

    def test_payload_widths_are_lane_shapes_not_physical_register_kills(self):
        for name in source.PH+source.PS:
            for bits,lanes in [(128,4),(256,8),(512,16)]:
                result=source.payload_shape(name,bits)
                self.assertEqual(result["lanes"],lanes)
                self.assertEqual(result["sourcePayloadBits"],lanes*(16 if name in source.PH else 32))
                self.assertEqual(result["resultPayloadBits"],lanes*(32 if name in source.PH else 16))
                self.assertFalse(result["productionAdmission"] or result["legalDomainComplete"])

    def test_variant_memory_and_broadcast_differences_are_preserved(self):
        for bits in (128,256,512):
            for name in source.PH+source.PS:
                allowed="store" if name=="VCVTPS2PH" else "load"
                source.payload_shape(name,bits,allowed)
                with self.assertRaises(ValueError):source.payload_shape(name,bits,"load" if allowed=="store" else "store")
            self.assertEqual(source.payload_shape("VCVTPH2PSX",bits,"load",True)["memoryBroadcastBits"],16)
            self.assertEqual(source.payload_shape("VCVTPS2PHX",bits,"load",True)["memoryBroadcastBits"],32)
            for name in ("VCVTPH2PS","VCVTPS2PH"):
                with self.assertRaises(ValueError):source.payload_shape(name,bits,"load",True)
            with self.assertRaises(ValueError):source.payload_shape("VCVTPH2PSX",bits,"register",True)

    def test_invalid_names_widths_roles_and_boolean_shapes_fail(self):
        for args in [("MOV",128),("VCVTPH2PS",64),("VCVTPH2PS",True),("VCVTPH2PS",128.0),
                     ("VCVTPH2PS",128,"io"),("VCVTPH2PSX",128,"load",1)]:
            with self.subTest(args=args),self.assertRaises(ValueError):source.payload_shape(*args)

    def test_all_1024_source_table_rounding_selector_combinations(self):
        for immediate in range(256):
            for rc in range(4):
                table=[0,1,2,3,rc,rc,rc,rc]
                result=source.rounding_selector("VCVTPS2PH",immediate,rc)
                self.assertEqual(result["mode"],table[immediate%8])
                self.assertEqual(result["source"],"imm8" if immediate%8<4 else "MXCSR.RC")
                self.assertFalse(result["productionAdmission"])

    def test_x_rounding_is_conditional_and_never_resolves_er_by_default(self):
        for rc in range(4):
            self.assertEqual(source.rounding_selector("VCVTPS2PHX",255,rc)["mode"],rc)
            for name in source.PS:
                with self.assertRaises(source.SourceUnknown):source.rounding_selector(name,0,rc,embedded_rounding=True)
        for args in [("VCVTPH2PS",0,0),("VCVTPS2PH",-1,0),("VCVTPS2PH",256,0),("VCVTPS2PH",True,0),
                     ("VCVTPS2PH",0,True),("VCVTPS2PH",0,4)]:
            with self.subTest(args=args),self.assertRaises(ValueError):source.rounding_selector(*args)

    def test_source_conflicts_cannot_be_dropped_from_shapes(self):
        for name in source.PH:self.assertIn("ph-ymm-clear-overlap",source.payload_shape(name,256)["unresolved"])
        self.assertIn("ph-legacy-denormal-scope",source.payload_shape("VCVTPH2PS",128)["unresolved"])
        self.assertIn("psx-rounding-er-scope",source.payload_shape("VCVTPS2PHX",512)["unresolved"])
        self.assertIn("psx-feature-width-scope",source.payload_shape("VCVTPS2PHX",512)["unresolved"])
        clear=self.pack["clauses"]["ph-ymm-clear-statement"]["parameters"]
        self.assertEqual(set(range(clear["resultBits"])) & set(range(clear["clearLowBit"],clear["clearHighBit"]+1)),set(range(128,256)))

    def test_maintained_output_and_missing_saved_products_are_not_source_qualification(self):
        with self.assertRaisesRegex(ValueError,"test output must"):
            source.reconstruct(Path("old"),Path("new"),source.INPUT.parent/"generated")
        with tempfile.TemporaryDirectory() as directory,self.assertRaisesRegex(ValueError,"missing"):
            source.check(Path("old"),Path("new"),Path(directory)/"missing")


if __name__=="__main__":unittest.main()
