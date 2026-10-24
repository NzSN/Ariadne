"""P1 provenance/representation scope and hostile source-variant controls."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import amd64_source_adoption as source


def variant_pages():
    policy=source.entry.read(source.INPUT)
    result={}
    for side in ("old","new"):
        pages=[]
        for page in range(1,369):
            words=[dict(text="operand",rect=[10.0,20.0,45.0,30.0])]+copy.deepcopy(policy["markingWords"][side])
            if page==29:words += [copy.deepcopy(m[side]) for m in policy["layoutChanges"]["moves"]]
            pages.append(dict(pdfPage=page,size=[612.0,792.0],wordCount=len(words),cells=[dict(wordBoxes=words)]))
        result[side]=pages
    return result,policy


class SourceAdoptionControls(unittest.TestCase):
    def test_reviewed_policy_selects_five_exact_editions_and_keeps_later_stage_boundaries(self):
        policy=source.entry.read(source.INPUT);source.reviewed_policy(policy)
        self.assertEqual([d["volume"] for d in policy["selectedDocuments"]],[1,2,3,4,5])
        self.assertEqual([d["revision"] for d in policy["selectedDocuments"]],["3.25","3.45","3.38","3.27","3.16"])
        self.assertIn("required-clause",policy["stageBoundary"]["P2"])
        self.assertNotIn("p1Complete",policy)

    def test_resealed_authority_scope_and_acceptance_flag_changes_are_rejected(self):
        for attack in ("source","scope","decision","kind","omission","marking","layout","P2","adoption"):
            value=copy.deepcopy(source.entry.read(source.INPUT))
            if attack=="source":value["selectedDocuments"][3]["pdfSha256"]="0"*64
            elif attack=="scope":value["scopeSha256"]="0"*64
            elif attack=="decision":value["decision"]="adopt-everything"
            elif attack=="kind":value["corpusVersion"]=True
            elif attack=="omission":value["selectedDocuments"].pop()
            elif attack=="marking":value["markingWords"]["new"][0]["text"]="[Public"
            elif attack=="layout":value["layoutChanges"]["moves"][0]["new"]["text"]="Elsevier"
            elif attack=="P2":value["stageBoundary"]["P2"]="complete"
            else:value["constraintsParsed"]=True
            with self.subTest(attack=attack),self.assertRaises(ValueError):source.reviewed_policy(value)

    def test_exact_markings_and_reviewed_word_relocations_are_accounted_on_all_pages(self):
        pages,policy=variant_pages();before=copy.deepcopy(pages)
        result=source.compare_volume5(pages["old"],pages["new"],policy["markingWords"],policy["layoutChanges"])
        self.assertEqual(pages,before)
        self.assertEqual(len(result["pages"]),368)
        self.assertEqual(result["pages"][28]["nonMarkingWords"],5)
        self.assertEqual(result["originalMarking"],"[AMD Public Use]")
        self.assertEqual(result["selectedMarking"],"[AMD Confidential - Distribution with NDA]")

    def test_changed_instruction_word_geometry_multiplicity_and_page_accounting_fail(self):
        for attack in ("body-word","body-position","body-duplicate","page-omit","page-order","page-size","word-count"):
            pages,policy=variant_pages();page=pages["new"][99];words=page["cells"][0]["wordBoxes"]
            if attack=="body-word":words[0]["text"]="different-operand"
            elif attack=="body-position":words[0]["rect"][0]+=1
            elif attack=="body-duplicate":words.append(copy.deepcopy(words[0]));page["wordCount"]+=1
            elif attack=="page-omit":pages["new"].pop()
            elif attack=="page-order":pages["new"][0],pages["new"][1]=pages["new"][1],pages["new"][0]
            elif attack=="page-size":page["size"][0]+=1
            else:page["wordCount"]+=1
            with self.subTest(attack=attack),self.assertRaises(ValueError):
                source.compare_volume5(pages["old"],pages["new"],policy["markingWords"],policy["layoutChanges"])

    def test_markings_cannot_be_erased_moved_or_broadly_filtered_as_footer_text(self):
        for attack in ("omit","move","duplicate","other-footer-word"):
            pages,policy=variant_pages();page=pages["new"][40];words=page["cells"][0]["wordBoxes"]
            if attack=="omit":words.pop(1);page["wordCount"]-=1
            elif attack=="move":words[1]["rect"][0]+=1
            elif attack=="duplicate":words.append(copy.deepcopy(words[1]));page["wordCount"]+=1
            else:words.append(dict(text="additional-source-note",rect=[10,750,90,760]));page["wordCount"]+=1
            with self.subTest(attack=attack),self.assertRaises(ValueError):
                source.compare_volume5(pages["old"],pages["new"],policy["markingWords"],policy["layoutChanges"])

    def test_bibliography_relocations_are_exact_and_cannot_correct_text(self):
        for attack in ("word","position","duplicate","foreign-page"):
            pages,policy=variant_pages();page=pages["new"][28];words=page["cells"][0]["wordBoxes"]
            if attack=="word":words[-1]["text"]="1997."
            elif attack=="position":words[-1]["rect"][0]+=.01
            elif attack=="duplicate":words.append(copy.deepcopy(words[-1]));page["wordCount"]+=1
            else:
                p=pages["new"][30];p["cells"][0]["wordBoxes"][0]["rect"][0]+=.0036
            with self.subTest(attack=attack),self.assertRaises(ValueError):
                source.compare_volume5(pages["old"],pages["new"],policy["markingWords"],policy["layoutChanges"])

    def test_predecessor_source_input_drift_cannot_be_resealed(self):
        with patch.object(source.entry.migration,"sha",return_value="0"*64),self.assertRaisesRegex(ValueError,"input drift"):
            source.reviewed_policy(source.entry.read(source.INPUT))

    def test_missing_outputs_and_maintained_run_products_cannot_qualify_source(self):
        with self.assertRaisesRegex(ValueError,"test output must"):
            source.reconstruct(Path("old"),Path("publisher"),source.INPUT.parent/"output")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError,"missing"):
                source.check(Path("old"),Path("publisher"),Path(tmp)/"missing")
            with patch.object(source.entry,"reconstruct",side_effect=ValueError("source reproduction failed")):
                with self.assertRaisesRegex(ValueError,"source reproduction failed"):
                    source.reconstruct(Path("old"),Path("publisher"),Path(tmp)/"fresh")
            self.assertFalse((Path(tmp)/"fresh/source-adoption.json").exists())


if __name__=="__main__":unittest.main()
