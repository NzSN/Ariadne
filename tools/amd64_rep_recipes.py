#!/usr/bin/env python3
"""Strict selected memory-REP recipes; these tuples are not a denominator."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECIPES = ROOT / "tests/bap/fixtures/repeated-string/memory-recipes-v2.json"
PROFILE = "bap-bit-provenance-v13"
MANUAL_SHA = "e18bd39ad0ca19d2eb9b9ea25c2635144c5ab368e5d6fbdc7a08345515ea1aee"


def load_recipes(path=RECIPES):
    document = json.loads(Path(path).read_text())
    if document.get("schema") != "ariadne.amd64-memory-rep-recipes/v2":
        raise ValueError("unknown memory-REP recipe schema")
    source = document["sources"]["amd-24594-r3.38"]
    if (source["sha256"] != MANUAL_SHA or source["publication"] != "24594"
            or source["revision"] != "3.38" or source["repeatPrefixPdfPages"] != [54, 55, 56]
            or source["repeatPrefixTables"] != ["1-6", "1-7", "1-8"]):
        raise ValueError("memory-REP manual source differs")
    if document["environment"] != {
            "mode": "long-64", "flatDefaultSegments": True,
            "outcomes": "finite-normal-completion-only",
            "prefixOrder": "66 before F2/F3; REX.W after F2/F3",
            "excludedPrefixes": ["address-size-67", "segment-override", "lock",
                                 "duplicate", "extra", "alternative-order"]}:
        raise ValueError("memory-REP environment differs")
    cases = document["cases"]
    expected = {}
    for family, prefix, byte, wide, condition, pages in [
            ("movs", "f3", 0xa4, 0xa5, "count", [301, 302]),
            ("stos", "f3", 0xaa, 0xab, "count", [396, 397]),
            ("lods", "f3", 0xac, 0xad, "count", [267, 268]),
            ("cmps", "f3", 0xa6, 0xa7, "equal", [207, 208]),
            ("cmps", "f2", 0xa6, 0xa7, "not-equal", [207, 208]),
            ("scas", "f3", 0xae, 0xaf, "equal", [376, 377]),
            ("scas", "f2", 0xae, 0xaf, "not-equal", [376, 377])]:
        for bits, suffix, extra in [(8, "B", ""), (16, "W", "66"),
                                    (32, "L", ""), (64, "Q", "48")]:
            encoded = (extra + prefix if bits == 16 else prefix + extra)
            encoded += f"{byte if bits == 8 else wide:02x}"
            expected[encoded] = (family, bits, condition, family.upper() + suffix, pages)
    if len(cases) != 28 or len({case["name"] for case in cases}) != 28:
        raise ValueError("memory-REP recipe cardinality or name identity differs")
    seen = set()
    for case in cases:
        encoded = case["bytes"]
        if encoded not in expected or encoded in seen:
            raise ValueError("unreviewed or duplicate memory-REP encoding")
        seen.add(encoded)
        family, bits, condition, opcode, pages = expected[encoded]
        if (case["family"] != family or case["operation"] != family
                or case["elementBits"] != bits or case["repeatCondition"] != condition
                or case["bapOpcode"] != opcode or case["manualPdfPages"] != pages
                or case["manualSource"] != "amd-24594-r3.38"
                or any(case[key] != 64 for key in ["addressBits", "countBits", "indexBits"])
                or case["sourceSegment"] != ("default-flat-ds" if family in {"movs", "lods", "cmps"} else "none")
                or case["destinationSegment"] != ("default-flat-es" if family in {"movs", "stos", "cmps", "scas"} else "none")):
            raise ValueError("memory-REP recipe domain differs")
        if family == "lods":
            if case["profile"] is not None or case.get("unsupportedReason") != "pinned-legacy-producer-empty-bil":
                raise ValueError("missing LODS producer lift cannot be admitted")
        elif case["profile"] != PROFILE or "unsupportedReason" in case:
            raise ValueError("reviewed memory-REP profile differs")
    return document


if __name__ == "__main__":
    recipes = load_recipes()
    print(f'Memory-REP recipes: {len(recipes["cases"])} selected tuples; '
          '24 nonempty-lift candidates, 4 missing LODS lifts')
