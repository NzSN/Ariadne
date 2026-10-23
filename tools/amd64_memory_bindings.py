#!/usr/bin/env python3
"""Finite MOV8 memory observations; independent EA equations are test oracles.

This module does not supply production instruction semantics. Unsupported BAP
address behavior stays unbound, and no finite result closes an XED candidate.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile

import amd64_domain_bindings as register
import amd64_domains as domains
from check_bap_admission_oracle import Evaluator, Value

ROOT = domains.ROOT
QUERY_BASE = 0x200401000
BANKS = register.BANKS
FLAGS = register.FLAGS
MASK = register.MASK
PROFILE = "bap-bit-provenance-v6"
CONTRACT = "mov8-memory-address64-byte-origins/v1"
RUST_TEST = "bap::projection::mov8_memory_domain_binding_observer::fresh_memory_mov8_observations_preserve_origins_and_prefix_refusals"


def sources(root=ROOT):
    names = set(register.sources(root)) | {"tools/amd64_memory_bindings.py",
        "tests/bap/mov8_memory_domain_binding_observer.rs"}
    return {name: domains.sha(Path(root) / name) for name in sorted(names)}


def validate_inputs(document, constraints, bindings, pdf, bbox, root=ROOT):
    from amd64_source_constraints import validate_pack, validate_architecture_pack
    points = domains.validate_memory_mov8_domain(document, root=root)
    register.require(domains.digest(constraints) == domains.digest(domains.read(Path(root) / domains.ARCHITECTURE_PACK_PATH)),
                     "substituted memory architectural constraints")
    validate_pack(domains.read(Path(root) / domains.PACK_PATH), pdf, bbox, root=root)
    validate_architecture_pack(constraints, pdf, bbox, root=root)
    register.fields(bindings, {"schema", "domainSha256", "sourcePacksSha256", "profile", "consumer", "contract",
        "implementationSources", "producerPin", "referencePin", "requiredTargets", "partitions"}, "memory binding")
    register.require(bindings["schema"] == "ariadne.amd64-memory-bindings/v1"
        and bindings["domainSha256"] == domains.digest(document)
        and bindings["sourcePacksSha256"] == domains.digest(document["sourcePacks"])
        and bindings["implementationSources"] == sources(root), "stale memory binding inputs/sources")
    register.require(bindings["profile"] == PROFILE and bindings["consumer"] == "plain-dependencies"
        and bindings["contract"] == CONTRACT and bindings["requiredTargets"] == register.TARGETS,
        "unreviewed memory contract/consumer")
    frozen = register.read(Path(root) / "tests/bap/fixtures/amd64-semantics/mov8-domain/profile-bindings.json")
    register.require(bindings["producerPin"] == frozen["producerPin"] and bindings["referencePin"] == frozen["referencePin"],
                     "memory producer/reference differs from qualified helper identities")
    register.require(isinstance(bindings["partitions"], list), "memory partitions")
    selected = set()
    for partition in bindings["partitions"]:
        register.fields(partition, {"id", "form", "addressBits", "disposition", "reason"}, "memory partition")
        form, bits = partition["form"], partition["addressBits"]
        register.require(form in domains.MEMORY_FORMS and type(bits) is int and bits in {32, 64}
            and partition["id"] == f"{form}-address{bits}"
            and partition["disposition"] == ("S" if bits == 64 else "U")
            and isinstance(partition["reason"], str) and partition["reason"], "memory partition capability")
        register.require((form, bits) not in selected, "overlapping memory partitions")
        selected.add((form, bits))
    register.require(selected == {(form, bits) for form in domains.MEMORY_FORMS for bits in (32, 64)},
                     "memory partition omission")
    return points


class MemoryEvaluator(Evaluator):
    def __init__(self, registers, memory):
        super().__init__(registers, memory)
        self.accesses = []

    def expr(self, expression):
        kind = expression["kind"]
        if kind in {"load", "store"}:
            register.require(expression["width"] == 8, "MOV8 oracle memory width")
            memory = self.expr(expression["mem"])
            address = self.expr(expression["addr"]).n
            self.accesses.append((kind, address))
            if kind == "load":
                return Value(memory[address], 8)
            result = dict(memory)
            result[address] = self.expr(expression["value"]).n
            return result
        return super().expr(expression)

    def statements(self, statements):
        for statement in statements:
            if statement["kind"] == "move" and statement["var"]["type"] == "mem":
                self.memory = self.expr(statement["value"])
            else:
                super().statements([statement])


def numeric_observation(encoded, bil, va):
    decoded = domains.decode_memory_mov8(encoded)
    boundaries = (0, 1, 0x7f, 0x80000000, 0xffffff80, 0xffffffff, 0x7fffffff, 0x12345678)
    for seed, boundary in enumerate(boundaries):
        registers = [((bank + 1) << 32) | ((boundary + bank * 17) & 0xffffffff) for bank in range(16)]
        if decoded["base"] is not None:
            bank = decoded["base"]
            registers[bank] = ((bank + 1) << 32) | boundary
        address = domains.memory_mov8_address(decoded, registers, va)
        initial = dict(zip(BANKS, registers))
        initial.update({name: (seed >> (index % 3)) & 1 for index, name in enumerate(FLAGS)})
        expected = dict(initial)
        memory = {address: (seed * 37 + 0xa5) & 255, (address + 1) & MASK: 0x5a, (address - 1) & MASK: 0x3c}
        expected_memory = dict(memory)
        bank, offset = decoded["dataBank"], decoded["dataByte"] * 8
        if decoded["operation"] == "load":
            expected[BANKS[bank]] = (registers[bank] & ~(255 << offset)) | (memory[address] << offset)
        else:
            expected_memory[address] = (registers[bank] >> offset) & 255
        evaluator = MemoryEvaluator({name: Value(value, 64 if name in BANKS else 1)
                                     for name, value in initial.items()}, memory)
        try:
            evaluator.statements(bil)
        except KeyError:
            # A missing oracle byte is a concrete address counterexample, not a
            # fabricated value or an invitation to fill a captured memory hole.
            if evaluator.accesses and evaluator.accesses != [(decoded["operation"], address)]:
                return dict(matched=False, cases=seed + 1, witness=dict(seed=seed, expectedAddress=address,
                    accesses=evaluator.accesses, reason="memory-address-disagreement"))
            raise
        if evaluator.accesses != [(decoded["operation"], address)]:
            return dict(matched=False, cases=seed + 1, witness=dict(seed=seed, expectedAddress=address,
                accesses=evaluator.accesses, reason="memory-address-disagreement"))
        if evaluator.memory != expected_memory or any(evaluator.values[name].n != value for name, value in expected.items()):
            return dict(matched=False, cases=seed + 1, witness=dict(seed=seed, expectedAddress=address,
                accesses=evaluator.accesses, reason="register-memory-or-flags-disagreement"))
    return dict(matched=True, cases=8, witness=None)


def address_register(bank, width):
    if bank is None:
        return "NONE"
    if width == 64:
        return BANKS[bank]
    return ["EAX", "ECX", "EDX", "EBX", "ESP", "EBP", "ESI", "EDI"][bank] if bank < 8 else f"R{bank}D"


def validate_reference_row(line, encoded, va):
    decoded = domains.decode_memory_mov8(encoded)
    base = ("EIP" if decoded["addressBits"] == 32 else "RIP") if decoded["ipRelative"] else address_register(decoded["base"], decoded["addressBits"])
    address = ["r:" + base, "i:" + str(decoded["scale"]), "r:" + address_register(decoded["index"], decoded["addressBits"]),
               "i:" + str(decoded["displacement"]), "r:NONE"]
    data = "r:" + register.register_name((decoded["dataBank"], decoded["dataByte"]))
    load = decoded["operation"] == "load"
    opcode = "MOV8rm" if load else "MOV8mr"
    expected = ["v2", opcode, "6", *([data, *address] if load else [*address, data]),
                "1" if load else "0", "1" if load else "2", "0", "0", *(["-1"] * 6),
                str(va), "ok", str(decoded["consumedLength"]), "ordinary", "-"]
    actual = line.split() if isinstance(line, str) else []
    # LLVM retains redundant SIB encodings using its zero-index pseudo-register.
    # Accept that spelling only when the independently decoded index is absent.
    index_column = 6 if load else 5
    zero_index = "r:EIZ" if decoded["addressBits"] == 32 else "r:RIZ"
    if decoded["index"] is None and len(actual) > index_column and actual[index_column] == zero_index:
        actual[index_column] = "r:NONE"
    register.require(actual == expected, "memory decode/control/address disagreement: " + encoded)
    return opcode


def collect(points, domain_digest, binding_digest, helper, runtime, reference, library):
    """Fresh protocol observations; callers separately bind sources and admission."""
    helper, runtime, reference, library = [Path(path).resolve() for path in (helper, runtime, reference, library)]
    env = {**os.environ, "LD_LIBRARY_PATH": str(runtime / "usr/local/lib") + ":" + str(runtime / "usr/lib/x86_64-linux-gnu"),
           "XDG_STATE_HOME": str(runtime / "state"), "XDG_CACHE_HOME": str(runtime / "cache")}
    rows = []
    for target in register.TARGETS:
        snapshot = domains.digest(dict(domain=domain_digest, bindings=binding_digest, target=target))
        request = f"ARIADNE-BAP-LIFT 1 {target} {snapshot}\n"
        for batch, start in enumerate(range(0, len(points), 256)):
            block = points[start:start + 256]
            request += f"batch {batch} {len(block)}\n" + "".join(f"0x{QUERY_BASE + (start + index) * 32:016x} {point['bytes']}\n" for index, point in enumerate(block))
        lifted = subprocess.run([str(helper), str(runtime / "usr/local/lib/bap")], input=request,
            text=True, capture_output=True, env=env, timeout=300)
        register.require(lifted.returncode == 0, "fresh memory BAP query failed: " + lifted.stderr[-2000:])
        frames = [register.strict_json(line) for line in lifted.stdout.splitlines()]
        responses = register.producer_rows(frames, target, snapshot, len(points))
        request = "".join(f"{QUERY_BASE + index * 32} {point['bytes']}\n" for index, point in enumerate(points))
        decoded = subprocess.run([str(reference), "--protocol=2-checked" + ("-linux" if target == "linux-amd64" else "")],
            input=request, text=True, capture_output=True, env={**os.environ, "LD_LIBRARY_PATH": str(library.parent)}, timeout=120)
        register.require(decoded.returncode == 0, "fresh memory reference query failed: " + decoded.stderr[-2000:])
        lines = decoded.stdout.splitlines()
        ready = "ariadne-llvm-mc 20.1.2 protocol 2" + (" target x86_64-unknown-linux-gnu" if target == "linux-amd64" else "")
        register.require(len(lines) == len(points) + 1 and lines[0] == ready, "memory reference handshake/count")
        for index, (point, response, line) in enumerate(zip(points, responses, lines[1:])):
            va = QUERY_BASE + index * 32
            validate_reference_row(line, point["bytes"], va)
            register.require(response["bytes"] == point["bytes"] and response["status"] == "decoded"
                and response["length"] == len(point["bytes"]) // 2, "memory producer consumed bytes")
            rows.append(dict(target=target, point=point, response=response, reference=line,
                astSha256=domains.digest(response["bil"]), numeric=numeric_observation(point["bytes"], response["bil"], va)))
    return rows


def validate_observations(observations, document, constraints, bindings, pdf, bbox, root=ROOT, require_rust=True):
    points = validate_inputs(document, constraints, bindings, pdf, bbox, root)
    register.fields(observations, {"schema", "domainSha256", "bindingsSha256", "sourcePacksSha256",
        "implementationSources", "sourceEvidence", "producer", "reference", "rows", "rustObserver"}, "memory observations")
    register.require(observations["schema"] == "ariadne.amd64-memory-observations/v1"
        and observations["domainSha256"] == domains.digest(document)
        and observations["bindingsSha256"] == domains.digest(bindings)
        and observations["sourcePacksSha256"] == domains.digest(document["sourcePacks"])
        and observations["implementationSources"] == sources(root), "stale memory observation identity")
    register.require(observations["sourceEvidence"] == {"pdfSha256": domains.sha(pdf), "bboxSha256": domains.sha(bbox)},
                     "memory source evidence identity")
    register.validate_producer(observations["producer"], bindings, root)
    register.validate_reference(observations["reference"], bindings)
    expected = {(target, register.point_key(point)): (index, point) for target in register.TARGETS for index, point in enumerate(points)}
    seen, matches, mismatches, scenarios = set(), 0, 0, 0
    register.require(isinstance(observations["rows"], list), "memory observation rows")
    for row in observations["rows"]:
        register.fields(row, {"target", "point", "response", "reference", "astSha256", "numeric", "disposition"}, "memory observation row")
        key = row["target"], register.point_key(row["point"])
        register.require(key in expected and key not in seen and row["point"] == expected[key][1], "memory observation omission/duplicate/substitution")
        seen.add(key)
        index, point = expected[key]
        va = QUERY_BASE + index * 32
        snapshot = domains.digest(dict(domain=domains.digest(document), bindings=domains.digest(bindings), target=row["target"]))
        response = row["response"]
        register.fields(response, {"schema", "batch", "snapshot", "va", "status", "length", "bytes", "opcode", "properties", "bil"}, "memory producer response")
        register.require(response["schema"] == "ariadne.bap-site/v1" and type(response["batch"]) is int
            and response["batch"] == index // 256 and response["snapshot"] == snapshot
            and response["va"] == f"0x{va:016x}" and response["bytes"] == point["bytes"]
            and response["status"] == "decoded" and type(response["length"]) is int
            and response["length"] == len(point["bytes"]) // 2 and response["bil"], "memory producer query/extent identity")
        opcode = validate_reference_row(row["reference"], point["bytes"], va)
        register.require(response["opcode"] == opcode and row["astSha256"] == domains.digest(response["bil"]), "memory opcode/AST identity")
        register.fields(response["properties"], {"jump", "conditional", "indirect", "call", "return", "control"}, "memory control properties")
        register.require(all(value is False for value in response["properties"].values()), "memory control properties differ")
        disposition = "S" if point["environment"]["addressBits"] == 64 else "U"
        register.require(row["disposition"] == disposition, "memory prefix disposition differs")
        numeric = numeric_observation(point["bytes"], response["bil"], va)
        register.require(domains.digest(row["numeric"]) == domains.digest(numeric), "memory numeric observation differs")
        register.require(disposition != "S" or numeric["matched"], "supported memory address/value counterexample")
        matches += numeric["matched"]
        mismatches += not numeric["matched"]
        scenarios += numeric["cases"]
    register.require(seen == set(expected), "missing memory observations")
    observer = observations["rustObserver"]
    if observer is not None:
        register.fields(observer, {"test", "inputSha256", "stdout", "stderr"}, "memory Rust observer")
        register.require(observer["test"] == RUST_TEST and observer["inputSha256"] == domains.digest(register.rust_input(observations))
            and isinstance(observer["stdout"], str) and isinstance(observer["stderr"], str)
            and f"test {RUST_TEST} ... ok" in observer["stdout"]
            and "test result: ok. 1 passed; 0 failed;" in observer["stdout"], "memory Rust observer identity/result")
    register.require(not require_rust or observer is not None, "missing fresh memory Rust observer")
    return dict(schema="ariadne.amd64-memory-binding-assessment/v1", finiteEncodingSelectionComplete=True,
        domainPoints=len(points), supportedPoints=2880, unsupportedPoints=2880, unresolvedPoints=0,
        observations=len(seen), numericMatches=matches, numericMismatches=mismatches, numericScenarios=scenarios,
        profileBindingsValidated=observer is not None, totalDisposition=True, implementationComplete=False,
        nativeConsumerValidated=False, wholeAddressGrammarComplete=False, candidateFullDomainBindings=0,
        sourceComplete=False, vendorFullDenominator=False, fullAmd64Coverage=False, profile=PROFILE,
        consumer="plain-dependencies", unsupportedReason="All address32 MOV8 points retain the existing production prefix-policy refusal; numeric witnesses do not override admission.",
        ipPremise="RIP-relative memory uses exact queried VA plus consumed length; RIP is outside the provenance catalogue.")


def build(document, constraints, bindings, pdf, bbox, helper, runtime, reference, library, root=ROOT, *, work_dir):
    points = validate_inputs(document, constraints, bindings, pdf, bbox, root)
    helper, runtime, reference, library = [Path(path).resolve() for path in (helper, runtime, reference, library)]
    producer = dict(helperPath=str(helper), helperSha256=domains.sha(helper), runtimeRoot=str(runtime),
        runtimeLockPath="native/bap/toolchain.lock.json", runtimeLockSha256=domains.sha(Path(root) / "native/bap/toolchain.lock.json"))
    decode = dict(helperPath=str(reference), helperSha256=domains.sha(reference), libraryPath=str(library),
                  librarySha256=domains.sha(library), version=bindings["referencePin"]["version"])
    register.validate_producer(producer, bindings, root)
    register.validate_reference(decode, bindings)
    rows = collect(points, domains.digest(document), domains.digest(bindings), helper, runtime, reference, library)
    for row in rows:
        row["disposition"] = "S" if row["point"]["environment"]["addressBits"] == 64 else "U"
    observations = dict(schema="ariadne.amd64-memory-observations/v1", domainSha256=domains.digest(document),
        bindingsSha256=domains.digest(bindings), sourcePacksSha256=domains.digest(document["sourcePacks"]),
        implementationSources=sources(root), sourceEvidence={"pdfSha256": domains.sha(pdf), "bboxSha256": domains.sha(bbox)},
        producer=producer, reference=decode, rows=rows, rustObserver=None)
    validate_observations(observations, document, constraints, bindings, pdf, bbox, root, require_rust=False)
    Path(work_dir).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mov8-memory-rust-", dir=work_dir) as directory:
        path = Path(directory).resolve() / "observations.json"
        path.write_text(json.dumps(register.rust_input(observations)))
        result = subprocess.run(["cargo", "test", "--offline", "--locked", "--lib", RUST_TEST, "--", "--ignored", "--exact"],
            cwd=root, env={**os.environ, "ARIADNE_MOV8_MEMORY_OBSERVATIONS": str(path)}, text=True, capture_output=True, timeout=600)
        register.require(result.returncode == 0, "fresh memory Rust observer failed: " + result.stdout[-2500:] + result.stderr[-2500:])
        observations["rustObserver"] = dict(test=RUST_TEST, inputSha256=domains.digest(register.rust_input(observations)),
                                            stdout=result.stdout, stderr=result.stderr)
    validate_observations(observations, document, constraints, bindings, pdf, bbox, root)
    return observations
