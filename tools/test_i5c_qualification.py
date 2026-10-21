"""Adversarial controls for I5c qualification, without native campaign credit."""
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import check_i5b_mutations
import check_i5c as gate
import check_i5c_mutations as mutations
import compare_i5c_legacy as legacy
import i5c_qualification as evidence
import export_i5c_runtime as runtime_export


class QualificationControls(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def synthetic_baseline(self, path):
        # Synthetic parser/negative controls cannot supply a production origin.
        with patch.object(legacy, "LEGACY_BASELINE_SHA256", evidence.sha(path)):
            return legacy.baseline(path, evidence.sha(path))

    def test_all_frozen_mutants_have_unique_live_source_seams(self):
        rows = mutations.frozen_mutations()
        self.assertEqual(len(rows), 24)
        for row in rows:
            with self.subTest(row=row["name"]):
                result = mutations.transformed(evidence.ROOT, row["name"])
                self.assertTrue(result)
                for name, changed in result.items():
                    self.assertNotEqual(changed, (evidence.ROOT / name).read_text())
                selector, test = mutations.observer(row["observer_case"])
                self.assertTrue(test)
                self.assertIn(selector[0], ("lib", "test"))

    def test_older_i5b_mutation_seams_follow_the_shared_admission_owner(self):
        for name, _, changes in check_i5b_mutations.MUTATIONS:
            for filename, old, new in changes:
                with self.subTest(mutation=name, filename=filename):
                    self.assertEqual((evidence.ROOT / filename).read_text().count(old), 1)
                    self.assertNotEqual(old, new)

    def test_frozen_mutation_inventory_cannot_be_narrowed(self):
        record = evidence.read_json(evidence.FIXTURES / "mutations.json")
        for field in ("count", "records"):
            changed = copy.deepcopy(record)
            changed[field] = 23 if field == "count" else changed[field][:-1]
            with self.subTest(field=field), patch.object(mutations, "read_json", return_value=changed):
                with self.assertRaises(ValueError):
                    mutations.frozen_mutations()

    def test_duplicate_and_nonfinite_json_and_lfs_are_rejected(self):
        path = self.root / "record.json"
        for raw in ('{"passed":false,"passed":true}', '{"time":NaN}', evidence.LFS.decode()):
            path.write_text(raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                evidence.read_json(path)

    def test_retained_cache_payload_must_match_pointer_size_and_digest(self):
        payload = b'{"old-evidence":true}\n'
        digest = hashlib.sha256(payload).hexdigest()
        pointer = self.root / "old.json"
        pointer.write_bytes(evidence.LFS + f"oid sha256:{digest}\nsize {len(payload)}\n".encode())
        cached = self.root / ".git/lfs/objects" / digest[:2] / digest[2:4] / digest
        cached.parent.mkdir(parents=True)
        with patch.object(evidence, "ROOT", self.root):
            with self.assertRaises(ValueError):
                evidence.retained_path(pointer)
            cached.write_bytes(payload)
            self.assertEqual(evidence.retained_path(pointer), cached)
            cached.write_bytes(payload + b"changed")
            with self.assertRaises(ValueError):
                evidence.retained_path(pointer)

    def test_command_preserves_raw_stream_bytes(self):
        receipt, _, _ = evidence.command(self.root, "raw", [
            sys.executable, "-c", "import sys;sys.stdout.buffer.write(b'a\\r\\nb\\xff');sys.stderr.buffer.write(b'e\\r\\n')"], env={})
        self.assertEqual(receipt["exitCode"], 0)
        self.assertEqual(Path(receipt["stdout"]["path"]).read_bytes(), b"a\r\nb\xff")
        self.assertEqual(Path(receipt["stderr"]["path"]).read_bytes(), b"e\r\n")
        self.assertEqual(receipt["stdout"]["sha256"], hashlib.sha256(b"a\r\nb\xff").hexdigest())

    def test_cargo_selection_rejects_ambiguous_foreign_and_non_test_artifacts(self):
        executable = self.root / "test-binary"
        executable.write_bytes(b"compiled identity")
        row = {"reason": "compiler-artifact", "executable": str(executable),
               "target": {"name": "ariadne", "kind": ["lib"], "src_path": str(evidence.ROOT / "src/lib.rs")},
               "profile": {"test": True}}
        kwargs = dict(kind="lib", test=True, target_dir=self.root)
        self.assertEqual(evidence.cargo_artifact(json.dumps(row), "ariadne", **kwargs), evidence.artifact(executable))
        bad = copy.deepcopy(row)
        bad["target"]["src_path"] = "/unrelated/foreign.rs"
        ordinary = copy.deepcopy(row)
        ordinary["profile"]["test"] = False
        for raw in ("", json.dumps(row) + "\n" + json.dumps(row), json.dumps(bad), json.dumps(ordinary)):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                evidence.cargo_artifact(raw, "ariadne", **kwargs)
        with self.assertRaises(ValueError):
            evidence.cargo_artifact(json.dumps(row), "ariadne", **{**kwargs, "target_dir": self.root / "other"})

    def test_zero_tests_compiler_failures_and_timeouts_cannot_kill_a_mutant(self):
        executable = self.root / "compiled"
        executable.write_bytes(b"compiled observer")
        intended = "test selected ... FAILED\n\ntest result: FAILED. 0 passed; 1 failed; 0 ignored; 0 measured; 0 filtered out\n"
        good = {"exitCode": 101, "timedOut": False}
        with patch.object(evidence, "command", return_value=(good, intended, "")):
            evidence.observe(self.root, executable, "selected", failed=True)
        controls = [({"exitCode": 101, "timedOut": False}, "error: could not compile"),
                    ({"exitCode": 101, "timedOut": True}, intended),
                    ({"exitCode": 0, "timedOut": False}, intended),
                    (good, "test result: ok. 0 passed; 0 failed; 0 ignored;"),
                    (good, intended.replace("selected", "another")),
                    (good, intended + intended)]
        for receipt, stdout in controls:
            with self.subTest(receipt=receipt, stdout=stdout), patch.object(evidence, "command", return_value=(receipt, stdout, "")):
                with self.assertRaises(ValueError):
                    evidence.observe(self.root, executable, "selected", failed=True)

    def test_named_case_count_does_not_hide_duplicates_or_missing_cases(self):
        rows = [{"name": "a", "passed": True}, {"name": "b", "passed": True}]
        wire = lambda selected: "\n".join("CASE " + json.dumps(row) for row in selected)
        self.assertEqual(evidence.named_rows(wire(rows), "CASE ", {"a", "b"}), rows)
        for changed in (rows[:1], rows + rows[:1], [{"name": "a", "passed": 1}, rows[1]]):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                evidence.named_rows(wire(changed), "CASE ", {"a", "b"})

    def test_all_666_named_legacy_outputs_and_independent_pin_are_required(self):
        keys = legacy.expected_keys()
        self.assertEqual(len(keys), 666)
        self.assertEqual(sum(key.startswith("i5a/") for key in keys), 246)
        self.assertEqual(sum(key.startswith("i5b/") for key in keys), 342)
        self.assertEqual(sum(key.startswith("i5b-upstream/") for key in keys), 6)
        self.assertEqual(sum(key.startswith("base/") for key in keys), 72)
        path = self.root / "baseline.json"
        value = {"schema": "ariadne.i5c-legacy-bytes/v1",
                 "outputs": {key: {"bytes": 0, "sha256": "0" * 64} for key in keys}}
        evidence.write_json(path, value)
        self.synthetic_baseline(path)
        with self.assertRaises(ValueError):
            legacy.baseline(path, "f" * 64)
        value["outputs"].pop(next(iter(keys)))
        evidence.write_json(path, value)
        with self.assertRaises(ValueError):
            self.synthetic_baseline(path)

    def test_original_pre_w1_baseline_is_adapted_without_replacing_expected_bytes(self):
        outputs = {}
        for key in legacy.expected_keys():
            if key.startswith("base/"):
                old = key
            else:
                parts = key.split("/")
                if parts[0] == "i5b-upstream":
                    parts = ["i5b", "upstream-call", *parts[1:]]
                profile, case, backend, fmt = parts
                prefix = "zero-address-assessment." if profile == "i5a" else "zero-base-offset-assessment."
                old = f"{profile}/{case}/{backend}/{prefix}{'txt' if fmt == 'text' else fmt}"
            outputs[old] = {"bytes": 7, "sha256": "a" * 64}
        parity = [{"case": f"parity/{profile}/{case}/{backend}/{fmt}", "sha256": "a" * 64}
                  for profile, case in (("i5a", "zero-store"), ("i5a", "unknown-flags"),
                                        ("i5b", "mov32mi-positive"), ("i5b", "indexed"),
                                        ("i5b", "excluded-range"), ("i5b", "upstream-call"))
                  for backend in ("rust", "bap") for fmt in ("text", "json", "dot")]
        original = {"schema": "ariadne.i5c-legacy-before/v1", "passed": True, "total_outputs": 666,
                    "sources_unchanged": True, "outputs_normalized": False,
                    "native_build_receipts_preserved_raw": True, "outputs": outputs,
                    "public_api_cli_parity": parity}
        path = self.root / "original-baseline.json"
        evidence.write_json(path, original)
        adapted = self.synthetic_baseline(path)
        self.assertEqual(set(adapted["outputs"]), legacy.expected_keys())
        self.assertEqual(adapted["retainedCliParityCases"], 36)
        self.assertTrue(all(row == {"bytes": 7, "sha256": "a" * 64} for row in adapted["outputs"].values()))
        for change in ("normalized", "missing-parity", "bad-parity"):
            bad = copy.deepcopy(original)
            if change == "normalized":
                bad["outputs_normalized"] = True
            elif change == "missing-parity":
                bad["public_api_cli_parity"].pop()
            else:
                bad["public_api_cli_parity"][0]["sha256"] = "b" * 64
            evidence.write_json(path, bad)
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.synthetic_baseline(path)

    def make_archive(self, members):
        path = self.root / "evidence.tar.gz"
        with tarfile.open(path, "w:gz") as archive:
            for name, data, kind in members:
                item = tarfile.TarInfo(name)
                if kind == "file":
                    item.size = len(data)
                    archive.addfile(item, io.BytesIO(data))
                else:
                    item.type = tarfile.SYMTYPE
                    item.linkname = "elsewhere"
                    archive.addfile(item)
        return path

    def test_archive_verification_rejects_duplicate_missing_extra_link_and_changed_bytes(self):
        expected = {"entry": {"bytes": 1, "sha256": hashlib.sha256(b"x").hexdigest()}}
        gate.verify_archive(self.make_archive([("entry", b"x", "file")]), expected)
        for members in ([], [("entry", b"x", "file")] * 2, [("extra", b"x", "file")],
                        [("entry", b"x", "link")], [("entry", b"y", "file")]):
            with self.subTest(members=members), self.assertRaises(ValueError):
                gate.verify_archive(self.make_archive(members), expected)

    def test_runtime_stage_exports_cannot_be_omitted(self):
        path = self.root / "export.json"
        for stages in ({}, {"W2": {}}):
            evidence.write_json(path, {"schema": "ariadne.i5c-w2-w3-runtime-export/v1", "stages": stages})
            with self.subTest(stages=stages), self.assertRaises(ValueError):
                gate.runtime_files(path, evidence.sha(path))

    def test_producer_sealing_requires_original_inputs_tools_binaries_and_logs(self):
        directory = self.root / "producer"
        directory.mkdir()
        source = directory / "source/recipe.asm"
        source.parent.mkdir()
        source.write_bytes(b"original recipe")
        (directory / "source.tar.gz").write_bytes(b"original prepared archive")
        tools, binaries = {}, {}
        for name in ("gn.exe", "ninja.exe"):
            path = directory / "tools" / name
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(name.encode())
            tools[name] = evidence.sha(path)
        for name in ("ariadne_crash_demo.exe", "crashpad_handler.exe", "crashpad_database_util.exe"):
            path = directory / "source/out/Release" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(name.encode())
            binaries[name] = evidence.sha(path)
        evidence.write_json(directory / "build-inputs.json", {"sourceHashes": {"recipe.asm": evidence.sha(source)}})
        evidence.write_json(directory / "build.json", {
            "inputs": {"inputsSha256": evidence.sha(directory / "build-inputs.json"),
                       "sourceArchiveSha256": evidence.sha(directory / "source.tar.gz")},
            "toolHashes": tools, "binaryHashes": binaries})
        for name in ("tools.ensure", "owner.json", "tools.log", "gn.log", "gn-repeat.log", "build.log",
                     "arm64-rejection.log", "gn-version.log", "ninja-version.log", "clang-version.log"):
            (directory / name).write_bytes(b"original log")
        path = directory / "build.json"
        pin = evidence.sha(path)
        files = gate.producer_files(path, pin)
        self.assertEqual(files["producer/source/recipe.asm"].read_bytes(), b"original recipe")
        for relative in ("source.tar.gz", "source/recipe.asm", "tools/gn.exe",
                         "source/out/Release/crashpad_handler.exe", "build.log"):
            original = (directory / relative).read_bytes()
            (directory / relative).unlink()
            with self.subTest(relative=relative), self.assertRaises((OSError, ValueError)):
                gate.producer_files(path, pin)
            (directory / relative).write_bytes(original)
        with self.assertRaises(ValueError):
            gate.producer_files(path, "0" * 64)

    def test_runtime_export_checks_original_streams_and_rejects_a_self_consistent_omission(self):
        repo = self.root / "repo"
        campaign = self.root / "retained"
        campaign.mkdir()
        (campaign / "stdout.log").write_bytes(b"old successful test output\n")
        (campaign / "stderr.log").write_bytes(b"")
        for relative in ("20261020/w2", "20261021/w3"):
            qualified = repo / "evidence/Ariadne/address-wrap" / relative / "qualification.json"
            qualified.parent.mkdir(parents=True)
            streams = {name: {"path": "/campaign/" + name + ".log",
                              "bytes": (campaign / (name + ".log")).stat().st_size,
                              "sha256": evidence.sha(campaign / (name + ".log"))}
                       for name in ("stdout", "stderr")}
            evidence.write_json(qualified, {"passed": True, "records": [
                {"passed": True, "exit": 0, "timed_out": False, **streams}]})
        with patch.object(runtime_export, "ROOT", repo), patch.object(gate, "ROOT", repo):
            index_path = runtime_export.export(campaign, self.root / "export")
            value = evidence.read_json(index_path)
            gate.runtime_files(index_path, evidence.sha(index_path))
            del value["stages"]["W2"]["files"]["campaign/stdout.log"]
            (Path(value["stages"]["W2"]["root"]) / "campaign/stdout.log").unlink()
            evidence.write_json(index_path, value)
            with self.assertRaisesRegex(ValueError, "originally bound runtime stream"):
                gate.runtime_files(index_path, evidence.sha(index_path))

    def test_failed_sealing_or_source_drift_cannot_publish_positive_flags(self):
        record = {"passed": True, "failure": None, "sourceFixtureAcceptance": True,
                  "controlledWindowsPartialAcceptance": True, "controlledWindowsFullAcceptance": True,
                  "fullI5cAcceptance": True}
        for reason in ("archive failure", "source drift"):
            work = self.root / reason
            work.mkdir()
            with patch.object(gate, "seal") as seal, patch.object(gate, "sources", return_value={"changed": "1"}):
                if reason == "archive failure":
                    seal.side_effect = ValueError("archive mismatch")
                else:
                    seal.return_value = {"verified": True}
                self.assertFalse(gate.publish_acceptance(work, record, {}, {}))
            published = evidence.read_json(work / "report.json")
            for key in ("passed", "sourceFixtureAcceptance", "controlledWindowsPartialAcceptance", "controlledWindowsFullAcceptance", "fullI5cAcceptance"):
                self.assertIs(published[key], False)
            self.assertFalse((work / "sealed").exists())

    def test_preflight_failure_keeps_every_acceptance_flag_false(self):
        output = self.root / "preflight"
        prerequisite = {"passed": False, "qualificationEnvironment": None, "tools": {}, "missing": ["native runtime"]}
        with patch.object(sys, "argv", ["check_i5c.py", "--output", str(output), "--preflight-only"]), \
                patch.object(gate, "sources", return_value={"source": "0" * 64}), \
                patch.object(gate, "prerequisite_report", return_value=prerequisite), \
                patch.object(gate, "run_gate") as run:
            self.assertEqual(gate.main(), 1)
            run.assert_not_called()
        record = evidence.read_json(output / "report.json")
        for key in ("passed", "sourceFixtureAcceptance", "controlledWindowsPartialAcceptance", "controlledWindowsFullAcceptance", "fullI5cAcceptance"):
            self.assertIs(record[key], False)
        self.assertFalse((output / "sealed").exists())

    def test_successful_preflight_alone_cannot_qualify_a_tier(self):
        output = self.root / "ready"
        prerequisite = {"passed": True, "qualificationEnvironment": {}, "tools": {}, "missing": []}
        with patch.object(sys, "argv", ["check_i5c.py", "--output", str(output), "--preflight-only"]), \
                patch.object(gate, "sources", return_value={"source": "0" * 64}), \
                patch.object(gate, "prerequisite_report", return_value=prerequisite), \
                patch.object(gate, "run_gate") as run:
            self.assertEqual(gate.main(), 0)
            run.assert_not_called()
        record = evidence.read_json(output / "report.json")
        self.assertIs(record["prerequisitesPassed"], True)
        self.assertIs(record["fullI5cAcceptance"], False)
        self.assertIs(record["qualificationExecuted"], False)


if __name__ == "__main__":
    unittest.main()
