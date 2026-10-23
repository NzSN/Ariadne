"""Finite grammar and reviewed MOV8 denominator controls."""
import copy
from pathlib import Path
import unittest

import amd64_domains as domain

FIXTURES = domain.ROOT / "tests/bap/fixtures/amd64-semantics/mov8-domain"


def fixture():
    return domain.read(FIXTURES / "legal-domain.json")


class FiniteDomainControls(unittest.TestCase):
    def test_reviewed_all_640_points_and_deterministic_order(self):
        item = fixture()
        before = copy.deepcopy(item)
        points = domain.validate_mov8_domain(item)
        self.assertEqual(len(points), 640)
        self.assertEqual(sum(point["form"] == "mov8-register-88" for point in points), 320)
        self.assertEqual(points, sorted(points, key=lambda point: point["bytes"]))
        self.assertEqual(item, before)

    def test_narrowed_grammar_cannot_be_a_smaller_architectural_denominator(self):
        for attack in ("rm", "reg", "prefix", "form"):
            item = fixture()
            if attack in {"rm", "reg"}:
                for alternative in item["forms"][0]["alternatives"]:
                    part = next(part for part in alternative["sequence"][-1]["parts"] if part["name"] == attack)
                    part["values"].pop()
            elif attack == "prefix":
                item["forms"][0]["alternatives"].pop()
            else:
                item["forms"].pop()
            with self.assertRaises(ValueError, msg=attack):
                domain.validate_mov8_domain(item)

    def test_reserved_scope_changes_and_memory_forms_do_not_enter_slice(self):
        for attack in ("mod", "rex", "vendor", "mode_type", "exclusion", "source_complete"):
            item = fixture()
            if attack == "mod":
                item["forms"][0]["alternatives"][0]["sequence"][-1]["parts"][0]["values"] = [2, 3]
            elif attack == "rex":
                item["forms"][0]["alternatives"][1]["sequence"][0]["bytes"] = "48"
            elif attack == "vendor":
                item["scope"]["environmentAxes"]["vendor"] = ["Intel"]
            elif attack == "mode_type":
                item["scope"]["environmentAxes"]["mode"] = [64.0]
            elif attack == "exclusion":
                item["scope"]["exclusions"].append("rm7")
            else:
                item["scope"]["sourceComplete"] = True
            with self.assertRaises(ValueError, msg=attack):
                domain.validate_mov8_domain(item)

    def test_bits_must_be_disjoint_total_and_typed(self):
        for attack in ("overlap", "omitted", "boolean", "duplicate"):
            item = fixture()
            parts = item["forms"][0]["alternatives"][0]["sequence"][-1]["parts"]
            if attack == "overlap":
                parts[1]["lsb"] = 2
            elif attack == "omitted":
                parts.pop()
            elif attack == "boolean":
                parts[-1]["values"] = [False, 1]
            else:
                parts[-1]["values"].append(7)
            with self.assertRaises(ValueError, msg=attack):
                domain.enumerate_domain(item)

    def test_overlap_between_alternatives_or_forms_is_not_collapsed(self):
        item = fixture()
        item["forms"][0]["alternatives"].append(copy.deepcopy(item["forms"][0]["alternatives"][0]))
        with self.assertRaisesRegex(ValueError, "overlapping"):
            domain.enumerate_domain(item)
        item = fixture()
        item["forms"][1]["alternatives"] = copy.deepcopy(item["forms"][0]["alternatives"])
        with self.assertRaisesRegex(ValueError, "overlapping"):
            domain.enumerate_domain(item)

    def test_unsupported_dependencies_and_budget_are_unknown_not_partial_results(self):
        item = fixture()
        with self.assertRaises(domain.DomainUnknown):
            domain.enumerate_domain(item, budget=10)
        item["forms"][0]["alternatives"][0]["sequence"][-1]["kind"] = "dependent-modrm-sib"
        with self.assertRaises(domain.DomainUnknown):
            domain.enumerate_domain(item)

    def test_little_endian_fields_and_maximum_consumed_length(self):
        item = fixture()
        item["forms"] = [item["forms"][0]]
        alternative = item["forms"][0]["alternatives"][0]
        alternative["sequence"] = [dict(kind="literal", bytes="90"), dict(kind="uint-le", name="imm", width=2, values=[0x1234, 0xabcd])]
        item["forms"][0]["alternatives"] = [alternative]
        self.assertEqual([point["bytes"] for point in domain.enumerate_domain(item)], ["903412", "90cdab"])
        alternative["sequence"][0]["bytes"] = "90" * 14
        with self.assertRaisesRegex(ValueError, "length"):
            domain.enumerate_domain(item)

    def test_high_byte_rex_and_direction_roles(self):
        expected = {
            "88e0": (("rax", 1), ("rax", 0)),
            "8ae0": (("rax", 0), ("rax", 1)),
            "4088e0": (("rsp", 0), ("rax", 0)),
            "4488e0": (("r12", 0), ("rax", 0)),
            "4188e0": (("rsp", 0), ("r8", 0)),
            "458aff": (("r15", 0), ("r15", 0)),
        }
        for code, (source, destination) in expected.items():
            result = domain.decode_mov8_expectation(code)
            self.assertEqual((result["source"]["bank"], result["source"]["byteOffset"]), source)
            self.assertEqual((result["destination"]["bank"], result["destination"]["byteOffset"]), destination)
            self.assertEqual(result["nonDestinationBits"], "preserved")
        for code in ("4888c0", "4088c090", "6688c0", "8880", "408940", "88"):
            with self.assertRaises(ValueError, msg=code):
                domain.decode_mov8_expectation(code)

    def test_total_unsupported_and_unknown_accounting_is_not_implementation(self):
        points = domain.validate_mov8_domain(fixture())
        partitions = [dict(id="known", disposition="U", points=points[:-1], reason="producer gap"),
                      dict(id="open", disposition="X", points=points[-1:], reason="unresolved source applicability")]
        result = domain.validate_partitions(points, partitions)
        self.assertTrue(result["totalDisposition"])
        self.assertFalse(result["implementationDomainComplete"])
        self.assertFalse(result["profileBindingsValidated"])
        self.assertEqual((result["unsupported"], result["unresolved"]), (639, 1))
        partitions.pop()
        self.assertFalse(domain.validate_partitions(points, partitions)["totalDisposition"])

    def test_partition_overlap_outside_and_type_substitution_fail(self):
        points = domain.validate_mov8_domain(fixture())
        for attack in ("duplicate", "outside", "type"):
            part = dict(id="some", disposition="S", points=copy.deepcopy(points[:1]), reason="requires actual binding evidence")
            if attack == "duplicate":
                part["points"].append(copy.deepcopy(part["points"][0]))
            elif attack == "outside":
                part["points"][0]["bytes"] += "90"
            else:
                part["points"][0]["environment"]["mode"] = 64.0
            with self.assertRaises(ValueError, msg=attack):
                domain.validate_partitions(points, [part])


if __name__ == "__main__":
    unittest.main()
