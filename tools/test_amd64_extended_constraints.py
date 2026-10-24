"""Source-bound scaling examples and independent signed-displacement arithmetic."""
import copy
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

import amd64_extended_constraints as source


class ExtendedConstraintControls(unittest.TestCase):
    def setUp(self):
        self.pack=source.entry.read(source.INPUT)

    def test_pack_pins_both_source_volumes_and_keeps_unresolved_scope(self):
        self.assertEqual(len(source.validate_structure(self.pack)),53)
        self.assertEqual(len(self.pack["clauses"]),9)
        self.assertEqual(set(self.pack["sources"]),{"24592","24594"})
        self.assertIn("mov-displacement-reference-mismatch",self.pack["boundaries"])
        self.assertFalse(self.pack["clauses"]["mov-displacement-unresolved-reference"]["parameters"]["adjudicated"])

    def test_all_1792_encoded_byte_and_memory_access_size_cases(self):
        for factor in (1,2,4,8,16,32,64):
            for raw in range(256):
                signed=struct.unpack('b',bytes([raw]))[0]
                actual=source.scaled_disp8(raw,factor)
                self.assertEqual(actual,signed*factor)
                selected=source.select_displacement(actual,factor)
                self.assertEqual((selected["bytes"],selected["encoded"]),(1,raw))
                self.assertFalse(selected["productionAdmission"] or selected["legalDomainComplete"])

    def test_manual_full_vector_and_broadcast_examples(self):
        self.assertEqual(source.scaled_disp8(6,64),384)
        self.assertEqual(source.scaled_disp8(0xd0,4),-192)
        self.assertEqual(source.select_displacement(384,64)["encoded"],6)
        self.assertEqual(source.select_displacement(-192,4)["encoded"],0xd0)

    def test_all_signed_16_offsets_choose_compressed_iff_in_the_independent_image(self):
        for factor in (1,2,4,8,16,32,64):
            image={n*factor for n in range(-128,128)}
            for displacement in range(-32768,32768):
                chosen=source.select_displacement(displacement,factor)
                self.assertEqual(chosen["bytes"]==1,displacement in image)
                if chosen["bytes"]==4:
                    self.assertEqual(struct.unpack('<i',chosen["encoded"].to_bytes(4,'little'))[0],displacement)

    def test_boundary_values_and_nonmultiples_never_wrap_into_disp8(self):
        for factor in source.FACTORS:
            self.assertEqual(source.select_displacement(-128*factor,factor)["bytes"],1)
            self.assertEqual(source.select_displacement(127*factor,factor)["bytes"],1)
            for value in (-128*factor-1,128*factor,-(1<<31),(1<<31)-1):
                self.assertEqual(source.select_displacement(value,factor)["bytes"],4)
            if factor>1:self.assertEqual(source.select_displacement(factor+1,factor)["bytes"],4)

    def test_bool_float_bad_access_size_and_unsupported_domains_fail(self):
        for args in [(True,4),(1.0,4),(-1,4),(256,4),(1,True),(1,3),(1,0),(1,128)]:
            with self.subTest(args=args),self.assertRaises(ValueError):source.scaled_disp8(*args)
        for args in [(True,4),(0.0,4),(-(1<<31)-1,4),(1<<31,4),(0,3)]:
            with self.subTest(args=args),self.assertRaises(ValueError):source.select_displacement(*args)

    def test_resealed_rule_boundary_scope_and_pin_forgery_fail(self):
        for attack in ('rule','boundary','source','predecessor','anchor','foreign','parameter-type','adoption'):
            pack=copy.deepcopy(self.pack)
            if attack=='rule':pack['clauses'].pop('disp8-source-reference')
            elif attack=='boundary':pack['boundaries'].pop('memory-shape-admission')
            elif attack=='source':pack['sources']['24592']='0'*64
            elif attack=='predecessor':pack['architecturePackSha256']='0'*64
            elif attack=='anchor':pack['sourceCells'].pop(next(iter(pack['sourceCells'])))
            elif attack=='foreign':pack['sourceCells']['foreign']={}
            elif attack=='parameter-type':pack['clauses']['sae-scope']['parameters']['evexB']=True
            else:pack['productionAdmission']=True
            with self.subTest(attack=attack),self.assertRaises(ValueError):source.validate_structure(pack)

    def test_actual_reference_source_words_and_word_geometry_stay_bound(self):
        key='24594/pdf:66:cell:19'
        expected=self.pack['sourceCells'][key]
        actual={**copy.deepcopy(expected),'text':'“Disp8*N” in APM Volume 1 for more details.'}
        source.migration.paired.conversion.validate_anchor(expected,actual)
        for field in ('text','wordSpan','rect','wordBoxesSha256','unicodeSha256'):
            changed=copy.deepcopy(actual)
            if field in ('wordSpan','rect'):changed[field][0]+=1
            else:changed[field]='forged'
            with self.subTest(field=field),self.assertRaises(ValueError):
                source.migration.paired.conversion.validate_anchor(expected,changed)

    def test_omitted_actual_publication_and_source_replay_are_not_a_pass(self):
        with self.assertRaisesRegex(ValueError,'publication omitted'):
            source.validate_cells(self.pack,{'24592':[]})
        with self.assertRaisesRegex(ValueError,'actual source anchor omitted'):
            source.validate_cells(self.pack,{'24592':[],'24594':[]})
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,'missing'):source.check(Path('old'),Path('new'),Path(tmp)/'missing')
            with patch.object(source.migration,'reconstruct',side_effect=ValueError('source replay failed')):
                with self.assertRaisesRegex(ValueError,'source replay failed'):
                    source.reconstruct(Path('old'),Path('new'),Path(tmp)/'fresh')
            self.assertFalse((Path(tmp)/'fresh/extended-constraints.json').exists())


if __name__=='__main__':unittest.main()
