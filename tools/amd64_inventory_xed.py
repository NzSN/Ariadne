#!/usr/bin/env python3
"""Normalize the pinned official XED reader's complete selected record sequence.

This subprocess imports source from an already archive-verified checkout. It
does not infer instruction semantics or expand symbolic patterns into byte strings.
"""
import argparse
from collections import Counter
from enum import Enum
import hashlib
import json
from pathlib import Path
import sys


SCHEMA = "ariadne.xed-template-inventory/v1"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def plain(value):
    """Keep all upstream fields, including parsed operand and CPUID structures."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, Enum):
        return value.name
    if isinstance(value, (list, tuple)):
        return [plain(item) for item in value]
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in sorted(value.items())}
    if hasattr(value, "__dict__"):
        return plain(vars(value))
    raise ValueError("unhandled upstream field type: " + type(value).__name__)


def mode_domain(record):
    """Explicit mode/address constraints only; all other constraints are retained."""
    restriction = record["mode_restriction"]
    if restriction == "unspecified":
        modes = [16, 32, 64]
    elif restriction == "not64":
        modes = [16, 32]
    elif restriction in (0, 1, 2):
        modes = [[16], [32], [64]][restriction]
    else:
        raise ValueError("unknown upstream mode restriction")
    # An effective address size of 16 is impossible in 64-bit long mode.
    if record["easz"] == "a16" and 64 in modes:
        modes.remove(64)
    return modes


def normalize(records):
    rows = []
    occurrences = Counter()
    for index, record in enumerate(records):
        source = plain(vars(record) if hasattr(record, "__dict__") else record)
        for field in ("iclass", "iform", "pattern", "operands", "isa_set",
                      "space", "mode_restriction", "easz"):
            if field not in source:
                raise ValueError("missing upstream instruction field: " + field)
        identity = digest(source)
        occurrences[identity] += 1
        rows.append({
            "id": "xed:" + identity + ":" + str(occurrences[identity]),
            "sourceOrdinal": index,
            "mnemonic": source["iclass"],
            "iform": source["iform"],
            "modeDomain": mode_domain(source),
            "encodingSpace": source["space"],
            "isaSet": source["isa_set"],
            "source": source,
        })
    return rows


def summarize(rows):
    return {
        "records": len(rows),
        "longModeCandidates": sum(64 in row["modeDomain"] for row in rows),
        "longModeExcluded": sum(64 not in row["modeDomain"] for row in rows),
        "mnemonics": len({row["mnemonic"] for row in rows}),
        "iforms": len({row["iform"] for row in rows}),
        "isaSets": len({row["isaSet"] for row in rows}),
        "encodingSpaces": dict(sorted(Counter(row["encodingSpace"] for row in rows).items())),
        "amdOnlyRecords": sum("AMDONLY" in row["source"].get("attributes", "").split()
                              for row in rows),
        "undocumentedRecords": sum(bool(row["source"].get("undocumented")) for row in rows),
    }


def generate(source, build, mbuild):
    sys.path[:0] = [str(source / "pysrc"), str(mbuild)]
    import read_xed_db
    dgen = build / "dgen"
    names = ("all-state.txt", "all-dec-instructions.txt", "all-widths.txt",
             "all-extra-widths.txt", "all-element-types.txt", "all-cpuid.txt",
             "all-map-descriptions.txt")
    database = read_xed_db.xed_reader_t(*(str(dgen / name) for name in names))
    if database.deleted_instructions:
        raise ValueError("new DELETE_ICLASS directive requires explicit adapter review")
    rows = normalize(database.recs)
    selected = []
    for name in (build / "prep-inputs").read_text().splitlines():
        path = Path(name).resolve()
        selected.append({"path": path.relative_to(source.resolve()).as_posix(),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    inputs = {}
    for path in sorted(dgen.glob("*.txt")):
        # XED embeds absolute source paths in FILE comments; normalize only the
        # verified checkout prefix so a second workspace has the same identity.
        content = path.read_text().replace(str(source.resolve()), "<XED>")
        inputs[path.name] = hashlib.sha256(content.encode()).hexdigest()
    return {
        "schema": SCHEMA,
        "scope": {
            "denominator": "All records emitted by pinned XED default just-prep and official read_xed_db",
            "unit": "symbolic encoding template, not mnemonic, IFORM or concrete byte string",
            "modeDomainMeaning": "Explicit source mode/address constraints; all remaining legality constraints stay in source.pattern and the pinned grammar",
            "prefixAndOperandCoverage": "Symbolic constraints retained; no Cartesian expansion or exhaustive byte-validity claim",
            "cpuidMeaning": "Upstream groups retained; an empty group list does not establish hardware availability",
            "amdArchitectureCompleteness": "not-established-by-XED-inventory",
            "semanticsCoverage": "not-measured-by-this-tool",
        },
        "selectedInputs": selected,
        "preparedInputSha256": inputs,
        "operandWidths": plain(database.get_width_info_dict()),
        "counts": summarize(rows),
        "recordsSha256": digest(rows),
        "records": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--mbuild", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = generate(args.source.resolve(), args.build.resolve(), args.mbuild.resolve())
    args.output.write_bytes(canonical(result) + b"\n")
    print(json.dumps({"counts": result["counts"], "recordsSha256": result["recordsSha256"]}))


if __name__ == "__main__":
    main()
