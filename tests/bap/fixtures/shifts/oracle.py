#!/usr/bin/env python3
"""Independent BIL shift oracle using integer division and multiplication.

No Rust, native helper, or implementation source is loaded. The exhaustive
campaign covers every 1..256 data/count-width pair and all three operators,
representable boundary counts, and counts with bits above bit 63. Its rolling
digest is compact; selected numeric rows expose every individual width to the
Rust projector through branch probes. --write regenerates contract.json;
--check compares the complete frozen contract and captured-fixture identity.
"""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OPS = (9, 10, 11)


def operand(width, negative):
    value = sum(1 << bit for bit in range(width - 1) if bit % 5 in (0, 2))
    return value | ((1 << (width - 1)) if negative else 0)


def result(op, width, value, count):
    modulus = 2 ** width
    signed = value - modulus if value >= modulus // 2 else value
    if count >= width:
        return modulus - 1 if op == 9 and signed < 0 else 0
    factor = 2 ** count
    if op == 11:
        return (value * factor) % modulus
    if op == 10:
        return value // factor
    return (signed // factor) % modulus


def counts(width, count_width):
    values = {0, width - 1, width, width + 1}
    if count_width > 64:
        values.update((1 << (count_width - 1), (1 << (count_width - 1)) + 1))
    return sorted(n for n in values if n < (1 << count_width))


def selected_pairs():
    # Numerical rows expose both complete width axes and representative cross
    # pairs; the independent campaign above exhausts every pair, while Rust's
    # admission test separately exhausts the same full type cross product.
    pairs = {(width, 256) for width in range(1, 257)}
    pairs.update((128, width) for width in range(1, 257))
    pairs.update((width, count_width)
                 for width in (1, 8, 16, 32, 64, 128, 256)
                 for count_width in (1, 8, 16, 32, 64, 65, 128, 256))
    return sorted(pairs)


def contract():
    rolling = hashlib.sha256()
    total = 0
    for width in range(1, 257):
        for count_width in range(1, 257):
            for op in OPS:
                for negative in (False, True):
                    value = operand(width, negative)
                    for count in counts(width, count_width):
                        answer = result(op, width, value, count)
                        rolling.update(f"{width},{count_width},{op},{int(negative)},{count:x},{answer:x}\n".encode())
                        total += 1
    rows = []
    for width, count_width in selected_pairs():
        for op in OPS:
            for negative in (False, True):
                value = operand(width, negative)
                for count in counts(width, count_width):
                    answer = result(op, width, value, count)
                    rows.append({
                        "op": op, "value_width": width, "count_width": count_width,
                        "value_hex": hex(value), "count_hex": hex(count),
                        "result_hex": hex(answer),
                        "probe_bits": sorted({0, width // 2, width - 1}),
                    })
    captured = (HERE / "captured-xorps-bil.json").read_bytes()
    return {
        "schema": "ariadne.bap-shift-oracle/v1",
        "contract": {"value_width": [1, 256], "count_width": [1, 256],
                     "ops": {"9": "arithmetic-right", "10": "logical-right", "11": "logical-left"},
                     "result_width": "left operand", "count": "full unsigned bitvector",
                     "oversized": "zero or original-sign fill; no modulo count"},
        "campaign": {"width_pairs": 256 * 256, "cases": total,
                     "sha256": rolling.hexdigest(),
                     "boundaries": ["0", "w-1", "w", "w+1", "high-bit-above-63", "high-bit-above-63-plus-one"]},
        "captured_xorps_sha256": hashlib.sha256(captured).hexdigest(),
        "cases": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = contract()
    target = HERE / "contract.json"
    if args.write:
        target.write_text(json.dumps(expected, separators=(",", ":"), sort_keys=True) + "\n")
    else:
        actual = json.loads(target.read_text())
        if actual != expected:
            raise SystemExit("BIL shift oracle differs from frozen contract")
    print(f"BIL shift oracle PASS: {expected['campaign']['width_pairs']} width pairs, "
          f"{expected['campaign']['cases']} exhaustive numeric cases, "
          f"{len(expected['cases'])} projector rows; digest {expected['campaign']['sha256']}")


if __name__ == "__main__":
    main()
