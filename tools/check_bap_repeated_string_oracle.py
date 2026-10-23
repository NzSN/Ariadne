#!/usr/bin/env python3
"""Check actual BAP REP BIL against independent sequential element operations."""
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess

from check_bap_admission_oracle import Value, fresh_lifts
from check_bap_bit_count_oracle import BANKS, FLAGS, IdentityEvaluator
from amd64_rep_recipes import RECIPES, load_recipes
from i5a_native_contract import strict_json

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "tests/bap/fixtures/repeated-string/contract.json"
MASK = (1 << 64) - 1


class LoopEvaluator(IdentityEvaluator):
    def __init__(self, registers, memory, limit=4096):
        super().__init__(registers, memory)
        self.remaining = limit

    def expr(self, expression):
        if expression["kind"] == "store":
            memory = self.expr(expression["mem"]).copy()
            address = self.expr(expression["addr"]).n
            value = self.expr(expression["value"])
            if address is None or value.n is None or value.w % 8:
                raise ValueError("nonconcrete byte store")
            for index in range(value.w // 8):
                memory[(address + index) & MASK] = (value.n >> (index * 8)) & 255
            return memory
        return super().expr(expression)

    def statements(self, statements):
        for statement in statements:
            self.remaining -= 1
            if self.remaining < 0:
                raise ValueError("concrete REP oracle execution bound")
            if statement["kind"] == "while":
                while True:
                    condition = self.expr(statement["condition"]).n
                    if condition is None:
                        raise ValueError("nonconcrete REP condition")
                    if condition == 0:
                        break
                    self.remaining -= 1
                    if self.remaining < 0:
                        raise ValueError("concrete REP oracle execution bound")
                    self.statements(statement["body"])
            elif statement["kind"] == "move" and statement["var"]["type"] == "mem":
                if statement["var"]["virtual"] or statement["var"]["name"] != "mem":
                    raise ValueError("unexpected memory variable")
                self.memory = self.expr(statement["value"])
            else:
                super().statements([statement])


def subtract_flags(left, right, width=8):
    result = (left - right) & ((1 << width) - 1)
    sign = 1 << (width - 1)
    return {"CF": int(left < right), "PF": int((result & 255).bit_count() % 2 == 0),
            "AF": int(bool((left ^ right ^ result) & 16)), "ZF": int(result == 0),
            "SF": int(bool(result & sign)), "OF": int(bool((left ^ right) & (left ^ result) & sign))}


def expected(operation, registers, memory):
    result = {key: value.n for key, value in registers.items()}
    memory = memory.copy()
    step = -1 if result["DF"] else 1
    while result["RCX"]:
        source, destination = result["RSI"], result["RDI"]
        if operation == "movsb":
            memory[destination] = memory[source]
        elif operation == "stosb":
            memory[destination] = result["RAX"] & 255
        elif operation == "cmpsb":
            result.update(subtract_flags(memory[source], memory[destination]))
        else:
            raise ValueError("unknown byte-string operation")
        result["RDI"] = (destination + step) & MASK
        if operation != "stosb":
            result["RSI"] = (source + step) & MASK
        result["RCX"] -= 1
        if operation == "cmpsb" and not result["ZF"]:
            break
    return result, memory


def scenario(count, direction, flag_seed, layout, pattern):
    registers = {name: Value(0xA51234879BCD0123 ^ (index << 16), 64)
                 for index, name in enumerate(BANKS)}
    registers.update({flag: Value(flag_seed, 1) for flag in FLAGS})
    registers["DF"] = Value(direction, 1)
    registers["RCX"] = Value(count, 64)
    source, destination = {
        "disjoint": (0x7000, 0x8000), "overlap": (0x7000, 0x7001),
        "source-wrap": (0 if direction else MASK, 0x8000),
        "destination-wrap": (0x7000, 0 if direction else MASK),
    }[layout]
    registers["RSI"], registers["RDI"] = Value(source, 64), Value(destination, 64)
    step = -1 if direction else 1
    addresses = {(base + step * i) & MASK for base in (source, destination) for i in range(count)}
    memory = {address: ((address * 37) ^ 0x80) & 255 for address in addresses}
    if layout != "overlap":
        for index in range(count):
            source_address = (source + step * index) & MASK
            destination_address = (destination + step * index) & MASK
            byte = [0x80, 0x7f, 0, 0xff, 0x10, 0x11, 1, 0xfe][index % 8]
            memory[source_address] = byte
            differs = (pattern == "first-diff" and index == 0) or (pattern == "late-diff" and index == 2)
            memory[destination_address] = (byte ^ 0xff) if differs else byte
    return registers, memory


def check_case(case, bil, registers, memory):
    want_registers, want_memory = expected(case["operation"], registers, memory)
    actual = LoopEvaluator(registers, memory.copy())
    actual.statements(bil)
    for name, want in want_registers.items():
        if actual.values[name].n != want:
            raise ValueError(f'{case["name"]}: {name} got {actual.values[name].n}, expected {want}')
    if actual.memory != want_memory:
        raise ValueError(case["name"] + ": complete memory comparison differs")


def run():
    cases = json.loads(CONTRACT.read_text())["cases"]
    native, bil_sha, helper_sha = fresh_lifts(cases, CONTRACT)
    rows = []
    for case, lift in zip(cases, native):
        comparisons = 0
        for parameters in itertools.product((0, 1, 2, 4, 8), (0, 1), (0, 1),
                                            ("disjoint", "overlap", "source-wrap", "destination-wrap"),
                                            ("equal", "first-diff", "late-diff")):
            registers, memory = scenario(*parameters)
            try:
                check_case(case, lift["bil"], registers, memory)
            except (ValueError, KeyError) as error:
                raise ValueError(f"{parameters}: {error}") from error
            comparisons += 1
        rows.append({"case": case["name"], "comparisons": comparisons})
    sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return dict(schema="ariadne.bap-repeated-string-oracle/v1", passed=True,
                comparisons=sum(row["comparisons"] for row in rows), rows=rows,
                typedBilSha256=bil_sha, helperSha256=helper_sha, contractSha256=sha(CONTRACT),
                oracleSourceSha256=sha(__file__),
                evaluatorSources={str(path.relative_to(ROOT)): sha(path) for path in
                                  (ROOT / "tools/check_bap_admission_oracle.py", ROOT / "tools/check_bap_bit_count_oracle.py")},
                scope="Three exact long-mode byte-string forms; concrete BIL results for zero and finite counts, both directions, early mismatch, overlapping buffers and 64-bit pointer arithmetic wrap. No hardware exception/partial-fault or full REP qualification.")


def read_element(memory, address, size):
    return sum(memory[(address + lane) & MASK] << (lane * 8) for lane in range(size))


def write_element(memory, address, size, value):
    for lane in range(size):
        memory[(address + lane) & MASK] = (value >> (lane * 8)) & 255


def expected_recipe(case, registers, memory):
    """Sequential architectural equations, independent of producer BIL."""
    result = {key: value.n for key, value in registers.items()}
    memory = memory.copy()
    family, width = case["family"], case["elementBits"]
    size, mask = width // 8, (1 << width) - 1
    step = -size if result["DF"] else size
    while result["RCX"]:
        source, destination = result["RSI"], result["RDI"]
        # A whole source element is read before any byte of an overlapping
        # destination is written. This also covers elements crossing 2**64.
        if family in {"movs", "lods", "cmps"}:
            source_value = read_element(memory, source, size)
        if family == "movs":
            write_element(memory, destination, size, source_value)
        elif family == "stos":
            write_element(memory, destination, size, result["RAX"] & mask)
        elif family == "lods":
            result["RAX"] = ((result["RAX"] & ~mask) | source_value
                             if width < 32 else source_value)
        elif family == "cmps":
            result.update(subtract_flags(source_value, read_element(memory, destination, size), width))
        elif family == "scas":
            result.update(subtract_flags(result["RAX"] & mask, read_element(memory, destination, size), width))
        else:
            raise ValueError("unknown memory-string family")
        if family in {"movs", "lods", "cmps"}:
            result["RSI"] = (source + step) & MASK
        if family in {"movs", "stos", "cmps", "scas"}:
            result["RDI"] = (destination + step) & MASK
        result["RCX"] -= 1
        if case["repeatCondition"] == "equal" and result["ZF"] == 0:
            break
        if case["repeatCondition"] == "not-equal" and result["ZF"] == 1:
            break
    return result, memory


def scenario_recipe(case, count, direction, flag_seed, layout, pattern, accumulator):
    registers = {name: Value(0xA51234879BCD0123 ^ (index << 16), 64)
                 for index, name in enumerate(BANKS)}
    registers.update({flag: Value(flag_seed, 1) for flag in FLAGS})
    registers.update(DF=Value(direction, 1), RCX=Value(count, 64), RAX=Value(accumulator, 64))
    size = case["elementBits"] // 8
    source, destination = {
        "disjoint": (0x7000, 0x8000),
        "overlap-forward": (0x7000, 0x7001),
        "overlap-backward": (0x7001, 0x7000),
        "same-address": (0x7000, 0x7000),
        "source-wrap": (0 if direction else MASK - size // 2, 0x8000),
        "destination-wrap": (0x7000, 0 if direction else MASK - size // 2),
    }[layout]
    registers["RSI"], registers["RDI"] = Value(source, 64), Value(destination, 64)
    step = -size if direction else size
    addresses = {(base + step * index + lane) & MASK for base in (source, destination)
                 for index in range(max(count, 1)) for lane in range(size)}
    addresses.update({0x123456, 0x123457})  # unchanged unrelated memory
    memory = {address: ((address * 37) ^ 0x80) & 255 for address in addresses}
    if layout not in {"overlap-forward", "overlap-backward", "same-address"}:
        mask = (1 << case["elementBits"]) - 1
        for index in range(count):
            source_address = (source + step * index) & MASK
            destination_address = (destination + step * index) & MASK
            sign = 1 << (case["elementBits"] - 1)
            value = (accumulator if case["family"] == "scas" else
                     [sign, sign - 1, 0, mask, 0x10, 0x11, 1, 0xfe][index % 8]) & mask
            same = (pattern == "equal" or (pattern == "first-diff" and index != 0)
                    or (pattern == "late-diff" and index != 2)
                    or (pattern == "first-equal" and index == 0)
                    or (pattern == "late-equal" and index == 2))
            write_element(memory, source_address, size, value)
            write_element(memory, destination_address, size, value if same else value ^ mask)
    return registers, memory


def fresh_recipe_assessment(cases, contract_path):
    """Retain every actual lift, including the explicitly unsupported empties."""
    helper = Path(os.environ.get("ARIADNE_BAP_HELPER", ROOT / "target/ariadne-bap-lift"))
    runtime = Path(os.environ.get("BAP_RUNTIME_ROOT", ROOT / "tmp/bap-setup/stable"))
    snapshot = hashlib.sha256(Path(contract_path).read_bytes()).hexdigest()
    request = f"ARIADNE-BAP-LIFT 1 windows-amd64 {snapshot}\nbatch 0 {len(cases)}\n"
    request += "".join(f'0x{0x401000 + index * 32:016x} {case["bytes"]}\n'
                       for index, case in enumerate(cases))
    env = {**os.environ, "LD_LIBRARY_PATH": str(runtime / "usr/local/lib") + ":" + str(runtime / "usr/lib/x86_64-linux-gnu"),
           "XDG_STATE_HOME": str(runtime / "state"), "XDG_CACHE_HOME": str(runtime / "cache")}
    process = subprocess.run([str(helper), str(runtime / "usr/local/lib/bap")], input=request,
                             text=True, capture_output=True, env=env, timeout=300)
    if process.returncode:
        raise ValueError("fresh recipe BAP lift failed: " + process.stderr)
    responses = [strict_json(line) for line in process.stdout.splitlines()]
    if len(responses) != len(cases) + 2:
        raise ValueError("fresh recipe helper frame count differs")
    ready = responses[0]
    if (ready.get("schema") != "ariadne.bap-ready/v1" or ready.get("target") != "windows-amd64"
            or ready.get("snapshot") != snapshot or ready.get("version") != "2.5.0-alpha"
            or ready.get("lifter") != "legacy"):
        raise ValueError("fresh recipe helper identity differs")
    for index, (case, lift) in enumerate(zip(cases, responses[1:-1])):
        if (lift.get("schema") != "ariadne.bap-site/v1" or lift.get("snapshot") != snapshot
                or type(lift.get("batch")) is not int or lift["batch"] != 0
                or lift.get("va") != f"0x{0x401000 + index * 32:016x}"
                or lift.get("status") != "decoded" or lift.get("bytes") != case["bytes"]
                or type(lift.get("length")) is not int or lift["length"] != len(case["bytes"]) // 2
                or lift.get("opcode") != case["bapOpcode"] or not isinstance(lift.get("bil"), list)):
            raise ValueError("fresh recipe decoded facts differ: " + case["name"])
        if (case["profile"] is None) != (not lift["bil"]):
            raise ValueError("fresh recipe producer lift availability changed: " + case["name"])
    if (responses[-1] != {"schema": "ariadne.bap-batch/v1", "batch": 0, "count": len(cases)}
            or type(responses[-1].get("batch")) is not int
            or type(responses[-1].get("count")) is not int):
        raise ValueError("fresh recipe helper completion differs")
    return responses[1:-1]


def run_recipes(recipes_path=RECIPES, lifts_output=None):
    cases = load_recipes(recipes_path)["cases"]
    all_lifts = fresh_recipe_assessment(cases, recipes_path)
    if lifts_output is not None:
        lifts_output.parent.mkdir(parents=True, exist_ok=True)
        lifts_output.write_text(json.dumps(all_lifts, indent=2) + "\n")
    supported = [case for case in cases if case["profile"] is not None]
    native, bil_sha, helper_sha = fresh_lifts(supported, recipes_path)
    rows = []
    for case, lift in zip(supported, native):
        if lift["opcode"] != case["bapOpcode"]:
            raise ValueError("fresh selected opcode differs")
        comparisons = 0
        for parameters in itertools.product((0, 1, 2, 4, 8), (0, 1), (0, 1),
                                            ("disjoint", "overlap-forward", "overlap-backward", "same-address", "source-wrap", "destination-wrap"),
                                            ("equal", "first-diff", "late-diff", "first-equal", "late-equal"),
                                            (0xA51234879BCD0123, 0x7FFFFFFFFFFFFF80, 0x8000800080008080)):
            registers, memory = scenario_recipe(case, *parameters)
            want_registers, want_memory = expected_recipe(case, registers, memory)
            evaluator = LoopEvaluator(registers, memory.copy())
            try:
                evaluator.statements(lift["bil"])
                for name, want in want_registers.items():
                    if evaluator.values[name].n != want:
                        raise ValueError(f"{name} got {evaluator.values[name].n}, expected {want}")
                if evaluator.memory != want_memory:
                    raise ValueError("complete memory comparison differs")
            except (ValueError, KeyError) as error:
                raise ValueError(f'{case["name"]} {parameters}: {error}') from error
            comparisons += 1
        rows.append({"case": case["name"], "bytes": case["bytes"], "opcode": lift["opcode"],
                     "comparisons": comparisons})
    sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return dict(schema="ariadne.bap-repeated-string-oracle/v2", passed=True,
                selectedTuples=len(cases), nonemptyLiftForms=len(supported),
                unsupported=[{"case": case["name"], "reason": case["unsupportedReason"]}
                             for case in cases if case["profile"] is None],
                comparisons=sum(row["comparisons"] for row in rows), rows=rows,
                typedBilSha256=bil_sha, helperSha256=helper_sha, contractSha256=sha(recipes_path),
                oracleSourceSha256=sha(__file__),
                evaluatorSources={str(path.relative_to(ROOT)): sha(path) for path in
                                  (ROOT / "tools/check_bap_admission_oracle.py", ROOT / "tools/check_bap_bit_count_oracle.py",
                                   ROOT / "tools/amd64_rep_recipes.py")},
                scope="Selected default-address memory REP recipes; finite normal-completion numeric, all GPR/flags and complete supplied memory checks. Four LODS forms have empty producer BIL and remain refused. No I/O, address override, fault, restart or overall ISA qualification.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--recipes", type=Path, help="select the explicit v2 recipe contract; omission retains the v1 contract")
    parser.add_argument("--lifts-output", type=Path, help="ignored-output path for all 28 fresh v2 lifts")
    args = parser.parse_args()
    from run_output import run_output
    output = run_output(args.output)
    if args.lifts_output is not None and args.recipes is None:
        parser.error("--lifts-output requires --recipes")
    lifts_output = run_output(args.lifts_output) if args.lifts_output is not None else None
    report = run_recipes(args.recipes, lifts_output) if args.recipes else run()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(f'Repeated-string oracle: {len(report["rows"])} forms, {report["comparisons"]} comparisons pass')


if __name__ == "__main__":
    main()
