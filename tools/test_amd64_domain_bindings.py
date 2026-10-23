"""Actual MOV8 inputs and hostile finite-domain/provenance controls."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import amd64_domain_bindings as binding
import amd64_domains as domains

FIXTURES = binding.ROOT / "tests/bap/fixtures/amd64-semantics/mov8-domain"


class FiniteBindingControls(unittest.TestCase):
    def setUp(self):
        self.domain = binding.read(FIXTURES / "legal-domain.json")
        self.constraints = binding.read(FIXTURES / "source-constraints.json")
        self.bindings = binding.read(FIXTURES / "profile-bindings.json")
        # Algorithm tests reseal their own copies. Maintained bindings still
        # require a separate source-frozen actual producer/Rust campaign.
        self.bindings.update(domainSha256=binding.digest(self.domain),
                             constraintsSha256=binding.digest(self.constraints),
                             implementationSources=binding.sources())
        self.samples = binding.read(FIXTURES / "producer-samples.json")["cases"]

    def check_inputs(self):
        # Actual anchor replay is exercised by the owning constraint tests and
        # fresh CLI campaign. This unit control isolates binding partition logic.
        with mock.patch("amd64_source_constraints.validate_pack", return_value={}):
            return binding.validate_inputs(self.domain, self.constraints, self.bindings, "pdf", "bbox")

    def test_all_reviewed_points_accounted_without_claiming_whole_candidates(self):
        points, states = self.check_inputs()
        self.assertEqual(len(points), 640)
        self.assertEqual(set(states.values()), {"S"})
        self.assertEqual({point["form"] for point in points}, set(domains.MOV8_FORMS))

    def test_missing_overlapping_foreign_or_narrowed_partitions_fail(self):
        initial = copy.deepcopy(self.bindings)
        for attack in ("missing", "overlap", "foreign", "narrowed", "wrong-form"):
            self.bindings = copy.deepcopy(initial)
            part = self.bindings["partitions"][0]
            if attack == "missing":
                self.bindings["partitions"].pop()
            elif attack == "overlap":
                self.bindings["partitions"].append(dict(part, id="overlap"))
            elif attack == "foreign":
                part["bytes"] = ["90"]
            elif attack == "narrowed":
                part["bytes"] = ["88c0"]
            else:
                part["form"] = "invented"
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                self.check_inputs()

    def test_unsupported_partitions_do_not_become_supported(self):
        self.bindings["partitions"][0]["disposition"] = "U"
        _, states = self.check_inputs()
        self.assertEqual(sum(value == "U" for value in states.values()), 320)
        self.assertEqual(sum(value == "S" for value in states.values()), 320)

    def test_stale_sources_or_unreviewed_consumer_are_refused(self):
        for key, value in (("profile", "bap-bit-provenance-v15"), ("consumer", "guard-admission"),
                           ("contract", "generic-opcode-fallback"), ("implementationSources", {}),
                           ("requiredTargets", ["windows-amd64"])):
            saved = self.bindings[key]
            self.bindings[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.check_inputs()
            self.bindings[key] = saved

    def test_actual_numeric_inputs_preserve_every_other_byte_and_flags(self):
        self.assertEqual(len(self.samples), 6)
        for sample in self.samples:
            self.assertEqual(binding.check_numeric(sample["bytes"], sample["bil"]), 8)

    def test_high_byte_rex_and_direction_cannot_share_one_semantic_observation(self):
        samples = {sample["bytes"]: sample for sample in self.samples}
        for actual, wrong in (("88e0", "4088e0"), ("8ae0", "88e0"), ("4588c1", "458ac1")):
            with self.subTest(actual=actual, wrong=wrong), self.assertRaises(ValueError):
                binding.check_numeric(actual, samples[wrong]["bil"])
        self.assertEqual(binding.operands("88e0"), ((0, 0), (0, 1)))
        self.assertEqual(binding.operands("4088e0"), ((0, 0), (4, 0)))
        self.assertEqual(binding.operands("4588c1"), ((9, 0), (8, 0)))

    def test_unmodeled_prefix_and_consumed_extent_are_not_in_the_pilot(self):
        for encoded in ("4888c0", "6688c0", "404088c0", "88c090", "8880", "88", "90", "88C0", "88 c0"):
            with self.subTest(encoded=encoded), self.assertRaises(ValueError):
                binding.operands(encoded)

    def test_reference_binds_operands_control_extent_and_address(self):
        sample = next(row for row in self.samples if row["bytes"] == "4088e0")
        fields = sample["reference"].split()
        va = int(fields[-5])
        self.assertEqual(binding.validate_reference_row(sample["reference"], sample["bytes"], va), "MOV8rr")
        for index, wrong in ((3, "r:AH"), (4, "r:AH"), (-5, str(va + 1)), (-3, "2"), (-2, "jump"), (5, "0")):
            altered = fields.copy()
            altered[index] = wrong
            with self.subTest(index=index), self.assertRaises(ValueError):
                binding.validate_reference_row(" ".join(altered), sample["bytes"], va)

    def test_changed_reference_artifacts_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            helper, library = Path(temp) / "helper", Path(temp) / "library"
            helper.write_bytes(b"test reference")
            library.write_bytes(b"test library")
            record = dict(helperPath=str(helper), helperSha256=binding.legacy.sha(helper),
                          libraryPath=str(library), librarySha256=binding.legacy.sha(library),
                          version=self.bindings["referencePin"]["version"])
            pins = {key: record[key] for key in ("helperSha256", "librarySha256", "version")}
            binding.validate_reference(record, {"referencePin": pins})
            library.write_bytes(b"changed library")
            with self.assertRaisesRegex(ValueError, "stale reference"):
                binding.validate_reference(record, {"referencePin": pins})

    def test_producer_batch_frames_bind_typed_ids_counts_and_complete_sequence(self):
        ready = dict(schema="ariadne.bap-ready/v1", snapshot="snapshot", target="windows-amd64",
                     version="2.5.0-alpha", lifter="legacy")
        points = [{"index": index} for index in range(640)]
        frames = [ready]
        for batch, start in enumerate(range(0, len(points), 256)):
            block = points[start:start + 256]
            frames.extend(block)
            frames.append(dict(schema="ariadne.bap-batch/v1", batch=batch, count=len(block)))
        self.assertEqual(binding.producer_rows(frames, "windows-amd64", "snapshot", 640), points)
        for attack in ("bool-batch", "float-batch", "float-count", "wrong-count", "wrong-target",
                       "wrong-snapshot", "missing-boundary", "missing-row", "extra-frame"):
            altered = copy.deepcopy(frames)
            if attack == "bool-batch":
                altered[257]["batch"] = False
            elif attack == "float-batch":
                altered[257]["batch"] = 0.0
            elif attack == "float-count":
                altered[257]["count"] = 256.0
            elif attack == "wrong-count":
                altered[257]["count"] = 255
            elif attack == "wrong-target":
                altered[0]["target"] = "linux-amd64"
            elif attack == "wrong-snapshot":
                altered[0]["snapshot"] = "substituted"
            elif attack == "missing-boundary":
                altered.pop()
            elif attack == "missing-row":
                altered.pop(1)
            else:
                altered.append(copy.deepcopy(altered[-1]))
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                binding.producer_rows(altered, "windows-amd64", "snapshot", 640)

    def test_partial_or_duplicate_actual_inputs_cannot_supply_complete_observations(self):
        points, classified = self.check_inputs()
        index = {point["bytes"]: (i, point) for i, point in enumerate(points)}
        observations = dict(schema="ariadne.amd64-finite-observations/v4",
                            domainSha256=binding.digest(self.domain), constraintsSha256=binding.digest(self.constraints),
                            bindingsSha256=binding.digest(self.bindings), implementationSources=binding.sources(),
                            sourceEvidence={"pdfSha256": "0" * 64, "bboxSha256": "0" * 64},
                            producer={}, reference={}, rows=[], rustObserver=None)
        for sample in self.samples:
            i, point = index[sample["bytes"]]
            va = 0x401000 + i * 32
            snapshot = binding.digest({"domain": binding.digest(self.domain), "bindings": binding.digest(self.bindings),
                                       "target": "windows-amd64"})
            response = dict(schema="ariadne.bap-site/v1", batch=i // 256, snapshot=snapshot,
                            va=f"0x{va:016x}", status="decoded", length=len(point["bytes"]) // 2,
                            bytes=point["bytes"], opcode=sample["opcode"], bil=sample["bil"],
                            properties={key: False for key in ("jump", "conditional", "indirect", "call", "return", "control")})
            reference = sample["reference"].split()
            reference[-5] = str(va)
            observations["rows"].append(dict(target="windows-amd64", point=point, response=response,
                reference=" ".join(reference), astSha256=binding.digest(sample["bil"]), numericCases=8))
        # Only the external artifact prerequisites are mocked. Exact requests,
        # numeric semantics and complete domain observation accounting execute.
        with mock.patch.object(binding, "validate_inputs", return_value=(points, classified)), \
                mock.patch.object(binding, "validate_producer"), mock.patch.object(binding, "validate_reference"), \
                mock.patch.object(binding.legacy, "sha", return_value="0" * 64):
            observations["implementationSources"] = binding.sources()
            attacks = {"partial": "missing supported observations",
                       "duplicate": "omitted, duplicate or wrong domain observation",
                       "snapshot": "producer request/extent identity",
                       "bool-batch": "producer request/extent identity",
                       "wrong-byte": "producer request/extent identity",
                       "false-flags": "register MOV control/memory properties"}
            for attack, expected_error in attacks.items():
                altered = copy.deepcopy(observations)
                if attack == "duplicate":
                    altered["rows"].append(copy.deepcopy(altered["rows"][0]))
                elif attack == "snapshot":
                    altered["rows"][0]["response"]["snapshot"] = "1" * 64
                elif attack == "bool-batch":
                    altered["rows"][0]["response"]["batch"] = False
                elif attack == "wrong-byte":
                    altered["rows"][0]["response"]["bytes"] = "90"
                elif attack == "false-flags":
                    altered["rows"][0]["response"]["properties"]["jump"] = 0
                with self.subTest(attack=attack), self.assertRaisesRegex(ValueError, expected_error):
                    binding.validate_observations(altered, self.domain, self.constraints, self.bindings,
                                                  "pdf", "bbox", require_rust=False)


if __name__ == "__main__":
    unittest.main()
