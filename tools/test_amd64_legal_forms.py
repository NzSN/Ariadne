#!/usr/bin/env python3
"""Portable omission, partition and hostile-provenance controls for the v2 pilot."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import amd64_legal_forms as legal

FIXTURES = legal.ROOT / "tests/bap/fixtures/amd64-semantics"


class LegalDomains(unittest.TestCase):
    def setUp(self):
        self.forms = legal.read(FIXTURES / "legal-forms-pilot-v2.json")
        self.bindings = legal.read(FIXTURES / "profile-bindings-pilot-v2.json")
        # Algorithm controls must be runnable while parallel implementation work
        # changes source. The real CLI gate separately checks the frozen fixture.
        self.bindings["implementationSources"] = legal.current_sources()
        self.rebind()

    def rebind(self):
        self.bindings["legalFormsSha256"] = legal.digest(self.forms)

    def check(self):
        return legal.assess(self.forms, self.bindings)

    def test_complete_accounting_is_not_implementation_or_vendor_coverage(self):
        report = self.check()
        self.assertTrue(report["totalDisposition"])
        self.assertEqual(report["enumeratedPoints"], 24)
        self.assertEqual(sum(row["supported"] for row in report["forms"]), 3)
        self.assertEqual(sum(row["unsupported"] for row in report["forms"]), 21)
        self.assertFalse(report["implementationComplete"])
        self.assertFalse(report["currentObservationsValidated"])
        self.assertFalse(report["profileBindingsValidated"])
        self.assertFalse(report["sourceComplete"])
        self.assertFalse(report["vendorFullDenominator"])
        self.assertFalse(report["fullAmd64Coverage"])

    def test_all_width_and_address_points_are_enumerated(self):
        _, domains = legal.validate_legal(self.forms)
        self.assertEqual({point[0] for point in domains["amd-canonical-f3-movs"]},
                         {"f367a4", "f3a4", "f36766a5", "f366a5", "f367a5", "f3a5", "f36748a5", "f348a5"})
        for byte_string, environment in domains["amd-canonical-f3-movs"]:
            self.assertEqual(dict(environment)["addressBits"], 32 if "67" in byte_string else 64)

    def test_unsupported_and_unresolved_are_different_from_holes(self):
        self.bindings["partitions"][1]["disposition"] = "X"
        report = self.check()
        self.assertTrue(report["totalDisposition"])
        self.assertEqual(sum(row["unresolved"] for row in report["forms"]), 7)
        self.assertFalse(report["implementationDomainComplete"])
        self.bindings["partitions"][1]["grammar"]["alternatives"].pop()
        report = self.check()
        self.assertFalse(report["totalDisposition"])
        self.assertEqual(sum(row["holes"] for row in report["forms"]), 1)
        self.assertIsNotNone(next(row["firstHole"] for row in report["forms"] if row["holes"]))

    def test_overlapping_partitions_reject_even_same_disposition(self):
        extra = copy.deepcopy(self.bindings["partitions"][1])
        extra["id"] += "-duplicate"
        self.bindings["partitions"].append(extra)
        with self.assertRaisesRegex(ValueError, "overlapping S/U/X"):
            self.check()

    def test_binding_must_be_subset_of_legal_domain(self):
        self.bindings["partitions"][0]["grammar"]["alternatives"][0]["opcode"] = "90"
        with self.assertRaisesRegex(ValueError, "outside referenced legal form"):
            self.check()

    def test_legal_omission_is_not_repaired_by_corresponding_binding_omission(self):
        self.forms["forms"][0]["grammar"]["alternatives"].pop()
        self.bindings["partitions"][1]["grammar"]["alternatives"].pop()
        self.rebind()
        with self.assertRaisesRegex(ValueError, "independent reviewed derivation"):
            self.check()

    def test_illegal_prefix_width_or_opcode_cannot_be_hashed_into_authority(self):
        for change in ("prefix", "width", "opcode"):
            with self.subTest(change=change):
                original = copy.deepcopy(self.forms)
                alternative = self.forms["forms"][0]["grammar"]["alternatives"][0]
                if change == "prefix":
                    alternative["prefixes"][0] = "f2"
                elif change == "width":
                    alternative["environment"]["operandBits"] = [64]
                else:
                    alternative["opcode"] = "90"
                self.rebind()
                with self.assertRaisesRegex(ValueError, "independent reviewed derivation"):
                    self.check()
                self.forms = original

    def test_exclusion_inside_domain_and_changed_scope_are_rejected(self):
        self.forms["scope"]["exclusions"].append(dict(id="hard-case", kind="point", reason="omit a byte point",
                                                     beforeDomainConstruction=False))
        self.rebind()
        with self.assertRaisesRegex(ValueError, "before D"):
            self.check()

    def test_candidate_and_authoritative_boolean_cannot_promote_v1(self):
        self.forms["schema"] = "ariadne.amd64-form-case-associations/v1"
        with self.assertRaisesRegex(ValueError, "v2 legal-form"):
            self.check()
        self.forms["schema"] = legal.LEGAL
        self.forms["authoritative"] = True
        with self.assertRaisesRegex(ValueError, "legal forms fields"):
            self.check()

    def test_duplicates_and_stale_provenance_reject(self):
        for key in ("forms", "sourcePins", "reviewedRules", "sourceCells"):
            with self.subTest(key=key):
                self.forms[key].append(copy.deepcopy(self.forms[key][0]))
                self.rebind()
                with self.assertRaisesRegex(ValueError, "duplicate"):
                    self.check()
                self.forms[key].pop()
        self.rebind()
        self.bindings["implementationSources"]["src/bap/repeated_strings.rs"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "stale implementation"):
            self.check()

    def test_stale_source_publication_and_orphan_source_address_reject(self):
        self.forms["sourcePins"][0]["pdfSha256"] = "0" * 64
        self.rebind()
        with self.assertRaisesRegex(ValueError, "PDF identity"):
            self.check()
        self.forms["sourcePins"][0]["pdfSha256"] = legal.PDF_SHA
        self.forms["reviewedRules"][0]["sourceCells"].append("pdf:999:cell:0")
        self.rebind()
        with self.assertRaisesRegex(ValueError, "source cells"):
            self.check()

    def test_unknown_grammar_does_not_receive_partial_success(self):
        self.forms["forms"][0]["grammar"]["regex"] = "f3.*"
        self.rebind()
        with self.assertRaisesRegex(ValueError, "grammar fields"):
            self.check()

    def test_finite_fields_have_exact_little_endian_cartesian_domain(self):
        grammar = {"alternatives": [dict(prefixes=["66"], opcode="b8", fields=[
            dict(name="imm16", width=2, values=[0, 255, 0x1234])],
            environment={"mode": [64], "addressBits": [64], "operandBits": [16]})]}
        points = legal.enumerate_grammar(grammar, self.forms["scope"]["environmentAxes"], legal.Budget(100))
        self.assertEqual({point[0] for point in points}, {"66b80000", "66b8ff00", "66b83412"})

    def test_more_than_fifteen_bytes_and_duplicate_alternatives_reject(self):
        grammar = {"alternatives": [dict(prefixes=["66"] * 15, opcode="90", fields=[], environment={})]}
        with self.assertRaisesRegex(ValueError, "15 consumed bytes"):
            legal.enumerate_grammar(grammar, self.forms["scope"]["environmentAxes"], legal.Budget(100))
        alternative = self.forms["forms"][0]["grammar"]["alternatives"][0]
        grammar = {"alternatives": [alternative, alternative]}
        with self.assertRaisesRegex(ValueError, "overlapping alternatives"):
            legal.enumerate_grammar(grammar, self.forms["scope"]["environmentAxes"], legal.Budget(100))

    def test_budget_unknown_does_not_claim_any_completion_gate(self):
        report = legal.assess(self.forms, self.bindings, budget=3)
        self.assertEqual(report["status"], "unknown")
        self.assertFalse(report["totalDisposition"])
        self.assertFalse(report["implementationComplete"])
        self.assertFalse(report["fullAmd64Coverage"])

    def test_query_consumed_bytes_not_stream_prefix_and_requested_profile_only(self):
        environment = dict(mode=64, addressBits=64, operandBits=8)
        valid = legal.query(self.bindings, self.forms, None, "f3a4", environment)
        self.assertEqual(valid["matches"][0]["disposition"], "S")
        self.assertFalse(valid["profileAdmissionValidated"])
        for encoded in ("f3a490", "f2a4", "66f3a4", "f367a4"):
            self.assertFalse(legal.query(self.bindings, self.forms, None, encoded, environment)["matches"])
        with patch.object(legal, "assess", return_value=dict(status="checked", profileBindingsValidated=True)):
            self.assertTrue(legal.query(self.bindings, self.forms, None, "f3a4", environment)["profileAdmissionValidated"])
            self.assertFalse(legal.query(self.bindings, self.forms, None, "f3a490", environment)["profileAdmissionValidated"])
            wide = dict(mode=64, addressBits=64, operandBits=16)
            self.assertFalse(legal.query(self.bindings, self.forms, None, "f366a5", wide)["profileAdmissionValidated"])
        with self.assertRaisesRegex(ValueError, "15 consumed bytes"):
            legal.query(self.bindings, self.forms, None, "90" * 16, environment)
        self.bindings["consumer"]["profile"] = "bap-bit-provenance-v13"
        with self.assertRaisesRegex(ValueError, "unknown consumer"):
            self.check()

    def test_feature_alias_guards_partition_entire_environment(self):
        axes = {"bmi1": [False, True]}
        domain = {legal.point_key("f30fbcc0", {"bmi1": feature}) for feature in (False, True)}
        forms = {"tzcnt": {"meaning": "tzcnt"}, "bsf": {"meaning": "bsf"}}
        rule = dict(left="tzcnt", right="bsf", kind="guarded-alias", rationale="Feature-dependent opcode meaning",
                    axis="bmi1", dispatch={"tzcnt": [True], "bsf": [False]})
        legal.validate_overlaps(forms, {name: domain for name in forms}, [rule], axes)
        for bad in ({"tzcnt": [True], "bsf": [True]}, {"tzcnt": [True, False], "bsf": [False]}):
            rule["dispatch"] = bad
            with self.assertRaisesRegex(ValueError, "partition the environment"):
                legal.validate_overlaps(forms, {name: domain for name in forms}, [rule], axes)
        with self.assertRaisesRegex(ValueError, "unresolved overlapping"):
            legal.validate_overlaps(forms, {name: domain for name in forms}, [], axes)

    def test_identical_alias_needs_equal_meaning(self):
        point = {legal.point_key("f3a4", {"mode": 64})}
        forms = {"a": {"meaning": "movs"}, "b": {"meaning": "movs"}}
        rule = dict(left="a", right="b", kind="identical-meaning", rationale="Reviewed synonym")
        legal.validate_overlaps(forms, {"a": point, "b": point}, [rule], {"mode": [64]})
        forms["b"]["meaning"] = "stos"
        with self.assertRaisesRegex(ValueError, "meanings differ"):
            legal.validate_overlaps(forms, {"a": point, "b": point}, [rule], {"mode": [64]})

    def fake_observations(self):
        snapshot = legal.digest({"legal": legal.digest(self.forms), "bindings": legal.digest(self.bindings)})
        result = dict(schema=legal.OBSERVATIONS, legalFormsSha256=legal.digest(self.forms),
                      bindingsSha256=legal.digest(self.bindings), sourceSha256=legal.current_sources(),
                      sourceEvidence={}, rustAdmissionTest=None,
                      producer=dict(helperPath="fake-helper", helperSha256=self.bindings["producerPin"]["helperSha256"],
                                    runtimeRoot="fake-runtime", runtimeLockPath="native/bap/toolchain.lock.json",
                                    runtimeLockSha256=legal.sha(legal.ROOT / "native/bap/toolchain.lock.json")), rows=[])
        # Syntactically valid BIL does not excuse wrong bytes/provenance. These
        # transport negatives fail before the independent semantic interpreter.
        bil = [{"kind": "while", "condition": {"kind": "int", "value": "0:1u"}, "body": []}]
        for partition in self.bindings["partitions"]:
            if partition["disposition"] != "S":
                continue
            alternative = partition["grammar"]["alternatives"][0]
            encoded = "".join(alternative["prefixes"]) + alternative["opcode"]
            va = f'0x{0x401000 + len(result["rows"]) * 32:016x}'
            response = dict(schema="ariadne.bap-site/v1", batch=0, snapshot=snapshot, va=va, status="decoded", length=2,
                            bytes=encoded, opcode={"f3a4": "MOVSB", "f3aa": "STOSB", "f3a6": "CMPSB"}[encoded], properties={}, bil=bil)
            result["rows"].append(dict(id=partition["observationIds"][0], partition=partition["id"],
                request=dict(snapshot=snapshot, va=va, consumedBytes=encoded, decodeEnvironment=dict(mode=64, addressBits=64, operandBits=8),
                             target="windows-amd64", profile=legal.PROFILE, consumer="plain-dependencies"),
                response=response, astSha256=legal.digest(bil), comparisonCount=240))
        return result

    def observe_negative(self, observations, expected):
        _, domains = legal.validate_legal(self.forms)
        partitions, classified = legal.validate_bindings(self.bindings, self.forms, domains)
        real_sha = legal.sha
        def sha(path):
            return self.bindings["producerPin"]["helperSha256"] if str(path) == "fake-helper" else real_sha(path)
        with patch.object(legal, "validate_source_evidence", return_value=35), patch.object(legal, "sha", side_effect=sha), \
                patch.object(legal, "read", return_value={"files": {}}):
            with self.assertRaisesRegex(ValueError, expected):
                legal.validate_observations(observations, self.forms, self.bindings, partitions, classified)

    def test_valid_bil_for_wrong_or_illegally_prefixed_bytes_rejects(self):
        for encoded in ("f2a4", "f3a490", "66f3a4"):
            observation = self.fake_observations()
            observation["rows"][0]["request"]["consumedBytes"] = encoded
            self.observe_negative(observation, "bytes/environment not admitted")
        observation = self.fake_observations()
        observation["rows"][0]["response"]["bytes"] = "f3a6"
        self.observe_negative(observation, "response bytes/consumed extent")

    def test_wrong_decode_environment_consumer_and_extent_reject(self):
        for change, expected in (("environment", "bytes/environment not admitted"),
                                 ("consumer", "consumer identity"), ("extent", "consumed extent"),
                                 ("ast", "AST digest differs")):
            observation = self.fake_observations()
            row = observation["rows"][0]
            if change == "environment":
                row["request"]["decodeEnvironment"]["addressBits"] = 32
            elif change == "consumer":
                row["request"]["profile"] = "bap-bit-provenance-v13"
            elif change == "extent":
                row["response"]["length"] = 3
            else:
                row["astSha256"] = "0" * 64
            self.observe_negative(observation, expected)

    def test_duplicate_stale_or_omitted_observations_reject(self):
        observation = self.fake_observations()
        observation["rows"].append(copy.deepcopy(observation["rows"][0]))
        self.observe_negative(observation, "duplicate observation")
        observation = self.fake_observations()
        observation["sourceSha256"]["src/bap/ast.rs"] = "0" * 64
        self.observe_negative(observation, "stale current test sources")
        observation = self.fake_observations()
        observation["rows"] = []
        self.observe_negative(observation, "missing/duplicate observation provenance")

    def test_unpinned_helper_runtime_and_snapshot_are_refused(self):
        observation = self.fake_observations()
        observation["producer"]["helperSha256"] = "0" * 64
        self.observe_negative(observation, "unpinned helper identity")
        observation = self.fake_observations()
        observation["producer"]["runtimeLockSha256"] = "0" * 64
        self.observe_negative(observation, "stale runtime lock")
        observation = self.fake_observations()
        observation["rows"][0]["response"]["snapshot"] = "0" * 64
        self.observe_negative(observation, "snapshot/VA mismatch")

    def test_source_cells_replay_geometry_not_only_hash_of_claim(self):
        from amd64_manual_geometry import read_geometry
        with tempfile.TemporaryDirectory() as work:
            bbox = Path(work) / "source.xml"
            prefix = '<doc>' + '<page width="100" height="100" />' * 49
            page = '<page width="100" height="100"><line><word xMin="1" yMin="1" xMax="2" yMax="2">66h</word></line></page></doc>'
            bbox.write_text(prefix + page)
            cell = dict(read_geometry(bbox)[49]["cells"][0], pdfSha256=legal.PDF_SHA)
            reference = {key: value for key, value in cell.items() if key in self.forms["sourceCells"][0]}
            real_sha = legal.sha
            def sha(path):
                return legal.PDF_SHA if str(path) == "pinned.pdf" else real_sha(path)
            evidence = dict(pdfPath="pinned.pdf", bboxPath=str(bbox), bboxSha256=real_sha(bbox))
            with patch.object(legal, "sha", side_effect=sha):
                self.assertEqual(legal.validate_source_evidence({"sourceCells": [reference]}, evidence), 1)
                bbox.write_text(prefix + page.replace('xMax="2"', 'xMax="3"'))
                evidence["bboxSha256"] = real_sha(bbox)
                with self.assertRaisesRegex(ValueError, "geometry differ"):
                    legal.validate_source_evidence({"sourceCells": [reference]}, evidence)

    def test_duplicate_json_keys_and_nonfinite_values_reject(self):
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            legal.strict_json('{"schema":"v2","schema":"v1"}')
        with self.assertRaisesRegex(ValueError, "nonfinite JSON"):
            legal.strict_json('{"value":NaN}')


class MemoryDomains(unittest.TestCase):
    def setUp(self):
        self.forms = legal.read(FIXTURES / "legal-forms-memory-rep-v3.json")
        self.bindings = legal.read(FIXTURES / "profile-bindings-memory-rep-v3.json")
        self.bindings["implementationSources"] = legal.current_memory_sources()
        # Algorithm controls can run during parallel source work; CLI gates use
        # the frozen fixture and real current source/producer identities.
        for name, contract in legal.SOURCE_PRODUCERS.items():
            path = legal.ROOT / contract["lock"]
            self.bindings["producerPins"][name]["lockSha256"] = legal.sha(path) if path.exists() else None

    def rebind(self):
        self.bindings["legalFormsSha256"] = legal.digest(self.forms)

    def check(self, observations=None):
        return legal.assess(self.forms, self.bindings, observations)

    def test_full_finite_accounting_keeps_vendor_and_observation_gates_open(self):
        report = self.check()
        self.assertEqual(report["enumeratedPoints"], 56)
        self.assertEqual([sum(form["supported"] for form in consumer["forms"])
                          for consumer in report["consumers"]], [3, 24, 28, 56])
        self.assertTrue(report["totalDisposition"])
        self.assertTrue(report["consumers"][-1]["implementationDomainComplete"])
        for field in ("sourceComplete", "vendorFullDenominator", "fullAmd64Coverage",
                      "implementationComplete", "currentObservationsValidated", "profileBindingsValidated"):
            self.assertFalse(report[field])
        self.assertEqual(report["candidateFullDomainBindings"], 0)

    def test_new_prefix_scope_does_not_rewrite_old_pilot(self):
        self.assertEqual(legal.expected_rep_domain(
            dict(operation="movs", elementBits=[16], addressBits=[32]),
            dict(mode=[64], operandBits=[16], addressBits=[32]), legal.Budget(100)),
            {legal.point_key("f36766a5", dict(mode=64, operandBits=16, addressBits=32))})
        self.assertIn("6766f3a5", legal.memory_cases())
        self.assertNotIn("f36766a5", legal.memory_cases())

    def test_omitted_or_unreviewed_legal_point_cannot_be_rehashed(self):
        self.forms["forms"][0]["grammar"]["alternatives"].pop()
        self.rebind()
        with self.assertRaisesRegex(ValueError, "independent reviewed derivation"):
            self.check()

    def test_missing_family_is_not_a_smaller_complete_denominator(self):
        self.forms["forms"].pop()
        self.forms["reviewedRules"].pop()
        self.rebind()
        with self.assertRaisesRegex(ValueError, "family denominator"):
            self.check()

    def test_opcode_source_cells_are_required_in_addition_to_general_prefixes(self):
        self.forms["sourceCells"] = [cell for cell in self.forms["sourceCells"] if cell["pdfPage"] < 100]
        self.rebind()
        with self.assertRaisesRegex(ValueError, "opcode/repeat/address-size"):
            self.check()

    def test_rule_cannot_substitute_another_familys_source_cells(self):
        self.forms["reviewedRules"][0]["sourceCells"] = legal.memory_source_ids("lods")
        self.rebind()
        with self.assertRaisesRegex(ValueError, "reviewed rule differs"):
            self.check()

    def test_other_vendor_is_outside_exact_environment(self):
        case = legal.memory_cases()["67f3a4"]
        query = legal.query(self.bindings, self.forms, None, case["bytes"], case["environment"])
        self.assertEqual([row["disposition"] for row in query["matches"]], ["U", "U", "U", "S"])
        environment = dict(case["environment"], vendor="Intel")
        self.assertEqual(legal.query(self.bindings, self.forms, None, case["bytes"], environment)["matches"], [])
        environment.pop("vendor")
        self.assertEqual(legal.query(self.bindings, self.forms, None, case["bytes"], environment)["matches"], [])

    def test_nonflat_faults_stream_suffix_and_prefix_neighbors_are_outside_scope(self):
        case = legal.memory_cases()["6766f3a5"]
        for code in ("6766f3a590", "66f367a5", "6766f3f3a5", "646766f3a5", "67f36c"):
            self.assertFalse(legal.query(self.bindings, self.forms, None, code, case["environment"])["matches"])
        for change in (dict(flatDefaultSegments=False), dict(outcomes="restart"), dict(addressBits=64)):
            environment = dict(case["environment"], **change)
            self.assertFalse(legal.query(self.bindings, self.forms, None, case["bytes"], environment)["matches"])

    def test_boolean_integer_and_float_environments_are_distinct(self):
        case = legal.memory_cases()["67f3a4"]
        for changes in (dict(flatDefaultSegments=1), dict(mode=64.0), dict(addressBits=32.0)):
            environment = dict(case["environment"], **changes)
            self.assertFalse(legal.query(self.bindings, self.forms, None, case["bytes"], environment)["matches"])
            observations = self.fake_observations()
            row = next(row for row in observations["rows"] if row["request"]["consumedBytes"] == case["bytes"])
            row["request"]["decodeEnvironment"] = environment
            with self.assertRaisesRegex(ValueError, "request bytes/environment"):
                self.observe(observations)
        self.forms["scope"]["environmentAxes"]["flatDefaultSegments"] = [1]
        self.rebind()
        with self.assertRaisesRegex(ValueError, "memory scope"):
            self.check()

    def test_partition_hole_and_unresolved_are_not_success(self):
        self.bindings["consumers"][-1]["partitions"].pop()
        report = self.check()
        self.assertFalse(report["totalDisposition"])
        self.assertEqual(sum(row["holes"] for row in report["consumers"][-1]["forms"]), 1)
        partition = self.bindings["consumers"][-1]["partitions"][0]
        partition.update(disposition="X", producer=None, observationIds=[])
        self.assertFalse(self.check()["consumers"][-1]["implementationDomainComplete"])

    def test_partition_overlap_and_outside_domain_refuse(self):
        consumer = self.bindings["consumers"][-1]
        extra = copy.deepcopy(consumer["partitions"][0])
        extra["id"] += "-duplicate"
        consumer["partitions"].append(extra)
        with self.assertRaisesRegex(ValueError, "overlapping memory"):
            self.check()
        consumer["partitions"].pop()
        consumer["partitions"][0]["grammar"]["alternatives"][0]["opcode"] = "90"
        with self.assertRaisesRegex(ValueError, "outside legal domain"):
            self.check()

    def test_old_profile_cannot_adopt_new_address_consumer(self):
        consumer = self.bindings["consumers"][2]
        partition = next(row for row in consumer["partitions"] if row["id"].endswith("67f3a4"))
        partition.update(disposition="S", producer="repAddress", observationIds=["fake"])
        with self.assertRaisesRegex(ValueError, "consumer/producer does not admit"):
            self.check()

    def test_selected_producer_must_match_each_profile_and_exact_byte(self):
        for index, code, wrong in ((2, "f3ac", "base"), (3, "f3ac", "lods"),
                                   (3, "67f3a4", "base"), (3, "f3a4", "repAddress")):
            partition = next(row for row in self.bindings["consumers"][index]["partitions"] if row["id"].endswith("-" + code))
            before = partition["producer"]
            partition["producer"] = wrong
            with self.assertRaisesRegex(ValueError, "consumer/producer does not admit"):
                self.check()
            partition["producer"] = before

    def test_stale_implementation_source_and_source_runtime_pin_refuse(self):
        self.bindings["implementationSources"]["src/bap/projection.rs"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "stale memory implementation"):
            self.check()
        self.bindings["implementationSources"] = legal.current_memory_sources()
        self.bindings["producerPins"]["lods"]["lockSha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source producer lock identity"):
            self.check()

    def test_unsupported_partition_cannot_claim_observation(self):
        partition = next(row for row in self.bindings["consumers"][0]["partitions"] if row["disposition"] == "U")
        partition["observationIds"] = ["fabricated"]
        with self.assertRaisesRegex(ValueError, "unsupported/unresolved"):
            self.check()

    def test_budget_exhaustion_and_schema_errors_never_close(self):
        report = legal.assess(self.forms, self.bindings, budget=3)
        self.assertEqual(report["status"], "unknown")
        self.assertFalse(report["profileBindingsValidated"])
        self.bindings["schema"] = legal.BINDINGS
        with self.assertRaisesRegex(ValueError, "stale memory legal binding"):
            self.check()

    def fake_observations(self):
        snapshot = legal.digest({"legal": legal.digest(self.forms), "bindings": legal.digest(self.bindings)})
        result = dict(schema=legal.MEMORY_OBSERVATIONS, legalFormsSha256=legal.digest(self.forms),
                      bindingsSha256=legal.digest(self.bindings), sourceSha256=legal.current_memory_sources(),
                      producers={}, sourceEvidence={}, rows=[], rustAdmissionTest=None)
        cases = legal.memory_cases()
        for consumer in self.bindings["consumers"]:
            for partition in consumer["partitions"]:
                if partition["disposition"] != "S":
                    continue
                alternative = partition["grammar"]["alternatives"][0]
                code = "".join(alternative["prefixes"]) + alternative["opcode"]
                case = cases[code]
                va = f'0x{0x401000 + 32 * len(result["rows"]):016x}'
                bil = [{"kind": "while", "condition": {"kind": "int", "value": "0:1u"}, "body": []}]
                response = dict(snapshot=snapshot, va=va, bytes=code, length=len(code) // 2, bil=bil)
                producer = partition["producer"]
                if producer == "base":
                    response.update(schema="ariadne.bap-site/v1", batch=0, status="decoded", opcode=case["opcode"], properties={})
                else:
                    response.update(schema=f'ariadne.bap-source-{legal.SOURCE_PRODUCERS[producer]["stem"]}/v1',
                                    build_id="b" * 64, target="windows-amd64")
                result["rows"].append(dict(id=partition["observationIds"][0], partition=partition["id"], producer=producer,
                    request=dict(snapshot=snapshot, va=va, consumedBytes=code, decodeEnvironment=case["environment"],
                                 target="windows-amd64", profile=consumer["id"], consumer="plain-dependencies"),
                    response=response, astSha256=legal.digest(bil), comparisonCount=1))
        return result

    def observe(self, observations):
        with patch.object(legal, "validate_source_evidence", return_value=516), \
                patch.object(legal, "validate_memory_producers", return_value={name: {"build_id": "b" * 64} for name in legal.SOURCE_PRODUCERS}), \
                patch.object(legal, "memory_comparisons", return_value=1):
            return self.check(observations)

    def test_skip_rust_admission_leaves_profile_binding_gate_open(self):
        report = self.observe(self.fake_observations())
        self.assertTrue(report["currentObservationsValidated"])
        self.assertFalse(report["profileBindingsValidated"])
        self.assertFalse(report["implementationComplete"])

    def test_wrong_request_or_producer_response_identity_refuses(self):
        for container, field, bad in (("request", "profile", legal.MEMORY_PROFILES[3]),
                                       ("request", "target", "linux-amd64"),
                                       ("response", "snapshot", "0" * 64),
                                       ("response", "length", 15),
                                       ("response", "opcode", "NOP"),
                                       ("response", "bytes", "90")):
            observations = self.fake_observations()
            observations["rows"][0][container][field] = bad
            with self.assertRaises(ValueError):
                self.observe(observations)

    def test_ast_numeric_count_and_unreviewed_vendor_refuse(self):
        for change in ("ast", "count", "vendor", "producer", "build"):
            observations = self.fake_observations()
            row = next(row for row in observations["rows"] if row["producer"] == "repAddress")
            if change == "ast":
                row["astSha256"] = "0" * 64
            elif change == "count":
                row["comparisonCount"] = 2
            elif change == "vendor":
                row["request"]["decodeEnvironment"]["vendor"] = "Intel"
            elif change == "producer":
                row["producer"] = "lods"
            else:
                row["response"]["build_id"] = "0" * 64
            with self.assertRaises(ValueError):
                self.observe(observations)

    def test_missing_duplicate_or_stale_observation_refuses(self):
        for change in ("missing", "duplicate", "stale"):
            observations = self.fake_observations()
            if change == "missing":
                observations["rows"].pop()
            elif change == "duplicate":
                observations["rows"].append(copy.deepcopy(observations["rows"][0]))
            else:
                observations["bindingsSha256"] = "0" * 64
            with self.assertRaises(ValueError):
                self.observe(observations)

    def test_rust_observer_cannot_be_replaced_by_passed_boolean(self):
        observations = self.fake_observations()
        observations["rustAdmissionTest"] = dict(passed=True)
        with self.assertRaisesRegex(ValueError, "Rust admission observer fields"):
            self.observe(observations)

    def producer_fixture(self, root):
        def write(relative, value):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value))
            return path
        helper = root / "helper"
        helper.write_text("fake binary for identity controls")
        write("native/bap/toolchain.lock.json", {"files": {}})
        sdk = dict(bapSourceRevision="revision", bapSourceArchive={"sha256": "a" * 64})
        write("native/bap-core/sdk.lock.json", sdk)
        producers = dict(base=dict(helperPath=str(helper), helperSha256=legal.sha(helper), runtimeRoot=str(root),
            runtimeLockPath="native/bap/toolchain.lock.json", runtimeLockSha256=legal.sha(root / "native/bap/toolchain.lock.json")))
        pins = dict(base={key: producers["base"][key] for key in ("helperSha256", "runtimeLockPath", "runtimeLockSha256")})
        for name, contract in legal.SOURCE_PRODUCERS.items():
            for source in contract["sources"]:
                path = root / "native/bap/source-coverage" / source
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("stable test source " + source)
            directory = root / name
            directory.mkdir()
            executable = directory / (contract["stem"] + "-lift")
            executable.write_text("fake executable for artifact identity controls")
            binding = dict(sources={source: legal.sha(root / "native/bap/source-coverage" / source)
                                    for source in contract["sources"]},
                           sdk_lock_sha256=legal.sha(root / "native/bap-core/sdk.lock.json"),
                           base_revision="revision", source_archive_sha256="a" * 64)
            manifest = dict(schema=f'ariadne.bap-source-{contract["stem"]}-build/v1', profiles=[contract["profile"]],
                runtime_role=contract["role"], executable=contract["stem"] + "-lift", executable_sha256=legal.sha(executable),
                max_response_bytes=65536, cases=sorted(code for code, case in legal.memory_cases().items()
                    if case["family"] == "lods" and case["addressBits"] == 64 or name == "repAddress" and case["addressBits"] == 32),
                binding=binding, build_id=legal.digest(binding))
            if name == "repAddress":
                manifest.update(vendor="AMD", semantic_premises=["amd-long-mode-memory-rep", "address32-zero-count-preserves-upper-lanes"])
            write(f"{name}/manifest.json", manifest)
            lock = dict(schema=f'ariadne.bap-source-{contract["stem"]}-lock/v1',
                        manifest_sha256=legal.sha(directory / "manifest.json"), executable_sha256=legal.sha(executable))
            write(contract["lock"], lock)
            pins[name] = dict(lockPath=contract["lock"], lockSha256=legal.sha(root / contract["lock"]))
            producers[name] = dict(directory=str(directory), manifestSha256=lock["manifest_sha256"],
                                   executableSha256=lock["executable_sha256"], lockSha256=pins[name]["lockSha256"])
        return producers, {"producerPins": pins}

    def test_selected_executable_and_source_file_drift_are_rejected(self):
        for target in ("repAddress/rep-address-lift", "lods/lods-lift", "native/bap/source-coverage/rep_address.patch"):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                producers, bindings = self.producer_fixture(root)
                self.assertEqual(set(legal.validate_memory_producers(producers, bindings, root)), {"lods", "repAddress"})
                (root / target).write_text("changed")
                with self.assertRaisesRegex(ValueError, "artifact differs|source binding"):
                    legal.validate_memory_producers(producers, bindings, root)

    def test_rehashed_source_manifest_cannot_change_vendor_or_case_scope(self):
        for change in ("vendor", "premise", "case", "build"):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                producers, bindings = self.producer_fixture(root)
                path = root / "repAddress/manifest.json"
                manifest = legal.read(path)
                if change == "vendor":
                    manifest["vendor"] = "Intel"
                elif change == "premise":
                    manifest["semantic_premises"].pop()
                elif change == "case":
                    manifest["cases"].pop()
                else:
                    manifest["build_id"] = "0" * 64
                path.write_text(json.dumps(manifest))
                lock_path = root / legal.SOURCE_PRODUCERS["repAddress"]["lock"]
                lock = legal.read(lock_path)
                lock["manifest_sha256"] = legal.sha(path)
                lock_path.write_text(json.dumps(lock))
                producers["repAddress"].update(manifestSha256=legal.sha(path), lockSha256=legal.sha(lock_path))
                bindings["producerPins"]["repAddress"]["lockSha256"] = legal.sha(lock_path)
                with self.assertRaisesRegex(ValueError, "manifest contract|semantic premises|SDK/build identity"):
                    legal.validate_memory_producers(producers, bindings, root)


if __name__ == "__main__":
    unittest.main()
