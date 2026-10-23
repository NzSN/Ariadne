"""Dependent address tails and independently enumerated finite MOV8 membership."""
import copy
import unittest

import amd64_domains as domain


def grammar_document():
    forms = []
    for name, opcode in domain.MEMORY_FORMS.items():
        alternatives = []
        for bits in (32, 64):
            for rex in (None, *range(0x40, 0x48)):
                prefix = ("67" if bits == 32 else "") + (f"{rex:02x}" if rex is not None else "")
                alternatives.append(dict(environment={"addressBits": [bits]}, sequence=[
                    dict(kind="literal", bytes=prefix + opcode),
                    dict(kind="modrm-sib-displacement", name="address", mod=[0, 1, 2], reg=[0, 4], rm=[0, 4, 5],
                         sib=dict(scale=[0, 3], index=[0, 4], base=[0, 5]),
                         displacements={"8": [-128, 0, 127], "32": [-2147483648, 0, 2147483647]})]))
        rules = domain.MEMORY_RULES | {"mov8-direction-" + opcode, "mov-copy-width", "register-code-map",
                                      "byte-register-alias-preservation", "flags-unmodified"}
        forms.append(dict(id=name, meaning="mov8-memory-" + ("store" if opcode == "88" else "load"),
                          sourceRules=sorted(rules), alternatives=alternatives))
    return dict(schema=domain.MEMORY_SCHEMA, scope=domain.memory_mov8_scope(),
                sourcePacks=[dict(path=name, sha256="0" * 64) for name in
                             (domain.PACK_PATH, domain.ARCHITECTURE_PACK_PATH)], forms=forms)


class MemoryDomainControls(unittest.TestCase):
    def test_dependent_grammar_equals_independent_5760_member_construction(self):
        document = grammar_document()
        before = copy.deepcopy(document)
        points = domain.enumerate_domain(document)
        self.assertEqual(points, domain.memory_mov8_points())
        self.assertEqual(len(points), 5760)
        self.assertEqual(document, before)
        for point in points:
            decoded = domain.decode_memory_mov8(point["bytes"])
            self.assertEqual(decoded["addressBits"], point["environment"]["addressBits"])
            self.assertEqual(decoded["consumedLength"] * 2, len(point["bytes"]))

    def test_rex_high_bytes_and_all_three_extensions_are_distinct(self):
        expected = {"8820": (0, 1, 0, None), "408820": (4, 0, 0, None),
                    "448820": (12, 0, 0, None), "418800": (0, 0, 8, None),
                    "42880420": (0, 0, 0, 12), "47882400": (12, 0, 8, 8)}
        for code, values in expected.items():
            d = domain.decode_memory_mov8(code)
            self.assertEqual((d["dataBank"], d["dataByte"], d["base"], d["index"]), values)

    def test_rip_eip_use_next_ip_and_signed_displacement_before_address_wrap(self):
        registers = [0] * 16
        for prefix, width in (("", 64), ("67", 32), ("41", 64), ("6741", 32)):
            d = domain.decode_memory_mov8(prefix + "8a0500000080")
            self.assertTrue(d["ipRelative"])
            self.assertIsNone(d["base"])
            va = (1 << 32) - 3
            self.assertEqual(domain.memory_mov8_address(d, registers, va),
                             (va + d["consumedLength"] - (1 << 31)) & ((1 << width) - 1))

    def test_sib_no_base_ignores_rex_b_and_index_four_depends_on_rex_x(self):
        registers = [0x100000010 + index for index in range(16)]
        for prefix in ("", "41", "67", "6741"):
            d = domain.decode_memory_mov8(prefix + "8804e500000080")
            self.assertTrue(d["noBase"])
            self.assertIsNone(d["base"])
            self.assertIsNone(d["index"])
            self.assertEqual(domain.memory_mov8_address(d, registers, 0x401000),
                             -(1 << 31) & ((1 << d["addressBits"]) - 1))
        d = domain.decode_memory_mov8("67438804e500000080")
        self.assertEqual(d["index"], 12)
        self.assertEqual(domain.memory_mov8_address(d, registers, 0x401000),
                         (registers[12] * 8 - (1 << 31)) & 0xffffffff)

    def test_missing_extra_or_unselected_dependent_bytes_and_prefixes_fail(self):
        for code in ("8804", "880500", "880090", "88042000", "884000", "880401", "8801",
                     "884001", "880501000000", "4087c0", "488800", "668800", "40678800",
                     "67678800", "40408800", "88c0", "8804a000000000"):
            # 884000 is a selected disp8 zero point, so an extra suffix rejects it.
            if code == "884000":
                code += "00"
            with self.subTest(code=code), self.assertRaises(ValueError):
                domain.decode_memory_mov8(code)

    def test_dependent_node_refuses_unknown_bits_types_missing_values_and_budget(self):
        initial = grammar_document()
        for attack in ("register", "boolean", "unsigned-disp", "omitted-disp", "unknown-field"):
            document = copy.deepcopy(initial)
            node = document["forms"][0]["alternatives"][0]["sequence"][-1]
            if attack == "register":
                node["mod"].append(3)
            elif attack == "boolean":
                node["sib"]["index"] = [False, 4]
            elif attack == "unsigned-disp":
                node["displacements"]["8"].append(255)
            elif attack == "omitted-disp":
                node["displacements"].pop("32")
            else:
                node["ignoreMissingSib"] = True
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                domain.enumerate_domain(document)
        with self.assertRaises(domain.DomainUnknown):
            domain.enumerate_domain(initial, budget=100)
        initial["schema"] = domain.SCHEMA
        initial["sourcePack"] = initial.pop("sourcePacks")[0]
        with self.assertRaises(domain.DomainUnknown):
            domain.enumerate_domain(initial)

    def test_partial_fields_cannot_claim_the_independent_finite_denominator(self):
        for attack in ("sib-index", "disp32", "address32", "rex-x", "rip-relative"):
            document = grammar_document()
            for form in document["forms"]:
                if attack == "address32":
                    form["alternatives"] = [a for a in form["alternatives"] if a["environment"]["addressBits"] == [64]]
                elif attack == "rex-x":
                    form["alternatives"] = [a for a in form["alternatives"] if "42" not in a["sequence"][0]["bytes"]]
                else:
                    for alternative in form["alternatives"]:
                        node = alternative["sequence"][-1]
                        if attack == "sib-index":
                            node["sib"]["index"] = [0]
                        elif attack == "disp32":
                            node["displacements"]["32"] = [0]
                        else:
                            node["rm"] = [0, 4]
            self.assertNotEqual(domain.enumerate_domain(document), domain.memory_mov8_points(), attack)


if __name__ == "__main__":
    unittest.main()
