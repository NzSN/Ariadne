"""Lossless wire view for the two integer-address maps unsupported by Mirrors v1.

Unlike the compiler's interval-only zip projection, this preserves arbitrary
sparse keys explicitly. Type transformations derive from Apalache declarations,
never sampled values. Every converted trace is checked by an exact inverse.
"""

from copy import deepcopy

FIELDS = {
    "provenance": ("source", "(Int -> Str)", "Set({ source: Str, va: Int })"),
    "reaching": ("definitions", "(Int -> Set({ loc: Str, origin: Str, site: Int }))",
                 "Set({ definitions: Set({ loc: Str, origin: Str, site: Int }), va: Int })"),
}


def project(raw):
    projected = deepcopy(raw)
    for name, (field, source_type, target_type) in FIELDS.items():
        actual_type = raw["#meta"]["varTypes"][name]
        if "".join(actual_type.split()) != "".join(source_type.split()):
            raise ValueError(f"unsupported declared source type for {name}: {actual_type}")
        projected["#meta"]["varTypes"][name] = target_type
        for state in projected["states"]:
            mapping = state[name]
            if not isinstance(mapping, dict) or set(mapping) != {"#map"}:
                raise ValueError(f"{name} must be a strict ITF map")
            seen = set()
            rows = []
            for pair in mapping["#map"]:
                if not isinstance(pair, list) or len(pair) != 2:
                    raise ValueError("malformed map pair")
                key, value = pair
                if not isinstance(key, dict) or set(key) != {"#bigint"}:
                    raise ValueError("map key must be an ITF integer")
                address = key["#bigint"]
                if not isinstance(address, str) or not address.isdecimal() or str(int(address)) != address:
                    raise ValueError("address must be canonical nonnegative decimal")
                if address in seen:
                    raise ValueError("duplicate map address")
                seen.add(address)
                rows.append({"va": key, field: value})
            state[name] = {"#set": rows}
    if restore(projected, raw["#meta"]["varTypes"]) != raw:
        raise ValueError("projection changed information other than the declared wire representation")
    return projected


def restore(projected, source_types):
    raw = deepcopy(projected)
    for name, (field, _, _) in FIELDS.items():
        raw["#meta"]["varTypes"][name] = source_types[name]
        for state in raw["states"]:
            rows = state[name]["#set"]
            if any(set(row) != {"va", field} for row in rows):
                raise ValueError("malformed projection row")
            state[name] = {"#map": [[row["va"], row[field]] for row in rows]}
    return raw
