#!/usr/bin/env python3
"""Real-code Stage 5.1 mutations; builds/runs belong on authorized remote WSL.

--check-seams only checks anchors and observer names. A campaign first executes
an unmodified observer, then compiles and runs the changed SUT in its own source
and target directory. Compile/timeout/transport failures earn no kill credit.
No native-helper, concrete-proof or original-dump qualification is implied.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
CORE_OBSERVER = "independent_recovery_prefixes_match_frozen_control_facts"
ORACLE_TEST = "frame_structure_oracle"


@dataclass(frozen=True)
class Mutant:
    name: str
    file: str
    before: str
    after: str
    observer: str
    target: str = ORACLE_TEST
    scope: tuple[str, str] | None = None


def mutants():
    recover_scope = ("pub fn recover(", "/// Failure to validate an exact producer prefix")
    return [
        Mutant("missing-taken-edge", "src/engine.rs", "self.state.edges.insert(edge);",
               "if edge.kind != EdgeKind::Taken { self.state.edges.insert(edge); }", CORE_OBSERVER),
        Mutant("missing-local-frontier", "src/engine.rs", "self.state.pending.insert(edge.dst);",
               "if edge.kind != EdgeKind::Next { self.state.pending.insert(edge.dst); }", CORE_OBSERVER),
        Mutant("forged-drained", "src/recovery.rs", "break (RecoveryStop::VisitLimit, elapsed_ms);",
               "break (RecoveryStop::Drained, elapsed_ms);", CORE_OBSERVER, scope=recover_scope),
        Mutant("finish-recovery-after-drain", "src/recovery.rs",
               "if analyzer.state().pending.is_empty() {\n            break (RecoveryStop::Drained, elapsed_ms);",
               "if analyzer.state().pending.is_empty() {\n            analyzer.step();\n            break (RecoveryStop::Drained, elapsed_ms);",
               CORE_OBSERVER, scope=recover_scope),
        Mutant("admit-final-unknown-guard", "src/engine.rs",
               "if source == ByteSource::Unavailable || !self.request.decodable.contains(&address) {",
               "if source == ByteSource::Unavailable {",
               "independent_final_unknown_guard_does_not_admit_candidate"),
        Mutant("unreached-active-call", "src/investigation/frame_structure.rs",
               "parent.recovery.state().decoded.iter()", "parent.request().addresses.iter()",
               "investigation::frame_structure::tests::active_call_requires_reached_e8_not_merely_prepared_source",
               target="lib"),
        Mutant("ignored-host-replay-limit", "src/recovery.rs",
               "if receipt.visits > max_replay_visits {",
               "if false && receipt.visits > max_replay_visits {",
               "independent_host_replay_cap_is_not_raised_by_producer"),
        Mutant("ignored-producer-visit-limit", "src/recovery.rs",
               "if visits >= limits.max_visits {", "if false && visits >= limits.max_visits {",
               CORE_OBSERVER, scope=recover_scope),
        Mutant("follow-call-context-as-local", "src/engine.rs",
               "if edge.kind.is_local() && !self.state.visited.contains(&edge.dst) {",
               "if !self.state.visited.contains(&edge.dst) {", CORE_OBSERVER),
    ]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(root):
    files = [root / "Cargo.toml", root / "Cargo.lock", root / "tools/check_frame_structure_mutations.py"]
    for directory in ("src", "tests", "Specs", "native"):
        files.extend(path for path in (root / directory).rglob("*")
                     if path.is_file() and not path.is_symlink() and "__pycache__" not in path.parts)
    return {str(path.relative_to(root)): sha(path) for path in sorted(set(files))}


# Match complete lexical tokens while retaining original source offsets.
# Quoted strings and comments are consumed whole, so code-shaped text inside
# them cannot become a mutation anchor. This scanner is only an anchor finder,
# not a Rust parser; uniqueness and the compiled behavioral observer remain
# mandatory. Splitting punctuation keeps rustfmt line wrapping immaterial.
ANCHOR_TOKEN = re.compile(
    r'(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)|'
    r'(?P<string>"(?:\\.|[^"\\])*")|'
    r'[A-Za-z_][A-Za-z_0-9]*|[0-9]+|[^\s]'
)


def anchor_tokens(text):
    return [(match.group(), match.start(), match.end()) for match in ANCHOR_TOKEN.finditer(text)
            if match.lastgroup != "comment"]


def apply(original, mutant):
    start, end = 0, len(original)
    if mutant.scope:
        require(original.count(mutant.scope[0]) == 1 and original.count(mutant.scope[1]) == 1,
                f"mutation scope changed: {mutant.name}")
        start, end = original.index(mutant.scope[0]), original.index(mutant.scope[1])
        require(start < end, f"mutation scope is reversed: {mutant.name}")
    region = original[start:end]
    tokens = anchor_tokens(region)
    expected = [token for token, _, _ in anchor_tokens(mutant.before)]
    require(bool(expected), f"mutation anchor is empty: {mutant.name}")
    matches = [index for index in range(len(tokens) - len(expected) + 1)
               if [token for token, _, _ in tokens[index:index + len(expected)]] == expected]
    require(len(matches) == 1, f"mutation token seam is not unique: {mutant.name}")
    index = matches[0]
    left, right = start + tokens[index][1], start + tokens[index + len(expected) - 1][2]
    return original[:left] + mutant.after + original[right:]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def observe(command, source, env, output, timeout, expected, mutant):
    started = time.monotonic()
    try:
        run = subprocess.run(command, cwd=source, env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        text, code, timed_out = run.stdout, run.returncode, False
    except subprocess.TimeoutExpired as error:
        text = error.stdout or ""
        if isinstance(text, bytes):
            text = text.decode(errors="replace")
        code, timed_out = None, True
    output.write_text(text)
    artifacts = {}
    for line in text.splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict) and record.get("reason") == "compiler-artifact" and record.get("executable"):
            executable = Path(record["executable"])
            if executable.is_file():
                artifacts[str(executable)] = sha(executable)
    expected_pass = re.search(r"^test " + re.escape(expected) + r" \.\.\. ok$", text, re.MULTILINE)
    summaries = re.findall(
        r"^failures:\n((?:[ \t]*\n|[ \t]+[A-Za-z0-9_:]+\n)+)(?=test result: FAILED)",
        text, re.MULTILINE,
    )
    failed = set(re.findall(r"^[ \t]+([A-Za-z0-9_:]+)$", summaries[-1], re.MULTILINE)) if summaries else set()
    passed = (not timed_out and code == 0 and expected_pass is not None
              and "test result: ok. 1 passed;" in text and bool(artifacts))
    rejected = (not timed_out and code == 101 and expected in failed
                and "test result: FAILED" in text and "panicked at" in text and bool(artifacts))
    return {"command": command, "returncode": code, "timeout": timed_out,
            "seconds": time.monotonic() - started, "observer": expected,
            "baseline_passed": passed if not mutant else None,
            "compiled_behavior_rejected": rejected if mutant else None,
            "failed_tests": sorted(failed), "test_binaries": artifacts,
            "log_sha256": sha(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check-seams", action="store_true")
    mode.add_argument("--remote", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--build-root", type=Path,
                        help="Fresh campaign directory under this checkout's target/; never shared with replay")
    parser.add_argument("--only", action="append", default=[], help="Select named mutant; repeatable")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--discard-builds", action="store_true")
    args = parser.parse_args()
    selected = [row for row in mutants() if not args.only or row.name in args.only]
    require((len(args.only) == len(set(args.only)) and len(selected) == len(args.only))
            if args.only else bool(selected), "unknown or duplicate mutant selection")
    for row in selected:
        apply((ROOT / row.file).read_text(), row)
        observer = row.observer.rsplit("::", 1)[-1]
        test_source = (ROOT / "tests/investigation/frame_structure.rs" if row.target == "lib"
                       else ROOT / "tests/frame_structure_oracle.rs")
        require(test_source.read_text().count("fn " + observer + "(") == 1,
                "expected real observer missing: " + observer)
    if args.check_seams:
        print(f"Frame-structure mutation seams PASS: {len(selected)} unique edits and existing observers; no campaign executed")
        return
    if args.output_dir is None:
        parser.error("--remote requires --output-dir")
    require(args.timeout > 0, "timeout must be positive")
    output = args.output_dir.resolve()
    require(all(not output.is_relative_to(ROOT / directory)
                for directory in ("src", "tests", "Specs", "native")),
            "output directory cannot be inside copied source inputs")
    output.mkdir(parents=True, exist_ok=False)
    build = (args.build_root or ROOT / "target/frame-structure-mutations" / output.name).resolve()
    require(build.is_relative_to((ROOT / "target").resolve()), "build-root must be under the checkout target/")
    require(not build.exists(), "campaign build root already exists")
    build.mkdir(parents=True)
    before = inventory(ROOT)
    records = []
    sibling_manifest = ROOT.parent / "MirrorRust/Cargo.toml"
    require(sibling_manifest.is_file(), "frozen optional sibling manifest is missing")
    sibling_before = sha(sibling_manifest)
    (output / "sibling-manifest.json").write_text(json.dumps(
        {"path": str(sibling_manifest), "sha256": sibling_before,
         "scope": "Optional dependency resolver manifest; mbt is not activated"}, indent=2) + "\n")
    (output / "source-inventory.json").write_text(json.dumps(before, indent=2) + "\n")
    env = dict(os.environ, CARGO_BUILD_JOBS="1", CARGO_INCREMENTAL="0")
    rustc = subprocess.run(["rustc", "-Vv"], check=True, text=True, capture_output=True)
    cargo = subprocess.run(["cargo", "-V"], check=True, text=True, capture_output=True)
    (output / "tool-versions.txt").write_text(rustc.stdout + cargo.stdout)
    for row in selected:
        case = output / row.name
        source = case / "source"
        source.mkdir(parents=True)
        for directory in ("src", "tests", "Specs", "native"):
            shutil.copytree(ROOT / directory, source / directory,
                            ignore=shutil.ignore_patterns("__pycache__"))
        for item in ("Cargo.toml", "Cargo.lock"):
            shutil.copyfile(ROOT / item, source / item)
        manifest = source / "Cargo.toml"
        relative_dependency = 'path = "../MirrorRust"'
        require(manifest.read_text().count(relative_dependency) == 1, "optional sibling dependency seam changed")
        manifest.write_text(manifest.read_text().replace(
            relative_dependency, "path = " + json.dumps(str(ROOT.parent / "MirrorRust")), 1))
        case_build = build / row.name
        command = ["cargo", "test", "--offline", "--locked", "--no-default-features", "--features", "input",
                   "--message-format=json", "--target-dir", str(case_build)]
        command += ["--lib"] if row.target == "lib" else ["--test", row.target]
        command += [row.observer, "--", "--exact", "--nocapture", "--test-threads=1"]
        control = observe(command, source, env, case / "control.log", args.timeout, row.observer, False)
        (case / "control.json").write_text(json.dumps(control, indent=2) + "\n")
        require(control["baseline_passed"], "unmodified observer failed; no mutation credit: " + row.name)
        target = source / row.file
        original = target.read_text()
        target.write_text(apply(original, row))
        changed_sha = sha(target)
        observed = observe(command, source, env, case / "mutant.log", args.timeout, row.observer, True)
        record = {"name": row.name, "source_file": row.file,
                  "original_source_sha256": hashlib.sha256(original.encode()).hexdigest(),
                  "mutant_source_sha256": changed_sha, "control": control, "mutant": observed}
        records.append(record)
        (case / "result.json").write_text(json.dumps(record, indent=2) + "\n")
        report = {"schema": "ariadne.frame-structure-mutations/v1",
                  "expected_mutants": [item.name for item in selected], "complete": len(records) == len(selected),
                  "passed": len(records) == len(selected) and all(
                      item["control"]["baseline_passed"] and item["mutant"]["compiled_behavior_rejected"]
                      for item in records), "records": records}
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        require(observed["compiled_behavior_rejected"],
                "mutant escaped or compile/transport failure; no credit: " + row.name)
        require(sha(target) == changed_sha, "mutant source changed while testing")
        require(inventory(ROOT) == before, "original checkout changed during campaign")
        require(sha(sibling_manifest) == sibling_before, "optional sibling manifest changed during campaign")
        print(f"{row.name}: unmodified control passed; compiled mutant rejected", flush=True)
        if args.discard_builds:
            shutil.rmtree(case_build)
    (output / "source-stability.json").write_text(json.dumps({"unchanged": inventory(ROOT) == before}) + "\n")
    print(f"Frame-structure mutations PASS: {len(records)} compiled real-code mutants rejected")


if __name__ == "__main__":
    main()
