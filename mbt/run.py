#!/usr/bin/env python3
"""Replay the fixed oracle against the real implementation and temporary mutants."""

import argparse
import json
from pathlib import Path
import shutil
import sys

from binding import GENERATED, TARGET, check_binding, generated_hashes
from tools import (FIXTURES, MBT, ROOT, mirrors_tools, prepare_model, run,
                   sha256, verify_corpus, work_directory, write_json)


def build(manifest, destination, log):
    run(["cargo", "build", "--offline", "--locked", "--manifest-path", manifest,
         "--target-dir", MBT / "target"], log=log, timeout=180)
    shutil.copy2(MBT / "target/debug/ariadne-mbt", destination)


def replay(executable, mode, mirror, model, lock, traces, directory):
    result = run([executable, mode, mirror, model, lock, *traces], expected=(0, 1),
                 log=directory / "replay.log", timeout=60)
    report = json.loads(result.stdout.splitlines()[-1])
    report["executableSha256"] = sha256(executable)
    write_json(directory / "report.json", report)
    if result.returncode != 0 or not report["gatePassed"]:
        raise RuntimeError(f"{mode} replay failed acceptance; see {directory / 'report.json'}")
    return report


def mutant_manifest(mutation, directory):
    # Bulk mechanical mutation only in a fresh test-artifact copy. The working
    # implementation and the observer are never modified by the mutation tier.
    sut = directory / "sut"
    sut.mkdir()
    shutil.copytree(ROOT / "src", sut / "src")
    for filename in ("Cargo.toml", "Cargo.lock"):
        shutil.copyfile(ROOT / filename, sut / filename)
    engine = sut / "src/engine.rs"
    original = engine.read_text()
    if original.count(mutation["old"]) != 1:
        raise RuntimeError(f"mutation {mutation['name']} must match exactly once; review it after implementation changes")
    engine.write_text(original.replace(mutation["old"], mutation["new"], 1))
    evaluator = directory / "evaluator"
    evaluator.mkdir()
    shutil.copytree(MBT / "src", evaluator / "src")
    shutil.copytree(GENERATED, evaluator / "generated")
    if generated_hashes(evaluator / "generated") != generated_hashes():
        raise RuntimeError("mutation changed the compiler-generated binding")
    if sha256(evaluator / "src/adapter.rs") != sha256(MBT / "src/adapter.rs"):
        raise RuntimeError("mutation changed the actual-state observer")
    manifest = (MBT / "Cargo.toml").read_text()
    manifest = manifest.replace('path = ".."', f'path = {json.dumps(str(sut))}')
    manifest = manifest.replace('path = "../../MirrorRust"',
                                f'path = {json.dumps(str(ROOT.parent / "MirrorRust"))}')
    (evaluator / "Cargo.toml").write_text(manifest)
    shutil.copyfile(MBT / "Cargo.lock", evaluator / "Cargo.lock")
    return evaluator / "Cargo.toml", sha256(engine)


