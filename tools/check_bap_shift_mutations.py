#!/usr/bin/env python3
"""Source-bound shift compatibility mutations; execute builds only in remote WSL.

Five Rust mutants have private SUTs and release targets. --native additionally
builds separate control/mutant analysis helpers for the captured guarded XORPS
observer. Every observation requires the exact nonempty control to pass first;
compile errors, timeouts and unrelated panics never qualify. A named semantic
rejection is accepted only with its explicit expected diagnostic. Rust build
trees are discarded after executable hashes are recorded by default.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import check_guard_admission_mutations as common
from rust_layout import ROOT, copy_sut


UNIT_SOURCE = "tests/bap/shift_projection_unit.rs"
UNIT_PREFIX = "bap::shift_projection_tests::"
NATIVE_SOURCE = "tests/input/bap_core.rs"
NATIVE_TEST = "captured_xorps_shift_width_has_guarded_native_parity_and_rejects_rehashed_nonshift"
ADMISSION = "src/bap/admission.rs"
PROJECTION = "src/bap/projection.rs"
SHIFT_GATE = "let ty = if matches!(op, 9..=11) { l } else { same(l, r)? };"
MUTATIONS = [
    {
        "name": "restore-equal-width-shift-gate", "source": ADMISSION,
        "edits": [(SHIFT_GATE, "let ty = same(l, r)?; // mutant: reject independent shift counts")],
        "test": "captured_xorps_retains_legacy_upper_half_and_coarse_old_origins",
        "diagnostic": "BIL operand type/width mismatch",
        "panic_anchor": 'let p = projection::project(&bil, "XORPSrr", &[0x0f, 0x57, 0xc0], 0x7ff7744075b3).unwrap();',
        "contract": "The original captured XORPS lift accepts its 128-bit value and eight-bit count.",
    },
    {
        "name": "allow-unequal-nonshift-operands", "source": ADMISSION,
        "edits": [(SHIFT_GATE, "let ty = l; // mutant: permit every unequal binary width")],
        "test": "independent_count_width_is_valid_but_nonshift_width_mismatches_stay_invalid",
        "diagnostic": "nonshift 0",
        "panic_anchor": 'assert!(admission::capabilities(&bil).is_err(), "nonshift {op}");',
        "contract": "Only the three BIL shift operators have independent operand widths.",
    },
    {
        "name": "mask-shift-count-modulo-value-width", "source": PROJECTION,
        "edits": [("right.bounded_shift_count(l.len())",
                   "right.bounded_shift_count(l.len()).map(|count| count % l.len())")],
        "test": "a_known_oversized_count_erases_data_origins_without_modulo_reduction",
        "diagnostic": "wide count was truncated or wrapped for op 10",
        "panic_anchor": 'assert!(\n            p.uses.is_empty(),\n            "wide count was truncated or wrapped for op {op}"',
        "contract": "Oversized BIL counts saturate to fill outcomes rather than becoming count zero.",
    },
    {
        "name": "truncate-shift-count-to-64-bits", "source": PROJECTION,
        "edits": [("for (index, bit) in bits.iter().enumerate() {",
                   "for (index, bit) in bits.iter().take(64).enumerate() { // mutant: discard high count bits")],
        "test": "full_unsigned_counts_and_boundary_fills_match_the_independent_integer_oracle",
        "panic_anchor": 'assert_eq!(\n                p.uses,\n                gpr(if hex_bit(expected, bit) { "rbx" } else { "rcx" })',
        "contract": "All count bits, including those above bit 63, determine the fill outcome.",
    },
    {
        "name": "cancel-xor-from-abstract-metadata-equality", "source": PROJECTION,
        "edits": [("if *op == 6 && justified_equal(lhs, rhs, l, r) {",
                   "if *op == 6 && (l == r || justified_equal(lhs, rhs, l, r)) { // mutant: dependencies are value identity")],
        "test": "equal_abstract_metadata_does_not_prove_computed_values_equal",
        "diagnostic": "different expressions falsely cancelled",
        "panic_anchor": 'assert!(\n        p.uses.is_superset(&gpr("rbx")),\n        "different expressions falsely cancelled"',
        "contract": "Distinct expressions with equal origin metadata retain their possible dependencies.",
    },
]
NATIVE_MUTATION = {
    "name": "native-restore-equal-width-shift-gate",
    "source": "native/bap-core/guard.ml",
    "edits": [("let ty=if List.mem op [9;10;11] then left else equal_type left right in",
               "let ty=equal_type left right in (* mutant: reject independent shift counts *)")],
    "test": NATIVE_TEST, "diagnostic": "guard coverage/stop mismatch",
    "panic_anchor": 'let native = NativeAnalyzer::from_capture(&config(), "guarded-shift-parity", &prepared)\n        .unwrap()',
    "panic_offset": 1,
    "contract": "The independent native type gate agrees with the valid captured mixed-width lift.",
}


def source_inventory():
    paths = common.source_inventory()
    paths[str(Path(__file__).relative_to(ROOT))] = common.sha256(__file__)
    return dict(sorted(paths.items()))


def observer_binding(spec):
    path = NATIVE_SOURCE if spec is NATIVE_MUTATION else UNIT_SOURCE
    source = (ROOT / path).read_text()
    anchor = spec["panic_anchor"]
    if source.count(anchor) != 1:
        raise ValueError(f'{spec["name"]}: expected one observer panic anchor')
    line = source[:source.index(anchor)].count("\n") + 1 + spec.get("panic_offset", 0)
    return path, line


def check_seams(native=False):
    selected = [*MUTATIONS, *([NATIVE_MUTATION] if native else [])]
    for spec in selected:
        common.apply_mutation((ROOT / spec["source"]).read_text(), spec)
        observer = ROOT / (NATIVE_SOURCE if spec is NATIVE_MUTATION else UNIT_SOURCE)
        count = len(re.findall(rf"(?m)^fn {re.escape(spec['test'])}\(\)", observer.read_text()))
        if count != 1:
            raise ValueError(f'{spec["name"]}: exact observer occurs {count} times')
        observer_binding(spec)
    return {"seamsUnique": True, "cargoInvoked": False, "nativeBuildInvoked": False,
            "mutations": [{"name": s["name"], "source": s["source"],
                           "test": s["test"], "diagnostic": s.get("diagnostic"),
                           "panicObserver": observer_binding(s),
                           "contract": s["contract"]} for s in selected]}


def failed_evidence(output, code, test, diagnostic=None):
    evidence = common.test_evidence(output, code, test, "FAILED")
    spec = next((s for s in [*MUTATIONS, NATIVE_MUTATION]
                 if test == (s["test"] if s is NATIVE_MUTATION else UNIT_PREFIX + s["test"])), None)
    if spec is None:
        raise ValueError(f"no bound mutation observer: {test}")
    observer, line = observer_binding(spec)
    # Rust's custom assert! message need not contain the word 'assertion'. Bind
    # it to this exact test's panic location, not a diagnostic elsewhere in a log.
    panics = re.finditer(
        r"(?m)^thread '([^']+)'(?: \(\d+\))? panicked at ([^\r\n]+):(\d+):(\d+):\r?\n"
        r"([\s\S]*?)(?=\r?\n(?:note:|stack backtrace:|failures:|test result:|thread ')|\Z)",
        output,
    )
    matching = [p for p in panics if p.group(1) == test
                and (p.group(2) == observer or p.group(2).endswith("/" + observer))
                and int(p.group(3)) == line]
    panic_bound = len(matching) == 1
    semantic = False
    if diagnostic is not None:
        summary = re.search(r"(?m)^test result: FAILED\. 0 passed; 1 failed; 0 ignored;", output)
        semantic = (code == 101 and evidence["cleanBuild"]
                    and evidence["observedTests"] == [(test, "FAILED")]
                    and summary is not None and panic_bound
                    and diagnostic in matching[0].group(5))
    evidence["expectedDiagnostic"] = diagnostic
    evidence["semanticRejectionMatched"] = semantic
    evidence["panicObserver"] = observer
    evidence["panicLine"] = line
    evidence["panicObserverMatched"] = panic_bound
    # A declared semantic observer must fail for that reason, even if some
    # unrelated assertion in the same larger test also happened to fail.
    evidence["qualified"] = semantic if diagnostic is not None else evidence["qualified"] and panic_bound
    return evidence


def command(manifest, build, test, native):
    return ["cargo", "test", "--offline", "--locked", "--release",
            "--manifest-path", str(manifest), "--target-dir", str(build),
            *(["--test", "input_bap_core"] if native else ["--lib"]),
            test, "--", "--exact", *(["--include-ignored"] if native else []),
            "--test-threads=1"]


def binaries(build, native):
    prefix = "input_bap_core-" if native else "ariadne-"
    return {str(p.relative_to(build)): common.sha256(p)
            for p in sorted((build / "release/deps").glob(prefix + "*"))
            if p.is_file() and not p.is_symlink() and os.access(p, os.X_OK)}


def run_test(directory, manifest, build, test, native, env, label, timeout, diagnostic):
    cmd = command(manifest, build, test, native)
    started = time.monotonic()
    try:
        result = subprocess.run(cmd, cwd=manifest.parent, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        output, code = result.stdout, result.returncode
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        output += f"\nTIMEOUT after {timeout} seconds\n"
        code = None
    log = directory / (label + ".log")
    log.write_text(output)
    identities = binaries(build, native)
    control = common.test_evidence(output, code, test, "ok")
    mutant = failed_evidence(output, code, test, diagnostic)
    return {"command": cmd, "exitCode": code, "seconds": time.monotonic() - started,
            "log": str(log), "logSha256": common.sha256(log), "testBinaries": identities,
            "controlEvidence": control, "mutantEvidence": mutant,
            "passed": control["qualified"] and bool(identities),
            "runtimeRejected": mutant["qualified"] and bool(identities)}


def build_helper(directory, sources, label, timeout):
    output = directory / label
    cmd = ["python3", str(ROOT / "native/bap-core/build.py"),
           "--source-dir", str(sources), "--output", str(output)]
    try:
        result = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, timeout=timeout)
        text, code = result.stdout, result.returncode
    except subprocess.TimeoutExpired as error:
        text = error.stdout or ""
        if isinstance(text, bytes):
            text = text.decode(errors="replace")
        text += f"\nTIMEOUT after {timeout} seconds\n"
        code = None
    log = directory / (label + "-build.log")
    log.write_text(text)
    helper, manifest = output / "ariadne-bap-core", output / "manifest.json"
    record = {"command": cmd, "exitCode": code, "logSha256": common.sha256(log),
              "helperSha256": common.sha256(helper) if helper.is_file() else None,
              "manifestSha256": common.sha256(manifest) if manifest.is_file() else None,
              "manifest": json.loads(manifest.read_text()) if manifest.is_file() else None}
    return output, record, code == 0 and helper.is_file() and manifest.is_file()


def run_mutation(output, spec, args, seed, env, before):
    native = spec is NATIVE_MUTATION
    directory = output / spec["name"]
    directory.mkdir()
    sut = directory / "sut"
    manifest = copy_sut(sut)
    if native:
        shutil.copytree(ROOT / "native/bap-core", sut / "native/bap-core")
    sources = common.tree_inventory(sut)
    observers = {p: digest for p, digest in sources.items() if p.startswith("tests/")}
    target = sut / spec["source"]
    original = target.read_bytes()
    mutant = common.apply_mutation(original.decode(), spec).encode()
    test = spec["test"] if native else UNIT_PREFIX + spec["test"]
    record = {"name": spec["name"], "contract": spec["contract"], "source": spec["source"],
              "test": test, "originalSha256": hashlib.sha256(original).hexdigest(),
              "mutatedSha256": hashlib.sha256(mutant).hexdigest(),
              "sutSourceHashes": sources, "observerHashes": observers,
              "control": None, "mutant": None, "helperBuilds": [],
              "sourceRestored": False, "observersUnchanged": False, "sutSourcesRestored": False,
              "passed": False}
    (directory / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    build = directory / "build"
    try:
        common.seed_release_cache(build, seed)
        # Cache dependency artifacts, but force this copied package to compile.
        # A package fingerprint from another SUT is never evidence for this one.
        package_fingerprints = []
        for fingerprint in sorted((build / "release/.fingerprint").glob("ariadne-analysis-*")):
            package_fingerprints.append(str(fingerprint.relative_to(build)))
            if fingerprint.is_dir():
                shutil.rmtree(fingerprint)
            elif fingerprint.exists():
                fingerprint.unlink()
        record["discardedSeedPackageFingerprints"] = package_fingerprints
        target.write_bytes(original)
        if native:
            # The native source is not a Rust include dependency. Refresh the
            # copied integration observer so a seed cannot reuse an executable
            # whose CARGO_MANIFEST_DIR still names another checkout.
            os.utime(sut / NATIVE_SOURCE, None)
        control_env = env.copy()
        if native:
            helper_dir, helper_record, ready = build_helper(
                directory, sut / "native/bap-core", "control-helper", args.timeout_seconds)
            record["helperBuilds"].append(helper_record)
            if not ready:
                raise RuntimeError(f'{spec["name"]}: unmodified helper build failed')
            control_env["ARIADNE_BAP_CORE_DIR"] = str(helper_dir)
        control = run_test(directory, manifest, build, test, native, control_env,
                           "control", args.timeout_seconds, spec.get("diagnostic"))
        record["control"] = control
        if not control["passed"]:
            raise RuntimeError(f'{spec["name"]}: exact unmodified control did not pass')
        target.write_bytes(mutant)
        mutant_env = env.copy()
        if native:
            helper_dir, helper_record, ready = build_helper(
                directory, sut / "native/bap-core", "mutant-helper", args.timeout_seconds)
            record["helperBuilds"].append(helper_record)
            if not ready:
                raise RuntimeError(f'{spec["name"]}: mutant helper build failed; no mutation credit')
            mutant_env["ARIADNE_BAP_CORE_DIR"] = str(helper_dir)
        changed = run_test(directory, manifest, build, test, native, mutant_env,
                           "mutant", args.timeout_seconds, spec.get("diagnostic"))
        record["mutant"] = changed
        if not changed["runtimeRejected"]:
            raise RuntimeError(f'{spec["name"]}: expected named runtime rejection absent')
        if source_inventory() != before:
            raise RuntimeError("root source inventory changed during campaign")
        record["passed"] = True
    finally:
        target.write_bytes(original)
        restored = common.tree_inventory(sut)
        record["sourceRestored"] = common.sha256(target) == record["originalSha256"]
        record["observersUnchanged"] = all(restored.get(p) == digest for p, digest in observers.items())
        record["sutSourcesRestored"] = restored == sources
        record["buildDiscarded"] = not args.keep_builds
        if not args.keep_builds and build.exists():
            shutil.rmtree(build)
        record["passed"] = record["passed"] and all(record[k] for k in (
            "sourceRestored", "observersUnchanged", "sutSourcesRestored"))
        (directory / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    if not record["passed"]:
        raise RuntimeError(f'{spec["name"]}: SUT source or observer restoration failed')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-seams", action="store_true")
    parser.add_argument("--output", type=Path, help="new child directory under repository target/")
    parser.add_argument("--native", action="store_true", help="also build/run the isolated native type-gate mutant")
    parser.add_argument("--seed-build-dir", type=Path)
    parser.add_argument("--keep-builds", action="store_true")
    parser.add_argument("--build-jobs", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--helper", type=Path, default=ROOT / "target/ariadne-bap-lift")
    parser.add_argument("--decoder", type=Path, default=ROOT / "target/ariadne-llvm-mc")
    parser.add_argument("--runtime-root", type=Path, default=ROOT / "tmp/bap-setup/stable")
    args = parser.parse_args()
    seams = check_seams(args.native)
    if args.check_seams:
        print(json.dumps(seams, indent=2))
        return
    if args.output is None:
        parser.error("--output is required unless --check-seams is selected")
    if args.build_jobs <= 0 or args.timeout_seconds <= 0:
        parser.error("build jobs and timeout must be positive")
    output, target_root = args.output.resolve(), (ROOT / "target").resolve()
    if output == target_root or not output.is_relative_to(target_root):
        parser.error("--output must be a new child directory under target/")
    seed = args.seed_build_dir.resolve() if args.seed_build_dir else None
    if seed is not None and (not seed.is_dir() or seed == output
                             or seed.is_relative_to(output) or output.is_relative_to(seed)):
        parser.error("release seed must exist separately from campaign output")
    env = {**os.environ, "CARGO_BUILD_JOBS": str(args.build_jobs)}
    tool_hashes = {}
    if args.native:
        for name, path in (("ARIADNE_BAP_HELPER", args.helper), ("ARIADNE_LLVM_MC", args.decoder)):
            path = path.resolve()
            if not path.is_file():
                parser.error(f"native campaign requires helper: {path}")
            env[name], tool_hashes[name] = str(path), common.sha256(path)
        runtime = args.runtime_root.resolve()
        if not runtime.is_dir():
            parser.error(f"native campaign requires runtime: {runtime}")
        env["BAP_RUNTIME_ROOT"] = str(runtime)
    output.mkdir(parents=True, exist_ok=False)
    before = source_inventory()
    selected = [*MUTATIONS, *([NATIVE_MUTATION] if args.native else [])]
    records = []
    report = {"schema": "ariadne.bap-shift-mutations/v1", "sourceHashes": before,
              "expectedMutations": [s["name"] for s in selected], "nativeSelected": args.native,
              "release": True, "seedBuildDir": str(seed) if seed else None,
              "helperHashes": tool_hashes, "mutations": records, "sourcesStable": False,
              "passed": False}
    failure = None
    try:
        for spec in selected:
            try:
                record = run_mutation(output, spec, args, seed, env, before)
            except (RuntimeError, ValueError, OSError, subprocess.SubprocessError):
                retained = output / spec["name"] / "result.json"
                if retained.is_file():
                    records.append(json.loads(retained.read_text()))
                raise
            records.append(record)
            print(f'{spec["name"]}: expected named runtime rejection', flush=True)
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
        failure = str(error)
    finally:
        report["sourcesStable"] = before == source_inventory()
        report["passed"] = (failure is None and report["sourcesStable"]
                            and len(records) == len(selected) and all(r["passed"] for r in records))
        if failure is not None:
            report["failure"] = failure
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f'Report: {output / "report.json"}', flush=True)
    if not report["passed"]:
        raise SystemExit(failure or "root source inventory changed during campaign")


if __name__ == "__main__":
    main()
