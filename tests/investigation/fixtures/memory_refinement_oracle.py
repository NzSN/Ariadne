#!/usr/bin/env python3
"""Independent integer/set oracle; no Ariadne evaluator or BAP output inputs."""
import json
from pathlib import Path


def overlap(a, n, b, m, bits=64):
    modulus = 1 << bits
    return bool({(a+i) % modulus for i in range(n)} &
                {(b+i) % modulus for i in range(m)})


def predecessors(kind, after, operand, bits=4):
    modulus = 1 << bits
    functions = {
        "copy": lambda x: x,
        "add": lambda x: (x+operand) % modulus,
        "sub": lambda x: (x-operand) % modulus,
        "and": lambda x: x & operand,
        "constant": lambda x: operand,
    }
    return [x for x in range(modulus) if functions[kind](x) == after]


def cases():
    maximum = (1 << 64)-1
    ranges = []
    for a in [0, 1, 0x18, 0x28, maximum-7, maximum-1, maximum]:
        for b in [0, 1, 0x18, 0x28, maximum-7, maximum-1, maximum]:
            for n in [1, 2, 4, 8]:
                for m in [1, 2, 4, 8]:
                    ranges.append({"a": f"0x{a:016x}", "a_bytes": n,
                                   "b": f"0x{b:016x}", "b_bytes": m,
                                   "overlapping": overlap(a,n,b,m)})
    inverse = []
    for kind in ["copy", "add", "sub", "and", "constant"]:
        for operand in range(16):
            for after in range(16):
                values = predecessors(kind,after,operand)
                precision = ("conflict" if not values else "exact" if len(values)==1
                             else "unknown" if len(values)==16 else "constrained")
                inverse.append({"kind": kind, "width": 4, "operand": operand,
                                "after": after, "before": values,
                                "precision": precision})
    return {"schema": "ariadne.memory-refinement-oracle/v1",
            "range_cases": ranges, "inverse_cases": inverse,
            "scope": "Independent finite integer/set expectations, not ISA qualification"}


if __name__ == "__main__":
    path = Path(__file__).with_name("memory_refinement_oracle.json")
    data = cases()
    if path.exists():
        assert json.loads(path.read_text()) == data, "frozen independent oracle changed"
    else:
        path.write_text(json.dumps(data,indent=2)+"\n")
    print(f"Oracle PASS: {len(data['range_cases'])} range cases, "
          f"{len(data['inverse_cases'])} inverse cases")
