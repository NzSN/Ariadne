#!/usr/bin/env python3
"""Extract an authoritative AMD reference index and account for encoding rows.

PDF outline destinations define section ownership. Every nonempty line in a
detected mnemonic table is classified; missing/merged cells and unparsed text
remain explicit gaps. Constraint references locate source statements and do not
claim a complete formal encoding/feature legality model. Products stay ignored.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

from amd64_inventory import check as check_xed, fetch as fetch_pins, load_lock as xed_lock, strict_json
from amd64_inventory_xed import canonical, digest
from run_output import run_output

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "tests/bap/fixtures/amd-manuals.lock.json"
LOCK = ROOT / "tests/bap/fixtures/amd64-semantics/manual-inventory.lock.json"
SCHEMA = "ariadne.amd-manual-inventory/v1"
HEADER = re.compile(r"^\s*Mnemonic\b")
STOP = re.compile(r"^(?:Related Instructions?|rFLAGS Affected|Flags Affected|Exceptions|Action|Operation|"
                  r"General-Purpose|System Instruction Reference|Instruction Reference|"
                  r"[0-9]+\s+(?:General-Purpose|System Instruction|Instruction Reference))")
MNEMONIC = re.compile(r"^(?:[A-Z][A-Z0-9]+(?:cc|level)?(?:\s|/|$)|\(None\))")
OPERAND_CONTINUATION = re.compile(r"^(?:imm[0-9]+|reg(?:/mem)?[0-9]+|mem[0-9]+|segReg|[xyz]mm[0-9]*)(?:[,\s]|$)")
OPCODE_START = re.compile(r"^(?:[0-9A-F]{2}(?:\s|$)|[0-9A-F]h|NP\b|REX\b|VEX\b|EVEX\b|XOP\b)")
CONSTRAINTS = {
    "mode": re.compile(r"(?:64.bit|32.bit|16.bit|compatibility|legacy|real|virtual.8086)\s+mode", re.I),
    "prefix": re.compile(r"\b(?:prefix|LOCK|REP(?:E|NE|Z|NZ)?|REX|VEX|XOP|EVEX)\b"),
    "feature": re.compile(r"\b(?:CPUID|Fn[0-9A-Fa-f_]+|feature flag|instruction subset|"
                          r"AVX[A-Z0-9_]*|SSE[A-Z0-9.]*|MMX|AES|PCLMULQDQ|BMI[12]|TBM|FMA4?)\b"),
    "privilege-state": re.compile(r"\b(?:CPL|privileg|CR[0348]|EFER|XCR0|SNP.active|VMPL)"),
}


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def entries_from_outline(outline, chapter_titles):
    chapters = outline["outline"]
    result = []
    for title in chapter_titles:
        matches = [(index, row) for index, row in enumerate(chapters) if row["title"] == title]
        if len(matches) != 1:
            raise ValueError("missing or ambiguous instruction chapter: " + title)
        index, chapter = matches[0]
        end = chapters[index + 1]["pdfPage"] if index + 1 < len(chapters) else outline["pages"] + 1
        children = chapter.get("children", [])
        if not children:
            raise ValueError("instruction chapter has no outline entries")
        starts = sorted({row["pdfPage"] for row in children} | {end})
        for ordinal, row in enumerate(children):
            start = row["pdfPage"]
            if not chapter["pdfPage"] <= start < end:
                raise ValueError("unexpected instruction outline nesting or range")
            result.append(dict(id=f"amd-entry:{len(result):04}", chapter=title,
                               chapterOrdinal=ordinal, title=row["title"], uri=row["uri"],
                               subsections=row.get("children", []),
                               pdfPage=start, pdfEndPage=starts[starts.index(start) + 1] - 1))
    return result


def source_reference(page, line, text):
    return {"pdfPage": page, "line": line, "textSha256": hashlib.sha256(text.encode()).hexdigest()}


def mnemonic_belongs(token, titles):
    names = [name for title in titles for name in re.findall(r"[A-Z][A-Z0-9]*(?:cc|level)?", title)]
    if token == "(None)":
        return True
    return any(token == name
               or (name.endswith("cc") and re.fullmatch(re.escape(name[:-2]) + r"[A-Z]+", token))
               or (name.endswith("level") and re.fullmatch(re.escape(name[:-5]) + r"[A-Z0-9]*", token))
               or token in {name + suffix for suffix in ("B", "W", "D", "Q", "F", "1")}
               for name in names)


def classify_table_line(line, header):
    text = line.strip()
    if not text:
        return "blank", None
    if "Opcode" in header and "Description" in header:
        op, desc = header.index("Opcode"), header.index("Description")
        indentation = len(line) - len(line.lstrip())
        if indentation >= op - 1:
            first = re.split(r"\s{2,}", text)[0]
            encoding = first if indentation < desc - 2 and (OPCODE_START.match(first) or first.startswith("/")) else ""
            return "description-or-encoding-continuation", {"encoding": encoding} if encoding else None
        cells = re.split(r"\s{2,}", text)
        mnemonic = cells[0]
        if MNEMONIC.match(mnemonic):
            candidate = cells[1:2]
            # A vertically merged opcode cell can leave the description as
            # the next nonblank cell. Do not promote that prose to an opcode.
            if candidate and not (OPCODE_START.match(candidate[0]) or candidate[0].startswith("/")):
                candidate = []
            return "row", {"mnemonic": mnemonic, "encodingCells": candidate}
        if OPERAND_CONTINUATION.match(mnemonic):
            return "operand-continuation", {"fragment": mnemonic}
        return "unparsed", None
    if "Encoding" in header:
        cells = re.split(r"\s{2,}", text)
        token = cells[0].split()[0]
        if token in {"VEX", "XOP", "EVEX", "Opcode", "Prefix", "Legacy", "REX", "RXB.map_select", "W.vvvv.L.pp"}:
            return "column-header", None
        if MNEMONIC.match(cells[0]) and len(cells) >= 2:
            # Notes/Description cells are separate prose, not opcode columns.
            encoding = cells[1:2] if "Notes" in header or "Description" in header else cells[1:]
            return "row", {"mnemonic": cells[0], "encodingCells": encoding}
        return "unparsed", None
    return "unparsed", None


def extract(text, outline, chapter_titles):
    pages = text.split("\f")
    if pages[-1].strip() == "":
        pages.pop()
    if len(pages) != outline["pages"]:
        raise ValueError("PDF/text page count differs")
    entries = entries_from_outline(outline, chapter_titles)
    entry_titles = {entry["id"]: entry["title"] for entry in entries}
    tables, rows, gaps, constraints = [], [], [], []
    owners = defaultdict(list)
    for entry in entries:
        for page in range(entry["pdfPage"], entry["pdfEndPage"] + 1):
            owners[page].append(entry["id"])
    for number, entry_ids in sorted(owners.items()):
        lines = pages[number - 1].splitlines()
        for lineno, line in enumerate(lines, 1):
            categories = [name for name, pattern in CONSTRAINTS.items() if pattern.search(line)]
            if categories:
                constraints.append(dict(source_reference(number, lineno, line), entryIds=entry_ids,
                                        categories=categories, sourceText=line.strip()))
            if not HEADER.match(line):
                continue
            table = dict(id=f"amd-table:{len(tables):04}", entryIds=entry_ids,
                         pdfPage=number, headerLine=lineno, header=line.strip(), lines=[])
            if "Opcode" not in line and "Encoding" not in line:
                gaps.append(dict(kind="unrecognized-mnemonic-table-header", table=table["id"]))
            tables.append(table)
            previous_row = None
            for offset in range(lineno, len(lines)):
                value = lines[offset]
                stripped = value.strip()
                if STOP.match(stripped) or HEADER.match(value):
                    break
                kind, row = classify_table_line(value, line)
                if kind == "row" and not mnemonic_belongs(row["mnemonic"].split()[0],
                                                           [entry_titles[key] for key in entry_ids]):
                    kind, row = "unparsed", None
                reference = source_reference(number, offset + 1, value)
                table["lines"].append(dict(reference, classification=kind))
                if kind == "row":
                    row = dict(row, id=f"amd-row:{len(rows):05}", table=table["id"],
                               entryIds=entry_ids, source=reference)
                    rows.append(row)
                    previous_row = row
                    if not row["encodingCells"]:
                        gaps.append(dict(kind="missing-or-merged-encoding-cell", row=row["id"], source=reference))
                    elif not OPCODE_START.match(row["encodingCells"][0]):
                        gaps.append(dict(kind="fragmented-or-unrecognized-encoding-cell", row=row["id"], source=reference))
                elif kind == "operand-continuation":
                    if previous_row is not None:
                        previous_row["mnemonic"] += " " + row["fragment"]
                        previous_row.setdefault("sourceContinuations", []).append(reference)
                    else:
                        gaps.append(dict(kind="operand-continuation-without-row", table=table["id"], source=reference))
                elif kind == "unparsed":
                    gaps.append(dict(kind="unparsed-table-line", table=table["id"],
                                     source=reference, sourceText=stripped))
                elif kind == "description-or-encoding-continuation" and row:
                    gaps.append(dict(kind="encoding-cell-without-mnemonic", table=table["id"],
                                     source=reference, encodingCell=row["encoding"]))
    for entry in entries:
        table_ids = [table["id"] for table in tables if entry["id"] in table["entryIds"]]
        entry["tableIds"] = table_ids
        if not table_ids:
            section = "\n".join(pages[entry["pdfPage"] - 1:entry["pdfEndPage"]])
            alias = re.search(r"This instruction is synonymous with the ([A-Z0-9]+) instruction", section)
            if alias:
                entry["explicitAliasOf"] = alias.group(1)
            else:
                gaps.append(dict(kind="instruction-entry-without-encoding-table", entry=entry["id"]))
    return dict(entries=entries, tables=tables, rows=rows, constraintReferences=constraints, gaps=gaps)


def reconcile(rows, xed):
    by_name = defaultdict(list)
    for item in xed["records"]:
        by_name[item["mnemonic"]].append(item["id"])
    manual_encodings = defaultdict(set)
    for row in rows:
        if row["encodingCells"]:
            manual_encodings[tuple(row["encodingCells"])].add(row["mnemonic"].split()[0])
    result = []
    for row in rows:
        token = row["mnemonic"].split()[0]
        aliases = sorted(name for name in manual_encodings.get(tuple(row["encodingCells"]), [])
                         if name != token and name in by_name)
        result.append(dict(row=row["id"], mnemonicToken=token,
                           exactNameCandidates=by_name.get(token, []),
                           sameEncodingTextNameCandidates=aliases,
                           relation="name-only-candidate" if token in by_name else "unmatched-name",
                           encodingLegalityReconciled=False))
    return result


def counts(content):
    return dict(entries=len(content["entries"]), tables=len(content["tables"]),
                rows=len(content["rows"]),
                tableLines=sum(len(table["lines"]) for table in content["tables"]),
                chapters=dict(sorted(Counter(entry["chapter"] for entry in content["entries"]).items())),
                lineClasses=dict(sorted(Counter(line["classification"] for table in content["tables"]
                                                for line in table["lines"]).items())),
                gaps=dict(sorted(Counter(gap["kind"] for gap in content["gaps"]).items())),
                constraintReferences=len(content["constraintReferences"]))


def validate_output(result, pin):
    fields = {"schema", "publication", "revision", "sourceProvenance", "pdfSha256", "layoutTextSha256", "outlineSha256",
              "scope", "content", "contentSha256", "counts", "xedComparison"}
    if set(result) != fields or result["schema"] != SCHEMA:
        raise ValueError("manual inventory schema")
    for key in ("publication", "revision", "sourceProvenance", "pdfSha256", "layoutTextSha256", "outlineSha256"):
        if result[key] != pin[key]:
            raise ValueError("manual inventory source differs: " + key)
    if (digest(result["content"]) != result["contentSha256"]
            or result["contentSha256"] != pin["contentSha256"]
            or result["counts"] != counts(result["content"])
            or result["counts"] != pin["counts"]
            or digest(result["scope"]) != pin["scopeSha256"]):
        raise ValueError("manual inventory differs from frozen source transcription")
    if result["xedComparison"] is not None:
        if (result["xedComparison"]["xedRecordsSha256"] != pin["xedRecordsSha256"]
                or digest(result["xedComparison"]) != pin["xedComparisonSha256"]):
            raise ValueError("manual/XED candidate comparison changed")


def require_no_gaps(result):
    if result["content"]["gaps"]:
        raise ValueError("source transcription is incomplete: " + json.dumps(result["counts"]["gaps"], sort_keys=True))


def source_for(pin):
    source_lock = strict_json(SOURCES.read_bytes())
    sources = source_lock["sources"] + pin.get("additionalSources", [])
    return next(source for source in sources if source["publication"] == pin["publication"]
                and source["revision"] == pin["revision"])


def generate(pdf_cache, output, pin, xed_path=None, existing_text=None):
    source = source_for(pin)
    pdf = Path(pdf_cache).resolve() / source["filename"]
    if pdf.stat().st_size != source["bytes"] or sha_file(pdf) != source["sha256"]:
        raise ValueError("AMD PDF differs from authoritative source pin")
    output = run_output(output)
    output.mkdir(parents=True, exist_ok=False)
    mutool = shutil.which("mutool")
    if not mutool:
        raise ValueError("mutool is required for authoritative PDF outline destinations")
    with (output / "outline.json").open("wb") as stream:
        subprocess.run([mutool, "run", str(ROOT / "tools/amd64_manual_outline.js"), str(pdf)],
                       stdout=stream, check=True, timeout=60)
    if existing_text:
        text = Path(existing_text).read_text()
    else:
        pdftotext = shutil.which("pdftotext")
        if not pdftotext:
            raise ValueError("pdftotext is required for layout-preserving extraction")
        with (output / "pdftotext.log").open("wb") as log:
            subprocess.run([pdftotext, "-layout", str(pdf), str(output / "layout.txt")],
                           stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)
        text = (output / "layout.txt").read_text()
    outline = strict_json((output / "outline.json").read_bytes())
    content = extract(text, outline, pin["chapters"])
    comparison = None
    if xed_path:
        xed = check_xed(xed_path, xed_lock())
        comparison = dict(xedRecordsSha256=xed["recordsSha256"], rows=reconcile(content["rows"], xed))
    result = dict(schema=SCHEMA, publication=source["publication"], revision=source["revision"],
                  sourceProvenance=pin["sourceProvenance"],
                  pdfSha256=source["sha256"], layoutTextSha256=hashlib.sha256(text.encode()).hexdigest(),
                  outlineSha256=digest(outline), content=content, contentSha256=digest(content),
                  counts=counts(content), xedComparison=comparison, scope={
                      "unit": "PDF instruction-reference entry and physical encoding-table row",
                      "constraints": "Keyword-located source references, not a complete formal legality model",
                      "mergedCells": "Missing opcode cells are retained as gaps; no unchecked fill-down",
                      "comparison": "XED names and identical manual encoding text produce candidates only",
                      "exclusions": "Global encoding rules, appendix maps, concrete byte expansion and semantic validation remain separate obligations",
                  })
    (output / "inventory.json").write_bytes(canonical(result) + b"\n")
    validate_output(result, pin)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=LOCK)
    parser.add_argument("--publication", default="24594")
    commands = parser.add_subparsers(dest="command", required=True)
    fetch_command = commands.add_parser("fetch")
    fetch_command.add_argument("--pdf-cache", type=Path, default=ROOT / "target/amd-manual-inventory")
    extract_command = commands.add_parser("extract")
    extract_command.add_argument("--pdf-cache", type=Path, default=ROOT / "target/amd-manual-inventory")
    extract_command.add_argument("--output", type=Path, required=True)
    extract_command.add_argument("--layout-text", type=Path)
    extract_command.add_argument("--xed-inventory", type=Path)
    check_command = commands.add_parser("check")
    check_command.add_argument("inventory", type=Path)
    check_command.add_argument("--require-no-gaps", action="store_true",
                               help="fail if any table row/cell/header remains unresolved; not an ISA semantics gate")
    args = parser.parse_args(argv)
    lock = strict_json(args.lock.read_bytes())
    if lock["schema"] != "ariadne.amd-manual-inventory-lock/v1":
        raise ValueError("manual inventory lock schema")
    pin = next(item for item in lock["documents"] if item["publication"] == args.publication)
    if args.command == "fetch":
        source = source_for(pin)
        fetch_pins(args.pdf_cache, {"sources": [dict(name=source["publication"], archive=source["filename"],
                   archiveUrl=source["content_url"], bytes=source["bytes"], sha256=source["sha256"])]})
        return 0
    if args.command == "extract":
        result = generate(args.pdf_cache, args.output, pin, args.xed_inventory, args.layout_text)
    else:
        result = strict_json(args.inventory.read_bytes())
        validate_output(result, pin)
        if args.require_no_gaps:
            require_no_gaps(result)
    print(json.dumps(dict(publication=result["publication"], counts=result["counts"],
                          contentSha256=result["contentSha256"], legalEncodingCompleteness="not-established")))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
