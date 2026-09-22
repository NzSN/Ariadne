import json
import copy
import unittest

import amd64_forms


class FormInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.forms, cls.review = amd64_forms.generate()
        cls.by_id = {form["form_id"]: form for form in cls.forms["forms"]}

    def test_every_entry_has_a_stable_form_or_reviewed_redirect(self):
        self.assertEqual(154, len(self.review["entries"]))
        self.assertTrue(all(entry["form_ids"] or entry["redirects"] for entry in self.review["entries"]))

    def test_unknown_constraints_are_not_encoded_as_unrestricted(self):
        for form in self.forms["forms"]:
            for name in ("modes", "features", "cpl", "operand_sizes", "address_sizes", "prefixes"):
                constraint = form["constraints"][name]
                if constraint["knowledge"] == "unknown":
                    self.assertEqual([], constraint.get("allowed", constraint.get("required")))
            if form["review"]["level"] == "semantic-reviewed":
                self.assertEqual("reviewed", form["review"]["status"])
                self.assertEqual([], form["review"]["open_obligations"])
            else:
                self.assertTrue(form["review"]["open_obligations"])

    def test_merged_and_split_cells_are_reconciled(self):
        self.assertEqual("0F 40 /r", self.by_id["AMD64-F-0150"]["encoding"]["source_text"])
        self.assertEqual("0F 92 /0", self.by_id["AMD64-F-0779"]["encoding"]["source_text"])
        self.assertEqual("8F RXB.09 0.1111.0.00 12 /0", self.by_id["AMD64-F-0453"]["encoding"]["source_text"])
        self.assertEqual("C4 RXB.02 0.cntl.0.00 F7 /r", self.by_id["AMD64-F-0068"]["encoding"]["source_text"])

    def test_nop_memory_shape_does_not_imply_memory_access(self):
        for form_id in ("AMD64-F-0553", "AMD64-F-0554", "AMD64-F-0555", "AMD64-F-0556"):
            form = self.by_id[form_id]
            self.assertTrue(all(operand["access"] == "none" for operand in form["operands"]))
            self.assertEqual(["rIP"], form["semantics"]["writes"]["items"])
            self.assertEqual("pending-semantic-review", form["review"]["status"])
            self.assertIn("review-prefix-aliases-including-F3-90-PAUSE-and-REX-B-XCHG",
                          form["review"]["open_obligations"])

    def test_unary_review_retains_memory_alternatives_and_legacy_opcode_modes(self):
        dec = self.by_id["AMD64-F-0282"]
        self.assertEqual(["gpr", "memory"], dec["operands"][0]["allowed_concrete_kinds"])
        self.assertEqual(["CF"], dec["semantics"]["preserved"]["items"])
        self.assertEqual("partial", dec["implementation"]["status"])
        embedded = self.by_id["AMD64-F-0286"]
        self.assertNotIn("long64", embedded["constraints"]["modes"]["allowed"])
        self.assertEqual(["gpr"], embedded["operands"][0]["allowed_concrete_kinds"])
        self.assertTrue(dec["review"]["open_obligations"])

    def test_contaminated_and_wrapped_cells_are_repaired(self):
        self.assertEqual("0F 01 FA", self.by_id["AMD64-F-0477"]["encoding"]["source_text"])
        self.assertEqual("0F 01 FB", self.by_id["AMD64-F-0548"]["encoding"]["source_text"])
        self.assertEqual("IMUL reg16, reg/mem16, imm16", self.by_id["AMD64-F-0309"]["source_spelling"])
        self.assertEqual("MOV reg16/32/64/mem16, segReg", self.by_id["AMD64-F-0486"]["source_spelling"])

    def test_shl_redirect_and_xlat_identity_are_preserved(self):
        shl = next(entry for entry in self.review["entries"] if entry["entry_id"] == "V3-GP-133")
        self.assertEqual("V3-GP-126", shl["redirects"][0]["entry_id"])
        xlat = next(entry for entry in self.review["entries"] if entry["entry_id"] == "V3-GP-152")
        xlatb = next(entry for entry in self.review["entries"] if entry["entry_id"] == "V3-GP-153")
        self.assertEqual(xlat["form_ids"], xlatb["form_ids"])
        self.assertNotEqual(xlat["entry_id"], xlatb["entry_id"])

    def test_core_integer_review_is_source_grounded_but_not_closed(self):
        add = self.by_id["AMD64-F-0006"]
        self.assertEqual("reviewed", add["constraints"]["modes"]["knowledge"])
        self.assertEqual("read-write", add["operands"][0]["access"])
        self.assertEqual("read", add["operands"][1]["access"])
        self.assertIn("#PF", {item["vector"] for item in add["semantics"]["exceptions"]["items"]})
        self.assertEqual("pending-semantic-review", add["review"]["status"])
        result = amd64_forms.validate_decoded(add, {
            "form_id": add["form_id"], "encoding_family": "legacy", "mode": "long64",
            "operand_size": 8, "address_size": 64,
            "prefix_conflict": False, "prefixes": [], "rex_present": False, "high_byte_register": False,
            "operands": [{"kind": "gpr", "width_bits": 8, "identity": "gpr:0:low8",
                          "encoded_width_bits": 8, "semantic_width_bits": 8, "extension": "none",
                          "access": "read-write", "evaluation_order": 1},
                         {"kind": "immediate", "width_bits": 8, "identity": "",
                          "encoded_width_bits": 8, "semantic_width_bits": 8, "extension": "none",
                          "access": "read", "evaluation_order": 2}],
        }, {"features": [], "modes": ["long64"], "operand_sizes": [8, 16, 32, 64], "address_sizes": [32, 64]})
        self.assertEqual("undetermined", result["kind"])

    def test_bounded_core_byte_forms_are_closed_with_exact_identity(self):
        closed = {form["form_id"] for form in self.forms["forms"]
                  if form["review"]["level"] == "semantic-reviewed"}
        self.assertEqual(33, len(closed))
        self.assertTrue({"AMD64-F-0026", "AMD64-F-0029", "AMD64-F-0496",
                         "AMD64-F-0499", "AMD64-F-0503-R"} <= closed)
        add = self.by_id["AMD64-F-0026"]
        self.assertEqual(["gpr:0:low8"], add["operands"][0]["allowed_identities"])
        self.assertEqual("reviewed", add["review"]["status"])
        decoded = {
            "form_id": add["form_id"], "encoding_family": "legacy", "mode": "long64",
            "operand_size": 8, "address_size": 64, "prefix_conflict": False, "prefixes": [],
            "rex_present": False, "high_byte_register": True,
            "operands": [{"kind": "gpr", "width_bits": 8, "identity": "gpr:0:high8",
                          "encoded_width_bits": 8, "semantic_width_bits": 8, "extension": "none",
                          "access": "read-write", "evaluation_order": 1},
                         {"kind": "immediate", "width_bits": 8, "identity": "",
                          "encoded_width_bits": 8, "semantic_width_bits": 8, "extension": "none",
                          "access": "read", "evaluation_order": 2}],
        }
        self.assertEqual("normalization-error",
                         amd64_forms.validate_decoded(add, decoded, {"features": [], "modes": ["long64"], "operand_sizes": [8, 16, 32, 64], "address_sizes": [32, 64]})["kind"])
        add64 = self.by_id["AMD64-F-0029"]
        self.assertEqual((32, 64, "sign"),
                         (add64["operands"][1]["encoded_width_bits"],
                          add64["operands"][1]["semantic_width_bits"],
                          add64["operands"][1]["extension"]))
        mov64 = self.by_id["AMD64-F-0499"]
        self.assertEqual((64, 64, "none"),
                         (mov64["operands"][1]["encoded_width_bits"],
                          mov64["operands"][1]["semantic_width_bits"],
                          mov64["operands"][1]["extension"]))
        mov_sign = self.by_id["AMD64-F-0503-R"]
        self.assertEqual((32, 64, "sign"),
                         (mov_sign["operands"][1]["encoded_width_bits"],
                          mov_sign["operands"][1]["semantic_width_bits"],
                          mov_sign["operands"][1]["extension"]))

    def test_closed_data_drives_width_shape_and_lock_validation(self):
        form = copy.deepcopy(self.by_id["AMD64-F-0026"])
        form["review"].update(level="semantic-reviewed", status="reviewed", open_obligations=[])
        decoded = {
            "form_id": form["form_id"], "encoding_family": "legacy", "mode": "long64",
            "operand_size": 8, "address_size": 64,
            "prefix_conflict": False, "prefixes": [], "rex_present": False, "high_byte_register": False,
            "operands": [{"kind": "gpr", "width_bits": 8, "identity": "gpr:0:low8",
                          "encoded_width_bits": 8, "semantic_width_bits": 8, "extension": "none",
                          "access": "read-write", "evaluation_order": 1},
                         {"kind": "immediate", "width_bits": 8, "identity": "",
                          "encoded_width_bits": 8, "semantic_width_bits": 8, "extension": "none",
                          "access": "read", "evaluation_order": 2}],
        }
        self.assertEqual("validated", amd64_forms.validate_decoded(form, decoded, {"features": [], "modes": ["long64"], "operand_sizes": [8, 16, 32, 64], "address_sizes": [32, 64]})["kind"])
        profile = {"features": [], "modes": ["long64"], "operand_sizes": [16, 32, 64], "address_sizes": [32, 64]}
        self.assertEqual({"kind": "profile-error", "reasons": ["operand-size-not-implemented-by-profile"]},
                         amd64_forms.validate_decoded(form, decoded, profile))
        profile.update(operand_sizes=[8], address_sizes=[32])
        self.assertEqual({"kind": "profile-error", "reasons": ["address-size-not-implemented-by-profile"]},
                         amd64_forms.validate_decoded(form, decoded, profile))
        profile["address_sizes"] = [64]
        conflicting = dict(decoded, prefix_conflict=True)
        self.assertEqual({"kind": "undefined-encoding", "reasons": ["conflicting-prefixes"]},
                         amd64_forms.validate_decoded(form, conflicting, profile))
        del conflicting["prefix_conflict"]
        self.assertEqual("undetermined", amd64_forms.validate_decoded(form, conflicting, profile)["kind"])
        self.assertEqual("undetermined", amd64_forms.validate_decoded(form, decoded, {"features": [], "modes": ["long64"]})["kind"])
        privileged = copy.deepcopy(form)
        privileged["constraints"]["cpl"]["allowed"] = [0]
        self.assertEqual({"kind": "undetermined", "obligations": ["cpu-privilege-binding-required"]},
                         amd64_forms.validate_decoded(privileged, decoded, profile))
        wrong_width = copy.deepcopy(decoded)
        wrong_width["operands"][1]["width_bits"] = 16
        self.assertEqual("normalization-error", amd64_forms.validate_decoded(form, wrong_width, {"features": [], "modes": ["long64"], "operand_sizes": [8, 16, 32, 64], "address_sizes": [32, 64]})["kind"])
        locked = copy.deepcopy(decoded)
        locked["prefixes"] = ["lock"]
        self.assertEqual("architectural-invalid", amd64_forms.validate_decoded(form, locked, {"features": [], "modes": ["long64"], "operand_sizes": [8, 16, 32, 64], "address_sizes": [32, 64]})["kind"])

    def test_redundant_rex_facts_must_be_coherent(self):
        form = copy.deepcopy(self.by_id["AMD64-F-0026"])
        form["review"].update(level="semantic-reviewed", status="reviewed", open_obligations=[])
        decoded = {
            "form_id": form["form_id"], "encoding_family": "legacy", "mode": "long64",
            "operand_size": 8, "address_size": 64,
            "prefix_conflict": False, "prefixes": ["rex"], "rex_present": False, "high_byte_register": False,
            "operands": [{"kind": "gpr", "width_bits": 8, "identity": "gpr:0:low8",
                          "encoded_width_bits": 8, "semantic_width_bits": 8, "extension": "none",
                          "access": "read-write", "evaluation_order": 1},
                         {"kind": "immediate", "width_bits": 8, "identity": "",
                          "encoded_width_bits": 8, "semantic_width_bits": 8, "extension": "none",
                          "access": "read", "evaluation_order": 2}],
        }
        self.assertEqual("normalization-error", amd64_forms.validate_decoded(form, decoded, {"features": [], "modes": ["long64"], "operand_sizes": [8, 16, 32, 64], "address_sizes": [32, 64]})["kind"])
        decoded.update(rex_present=True, mode="protected", address_size=32)
        self.assertIn("incoherent-decoder-evidence",
                      amd64_forms.validate_decoded(form, decoded, {
                          "features": [], "modes": ["protected"], "operand_sizes": [8], "address_sizes": [32]
                      })["reasons"])

    def test_empty_unknown_allowlists_cannot_be_closed_by_status_only(self):
        form = copy.deepcopy(self.by_id["AMD64-F-0001"])
        form["review"].update(level="semantic-reviewed", status="reviewed", open_obligations=[])
        # The executable JSON mirror rejects absent reviewed mode data rather
        # than interpreting an extracted empty list as all modes.
        decoded = {
            "form_id": form["form_id"], "encoding_family": "legacy", "mode": "real",
            "operand_size": 8, "address_size": 16,
            "prefix_conflict": False, "prefixes": [], "rex_present": False, "high_byte_register": False, "operands": [],
        }
        self.assertNotEqual("validated", amd64_forms.validate_decoded(form, decoded, {"features": [], "modes": ["real"], "operand_sizes": [8, 16, 32], "address_sizes": [16, 32]})["kind"])


if __name__ == "__main__":
    unittest.main()
