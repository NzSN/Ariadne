"""Actual GF-table words, finite arithmetic oracle and no-source-correction controls."""
import copy
import unittest

import amd64_p2_gf as gf


def peasant_multiply(a,b):
    value=0
    while b:
        if b&1:value^=a
        a=(a<<1)^(0x11b if a&128 else 0)
        b>>=1
    return value


def power(value,exponent):
    result=1
    while exponent:
        if exponent&1:result=peasant_multiply(result,value)
        value=peasant_multiply(value,value)
        exponent>>=1
    return result


class GFTableControls(unittest.TestCase):
    def setUp(self):
        self.page=gf.entry.read(gf.INPUT.parent/"p2-gf-table-excerpt.json")
        self.pack=gf.entry.read(gf.INPUT)

    def test_all_65536_byte_products_against_independent_shift_reduce_oracle(self):
        for a in range(256):
            for b in range(256):self.assertEqual(gf.multiply(a,b),peasant_multiply(a,b))

    def test_all_256_inverses_against_independent_exponentiation(self):
        for value in range(256):
            actual=gf.inverse(value)
            self.assertEqual(actual,power(value,254) if value else 0)
            self.assertEqual(gf.multiply(value,actual),1 if value else 0)
        self.assertEqual(gf.inverse(0xf1),0x23)
        self.assertEqual(gf.multiply(0xf1,0x5b),0x5a)

    def test_actual_table_keeps_the_duplicate_literal_and_noninverse_witness(self):
        table=gf.literal_table(self.page,gf.digest(self.page["cells"]),self.pack["literalValues"])
        self.assertEqual(len(table),256)
        self.assertEqual(table[0xf1]["value"],0x5b)
        self.assertEqual(table[0xf0]["value"],0x5b)
        self.assertEqual(table[0xf1]["sourceCell"],"pdf:228:cell:67")
        self.assertEqual(table[0xf1]["word"]["text"],"5B")
        mismatches=[n for n in range(256) if table[n]["value"]!=gf.inverse(n)]
        self.assertEqual(mismatches,[0xf1])
        self.assertEqual(table[table[0xf1]["value"]]["value"],0xf0)

    def test_geometry_replay_is_independent_of_pdf_cell_reading_order(self):
        changed=copy.deepcopy(self.page)
        changed["cells"].reverse()
        self.assertEqual([(v["inputByte"],v["value"]) for v in gf.parse_table(changed)],
                         [(v["inputByte"],v["value"]) for v in gf.parse_table(self.page)])

    def test_omitted_headers_values_moved_words_and_unknown_table_material_fail(self):
        for attack in ("header","value","duplicate","moved","unknown"):
            page=copy.deepcopy(self.page)
            if attack=="header":page["cells"]=[c for c in page["cells"] if c["id"]!="pdf:228:cell:34"]
            elif attack=="value":page["cells"]=[c for c in page["cells"] if c["id"]!="pdf:228:cell:67"]
            elif attack=="duplicate":page["cells"].append(copy.deepcopy(next(c for c in page["cells"] if c["id"]=="pdf:228:cell:67")))
            else:
                cell=next(c for c in page["cells"] if c["id"]=="pdf:228:cell:67")
                if attack=="moved":
                    cell["wordBoxes"][0]["rect"][0]+=5
                    cell["wordBoxes"][0]["rect"][2]+=5
                else:cell["wordBoxes"][0]["text"]="unparsed"
            with self.subTest(attack=attack),self.assertRaises(ValueError):gf.parse_table(page)

    def test_resealed_numeric_correction_cannot_replace_publisher_literal(self):
        page=copy.deepcopy(self.page)
        cell=next(c for c in page["cells"] if c["id"]=="pdf:228:cell:67")
        cell["text"]="23";cell["wordBoxes"][0]["text"]="23"
        with self.assertRaisesRegex(ValueError,"source population"):
            gf.literal_table(page,gf.digest(self.page["cells"]),self.pack["literalValues"])
        with self.assertRaisesRegex(ValueError,"literal lookup"):
            gf.literal_table(page,gf.digest(page["cells"]),self.pack["literalValues"])

    def test_bool_nonbyte_and_missing_source_inputs_fail(self):
        for value in (True,-1,256,0.0,None):
            with self.subTest(value=value),self.assertRaises(ValueError):gf.inverse(value)
            with self.subTest(value=value),self.assertRaises(ValueError):gf.multiply(value,1)
        with self.assertRaisesRegex(ValueError,"source population"):
            gf.assess(dict(predecessor=[],replacement=[]))


if __name__=="__main__":unittest.main()
