#!/usr/bin/env python3
"""Remote-only real-code mutation campaign with isolated SUT build directories."""
import argparse
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", action="store_true", required=True,
                        help="Assert execution in the task-owned remote environment")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)
    records = []
    for name, file, before, after, observer in MUTATIONS:
        case = out/name
        source = case/"source"
        source.mkdir(parents=True)
        for folder in ["src", "tests"]:
            shutil.copytree(ROOT/folder, source/folder)
        for item in ["Cargo.toml", "Cargo.lock"]:
            shutil.copyfile(ROOT/item, source/item)
        manifest = source/"Cargo.toml"
        manifest.write_text(manifest.read_text().replace('path = "../MirrorRust"',
                            'path = '+json.dumps(str(ROOT.parent/"MirrorRust"))))
        target = source/file
        text = target.read_text()
        if text.count(before) != 1:
            raise ValueError(f"{name}: mutation seam no longer uniquely matches")
        target.write_text(text.replace(before, after, 1))
        command = ["cargo", "test", "--offline", "--locked", "--lib", observer,
                   "--target-dir", str(case/"build"), "-j", "1", "--", "--nocapture"]
        with (case/"observer.log").open("w") as log:
            result = subprocess.run(command, cwd=source, stdout=log, stderr=subprocess.STDOUT)
        output = (case/"observer.log").read_text()
        rejected = result.returncode != 0 and "test result: FAILED" in output and "panicked at" in output
        records.append({"name":name,"observer":observer,"exit":result.returncode,
                        "compiled_behavior_rejected":rejected})
        (out/"report.json").write_text(json.dumps({"schema":"ariadne.memory-refinement-mutations/v1",
                         "passed":all(r["compiled_behavior_rejected"] for r in records),
                         "complete":len(records)==len(MUTATIONS),"records":records},indent=2)+"\n")
        if not rejected:
            raise SystemExit(f"{name}: not credited as a compiled behavioral rejection")
    print(f"Mutation PASS: {len(records)} actual mutants rejected by unchanged observers")


if __name__ == "__main__":
    main()
