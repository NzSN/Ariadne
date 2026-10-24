"""Finite memory source/domain relations, address witnesses and refusal controls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import amd64_domain_bindings as register
import amd64_domains as domain
import amd64_memory_bindings as memory
import amd64_reconciliation as reconciliation

FIXTURES = domain.ROOT / "tests/bap/fixtures/amd64-semantics/mov8-memory-domain"


class MemoryBindingControls(unittest.TestCase):
    def setUp(self):
        self.document = domain.read(FIXTURES / "legal-domain.json")
        self.constraints = domain.read(domain.ROOT / domain.ARCHITECTURE_PACK_PATH)
        self.bindings = domain.read(FIXTURES / "profile-bindings.json")
        # Source identities in unit copies do not qualify maintained registries.
        self.bindings["implementationSources"] = memory.sources()
        self.samples = domain.read(FIXTURES / "producer-samples.json")["cases"]

    def inputs(self):
        with mock.patch("amd64_source_constraints.validate_pack"), \
                mock.patch("amd64_source_constraints.validate_architecture_pack"):
            return memory.validate_inputs(self.document, self.constraints, self.bindings, "pdf", "bbox")

    def test_actual_source_bound_domain_and_explicit_address32_refusal(self):
        points = self.inputs()
        self.assertEqual(len(points), 5760)
        self.assertEqual(sum(p["environment"]["addressBits"] == 64 for p in points), 2880)
        self.assertEqual([p["disposition"] for p in self.bindings["partitions"]], ["U", "S", "U", "S"])

    def test_narrowed_domain_or_source_derivation_does_not_close_membership(self):
        for attack in ("source", "rule", "grammar", "environment"):
            document = copy.deepcopy(self.document)
            if attack == "source":
                document["sourcePacks"][1]["sha256"] = "0" * 64
            elif attack == "rule":
                document["forms"][0]["sourceRules"].remove("address-size-truncation")
            elif attack == "grammar":
                document["forms"][0]["alternatives"][0]["sequence"][-1]["sib"]["base"] = [0]
            else:
                document["scope"]["environmentAxes"]["addressBits"] = [64]
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                domain.validate_memory_mov8_domain(document)

    def test_every_memory_form_requires_the_reviewed_prefix_and_length_rules(self):
        required = {"prefix-group-order", "legacy-prefix-byte-groups", "rex-placement-count",
                    "instruction-length-limit", "operand-size-override"}
        clauses = {clause["id"] for clause in self.constraints["clauses"]}
        self.assertTrue(required <= clauses)
        points = domain.validate_memory_mov8_domain(self.document)
        self.assertEqual(len(points), 5760)
        self.assertEqual(sum(point["environment"]["addressBits"] == 64 for point in points), 2880)
        for index, form in enumerate(self.document["forms"]):
            self.assertTrue(required <= set(form["sourceRules"]))
            for rule in sorted(required):
                item = copy.deepcopy(self.document)
                item["forms"][index]["sourceRules"].remove(rule)
                with self.subTest(form=form["id"], missing=rule), self.assertRaisesRegex(
                        ValueError, "memory MOV8 source derivation differs"):
                    domain.validate_memory_mov8_domain(item)

    def test_partition_holes_overlap_types_and_unreviewed_admission_fail(self):
        baseline = copy.deepcopy(self.bindings)
        for attack in ("hole", "overlap", "boolean", "admit32", "native", "stale"):
            self.bindings = copy.deepcopy(baseline)
            if attack == "hole":
                self.bindings["partitions"].pop()
            elif attack == "overlap":
                self.bindings["partitions"].append(copy.deepcopy(self.bindings["partitions"][0]))
            elif attack == "boolean":
                self.bindings["partitions"][0]["addressBits"] = True
            elif attack == "admit32":
                self.bindings["partitions"][0]["disposition"] = "S"
            elif attack == "native":
                self.bindings["consumer"] = "native-captured-analysis"
            else:
                self.bindings["implementationSources"] = {}
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                self.inputs()

    def test_actual_numeric_source_inputs_preserve_successes_and_counterexamples(self):
        for sample in self.samples:
            va = int(sample["va"], 16)
            result = memory.numeric_observation(sample["bytes"], sample["bil"], va)
            address32 = sample["bytes"].startswith("67")
            self.assertEqual(result["matched"], not address32, sample["bytes"])
            if address32:
                self.assertEqual(result["witness"]["reason"], "memory-address-disagreement")
                self.assertNotEqual(result["witness"]["expectedAddress"], result["witness"]["accesses"][0][1])
            else:
                self.assertEqual(result["cases"], 8)

    def test_reference_binds_rip_eip_register_views_displacement_and_va(self):
        for sample in self.samples:
            memory.validate_reference_row(sample["reference"], sample["bytes"], int(sample["va"], 16))
        sample = next(row for row in self.samples if row["bytes"] == "678a0500000000")
        for before, after in (("r:EIP", "r:RIP"), ("i:0", "i:1"), ("MOV8rm", "MOV8mr")):
            with self.subTest(before=before), self.assertRaises(ValueError):
                memory.validate_reference_row(sample["reference"].replace(before, after), sample["bytes"], int(sample["va"], 16))
        with self.assertRaises(ValueError):
            memory.validate_reference_row(sample["reference"], sample["bytes"], int(sample["va"], 16) + 1)

    def test_memory_relations_leave_all_whole_candidate_obligations_open(self):
        relations = domain.read(FIXTURES / "template-relations.json")
        xed = domain.read(FIXTURES / "xed-records.json")
        points = domain.validate_memory_mov8_domain(self.document)
        result = reconciliation.reconciliation_report(self.document, points, relations, xed)
        self.assertEqual(result["counts"]["finitePoints"], 5760)
        self.assertEqual(result["counts"]["partialCandidateRelations"], 2)
        self.assertEqual(result["counts"]["candidateFullDomainBindings"], 0)
        self.assertFalse(result["fullDomainReconciliation"])
        changed = copy.deepcopy(relations)
        changed["relations"][0]["completeTemplateDomain"] = True
        with self.assertRaises(ValueError):
            reconciliation.reconciliation_report(self.document, points, changed, xed)
        with self.assertRaises(ValueError):
            reconciliation.reconcile(self.document, relations, xed)

    def test_partial_rows_and_forged_numeric_or_query_identity_fail_at_own_checks(self):
        points = self.inputs()
        lookup = {point["bytes"]: (index, point) for index, point in enumerate(points)}
        with tempfile.TemporaryDirectory() as directory:
            pdf, bbox = Path(directory) / "pdf", Path(directory) / "bbox"
            pdf.write_bytes(b"unit PDF identity"); bbox.write_bytes(b"unit bbox identity")
            observations = dict(schema="ariadne.amd64-memory-observations/v1", domainSha256=domain.digest(self.document),
                bindingsSha256=domain.digest(self.bindings), sourcePacksSha256=domain.digest(self.document["sourcePacks"]),
                implementationSources=memory.sources(), sourceEvidence={"pdfSha256": domain.sha(pdf), "bboxSha256": domain.sha(bbox)},
                producer={}, reference={}, rows=[], rustObserver=None)
            for sample in self.samples:
                index, point = lookup[sample["bytes"]]
                va = memory.QUERY_BASE + index * 32
                self.assertEqual(int(sample["va"], 16), va)
                snapshot = domain.digest(dict(domain=domain.digest(self.document), bindings=domain.digest(self.bindings), target="windows-amd64"))
                response = dict(schema="ariadne.bap-site/v1", batch=index // 256, snapshot=snapshot, va=f"0x{va:016x}",
                    bytes=sample["bytes"], opcode=sample["opcode"], status="decoded", length=len(sample["bytes"]) // 2,
                    properties={key: False for key in ("jump", "conditional", "indirect", "call", "return", "control")}, bil=sample["bil"])
                observations["rows"].append(dict(target="windows-amd64", point=point, response=response, reference=sample["reference"],
                    astSha256=domain.digest(sample["bil"]), numeric=memory.numeric_observation(sample["bytes"], sample["bil"], va),
                    disposition="U" if point["environment"]["addressBits"] == 32 else "S"))
            with mock.patch.object(memory, "validate_inputs", return_value=points), \
                    mock.patch.object(register, "validate_producer"), mock.patch.object(register, "validate_reference"):
                for attack, reason in [("partial", "missing memory observations"), ("duplicate", "omission/duplicate/substitution"),
                    ("snapshot", "query/extent identity"), ("float-length", "query/extent identity"),
                    ("numeric", "numeric observation differs"), ("admit32", "prefix disposition differs")]:
                    changed = copy.deepcopy(observations)
                    row = changed["rows"][0]
                    if attack == "duplicate": changed["rows"].append(copy.deepcopy(row))
                    elif attack == "snapshot": row["response"]["snapshot"] = "0" * 64
                    elif attack == "float-length": row["response"]["length"] = float(row["response"]["length"])
                    elif attack == "numeric": row["numeric"]["cases"] = 0
                    elif attack == "admit32": changed["rows"][-1]["disposition"] = "S"
                    with self.subTest(attack=attack), self.assertRaisesRegex(ValueError, reason):
                        memory.validate_observations(changed, self.document, self.constraints, self.bindings, pdf, bbox, require_rust=False)


if __name__ == "__main__":
    unittest.main()
