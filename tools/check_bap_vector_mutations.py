#!/usr/bin/env python3
"""Source-bound vector projection mutations; run Cargo only on the remote WSL host.

Each mutant gets a private SUT and build directory. A failed compilation or an
unrelated test failure is never counted as mutation sensitivity.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from rust_layout import ROOT, copy_sut, source_files


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory():
    paths = source_files() | {Path(__file__)}
    paths.update(p for p in (ROOT / "native/bap").rglob("*") if p.is_file())
    return {str(p.relative_to(ROOT)): sha256(p) for p in sorted(paths)}


# A mutation is attached to one exact behavioral observer. The first mutation
# also exercises the native producer path, which emits the actual XMM/YMM BIL.
MUTATIONS = [
    {
        "name": "aggregate-vector-must-kill",
        "file": "src/bap/projection.rs",
        "old": 'if cell != "state:other"',
        "new": "if true /* mutant: treat the coarse vector location as a full kill */",
        "tests": [
            ("lib", "bap::vector_projection_tests::vector_load_self_move_and_conditional_writes_never_kill_aggregate_origins"),
            ("native", "vector_producer_tracks_coarse_state_and_retains_alignment_refusal"),
        ],
    },
    {
        "name": "collapse-vector-banks",
        "file": "src/bap/registers.rs",
        "old": 'name: format!("YMM{bank}"),',
        "new": 'name: "YMM0".into(), // mutant: collapse all vector banks',
        "tests": [("lib", "bap::vector_projection_tests::vector_banks_stay_independent_despite_shared_public_location")],
    },
    {
        "name": "read-upper-half-as-xmm",
        "file": "src/bap/projection.rs",
        "old": 'return Ok(Value::Bits(state.env[&key].bits()?[..var.width].to_vec()));',
        "new": 'let start = if var.width == 128 { 128 } else { 0 }; return Ok(Value::Bits(state.env[&key].bits()?[start..start + var.width].to_vec()));',
        "tests": [("lib", "bap::vector_projection_tests::ymm_and_xmm_share_backing_in_both_read_directions")],
    },
    {
        "name": "xmm-write-clobbers-upper-ymm",
        "file": "src/bap/projection.rs",
        "old": 'bits[..var.width].clone_from_slice(value.bits()?);',
        "new": 'bits[..var.width].clone_from_slice(value.bits()?); if var.width == 128 { for bit in &mut bits[128..] { *bit = Bit::constant(false); } }',
        "tests": [("lib", "bap::vector_projection_tests::xmm_write_preserves_upper_ymm_and_ymm_write_replaces_prior_xmm_view")],
    },
    {
        "name": "vector-payload-as-stack-address",
        "file": "src/bap/projection.rs",
        "old": 'let address = child(addr)?;\n            let stored = child(value)?;',
        "new": 'let address = child(value)?; // mutant: bind the payload as the address\n            let stored = child(value)?;',
        "tests": [("lib", "bap::vector_projection_tests::vector_stores_keep_payload_and_address_origins_without_memory_kills")],
    },
    {
        "name": "filtered-gpr-as-vector-destination",
        "file": "src/bap/admission.rs",
        "old": 'let first = fields.get(3)?.strip_prefix("r:")?;\n    let expected = crate::effects::RegisterView::parse(first)?;\n    match e.operands.first()? {\n        crate::effects::Operand::Register(r) if *r == expected => Some(r),\n        _ => None,\n    }',
        "new": 'e.operands.iter().find_map(|operand| match operand {\n        crate::effects::Operand::Register(r) => Some(r),\n        _ => None,\n    }) // mutant: the filtered first GPR may be only an address base',
        "tests": [("native", "vector_producer_tracks_coarse_state_and_retains_alignment_refusal")],
    },
]


def unique_mutation(text, spec):
    count = text.count(spec["old"])
    if count != 1:
        raise ValueError(f'{spec["name"]}: expected one source anchor, found {count}')
    return text.replace(spec["old"], spec["new"], 1)


def command(manifest, build, kind, test):
    return [
        "cargo", "test", "--offline", "--locked", "--release", "--manifest-path", str(manifest),
        "--target-dir", str(build),
        *(["--lib"] if kind == "lib" else ["--test", "bap_native"]),
        test, "--", "--exact", "--include-ignored", "--test-threads=1",
    ]


def test_evidence(output, result, test, expected):
    status = re.search(rf"^test {re.escape(test)} \.\.\. (ok|FAILED)$", output, re.MULTILINE)
    clean_build = not any(s in output for s in ("could not compile", "error: linker", "error[E"))
    suite = "test result: ok." if expected == "ok" else "test result: FAILED"
    assertion = expected == "ok" or "assertion failed" in output or "assertion `left == right` failed" in output
    return (result.returncode == (0 if expected == "ok" else 101)
            and clean_build and status is not None and status.group(1) == expected
            and suite in output and assertion)


def run_test(directory, manifest, build, kind, test, env, label):
    cmd = command(manifest, build, kind, test)
    try:
        result = subprocess.run(cmd, cwd=manifest.parent, env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=900)
        output = result.stdout
        code = result.returncode
    except subprocess.TimeoutExpired as error:
        output = (error.stdout or b"").decode(errors="replace") if isinstance(error.stdout, bytes) else (error.stdout or "")
        output += "\nTIMEOUT after 900 seconds\n"
        code = None
    log = directory / f"{label}.log"
    log.write_text(output)
    probe = type("Result", (), {"returncode": code})()
    return {
        "command": cmd,
        "exitCode": code,
        "log": str(log),
        "logSha256": sha256(log),
        "passed": test_evidence(output, probe, test, "ok"),
        "assertionRejected": test_evidence(output, probe, test, "FAILED"),
    }


def seed_build(build, seed):
    """Make a private copy of dependency artifacts, using reflinks where possible.

    Symlinks and hardlink-based sharing are forbidden: Cargo is free to replace
    or remove files in its target directory during each control/mutant pair.
    """
    if seed is None:
        return
    for path in seed.rglob("*"):
        if path.is_symlink():
            raise RuntimeError(f"seed target contains a symlink: {path}")
    build.mkdir(parents=True, exist_ok=False)
    for path in seed.rglob("*"):
        relative = path.relative_to(seed)
        copied = build / relative
        if path.is_dir():
            copied.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            copied.parent.mkdir(parents=True, exist_ok=True)
            # GNU cp's auto mode falls back to an independent byte copy if the
            # backing filesystem does not support copy-on-write reflinks.
            subprocess.run(["cp", "--reflink=auto", "--preserve=mode,timestamps",
                            "--", str(path), str(copied)], check=True)
        else:
            raise RuntimeError(f"unsupported seed target entry: {path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-seams", action="store_true", help="validate unique source anchors without building")
    parser.add_argument("--output", type=Path, help="new directory under repository target/")
    parser.add_argument("--helper", type=Path, default=ROOT / "target/ariadne-bap-lift")
    parser.add_argument("--decoder", type=Path, default=ROOT / "target/ariadne-llvm-mc")
    parser.add_argument("--runtime-root", type=Path, default=ROOT / "tmp/bap-setup/stable")
    parser.add_argument("--seed-build-dir", type=Path, help="prebuilt Cargo target tree copied into each private test build")
    args = parser.parse_args()
    for spec in MUTATIONS:
        unique_mutation((ROOT / spec["file"]).read_text(), spec)
    if args.check_seams:
        print(json.dumps({"seamsUnique": True, "mutations": [s["name"] for s in MUTATIONS]}, indent=2))
        return
    if args.output is None:
        parser.error("--output is required unless --check-seams is selected")
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / "target").resolve()):
        parser.error("--output must be under this repository's target/ directory")
    seed = args.seed_build_dir.resolve() if args.seed_build_dir else None
    if seed is not None and (not seed.is_dir() or output.is_relative_to(seed) or seed.is_relative_to(output)):
        parser.error("--seed-build-dir must be an existing directory separate from --output")
    output.mkdir(parents=True, exist_ok=False)
    before = inventory()
    helper = args.helper.resolve()
    decoder = args.decoder.resolve()
    runtime = args.runtime_root.resolve()
    for path in (helper, decoder, runtime):
        if not path.exists():
            raise SystemExit(f"required remote helper/runtime missing: {path}")
    env = {**os.environ, "ARIADNE_BAP_HELPER": str(helper),
           "ARIADNE_LLVM_MC": str(decoder), "BAP_RUNTIME_ROOT": str(runtime),
           "CARGO_BUILD_JOBS": "4"}
    records = []
    report = {"schema": "ariadne.bap-vector-mutations/v1", "sourceHashes": before,
              "helperHashes": {"bap": sha256(helper), "decoder": sha256(decoder)},
              "seedBuildDir": str(seed) if seed else None, "mutations": records, "passed": False}
    failure = None
    try:
        for spec in MUTATIONS:
            name = spec["name"]
            directory = output / name
            directory.mkdir()
            sut = directory / "sut"
            manifest = copy_sut(sut)
            observers = {str(p.relative_to(sut)): sha256(p) for p in (sut / "tests").rglob("*") if p.is_file()}
            target = sut / spec["file"]
            original = target.read_text()
            mutant = unique_mutation(original, spec)
            record = {"name": name, "source": spec["file"],
                      "originalSha256": sha256(target), "mutatedSha256": hashlib.sha256(mutant.encode()).hexdigest(),
                      "observers": observers, "checks": []}
            records.append(record)
            for kind, test in spec["tests"]:
                label = kind + "-" + test.rsplit("::", 1)[-1]
                build = directory / "build" / label
                seed_build(build, seed)
                control = run_test(directory, manifest, build, kind, test, env, label + "-control")
                if not control["passed"]:
                    raise RuntimeError(f"{name}: unmodified control did not pass: {test}")
                target.write_text(mutant)
                try:
                    changed = run_test(directory, manifest, build, kind, test, env, label + "-mutant")
                finally:
                    target.write_text(original)
                record["checks"].append({"kind": kind, "test": test, "control": control, "mutant": changed})
                if not changed["assertionRejected"]:
                    raise RuntimeError(f"{name}: mutant was not rejected by expected assertion: {test}")
            record["observersUnchanged"] = all(sha256(sut / p) == digest for p, digest in observers.items())
            record["sourceRestored"] = sha256(target) == record["originalSha256"]
            if not record["observersUnchanged"] or not record["sourceRestored"]:
                raise RuntimeError(f"{name}: SUT source or observers changed after mutation")
            print(f"{name}: {len(record['checks'])} expected assertion rejection(s)", flush=True)
    except (RuntimeError, ValueError) as error:
        failure = str(error)
    finally:
        report["sourcesStable"] = before == inventory()
        report["passed"] = failure is None and report["sourcesStable"] and len(records) == len(MUTATIONS)
        if failure:
            report["failure"] = failure
        (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        print(f"Report: {output / 'report.json'}", flush=True)
    if not report["passed"]:
        raise SystemExit(failure or "source inventory changed during campaign")


if __name__ == "__main__":
    main()
