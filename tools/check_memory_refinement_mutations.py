#!/usr/bin/env python3
"""Remote-only real-code mutation campaign with isolated SUT build directories."""
import argparse
import hashlib
import os
import re
import time
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS = [
    ("unknown-footprint-admitted", "src/investigation/memory_refinement.rs",
     ".is_none_or(|r| !r.memory_footprint_complete)",
     ".is_some_and(|r| !r.memory_footprint_complete)",
     "loops_and_absent_receipts_do_not_gain_precise_aliases"),
    ("unknown-pair-excluded", "src/investigation/memory_refinement.rs",
     '.all(|p| p.relation == "disjoint")', '.all(|_| true)',
     "loops_and_absent_receipts_do_not_gain_precise_aliases"),
    ("and-drops-known-bits", "src/investigation/backward_values.rs",
     "let mask = known_mask & operand;", "let mask = 0;",
     "inverse_rules_match_1280_exhaustive_predecessor_sets"),
    ("range-wrap-discarded", "src/investigation/memory_refinement.rs",
     "vec![(start, modulus), (0, end - modulus)]", "vec![(start, modulus)]",
     "modular_ranges_match_784_independent_integer_cases"),
    ("unknown-value-guessed-zero", "src/investigation/backward_values.rs",
     'result.before = Some(BackwardValue::Unknown {\n                    width,\n                    reason: "information-erasure".into(),\n                });',
     'result.before = Some(BackwardValue::Exact { width, value: 0 });',
     "inverse_rules_match_1280_exhaustive_predecessor_sets"),
]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory():
    files = {str(p.relative_to(ROOT)): sha(p)
             for folder in ("src", "tests", "Specs", "native")
             for p in (ROOT / folder).rglob("*")
             if p.is_file() and not {"__pycache__", ".tlacache", "target"}.intersection(p.parts)}
    for name in ("Cargo.toml", "Cargo.lock", "tools/check_memory_refinement_mutations.py"):
        files[name] = sha(ROOT / name)
    return files


def observe(command, source, log):
    started = time.monotonic()
    try:
        result = subprocess.run(command, cwd=source,
                                env=dict(os.environ, CARGO_BUILD_JOBS="2", CARGO_INCREMENTAL="1"),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, timeout=900)
        output, code, timed_out = result.stdout, result.returncode, False
    except subprocess.TimeoutExpired as error:
        output = error.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        code, timed_out = None, True
    log.write_text(output)
    binaries = {}
    for line in output.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if value.get("reason") == "compiler-artifact" and value.get("executable"):
            binary = Path(value["executable"])
            binaries[str(binary)] = sha(binary)
    return {"returncode": code, "timeout": timed_out,
            "seconds": time.monotonic() - started,
            "log_sha256": sha(log), "binaries": binaries}, output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", action="store_true",
                        help="Assert execution in the task-owned remote environment")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--check-seams", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    for name, file, before, _, observer in MUTATIONS:
        assert (ROOT / file).read_text().count(before) == 1, (name, "nonunique seam")
        assert any(("fn " + observer + "(") in p.read_text()
                   for p in (ROOT / "tests").rglob("*.rs")), observer
    if args.check_seams:
        print(f"{len(MUTATIONS)} unique mutation seams and unchanged observers found")
        return
    assert args.remote and args.output_dir, "--remote and --output-dir are required"
    out = args.output_dir.resolve()
    assert args.resume or not out.exists()
    out.mkdir(parents=True, exist_ok=args.resume)
    frozen = inventory()
    if args.resume:
        assert json.loads((out / "source-inventory.json").read_text()) == frozen
    else:
        (out / "source-inventory.json").write_text(json.dumps(frozen, indent=2) + "\n")
    records = []
    for name, file, before, after, observer in MUTATIONS:
        case = out / name
        case.mkdir(exist_ok=args.resume)
        qualified = "investigation::memory_refinement::tests::" + observer
        if args.resume and (case / "result.json").is_file():
            record = json.loads((case / "result.json").read_text())
            assert record["control"]["passed"] and record["mutant"]["behavior_rejected"]
            assert sha(case / "control.log") == record["control"]["log_sha256"]
            assert sha(case / "mutant.log") == record["mutant"]["log_sha256"]
            records.append(record)
            continue
        source = case / "source"
        if source.exists():
            shutil.rmtree(source)
        source.mkdir()
        for folder in ("src", "tests", "Specs", "native"):
            shutil.copytree(ROOT / folder, source / folder,
                            ignore=shutil.ignore_patterns("__pycache__", ".tlacache", "target"))
        for item in ("Cargo.toml", "Cargo.lock"):
            shutil.copyfile(ROOT / item, source / item)
        manifest = source / "Cargo.toml"
        manifest.write_text(manifest.read_text().replace('path = "../MirrorRust"',
                            'path = ' + json.dumps(str(ROOT.parent / "MirrorRust"))))
        target = source / file
        original = target.read_text()
        assert original.count(before) == 1
        command = ["cargo", "test", "--offline", "--locked", "--no-default-features",
                   "--features", "input", "--message-format=json", "--lib", qualified,
                   "--target-dir", str(case / "build"), "--", "--exact", "--nocapture",
                   "--test-threads=1"]
        control, output = observe(command, source, case / "control.log")
        control["passed"] = (control["returncode"] == 0 and bool(control["binaries"])
                             and f"test {qualified} ... ok" in output)
        assert control["passed"], (name, "unmodified observer failed")
        try:
            target.write_text(original.replace(before, after, 1))
            mutant_hash = sha(target)
            result, output = observe(command, source, case / "mutant.log")
        finally:
            target.write_text(original)
        result["behavior_rejected"] = (
            result["returncode"] == 101 and not result["timeout"] and bool(result["binaries"])
            and "test result: FAILED" in output and "panicked at" in output
            and bool(re.search(r"^    " + re.escape(qualified) + r"$", output, re.MULTILINE)))
        record = {"name": name, "file": file, "observer": qualified,
                  "original_sha256": hashlib.sha256(original.encode()).hexdigest(),
                  "mutant_sha256": mutant_hash, "control": control, "mutant": result}
        records.append(record)
        (case / "result.json").write_text(json.dumps(record, indent=2) + "\n")
        complete = len(records) == len(MUTATIONS)
        report = {"schema": "ariadne.memory-refinement-mutations/v2", "complete": complete,
                  "passed": complete and all(r["control"]["passed"]
                                             and r["mutant"]["behavior_rejected"] for r in records),
                  "records": records}
        (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        assert result["behavior_rejected"], (name, "escaped or compile/transport failure")
        assert inventory() == frozen, "source changed during campaign"
        print(f"{name}: unmodified control passed; compiled mutation rejected", flush=True)
    stable = inventory() == frozen
    (out / "source-stability.json").write_text(json.dumps({"unchanged": stable}) + "\n")
    assert stable
    print(f"Mutation PASS: {len(records)} actual mutants rejected by unchanged observers")


if __name__ == "__main__":
    main()
