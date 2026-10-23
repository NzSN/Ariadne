#!/usr/bin/env python3
"""Qualify exact source-built REP forms against independent AMD element rules.

This is a finite normal-completion check, not a full ISA or hardware-fault
model. In particular, AMD zero-count preservation is not an Intel contract.
Only LoopEvaluator is shared with the older oracle; all expected state and
test-state construction below are independent of the producer and projector.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import subprocess

from check_bap_admission_oracle import Value
from check_bap_bit_count_oracle import BANKS, FLAGS
from check_bap_repeated_string_oracle import LoopEvaluator
from i5a_native_contract import strict_json

ROOT = Path(__file__).resolve().parents[1]
MASK32, MASK64 = (1 << 32) - 1, (1 << 64) - 1
HIGH_COUNT = 0x8765432100000000
ACCUMULATORS = (0xA51234879BCD0123, 0x7FFFFFFFFFFFFF80, 0x8000800080008080)
LAYOUTS = ("disjoint", "overlap-forward", "overlap-backward", "same-address",
           "source-wrap", "destination-wrap", "both-wrap")
PATTERNS = ("equal", "first-diff", "late-diff", "first-equal", "late-equal")
SOURCES = {
    "amd-24592-r3.25": {
        "sha256": "aed9236b718ae86cdb49f7d628f4ebb1a4bdce1a012df6cf6aad6735776c8a38",
        "url": "https://docs.amd.com/api/khub/documents/OdDzCKsU4uf~KbI1htdPvA/content",
        "sections": ["2.2.3.1", "3.1.2.3"],
        "rules": "Effective address truncation before zero extension; 32-bit register results zero extend, partial 8/16-bit writes preserve upper lanes.",
    },
    "amd-24594-r3.38": {
        "sha256": "e18bd39ad0ca19d2eb9b9ea25c2635144c5ab368e5d6fbdc7a08345515ea1aee",
        "url": "https://docs.amd.com/api/khub/documents/BqEoC2FadIAgbrUdEzDJIg/content",
        "sections": ["1.2.3", "1.2.6", "CMPS", "LODS", "MOVS", "SCAS", "STOS"],
        "pdfPages": [51, 52, 54, 55, 56, 207, 208, 267, 268, 301, 302, 376, 377, 396, 397],
        "rules": "Address size selects count and implicit index widths; repeat comparison termination follows each element; DF selects the signed element stride.",
    },
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_cases():
    cases = {}
    for family, repeat, byte, wide, condition in (
            ("movs", "f3", 0xA4, 0xA5, "count"),
            ("stos", "f3", 0xAA, 0xAB, "count"),
            ("lods", "f3", 0xAC, 0xAD, "count"),
            ("cmps", "f3", 0xA6, 0xA7, "equal"),
            ("cmps", "f2", 0xA6, 0xA7, "not-equal"),
            ("scas", "f3", 0xAE, 0xAF, "equal"),
            ("scas", "f2", 0xAE, 0xAF, "not-equal")):
        for bits in (8, 16, 32, 64):
            code = ("66" if bits == 16 else "") + repeat
            code += "48" if bits == 64 else ""
            code += f"{byte if bits == 8 else wide:02x}"
            for address_bits in ((64, 32) if family == "lods" else (32,)):
                exact = ("67" if address_bits == 32 else "") + code
                cases[exact] = dict(bytes=exact, family=family, elementBits=bits,
                                    addressBits=address_bits, repeatCondition=condition)
    require(len(cases) == 32, "oracle exact-form scope")
    return cases


CASES = make_cases()
CODES = set(CASES)


def parameters(case):
    counts = (0, 1, 2, 4)
    if case["addressBits"] == 32:
        counts += (HIGH_COUNT, HIGH_COUNT | 1, HIGH_COUNT | 3)
    return itertools.product(counts, (0, 1), (0, 1), LAYOUTS, PATTERNS, ACCUMULATORS)


def read_element(memory, address, size):
    # Truncate only the element's starting effective address. Its byte lanes
    # remain contiguous linear-memory bytes, even across the 4 GiB boundary.
    return int.from_bytes(bytes(memory[(address + i) & MASK64] for i in range(size)), "little")


def write_element(memory, address, size, value):
    for i, byte in enumerate(value.to_bytes(size, "little")):
        memory[(address + i) & MASK64] = byte


def difference_flags(left, right, bits):
    modulus, sign = 1 << bits, 1 << (bits - 1)
    result = (left - right) % modulus
    signed = lambda value: value - modulus if value >= sign else value
    mathematical = signed(left) - signed(right)
    return dict(CF=int(left < right), PF=int(sum((result >> i) & 1 for i in range(8)) % 2 == 0),
                AF=int((left & 15) < (right & 15)), ZF=int(result == 0),
                SF=int(result >= sign), OF=int(not -sign <= mathematical < sign))


def expected(case, registers, memory):
    result = {name: value.n for name, value in registers.items()}
    memory = memory.copy()
    family, bits, address_bits = case["family"], case["elementBits"], case["addressBits"]
    address_mask, element_mask, size = (1 << address_bits) - 1, (1 << bits) - 1, bits // 8
    remaining = result["RCX"] & address_mask
    require(remaining <= 8, "independent oracle finite-count bound")
    step = -size if result["DF"] else size
    # No operation, decrement or index write occurs at zero count under this
    # AMD model. Fresh Ryzen 7950X observations corroborate this corner case;
    # Intel Core 5 220H observations differ and are outside the premise.
    while remaining:
        source, destination = result["RSI"] & address_mask, result["RDI"] & address_mask
        if family in {"movs", "lods", "cmps"}:
            source_value = read_element(memory, source, size)
        if family == "movs":
            write_element(memory, destination, size, source_value)
        elif family == "stos":
            write_element(memory, destination, size, result["RAX"] & element_mask)
        elif family == "lods":
            result["RAX"] = ((result["RAX"] & (MASK64 ^ element_mask)) | source_value
                             if bits < 32 else source_value)
        elif family == "cmps":
            result.update(difference_flags(source_value, read_element(memory, destination, size), bits))
        elif family == "scas":
            result.update(difference_flags(result["RAX"] & element_mask,
                                           read_element(memory, destination, size), bits))
        else:
            raise ValueError("unknown oracle string family")
        if family in {"movs", "lods", "cmps"}:
            result["RSI"] = (source + step) & address_mask
        if family in {"movs", "stos", "cmps", "scas"}:
            result["RDI"] = (destination + step) & address_mask
        remaining -= 1
        result["RCX"] = remaining
        if case["repeatCondition"] == "equal" and result["ZF"] == 0:
            break
        if case["repeatCondition"] == "not-equal" and result["ZF"] == 1:
            break
    return result, memory


def scenario(case, count, direction, flag_seed, layout, pattern, accumulator):
    state = {name: Value(0xA51234879BCD0123 ^ (index << 20), 64)
             for index, name in enumerate(BANKS)}
    state.update({name: Value(flag_seed, 1) for name in FLAGS})
    state.update(RCX=Value(count, 64), RAX=Value(accumulator, 64), DF=Value(direction, 1))
    address_mask, size = (1 << case["addressBits"]) - 1, case["elementBits"] // 8
    boundary = 0 if direction else address_mask - size // 2
    source, destination = {
        "disjoint": (0x7000, 0x8000), "overlap-forward": (0x7000, 0x7001),
        "overlap-backward": (0x7001, 0x7000), "same-address": (0x7000, 0x7000),
        "source-wrap": (boundary, 0x8000), "destination-wrap": (0x7000, boundary),
        "both-wrap": (boundary, boundary),
    }[layout]
    high_source, high_destination = ((0x13579BDF00000000, 0x2468ACE000000000)
                                      if case["addressBits"] == 32 else (0, 0))
    state["RSI"], state["RDI"] = Value(source | high_source, 64), Value(destination | high_destination, 64)
    count &= address_mask
    require(count <= 8, "scenario finite-count bound")
    step = -size if direction else size
    addresses = {0x123456, 0x123457, 0x8000000000001234, 0xFFFFFFFFFFFF1111}
    for base in (source, destination):
        for index in range(max(count, 1)):
            start = (base + step * index) & address_mask
            addresses.update((start + lane) & MASK64 for lane in range(size))
    memory = {address: ((address * 37) ^ (address >> 32) ^ 0x80) & 255 for address in addresses}
    if layout in {"disjoint", "source-wrap", "destination-wrap"}:
        mask, sign = (1 << case["elementBits"]) - 1, 1 << (case["elementBits"] - 1)
        for index in range(count):
            value = (accumulator if case["family"] == "scas" else
                     (sign, sign - 1, 0, mask)[index % 4]) & mask
            equal = (pattern == "equal" or (pattern == "first-diff" and index != 0)
                     or (pattern == "late-diff" and index != 2)
                     or (pattern == "first-equal" and index == 0)
                     or (pattern == "late-equal" and index == 2))
            write_element(memory, (source + step * index) & address_mask, size, value)
            write_element(memory, (destination + step * index) & address_mask, size,
                          value if equal else value ^ mask)
    return state, memory


def verify_capi_types(bil):
    """Reject ill-typed cast encodings that can be numerically indistinguishable."""
    nodes = 0

    def expr(value, depth=0):
        nonlocal nodes
        nodes += 1
        require(nodes <= 8192 and depth <= 64, "typed oracle AST budget")
        kind = value["kind"]
        child = lambda x: expr(x, depth + 1)
        if kind == "var":
            return None if value["var"]["type"] == "mem" else value["var"]["width"]
        if kind == "int":
            return int(value["value"].split(":")[1].rstrip("us"))
        if kind == "cast":
            source, width, op = child(value["arg"]), value["width"], value["op"]
            require(source is not None and width > 0 and op in range(4), "C API cast fields")
            require(width <= source if op < 2 else width >= source, "C API cast direction")
            return width
        if kind == "extract":
            source = child(value["arg"])
            require(source is not None and 0 <= value["lo"] <= value["hi"] < source, "extract bounds")
            return value["hi"] - value["lo"] + 1
        if kind == "concat":
            left, right = child(value["lhs"]), child(value["rhs"])
            require(left is not None and right is not None, "concat types")
            return left + right
        if kind == "binop":
            left, right = child(value["lhs"]), child(value["rhs"])
            require(left is not None and left == right and value["op"] in range(19), "binary types")
            return 1 if value["op"] <= 5 else left
        if kind == "unop":
            require(value["op"] in (0, 1), "unary operator")
            width = child(value["arg"])
            require(width is not None, "unary type")
            return width
        if kind == "ite":
            condition, yes, no = child(value["condition"]), child(value["yes"]), child(value["no"])
            require(condition == 1 and yes == no, "conditional types")
            return yes
        if kind in {"load", "store"}:
            require(child(value["mem"]) is None and child(value["addr"]) == 64, "memory operand types")
            if kind == "load":
                require(value["width"] in (8, 16, 32, 64), "element width")
                return value["width"]
            require(child(value["value"]) in (8, 16, 32, 64), "store width")
            return None
        if kind == "let":
            require(child(value["value"]) == value["var"]["width"], "let type")
            return child(value["body"])
        raise ValueError("unsupported typed oracle expression " + kind)

    def statements(items, depth=0):
        for statement in items:
            kind = statement["kind"]
            if kind == "move":
                width = None if statement["var"]["type"] == "mem" else statement["var"]["width"]
                require(expr(statement["value"]) == width, "move type")
            elif kind == "while":
                require(depth == 0 and expr(statement["condition"]) == 1, "loop type or nesting")
                statements(statement["body"], depth + 1)
            elif kind == "if":
                require(expr(statement["condition"]) == 1, "if condition type")
                statements(statement["yes"], depth + 1)
                statements(statement["no"], depth + 1)
            else:
                raise ValueError("unsupported typed oracle statement " + kind)
    require(isinstance(bil, list) and bil, "empty oracle BIL")
    statements(bil)


def check_bil(code, bil, values):
    case = CASES[code]
    state, memory = scenario(case, *values)
    wanted, wanted_memory = expected(case, state, memory)
    evaluator = LoopEvaluator(state, memory.copy())
    try:
        evaluator.statements(bil)
        for name, value in wanted.items():
            require(evaluator.values[name].n == value,
                    f"{name} got {evaluator.values[name].n:#x}, expected {value:#x}")
        require(evaluator.memory == wanted_memory, "complete supplied memory differs")
    except (KeyError, ValueError) as error:
        raise ValueError(f"{code} {values}: {error}") from error


def check_source_binding(binding):
    expected_names = {"rep_address_build.py", "rep_address_lift.ml", "rep_address_probe.ml",
                      "rep_address.patch", "lods.patch", "build.py"}
    require(set(binding["sources"]) == expected_names, "producer source inventory differs")
    sources = {}
    for name, digest in binding["sources"].items():
        relative = "native/bap/source-coverage/" + name
        require(sha(ROOT / relative) == digest, "producer source differs: " + relative)
        sources[relative] = digest
    relative = "native/bap-core/sdk.lock.json"
    require(sha(ROOT / relative) == binding["sdk_lock_sha256"], "producer SDK lock differs")
    sources[relative] = binding["sdk_lock_sha256"]
    return sources


def run(runtime, manifest_sha256, executable_sha256, lifts_output=None):
    runtime = Path(runtime).resolve()
    manifest_path, executable = runtime / "manifest.json", runtime / "rep-address-lift"
    require(sha(manifest_path) == manifest_sha256, "explicit REP address manifest pin differs")
    require(sha(executable) == executable_sha256, "explicit REP address executable pin differs")
    manifest = strict_json(manifest_path.read_text())
    require(manifest["schema"] == "ariadne.bap-source-rep-address-build/v1"
            and manifest["profiles"] == ["bap-bit-provenance-v15"]
            and manifest["runtime_role"] == "rep-address-source"
            and manifest["vendor"] == "AMD"
            and manifest["semantic_premises"] == ["amd-long-mode-memory-rep", "address32-zero-count-preserves-upper-lanes"]
            and manifest["executable"] == "rep-address-lift"
            and manifest["executable_sha256"] == executable_sha256
            and manifest["cases"] == sorted(CODES)
            and manifest["max_response_bytes"] == 65536, "REP address manifest contract")
    encoded = json.dumps(manifest["binding"], sort_keys=True, separators=(",", ":")).encode()
    require(hashlib.sha256(encoded).hexdigest() == manifest["build_id"], "REP address build binding")
    producer_sources = check_source_binding(manifest["binding"])
    rows, lifts = [], []
    for target, code in itertools.product(("windows-amd64", "linux-amd64"), CASES):
        snapshot, va = "e" * 64, "0xffff800000401000"
        process = subprocess.run([str(executable), target, snapshot, va, code],
                                 capture_output=True, text=True, timeout=60)
        require(process.returncode == 0, "fresh REP address producer failed: " + process.stderr)
        require(len(process.stdout.encode()) <= 65536, "REP address response budget")
        row = strict_json(process.stdout)
        require(set(row) == {"schema", "build_id", "target", "snapshot", "va", "bytes", "length", "bil"}
                and row["schema"] == "ariadne.bap-source-rep-address/v1"
                and row["build_id"] == manifest["build_id"] and row["target"] == target
                and row["snapshot"] == snapshot and row["va"] == va and row["bytes"] == code
                and type(row["length"]) is int and row["length"] == len(code) // 2,
                "fresh REP address response binding")
        verify_capi_types(row["bil"])
        comparisons = 0
        for values in parameters(CASES[code]):
            check_bil(code, row["bil"], values)
            comparisons += 1
        rows.append(dict(target=target, bytes=code, comparisons=comparisons))
        lifts.append(row)
    refused = 0
    for code in ("f3a4", "67a4", "6767f3a4", "f367a4", "f067f3a4", "6467f3a4", "6740f3a4",
                 "67f3f3a4", "67f2a4", "67f3a490", "67f36c", "67f36e", "67F3A4", "67", ""):
        process = subprocess.run([str(executable), "windows-amd64", "e" * 64, "0xffff800000401000", code],
                                 capture_output=True, text=True, timeout=60)
        require(process.returncode != 0 and not process.stdout, "out-of-scope REP address bytes accepted")
        refused += 1
    require(sha(manifest_path) == manifest_sha256 and sha(executable) == executable_sha256,
            "runtime identity changed during oracle")
    require(check_source_binding(manifest["binding"]) == producer_sources, "producer source changed during oracle")
    if lifts_output is not None:
        lifts_output.parent.mkdir(parents=True, exist_ok=True)
        lifts_output.write_text(json.dumps(lifts, indent=2) + "\n")
    source_paths = [Path(__file__), ROOT / "tests/bap/test_rep_address_oracle.py",
                    ROOT / "tools/check_bap_repeated_string_oracle.py",
                    ROOT / "tools/check_bap_bit_count_oracle.py", ROOT / "tools/check_bap_admission_oracle.py"]
    return dict(schema="ariadne.bap-rep-address-oracle/v1", passed=True, forms=len(CASES),
                comparisons=sum(row["comparisons"] for row in rows), rows=rows,
                refusedRuntimeNeighbors=refused, runtimeManifestSha256=manifest_sha256,
                runtimeExecutableSha256=executable_sha256, producerBinding=manifest["binding"],
                producerSources=producer_sources,
                typedBilSha256=hashlib.sha256(json.dumps(lifts, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
                oracleSources={str(path.relative_to(ROOT)): sha(path) for path in source_paths},
                architecturalSources=SOURCES, vendorPremise="AMD normal-completion semantics; not Intel zero-count upper-lane semantics",
                scope="32 exact source-bundle forms on both target labels: four default LODS and 28 address32 memory REP forms. Finite low counts, high count/index bits, AMD zero-count preservation, modulo index updates, contiguous element lanes, both directions and initial ZF values, early termination, overlap, accumulator lanes, subtraction flags, every supplied GPR/flag and all memory. Abstract 64-bit lane wrap is not hardware fault qualification. No segment override, I/O, exception, partial-fault, restart or overall ISA qualification.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--executable-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--lifts-output", type=Path)
    args = parser.parse_args()
    from run_output import run_output
    output = run_output(args.output)
    lifts = run_output(args.lifts_output) if args.lifts_output else None
    report = run(args.runtime, args.manifest_sha256, args.executable_sha256, lifts)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": True, "forms": report["forms"], "comparisons": report["comparisons"]}))


if __name__ == "__main__":
    main()
