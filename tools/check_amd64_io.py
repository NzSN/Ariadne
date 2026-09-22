#!/usr/bin/env python3
"""Generate/check the lane-owned IN/OUT/INS/OUTS semantic supplement."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Specs" / "AMD64"
OUTPUT = DATA / "io-form-supplement.json"
ENTRY_IDS = ["V3-GP-057", "V3-GP-059", "V3-GP-099", "V3-GP-100"]


def read(path):
    return json.loads(path.read_text())


def width_bits(spelling):
    match = re.search(r"mem(8|16|32)", spelling)
    if match:
        return int(match.group(1))
    for token, width in [("EAX", 32), ("AX", 16), ("AL", 8)]:
        if re.search(rf"\b{token}\b", spelling):
            return width
    suffix = spelling.split()[0][-1]
    return {"B": 8, "W": 16, "D": 32}[suffix]


def build():
    locks = read(DATA / "manuals.lock.json")["sources"]
    source = read(DATA / "instruction-source.json")
    forms = read(DATA / "forms.json")
    entries = {row["id"]: row for row in source["entries"]}
    selected = [row for row in forms["forms"] if set(row["entry_ids"]) & set(ENTRY_IDS)]
    rows = []
    for form in selected:
        entry_id = next(entry for entry in form["entry_ids"] if entry in ENTRY_IDS)
        spelling = form["source_spelling"]
        mnemonic = spelling.split()[0]
        string = entry_id in {"V3-GP-059", "V3-GP-100"}
        direction = "input" if entry_id in {"V3-GP-057", "V3-GP-059"} else "output"
        port_source = "dx-low16" if string or "DX" in spelling else "immediate8-zero-extended"
        width = width_bits(spelling)
        rows.append({
            "form_id": form["form_id"],
            "entry_id": entry_id,
            "source_spelling": spelling,
            "source_rows": form["source"]["row_ids"],
            "direction": direction,
            "string": string,
            "port_source": port_source,
            "data_width_bits": width,
            "effective_64_bit_operand_behavior": "normalize-to-32-bit-port",
            "repeat_modes": ["none", "rep"] if string else ["none"],
            "permission_dependency": "SYS-IO-PERMISSION",
            "permission_rule": "bitmap required in virtual8086 or when CPL > IOPL; all consecutive byte-port bits must be covered and clear",
            "unaligned_rule": "architecturally permitted; byte transaction order implementation-dependent",
            "boundary_rule": "cross-FFFF behavior remains source-unspecified when IOPL bypasses bitmap denial",
            "form_review_status": form["review"]["status"],
            "shared_form_implementation_status": form["implementation"]["status"],
            "io1_projection_status": "source-reviewed-supplement",
            "binding_owner": "/root/external_io",
            "binding_status": ("partial-success-binding-ordering-open" if string
                               else "direct-body-bound-shared-form-open"),
            "exception_device_priority": (
                "mixed memory/permission/device priority remains ordering-open"
                if string else
                "permission denial or permission-read page fault precedes device binding; "
                "missing device rule is modeling-unavailable after permission and ordering"
            ),
            "open_obligations": form["review"]["open_obligations"] + [
                "attach supplement to validated executable form",
                "close cross-boundary port behavior or retain unavailable outcome",
            ],
        })
    entry_rows = []
    for entry_id in ENTRY_IDS:
        entry = entries[entry_id]
        entry_forms = [row["form_id"] for row in rows if row["entry_id"] == entry_id]
        entry_rows.append({
            "entry_id": entry_id,
            "title": entry["title"],
            "pdf_pages": list(range(entry["pdf_page"], entry["pdf_end_page"] + 1)),
            "form_ids": entry_forms,
            "full_entry_status": "open",
        })
    return {
        "schema_version": 1,
        "generated_by": "tools/check_amd64_io.py",
        "authority": {
            "volume1_sha256": next(x["sha256"] for x in locks if x["volume"] == 1),
            "volume2_sha256": next(x["sha256"] for x in locks if x["volume"] == 2),
            "volume3_sha256": next(x["sha256"] for x in locks if x["volume"] == 3),
            "sources": ["V1-SECTION-0090", "V1-SECTION-0091", "V1-SECTION-0092",
                        "V2-SECTION-0650", "V2-SECTION-0683", "V3-GP-057",
                        "V3-GP-059", "V3-GP-099", "V3-GP-100"],
        },
        "completeness_boundary": (
            "This supplement records reviewed IO semantics without changing forms.json. "
            "Direct IN/OUT body effects are bound to explicit device events; shared form "
            "acceptance remains open. INS/OUTS are bound only "
            "for successful resolved/device-rule cases. No entry or form is complete."
        ),
        "summary": {"entry_rows": 4, "form_rows": len(rows),
                    "fully_implemented_entries": 0, "fully_bound_forms": 0},
        "entries": entry_rows,
        "forms": rows,
    }


def validate(data):
    forms = read(DATA / "forms.json")
    source = read(DATA / "instruction-source.json")
    expected = {row["form_id"] for row in forms["forms"]
                if set(row["entry_ids"]) & set(ENTRY_IDS)}
    actual = {row["form_id"] for row in data["forms"]}
    if actual != expected or len(actual) != len(data["forms"]):
        raise ValueError("IO supplement forms drifted from forms.json")
    if [row["entry_id"] for row in data["entries"]] != ENTRY_IDS:
        raise ValueError("IO supplement must contain four assigned entries in stable order")
    titles = {row["id"]: row["title"] for row in source["entries"]}
    for row in data["entries"]:
        if row["title"] != titles[row["entry_id"]]:
            raise ValueError(f"{row['entry_id']}: title drift")
    if len(data["forms"]) != 24:
        raise ValueError("Expected 24 IN/OUT/INS/OUTS forms")
    if data["summary"]["fully_bound_forms"] != 0:
        raise ValueError("IO1 does not close forms")
    print("AMD64 IO supplement valid: 4 entries, 24 forms, 0 fully bound")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["generate", "check"])
    args = parser.parse_args()
    if args.command == "generate":
        OUTPUT.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n")
    validate(read(OUTPUT))


if __name__ == "__main__":
    main()
