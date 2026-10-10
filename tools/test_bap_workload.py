"""Controlled workload-runner regressions, not native capture acceptance.

The real main() consumes stub CLI reports and phase CSVs; no native tools run.
Temporary bytes and mocked artifact hashes stand in for the pinned captures.
"""
from contextlib import redirect_stderr, redirect_stdout
import copy
import csv
import hashlib
import io
import itertools
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import measure_bap as measurement
from test_bap_workload_contract import CASE as WINDOWS


LINUX = json.loads((measurement.ROOT / "evidence/Ariadne/priority-1-real-capture-case.json").read_text())
ACTIVE_HISTORICAL = {"id": "historical-test-double", "capture": {**LINUX["capture"], "platform": "linux"},
                     "query": LINUX["query"], "expectations": {"decodedStarts": 34, "phaseBudgetMs": 250}}



class ControlledBapWorkloadTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="ariadne-controlled-bap-runner-")
        self.addCleanup(directory.cleanup)
        self.work = Path(directory.name)
        self.output = self.work / "workloads"
        self.windows_dump = self.work / "windowsWorkload.dmp"
        with self.windows_dump.open("wb") as capture:
            capture.truncate(WINDOWS["capture"]["bytes"])
        self.windows_case = copy.deepcopy(WINDOWS)
        self.windows_hash = hashlib.sha256(self.windows_dump.read_bytes()).hexdigest()
        self.windows_case["capture"]["sha256"] = self.windows_hash
        self.case_path = self.work / "case.json"
        self.archive_path = self.work / "inputs.tar.gz"
        self._bundle()
        self.initial_sources = {"src/engine.rs": "a" * 64, "tools/measure_bap.py": "b" * 64,
                                measurement.WINDOWS_ARCHIVE_RELATIVE: self.windows_case["inputArchive"]["sha256"]}
        self.current_sources = dict(self.initial_sources)
        self.change_sources = False
        self.windows_report_mutation = None
        self.elapsed_ms = 1000
        self.cli_reports = {}
        self.commands = []

    def _bundle(self, members=None, *, update_digest=True):
        if members is None:
            members = [("capture.dmp", tarfile.REGTYPE, self.windows_dump.read_bytes())]
        with tarfile.open(self.archive_path, "w:gz") as archive:
            for name, kind, data in members:
                member = tarfile.TarInfo(name)
                member.type = kind
                if kind == tarfile.REGTYPE:
                    member.size = len(data)
                elif kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                    member.linkname = "../capture.dmp"
                archive.addfile(member, io.BytesIO(data) if kind == tarfile.REGTYPE else None)
        digest = hashlib.sha256(self.archive_path.read_bytes()).hexdigest()
        if update_digest:
            self.windows_case["inputArchive"]["sha256"] = digest
        if hasattr(self, "initial_sources"):
            self.initial_sources[measurement.WINDOWS_ARCHIVE_RELATIVE] = digest
            self.current_sources[measurement.WINDOWS_ARCHIVE_RELATIVE] = digest
        self.case_path.write_text(json.dumps(self.windows_case))

    def _is_windows(self, capture):
        return capture == self.windows_dump or capture.name == "capture.dmp"

    def _sha(self, path):
        path = Path(path)
        if path == self.windows_dump:
            return self.windows_hash
        if path.name == "chromium-member-uaf.dmp":
            return LINUX["capture"]["sha256"]
        if path.is_relative_to(self.work):
            return hashlib.sha256(path.read_bytes()).hexdigest()
        return "c" * 64

    def _cli_report(self, capture, entry):
        entry = f"0x{int(entry, 16):016x}"
        if self._is_windows(capture):
            seed = WINDOWS["query"]["seed_va"]
            producer = WINDOWS["query"]["producer_va"]
            decoded = [f"0x{int(entry, 16) + offset:016x}" for offset in range(98)]
            sliced = [producer, seed]
        elif capture.name == "chromium-member-uaf.dmp":
            seed = LINUX["query"]["seed_va"]
            producer = LINUX["query"]["producer_va"]
            decoded = [f"0x{int(entry, 16) + offset:016x}" for offset in range(32)] + [producer, seed]
            sliced = [producer, seed]
        else:
            seed = f"0x{int(entry, 16) + 6:016x}"
            decoded = [f"0x{int(entry, 16) + offset:016x}" for offset in (0, 3, 6, 8)]
            sliced = decoded[:3] if capture.name == "bap_precision_linux.dmp" else [entry, seed]
        report = {
            "identity": {"artifact_sha256": self._sha(capture), "query_id": "d" * 64,
                         "platform": "windows" if self._is_windows(capture) or capture.name == "stage_b_windows.dmp" else "linux",
                         "decoder_target": "x86_64-pc-windows-msvc" if self._is_windows(capture) or capture.name == "stage_b_windows.dmp" else "x86_64-pc-linux-gnu"},
            "query": {"entries": [entry], "seeds": [seed]},
            "analysis": {
                "decoded": decoded, "edges": [], "slice": sliced, "obligations": [],
                "missing_slice_seeds": [],
            },
            "preparation": {"sites": [
                {"va": va, "byte_source": "captured", "semantic": {"status": "external_lift"}}
                for va in decoded
            ]},
        }
        if self._is_windows(capture):
            report["analysis"]["reaching"] = [{
                "before": seed,
                "definitions": [
                    {"loc": f"gpr:rcx:{byte}", "site": producer, "origin": "instruction"}
                    for byte in range(8)
                ],
            }]
            if self.windows_report_mutation:
                self.windows_report_mutation(report)
        return report

    def _run(self, command):
        args = [str(part) for part in command]
        self.commands.append(args)
        if args[0] == "cargo":
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[0] == "/usr/bin/time":
            capture = Path(args[6])
            entry = args[args.index("--entry") + 1]
            output = Path(args[args.index("--output-dir") + 1])
            output.mkdir()
            Path(args[4]).write_text("1,1024\n")
            report = self._cli_report(capture, entry)
            self.cli_reports[capture] = report
            (output / "report.json").write_text(json.dumps(report))
            (output / "report.txt").write_text("controlled runner report\n")
            (output / "report.dot").write_text("digraph controlled_runner {}\n")
            return subprocess.CompletedProcess(args, 0, "", "")
        if Path(args[0]).name != "bap_minidump":
            raise AssertionError(f"Unexpected command: {args}")
        capture = Path(args[1])
        report = self.cli_reports[capture]
        row = {
            "artifact_sha256": report["identity"]["artifact_sha256"],
            **{key: len(report["analysis"][key]) for key in ("decoded", "edges", "slice", "obligations")},
            "prepare_ns": 1_000_000, "analysis_ns": 1_000_000, "render_ns": 1_000_000,
        }
        data = io.StringIO()
        writer = csv.DictWriter(data, fieldnames=list(row), lineterminator="\n")
        writer.writeheader()
        writer.writerows([row] * 6)
        if self.change_sources:
            self.current_sources["src/engine.rs"] = "e" * 64
        return subprocess.CompletedProcess(args, 0, data.getvalue(), "")

    def _measure(self, *, windows=True, bundled=False, environment=None, extra_args=()):
        argv = ["measure_bap.py", "--output", str(self.output)]
        if windows and not bundled:
            argv += ["--windows-dump", str(self.windows_dump)]
        elif not windows:
            argv += ["--skip-windows"]
        argv += extra_args
        environment = {"ARIADNE_PRIORITY4_DUMP": str(self.work / "unavailable-legacy-capture.dmp"),
                       "ARIADNE_BAP_WINDOWS_DUMP": "", **(environment or {})}
        ticks = itertools.count(step=int(self.elapsed_ms * 1_000_000))
        with patch.object(measurement.real_case, "load_case", return_value=ACTIVE_HISTORICAL), \
             patch.object(measurement.real_case, "selected_dump", return_value=measurement.ROOT / "tmp/priority1/chromium-member-uaf.dmp"), \
             patch.object(measurement.real_case, "validate_report"), \
             patch.object(measurement, "sources", side_effect=lambda: dict(self.current_sources)), \
             patch.object(measurement, "WINDOWS_CASE_PATH", self.case_path), \
             patch.object(measurement, "WINDOWS_ARCHIVE_PATH", self.archive_path), \
             patch.object(measurement, "sha", side_effect=self._sha), \
             patch.object(measurement, "run", side_effect=self._run), \
             patch.object(measurement.time, "perf_counter_ns", side_effect=lambda: next(ticks)), \
             patch.dict(os.environ, environment), \
             patch("sys.argv", argv), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            measurement.main()

    def _record(self):
        return json.loads((self.output / "report.json").read_text())

    def test_stable_windows_run_preserves_source_inventory_and_passes(self):
        self._measure()
        record = self._record()
        self.assertEqual(record["schema"], "ariadne.bap-workloads/v4")
        self.assertIsInstance(record["sourceHashes"], dict)
        self.assertEqual(record["sourceHashes"], self.initial_sources)
        self.assertTrue(record["passed"])
        self.assertTrue(record["sourcesStable"])
        self.assertTrue(record["windowsWorkloadChecked"])
        self.assertTrue(record["windowsWorkloadTargetMet"])
        self.assertTrue(record["defaultPromotionEligible"])
        self.assertIsNone(record["windowsWorkloadBudgetMs"])
        self.assertEqual(record["missing"], [])
        windows = [row for row in record["records"] if row["workload"] == WINDOWS["id"]]
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0]["counts"]["decoded"], 98)
        self.assertEqual(windows[0]["elapsedMs"], {"median": 1000, "min": 1000, "max": 1000, "samples": 5})
        self.assertEqual(windows[0]["warmupSamplesMs"], [1000])
        self.assertEqual(windows[0]["elapsedSamplesMs"], [1000] * 5)
        self.assertEqual(windows[0]["query"], {"entries": [WINDOWS["query"]["entry_va"]], "seeds": [WINDOWS["query"]["seed_va"]]})
        self.assertTrue(record["windowsWorkloadQualification"]["valid"])
        self.assertFalse(windows[0]["historicalCapture"])
        self.assertEqual(windows[0]["captureKind"], "controlled-crashpad-windows")
        self.assertFalse(any(key.startswith("windows98") for key in record))

    def test_changed_sources_fail_and_preserve_original_inventory(self):
        self.change_sources = True
        with self.assertRaisesRegex(SystemExit, "workload sources changed during validation"):
            self._measure()
        record = self._record()
        self.assertFalse(record["passed"])
        self.assertFalse(record["sourcesStable"])
        self.assertIsInstance(record["sourceHashes"], dict)
        self.assertEqual(record["sourceHashes"], self.initial_sources)
        self.assertNotEqual(record["sourceHashes"], self.current_sources)

    def test_no_windows_preserves_available_workloads_and_missing_prerequisite(self):
        self._measure(windows=False)
        record = self._record()
        self.assertTrue(record["passed"])
        self.assertTrue(record["sourcesStable"])
        self.assertEqual(record["sourceHashes"], self.initial_sources)
        self.assertEqual([row["workload"] for row in record["records"]], [
            "stage-b-linux", "stage-b-windows", "controlled-not", "real-capture",
        ])
        self.assertFalse(record["windowsWorkloadChecked"])
        self.assertFalse(record["windowsWorkloadTargetMet"])
        self.assertFalse(record["defaultPromotionEligible"])
        self.assertIsNone(record["windowsWorkloadBudgetMs"])
        self.assertEqual(record["windowsWorkloadQualification"]["status"], "unavailable")
        self.assertEqual(record["missing"], [record["windowsWorkloadQualification"]["reason"]])

    def test_wrong_pinned_windows_hash_is_rejected_before_workloads(self):
        self.windows_hash = "0" * 64
        with self.assertRaisesRegex(RuntimeError, "Pinned controlled Windows artifact hash mismatch"):
            self._measure()
        self.assertFalse(any(command[0] == "/usr/bin/time" for command in self.commands))
        self.assertFalse((self.output / "report.json").exists())

    def test_wrong_pinned_windows_size_is_rejected_before_workloads(self):
        with self.windows_dump.open("ab") as capture:
            capture.write(b"\0")
        with self.assertRaisesRegex(RuntimeError, "Pinned controlled Windows artifact hash mismatch"):
            self._measure()
        self.assertFalse(any(command[0] == "/usr/bin/time" for command in self.commands))
        self.assertFalse((self.output / "report.json").exists())

    def test_default_uses_verified_bundle_and_ignores_legacy_environment(self):
        self._measure(bundled=True)
        record = self._record()
        self.assertTrue(record["windowsWorkloadQualification"]["valid"])
        materialized = list(self.output.glob("windows-input-*/capture.dmp"))
        self.assertEqual(len(materialized), 1)
        self.assertEqual(materialized[0].read_bytes(), self.windows_dump.read_bytes())
        self.assertTrue(any(command[0] == "/usr/bin/time" and command[6] == str(materialized[0])
                            for command in self.commands))

    def test_new_environment_selects_only_exact_pinned_override(self):
        with patch.object(measurement, "materialize_windows_capture") as materialize:
            self._measure(bundled=True, environment={"ARIADNE_BAP_WINDOWS_DUMP": str(self.windows_dump)})
        materialize.assert_not_called()
        self.assertTrue(self._record()["windowsWorkloadQualification"]["valid"])
        self.assertFalse(list(self.output.glob("windows-input-*")))

    def test_explicit_override_takes_precedence_over_environment(self):
        self._measure(environment={"ARIADNE_BAP_WINDOWS_DUMP": str(self.work / "missing.dmp")})
        self.assertTrue(self._record()["windowsWorkloadQualification"]["valid"])

    def test_skip_windows_suppresses_environment_and_bundle(self):
        with patch.object(measurement, "materialize_windows_capture") as materialize:
            self._measure(windows=False, environment={"ARIADNE_BAP_WINDOWS_DUMP": str(self.work / "missing.dmp")})
        materialize.assert_not_called()
        self.assertFalse(self._record()["windowsWorkloadChecked"])
        self.assertEqual(self._record()["windowsWorkloadQualification"]["status"], "unavailable")

    def test_skip_and_explicit_override_are_mutually_exclusive(self):
        with self.assertRaises(SystemExit) as error:
            self._measure(extra_args=["--skip-windows"])
        self.assertEqual(error.exception.code, 2)
        self.assertFalse(self.commands)

    def test_historical_windows_capture_cannot_be_relabelled(self):
        self.windows_hash = "4b3deb70134015ec227b3cf5edf82e1dac0b308b3f19ae62f79cbd4251109e86"
        with self.assertRaisesRegex(RuntimeError, "Pinned controlled Windows artifact hash mismatch"):
            self._measure()
        self.assertFalse(any(command[0] == "/usr/bin/time" for command in self.commands))
        self.assertFalse((self.output / "report.json").exists())

    def test_wrong_archive_hash_is_rejected_before_workloads(self):
        self._bundle([("capture.dmp", tarfile.REGTYPE, b"x" * WINDOWS["capture"]["bytes"])], update_digest=False)
        with self.assertRaisesRegex(RuntimeError, "Windows input archive hash mismatch"):
            self._measure(bundled=True)
        self.assertFalse(any(command[0] == "/usr/bin/time" for command in self.commands))
        self.assertFalse((self.output / "report.json").exists())

    def test_external_override_cannot_qualify_a_broken_archive_pin(self):
        self._bundle([("capture.dmp", tarfile.REGTYPE, b"x" * WINDOWS["capture"]["bytes"])], update_digest=False)
        for selection in ("explicit", "environment"):
            with self.subTest(selection=selection):
                self.output = self.work / f"archive-mismatch-{selection}"
                with self.assertRaisesRegex(RuntimeError, "Windows input archive hash mismatch"):
                    self._measure(bundled=selection == "environment",
                                  environment={"ARIADNE_BAP_WINDOWS_DUMP": str(self.windows_dump)})
                self.assertFalse((self.output / "report.json").exists())
        self.assertFalse(any(command[0] == "/usr/bin/time" for command in self.commands))

    def test_external_override_checks_actual_archive_despite_matching_recorded_digest(self):
        self.archive_path.write_bytes(b"changed after inventory snapshot")
        with self.assertRaisesRegex(RuntimeError, "Windows input archive hash mismatch"):
            self._measure()
        self.assertFalse((self.output / "report.json").exists())

    def test_skip_windows_remains_implementation_only_with_archive_digest_mismatch(self):
        self._bundle([("capture.dmp", tarfile.REGTYPE, b"x" * WINDOWS["capture"]["bytes"])], update_digest=False)
        self._measure(windows=False)
        self.assertTrue(self._record()["passed"])
        self.assertFalse(self._record()["windowsWorkloadChecked"])
        self.assertFalse(self._record()["windowsWorkloadTargetMet"])

    def test_archive_capture_requires_one_regular_member_of_pinned_size(self):
        data = self.windows_dump.read_bytes()
        variants = (
            [], [("../capture.dmp", tarfile.REGTYPE, data)],
            [("capture.dmp", tarfile.SYMTYPE, b"")],
            [("capture.dmp", tarfile.LNKTYPE, b"")],
            [("capture.dmp", tarfile.DIRTYPE, b"")],
            [("capture.dmp", tarfile.REGTYPE, data + b"x")],
            [("capture.dmp", tarfile.REGTYPE, data)] * 2,
        )
        for index, members in enumerate(variants):
            with self.subTest(case=index):
                self.output = self.work / f"bad-member-{index}"
                self._bundle(members)
                with self.assertRaisesRegex(RuntimeError, "one regular capture member of the pinned size"):
                    self._measure(bundled=True)
                self.assertFalse((self.output / "report.json").exists())
                self.assertFalse(list(self.output.glob("windows-input-*")))

    def test_bundled_capture_content_hash_is_verified(self):
        self._bundle([("capture.dmp", tarfile.REGTYPE, b"x" * WINDOWS["capture"]["bytes"])])
        with self.assertRaisesRegex(RuntimeError, "Windows bundled capture hash or size mismatch"):
            self._measure(bundled=True)
        self.assertFalse((self.output / "report.json").exists())
        self.assertFalse(list(self.output.glob("windows-input-*")))

    def test_bundle_copies_only_capture_member_to_fresh_directory(self):
        self._bundle([("capture.dmp", tarfile.REGTYPE, self.windows_dump.read_bytes()),
                      ("../escape", tarfile.REGTYPE, b"not extracted"),
                      ("companion.exe", tarfile.REGTYPE, b"not extracted")])
        with patch.object(measurement, "WINDOWS_ARCHIVE_PATH", self.archive_path):
            first = measurement.materialize_windows_capture(self.windows_case, self.work)
            second = measurement.materialize_windows_capture(self.windows_case, self.work)
        self.assertNotEqual(first.parent, second.parent)
        self.assertEqual(first.read_bytes(), self.windows_dump.read_bytes())
        self.assertEqual(list(first.parent.iterdir()), [first])
        self.assertFalse((self.work / "escape").exists())
        self.assertFalse((self.work / "companion.exe").exists())

    def test_exact_decoded_count_and_unique_sites_are_required(self):
        for change in ("missing", "extra", "duplicate"):
            with self.subTest(change=change):
                self.output = self.work / f"decoded-{change}"

                def mutate(report):
                    decoded = report["analysis"]["decoded"]
                    if change == "missing":
                        decoded.pop()
                    elif change == "extra":
                        decoded.append("0x0000000140002000")
                    else:
                        decoded[-1] = decoded[0]

                self._assert_windows_report_rejected(mutate, "Windows producer/seed acceptance failed")

    def _assert_windows_report_rejected(self, mutation, message):
        self.windows_report_mutation = mutation
        with self.assertRaisesRegex(RuntimeError, message):
            self._measure()
        self.assertFalse((self.output / "report.json").exists())

    def test_wrong_windows_report_artifact_is_rejected(self):
        self._assert_windows_report_rejected(
            lambda report: report["identity"].update(artifact_sha256="0" * 64),
            "query/artifact mismatch",
        )

    def test_wrong_windows_report_query_is_rejected(self):
        for field in ("entries", "seeds"):
            with self.subTest(field=field):
                self.output = self.work / field
                self._assert_windows_report_rejected(
                    lambda report: report["query"].update({field: ["0x0000000000401000"]}),
                    "query/artifact mismatch",
                )

    def test_missing_windows_slice_producer_is_rejected(self):
        self._assert_windows_report_rejected(
            lambda report: report["analysis"]["slice"].remove(WINDOWS["query"]["producer_va"]),
            "Windows producer/seed acceptance failed",
        )

    def test_wrong_windows_reaching_producer_is_rejected(self):
        self._assert_windows_report_rejected(
            lambda report: report["analysis"]["reaching"][0]["definitions"][0].update(
                site=WINDOWS["query"]["seed_va"]),
            "Windows independent address-origin witness failed",
        )

    def test_missing_windows_reaching_byte_is_rejected(self):
        self._assert_windows_report_rejected(
            lambda report: report["analysis"]["reaching"][0]["definitions"].pop(),
            "Windows independent address-origin witness failed",
        )

    def test_noninstruction_windows_origin_is_rejected(self):
        self._assert_windows_report_rejected(
            lambda report: report["analysis"]["reaching"][0]["definitions"][0].update(
                origin="entry"),
            "Windows independent address-origin witness failed",
        )

    def test_noncaptured_windows_decoded_bytes_are_rejected(self):
        self._assert_windows_report_rejected(
            lambda report: report["preparation"]["sites"][0].update(byte_source="file"),
            "Windows decoded bytes lack captured provenance",
        )

    def test_missing_windows_decoded_preparation_is_rejected(self):
        for missing in ("one", "all"):
            with self.subTest(missing=missing):
                self.output = self.work / f"missing-preparation-{missing}"
                self._assert_windows_report_rejected(
                    lambda report: (report["preparation"]["sites"].pop()
                                    if missing == "one" else report["preparation"]["sites"].clear()),
                    "Windows decoded bytes lack captured provenance",
                )

    def test_duplicate_windows_decoded_preparation_is_rejected(self):
        for byte_source in ("captured", "file"):
            with self.subTest(byte_source=byte_source):
                self.output = self.work / f"duplicate-preparation-{byte_source}"
                self._assert_windows_report_rejected(
                    lambda report: report["preparation"]["sites"].append({
                        **report["preparation"]["sites"][0], "byte_source": byte_source,
                    }),
                    "Windows decoded bytes lack captured provenance",
                )

    def test_unlimited_budget_accepts_slow_valid_workloads(self):
        for median, target_met in ((2000, True), (2001, True), (10667.760921, True), (1000000, True)):
            with self.subTest(median=median):
                self.output = self.work / f"budget-{median}"
                self.elapsed_ms = median
                self._measure()
                record = self._record()
                self.assertTrue(record["passed"])
                self.assertTrue(record["sourcesStable"])
                self.assertIsNone(record["windowsWorkloadBudgetMs"])
                self.assertEqual(record["windowsWorkloadTargetMet"], target_met)
                self.assertEqual(record["defaultPromotionEligible"], target_met)


if __name__ == "__main__":
    unittest.main()
