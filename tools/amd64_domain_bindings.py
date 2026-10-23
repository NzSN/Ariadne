#!/usr/bin/env python3
"""Source-bound finite MOV8 observations for the existing v6 dependency profile.

This additive v4 pilot does not promote candidate associations or expand the
production profile. Actual BAP semantics, independent decode facts, numeric
equations and Rust byte-origin projection are checked separately.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from amd64_inventory import strict_json
from amd64_inventory_xed import digest
import amd64_legal_forms as legacy
from check_bap_admission_oracle import Evaluator, Value
from run_output import run_output

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "bap-bit-provenance-v6"
CONTRACT = "mov8-register-byte-origins/v1"
TARGETS = ["windows-amd64", "linux-amd64"]
RUST_TEST = "bap::projection::mov8_domain_binding_observer::fresh_mov8_domain_observations_match_byte_origins"
BANKS = ["RAX", "RCX", "RDX", "RBX", "RSP", "RBP", "RSI", "RDI"] + [f"R{i}" for i in range(8, 16)]
FLAGS = ["CF", "PF", "AF", "ZF", "SF", "OF", "DF"]
MASK = (1 << 64) - 1


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return strict_json(Path(path).read_text())


def fields(value, names, label):
    require(isinstance(value, dict) and set(value) == set(names), label + " fields")


def sources(root=ROOT):
    root = Path(root)
    names = set(legacy.current_sources(root)) | {
        "tools/amd64_domain_bindings.py", "tools/amd64_domains.py",
        "tools/amd64_reconciliation.py", "tools/amd64_source_constraints.py",
        "tools/check_bap_admission_oracle.py", "tools/i5a_native_contract.py",
        "tests/bap/fixtures/admission/oracle.py", "tests/bap/mov8_domain_binding_observer.rs",
        "native/llvm_mc/decode.cpp", "src/llvm_mc/protocol.rs",
        "src/effects/locations.rs", "src/bap/ast.rs", "src/reports/codecs.rs",
    }
    return {name: legacy.sha(root / name) for name in sorted(names)}


def operands(encoded):
    """Independent byte-field equation; never used by production projection."""
    require(isinstance(encoded, str) and encoded == encoded.lower(), "byte spelling")
    try:
        code = bytes.fromhex(encoded)
    except ValueError as error:
        raise ValueError("byte spelling") from error
    require(len(code) in (2, 3) and code.hex() == encoded, "MOV8 consumed extent")
    rex = code[0] if len(code) == 3 else 0
    opcode, modrm = code[-2:]
    require(rex in (0, 0x40, 0x41, 0x44, 0x45) and opcode in (0x88, 0x8a)
            and modrm >> 6 == 3, "outside the declared MOV8 pilot")
    def register(field, extended):
        if extended:
            return field + 8, 0
        if not rex and field >= 4:
            return field - 4, 1
        return field, 0
    reg = register((modrm >> 3) & 7, bool(rex & 4))
    rm = register(modrm & 7, bool(rex & 1))
    return (rm, reg) if opcode == 0x88 else (reg, rm)


def register_name(operand):
    bank, offset = operand
    if offset:
        return ["AH", "CH", "DH", "BH"][bank]
    return ["AL", "CL", "DL", "BL", "SPL", "BPL", "SIL", "DIL"][bank] if bank < 8 else f"R{bank}B"


def check_numeric(encoded, bil):
    destination, source = operands(encoded)
    db, do = destination
    sb, so = source
    for seed, value in enumerate((0, 1, 0x7f, 0x80, 0xff, 0x0123456789abcdef, 1 << 63, MASK)):
        initial = {name: ((0x9e3779b97f4a7c15 * (index + seed + 1)) ^ (seed << (index % 8 * 8))) & MASK
                   for index, name in enumerate(BANKS)}
        initial[BANKS[sb]] = value
        initial.update({flag: (seed >> (index % 3)) & 1 for index, flag in enumerate(FLAGS)})
        expected = dict(initial)
        expected[BANKS[db]] = ((initial[BANKS[db]] & ~(255 << (do * 8)))
                               | (((initial[BANKS[sb]] >> (so * 8)) & 255) << (do * 8)))
        memory = {}
        evaluator = Evaluator({name: Value(number, 64 if name in BANKS else 1)
                               for name, number in initial.items()}, memory)
        try:
            evaluator.statements(bil)
            require(all(evaluator.values[name].n == value for name, value in expected.items()),
                    "MOV8 numeric register/flag mismatch")
            require(not memory, "register MOV unexpectedly accesses memory")
        except (KeyError, TypeError, AssertionError, IndexError) as error:
            raise ValueError("invalid MOV8 numeric observation") from error
    return 8


def point_key(point):
    return point["form"], point["bytes"], digest(point["environment"])


def validate_inputs(domain, constraints, bindings, pdf, bbox, root=ROOT):
    from amd64_domains import enumerate_domain, validate_mov8_domain
    from amd64_source_constraints import validate_pack
    validate_mov8_domain(domain, source_pack=constraints, root=root)
    validate_pack(constraints, pdf, bbox, root=root)
    points = list(enumerate_domain(domain))
    fields(bindings, {"schema", "domainSha256", "constraintsSha256", "profile", "consumer",
                      "contract", "requiredTargets", "implementationSources", "producerPin",
                      "referencePin", "partitions"}, "finite bindings")
    require(bindings["schema"] == "ariadne.amd64-finite-bindings/v4"
            and bindings["domainSha256"] == digest(domain)
            and bindings["constraintsSha256"] == digest(constraints), "stale finite binding inputs")
    require(bindings["profile"] == PROFILE and bindings["consumer"] == "plain-dependencies"
            and bindings["contract"] == CONTRACT and bindings["requiredTargets"] == TARGETS,
            "unreviewed finite consumer contract")
    require(bindings["implementationSources"] == sources(root), "stale finite binding source closure")
    fields(bindings["producerPin"], {"helperSha256", "runtimeLockSha256"}, "producer pin")
    require(bindings["producerPin"] == read(Path(root) / "tests/bap/fixtures/amd64-semantics/profile-bindings-pilot-v2.json")["producerPin"],
            "producer pin differs from the frozen packaged producer")
    fields(bindings["referencePin"], {"helperSha256", "librarySha256", "version"}, "reference pin")
    require(bindings["referencePin"]["version"] == "ariadne-llvm-mc 20.1.2 protocol 2", "reference version")
    for key in ("helperSha256", "librarySha256"):
        require(isinstance(bindings["referencePin"][key], str)
                and re.fullmatch(r"[0-9a-f]{64}", bindings["referencePin"][key]), "reference digest")
    require(isinstance(bindings["partitions"], list), "partition list")
    classified, names = {}, set()
    domain_keys = {point_key(point) for point in points}
    for partition in bindings["partitions"]:
        fields(partition, {"id", "form", "bytes", "disposition", "reason"}, "partition")
        require(isinstance(partition["id"], str) and partition["id"] not in names
                and partition["disposition"] in ("S", "U", "X") and isinstance(partition["reason"], str)
                and partition["reason"], "partition identity/disposition")
        names.add(partition["id"])
        require(partition["bytes"] == "all" or (isinstance(partition["bytes"], list)
                and all(isinstance(value, str) for value in partition["bytes"])), "partition bytes selector")
        selected = [point for point in points if point["form"] == partition["form"]
                    and (partition["bytes"] == "all" or point["bytes"] in partition["bytes"])]
        require(selected, "empty or unknown partition")
        if partition["bytes"] != "all":
            require(isinstance(partition["bytes"], list) and len(set(partition["bytes"])) == len(partition["bytes"])
                    and {point["bytes"] for point in selected} == set(partition["bytes"]), "binding domain outside legal form")
        for point in selected:
            key = point_key(point)
            require(key not in classified, "overlapping disposition partitions")
            operands(point["bytes"])
            classified[key] = partition["disposition"]
    require(set(classified) == domain_keys, "unassigned domain points")
    return points, classified


def validate_producer(record, bindings, root=ROOT):
    legacy.validate_producer(record, {"producerPin": bindings["producerPin"]}, root)
    require(record["runtimeLockSha256"] == bindings["producerPin"]["runtimeLockSha256"], "runtime pin differs")


def validate_reference(record, bindings):
    fields(record, {"helperPath", "helperSha256", "libraryPath", "librarySha256", "version"}, "reference")
    for name in ("helper", "library"):
        require(legacy.sha(record[name + "Path"]) == record[name + "Sha256"]
                == bindings["referencePin"][name + "Sha256"], "stale reference " + name)
    require(record["version"] == bindings["referencePin"]["version"], "reference handshake version")


def validate_reference_row(record, encoded, va):
    destination, source = operands(encoded)
    code = bytes.fromhex(encoded)
    opcode = "MOV8rr" if code[-2] == 0x88 else "MOV8rr_REV"
    expected = ["v2", opcode, "2", "r:" + register_name(destination), "r:" + register_name(source),
                "1", "0", "0", "0", "-1", "-1", str(va), "ok", str(len(code)), "ordinary", "-"]
    require(isinstance(record, str) and record.split() == expected, "independent decode/control disagreement")
    return opcode


def rust_input(observations):
    return {"rows": observations["rows"]}


def validate_observations(observations, domain, constraints, bindings, pdf, bbox, root=ROOT, require_rust=True):
    points, classified = validate_inputs(domain, constraints, bindings, pdf, bbox, root)
    fields(observations, {"schema", "domainSha256", "constraintsSha256", "bindingsSha256", "implementationSources",
                          "sourceEvidence", "producer", "reference", "rows", "rustObserver"}, "observations")
    require(observations["schema"] == "ariadne.amd64-finite-observations/v4"
            and observations["domainSha256"] == digest(domain)
            and observations["constraintsSha256"] == digest(constraints)
            and observations["bindingsSha256"] == digest(bindings)
            and observations["implementationSources"] == sources(root), "stale observation inputs/sources")
    require(observations["sourceEvidence"] == {"pdfSha256": legacy.sha(pdf), "bboxSha256": legacy.sha(bbox)},
            "source evidence identity")
    validate_producer(observations["producer"], bindings, root)
    validate_reference(observations["reference"], bindings)
    supported = [point for point in points if classified[point_key(point)] == "S"]
    require(len(supported) == 640, "this actual Rust observer requires the complete finite MOV8 pilot")
    expected = {(target, point_key(point)): (index, point) for target in TARGETS for index, point in enumerate(supported)}
    seen, comparisons = set(), 0
    for row in observations["rows"]:
        fields(row, {"target", "point", "response", "reference", "astSha256", "numericCases"}, "observation row")
        key = row["target"], point_key(row["point"])
        require(key in expected and key not in seen and row["point"] == expected[key][1], "omitted, duplicate or wrong domain observation")
        seen.add(key)
        index, point = expected[key]
        va = 0x401000 + index * 32
        snapshot = digest({"domain": digest(domain), "bindings": digest(bindings), "target": row["target"]})
        response = row["response"]
        fields(response, {"schema", "batch", "snapshot", "va", "status", "length", "bytes", "opcode", "properties", "bil"}, "producer response")
        require(response["schema"] == "ariadne.bap-site/v1" and type(response["batch"]) is int
                and response["batch"] == index // 256 and response["snapshot"] == snapshot
                and response["va"] == f"0x{va:016x}" and response["bytes"] == point["bytes"]
                and response["status"] == "decoded" and type(response["length"]) is int
                and response["length"] == len(point["bytes"]) // 2 and response["bil"], "producer request/extent identity")
        opcode = validate_reference_row(row["reference"], point["bytes"], va)
        require(response["opcode"] == opcode and row["astSha256"] == digest(response["bil"]), "producer opcode/AST identity")
        fields(response["properties"], {"jump", "conditional", "indirect", "call", "return", "control"}, "control properties")
        require(all(value is False for value in response["properties"].values()), "register MOV control/memory properties")
        count = check_numeric(point["bytes"], response["bil"])
        require(type(row["numericCases"]) is int and row["numericCases"] == count, "numeric case count")
        comparisons += count
    require(seen == set(expected), "missing supported observations")
    observer = observations["rustObserver"]
    if observer is not None:
        fields(observer, {"test", "inputSha256", "stdout", "stderr"}, "Rust observer")
        require(observer["test"] == RUST_TEST and observer["inputSha256"] == digest(rust_input(observations))
                and isinstance(observer["stdout"], str) and isinstance(observer["stderr"], str)
                and f"test {RUST_TEST} ... ok" in observer["stdout"]
                and "test result: ok. 1 passed; 0 failed;" in observer["stdout"], "Rust observer identity/result")
    require(not require_rust or observer is not None, "missing actual Rust binding observer")
    return dict(schema="ariadne.amd64-finite-binding-assessment/v4", domainPoints=len(points),
                observations=len(seen), numericCases=comparisons, profileBindingsValidated=observer is not None,
                finiteProjectionComplete=observer is not None and all(value == "S" for value in classified.values()),
                nativeConsumerValidated=False, finiteImplementationComplete=False,
                candidateFullDomainBindings=0, sourceComplete=False, vendorFullDenominator=False, fullAmd64Coverage=False,
                consumer="plain-dependencies", profile=PROFILE,
                precisionLimit="Existing v6 reverse-encoding self MOV keeps no definite kill; byte uses/possible writes are exact.")


def build(domain, constraints, bindings, pdf, bbox, helper, runtime, reference, library, root=ROOT):
    points, classified = validate_inputs(domain, constraints, bindings, pdf, bbox, root)
    require(all(value == "S" for value in classified.values()), "fresh pilot observer requires all points supported")
    helper, runtime, reference, library = [Path(p).resolve() for p in (helper, runtime, reference, library)]
    producer = dict(helperPath=str(helper), helperSha256=legacy.sha(helper), runtimeRoot=str(runtime),
                    runtimeLockPath="native/bap/toolchain.lock.json", runtimeLockSha256=legacy.sha(Path(root) / "native/bap/toolchain.lock.json"))
    decode = dict(helperPath=str(reference), helperSha256=legacy.sha(reference), libraryPath=str(library),
                  librarySha256=legacy.sha(library), version=bindings["referencePin"]["version"])
    validate_producer(producer, bindings, root)
    validate_reference(decode, bindings)
    result = dict(schema="ariadne.amd64-finite-observations/v4", domainSha256=digest(domain),
                  constraintsSha256=digest(constraints), bindingsSha256=digest(bindings), implementationSources=sources(root),
                  sourceEvidence={"pdfSha256": legacy.sha(pdf), "bboxSha256": legacy.sha(bbox)}, producer=producer,
                  reference=decode, rows=[], rustObserver=None)
    env = {**os.environ, "LD_LIBRARY_PATH": str(runtime / "usr/local/lib") + ":" + str(runtime / "usr/lib/x86_64-linux-gnu"),
           "XDG_STATE_HOME": str(runtime / "state"), "XDG_CACHE_HOME": str(runtime / "cache")}
    for target in TARGETS:
        snapshot = digest({"domain": digest(domain), "bindings": digest(bindings), "target": target})
        command = f"ARIADNE-BAP-LIFT 1 {target} {snapshot}\n"
        for batch, start in enumerate(range(0, len(points), 256)):
            block = points[start:start + 256]
            command += f"batch {batch} {len(block)}\n" + "".join(f"0x{0x401000 + (start + i) * 32:016x} {point['bytes']}\n" for i, point in enumerate(block))
        process = subprocess.run([str(helper), str(runtime / "usr/local/lib/bap")], input=command,
                                 text=True, capture_output=True, env=env, timeout=300)
        require(process.returncode == 0, "fresh producer failed: " + process.stderr[-2000:])
        frames = [strict_json(line) for line in process.stdout.splitlines()]
        require(frames and frames[0] == {"schema": "ariadne.bap-ready/v1", "snapshot": snapshot, "target": target,
                                        "version": "2.5.0-alpha", "lifter": "legacy"}, "producer ready identity")
        lifted, cursor = [], 1
        for batch, start in enumerate(range(0, len(points), 256)):
            count = min(256, len(points) - start)
            lifted += frames[cursor:cursor + count]
            cursor += count
            require(cursor < len(frames) and frames[cursor] == {"schema": "ariadne.bap-batch/v1", "batch": batch, "count": count}, "producer batch boundary")
            cursor += 1
        require(cursor == len(frames), "unexpected producer frames")
        command = "".join(f"{0x401000 + i * 32} {point['bytes']}\n" for i, point in enumerate(points))
        option = "--protocol=2-checked" + ("-linux" if target == "linux-amd64" else "")
        process = subprocess.run([str(reference), option], input=command, text=True, capture_output=True,
                                 env={**os.environ, "LD_LIBRARY_PATH": str(library.parent)}, timeout=60)
        require(process.returncode == 0, "fresh reference failed: " + process.stderr[-2000:])
        lines = process.stdout.splitlines()
        ready = decode["version"] + (" target x86_64-unknown-linux-gnu" if target == "linux-amd64" else "")
        require(len(lines) == len(points) + 1 and lines[0] == ready, "reference handshake/frame count")
        for point, response, line in zip(points, lifted, lines[1:]):
            result["rows"].append(dict(target=target, point=point, response=response, reference=line,
                                       astSha256=digest(response.get("bil")), numericCases=8))
    validate_observations(result, domain, constraints, bindings, pdf, bbox, root, require_rust=False)
    with tempfile.TemporaryDirectory(prefix="ariadne-mov8-bindings-") as directory:
        path = Path(directory) / "lifts.json"
        path.write_text(json.dumps(rust_input(result)))
        test = subprocess.run(["cargo", "test", "--offline", "--locked", "--lib", RUST_TEST, "--", "--ignored", "--exact"],
                              cwd=root, env={**os.environ, "ARIADNE_MOV8_BINDING_OBSERVATIONS": str(path)},
                              text=True, capture_output=True, timeout=600)
        require(test.returncode == 0, "fresh Rust observer failed: " + test.stdout[-2500:] + test.stderr[-2500:])
        result["rustObserver"] = dict(test=RUST_TEST, inputSha256=digest(rust_input(result)), stdout=test.stdout, stderr=test.stderr)
    validate_observations(result, domain, constraints, bindings, pdf, bbox, root)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "check"))
    for name in ("domain", "constraints", "bindings", "pdf", "bbox", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--observations", type=Path)
    parser.add_argument("--helper", type=Path, default=ROOT / "target/ariadne-bap-lift")
    parser.add_argument("--runtime", type=Path, default=ROOT / "tmp/bap-setup/stable")
    parser.add_argument("--reference", type=Path, default=ROOT / "target/ariadne-llvm-mc")
    parser.add_argument("--reference-library", type=Path, default=ROOT / "target/resume-llvm20/usr/lib/x86_64-linux-gnu/libLLVM.so.20.1")
    args = parser.parse_args()
    common = [read(args.domain), read(args.constraints), read(args.bindings), args.pdf, args.bbox]
    if args.action == "build":
        result = build(*common, args.helper, args.runtime, args.reference, args.reference_library)
    else:
        require(args.observations is not None, "check requires observations")
        result = validate_observations(read(args.observations), *common)
    output = run_output(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(str(output))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as error:
        print("Finite binding rejected: " + str(error), file=sys.stderr)
        sys.exit(2)