def compare_baseline(report, path):
    baseline = json.loads(path.read_text())
    contract = json.loads((MBT / "corpus/AriadneReplay.lock.json").read_text())["contract"]
    stable_ids = {action["wireAction"]: action["id"] for action in contract["actions"]}
    old = baseline["positive"]
    new = report["positive"]
    actions = {stable_ids.get(action, action): count for action, count in old["matchedActionCounts"].items()}
    pairs = {"->".join(stable_ids.get(action, action) for action in pair.split("->")): count
             for pair, count in old["matchedPairCounts"].items()}
    mismatch_positions = lambda evidence: {
        row["mutation"]: (row["mismatch"]["action"], row["observationsDispatched"])
        for row in evidence["mutants"]
    }
    checks = {
        "oraclePreserved": baseline["corpusManifestSha256"] == report["corpusManifestSha256"],
        "sutPreserved": baseline["sutSources"] == report["sutSources"],
        "semanticDigestPreserved": old["semanticDigest"] == new["semanticDigest"],
        "completeReplayPreserved": old["matchedObservations"] == new["matchedObservations"]
                                   and old["fixtures"] == new["fixtures"]
                                   and old["completedTraces"] == new["completedTraces"],
        "coveragePreserved": actions == new["matchedActionCounts"] and pairs == new["matchedPairCounts"],
        "mutantMismatchPositionsPreserved": mismatch_positions(baseline) == mismatch_positions(report),
        "admissionBarrierPreserved": baseline["wrongDigest"]["factoryCalls"] == 0
                                     and report["wrongDigest"]["factoryCalls"] == 0,
    }
    if not baseline["passed"] or not all(checks.values()):
        raise RuntimeError(f"generated-binding migration changed baseline behavior: {checks}")
    return {"baselineSha256": sha256(path), **checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compare-baseline", type=Path,
                        help="also require preservation against a previous MBT result")
    args = parser.parse_args()
    manifest = verify_corpus()
    work = work_directory("replay")
    print(f"Replay logs: {work}", flush=True)
    mirrors, compiler, mirror = mirrors_tools()
    model = prepare_model(work)
    lock = MBT / "corpus/AriadneReplay.lock.json"
    check_binding(compiler, model, work / "generated-freshness.log")
    for fixture in FIXTURES:
        run([compiler, "preflight", "--lock", lock, "--trace", MBT / "corpus" / f"{fixture}.itf.json",
             "--require-all-actions", "--diagnostics", "json"], log=work / f"{fixture}-preflight.log")
    # Repeat the whole suite using one negotiated binding. Every init must
    # create a fresh Analyzer, including after the preceding fixture completed.
    traces = [MBT / "corpus" / f"{fixture}.itf.json" for fixture in FIXTURES] * 2
    good_dir = work / "good"
    good_dir.mkdir()
    executable = good_dir / "ariadne-mbt"
    build(MBT / "Cargo.toml", executable, good_dir / "build.log")
    positive = replay(executable, "good", mirror, model, lock, traces, good_dir)
    expected_states = 2 * sum(manifest["traceStates"].values())
    if positive["matchedObservations"] != expected_states:
        raise RuntimeError("not every corpus state was observed and matched")
    print(f"Correct implementation: {positive['completedTraces']} traces, {positive['matchedObservations']} matched states", flush=True)
    rejected_dir = work / "wrong-digest"
    rejected_dir.mkdir()
    rejected = replay(executable, "wrong-digest", mirror, model, lock, traces, rejected_dir)
    print("Wrong digest: rejected before adapter creation", flush=True)
    mutants = []
    for mutation in json.loads((MBT / "mutations.json").read_text()):
        directory = work / mutation["name"]
        directory.mkdir()
        candidate_manifest, engine_digest = mutant_manifest(mutation, directory)
        candidate_executable = directory / "ariadne-mbt"
        build(candidate_manifest, candidate_executable, directory / "build.log")
        report = replay(candidate_executable, "mutant", mirror, model, lock, traces, directory)
        if report["mismatch"]["action"] != mutation["action"]:
            raise RuntimeError(f"unexpected first mismatch for {mutation['name']}")
        report["mutation"] = mutation["name"]
        report["engineSha256"] = engine_digest
        mutants.append(report)
        print(f"{mutation['name']}: genuine mismatch at {mutation['action']}, port Drop confirmed", flush=True)
    identity_path = MBT / ".work/toolchain.json"
    report = {
        "schema": "ariadne.mbt-results/v2", "passed": True,
        "scope": "local negotiated replay; no restricted-worker or author-isolation claim",
        "command": "python3 mbt/run.py", "corpusManifestSha256": sha256(MBT / "corpus/manifest.json"),
        "observerSha256": sha256(MBT / "src/adapter.rs"),
        "generatedBinding": {"targetProfile": TARGET, "artifacts": generated_hashes(),
                             "freshnessChecked": True},
        "sutSources": {str(path.relative_to(ROOT)): sha256(path) for path in sorted((ROOT / "src").glob("*.rs"))},
        "tools": {"mirrorsRevision": run(["git", "rev-parse", "HEAD"], cwd=mirrors).stdout.strip(),
                  "mirrorSha256": sha256(mirror), "compilerSha256": sha256(compiler),
                  "mirrorrustRevision": run(["git", "rev-parse", "HEAD"], cwd=ROOT.parent / "MirrorRust").stdout.strip(),
                  "mirrorgateInspectedRevision": run(["git", "rev-parse", "HEAD"], cwd=ROOT.parent / "MirrorGate").stdout.strip(),
                  "rustc": run(["rustc", "--version"]).stdout.strip(),
                  "cargoLockSha256": sha256(MBT / "Cargo.lock"),
                  "compatibilityBuild": json.loads(identity_path.read_text()) if identity_path.is_file() else None},
        "positive": positive, "wrongDigest": rejected, "mutants": mutants,
    }
    if args.compare_baseline:
        report["migration"] = compare_baseline(report, args.compare_baseline)
        report["command"] += f" --compare-baseline {args.compare_baseline}"
        print("Baseline preserved: oracle, SUT, replay, coverage, and first mutant mismatch positions", flush=True)
    results = MBT / "results"
    results.mkdir(exist_ok=True)
    write_json(results / "latest.json", report)
    print(f"MBT acceptance passed; evidence: {results / 'latest.json'}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"MBT FAILED: {error}", file=sys.stderr)
        raise SystemExit(1) from error
