#!/usr/bin/env python3
"""Fresh finite memory-MOV8 native consumption, separate from producer validation.

Run through with_mirrorrust_snapshot.py. All outputs are disposable. The four
existing register/native barrier tests are regressions in this same source and
executed-artifact freeze, not imported acceptance from a saved report.
"""
import argparse
import copy
import json
import math
from pathlib import Path
import subprocess

import amd64_domains as domains
import amd64_memory_bindings as memory
import check_amd64_mov8_native as register

ROOT = domains.ROOT
INPUT = ROOT / "tests/bap/fixtures/amd64-semantics/mov8-memory-domain"
SCHEMA = "ariadne.amd64-mov8-memory-native-assessment/v1"
PREFIX = register.TEST_PREFIX + "memory::"
MEMORY_TESTS = (
    ("memory-domain", PREFIX + "memory_domain_has_independent_address_and_alias_partitions", None),
    ("memory-consumer", PREFIX + "native_memory_mov8_preserves_byte_and_weak_memory_origins",
     "MOV8_MEMORY_NATIVE points=2880 targets=2 instances=5760 batches=90 loads=2880 stores=2880 weak_memory_updates=2880"),
    ("memory-address32", PREFIX + "native_memory_mov8_address32_stops_before_consumers",
     "MOV8_MEMORY_ADDRESS32 points=2880 targets=2 refused_instances=5760 batches=90 decoded=0 consumer_starts=0 known_addresses=0 definite_writes=0"),
)
TESTS = MEMORY_TESTS + register.TESTS


def source_closure():
    result = register.source_closure()
    result.update(memory.sources())
    result.update({name: register.sha(ROOT / name) for name in (
        "tools/check_amd64_mov8_memory_native.py", "tools/test_amd64_mov8_memory_native.py")})
    return dict(sorted(result.items()))


def validate_domain(document, points, partitions):
    register.require(len(points) == 5760 and len({register.bindings_tool.point_key(p) for p in points}) == 5760,
                     "memory native domain omission or duplication")
    register.require(points == domains.memory_mov8_points(), "memory native domain differs from independent finite enumeration")
    assigned = {(p["form"], p["addressBits"]): p["disposition"] for p in partitions}
    expected = {(form, bits): "S" if bits == 64 else "U" for form in domains.MEMORY_FORMS for bits in (32, 64)}
    register.require(len(partitions) == 4 and assigned == expected, "memory native partitions omit or admit address32 points")
    register.require(document["scope"]["sourceComplete"] is False
                     and document["scope"]["vendorFullDenominator"] is False,
                     "finite memory gate cannot establish the full source/vendor domain")
    return dict(points=5760, supportedPoints=2880, refusedPoints=2880,
                domainSha256=domains.digest(document), sourceComplete=False, vendorFullDenominator=False)


def inventory(config):
    # Reuse actual source/tool/library/SDK and read-only dependency validation.
    # The register regression input is validated afresh, not a retained receipt.
    reg = copy.copy(config)
    reg.domain = register.INPUT / "legal-domain.json"
    reg.constraints = register.INPUT / "source-constraints.json"
    reg.bindings = register.INPUT / "profile-bindings.json"
    result = register.inventory(reg)
    result["registerRegressionInputs"] = {name: result[name] for name in ("inputPaths", "inputHashes", "domain")}
    document, constraints, bindings = (register.read(path) for path in (config.domain, config.constraints, config.bindings))
    points = memory.validate_inputs(document, constraints, bindings, config.pdf, config.bbox)
    result["domain"] = validate_domain(document, points, bindings["partitions"])
    result["sourceHashes"] = source_closure()
    result["inputPaths"] = {name: str(getattr(config, name)) for name in ("domain", "constraints", "bindings", "pdf", "bbox")}
    result["inputHashes"] = {name: register.sha(getattr(config, name)) for name in result["inputPaths"]}
    return result


def result_fields(passed):
    return dict(schema=SCHEMA, domainPoints=5760, supportedPoints=2880, refusedPoints=2880,
        nativeCaptureInstances=5760 if passed else 0, nativeRefusedInstances=5760 if passed else 0,
        nativeAnalysisBatches=180 if passed else 0, registerRegressionInstances=1280 if passed else 0,
        registerRegressionValidated=passed, address32ProducerQualified=False,
        scope="Finite address64 memory-MOV8 native byte-origin/weak-write consumption and address32 refusal in synthetic Windows/Linux minidumps; current register/native barriers rerun in the same source/tool/test-artifact freeze.",
        limits=["Pinned BAP lifting and reader-normalized effects remain trusted inputs.",
                "Synthetic captures do not establish actual program execution or an executed writer.",
                "Address32 points remain refused, including numerically matching producer samples.",
                "The producer/projection assessment, wider grammar, authoritative full domains and full AMD64 support remain separate."])


def qualify(config, *, runner=subprocess.run, inspect=inventory):
    return register.qualify(config, runner=runner, inspect=inspect, tests=TESTS, result_fields=result_fields)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--domain", type=Path, default=INPUT / "legal-domain.json")
    parser.add_argument("--constraints", type=Path, default=ROOT / domains.ARCHITECTURE_PACK_PATH)
    parser.add_argument("--bindings", type=Path, default=INPUT / "profile-bindings.json")
    parser.add_argument("--pdf", type=Path, default=ROOT / "target/amd-manual-inventory/24594_3.38_APM_Vol3_PUB.pdf")
    parser.add_argument("--bbox", type=Path, default=ROOT / "target/tool-recovery/source-replay/corpus/24594/bbox.html")
    parser.add_argument("--helper", type=Path, default=ROOT / "target/ariadne-bap-lift")
    parser.add_argument("--runtime", type=Path, default=ROOT / "target/tool-recovery/helper-candidate-v1/base-runtime")
    parser.add_argument("--reference", type=Path, default=ROOT / "target/ariadne-llvm-mc")
    parser.add_argument("--reference-library", type=Path, default=ROOT / "target/resume-llvm20/usr/lib/x86_64-linux-gnu/libLLVM.so.20.1")
    parser.add_argument("--core", type=Path, default=ROOT / "target/resume-native-v15/core")
    parser.add_argument("--timeout", type=float, default=1800)
    config = parser.parse_args()
    register.require(math.isfinite(config.timeout) and config.timeout > 0, "native timeout must be finite and positive")
    for name, value in vars(config).items():
        if isinstance(value, Path):
            setattr(config, name, value.resolve())
    result = qualify(config)
    print(json.dumps({key: result[key] for key in ("schema", "nativeConsumerValidated", "nativeCaptureInstances", "nativeRefusedInstances", "registerRegressionValidated", "error")}))
    return 0 if result["nativeConsumerValidated"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
