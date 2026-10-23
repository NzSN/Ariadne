#!/usr/bin/env python3
"""Reconstruct source cells and account for every historical AMD manual gap.

This v2 candidate consumes fresh word-box/outline products. It never changes the
historical v1 transcription or treats backlog recovery as source completeness.
Coordinates are PDF points with a top-left origin; pages are one based. Word
boxes are retained, not falsely described as original PDF glyph outlines.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import io
import itertools
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

from amd64_inventory_xed import canonical, digest
from amd64_manual_inventory import LOCK, entries_from_outline, mnemonic_belongs, sha_file
from amd64_source_corpus import validate_lock as validate_corpus_lock
from run_output import run_output

SCHEMA = "ariadne.amd-manual-geometry/v2"
RULES = "ariadne.amd-geometry-rules/v2"
STOP = re.compile(r"^(?:Related Instructions?|rFLAGS Affected|Flags Affected|Exceptions|Action|Operation)$")
CODE_START = re.compile(r"^(?:[0-9A-F]{2}(?:\b|\+)|NP\b|REX\b|VEX\b|EVEX\b|XOP\b)")
CODE_TOKEN = re.compile(r"^(?:[0-9A-F]{2}(?:\+[ri])?|/[0-7r]|[ic][bwdq]|[0-9A-F]{2}h|"
                        r"(?:REX|VEX|EVEX|XOP)(?:\.[A-Za-z0-9.]+)?|\+|[ri])$")
FIELD = re.compile(r"^(?:[RXBWrxbxvV0-9][A-Za-z0-9_.'/+\-]*|/r)$")
OPERAND = re.compile(r"^(?:[xyz]mm[0-9]*|mmx?[0-9]*|imm[0-9]*|reg(?:/mem)?[0-9]*|mem[0-9]*|"
                     r"segReg|\{[a-z0-9]+\})(?:[,/\s{]|$)")
COLUMN_HEADERS = {"Opcode", "VEX", "XOP", "EVEX", "Prefix", "Legacy", "REX",
                  "RXB.map_select", "W.vvvv.L.pp", "R'X'B'R.00mm", "W.vvvv.1.pp",
                  "z.L'L.b.V'.aaa", "P0", "P1", "P2"}


def norm(text):
    return "".join(text.split())


def rectangle(cells):
    return [round(f(c["rect"][i] for c in cells), 6)
            for i, f in enumerate((min, min, max, max))]


def local(tag):
    return tag.rsplit("}", 1)[-1]


def read_geometry(path):
    """Read *every* XML page/line/word, checking finite, nonempty geometry."""
    import math
    # Poppler faithfully emits some PDF control-code glyphs as XML-invalid
    # Unicode scalars. Escape and restore them; never delete a word/line.
    raw = Path(path).read_text(encoding="utf-8")
    if any(0xF0000 <= ord(char) < 0xF0020 for char in raw):
        raise ValueError("reserved source-control escape scalar collision")
    xml = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]",
                 lambda match: chr(0xF0000 + ord(match[0])), raw)
    pages = []
    for event, page in ET.iterparse(io.StringIO(xml), events=("end",)):
        if local(page.tag) != "page":
            continue
        number = len(pages) + 1
        size = [float(page.attrib[key]) for key in ("width", "height")]
        if any(not math.isfinite(value) or value <= 0 for value in size):
            raise ValueError("invalid PDF page geometry")
        cells, word_ordinal = [], 0
        for line in page.iter():
            if local(line.tag) != "line":
                continue
            words = []
            start = word_ordinal
            for word in line:
                if local(word.tag) != "word":
                    continue
                box = [float(word.attrib[key]) for key in ("xMin", "yMin", "xMax", "yMax")]
                if (not word.text or any(not math.isfinite(value) for value in box)
                        or not (0 <= box[0] < box[2] <= size[0] + 1
                                and 0 <= box[1] < box[3] <= size[1] + 1)):
                    raise ValueError("invalid source word geometry")
                restored = "".join(chr(ord(char) - 0xF0000) if 0xF0000 <= ord(char) < 0xF0020 else char
                                   for char in word.text)
                words.append({"text": restored, "rect": box})
                word_ordinal += 1
            if not words:
                continue
            text = " ".join(word["text"] for word in words)
            cells.append(dict(id=f"pdf:{number}:cell:{len(cells)}", pdfPage=number,
                              rect=rectangle(words), wordSpan=[start, word_ordinal],
                              wordBoxesSha256=digest(words), unicodeSha256=hashlib.sha256(text.encode()).hexdigest(),
                              text=text, wordBoxes=words, glyphSpan=None,
                              glyphEvidence="not-extracted: source is Unicode word boxes"))
        pages.append(dict(pdfPage=number, size=size, wordCount=word_ordinal, cells=cells))
        page.clear()
    if not pages:
        raise ValueError("empty PDF word geometry")
    return pages


def physical_lines(cells):
    """Join cell lines sharing a baseline without joining neighboring text rows."""
    groups = []
    for cell in sorted(cells, key=lambda item: (item["rect"][1], item["rect"][0], item["id"])):
        choices = [group for group in groups[-5:]
                   if abs(group["y"] - cell["rect"][1]) <= 1.2
                   and abs(group["height"] - (cell["rect"][3] - cell["rect"][1])) <= 3]
        if len(choices) > 1:
            raise ValueError("ambiguous geometric baseline")
        if choices:
            group = choices[0]
            # Overlap/overprint does not establish two independent cells.
            if any(min(old["rect"][2], cell["rect"][2]) - max(old["rect"][0], cell["rect"][0]) > 1
                   for old in group["cells"]):
                group["ambiguous"] = True
            group["cells"].append(cell)
        else:
            groups.append(dict(y=cell["rect"][1], height=cell["rect"][3] - cell["rect"][1],
                               cells=[cell], ambiguous=False))
    for group in groups:
        group["cells"].sort(key=lambda item: (item["rect"][0], item["id"]))
        group["text"] = " ".join(cell["text"] for cell in group["cells"])
        group["rect"] = rectangle(group["cells"])
    return sorted(groups, key=lambda group: group["y"])


def exact_line(groups, text):
    matches = [group for group in groups if norm(group["text"]) == norm(text)]
    return matches[0] if len(matches) == 1 and not matches[0]["ambiguous"] else None


def exact_source_line(groups, lines, index):
    """Disambiguate repeated text with occurrence order and source neighbors.

    Both the layout and geometry must contain exactly the same number of copies;
    unique adjacent source anchors must bracket the selected physical line.
    """
    text = norm(lines[index])
    matches = [group for group in groups if norm(group["text"]) == text]
    positions = [number for number, line in enumerate(lines) if norm(line) == text]
    if text and not matches and len(positions) == 1:
        return staggered_source_line(groups, lines[index])
    if not text or not matches or len(matches) != len(positions):
        return None
    if len(matches) == 1:
        return matches[0] if not matches[0]["ambiguous"] else None
    candidate = matches[positions.index(index)]
    if candidate["ambiguous"]:
        return None
    anchors = []
    for indices in (range(index - 1, -1, -1), range(index + 1, len(lines))):
        anchor = next((found for number in indices if norm(lines[number]) != text
                       and (found := exact_line(groups, lines[number])) is not None), None)
        anchors.append(anchor)
    if (anchors[0] is None or anchors[1] is None
            or not anchors[0]["y"] < candidate["y"] < anchors[1]["y"]):
        return None
    return candidate


def staggered_source_line(groups, line):
    """Match layout columns whose source baselines are staggered by five points.

    Poppler's layout output sometimes puts a vertically centered mnemonic and
    an adjacent description on the same text line. Every column must match a
    complete, non-overprinted source cell, in order, with one unique geometric
    assignment. This does not relax ownership or infer an absent encoding.
    """
    columns = re.split(r"\s{2,}", line.strip())
    if len(columns) < 2:
        return None
    choices = [[cell for group in groups if not group["ambiguous"] for cell in group["cells"]
                if norm(cell["text"]) == norm(column)] for column in columns]
    if any(not options for options in choices):
        return None
    size = 1
    for options in choices:
        size *= len(options)
    if size > 128:
        return None
    candidates = []
    for cells in itertools.product(*choices):
        if (max(cell["rect"][1] for cell in cells) - min(cell["rect"][1] for cell in cells) <= 6
                and all(left["rect"][2] + 1 < right["rect"][0] for left, right in zip(cells, cells[1:]))):
            candidates.append(cells)
    if len(candidates) != 1:
        return None
    cells = list(candidates[0])
    box = rectangle(cells)
    return dict(text=" ".join(cell["text"] for cell in cells), cells=cells,
                y=box[1], height=box[3] - box[1], rect=box, ambiguous=False)


def source_ids(group):
    return [cell["id"] for cell in group["cells"]]


def encoding_cell(cell):
    words = cell["text"].split()
    return bool(words and CODE_START.match(words[0]) and all(CODE_TOKEN.fullmatch(word) for word in words))


def centered_operand_encoding(table, table_rows, body, header, left):
    """Bind a centered opcode only inside one two-line mnemonic/operand cell.

    A pair of distinct mnemonic heads can never share this rule. The opcode must
    be at the geometric midpoint of one head and its adjacent operand line,
    under the explicit Opcode column and before Description.
    """
    opcode = [cell for cell in header["cells"] if cell["text"] == "Opcode"]
    description = [cell for cell in header["cells"] if cell["text"] == "Description"]
    if len(opcode) != 1 or len(description) != 1:
        return
    opcode_left, description_left = opcode[0]["rect"][0], description[0]["rect"][0]
    for row in table_rows:
        if row["encodingCells"]:
            continue
        head = next(cell for group in body for cell in group["cells"] if cell["id"] in row["headCells"])
        next_left = next((group for group in body if group["y"] > head["rect"][1] + 1.2
                          and any(-2 <= cell["rect"][0] - left <= 24 for cell in group["cells"])), None)
        if next_left is None or next_left["ambiguous"]:
            continue
        operands = [cell for cell in next_left["cells"] if -2 <= cell["rect"][0] - left <= 24]
        if (len(operands) != 1 or not OPERAND.match(operands[0]["text"])
                or not 0 < operands[0]["rect"][1] - head["rect"][1] <= 12
                or max(head["rect"][2], operands[0]["rect"][2]) >= opcode_left - 2):
            continue
        operand = operands[0]
        band = [group for group in body if head["rect"][1] - 1.2 <= group["y"] <= operand["rect"][1] + 1.2]
        if any(group["ambiguous"] for group in band):
            continue
        middle = (head["rect"][1] + operand["rect"][1]) / 2
        enc = [cell for group in band for cell in group["cells"]
               if opcode_left - 2 <= cell["rect"][0] < description_left - 2]
        if (len(enc) != 1 or not encoding_cell(enc[0])
                or abs(enc[0]["rect"][1] - middle) > 1.2
                or enc[0]["rect"][2] >= description_left - 2):
            continue
        allowed_left = {head["id"], operand["id"], enc[0]["id"]}
        if any(cell["id"] not in allowed_left and cell["rect"][0] < description_left - 2
               for group in band for cell in group["cells"]):
            continue
        row.update(encodingCells=[enc[0]["id"]], status="explicit-centered-operand-encoding-row",
                   centeredEncodingCells=sorted(allowed_left), descriptionColumnLeft=description_left)
        row["operandContinuations"].append(dict(cells=[operand["id"]],
            rule="single-mnemonic-centered-opcode-operand/v2", sourceLineCells=source_ids(next_left)))
        row["rect"][2] = max(row["rect"][2], enc[0]["rect"][2])
        row["rect"][3] = max(row["rect"][3], operand["rect"][3])


def diagram_regions(table, table_rows, body, entries):
    """Locate register-bit diagrams with their literal, source-owned EPS labels.

    This classifies non-encoding material only. Diagram operations and their
    semantic constraints remain unparsed source obligations.
    """
    labels = re.compile(r"(?:[xyz]mm|mmx?|reg|mem|imm)[0-9]*(?:/(?:[xyz]mm|mmx?|reg|mem|imm)[0-9]*)*")
    regions = []
    last_row = max((row["rect"][3] for row in table_rows), default=float("inf"))
    for end_index, end in enumerate(body):
        if end["ambiguous"] or len(end["cells"]) != 1:
            continue
        match = re.fullmatch(r"([A-Za-z0-9]+)(?:[-_][A-Za-z0-9_-]+)?\.eps", end["text"])
        if match is None:
            continue
        owners = [key for key in table["entryIds"] if mnemonic_belongs(match[1].upper(), [entries[key]["title"]])]
        if len(owners) != 1:
            continue
        starts = []
        for index, group in enumerate(body[:end_index]):
            if (group["ambiguous"] or group["y"] <= last_row + 8 or end["y"] - group["y"] > 280
                    or not all(labels.fullmatch(cell["text"]) for cell in group["cells"])):
                continue
            nearby = body[index + 1:min(index + 4, end_index)]
            bits = [item for item in nearby if not item["ambiguous"] and len(item["text"].split()) >= 4
                    and all(word.isdecimal() and int(word) <= 512 for word in item["text"].split())]
            if bits:
                starts.append((index, group))
        if len(starts) != 1:
            continue
        start_index, start = starts[0]
        span = body[start_index:end_index + 1]
        if any(group["ambiguous"] or any(cell["text"] in {"Mnemonic", "Opcode", "Encoding"}
               or re.match(r"^(?:Notes?|Footnotes?):", cell["text"])
               or (encoding_cell(cell) and not all(word.isdecimal() for word in cell["text"].split()))
               or mnemonic_belongs(cell["text"].split()[0], [entries[owners[0]]["title"]])
               for cell in group["cells"]) for group in span):
            continue
        regions.append(dict(kind="source-owned-register-bit-diagram", entryId=owners[0],
                            cells=[key for group in span for key in source_ids(group)],
                            anchorCells=source_ids(start) + source_ids(end),
                            rect=rectangle([cell for group in span for cell in group["cells"]]),
                            constraintsParsed=False, rule="register-bit-diagram-with-owned-eps-label/v2"))
    return regions


def wrapped_3dnow_encoding(table_rows, body, header, left):
    """Join an explicit 0F 0F /r and trailing byte within one source row.

    The AMD tables wrap this encoding across two baselines. Recognize only this
    literal shape in a table with exactly one mnemonic head; no shared opcode
    or absent byte is inferred.
    """
    opcode = [cell for cell in header["cells"] if cell["text"] == "Opcode"]
    description = [cell for cell in header["cells"] if cell["text"] == "Description"]
    if len(table_rows) != 1 or len(opcode) != 1 or len(description) != 1:
        return
    row = table_rows[0]
    head = next(cell for group in body for cell in group["cells"] if cell["id"] in row["headCells"])
    opcode_left, description_left = opcode[0]["rect"][0], description[0]["rect"][0]
    nearby = [group for group in body if abs(group["y"] - head["rect"][1]) <= 12]
    if any(group["ambiguous"] for group in nearby):
        return
    enc = [cell for group in nearby for cell in group["cells"]
           if opcode_left - 2 <= cell["rect"][0] < description_left - 2]
    if (len(enc) != 2 or enc[0]["text"] != "0F 0F /r" or not re.fullmatch(r"[0-9A-F]{2}", enc[1]["text"])
            or abs(enc[0]["rect"][0] - enc[1]["rect"][0]) > 1.2
            or not 8 <= enc[1]["rect"][1] - enc[0]["rect"][1] <= 12
            or any(cell["rect"][2] >= description_left - 2 for cell in enc)):
        return
    others = [cell for group in nearby for cell in group["cells"]
              if cell["rect"][0] < opcode_left - 2 and cell["id"] not in row["headCells"]]
    operand = None
    if not others:
        if abs(head["rect"][1] - (enc[0]["rect"][1] + enc[1]["rect"][1]) / 2) > 1.2:
            return
    elif len(others) == 1:
        operand = others[0]
        if (not OPERAND.match(operand["text"]) or not -2 <= operand["rect"][0] - left <= 24
                or abs(head["rect"][1] - enc[0]["rect"][1]) > 1.2
                or abs(operand["rect"][1] - enc[1]["rect"][1]) > 1.2):
            return
    else:
        return
    if max(cell["rect"][2] for cell in [head] + others) >= opcode_left - 2:
        return
    bound = [head] + enc + others
    row.update(encodingCells=[cell["id"] for cell in enc], status="explicit-wrapped-3dnow-encoding-row",
               wrappedEncodingCells=[cell["id"] for cell in bound], descriptionColumnLeft=description_left)
    row["rect"][1] = min(row["rect"][1], enc[0]["rect"][1])
    row["rect"][2] = max(row["rect"][2], max(cell["rect"][2] for cell in bound))
    row["rect"][3] = max(cell["rect"][3] for cell in bound)
    if operand:
        group = next(group for group in nearby if operand in group["cells"])
        row["operandContinuations"].append(dict(cells=[operand["id"]],
            rule="single-mnemonic-wrapped-3dnow-encoding/v2", sourceLineCells=source_ids(group)))


def table_geometry(baseline, layout_pages, pages):
    """Recognize only explicitly owned rows and geometric operand continuations.

    No opcode fill-down is implemented. A missing cell is an unresolved source
    obligation even when the preceding/following row looks similar.
    """
    entries = {entry["id"]: entry for entry in baseline["entries"]}
    groups_by_page = {page["pdfPage"]: physical_lines(page["cells"]) for page in pages}
    tables, rows = [], []
    for table in baseline["tables"]:
        page = table["pdfPage"]
        groups = groups_by_page.get(page, [])
        source_lines = layout_pages[page - 1].splitlines()
        if not 1 <= table["headerLine"] <= len(source_lines):
            raise ValueError("historical header source address outside page")
        header = exact_source_line(groups, source_lines, table["headerLine"] - 1)
        result = dict(id=table["id"], pdfPage=page, entryIds=table["entryIds"],
                      headerCells=source_ids(header) if header else [], rows=[],
                      status="unresolved-header-geometry", continuations=[])
        tables.append(result)
        if header is None:
            continue
        mnemonic_headers = [cell for cell in header["cells"] if cell["text"] == "Mnemonic"]
        if len(mnemonic_headers) != 1:
            continue
        left = mnemonic_headers[0]["rect"][0]
        stop = next((group["y"] for group in groups if group["y"] > header["y"] + 2
                     and (any(cell["text"] == "Mnemonic" for cell in group["cells"])
                          or STOP.fullmatch(group["text"].strip()))), float("inf"))
        body = [group for group in groups if header["y"] + 2 < group["y"] < stop]
        result["rect"] = [header["rect"][0], header["rect"][1], header["rect"][2],
                          max((group["rect"][3] for group in body), default=header["rect"][3])]
        has_opcode = any(cell["text"] == "Opcode" for cell in header["cells"])
        has_encoding = any(cell["text"] == "Encoding" for cell in header["cells"])
        if not (has_opcode or has_encoding):
            continue
        subheaders = [group for group in body[:3] if not group["ambiguous"]
                      and any(word["text"] in COLUMN_HEADERS for cell in group["cells"]
                              for word in cell.get("wordBoxes", [cell]))
                      and not any(mnemonic_belongs(cell["text"].split()[0],
                                                  [entries[key]["title"] for key in table["entryIds"]])
                                  for cell in group["cells"] if abs(cell["rect"][0] - left) < 8)]
        result.update(status="located-header-and-columns", columnHeaderCells=[key for group in subheaders
                                                                              for key in source_ids(group)])
        prior = None
        for group in body:
            if group["ambiguous"] or group in subheaders:
                continue
            left_cells = [cell for cell in group["cells"] if -2 <= cell["rect"][0] - left <= 24]
            if len(left_cells) != 1:
                continue
            cell = left_cells[0]
            token = cell["text"].split()[0]
            owners = [key for key in table["entryIds"] if mnemonic_belongs(token, [entries[key]["title"]])]
            if len(owners) == 1:
                right = [item for item in group["cells"] if item["rect"][0] > cell["rect"][2] + 1]
                enc = [item for item in right if encoding_cell(item)]
                # Split VEX/EVEX fields are accepted only with explicit column
                # headers and a byte-bearing first cell on this exact row.
                if has_encoding and subheaders and enc:
                    labels = [word for group in subheaders for header_cell in group["cells"]
                              for word in header_cell.get("wordBoxes", [header_cell])]
                    encoding_labels = [word for word in labels if word["text"] in COLUMN_HEADERS
                                       or word["text"].startswith(("RXB", "W.vvvv", "z.L"))]
                    if encoding_labels:
                        first = min(word["rect"][0] for word in encoding_labels) - 12
                        notes = [word["rect"][0] for word in labels if word["text"] in {"Notes", "Description"}]
                        last = min(notes) - 3 if notes else float("inf")
                        enc = [item for item in right if first <= item["rect"][0] < last]
                row = dict(id=f"geometry-row:{page}:{len(rows)}", table=table["id"], pdfPage=page,
                           entryId=owners[0], headCells=[cell["id"]], encodingCells=[item["id"] for item in enc],
                           sourceLineCells=source_ids(group), operandContinuations=[],
                           mnemonic=cell["text"], rect=group["rect"],
                           status="explicit-encoding-row" if enc else "unresolved-missing-or-merged-cell")
                rows.append(row)
                result["rows"].append(row["id"])
                prior = row
            elif (not owners and prior and OPERAND.match(cell["text"])
                  and len(group["cells"]) == 1 and prior["encodingCells"]
                  and 0 < group["y"] - prior["rect"][3] + group["height"] <= 18):
                prior["operandContinuations"].append(dict(cells=[cell["id"]],
                                                         rule="same-column-neighbor-owned-operand/v2",
                                                         sourceLineCells=source_ids(group)))
                prior["rect"][3] = max(prior["rect"][3], group["rect"][3])
            else:
                # An orphan/unknown mnemonic-column line breaks continuity.
                prior = None
        table_rows = [row for row in rows if row["table"] == table["id"]]
        centered_operand_encoding(table, table_rows, body, header, left)
        wrapped_3dnow_encoding(table_rows, body, header, left)
        result["materialRegions"] = diagram_regions(table, table_rows, body, entries)
    # A repeated header on an adjacent page is a candidate only. An explicit
    # continued marker and a unique common source owner are required to link it.
    for current, following in zip(tables, tables[1:]):
        if following["pdfPage"] != current["pdfPage"] + 1:
            continue
        owners = sorted(set(current["entryIds"]) & set(following["entryIds"]))
        if not owners:
            continue
        current["continuations"].append(dict(table=following["id"], entryIds=owners,
            status="unresolved: repeated ownership does not establish table continuation"))
    return tables, rows, groups_by_page


def old_gap_id(publication, ordinal, gap):
    return f"amd-gap:{publication}:" + digest(dict(ordinal=ordinal, gap=gap))


def dispositions(publication, baseline, layout_pages, tables, rows, groups_by_page):
    old_tables = {item["id"]: item for item in baseline["tables"]}
    old_rows = {item["id"]: item for item in baseline["rows"]}
    table_map = {item["id"]: item for item in tables}
    result = []
    for ordinal, gap in enumerate(baseline["gaps"]):
        row = old_rows.get(gap.get("row"))
        table_id = gap.get("table") or (row or {}).get("table")
        table = old_tables.get(table_id)
        source = gap.get("source")
        if source is None and table:
            text = layout_pages[table["pdfPage"] - 1].splitlines()[table["headerLine"] - 1]
            source = dict(pdfPage=table["pdfPage"], line=table["headerLine"],
                          textSha256=hashlib.sha256(text.encode()).hexdigest())
        record = dict(oldGapId=old_gap_id(publication, ordinal, gap), ordinal=ordinal,
                      originalGap=gap, disposition="unresolved", cells=[], rule="no-unique-source-backed-resolution/v2",
                      rationale="No uniquely owned explicit encoding/operand/header geometry proves this obligation.")
        result.append(record)
        if source is None:
            continue
        page, line = source["pdfPage"], source["line"]
        lines = layout_pages[page - 1].splitlines()
        if not 1 <= line <= len(lines) or hashlib.sha256(lines[line - 1].encode()).hexdigest() != source["textSha256"]:
            raise ValueError("historical gap source/line digest differs")
        record["legacySource"] = source
        group = exact_source_line(groups_by_page.get(page, []), lines, line - 1)
        if group is None:
            record["rationale"] = "Historical source text has no unique, non-overprinted physical word-box line."
            continue
        ids = set(source_ids(group))
        record["cells"] = sorted(ids)
        candidates = [item for item in rows if item["table"] == table_id
                      and ids == set(item["sourceLineCells"]) and item["encodingCells"]]
        centered = [item for item in rows if item["table"] == table_id and item.get("centeredEncodingCells")
                    and ids & set(item["centeredEncodingCells"])
                    and all(cell["id"] in item["centeredEncodingCells"]
                            or cell["rect"][0] >= item["descriptionColumnLeft"] - 2 for cell in group["cells"])]
        wrapped = [item for item in rows if item["table"] == table_id and item.get("wrappedEncodingCells")
                   and ids & set(item["wrappedEncodingCells"])
                   and all(cell["id"] in item["wrappedEncodingCells"]
                           or cell["rect"][0] >= item["descriptionColumnLeft"] - 2 for cell in group["cells"])]
        continued = [(item, fragment) for item in rows if item["table"] == table_id
                     for fragment in item["operandContinuations"] if ids == set(fragment["sourceLineCells"])]
        parsed_table = table_map.get(table_id, {})
        headers = set(parsed_table.get("headerCells", [])) | set(parsed_table.get("columnHeaderCells", []))
        materials = [region for region in parsed_table.get("materialRegions", []) if ids <= set(region["cells"])]
        if len(wrapped) == 1:
            item = wrapped[0]
            record.update(disposition="justified-continuation", row=item["id"], entryId=item["entryId"],
                          cells=sorted(ids | set(item["wrappedEncodingCells"]) | set(parsed_table["headerCells"])),
                          rule="single-mnemonic-wrapped-3dnow-encoding/v2",
                          rationale="One source-owned mnemonic is bound to both explicit 0F 0F /r and trailing byte cells in the same Opcode column.")
        elif len(centered) == 1:
            item = centered[0]
            record.update(disposition="justified-continuation", row=item["id"], entryId=item["entryId"],
                          cells=sorted(ids | set(item["centeredEncodingCells"]) | set(parsed_table["headerCells"])),
                          rule="single-mnemonic-centered-opcode-operand/v2",
                          rationale="A unique mnemonic/operand pair brackets its explicit centered opcode in the named table columns.")
        elif len(candidates) == 1:
            item = candidates[0]
            record.update(disposition="resolved-cell", row=item["id"], entryId=item["entryId"],
                          cells=sorted(ids | set(item["encodingCells"]) | set(parsed_table["headerCells"])),
                          rule="explicit-owned-encoding-row/v2",
                          rationale="Exact physical line has a source-owned mnemonic and byte-bearing encoding cells.")
        elif len(continued) == 1:
            item, fragment = continued[0]
            record.update(disposition="justified-continuation", row=item["id"], entryId=item["entryId"],
                          cells=sorted(ids | set(item["headCells"]) | set(item["encodingCells"])
                                       | set(parsed_table["headerCells"])), rule=fragment["rule"],
                          rationale="Neighbor operand text is in the same mnemonic column, table and unique source-owned encoded row.")
        elif ids and ids <= headers and parsed_table.get("status") == "located-header-and-columns":
            record.update(disposition="non-encoding-material", rule="explicit-table-column-header/v2",
                          rationale="Exact source geometry identifies this text as an encoding-table header, not an omitted instruction row.")
        elif len(materials) == 1:
            material = materials[0]
            record.update(disposition="non-encoding-material", rule=material["rule"], entryId=material["entryId"],
                          cells=sorted(ids | set(material["anchorCells"])), constraintsParsed=False,
                          rationale="Exact source cells lie in a register-bit diagram bounded by register labels and a source-owned EPS label; diagram constraints remain unparsed.")
    return result


def region_accounting(outline, entries):
    """Account for the entire PDF, including unparsed rules/maps/appendices."""
    regions = []
    for number in range(1, outline["pages"] + 1):
        owned = [entry["id"] for entry in entries if entry["pdfPage"] <= number <= entry["pdfEndPage"]]
        top = [row["title"] for index, row in enumerate(outline["outline"])
               if row["pdfPage"] <= number < (outline["outline"][index + 1]["pdfPage"]
                                               if index + 1 < len(outline["outline"]) else outline["pages"] + 1)]
        regions.append(dict(pdfPage=number, outlineOwners=top, entryIds=owned,
                            status="instruction-region-constraints-unresolved" if owned else "global-rules-appendix-or-other-region-unresolved",
                            geometryAccounted=True, allConstraintsParsed=False))
    return regions


def derive(publication, pin, baseline, layout, outline, pages, inputs):
    if (baseline["pdfSha256"] != pin["pdfSha256"] or baseline["publication"] != publication
            or baseline["contentSha256"] != digest(baseline["content"])
            or baseline["contentSha256"] != pin["contentSha256"]
            or baseline["counts"] != pin["counts"]):
        raise ValueError("historical baseline content differs from immutable v1 lock")
    if baseline["outlineSha256"] != digest(outline) or digest(outline) != pin["outlineSha256"]:
        raise ValueError("source outline/ownership differs from immutable PDF outline")
    if hashlib.sha256(layout.encode()).hexdigest() != baseline["layoutTextSha256"]:
        raise ValueError("baseline layout differs from its exact v1 transcript input")
    layout_pages = layout.split("\f")
    if not layout_pages[-1].strip():
        layout_pages.pop()
    if (len(layout_pages) != outline["pages"] or len(pages) != outline["pages"]
            or [page["pdfPage"] for page in pages] != list(range(1, outline["pages"] + 1))):
        raise ValueError("PDF/layout/geometry page identity differs")
    entries = entries_from_outline(outline, pin["chapters"])
    if entries != [{key: value for key, value in entry.items() if key not in ("tableIds", "explicitAliasOf")}
                   for entry in baseline["content"]["entries"]]:
        raise ValueError("source entry ownership differs from historical baseline")
    tables, rows, groups = table_geometry(baseline["content"], layout_pages, pages)
    roles = defaultdict(list)
    for table in tables:
        for key in table["headerCells"] + table.get("columnHeaderCells", []):
            roles[key].append(dict(table=table["id"], row=None, column="table-header", entryIds=table["entryIds"]))
        for region in table.get("materialRegions", []):
            for key in region["cells"]:
                roles[key].append(dict(table=table["id"], row=None, column="non-encoding-diagram",
                                      entryIds=[region["entryId"]], constraintsParsed=False,
                                      classificationRule=region["rule"]))
    for row in rows:
        for column, keys in [("mnemonic", row["headCells"]), ("encoding", row["encodingCells"])]:
            for key in keys:
                roles[key].append(dict(table=row["table"], row=row["id"], column=column, entryIds=[row["entryId"]]))
        for continuation in row["operandContinuations"]:
            for key in continuation["cells"]:
                roles[key].append(dict(table=row["table"], row=row["id"], column="mnemonic-continuation",
                                       entryIds=[row["entryId"]], continuationRule=continuation["rule"]))
    cells = []
    for page in pages:
        owners = [entry["id"] for entry in entries if entry["pdfPage"] <= page["pdfPage"] <= entry["pdfEndPage"]]
        for cell in page["cells"]:
            if cell["pdfPage"] != page["pdfPage"] or not cell["id"].startswith(f"pdf:{page['pdfPage']}:cell:"):
                raise ValueError("source cell page identity drift")
            cells.append(dict({key: value for key, value in cell.items() if key != "wordBoxes"},
                              pdfSha256=pin["pdfSha256"], entryIds=owners, roles=roles[cell["id"]],
                              footnoteReferences=[], footnoteParsing="unresolved"))
    gap_records = dispositions(publication, baseline["content"], layout_pages, tables, rows, groups)
    content = dict(sourceCells=cells, tables=tables, rows=rows, oldGapDispositions=gap_records,
                   sourceRegions=region_accounting(outline, entries))
    counts = dict(pdfPages=len(pages), sourceCells=len(cells), geometryRows=len(rows),
                  explicitEncodingRows=sum(bool(row["encodingCells"]) for row in rows),
                  oldGaps=len(gap_records), dispositions=dict(sorted(Counter(item["disposition"] for item in gap_records).items())),
                  unresolvedSourceRegions=len(content["sourceRegions"]),
                  ambiguousCrossPageContinuations=sum(len(table["continuations"]) for table in tables))
    return dict(schema=SCHEMA, rules=RULES, publication=publication, revision=pin["revision"],
                sourceProvenance=pin["sourceProvenance"], pdfSha256=pin["pdfSha256"], inputs=inputs,
                historicalBaselineContentSha256=pin["contentSha256"], extractorSha256=sha_file(__file__),
                content=content, contentSha256=digest(content), counts=counts,
                acceptance=dict(oldGapBacklogClosed=counts["dispositions"].get("unresolved", 0) == 0,
                                allPdfPagesAccounted=True, allSelectedSourceConstraintsParsed=False,
                                sourceCompletenessEstablished=False, c2Complete=False,
                                legalEncodingCompletenessEstablished=False))


def validate_output(result, expected):
    """Compare to independently reconstructed inputs, not a resealable digest."""
    if result != expected:
        raise ValueError("geometry output differs from source reconstruction (omission, source or ownership drift)")
    ids = [item["oldGapId"] for item in result["content"]["oldGapDispositions"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate historical gap identity")
    return result


def verified_corpus_products(corpus, corpus_lock):
    lock = validate_corpus_lock(json.loads(Path(corpus_lock).read_text()))
    manifest_path = Path(corpus) / "products.json"
    products = json.loads(manifest_path.read_text())
    if (products["schema"] != "ariadne.amd64-source-corpus-products/v2"
            or products["corpusSha256"] != digest(lock)
            or products["extractor"] != lock["extractor"]
            or products["requiredPublications"] != [row["publication"] for row in lock["documents"]]):
        raise ValueError("source-region corpus manifest differs from candidate lock")
    return lock, products


def audit_regions(corpus, corpus_lock):
    """Enumerate all five source documents and every unresolved region clause."""
    lock, products = verified_corpus_products(corpus, corpus_lock)
    manifest_path = Path(corpus) / "products.json"
    expected = {row["publication"]: row for row in lock["documents"]}
    actual = {row["publication"]: row for row in products["reproducedPublications"]}
    if len(actual) != len(products["reproducedPublications"]) or set(actual) != set(expected):
        raise ValueError("source-region accounting omits/duplicates a required publication")
    documents = []
    for publication, pin in expected.items():
        product = actual[publication]
        if product["pdfSha256"] != pin["pdfSha256"]:
            raise ValueError("source-region PDF identity differs")
        work = Path(corpus) / publication
        for name, sha in product["products"].items():
            if Path(name).name != name or sha_file(work / name) != sha:
                raise ValueError("source-region product identity differs")
        if not {"bbox.html", "outline.json", "layout.txt"} <= set(product["products"]):
            raise ValueError("source-region product missing geometry/outline/layout")
        outline = json.loads((work / "outline.json").read_text())
        if outline["pages"] != pin["pdfPages"]:
            raise ValueError("source-region page count differs")
        if (work / "bbox.html").read_bytes().count(b"<page ") != outline["pages"]:
            raise ValueError("source-region geometry page omission")
        documents.append(dict(publication=publication, pdfSha256=pin["pdfSha256"],
                              products=product["products"], pages=region_accounting(outline, []),
                              requiredRegions=[dict(region, resolution="unresolved: independent source-region and constraint audit required")
                                               for region in pin["requiredRegions"]]))
    content = dict(documents=documents)
    return dict(schema="ariadne.amd-source-region-accounting/v2", corpusSha256=digest(lock),
                sourceProductsSha256=sha_file(manifest_path), extractorSha256=sha_file(__file__),
                content=content, contentSha256=digest(content),
                counts=dict(documents=len(documents), pdfPages=sum(len(row["pages"]) for row in documents),
                            requiredRegionClauses=sum(len(row["requiredRegions"]) for row in documents)),
                acceptance=dict(allRequiredPublicationsLocated=True, allPdfPagesAccounted=True,
                                allSelectedSourceConstraintsParsed=False, sourceCompletenessEstablished=False,
                                c2Complete=False))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("extract", "check", "regions", "check-regions"))
    parser.add_argument("--publication")
    parser.add_argument("--baseline", type=Path,
                        help="v1-compatible baseline directory, including its exact layout.txt")
    parser.add_argument("--corpus", required=True, type=Path,
                        help="fresh v2 source directory containing bbox.html and outline.json")
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--corpus-lock", type=Path,
                        default=Path(__file__).resolve().parents[1] / "tests/bap/fixtures/amd64-semantics/source-corpus-v2.lock.json")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.command in {"regions", "check-regions"}:
        result = audit_regions(args.corpus, args.corpus_lock)
        output = run_output(args.output)
        if args.command == "regions":
            output.mkdir(parents=True, exist_ok=False)
            (output / "regions.json").write_bytes(canonical(result) + b"\n")
        elif json.loads((output / "regions.json").read_text()) != result:
            raise ValueError("source-region accounting differs from source reconstruction")
        print(json.dumps(dict(counts=result["counts"], acceptance=result["acceptance"]), sort_keys=True))
        return 0
    if not args.publication or not args.baseline or not args.pdf:
        raise ValueError("extract/check require --publication, --baseline and --pdf")
    lock = json.loads(LOCK.read_text())
    pin = next(item for item in lock["documents"] if item["publication"] == args.publication)
    if sha_file(args.pdf) != pin["pdfSha256"]:
        raise ValueError("PDF differs from exact historical source identity")
    baseline_path = args.baseline / "inventory.json"
    layout_path = args.baseline / "layout.txt"
    bbox_path, outline_path = args.corpus / "bbox.html", args.corpus / "outline.json"
    baseline, outline = json.loads(baseline_path.read_text()), json.loads(outline_path.read_text())
    inputs = dict(baselineSha256=sha_file(baseline_path), baselineLayoutSha256=sha_file(layout_path),
                  geometrySha256=sha_file(bbox_path), outlineSha256=sha_file(outline_path),
                  layoutDriftFromHistoricalPin=sha_file(layout_path) != pin["layoutTextSha256"],
                  geometryFormat="pdftotext -bbox-layout UTF-8, top-left PDF-point word boxes",
                  sourceProductVerification="exact source-corpus/v2 manifest and product hashes; fresh C1 reproduction is a prerequisite")
    corpus_lock, corpus_products = verified_corpus_products(args.corpus.parent, args.corpus_lock)
    matched_products = [item for item in corpus_products["reproducedPublications"]
                        if item["publication"] == args.publication]
    if len(matched_products) != 1 or matched_products[0]["pdfSha256"] != pin["pdfSha256"]:
        raise ValueError("missing/ambiguous source-corpus publication identity")
    for name in ("bbox.html", "outline.json"):
        if matched_products[0]["products"].get(name) != sha_file(args.corpus / name):
            raise ValueError("source-corpus geometry/outline product digest differs")
    inputs["corpusSha256"] = digest(corpus_lock)
    inputs["corpusManifestSha256"] = sha_file(args.corpus.parent / "products.json")
    expected = derive(args.publication, pin, baseline, layout_path.read_text(), outline,
                      read_geometry(bbox_path), inputs)
    output = run_output(args.output)
    if args.command == "extract":
        output.mkdir(parents=True, exist_ok=False)
        (output / "geometry.json").write_bytes(canonical(expected) + b"\n")
    else:
        validate_output(json.loads((output / "geometry.json").read_text()), expected)
    print(json.dumps(dict(publication=args.publication, counts=expected["counts"],
                          acceptance=expected["acceptance"], contentSha256=expected["contentSha256"]), sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, ET.ParseError, StopIteration, KeyError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
