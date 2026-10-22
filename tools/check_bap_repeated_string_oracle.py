#!/usr/bin/env python3
"""Check actual BAP REP BIL against independent sequential byte operations."""
import argparse
import hashlib
import itertools
import json
from pathlib import Path

from check_bap_admission_oracle import Value, fresh_lifts
from check_bap_bit_count_oracle import BANKS, FLAGS, IdentityEvaluator

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


def subtract_flags(left, right):
    result = (left - right) & 255
    return {"CF": int(left < right), "PF": int(result.bit_count() % 2 == 0),
            "AF": int(bool((left ^ right ^ result) & 16)), "ZF": int(result == 0),
            "SF": result >> 7, "OF": int(bool((left ^ right) & (left ^ result) & 128))}


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from run_output import run_output
    output = run_output(args.output)
    report = run()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(f'Repeated-string oracle: {len(report["rows"])} forms, {report["comparisons"]} comparisons pass')


if __name__ == "__main__":
    main()
