#!/usr/bin/env python3
"""Compare fresh BAP bit-count BIL with independent integer equations."""
import argparse
import hashlib
import json
from pathlib import Path
import random

from check_bap_admission_oracle import Evaluator, Value, fresh_lifts

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "tests/bap/fixtures/bit-count/contract.json"
BANKS = ["RAX", "RCX", "RDX", "RBX", "RSP", "RBP", "RSI", "RDI"] + [f"R{i}" for i in range(8, 16)]
FLAGS = ["CF", "PF", "AF", "ZF", "SF", "OF", "DF"]


class IdentityEvaluator(Evaluator):
    """Keep typed-BIL temporary identities distinct from architectural names."""
    @staticmethod
    def key(var):
        return (var["name"], var["index"], True) if var["virtual"] else var["name"]

    def expr(self, expression):
        if expression["kind"] == "var":
            var = expression["var"]
            return self.memory if var["type"] == "mem" else self.values[self.key(var)]
        if expression["kind"] == "let":
            key = self.key(expression["var"])
            present = key in self.values
            old = self.values.get(key)
            self.values[key] = self.expr(expression["value"])
            result = self.expr(expression["body"])
            if present:
                self.values[key] = old
            else:
                del self.values[key]
            return result
        return super().expr(expression)

    def statements(self, statements):
        for statement in statements:
            kind = statement["kind"]
            if kind == "move":
                if statement["var"]["type"] == "mem":
                    raise ValueError("bit-count operation unexpectedly writes memory")
                self.values[self.key(statement["var"])] = self.expr(statement["value"])
            elif kind == "if":
                condition = self.expr(statement["condition"])
                if condition.n is None:
                    raise ValueError("indeterminate condition in numeric bit-count oracle")
                self.statements(statement["yes"] if condition.n else statement["no"])
            else:
                raise ValueError("unexpected bit-count BIL statement: " + kind)


def expected(operation, width, value):
    if not 0 <= value < 1 << width:
        raise ValueError("operand outside declared width")
    if operation == "popcnt":
        result = value.bit_count()
        flags = {flag: 0 for flag in ["CF", "PF", "AF", "SF", "OF"]}
        flags["ZF"] = int(value == 0)
    elif operation in {"lzcnt", "tzcnt"}:
        result = (width - value.bit_length() if operation == "lzcnt" else
                  width if value == 0 else (value & -value).bit_length() - 1)
        flags = {"CF": int(value == 0), "ZF": int(result == 0)}
    else:
        raise ValueError("unknown bit-count operation")
    return result, flags


def inputs(width):
    mask = (1 << width) - 1
    values = {0, 1, 2, 3, mask, mask - 1, mask >> 1, int("aa" * (width // 8), 16),
              int("55" * (width // 8), 16)}
    for bit in range(width):
        values.update({1 << bit, mask ^ (1 << bit)})
    rng = random.Random(0xB17C0000 + width)
    values.update(rng.getrandbits(width) for _ in range(32))
    return sorted(values)


def check_case(case, bil, value, flag_seed):
    width = case["width"]
    registers = {name: Value(0xA51234879BCD0123 ^ (i << 16), 64) for i, name in enumerate(BANKS)}
    registers.update({flag: Value(flag_seed, 1) for flag in FLAGS})
    memory = {}
    if case["source"] == "register":
        registers["RBX"] = Value(value, 64)
    elif case["source"] == "memory":
        registers["RBX"] = Value(0x7000, 64)
        memory = {0x7000 + i: (value >> (8 * i)) & 255 for i in range(width // 8)}
    else:
        raise ValueError("unknown operand source")
    evaluator = IdentityEvaluator(registers, memory.copy())
    evaluator.statements(bil)
    result, flags = expected(case["operation"], width, value)
    destination = ((registers["RAX"].n & ~0xffff) | result) if width == 16 else result
    checks = {"RAX": destination, "DF": flag_seed, **flags}
    checks.update({bank: registers[bank].n for bank in BANKS if bank != "RAX"})
    for name, want in checks.items():
        actual = evaluator.values.get(name)
        if actual is None or actual.n != want:
            raise ValueError(f'{case["name"]} input={value:#x} initial_flags={flag_seed} '
                             f'{name}: got {None if actual is None else actual.n}, expected {want}')
    if evaluator.memory != memory:
        raise ValueError("bit-count operation changed source memory")


def run(contract_path=CONTRACT, helper=None, runtime=None):
    contract = json.loads(Path(contract_path).read_text())
    cases = contract["cases"]
    lifts, bil_sha, helper_sha = fresh_lifts(cases, contract_path, helper, runtime)
    rows = []
    for case, lift in zip(cases, lifts):
        values = inputs(case["width"])
        for value in values:
            for flag_seed in (0, 1):
                check_case(case, lift["bil"], value, flag_seed)
        rows.append({"case": case["name"], "comparisons": len(values) * 2})
    sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return dict(schema="ariadne.bap-bit-count-oracle/v1", passed=True, cases=len(rows),
                comparisons=sum(row["comparisons"] for row in rows), rows=rows,
                contractSha256=sha(contract_path), typedBilSha256=bil_sha, helperSha256=helper_sha,
                oracleSourceSha256=sha(__file__), evaluatorSourceSha256=sha(ROOT / "tools/check_bap_admission_oracle.py"),
                scope="Fresh BAP numeric results, defined flags, partial/zero-extended destinations and unaffected state for 18 register/memory forms. Undefined flags are not compared; no full ISA or hardware qualification.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--helper", type=Path)
    parser.add_argument("--runtime", type=Path)
    args = parser.parse_args()
    from run_output import run_output
    output = run_output(args.output)
    report = run(helper=args.helper, runtime=args.runtime)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(f'Bit-count oracle: {report["cases"]} forms, {report["comparisons"]} comparisons pass')


if __name__ == "__main__":
    main()
