#!/usr/bin/env python3
"""Remote-only caller-coverage qualification. Preparing this file executes nothing.

Run inside the task's existing /caller-work wrapper. Prior model and native
controls may be retained only after their exact exercised source/tool/input
identities are rechecked. Full application/root regressions run freshly.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path("/home/nzsn/Repos/Ariadne-caller-coverage-20261015")
TASK = Path(__file__).resolve().parent


def sha(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def compact_copy(source, destination):
    """Retain logs, executed source mutants and data; hash omitted build files."""
    destination.mkdir(parents=True, exist_ok=False)
    inventory = {}
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        inventory[str(relative)] = sha(path)
        if path.suffix in {".json", ".log", ".stdout", ".stderr", ".ml", ".diff", ".rs", ".py", ".txt"}:
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    write(destination / "complete-artifact-hashes.json", inventory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--early-evidence", type=Path, required=True)
    parser.add_argument("--model-evidence", type=Path, required=True)
    parser.add_argument("--native-controls-result", type=Path)
    parser.add_argument("--root-evidence", type=Path, help="retain completed exact-snapshot root gates instead of duplicating them")
    parser.add_argument("--skip-native-capture", action="store_true", help="continue after an explicitly recorded failed capture gate; never grants full acceptance")
    parser.add_argument("--retained-prefix", type=Path, help="exact-snapshot earlier prefix whose layout/kernels/protocol passed")
    parser.add_argument("--receipt-dir", type=Path)
    parser.add_argument("--wire-dir", type=Path)
    parser.add_argument("--source-manifest", type=Path, default=Path("/caller-work/source-manifest.json"))
    parser.add_argument("--native-dir", type=Path, default=ROOT / "target/caller-native")
    parser.add_argument("--cargo-target", type=Path, default=ROOT / "target/caller-build")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    if args.skip_native_capture != (args.retained_prefix is not None):
        parser.error("--skip-native-capture and --retained-prefix must be used together")
    if Path.cwd() != ROOT or not Path("/caller-work").is_dir():
        raise SystemExit("run only inside the task's existing remote WSL /caller-work wrapper")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + str(os.getpid())
    out = Path("/caller-work/evidence") / ("qualification-" + stamp)
    out.mkdir(parents=True, exist_ok=False)
    build = ROOT / "target" / ("caller-qualification-" + stamp)
    build.mkdir(parents=True, exist_ok=False)
    print("Qualification artifacts:", out, flush=True)
    print("Isolated checker/replay/mutant builds:", build, flush=True)
    manifest = read(args.source_manifest)
    write(out / "source-manifest.json", manifest)
    write(out / "task-driver-hashes.json", {path.name: sha(path) for path in
          (Path(__file__), TASK / "core-replay.py", TASK / "opaque-mutations.py", TASK / "legacy-guard-probe.rs")})
    receipts = (args.receipt_dir or args.early_evidence / "caller-receipts").resolve()
    wires = (args.wire_dir or args.early_evidence / "caller-wires").resolve()
    environment = {**os.environ, "CARGO_TARGET_DIR": str(args.cargo_target), "CARGO_INCREMENTAL": "0",
                   "CARGO_PROFILE_DEV_DEBUG": "0", "CARGO_PROFILE_TEST_DEBUG": "0", "CARGO_BUILD_JOBS": str(args.jobs),
                   "ARIADNE_BAP_CORE_DIR": str(args.native_dir),
                   "ARIADNE_BAP_HELPER": str(ROOT / "target/ariadne-bap-lift"),
                   "BAP_RUNTIME_ROOT": str(ROOT / "tmp/bap-setup/stable"),
                   "ARIADNE_LLVM_MC": str(ROOT / "target/caller-llvm/ariadne-llvm-mc"),
                   "ARIADNE_LEGACY_COMPOSED_MINIDUMP": "/caller-work/legacy/v1-minidump.json",
                   "ARIADNE_LEGACY_COMPOSED_FRAME": "/caller-work/legacy/v1-frame.json",
                   "ARIADNE_LEGACY_V2_COMPOSED_MINIDUMP": "/caller-work/legacy/v2-minidump.json",
                   "ARIADNE_LEGACY_V2_COMPOSED_FRAME": "/caller-work/legacy/v2-frame.json",
                   "TMPDIR": "/caller-work/tmp"}
    # Qualification must not silently regenerate the prior exported inputs.
    environment.pop("ARIADNE_CALLER_RECEIPT_DIR", None)
    environment.pop("ARIADNE_CALLER_WIRE_DIR", None)
    gates = []

    def verify_sources():
        for name, identity in manifest["files"].items():
            if sha(ROOT / name) != identity:
                raise RuntimeError("qualification source snapshot differs: " + name)

    def run(name, command, tests=False, extra=None, timeout=7200):
        start = time.monotonic()
        print("Gate:", name, flush=True)
        selected = {**environment, **(extra or {})}
        if name == "layout":
            selected.pop("CARGO_TARGET_DIR", None)
        code = -1
        try:
            with (out / (name + ".log")).open("w") as log:
                completed = subprocess.run([str(value) for value in command], cwd=ROOT, env=selected,
                                           stdout=log, stderr=subprocess.STDOUT, timeout=timeout)
                code = completed.returncode
            text = (out / (name + ".log")).read_text(errors="replace")
        except (OSError, subprocess.TimeoutExpired) as error:
            text = str(error)
            (out / (name + ".log")).write_text(text + "\n")
        passed = code == 0
        counts = [int(value) for value in re.findall(r"test result: ok\. ([0-9]+) passed", text)]
        if tests:
            passed &= sum(counts) > 0
        record = {"name": name, "command": [str(value) for value in command], "exit_code": code,
                  "passed": passed, "tests_passed": sum(counts) if tests else None,
                  "seconds": time.monotonic() - start}
        gates.append(record)
        write(out / "gates.json", gates)
        print(name, "PASS" if passed else "FAIL", flush=True)
        if not passed:
            print(text[-8000:], flush=True)
            raise RuntimeError("qualification gate failed: " + name)
        return text

    def retained_models():
        prior = read(args.model_evidence / "source-manifest.json")
        selected = {name: identity for name, identity in manifest["files"].items()
                    if name.startswith(("Specs/PredicateAdmission", "tests/bap/fixtures/caller-coverage/",
                                        "tests/bap/fixtures/guards/"))
                    or name in {"Specs/AriadnePredicateAdmission.tla", "Specs/check-predicate-admission.sh"}}
        for name, identity in selected.items():
            if prior["files"].get(name) != identity:
                raise RuntimeError("retained 58-model source changed: " + name)
        status_path = args.model_evidence / "predicate-model.json"
        if not status_path.exists():
            status_path = args.model_evidence / "result.json"
        if read(status_path).get("exit_code") != 0:
            raise RuntimeError("retained predicate-model gate did not pass")
        log = args.model_evidence / "predicate-model.log"
        if "Predicate admission: 58 configurations passed safety and fair termination." not in log.read_text():
            raise RuntimeError("retained model log does not establish all 58 configurations")
        write(out / "retained-model-evidence.json", {"status": "retained-source-bound-pass", "configurations": 58,
              "evidence": str(args.model_evidence), "manifest_sha256": sha(args.model_evidence / "source-manifest.json"),
              "status_sha256": sha(status_path), "log_sha256": sha(log), "source_files": selected,
              "fresh_model_execution": False})

    def verify_native_identity():
        native = read(args.native_dir / "manifest.json")
        handshake = native["handshake"]
        for name, identity in handshake["source_hashes"].items():
            if sha(ROOT / "native/bap-core" / name) != identity:
                raise RuntimeError("native helper source identity changed: " + name)
        guard = hashlib.sha256(("ariadne.guard-checker/v2\n" + sha(ROOT / "src/bap/guard_admission.rs") + "\n"
                                + sha(ROOT / "src/bap/terminal_control.rs") + "\n").encode()).hexdigest()
        if handshake["guard_engine_sha256"] != guard:
            raise RuntimeError("native helper requires rebuild for current Rust checker identity")
        guard_model = sha(ROOT / "Specs/AriadnePredicateAdmission.tla")
        loop_model = sha(ROOT / "Specs/AriadneLoopTargetClosure.tla")
        loop_engine = hashlib.sha256(("ariadne.loop-target-engine/v1\n" + sha(ROOT / "src/bap/target_resolution.rs")
                    + "\n" + sha(ROOT / "src/bap/target_resolution/loop_closure.rs") + "\n").encode()).hexdigest()
        composition_model = hashlib.sha256(("ariadne.guarded-target-model/v3\n"
                    + sha(ROOT / "Specs/AriadneGuardedTargetResolution.tla") + "\n" + loop_model + "\n" + guard_model + "\n").encode()).hexdigest()
        composition_engine = hashlib.sha256(("ariadne.guarded-target-checker/v3\n"
                    + sha(ROOT / "src/bap/composition.rs") + "\n" + loop_engine + "\n" + guard + "\n").encode()).hexdigest()
        for key, identity in (("guard_model_sha256", guard_model), ("loop_model_sha256", loop_model),
                              ("loop_engine_sha256", loop_engine), ("composition_model_sha256", composition_model),
                              ("composition_engine_sha256", composition_engine)):
            if handshake[key] != identity:
                raise RuntimeError("native helper requires current proof identity: " + key)
        if sha(args.native_dir / "ariadne-bap-core") != native["helper_sha256"]:
            raise RuntimeError("native helper binary identity differs")
        return native

    def retain_root_checks():
        prior = read(args.root_evidence / "source-manifest.json")
        if prior["files"] != manifest["files"]:
            raise RuntimeError("root checks used a different complete source snapshot")
        required = {"format", "default-tests", "core-only-tests", "clippy", "release-build"}
        rows = read(args.root_evidence / "gates.json")
        selected = [row for row in rows if row["name"] in required]
        if {row["name"] for row in selected} != required or any(row["exit_code"] != 0 for row in selected):
            raise RuntimeError("root checks are incomplete or failed; no reuse credit")
        for name in ("default-tests", "core-only-tests"):
            text = (args.root_evidence / (name + ".log")).read_text(errors="replace")
            if not re.search(r"test result: ok\. [1-9][0-9]* passed", text):
                raise RuntimeError("root checks dispatched no positive tests: " + name)
        write(out / "retained-root-checks.json", {"status": "retained-exact-snapshot-pass",
              "source": str(args.root_evidence), "source_manifest_sha256": sha(args.root_evidence / "source-manifest.json"),
              "gates": selected, "uncredited_prior_gates": [row for row in rows if row["name"] not in required],
              "fresh_layout_gate": "layout.log",
              "logs": {row["name"]: sha(args.root_evidence / (row["name"] + ".log")) for row in selected}})

    def retain_prefix():
        prior = read(args.retained_prefix / "source-manifest.json")
        if prior["files"] != manifest["files"]:
            raise RuntimeError("continuation prefix used a different complete source snapshot")
        rows = read(args.retained_prefix / "gates.json")
        required = {"layout", "native-kernels", "native-producer-protocol"}
        selected = [row for row in rows if row["name"] in required]
        if {row["name"] for row in selected} != required or any(not row["passed"] for row in selected):
            raise RuntimeError("continuation prefix is missing a passing layout/kernel/protocol gate")
        capture = [row for row in rows if row["name"] == "native-capture"]
        if len(capture) != 1 or capture[0]["passed"] or capture[0]["exit_code"] == 0:
            raise RuntimeError("continuation requires the explicit failed native-capture record")
        write(out / "retained-prefix.json", {"status": "partial-prefix-retained-capture-pending",
              "source": str(args.retained_prefix), "source_manifest_sha256": sha(args.retained_prefix / "source-manifest.json"),
              "passing_gates": selected, "pending_gate": capture[0],
              "logs": {row["name"]: sha(args.retained_prefix / (row["name"] + ".log")) for row in selected + capture}})

    def retain_native_controls(path):
        result = read(path)
        if (not result.get("passed") or len(result["baseline"]["rows"]) != 88
                or len(result["production_protocol"]) != 24 or len(result["mutants"]) != 9
                or result["behavioral_mutant_credits"] != 9
                or not all(row["passed"] for row in result["baseline"]["rows"] + result["production_protocol"])):
            raise RuntimeError("retained native controls do not contain 88 + 24 passes and nine behavioral mutants")
        for name, identity in result["source_sha256"].items():
            if sha(ROOT / "native/bap-core" / name) != identity:
                raise RuntimeError("native controls' exercised source changed: " + name)
        for key, file in (("driver_sha256", "tests/bap/caller_coverage_native.ml"),
                          ("runner_sha256", "tests/bap/caller_coverage_native_controls.py")):
            if result[key] != sha(ROOT / file):
                raise RuntimeError("native controls' exact test harness changed: " + file)
        if result["native_manifest_sha256"] != sha(args.native_dir / "manifest.json"):
            raise RuntimeError("native control helper manifest changed")
        for key, directory in (("receipt_inputs", receipts), ("wire_inputs", wires)):
            for name, identity in result[key].items():
                if sha(directory / name) != identity:
                    raise RuntimeError("native control input changed: " + name)
        for name, identity in result["fixtures"].items():
            if sha(ROOT / name) != identity:
                raise RuntimeError("native control source fixture changed: " + name)
        compact_copy(path.parent, out / "native-controls")
        write(out / "retained-native-controls.json", {"status": "retained-source-tool-input-bound-pass",
              "result": str(path), "result_sha256": sha(path), "direct_controls": 88,
              "production_initialization_controls": 24, "behavioral_mutants": 9,
              "scope": "Actual recorded proof/capture inputs; fresh consumer regressions below are separate."})

    failure = None
    try:
        verify_sources()
        retained_models()
        verify_native_identity()
        # Some existing ignored tests intentionally use this public default path.
        decoder = ROOT / "target/caller-llvm/ariadne-llvm-mc"
        default = ROOT / "target/ariadne-llvm-mc"
        if not default.exists() and not default.is_symlink():
            default.symlink_to("caller-llvm/ariadne-llvm-mc")
        if sha(default) != sha(decoder):
            raise RuntimeError("caller checkout's default LLVM path differs from the private current decoder")
        write(out / "tools.json", {"native_manifest_sha256": sha(args.native_dir / "manifest.json"),
              "native_helper_sha256": sha(args.native_dir / "ariadne-bap-core"),
              "lifter_sha256": sha(ROOT / "target/ariadne-bap-lift"), "decoder_sha256": sha(decoder)})
        if args.native_controls_result:
            retain_native_controls(args.native_controls_result)
        else:
            controls = build / "native-controls"
            run("native-caller-controls", ["python3", ROOT / "tests/bap/caller_coverage_native_controls.py",
                "--native-dir", args.native_dir, "--output", controls, "--receipt-dir", receipts,
                "--wire-dir", wires, "--mutations"])
            retain_native_controls(controls / "result.json")
        if args.root_evidence is None:
            run("format", ["cargo", "fmt", "--all", "--", "--check"])
            run("default-tests", ["cargo", "test", "--offline", "--locked"], tests=True)
            run("core-only", ["cargo", "test", "--offline", "--locked", "--no-default-features"], tests=True)
            run("clippy", ["cargo", "clippy", "--offline", "--locked", "--all-features", "--all-targets", "--", "-D", "warnings"])
            run("frame-proof-removal-regression", ["cargo", "test", "--offline", "--locked", "--lib",
                "investigation::composition_unit::stripped_frame_proofs_cannot_relist_as_plain_reports_with_any_known_profile",
                "--", "--exact"], tests=True)
            run("protocol-codecs", ["cargo", "test", "--offline", "--locked", "--lib", "bap::core_protocol"], tests=True)
        if args.skip_native_capture:
            retain_prefix()
        else:
            run("layout", ["python3", "tools/check_rust_layout.py"])
            run("native-kernels", ["cargo", "test", "--offline", "--locked", "--test", "bap_core_bootstrap",
                "--test", "bap_core_analysis", "--test", "bap_core_stateflow", "--", "--ignored"], tests=True)
            run("native-producer-protocol", ["cargo", "test", "--offline", "--locked", "--test", "bap_protocol",
                "--", "--ignored"], tests=True)
            run("native-capture", ["cargo", "test", "--offline", "--locked", "--test", "input_bap_core", "--", "--ignored"], tests=True)
        frame_log = run("native-frame-paths", ["cargo", "test", "--offline", "--locked", "--test", "input_frame_paths", "--", "--ignored"], tests=True)
        for name in ("retained_combined_v1_minidump_and_frame_reports_replay_after_upgrade",
                     "retained_combined_v2_loop_reports_replay_after_guard_upgrade"):
            if "test " + name + " ... ok" not in frame_log:
                raise RuntimeError("actual retained combined report replay missing: " + name)
        run("native-composition", ["cargo", "test", "--offline", "--locked", "--lib",
            "actual_bap_pending_store_targets_and_native_rust_results_agree", "--", "--ignored"], tests=True)
        run("core-contract-tools", ["python3", "-m", "unittest", "discover", "-s", "tools", "-p", "test_bap_core_contract.py"])
        run("profile-contract-tools", ["python3", "-m", "unittest", "discover", "-s", "tools", "-p", "test_bap_profile_migration.py"])
        run("native-generated-replay", ["python3", TASK / "core-replay.py", "--helper-dir", args.native_dir,
            "--target-dir", build / "replay-build", "--output", out / "generated-replay"])
        run("native-opaque-mutations", ["python3", TASK / "opaque-mutations.py", "--native-dir", args.native_dir,
            "--cargo-target", build / "opaque-mutation-cargo", "--output", build / "opaque-mutations"])
        compact_copy(build / "opaque-mutations", out / "opaque-mutations")
        if args.root_evidence:
            retain_root_checks()
        else:
            run("release-build", ["cargo", "build", "--offline", "--locked", "--release", "--lib"])
        release = args.cargo_target / "release"
        serde = sorted((release / "deps").glob("libserde_json-*.rlib"))
        if not serde:
            raise RuntimeError("release serde_json dependency missing for retained-report probe")
        legacy_probe = build / "legacy-guard-probe"
        run("legacy-guard-probe-build", ["rustc", "--edition=2024", TASK / "legacy-guard-probe.rs", "-O", "-L",
            "dependency=" + str(release / "deps"), "--extern", "ariadne=" + str(release / "libariadne.rlib"),
            "--extern", "serde_json=" + str(serde[0]), "-o", legacy_probe])
        text = run("actual-legacy-guard-v1", [legacy_probe, "/caller-work/legacy/guard-v1.json"])
        write(out / "actual-legacy-guard-v1.json", {**json.loads(text.splitlines()[-1]),
              "probe_sha256": sha(legacy_probe), "source_sha256": sha(TASK / "legacy-guard-probe.rs"),
              "retained_report_sha256": sha(Path("/caller-work/legacy/guard-v1.json"))})
        verify_sources()
    except Exception as error:
        failure = str(error)
        print("Qualification stopped:", failure, flush=True)
    stable = all(sha(ROOT / name) == identity for name, identity in manifest["files"].items())
    pending = ["native-capture"] if args.skip_native_capture else []
    result = {"schema": "ariadne.caller-coverage-qualification/v1", "passed": failure is None and stable and not pending,
              "remaining_gates_passed": failure is None and stable, "pending_gates": pending,
              "recorded_utc": datetime.now(timezone.utc).isoformat(), "source_files_verified": len(manifest["files"]),
              "source_archive_sha256": manifest["archive_sha256"], "sources_stable": stable,
              "gates": gates, "error": failure, "build_output": str(build),
              "scope": "Finite normal-completion/control/effect and native/core/report regressions; actual original dump retry is a separate gate.",
              "fresh_model_run": False, "performance_or_universal_refinement_claim": False}
    write(out / "qualification.json", result)
    print("Qualification:", out / "qualification.json", flush=True)
    if pending:
        print("Continuation only: native-capture remains pending; full qualification is not passed.", flush=True)
    if not result["remaining_gates_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
