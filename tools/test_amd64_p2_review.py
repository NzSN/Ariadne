"""P2 source population, reference ownership and current-disposition controls."""
import copy
import unittest

import amd64_p2_review as r


class ReviewControls(unittest.TestCase):
    def setUp(self):
        self.doc = dict(publication="test", pdfSha256="a"*64)
        self.page = dict(pdfPage=1, size=[612,792], wordCount=2, cells=[
            dict(id="pdf:1:cell:0", pdfPage=1, text="AMD64 Technology", rect=[50,50,160,65], wordBoxes=[dict(text="AMD64 Technology",rect=[50,50,160,65])]),
            dict(id="pdf:1:cell:1", pdfPage=1, text="64-bit result", rect=[50,150,180,165], wordBoxes=[dict(text="64-bit result",rect=[50,150,180,165])])])
        self.key = r.cell_key(self.doc["pdfSha256"], "pdf:1:cell:1")
        self.clauses = {"width": dict(sourceCells={self.key}, issues=[])}
        self.decision = dict(**self.doc, pdfPage=1, sourceCellsSha256=r.digest(self.page["cells"]), inventory=["width"], roles=[
            dict(cells=["pdf:1:cell:0"], role="furniture", targets=[]), dict(cells=["pdf:1:cell:1"], role="clause", targets=["width"])])

    def validate(self, decision=None, **kwargs):
        return r.validate_page(decision or self.decision, kwargs.pop("page",self.page), self.doc,
                               kwargs.pop("clauses",self.clauses), kwargs.pop("contexts",{}),
                               kwargs.pop("references",{}), kwargs.pop("issues",{}))

    def test_complete_review_can_close_a_page_and_its_section(self):
        page = self.validate()
        self.assertEqual(page["state"], "reviewed-all-required-clauses")
        record = dict(**self.doc, pdfPage=1, sourceCellsSha256=r.digest(self.page["cells"]), state="required-whole-region-clause-review")
        regions = r.apply_reviews([record], [self.decision], {(self.doc["pdfSha256"],1):self.page}, {"test":self.doc}, self.clauses, {}, {}, {})
        self.assertEqual(r.section_state(self.doc["pdfSha256"],1,1,regions),
                         dict(state="reviewed-all-required-clauses", constraintsParsed=True, reviewedPages=1, requiredPages=1))
        self.assertEqual(record["state"],"required-whole-region-clause-review")

    def test_unreviewed_or_missing_pages_cannot_close_a_section(self):
        record = dict(**self.doc,pdfPage=1,sourceCellsSha256=r.digest(self.page["cells"]),state="required-whole-region-clause-review")
        regions=r.apply_reviews([record],[],{}, {"test":self.doc},self.clauses,{},{},{})
        self.assertFalse(r.section_state(self.doc["pdfSha256"],1,1,regions)["constraintsParsed"])
        with self.assertRaisesRegex(ValueError,"missing/duplicate"):
            r.section_state(self.doc["pdfSha256"],1,2,regions)

    def test_omitted_note_duplicate_role_stale_owner_and_saved_flags_fail(self):
        for attack in ("omitted", "duplicate", "owner", "hash", "unknown", "flag", "unused"):
            decision=copy.deepcopy(self.decision)
            if attack=="omitted":decision["roles"].pop()
            elif attack=="duplicate":decision["roles"].append(copy.deepcopy(decision["roles"][0]))
            elif attack=="owner":decision["publication"]="foreign"
            elif attack=="hash":decision["sourceCellsSha256"]="0"*64
            elif attack=="unknown":decision["roles"][1]["role"]="harmless-unknown"
            elif attack=="unused":decision["inventory"]=["not-reviewed"]
            else:decision["complete"]=True
            with self.subTest(attack=attack),self.assertRaises(ValueError):self.validate(decision)

    def test_context_is_independently_owned_and_cannot_hide_unknown_source(self):
        decision=copy.deepcopy(self.decision);decision["inventory"]=[]
        decision["roles"][1].update(role="context",targets=[self.key])
        with self.assertRaisesRegex(ValueError,"independently reviewed"):self.validate(decision)
        actual=self.validate(decision,contexts={self.key:dict(kind="reviewed-heading")})
        self.assertEqual(actual["state"],"reviewed-all-required-clauses")

    def test_normative_prose_cannot_be_reclassified_as_running_furniture(self):
        decision=copy.deepcopy(self.decision);decision["inventory"]=[]
        decision["roles"][1].update(role="furniture",targets=[])
        with self.assertRaisesRegex(ValueError,"normative source"):self.validate(decision)

    def test_foreign_clause_and_piggybacked_targets_fail(self):
        for cells in ({"foreign"},{self.key}):
            clauses=dict(self.clauses, other=dict(sourceCells=cells,issues=[]))
            decision=copy.deepcopy(self.decision);decision["inventory"].append("other")
            decision["roles"][1]["targets"]=["other"] if cells=={"foreign"} else ["width"]
            with self.assertRaises(ValueError):self.validate(decision,clauses=clauses)
        clauses=dict(self.clauses, other=dict(sourceCells={"foreign"},issues=[]))
        decision=copy.deepcopy(self.decision);decision["inventory"].append("other");decision["roles"][1]["targets"].append("other")
        with self.assertRaisesRegex(ValueError,"no owned evidence"):self.validate(decision,clauses=clauses)

    def test_references_have_actual_source_owners_and_preserve_target_conflicts(self):
        decision=copy.deepcopy(self.decision);decision["inventory"]=[]
        decision["roles"][1].update(role="reference",targets=["diagram"])
        refs={"diagram":dict(sourceCells=[self.key],targetCells=["target"],issues=["conflict"])}
        actual=self.validate(decision,references=refs,issues={"conflict":dict(state="unresolved")})
        self.assertEqual(actual["state"],"reviewed-source-with-open-dependencies")
        self.assertEqual(actual["pendingIssues"],["conflict"])
        refs["diagram"]["sourceCells"]=["foreign"]
        with self.assertRaisesRegex(ValueError,"reference ownership"):self.validate(decision,references=refs,issues={"conflict":dict(state="unresolved")})

    def test_unknown_dependency_cannot_disappear(self):
        clauses={"width":dict(sourceCells={self.key},issues=["missing"])}
        with self.assertRaisesRegex(ValueError,"no owner"):self.validate(clauses=clauses)
        value=self.validate(clauses=clauses,issues={"missing":dict(state="unresolved")})
        self.assertEqual(value["pendingIssues"],["missing"])

    def test_original_boundaries_survive_current_checked_resolution(self):
        old={"scope":dict(kind="unresolved-reference",meaning="old question")}
        decisions={"scope":dict(originalSha256=r.digest(old["scope"]),state="resolved-source-rule",rules=["width"],checks=["actual-source"],reason="Specific source rule now checked.")}
        recipes={"scope":dict(rules=["width"],checks=["actual-source"])}
        value=r.reconcile(old,decisions,self.clauses,{"actual-source":True},recipes)
        self.assertEqual(value[0]["original"],old["scope"])
        self.assertEqual(value[0]["state"],"resolved-source-rule")
        self.assertEqual(old["scope"]["kind"],"unresolved-reference")
        for attack in ("lost", "wrong-id", "flag", "failed-check", "missing-check"):
            bad=copy.deepcopy(decisions);checks={"actual-source":True}
            if attack=="lost":bad={}
            elif attack=="wrong-id":bad["scope"]["originalSha256"]="0"*64
            elif attack=="flag":bad["scope"]["complete"]=True
            elif attack=="failed-check":checks["actual-source"]=False
            else:bad["scope"]["checks"]=[]
            with self.subTest(attack=attack),self.assertRaises(ValueError):r.reconcile(old,bad,self.clauses,checks,recipes)
        with self.assertRaisesRegex(ValueError,"source-proof recipe"):
            r.reconcile(old,decisions,self.clauses,{"actual-source":True},{})

    def test_execution_mode_exclusion_is_not_a_semantic_correction(self):
        old={'non64-row':dict(kind='source-conflict',literal='6E')}
        decision=dict(originalSha256=r.digest(old['non64-row']),state='excluded-selected-execution-mode',
                      rules=['width'],checks=['mode-proof'],reason='Explicit non-64-only row; native-64 target.')
        recipes={'non64-row':dict(state='excluded-selected-execution-mode',rules=['width'],checks=['mode-proof'])}
        value=r.reconcile(old,{'non64-row':decision},self.clauses,{'mode-proof':True},recipes)
        self.assertEqual(value[0]['original']['literal'],'6E')
        self.assertEqual(value[0]['state'],'excluded-selected-execution-mode')
        bad=copy.deepcopy(decision);bad['state']='resolved-source-rule'
        with self.assertRaisesRegex(ValueError,'source-proof recipe'):
            r.reconcile(old,{'non64-row':bad},self.clauses,{'mode-proof':True},recipes)
        with self.assertRaisesRegex(ValueError,'executed source check'):
            r.reconcile(old,{'non64-row':decision},self.clauses,{'mode-proof':False},recipes)


if __name__=="__main__":unittest.main()
