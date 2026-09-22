#!/usr/bin/env python3
"""Generate/check the bounded C4 string-control coverage artifact."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Specs" / "AMD64"
OUTPUT = DATA / "string-coverage.json"
ENTRY_IDS = ["V3-GP-045", "V3-GP-059", "V3-GP-072", "V3-GP-088",
             "V3-GP-100", "V3-GP-130", "V3-GP-142"]

ENTRY_META = {
    "V3-GP-045": {
        "kind": "cmps", "widths": [1, 2, 4, 8], "repeat_modes": ["none", "repe", "repne"],
        "implicit_registers": ["RSI", "RDI", "RCX when repeated", "RFLAGS.DF", "status flags"],
        "stage_order": ["sourceRead", "destinationRead", "flagsWrite", "commitReady"],
        "open": ["bind both memory reads and their exception order", "bind full SUB flags to CPU state"]},
    "V3-GP-059": {
        "kind": "ins", "widths": [1, 2, 4], "repeat_modes": ["none", "rep"],
        "implicit_registers": ["RDX", "RDI", "RCX when repeated", "RFLAGS.DF"],
        "stage_order": ["ioRead", "destinationWrite", "commitReady"],
        "open": ["define port-width/device result contract", "prove I/O-read versus destination-fault ordering", "bind I/O permission and memory write outcomes"]},
    "V3-GP-072": {
        "kind": "lods", "widths": [1, 2, 4, 8], "repeat_modes": ["none", "rep"],
        "implicit_registers": ["RAX view", "RSI", "RCX when repeated", "RFLAGS.DF"],
        "stage_order": ["sourceRead", "accumulatorWrite", "commitReady"],
        "open": ["bind memory data to AL/AX/EAX/RAX write semantics", "bind memory faults"]},
    "V3-GP-088": {
        "kind": "movs", "widths": [1, 2, 4, 8], "repeat_modes": ["none", "rep"],
        "implicit_registers": ["RSI", "RDI", "RCX when repeated", "RFLAGS.DF"],
        "stage_order": ["sourceRead", "destinationWrite", "commitReady"],
        "open": ["bind read value to destination write", "prove source-read/destination-write fault and event ordering"]},
    "V3-GP-100": {
        "kind": "outs", "widths": [1, 2, 4], "repeat_modes": ["none", "rep"],
        "implicit_registers": ["RDX", "RSI", "RCX when repeated", "RFLAGS.DF"],
        "stage_order": ["sourceRead", "ioWrite", "commitReady"],
        "open": ["define port-width/device write contract", "prove memory-read versus I/O permission/effect ordering"]},
    "V3-GP-130": {
        "kind": "scas", "widths": [1, 2, 4, 8], "repeat_modes": ["none", "repe", "repne"],
        "implicit_registers": ["RAX view", "RDI", "RCX when repeated", "RFLAGS.DF", "status flags"],
        "stage_order": ["destinationRead", "flagsWrite", "commitReady"],
        "open": ["bind destination memory value and faults", "bind accumulator-minus-destination flags"]},
    "V3-GP-142": {
        "kind": "stos", "widths": [1, 2, 4, 8], "repeat_modes": ["none", "rep"],
        "implicit_registers": ["RAX view", "RDI", "RCX when repeated", "RFLAGS.DF"],
        "stage_order": ["destinationWrite", "commitReady"],
        "open": ["bind accumulator value to destination memory write", "bind memory faults"]},
}


def read(path):
    return json.loads(path.read_text())


def width_bytes(spelling: str):
    match = re.search(r"mem(8|16|32|64)", spelling)
    if match:
        return int(match.group(1)) // 8
    mnemonic = spelling.split()[0]
    suffix = mnemonic[-1]
    return {"B": 1, "W": 2, "D": 4, "Q": 8}.get(suffix)


def build():
    source = read(DATA / "instruction-source.json")
    forms = read(DATA / "forms.json")
    locks = read(DATA / "manuals.lock.json")["sources"]
    entries = {row["id"]: row for row in source["entries"]}
    selected_forms = [row for row in forms["forms"] if set(row["entry_ids"]) & set(ENTRY_IDS)]
    entry_rows = []
    form_rows = []
    for entry_id in ENTRY_IDS:
        entry = entries[entry_id]
        meta = ENTRY_META[entry_id]
        owned = [row for row in selected_forms if entry_id in row["entry_ids"]]
        memory_only = meta["kind"] not in {"ins", "outs"}
        entry_rows.append({
            "entry_id": entry_id,
            "title": entry["title"],
            "pdf_pages": list(range(entry["pdf_page"], entry["pdf_end_page"] + 1)),
            "form_ids": [row["form_id"] for row in owned],
            "kind": meta["kind"],
            "element_width_bytes": meta["widths"],
            "address_sizes_bits": [16, 32, 64],
            "repeat_modes": meta["repeat_modes"],
            "implicit_registers": meta["implicit_registers"],
            "stage_order": meta["stage_order"],
            "control_kernel_status": "implemented-checked",
            "memory_binding_status": ("resolved-captured-bytes-and-relational-cpu-memory-commit"
                                      if memory_only else "successful-path-resolved-memory-binding"),
            "io_binding_status": ("successful-explicit-device-rule-only"
                                  if meta["kind"] in {"ins", "outs"} else "not-applicable"),
            "entry_implementation_status": ("partial-memory-iteration-binding"
                                             if memory_only else "partial-success-binding-ordering-open"),
            "evidence": {
                "tla": ["Specs/AMD64Strings.tla", "Specs/AMD64StringsChecks.tla"] +
                       (["Specs/AMD64StringsMemory.tla", "Specs/AMD64StringsMemoryChecks.tla"]
                        if memory_only else
                        ["Specs/AMD64IO.tla", "Specs/AMD64IOStrings.tla"]),
                "lean": ["lean/AMD64/Strings.lean"] +
                        (["lean/AMD64/StringsMemory.lean"] if memory_only else
                         ["lean/AMD64/IO.lean", "lean/AMD64/IOStrings.lean"]),
            },
            "open_obligations": meta["open"] + [
                "reconcile and validate every form in the parent form ledger",
                "bind interruption/fault outcomes with independent committed-effect and iteration counts",
            ],
        })
        for form in owned:
            form_rows.append({
                "form_id": form["form_id"],
                "entry_id": entry_id,
                "source_spelling": form["source_spelling"],
                "element_width_bytes": width_bytes(form["source_spelling"]),
                "source_rows": form["source"]["row_ids"],
                "form_review_status": form["review"]["status"],
                "form_implementation_status": form["implementation"]["status"],
                "control_kernel_status": "covered-by-kind-and-width",
                "instruction_binding_status": "open",
                "open_obligations": form["review"]["open_obligations"],
            })
    return {
        "schema_version": 1,
        "generated_by": "tools/check_amd64_strings.py",
        "authority": {
            "volume1_sha256": next(x["sha256"] for x in locks if x["volume"] == 1),
            "volume2_sha256": next(x["sha256"] for x in locks if x["volume"] == 2),
            "volume3_sha256": next(x["sha256"] for x in locks if x["volume"] == 3),
            "repeat_section": {"id": "V3-SECTION-1082", "pdf_page": 54},
            "partial_progress_dependency": "SYS-PARTIAL-PROGRESS",
            "io_intercept_dependency": {"id": "V2-SECTION-0773", "pdf_page": 601},
        },
        "completeness_boundary": (
            "Checked means only the pure count/pointer/condition/stage/restart kernel. "
            "No entry or form is fully implemented until data movement, memory/I/O events, "
            "fault ordering, form legality, and CPU/memory outcome binding are evidenced."
        ),
        "summary": {
            "entry_rows": len(entry_rows),
            "form_rows": len(form_rows),
            "control_kernel_entries": len(entry_rows),
            "memory_data_binding_entries": 5,
            "io_mixed_failure_ordering_open_entries": 2,
            "fully_implemented_entries": 0,
            "fully_bound_forms": 0,
        },
        "entries": entry_rows,
        "forms": form_rows,
    }


def validate(data):
    forms = read(DATA / "forms.json")
    source = read(DATA / "instruction-source.json")
    expected_forms = {row["form_id"] for row in forms["forms"]
                      if set(row["entry_ids"]) & set(ENTRY_IDS)}
    if [row["entry_id"] for row in data["entries"]] != ENTRY_IDS:
        raise ValueError("string entry order/coverage differs from assignment")
    if len(data["entries"]) != 7 or len({row["entry_id"] for row in data["entries"]}) != 7:
        raise ValueError("exactly seven unique string entries are required")
    actual_forms = {row["form_id"] for row in data["forms"]}
    if actual_forms != expected_forms or len(actual_forms) != len(data["forms"]):
        raise ValueError("string forms differ from current reviewed form inventory")
    entries = {row["id"]: row for row in source["entries"]}
    for row in data["entries"]:
        if row["title"] != entries[row["entry_id"]]["title"]:
            raise ValueError(f"{row['entry_id']}: source title drift")
        if row["entry_implementation_status"] == "implemented":
            raise ValueError("control kernels may not claim full entry implementation")
    if data["summary"]["fully_implemented_entries"] != 0 or data["summary"]["fully_bound_forms"] != 0:
        raise ValueError("full coverage is not established")
    print(f"AMD64 string coverage valid: 7 entries, {len(actual_forms)} forms, 0 fully bound")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["generate", "check"])
    args = parser.parse_args()
    if args.command == "generate":
        OUTPUT.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + "\n")
    validate(read(OUTPUT))


if __name__ == "__main__":
    main()
