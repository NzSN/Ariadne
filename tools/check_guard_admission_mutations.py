#!/usr/bin/env python3
"""Bounded source mutations of the guard checker; run Cargo on remote WSL.

Each mutant has a private SUT and release target tree. Qualification requires a
passing exact unmodified observer and a named assertion failure after mutation;
compile errors, timeouts, empty filters and unrelated panics receive no credit.
Build directories are discarded after executable identities are recorded unless
--keep-builds is selected. No native mutant compilation or dependency fallback
is performed by this runner.
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

from rust_layout import ROOT, copy_sut, source_files


GUARD = "src/bap/guard_admission.rs"
OBSERVER = "tests/bap/guard_admission_unit.rs"
PREFIX = "bap::guard_admission_tests::"
MUTATIONS = [
    {
        "name": "empty-or-top-proves-alignment",
        "source": GUARD,
        "edits": [(
            "let verdict = if !closed {",
            "let verdict = if values == 0 || values == TOP {\n"
            "        Verdict::Aligned // mutant: vacuous/unknown alignment\n"
            "    } else if !closed {",
        )],
        "tests": [
            "direct_guard_verdicts_match_frozen_independent_product_graph",
            "barriers_limits_and_unreached_facts_never_admit_a_normal_outcome",
        ],
        "contract": "Empty and top cannot justify normal admission.",
    },
    {
        "name": "omit-candidate-predecessor-replay",
        "source": GUARD,
        "edits": [(
            "&& apply(relations[edge.src], facts[edge.src]) & !*next != 0",
            "&& false /* mutant: omit the candidate-only predecessor */\n"
            "                && apply(relations[edge.src], facts[edge.src]) & !*next != 0",
        )],
        "tests": ["replay_rejects_omitted_roots_candidate_predecessors_and_tampering"],
        "contract": "Replay must identify an omitted candidate predecessor before verdict validation.",
    },
    {
        "name": "ignore-source-control-barrier",
        "source": GUARD,
        "edits": [(
            ") && !super::admission::ordinary_unknown(&bil, &b, &error)",
            ") && false /* mutant: trust caller Ordinary despite raw source control */\n"
            "            && !super::admission::ordinary_unknown(&bil, &b, &error)",
        )],
        "tests": ["unreviewed_source_control_is_a_barrier_even_with_forged_ordinary_metadata"],
        "contract": "A later RSP reset cannot certify unknown source control.",
    },
    {
        "name": "omit-actual-premise-identities",
        "source": GUARD,
        "edits": [
            ("        &i.premises,", "        &Vec::<Premise>::new(), // mutant: drop actual intent premises"),
            ("        &report.input.premises,", "        &Vec::<Premise>::new(), // mutant: drop actual receipt premises"),
        ],
        "tests": ["final_identity_binds_actual_premises_and_request_without_hash_cycles"],
        "contract": "Actual premise instances belong to intent and receipt identities; policy alone is insufficient.",
    },
    {
        "name": "pending-transfer-needs-normal-projection",
        "source": GUARD,
        "edits": [(
            "let (rule, relation) = if pending.is_some() {",
            "let (rule, relation) = if pending.is_some()\n"
            "        && super::projection::project(\n"
            "            &statements(&site.ast)?, \"MOVAPS-reviewed-store\", &b, address(&site.site)?\n"
            "        ).is_ok() { // mutant: require admitted effects before independent pending transfer",
        )],
        "tests": ["joined_paths_and_changing_loops_prevent_false_alignment"],
        "contract": "The checked candidate RSP relation precedes normal selection and permits identity-loop closure.",
    },
    {
        "name": "normal-store-kills-old-memory",
        "source": "src/bap/projection.rs",
        "edits": [(
            'may_defs.insert("memory:any".into());',
            'may_defs.insert("memory:any".into());\n'
            '            definite.insert("memory:any".into()); // mutant: turn possible store into must kill',
        )],
        "tests": ["selected_normal_store_retains_weak_memory_definition_and_original_source"],
        "contract": "Selecting the normal store retains its empty memory must-def set.",
    },
]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_inventory():
    paths = source_files() | {Path(__file__)}
    for tree in ("native/bap", "native/bap-core"):
        paths.update(p for p in (ROOT / tree).rglob("*")
                     if p.is_file() and p.suffix != ".md"
                     and "__pycache__" not in p.parts)
    return {str(p.relative_to(ROOT)): sha256(p) for p in sorted(paths)}


def tree_inventory(sut):
    return {str(p.relative_to(sut)): sha256(p) for p in sorted(sut.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts}


def apply_mutation(original, spec):
    changed = original
    for old, new in spec["edits"]:
        count = changed.count(old)
        if count != 1:
            raise ValueError(f'{spec["name"]}: expected one source anchor, found {count}: {old!r}')
        changed = changed.replace(old, new, 1)
    if changed == original:
        raise ValueError(f'{spec["name"]}: mutation changed no source bytes')
    return changed


def check_seams():
    observer = (ROOT / OBSERVER).read_text()
    for spec in MUTATIONS:
        apply_mutation((ROOT / spec["source"]).read_text(), spec)
        for name in spec["tests"]:
            count = len(re.findall(rf"(?m)^fn {re.escape(name)}\(\)", observer))
            if count != 1:
                raise ValueError(f'{spec["name"]}: exact observer {name} occurs {count} times')
    return {
        "seamsUnique": True,
        "cargoInvoked": False,
        "mutations": [{"name": s["name"], "source": s["source"],
                       "tests": [PREFIX + n for n in s["tests"]],
                       "contract": s["contract"]} for s in MUTATIONS],
    }


def command(manifest, build, test):
    return ["cargo", "test", "--offline", "--locked", "--release",
            "--manifest-path", str(manifest), "--target-dir", str(build),
            "--lib", test, "--", "--exact", "--test-threads=1"]


def test_evidence(output, code, test, expected):
    matches = re.findall(r"(?m)^test ([A-Za-z0-9_:]+) \.\.\. (ok|FAILED)$", output)
    assertion = bool(re.search(r"assertion[^\n]*failed", output))
    clean_build = not any(marker in output for marker in (
        "could not compile", "error[E", "error: linker", "linking with", "TIMEOUT",
    ))
    summary = re.search(
        rf"(?m)^test result: {'ok' if expected == 'ok' else 'FAILED'}\. "
        rf"{1 if expected == 'ok' else 0} passed; {0 if expected == 'ok' else 1} failed; 0 ignored;",
        output,
    )
    valid = (code == (0 if expected == "ok" else 101)
             and matches == [(test, expected)] and clean_build
             and summary is not None and (expected == "ok" or assertion))
    return {"qualified": valid, "observedTests": matches,
            "cleanBuild": clean_build, "assertionFailure": assertion}


def binary_identities(build):
    deps = build / "release/deps"
    return {str(p.relative_to(build)): sha256(p) for p in sorted(deps.glob("ariadne-*"))
            if p.is_file() and not p.is_symlink() and os.access(p, os.X_OK)}


def run_test(directory, manifest, build, test, env, label, timeout):
    cmd = command(manifest, build, test)
    started = time.monotonic()
    try:
        result = subprocess.run(cmd, cwd=manifest.parent, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=timeout)
        output, code = result.stdout, result.returncode
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        output += f"\nTIMEOUT after {timeout} seconds\n"
        code = None
    log = directory / f"{label}.log"
    log.write_text(output)
    binaries = binary_identities(build)
    control = test_evidence(output, code, test, "ok")
    mutant = test_evidence(output, code, test, "FAILED")
    return {
        "command": cmd, "exitCode": code, "seconds": time.monotonic() - started,
        "log": str(log), "logSha256": sha256(log), "testBinaries": binaries,
        "controlEvidence": control, "mutantEvidence": mutant,
        "passed": control["qualified"] and bool(binaries),
        "assertionRejected": mutant["qualified"] and bool(binaries),
    }


def seed_release_cache(build, seed):
    """Copy only release artifacts; never share mutable Cargo targets by links."""
    if seed is None:
        return
    release = seed / "release"
    if not release.is_dir() or release.is_symlink():
        raise ValueError("--seed-build-dir must contain a regular release/ directory")
    entries = [release, *release.rglob("*")]
    rustc_info = seed / ".rustc_info.json"
    if rustc_info.exists() or rustc_info.is_symlink():
        entries.append(rustc_info)
    if any(p.is_symlink() for p in entries):
        raise ValueError("release seed cache contains a symlink")
    build.mkdir(parents=True, exist_ok=False)
    for p in entries:
        copied = build / p.relative_to(seed)
        if p.is_dir():
            copied.mkdir(parents=True, exist_ok=True)
        elif p.is_file():
            copied.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["cp", "--reflink=auto", "--preserve=mode,timestamps",
                            "--", str(p), str(copied)], check=True)
        else:
            raise ValueError(f"unsupported release seed entry: {p}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-seams", action="store_true", help="check source and observer anchors without Cargo")
    parser.add_argument("--output", type=Path, help="new campaign directory under this repository's target/")
    parser.add_argument("--seed-build-dir", type=Path, help="existing target tree whose release cache is independently copied")
    parser.add_argument("--keep-builds", action="store_true", help="retain task-owned release build trees after hashes are recorded")
    parser.add_argument("--build-jobs", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()
    seams = check_seams()
    if args.check_seams:
        print(json.dumps(seams, indent=2))
        return
    if args.output is None:
        parser.error("--output is required unless --check-seams is selected")
    if args.build_jobs <= 0 or args.timeout_seconds <= 0:
        parser.error("build jobs and timeout must be positive")
    output = args.output.resolve()
    target_root = (ROOT / "target").resolve()
    if output == target_root or not output.is_relative_to(target_root):
        parser.error("--output must be a new child directory under repository target/")
    seed = args.seed_build_dir.resolve() if args.seed_build_dir else None
    if seed is not None and (not seed.is_dir() or seed == output
                             or output.is_relative_to(seed) or seed.is_relative_to(output)):
        parser.error("release seed must exist separately from the campaign output")
    output.mkdir(parents=True, exist_ok=False)
    before = source_inventory()
    env = {**os.environ, "CARGO_BUILD_JOBS": str(args.build_jobs)}
    records = []
    report = {
        "schema": "ariadne.guard-admission-mutations/v1",
        "sourceHashes": before, "expectedMutations": [s["name"] for s in MUTATIONS],
        "seedBuildDir": str(seed) if seed else None, "release": True,
        "buildsDiscardedByDefault": not args.keep_builds,
        "mutations": records, "sourcesStable": False, "passed": False,
    }
    failure = None
    try:
        for spec in MUTATIONS:
            directory = output / spec["name"]
            directory.mkdir()
            sut = directory / "sut"
            manifest = copy_sut(sut)
            copied_sources = tree_inventory(sut)
            observers = {p: digest for p, digest in copied_sources.items()
                         if p.startswith("tests/")}
            target = sut / spec["source"]
            original = target.read_bytes()
            mutant = apply_mutation(original.decode(), spec).encode()
            record = {
                "name": spec["name"], "contract": spec["contract"],
                "source": spec["source"],
                "originalSha256": hashlib.sha256(original).hexdigest(),
                "mutatedSha256": hashlib.sha256(mutant).hexdigest(),
                "sutSourceHashes": copied_sources, "observerHashes": observers,
                "checks": [], "sourceRestored": False, "observersUnchanged": False,
                "sutSourcesRestored": False,
            }
            records.append(record)
            build = directory / "build"
            try:
                seed_release_cache(build, seed)
                for name in spec["tests"]:
                    test = PREFIX + name
                    # Refresh the package source timestamp so an optional copied
                    # cache cannot substitute a retained root executable for SUT.
                    target.write_bytes(original)
                    control = run_test(directory, manifest, build, test, env,
                                       name + "-control", args.timeout_seconds)
                    check = {"test": test, "control": control, "mutant": None}
                    record["checks"].append(check)
                    if not control["passed"]:
                        raise RuntimeError(f'{spec["name"]}: exact unmodified control failed: {test}')
                    target.write_bytes(mutant)
                    try:
                        changed = run_test(directory, manifest, build, test, env,
                                           name + "-mutant", args.timeout_seconds)
                    finally:
                        target.write_bytes(original)
                    check["mutant"] = changed
                    if not changed["assertionRejected"]:
                        raise RuntimeError(f'{spec["name"]}: no expected named assertion rejection: {test}')
                    if source_inventory() != before:
                        raise RuntimeError("root source inventory changed during the campaign")
            finally:
                target.write_bytes(original)
                restored = tree_inventory(sut)
                record["sourceRestored"] = sha256(target) == record["originalSha256"]
                record["observersUnchanged"] = all(restored.get(p) == digest for p, digest in observers.items())
                record["sutSourcesRestored"] = restored == copied_sources
                record["buildDiscarded"] = not args.keep_builds
                if not args.keep_builds and build.exists():
                    shutil.rmtree(build)
                (directory / "result.json").write_text(json.dumps(record, indent=2) + "\n")
            if not all(record[k] for k in ("sourceRestored", "observersUnchanged", "sutSourcesRestored")):
                raise RuntimeError(f'{spec["name"]}: source/observer bytes were not restored')
            print(f'{spec["name"]}: {len(record["checks"])} exact assertion rejection(s)', flush=True)
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
        failure = str(error)
    finally:
        report["sourcesStable"] = before == source_inventory()
        report["passed"] = failure is None and report["sourcesStable"] and len(records) == len(MUTATIONS)
        if failure is not None:
            report["failure"] = failure
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f'Report: {output / "report.json"}', flush=True)
    if not report["passed"]:
        raise SystemExit(failure or "root source inventory changed during the campaign")


if __name__ == "__main__":
    main()
