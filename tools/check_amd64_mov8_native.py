#!/usr/bin/env python3
"""Fresh native qualification of the finite 640-point register MOV8 domain.

Run through with_mirrorrust_snapshot.py. This gate consumes current sources and
tools, never a saved pass receipt. Its native claim is separate from the v4
projection assessment and from memory-form, vendor-wide or ISA qualification.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import amd64_domain_bindings as bindings_tool
from amd64_inventory_xed import digest
from i5a_native_contract import CORE_SOURCES
from run_output import run_output
from rust_layout import source_files
from with_mirrorrust_snapshot import active_identity

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "tests/bap/fixtures/amd64-semantics/mov8-domain"
SCHEMA = "ariadne.amd64-mov8-native-assessment/v1"
NATIVE_HELPER_SHA256 = "c32385208f2e4a779b7940927504c2b7a61482bb9bd7bd00a6e7ee8f0861888c"
NATIVE_MANIFEST_SHA256 = "1d0158ef254fd2a2a6ecf11bd9ad2758ee8426cead6af4d5820dbd5668deb62f"
TEST_PREFIX = "bap::projection::mov8_native_consumer::"
TESTS = (
    ("domain", TEST_PREFIX + "mov8_native_domain_keeps_all_alias_partitions", None),
    ("consumer", TEST_PREFIX + "native_mov8_domain_preserves_all_register_byte_origins",
     "MOV8_NATIVE_CONSUMER points=640 targets=2 instances=1280 independent_root_batches=20 definite_write_instances=1232 may_only_instances=48"),
    ("boundary", TEST_PREFIX + "native_mov8_boundary_controls_keep_host_and_native_claims_separate",
     "MOV8_NATIVE_BOUNDARY host_byte_refusals=20 host_profile_refusals=2 host_target_refusals=2 native_structural_refusals=120"),
    ("address32-barrier", TEST_PREFIX + "address_size_guard::native_address32_mov8_producer_errors_stay_behind_prefix_barrier",
     "MOV8_ADDRESS32_BARRIER actual_bad_lifts=6 profile_refusals=78 native_stopped_instances=18 known_address_claims=0 target_transfers=0 refinement_receipts=0"),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return bindings_tool.legacy.sha(path)


def read(path):
    return bindings_tool.read(path)


def source_closure():
    paths = set(source_files())
    paths.update(ROOT / name for name in bindings_tool.sources())
    paths.update((ROOT / "native/bap-core").glob("*.ml"))
    paths.update(ROOT / name for name in (
        "tools/check_amd64_mov8_native.py", "tools/test_amd64_mov8_native.py",
        "tools/with_mirrorrust_snapshot.py", "tools/run_output.py",
        "native/bap-core/build.py", "native/bap-core/setup-sdk.py",
    ))
    paths.update((ROOT / ".cargo").glob("config*"))
    paths.update(ROOT / name for name in ("rust-toolchain", "rust-toolchain.toml") if (ROOT / name).is_file())
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(paths)}


def labeled_digest(label, *values):
    return hashlib.sha256((label + "\n" + "\n".join(values) + "\n").encode()).hexdigest()


def expected_core_fields():
    caller = ROOT / "tests/bap/fixtures/caller-coverage/legacy-v2"
    legacy = ROOT / "tests/bap/fixtures/loop-closure/legacy-v1"
    caller_manifest = read(caller.parent / "legacy-manifest.json")
    guard_model = sha(ROOT / "Specs/AriadnePredicateAdmission.tla")
    guard_source = sha(ROOT / "src/bap/guard_admission.rs")
    terminal_source = sha(ROOT / "src/bap/terminal_control.rs")
    guard = labeled_digest("ariadne.guard-checker/v2", guard_source, terminal_source)
    advanced_guard = labeled_digest("ariadne.guard-checker/v3", guard_source, terminal_source)
    loop_model = sha(ROOT / "Specs/AriadneLoopTargetClosure.tla")
    loop = labeled_digest("ariadne.loop-target-engine/v1", sha(ROOT / "src/bap/target_resolution.rs"),
                          sha(ROOT / "src/bap/target_resolution/loop_closure.rs"))
    composition = sha(ROOT / "src/bap/composition.rs")
    return dict(compiler="4.12.1", bap_revision=read(ROOT / "native/bap-core/sdk.lock.json")["bapSourceRevision"],
        sdk_manifest_sha256=sha(ROOT / "target/bap-core-sdk/sdk-manifest.json"),
        guard_model_sha256=guard_model, guard_engine_sha256=guard, advanced_guard_engine_sha256=advanced_guard,
        advanced_composition_engine_sha256=labeled_digest("ariadne.guarded-target-checker/v4", composition, loop, advanced_guard),
        legacy_guard_model_sha256=sha(caller / "AriadnePredicateAdmission.tla.txt"),
        legacy_guard_engine_sha256=sha(caller / "guard_admission.rs.txt"),
        composition_model_sha256=labeled_digest("ariadne.guarded-target-model/v3",
            sha(ROOT / "Specs/AriadneGuardedTargetResolution.tla"), loop_model, guard_model),
        composition_engine_sha256=labeled_digest("ariadne.guarded-target-checker/v3", composition, loop, guard),
        legacy_composition_model_sha256=sha(legacy / "AriadneGuardedTargetResolution.tla.txt"),
        legacy_composition_engine_sha256=sha(legacy / "composition.rs.txt"),
        legacy_composition_v2_model_sha256=caller_manifest["composition_v2_model_sha256"],
        legacy_composition_v2_engine_sha256=caller_manifest["composition_v2_checker_sha256"],
        loop_model_sha256=loop_model, loop_engine_sha256=loop)


def validate_core(directory):
    directory = Path(directory)
    require(sha(directory / "manifest.json") == NATIVE_MANIFEST_SHA256
            and sha(directory / "ariadne-bap-core") == NATIVE_HELPER_SHA256,
            "native core differs from this gate's reviewed selection")
    manifest = read(directory / "manifest.json")
    require(manifest["schema"] == "ariadne.bap-core-build/v1"
            and manifest["helper_sha256"] == NATIVE_HELPER_SHA256
            and manifest["lock_sha256"] == sha(ROOT / "native/bap-core/sdk.lock.json"), "native manifest identity")
    expected_sources = {name: sha(ROOT / "native/bap-core" / name) for name in CORE_SOURCES}
    require(manifest["handshake"]["source_hashes"] == expected_sources, "native source bindings are stale")
    fields = expected_core_fields()
    require(all(manifest["handshake"].get(name) == value for name, value in fields.items()),
            "native model, SDK or compiler bindings are stale")
    return dict(helperSha256=NATIVE_HELPER_SHA256, manifestSha256=NATIVE_MANIFEST_SHA256,
                sourceHashes=expected_sources, currentFields=fields)


def validate_domain(points, classified):
    expected = {(prefix + f"{opcode:02x}{modrm:02x}") for prefix in ("", "40", "41", "44", "45")
                for opcode in (0x88, 0x8a) for modrm in range(0xc0, 0x100)}
    require(len(points) == 640 and len({bindings_tool.point_key(point) for point in points}) == 640
            and {point["bytes"] for point in points} == expected, "native observer domain differs from exact 640 byte points")
    require(set(classified) == {bindings_tool.point_key(point) for point in points}
            and all(value == "S" for value in classified.values()), "native domain has unsupported or unassigned points")
    return dict(points=640, bytesSha256=digest(sorted(expected)), profile=bindings_tool.PROFILE,
                consumer="plain-dependencies", targets=bindings_tool.TARGETS)


def execution_environment(config, cargo_target, rustc):
    env = dict(os.environ)
    for key in list(env):
        if key in {"LD_PRELOAD", "RUSTC_WRAPPER", "RUSTC_WORKSPACE_WRAPPER", "RUSTFLAGS", "CARGO_ENCODED_RUSTFLAGS",
                   "RUSTDOCFLAGS", "RUST_TEST_NOCAPTURE", "CARGO_BUILD_TARGET", "CARGO_BUILD_RUSTFLAGS"} or (
                key.startswith("CARGO_TARGET_") and key.endswith(("_RUNNER", "_RUSTFLAGS"))):
            env.pop(key)
    env.update(ARIADNE_BAP_HELPER=str(config.helper), BAP_RUNTIME_ROOT=str(config.runtime),
               ARIADNE_LLVM_MC=str(config.reference), ARIADNE_BAP_CORE_DIR=str(config.core),
               LD_LIBRARY_PATH=str(config.reference_library.parent), CARGO_TARGET_DIR=str(cargo_target),
               CARGO_TERM_COLOR="never", RUSTC=str(rustc), RUST_BACKTRACE="0")
    return env


def linked_libraries(executable, env):
    process = subprocess.run(["ldd", str(executable)], env=env, text=True, capture_output=True, check=True, timeout=30)
    require("not found" not in process.stdout, "unresolved native execution library")
    paths = re.findall(r"(?:=>\s+)?(/[^\s]+)\s+\(0x", process.stdout)
    return {str(Path(path).resolve()): sha(path) for path in paths}


def core_environment(env):
    # Match FamilySession::start_profile and the direct native refusal observer.
    result = dict(env)
    for name in ("OPAMROOT", "OPAMSWITCH", "OPAM_SWITCH_PREFIX", "OCAMLPATH", "OCAMLLIB",
                 "CAML_LD_LIBRARY_PATH", "OCAML_TOPLEVEL_PATH", "OCAMLTOP_INCLUDE_PATH",
                 "LD_LIBRARY_PATH", "LD_PRELOAD"):
        result.pop(name, None)
    return result


def rust_tools():
    result = {}
    for name in ("cargo", "rustc"):
        path = Path(subprocess.check_output(["rustup", "which", name], text=True).strip()).resolve()
        result[name] = dict(path=str(path), sha256=sha(path))
    result["rustc"]["version"] = subprocess.check_output([result["rustc"]["path"], "-vV"], text=True)
    result["python"] = dict(path=str(Path(sys.executable).resolve()), sha256=sha(sys.executable))
    cargo_home = Path(os.environ.get("CARGO_HOME", str(Path.home() / ".cargo")))
    result["cargoConfiguration"] = {str(path.resolve()): sha(path)
                                    for path in (cargo_home / "config", cargo_home / "config.toml") if path.is_file()}
    return result


def inventory(config):
    environment = active_identity()
    require(environment is not None, "run this qualification through tools/with_mirrorrust_snapshot.py")
    domain, constraints, bindings = (read(path) for path in (config.domain, config.constraints, config.bindings))
    points, classified = bindings_tool.validate_inputs(domain, constraints, bindings, config.pdf, config.bbox)
    scope = validate_domain(points, classified)
    producer = dict(helperPath=str(config.helper), helperSha256=sha(config.helper), runtimeRoot=str(config.runtime),
                    runtimeLockPath="native/bap/toolchain.lock.json", runtimeLockSha256=sha(ROOT / "native/bap/toolchain.lock.json"))
    reference = dict(helperPath=str(config.reference), helperSha256=sha(config.reference),
                     libraryPath=str(config.reference_library), librarySha256=sha(config.reference_library),
                     version=bindings["referencePin"]["version"])
    bindings_tool.validate_producer(producer, bindings)
    bindings_tool.validate_reference(reference, bindings)
    core = validate_core(config.core)
    toolchain = rust_tools()
    env = execution_environment(config, Path(config.output) / "cargo", toolchain["rustc"]["path"])
    producer_env = {**env, "LD_LIBRARY_PATH": str(config.runtime / "usr/local/lib") + ":" + str(config.runtime / "usr/lib/x86_64-linux-gnu")}
    libraries = {
        "producer": linked_libraries(config.helper, producer_env),
        "reference": linked_libraries(config.reference, env),
        "nativeCore": linked_libraries(config.core / "ariadne-bap-core", core_environment(env)),
    }
    runtime_files = {name: sha(config.runtime / name) for name in read(ROOT / "native/bap/toolchain.lock.json")["files"]}
    require(reference["librarySha256"] in libraries["reference"].values(), "selected LLVM library is not the linked runtime")
    require(runtime_files["usr/local/lib/libbap.so.2.5.0"] in libraries["producer"].values(),
            "selected BAP library is not the linked runtime")
    return dict(sourceHashes=source_closure(), inputPaths={name: str(getattr(config, name)) for name in
        ("domain", "constraints", "bindings", "pdf", "bbox")}, inputHashes={name: sha(getattr(config, name)) for name in
        ("domain", "constraints", "bindings", "pdf", "bbox")}, domain=scope,
        producer=producer, reference=reference, nativeCore=core, packagedRuntimeFiles=runtime_files,
        executionLibraries=libraries, toolchain=toolchain, qualificationEnvironment=environment)


def validate_test_process(process, name, marker):
    require(process.returncode == 0, "native test command failed: " + name)
    stdout, stderr = process.stdout, process.stderr
    require(isinstance(stdout, str) and isinstance(stderr, str), "missing native test transcript")
    require(re.findall(r"^running (\d+) tests?$", stdout, re.M) == ["1"], "native gate did not select exactly one test")
    cases = re.findall(r"^test (\S+) \.\.\. (ok|FAILED|ignored[^\n]*)$", stdout, re.M)
    require(cases == [(name, "ok")], "missing, duplicate, ignored or wrong native test")
    summaries = re.findall(r"^test result: ([^\n]+)$", stdout, re.M)
    require(len(summaries) == 1 and re.fullmatch(
        r"ok\. 1 passed; 0 failed; 0 ignored; 0 measured; \d+ filtered out; finished in [0-9.]+s", summaries[0]) is not None,
        "native test summary is incomplete or failed")
    if marker is not None:
        lines = (stdout + "\n" + stderr).splitlines()
        require(lines.count(marker) == 1, "native observation counts or boundary counters differ")
        prefix = marker.split()[0]
        require(sum(line.startswith(prefix) for line in lines) == 1, "duplicate or conflicting native metrics")
    return dict(test=name, selected=1, passed=1, marker=marker)


def test_artifact(process, cargo_target):
    paths = re.findall(r"^\s*Running unittests [^\n]* \(([^\n)]+)\)$", process.stderr, re.M)
    require(len(paths) == 1, "missing or ambiguous executed Rust test artifact")
    path = Path(paths[0])
    if not path.is_absolute():
        path = ROOT / path
    require(not path.is_symlink() and path.resolve().is_relative_to(cargo_target.resolve())
            and path.is_file(), "executed Rust test artifact is outside isolated Cargo target")
    return dict(path=str(path.resolve()), sha256=sha(path))


def qualify(config, *, runner=subprocess.run, inspect=inventory, tests=TESTS, result_fields=None):
    require(bool(tests), "native qualification must select named tests")
    require(math.isfinite(config.timeout) and config.timeout > 0, "native timeout must be finite and positive")
    output = run_output(config.output)
    require(not output.exists(), "native qualification requires a fresh output directory")
    output.mkdir(parents=True)
    before, after, gates, error, artifact_stable = None, None, [], None, False
    try:
        before = inspect(config)
        cargo = before["toolchain"]["cargo"]["path"]
        env = execution_environment(config, output / "cargo", before["toolchain"]["rustc"]["path"])
        for label, name, marker in tests:
            command = [cargo, "test", "--offline", "--locked", "--release", "--lib", name,
                       "--", "--exact", "--include-ignored", "--show-output", "--test-threads=1"]
            start = time.monotonic()
            process = runner(command, cwd=ROOT, env=env, text=True, capture_output=True, timeout=config.timeout)
            stdout, stderr = output / (label + ".stdout"), output / (label + ".stderr")
            stdout.write_text(process.stdout)
            stderr.write_text(process.stderr)
            gate = dict(name=label, command=command, exitCode=process.returncode,
                        seconds=round(time.monotonic() - start, 6),
                        stdoutSha256=sha(stdout), stderrSha256=sha(stderr), validated=False)
            gates.append(gate)
            gate["result"] = validate_test_process(process, name, marker)
            gate["testArtifact"] = test_artifact(process, output / "cargo")
            require(gate["testArtifact"] == gates[0]["testArtifact"], "Rust test artifact changed between native gates")
            gate["validated"] = True
        after = inspect(config)
        require(after == before, "native qualification source, tool, domain or dependency changed during execution")
        artifact = gates[0]["testArtifact"]
        require(sha(artifact["path"]) == artifact["sha256"], "executed Rust test artifact changed after the last gate")
        artifact_stable = True
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as failure:
        error = str(failure)
    passed = error is None and bool(tests) and len(gates) == len(tests) and all(gate["validated"] for gate in gates)
    result = dict(schema=SCHEMA, recordedUtc=datetime.now(timezone.utc).isoformat(),
        nativeConsumerValidated=passed, sourcesStable=before is not None and before == after,
        testArtifactStable=artifact_stable,
        sourceInputs=before, afterInputs=after, gates=gates, error=error,
        domainPoints=640, nativeCaptureInstances=1280 if passed else 0, nativeAnalysisBatches=20 if passed else 0,
        targets=bindings_tool.TARGETS, profile=bindings_tool.PROFILE, consumer="plain-dependencies",
        address32ProducerQualified=False, sourceComplete=False, vendorFullDenominator=False,
        fullAmd64Coverage=False, universalIsaValidation=False,
        scope="Fresh native consumption of 1280 independent register MOV8 instruction instances in 20 minidump analysis batches across two target profiles; address-32 producer gaps remain refused.",
        limits=["BAP instruction lifting and reader-normalized effects remain trusted inputs.",
                "Native structural refusals do not independently decode or reject self-consistent forged effects.",
                "The v4 projection assessment and its flags are unchanged; memory forms and full XED/AMD coverage are separate."])
    if result_fields is not None:
        result.update(result_fields(passed))
    (output / "assessment.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--domain", type=Path, default=INPUT / "legal-domain.json")
    parser.add_argument("--constraints", type=Path, default=INPUT / "source-constraints.json")
    parser.add_argument("--bindings", type=Path, default=INPUT / "profile-bindings.json")
    parser.add_argument("--pdf", type=Path, default=ROOT / "target/amd-manual-inventory/24594_3.38_APM_Vol3_PUB.pdf")
    parser.add_argument("--bbox", type=Path, default=ROOT / "target/tool-recovery/source-replay/corpus/24594/bbox.html")
    parser.add_argument("--helper", type=Path, default=ROOT / "target/checkpoint-resume-mov8/ariadne-bap-lift")
    parser.add_argument("--runtime", type=Path, default=ROOT / "tmp/bap-setup/stable")
    parser.add_argument("--reference", type=Path, default=ROOT / "target/tool-recovery/helpers/llvm-gcc13-resume-path")
    parser.add_argument("--reference-library", type=Path, default=ROOT / "target/tool-recovery/helpers/llvm20-plucky/usr/lib/x86_64-linux-gnu/libLLVM.so.20.1")
    parser.add_argument("--core", type=Path, default=ROOT / "target/resume-native-v15/core")
    parser.add_argument("--timeout", type=float, default=1800)
    args = parser.parse_args()
    require(math.isfinite(args.timeout) and args.timeout > 0, "native timeout must be finite and positive")
    for name, value in vars(args).items():
        if isinstance(value, Path):
            setattr(args, name, value.resolve())
    result = qualify(args)
    print(json.dumps(dict(schema=SCHEMA, nativeConsumerValidated=result["nativeConsumerValidated"],
                         nativeCaptureInstances=result["nativeCaptureInstances"], error=result["error"],
                         assessment=str(args.output / "assessment.json"))))
    return 0 if result["nativeConsumerValidated"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
