#!/usr/bin/env python3
"""Pin-aware source inventory. Extracted rows are review candidates, not support.

Only `fetch` uses the network. PDFs and extracted prose stay outside git.
`extract` needs pdfminer.six; `check` uses only the Python standard library.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from amd64_acceptance import check_ledger

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "Specs" / "AMD64"


def read_json(path: Path):
    return json.loads(path.read_text())


def write_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def verify_pdf(path: Path, source: dict):
    data = path.read_bytes()
    if not data.startswith(b"%PDF-"):
        raise ValueError(f"{path}: not a PDF")
    if len(data) != source["bytes"]:
        raise ValueError(f"{path}: byte length differs from source lock")
    if hashlib.sha256(data).hexdigest() != source["sha256"]:
        raise ValueError(f"{path}: SHA-256 differs from source lock")


def fetch(cache: Path, sources: list[dict]):
    cache.mkdir(parents=True, exist_ok=True)
    for source in sources:
        path = cache / source["filename"]
        if not path.exists():
            request = Request(source["content_url"], headers={"User-Agent": "Ariadne-source-pin/1"})
            with urlopen(request, timeout=120) as response:
                data = response.read()
            # Verify before publishing a cache entry. Never trust a 200 HTML response.
            temporary = path.with_suffix(".download")
            temporary.write_bytes(data)
            try:
                verify_pdf(temporary, source)
                temporary.replace(path)
            finally:
                temporary.unlink(missing_ok=True)
        verify_pdf(path, source)
        print(f"verified {source['publication']} revision {source['revision']}")


def outline(path: Path):
    from pdfminer.pdfdocument import PDFDocument
    from pdfminer.pdfpage import PDFPage
    from pdfminer.pdfparser import PDFParser
    from pdfminer.pdftypes import resolve1

    with path.open("rb") as stream:
        document = PDFDocument(PDFParser(stream))
        pages = list(PDFPage.create_pages(document))
        page_ids = {page.pageid: index + 1 for index, page in enumerate(pages)}
        rows = []
        for level, title, destination, action, _ in document.get_outlines():
            if destination is None:
                destination = resolve1(action)["D"]
            if isinstance(destination, (bytes, str)):
                destination = document.get_dest(destination)
            destination = resolve1(destination)
            if isinstance(destination, dict):
                destination = resolve1(destination["D"])
            rows.append({"level": level, "title": title, "pdf_page": page_ids[destination[0].objid]})
    return rows, len(pages)


def instruction_entries(rows: list[dict]):
    active = False
    entries = []
    for row in rows:
        if row["title"] == "3 General-Purpose Instruction Reference":
            active = True
        elif row["title"] == "4 System Instruction Reference":
            end = row["pdf_page"]
            break
        elif active and row["level"] == 2:
            entries.append(row)
    else:
        raise ValueError("General-purpose chapter boundary was not found")
    if not entries:
        raise ValueError("No general-purpose instruction entries found")
    starts = sorted({row["pdf_page"] for row in entries} | {end})
    for index, row in enumerate(entries, 1):
        row["id"] = f"V3-GP-{index:03}"
        row["pdf_end_page"] = starts[starts.index(row["pdf_page"]) + 1] - 1
    return entries


def form_candidates(path: Path, entries: list[dict]):
    """Extract mnemonic-column candidates, preserving page/coordinate evidence.

    PDF layout does not establish prefix, mode, feature or exception coverage.
    Multi-line cells and unusual tables need review. A source row may describe
    several forms (reg/mem, conditions, encodings); this is NOT a form count.
    """
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTChar, LTTextContainer, LTTextLine

    first = min(entry["pdf_page"] for entry in entries)
    last = max(entry["pdf_end_page"] for entry in entries)
    candidates = []
    for number, page in zip(range(first, last + 1), extract_pages(path, page_numbers=range(first - 1, last))):
        lines = [line for box in page if isinstance(box, LTTextContainer)
                 for line in box if isinstance(line, LTTextLine)]
        headers = [line for line in lines if line.get_text().strip() == "Mnemonic"]
        for header in headers:
            peers = [line for line in lines if abs(line.y0 - header.y0) < 3]
            opcode_header = next((line for line in peers if line.get_text().strip().startswith("Opcode")), None)
            description_header = next((line for line in peers if line.get_text().strip() == "Description"), None)
            encoding_header = next((line for line in peers if line.get_text().strip() == "Encoding"), None)
            if opcode_header is not None:
                opcode_x = opcode_header.x0
                if description_header is not None:
                    description_x = description_header.x0
                else:
                    chars = [char for char in opcode_header if isinstance(char, LTChar)]
                    text = "".join(char.get_text() for char in chars)
                    if "Description" not in text:
                        continue
                    description_x = chars[text.index("Description")].x0
            elif encoding_header is not None:
                # VEX/XOP tables use a centered Mnemonic/Encoding header and
                # several encoding columns instead of an Opcode/Description pair.
                if header.x0 < 100:  # Left-aligned Encoding header, e.g. CRC32.
                    opcode_x = encoding_header.x0
                    description_x = 315
                else:
                    opcode_x = (header.x1 + encoding_header.x0) / 2
                    description_x = 560
            else:
                continue
            stops = [line.y1 for line in lines if line.y1 < header.y0 and line.get_text().strip() in
                     {"Related Instructions", "rFLAGS Affected", "Exceptions", "Mnemonic", "Action"}]
            bottom = max(stops, default=65)
            cells = sorted((line for line in lines if bottom < line.y0 < header.y0
                            and 60 <= line.x0 < opcode_x - 2 and line.x1 < opcode_x + 2),
                           key=lambda line: -line.y0)
            owners = [entry for entry in entries if entry["pdf_page"] <= number <= entry["pdf_end_page"]]
            mnemonics = {name for entry in owners for name in re.findall(r"\b[A-Z][A-Za-z0-9]*\b", entry["title"])}
            if any(entry["title"] == "RET (Far)" for entry in owners):
                mnemonics.add("RETF")
            for line in cells:
                mnemonic = " ".join(line.get_text().split())
                token = mnemonic.split()[0] if mnemonic else ""
                matches = token in mnemonics or any(
                    name.endswith("cc") and re.fullmatch(name[:-2] + r"[A-Z]+", token)
                    or name.endswith("level") and re.fullmatch(name[:-5] + r"[A-Z0-9]+", token)
                    for name in mnemonics)
                if not matches:
                    continue
                opcodes = sorted((other for other in lines if abs(other.y0 - line.y0) < 6
                                  and opcode_x - 2 <= other.x0 < description_x - 2),
                                 key=lambda other: other.x0)
                candidates.append({
                    "id": f"V3-ROW-{len(candidates) + 1:04}",
                    "entry_ids": [entry["id"] for entry in entries
                                  if entry["pdf_page"] <= number <= entry["pdf_end_page"]],
                    "pdf_page": number,
                    "y_from_bottom": round(line.y0, 2),
                    "mnemonic_candidate": mnemonic,
                    "opcode_candidate": " ".join(" ".join(other.get_text().split()) for other in opcodes),
                    "review": "pending",
                })
    return candidates


def extract(cache: Path, sources: list[dict], destination: Path):
    import pdfminer
    from pdfminer.high_level import extract_text

    destination.mkdir(parents=True, exist_ok=True)
    all_sections = []
    instructions = None
    for source in sources:
        path = cache / source["filename"]
        verify_pdf(path, source)
        title = extract_text(path, page_numbers=[0])
        if source["publication"] not in title or source["revision"] not in title:
            raise ValueError(f"{path}: publication/revision missing from cover")
        rows, pages = outline(path)
        if pages != source["pdf_pages"]:
            raise ValueError(f"{path}: page count differs from lock")
        for row in rows:
            if re.match(r"^(?:[0-9]+(?:\.[0-9]+)*|Appendix [A-Z]|[A-Z]\.[0-9]+)\s", row["title"]):
                all_sections.append({
                    "id": f"V{source['volume']}-SECTION-{len(all_sections) + 1:04}",
                    "volume": source["volume"],
                    "title": row["title"],
                    "pdf_page": row["pdf_page"],
                    "level": row["level"],
                })
        if source["volume"] == 3:
            entries = instruction_entries(rows)
            candidates = form_candidates(path, entries)
            for entry in entries:
                entry["candidate_ids"] = [candidate["id"] for candidate in candidates if entry["id"] in candidate["entry_ids"]]
            instructions = {"entries": entries, "table_row_candidates": candidates}
        print(f"extracted Volume {source['volume']}: {pages} pages, {len(rows)} bookmarks", flush=True)
    common = {
        "schema_version": 1,
        "extractor": "tools/amd64_inventory.py",
        "pdfminer_six_version": pdfminer.__version__,
        "source_sha256": {str(source["volume"]): source["sha256"] for source in sources},
    }
    write_json(destination / "source-sections.json", {**common, "sections": all_sections})
    write_json(destination / "instruction-source.json", {**common, **instructions})
    print(f"extracted {len(instructions['entries'])} instruction entries and "
          f"{len(instructions['table_row_candidates'])} table-row candidates; all require semantic review")


def check_assignments(assignments: dict, entries: dict):
    """Dispatch integrity is independent of semantic implementation acceptance."""
    rows = assignments["instruction_entries"]
    if len(rows) != len(entries) or {row["entry_id"] for row in rows} != set(entries):
        raise ValueError("Assignments must cover every instruction entry exactly once")
    owners = {
        "X2": "/root/data_execution", "D2": "/root/external_io",
        "C3": "/root/control_stack", "C4": "/root/external_io",
        "D1": "/root/memory_atomic",
    }
    for row in rows:
        if row["role"] != "general-purpose-gpt":
            raise ValueError("Assigned role differs from the user-requested general-purpose-gpt")
        if owners.get(row["execution_task"]) != row["execution_owner"]:
            raise ValueError("Execution ownership differs from the agreed workstream")
        if row["form_review_owner"] != "/root":
            raise ValueError("Instruction form review must retain its assigned owner")
        if row["title"] != entries[row["entry_id"]]["title"]:
            raise ValueError("Assignment title differs from pinned source entry")


def check(sources: list[dict], cache: Path | None, require_complete: bool = False):
    expected = {str(source["volume"]): source["sha256"] for source in sources}
    for source in sources:
        if not re.fullmatch(r"[0-9a-f]{64}", source["sha256"]):
            raise ValueError("Invalid source SHA-256")
        if cache is not None:
            verify_pdf(cache / source["filename"], source)
    inst = read_json(DATA / "instruction-source.json")
    sections = read_json(DATA / "source-sections.json")
    for data in [inst, sections]:
        if data["source_sha256"] != expected:
            raise ValueError("Inventory source hashes differ from lock")
    page_counts = {source["volume"]: source["pdf_pages"] for source in sources}
    if len({section["id"] for section in sections["sections"]}) != len(sections["sections"]):
        raise ValueError("Duplicate source section IDs")
    for section in sections["sections"]:
        if not 1 <= section["pdf_page"] <= page_counts[section["volume"]]:
            raise ValueError("Section outside source PDF")
    for source in sources:
        if sum(section["volume"] == source["volume"] for section in sections["sections"]) != source["numbered_sections"]:
            raise ValueError("Numbered source section count differs from reviewed lock")
    entries = {entry["id"]: entry for entry in inst["entries"]}
    rows = {row["id"]: row for row in inst["table_row_candidates"]}
    if len(entries) != len(inst["entries"]) or len(rows) != len(inst["table_row_candidates"]):
        raise ValueError("Duplicate source IDs")
    volume3 = next(source for source in sources if source["volume"] == 3)
    if len(entries) != volume3["general_purpose_reference_entries"]:
        raise ValueError("Instruction reference entry count differs from reviewed lock")
    for entry in entries.values():
        if not 1 <= entry["pdf_page"] <= entry["pdf_end_page"] <= volume3["pdf_pages"]:
            raise ValueError("Instruction reference outside source PDF")
    assignment_path = DATA / "work-assignments.json"
    if assignment_path.exists():
        check_assignments(read_json(assignment_path), entries)
    coverage = read_json(DATA / "coverage.json")
    entry_reviews = coverage["instruction_entries"]
    if {entry["id"] for entry in entry_reviews} != set(entries) or len(entry_reviews) != len(entries):
        raise ValueError("Coverage must account for every source entry exactly once")
    section_ids = {section["id"] for section in sections["sections"] if section["volume"] == 1}
    if ({section["id"] for section in coverage["volume1_sections"]} != section_ids
            or len(coverage["volume1_sections"]) != len(section_ids)):
        raise ValueError("Coverage must account for every Volume 1 section")
    accepted_entries = 0
    complete = False
    if coverage["schema_version"] == 1:
        for section in coverage["volume1_sections"]:
            if section["status"] != "pending-state-review":
                raise ValueError("Closing state sections requires field-level obligations and evidence")
        for entry in entry_reviews:
            if entry["status"] != "pending-form-review":
                raise ValueError("Closing entries requires the semantic-case schema and evidence gate")
    elif coverage["schema_version"] == 2:
        forms_path, fields_path = DATA / "forms.json", DATA / "state-fields.json"
        result = check_ledger(coverage, ROOT,
                              read_json(forms_path) if forms_path.exists() else None,
                              read_json(fields_path) if fields_path.exists() else None)
        accepted_entries = result["complete_instruction_entries"]
        complete = result["complete"]
    else:
        raise ValueError("Unknown coverage ledger schema")
    for entry in entries.values():
        for candidate in entry["candidate_ids"]:
            if candidate not in rows or entry["id"] not in rows[candidate]["entry_ids"]:
                raise ValueError("Broken candidate reference")
    for row in rows.values():
        if not row["entry_ids"] or row["review"] != "pending":
            raise ValueError("Unowned or uncertified candidate")
        for entry_id in row["entry_ids"]:
            if entry_id not in entries or row["id"] not in entries[entry_id]["candidate_ids"]:
                raise ValueError("Broken reverse candidate reference")
            entry = entries[entry_id]
            if not entry["pdf_page"] <= row["pdf_page"] <= entry["pdf_end_page"]:
                raise ValueError("Candidate outside instruction reference pages")
    print(f"inventory integrity OK: {len(entries)} entries, {len(rows)} row candidates, "
          f"{len(section_ids)} Volume 1 sections; full-manual roadmap accepted entries: {accepted_entries}")
    no_rows = [entry["title"] for entry in entries.values() if not entry["candidate_ids"]]
    print(f"entries without table candidates (review required): {no_rows}")
    print(f"row candidates without same-line opcode (review required): "
          f"{sum(not row['opcode_candidate'] for row in rows.values())}")
    if require_complete and not complete:
        raise ValueError("Coverage is pending: source inventory is not completed ISA semantics")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["fetch", "extract", "check"])
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--output", type=Path, help="Separate extraction directory for reproducibility checks")
    parser.add_argument("--require-complete", action="store_true", help="Fail if architectural coverage remains open")
    args = parser.parse_args()
    sources = read_json(DATA / "manuals.lock.json")["sources"]
    try:
        if args.command == "check":
            check(sources, args.cache, args.require_complete)
        else:
            if args.cache is None:
                parser.error("fetch/extract require --cache")
            if args.command == "fetch":
                fetch(args.cache, sources)
            else:
                extract(args.cache, sources, args.output or DATA)
    except (ValueError, OSError, KeyError) as error:
        print(f"inventory error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
