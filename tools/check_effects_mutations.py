#!/usr/bin/env python3
"""Exercise real effect mistakes in isolated SUT copies, without changing tests."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RULES = "src/effects/rules.rs"
UNKNOWN = '''return Some(Summary {
    rule: "mutated-unknown".into(), operands: Vec::new(), kind: InstructionKind::Ordinary,
    uses: Catalogue.locations(), may_defs: Catalogue.locations(), must_defs: LocationSet::new(),
    undefined: LocationSet::new(), quality: EffectQuality::Opaque,
});'''
MUTATIONS = [
    ("opaque-control-loses-uncertainty", RULES,
     "opaque(&mut s);\n        return Some(s);\n    }\n    for width",
     "return Some(s);\n    }\n    for width",
     "opaque_control_forms_preserve_prior_origins_and_expose_uncertainty"),
    ("opaque-control-definite-kill", RULES,
     "opaque(&mut s);\n        return Some(s);\n    }\n    for width",
     "opaque(&mut s); s.must_defs = Catalogue.locations();\n        return Some(s);\n    }\n    for width",
     "opaque_control_forms_preserve_prior_origins_and_expose_uncertainty"),
    ("opaque-control-unreviewed-address-prefix", RULES,
     "if address_width != 64\n            || bytes.first()",
     "if false\n            || bytes.first()",
     "opaque_control_forms_preserve_prior_origins_and_expose_uncertainty"),
    ("partial-register-kill", "src/effects/locations.rs", "if self.width == 32 {", "if self.width <= 32 {",
     "partial_writes_preserve_other_bytes_and_dword_replaces_upper_half"),
    ("missing-address-use", RULES, "s.uses.extend(reads(&m));", "// mutated: omit address reads",
     "memory_keeps_possible_aliases_and_address_dependencies_lea_does_not_read_memory"),
    ("missing-carry-use", RULES, 's.uses.insert("flag:cf".into());', '// mutated: omit CF read',
     "carry_dependency_survives_increment_and_cmp_does_not_write_registers"),
    ("memory-wide-kill", RULES, 's.may_defs.insert("memory:any".into());',
     's.may_defs.insert("memory:any".into()); s.must_defs.insert("memory:any".into());',
     "memory_keeps_possible_aliases_and_address_dependencies_lea_does_not_read_memory"),
    ("call-preserves-rbx", RULES, "s.may_defs = Catalogue.locations();",
     's.may_defs = Catalogue.locations(); s.may_defs.retain(|l| !l.starts_with("gpr:rbx:"));',
     "control_flags_calls_and_unrecognized_control_have_distinct_evidence"),
    ("unknown-fallthrough", RULES, '.any(|code| code == raw.opcode)\n    {\n        return None;',
     '.any(|code| code == raw.opcode)\n    {\n        ' + UNKNOWN,
     "control_flags_calls_and_unrecognized_control_have_distinct_evidence"),
    ("mov-immediate-missing-address", RULES, "s.uses = reads(&destination);",
     "s.uses.clear();", "memory_immediate_mov_uses_address_registers_and_only_may_writes_memory"),
    ("mov-immediate-reads-old-memory", RULES, "s.uses = reads(&destination);",
     's.uses = reads(&destination); s.uses.insert("memory:any".into());',
     "memory_immediate_mov_uses_address_registers_and_only_may_writes_memory"),
    ("mov-immediate-kills-all-memory", RULES, 's.may_defs.extend(["memory:any".to_owned()]);',
     's.may_defs.extend(["memory:any".to_owned()]); s.must_defs.insert("memory:any".into());',
     "memory_immediate_mov_uses_address_registers_and_only_may_writes_memory"),
    ("mov-immediate-forgets-sign-extension", RULES, "let source = imm(&ops[5], 32, width)?;",
     "let source = imm(&ops[5], 32, 32)?;",
     "memory_immediate_mov_preserves_signed_payload_and_address_size"),
]


def main():
    decoder = Path(os.environ.get("ARIADNE_LLVM_MC", ROOT / "target/ariadne-llvm-mc")).resolve()
    directory = Path(tempfile.mkdtemp(prefix="ariadne-effects-mutations-"))
    print(f"Mutation artifacts: {directory}", flush=True)
    env = {**os.environ, "ARIADNE_LLVM_MC": str(decoder)}
    # Check the identical observer first; unavailable decoder/build is not a kill.
    baseline = subprocess.run(["cargo", "test", "--offline", "--test", "effects", "--", "--ignored"],
                              cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    (directory / "baseline.log").write_text(baseline.stdout + baseline.stderr)
    if baseline.returncode:
        raise SystemExit("Correct implementation failed; no mutation evidence accepted")
    results = []
    for name, file, old, new, test in MUTATIONS:
        sut = directory / name
        sut.mkdir()
        for tree in ("src", "tests"):
            shutil.copytree(ROOT / tree, sut / tree)
        for file_name in ("Cargo.toml", "Cargo.lock"):
            shutil.copy2(ROOT / file_name, sut / file_name)
        path = sut / file
        original = path.read_text()
        if original.count(old) != 1:
            raise RuntimeError(f"{name}: mutation anchor must match exactly once")
        path.write_text(original.replace(old, new))
        run = subprocess.run(["cargo", "test", "--offline", "--manifest-path", str(sut / "Cargo.toml"),
                              "--target-dir", str(directory / "target"), "--test", "effects", test,
                              "--", "--ignored", "--exact"], env=env, capture_output=True, text=True, timeout=120)
        log = run.stdout + run.stderr
        (sut / "run.log").write_text(log)
        killed = (run.returncode == 101 and f"test {test} ... FAILED" in log
                  and "assertion" in log and "could not compile" not in log)
        results.append({"mutation": name, "test": test, "assertionRejected": killed})
        print(f"{name}: {'assertion rejected' if killed else 'FAILED gate'}", flush=True)
        if not killed:
            raise RuntimeError(f"{name}: not a semantic rejection; see {sut / 'run.log'}")
    sources = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
               for base in (ROOT / "src", ROOT / "tests") for p in sorted(base.rglob('*')) if p.is_file()}
    (directory / "report.json").write_text(json.dumps({"sources": sources, "mutants": results}, indent=2) + "\n")


if __name__ == "__main__":
    main()
