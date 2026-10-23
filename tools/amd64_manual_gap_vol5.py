"""Source-bound recovery of Volume 5's historical table-parser overreach.

These rules account for old gaps. They do not parse diagram semantics, infer
instruction encodings, or establish completeness of the manual's constraints.
The caller supplies fresh word geometry and retains every original gap record.
"""
import hashlib
import itertools
import re


REGISTER = re.compile(r"(?:[xyz]mm|mmx?|reg|mem|imm)[0-9]*(?:/(?:[xyz]mm|mmx?|reg|mem|imm)[0-9]*)*")
EPS = re.compile(r"([A-Za-z0-9]+)(?:[-_][A-Za-z0-9_-]+)?\.eps")
DIAGRAM_WORDS = {".", "copy", "convert", "shift left", "shift right", "arithmetic"}


def norm(text):
    return "".join(text.split())


def ids(cells):
    return {cell["id"] for cell in cells}


def unique(items):
    return items[0] if len(items) == 1 else None


def region(cells, anchors, owner, rule, rationale, **evidence):
    return dict(cells=cells, anchors=anchors, owner=owner, rule=rule,
                rationale=rationale, evidence=evidence)


def _line_candidates(line, groups):
    """Enumerate exact source-cell assignments, including staggered columns.

    Layout can put a three-point-staggered right column on the preceding line.
    No text is split or invented, and alternatives remain alternatives until
    independent neighboring lines establish one vertical position.
    """
    candidates = [group for group in groups if not group["ambiguous"]
                  and norm(group["text"]) == norm(line)]
    columns = re.split(r"\s{2,}", line.strip())
    if len(columns) > 1:
        cells = [cell for group in groups if not group["ambiguous"] for cell in group["cells"]]
        choices = [[cell for cell in cells if norm(cell["text"]) == norm(column)] for column in columns]
        combinations = 1
        for options in choices:
            combinations *= len(options)
        if 0 < combinations <= 128:
            for selected in itertools.product(*choices):
                if (max(cell["rect"][1] for cell in selected) - min(cell["rect"][1] for cell in selected) <= 6
                        and all(left["rect"][2] + 1 < right["rect"][0]
                                for left, right in zip(selected, selected[1:]))):
                    candidates.append(dict(cells=list(selected), y=min(cell["rect"][1] for cell in selected),
                                           ambiguous=False))
    deduplicated = {tuple(sorted(ids(item["cells"]))): item for item in candidates}
    return list(deduplicated.values())


def _conflicting_assignments(assignments):
    """Every accepted layout line owns distinct cells in increasing order."""
    conflicting = set()
    ordered = sorted(assignments)
    for position, left_index in enumerate(ordered):
        left = assignments[left_index]
        for right_index in ordered[position + 1:]:
            right = assignments[right_index]
            if ids(left["cells"]) & ids(right["cells"]) or left["y"] >= right["y"]:
                conflicting.update((left_index, right_index))
    return conflicting


def source_matches(groups, lines, exact):
    """Retain exact matching and recover repeats using unique source neighbors.

    A recovered assignment requires both an earlier and a later independently
    matched layout line. Iteration only uses assignments proved in the previous
    round. Missing or duplicate geometry therefore cannot bootstrap a match.
    """
    matched = {}
    candidates = {}
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        direct = exact(groups, lines, index)
        if direct is not None:
            matched[index] = direct
        else:
            candidates[index] = _line_candidates(line, groups)
    # Even an exact whole-line match cannot be reused by another source line.
    # Removing both conflicting anchors prevents a damaged layout from lending
    # apparent authority to a subsequent neighbor-based recovery.
    for index in _conflicting_assignments(matched):
        del matched[index]
    while candidates:
        added = {}
        occupied = {key for match in matched.values() for key in ids(match["cells"])}
        for index, options in candidates.items():
            before = next((matched[j] for j in range(index - 1, -1, -1) if j in matched), None)
            after = next((matched[j] for j in range(index + 1, len(lines)) if j in matched), None)
            if before is None or after is None:
                continue
            fitting = [option for option in options if before["y"] < option["y"] < after["y"]
                       and not ids(option["cells"]) & occupied]
            if len(fitting) == 1:
                added[index] = fitting[0]
        # Two missing occurrences can each appear uniquely bracketed by the
        # same anchors. Neither is proved when they claim the same cells, or
        # when their candidate geometry reverses source line order.
        for index in _conflicting_assignments(added):
            del added[index]
        if not added:
            break
        matched.update(added)
        for index in added:
            del candidates[index]
    return matched


def _belongs(text, entry, belongs):
    return belongs(text, [entry["title"]])


def _footer_regions(cells, entry):
    lower = [cell for cell in cells if 720 < cell["rect"][1] < 780]
    publisher = unique([cell for cell in lower if cell["text"] == "[AMD Public Use]"])
    reference = unique([cell for cell in lower if cell["text"] == "Instruction Reference"])
    chapter_name = re.sub(r"^\d+\s+", "", entry["chapter"]).removesuffix(" Instruction Reference")
    chapter = unique([cell for cell in lower if cell["text"] == chapter_name])
    if publisher is None or reference is None or chapter is None:
        return []
    band = [cell for cell in lower if abs(cell["rect"][1] - chapter["rect"][1]) <= 1.2]
    numbers = [cell for cell in band if cell["text"].isdecimal()]
    labels = [cell for cell in band if cell is not chapter and cell not in numbers]
    if len(band) != 3 or len(numbers) != 1 or len(labels) != 1:
        return []
    names = re.findall(r"[A-Z][A-Z0-9]*", entry["title"])
    label = labels[0]["text"]
    owned = label == entry["title"] or label in names
    # The source's FCOMx/FISTx running titles abbreviate an explicitly named
    # instruction family; this is footer ownership, never encoding ownership.
    if label.endswith("x"):
        owned = label[:-1] in names and all(name.startswith(label[:-1]) for name in names)
    if not owned or not chapter["rect"][1] < reference["rect"][1] < chapter["rect"][1] + 18:
        return []
    anchors = band + [publisher, reference]
    return [region(anchors, anchors, entry["id"], "owned-running-footer/v2",
                   "The exact line is in the bottom running footer, with chapter, owned instruction title, printed page and publisher/reference anchors.")]


def _diagram_regions(cells, groups, rows, entry, belongs):
    end_rows = max(row["rect"][3] for row in rows)
    labels = [cell for cell in cells if EPS.fullmatch(cell["text"])
              and _belongs(EPS.fullmatch(cell["text"])[1].upper(), entry, belongs)]
    if len(labels) != 1:
        return []
    label = labels[0]
    starts = []
    for index, group in enumerate(groups):
        if (group["ambiguous"] or not end_rows + 8 < group["y"] < label["rect"][1]
                or label["rect"][1] - group["y"] > 340
                or not all(REGISTER.fullmatch(cell["text"]) for cell in group["cells"])):
            continue
        nearby = groups[index + 1:index + 4]
        if any(not candidate["ambiguous"] and len(candidate["text"].split()) >= 4
               and all(word.isdecimal() and int(word) <= 512 for word in candidate["text"].split())
               for candidate in nearby):
            starts.append(group)
    if not starts:
        return []
    first = min(starts, key=lambda item: item["y"])
    selected = [cell for cell in cells if first["y"] <= cell["rect"][1] <= label["rect"][3]]
    if any(group["ambiguous"] and ids(group["cells"]) & ids(selected) for group in groups):
        return []
    def allowed(cell):
        text = cell["text"]
        return (cell is label or REGISTER.fullmatch(text) or text in DIAGRAM_WORDS
                or all(word == "." for word in text.split())
                or all(word.isdecimal() and int(word) <= 512 for word in text.split()))
    if not all(allowed(cell) for cell in selected):
        return []
    anchors = [cell for start in starts for cell in start["cells"]] + [label]
    return [region(selected, anchors, entry["id"], "owned-multipart-register-diagram/v2",
                   "Register labels and decimal bit rows form one fenced diagram ending at its uniquely owned EPS label; its semantic constraints remain unparsed.",
                   diagramParts=len(starts))]


def _immediate_regions(cells, groups, rows, entry, belongs):
    captions = []
    for cell in cells:
        match = re.fullmatch(r"Table \d+-\d+\. Immediate-Byte Operand Encoding for 64-Bit ([A-Z0-9]+)", cell["text"])
        if match and _belongs(match[1], entry, belongs):
            captions.append(cell)
    if len(captions) != 1:
        return []
    caption = captions[0]
    if caption["rect"][1] <= max(row["rect"][3] for row in rows):
        return []
    stop = min((cell["rect"][1] for cell in cells if cell["text"] == "Related Instructions"
                and cell["rect"][1] > caption["rect"][1]), default=720)
    selected = [cell for cell in cells if caption["rect"][1] <= cell["rect"][1] < stop]
    required = {"Immediate-Byte", "Bit Field", "Value of Bit Field", "1–0"}
    headers = [cell for cell in selected if cell["text"] in required]
    result_header = [cell for cell in selected if cell["text"] in {"Source Bits Extracted", "Destination Bits Filled"}]
    if len(headers) != 4 or {cell["text"] for cell in headers} != required or len(result_header) != 1:
        return []
    pairs = [(str(index), f"{16 * index + 15}–{16 * index}") for index in range(4)]
    for value, bits in pairs:
        left = unique([cell for cell in selected if cell["text"] == value])
        right = unique([cell for cell in selected if cell["text"] == bits])
        if left is None or right is None or abs(left["rect"][1] - right["rect"][1]) > 1.2 or left["rect"][2] >= right["rect"][0]:
            return []
    allowed = required | {item for pair in pairs for item in pair} | {result_header[0]["text"], caption["text"]}
    if len(selected) != 14 or any(cell["text"] not in allowed for cell in selected):
        return []
    if any(group["ambiguous"] and ids(group["cells"]) & ids(selected) for group in groups):
        return []
    return [region(selected, [caption] + headers + result_header, entry["id"], "owned-immediate-field-table/v2",
                   "The source-owned caption and bit-field/value/selected-bit columns identify an immediate operand semantics table, not an additional instruction encoding.")]


def _stack_regions(cells, groups, rows, entry):
    if entry["title"] not in {"FDECSTP", "FINCSTP"}:
        return []
    before = unique([cell for cell in cells if cell["text"] == "Before " + entry["title"]])
    after = unique([cell for cell in cells if cell["text"] == "After " + entry["title"]])
    stop = unique([cell for cell in cells if cell["text"] == "Related Instructions"])
    if (before is None or after is None or stop is None
            or abs(before["rect"][1] - after["rect"][1]) > 1.2
            or before["rect"][1] <= max(row["rect"][3] for row in rows)
            or before["rect"][2] >= after["rect"][0]):
        return []
    body = [group for group in groups if before["rect"][1] + 2 < group["y"] < stop["rect"][1]]
    if len(body) != 9 or any(group["ambiguous"] for group in body):
        return []
    if [cell["text"] for cell in body[0]["cells"]] != ["Data Register", "Value", "Stack Pointer", "Stack Pointer", "Value"]:
        return []
    prior, later = set(), set()
    for index, group in enumerate(body[1:]):
        words = [cell["text"] for cell in group["cells"]]
        if (len(words) != 5 or words[0] != str(7 - index) or words[1] != f"num{index + 1}"
                or words[4] != words[1] or not re.fullmatch(r"ST\([0-7]\)", words[2])
                or not re.fullmatch(r"ST\([0-7]\)", words[3])):
            return []
        prior.add(words[2])
        later.add(words[3])
    if len(prior) != 8 or len(later) != 8:
        return []
    selected = [before, after] + [cell for group in body for cell in group["cells"]]
    return [region(selected, [before, after] + body[0]["cells"] + [stop], entry["id"], "owned-x87-stack-diagram/v2",
                   "Paired Before/After instruction labels, stack columns and eight indexed rows identify the x87 stack diagram; its semantic constraints remain unparsed.")]


def _result_regions(cells, groups, rows, entry):
    if entry["title"] not in {"FIST FISTP", "FISTTP"}:
        return []
    captions = [group for group in groups if not group["ambiguous"]
                and re.fullmatch(r"Table (\d+-\d+)\. Storing Numbers as Integers", group["text"])]
    if len(captions) != 1:
        return []
    caption = captions[0]
    number = re.fullmatch(r"Table (\d+-\d+)\. Storing Numbers as Integers", caption["text"])[1]
    intro = unique([cell for cell in cells if cell["text"] ==
                    f"Table {number} shows the results of storing various types of numbers as integers."])
    if intro is None or not max(row["rect"][3] for row in rows) < intro["rect"][1] < caption["y"]:
        return []
    stop = min((cell["rect"][1] for cell in cells if cell["text"] == "Related Instructions"
                and cell["rect"][1] > caption["y"]), default=720)
    selected = [cell for cell in cells if caption["y"] <= cell["rect"][1] < stop]
    source_header = unique([cell for cell in selected if cell["text"] == "ST(0)"])
    target_header = unique([cell for cell in selected if cell["text"] in {"DEST", "DESTINATION"}])
    if (source_header is None or target_header is None or source_header["rect"][2] >= target_header["rect"][0]
            or abs(source_header["rect"][1] - target_header["rect"][1]) > 1.2):
        return []
    value = re.compile(r"(?:[-+]∞|NaN|[-+]0|[–+]Finite-real [<≤≥] [–+]1|–1 < –Finite-real< –0|\+0 < \+Finite-real < \+1|-1 < Finite-real < \+1)")
    result = re.compile(r"(?:Invalid-operation \(IE\) exception|0|0 or [–+]1, depending on the rounding mode|[–+]Integer \(Invalid-operation \(IE\) exception if the integer is too large for the(?: destination\))?|destination\))")
    body = [cell for cell in selected if cell["rect"][1] > source_header["rect"][1] + 2]
    # All visible cells must belong to the named result table. A source note,
    # new encoding row or duplicated/overprinted text is not silently swallowed.
    if (len([cell for cell in body if value.fullmatch(cell["text"])]) < 6
            or not all(value.fullmatch(cell["text"]) or result.fullmatch(cell["text"]) for cell in body)
            or any(group["ambiguous"] and ids(group["cells"]) & ids(selected) for group in groups)):
        return []
    return [region([intro] + selected, [intro] + caption["cells"] + [source_header, target_header], entry["id"],
                   "owned-x87-integer-result-table/v2",
                   "The named Storing Numbers as Integers table has ST(0)/destination columns and numeric result material; continuation and semantic constraints remain unparsed.")]


def _narration_regions(cells, rows, entry, belongs, groups_by_page):
    result = []
    last = max(row["rect"][3] for row in rows)
    for cell in cells:
        if not last < cell["rect"][1] < 720:
            continue
        match = re.fullmatch(r"The following diagrams illustrate the operation of the ([A-Z0-9]+) instruction\.", cell["text"])
        if match and _belongs(match[1], entry, belongs):
            result.append(region([cell], [cell], entry["id"], "owned-diagram-introduction/v2",
                                 "The literal source sentence introduces diagrams for this instruction; it is prose, not an encoding row."))
        match = re.fullmatch(r"The numeric range for operands is shown in Table (\d+-\d+) on page (\d+)\.", cell["text"])
        if match:
            targets = []
            for page in range(entry["pdfPage"], entry["pdfEndPage"] + 1):
                target_cells = [item for group in groups_by_page.get(page, []) for item in group["cells"]]
                captions = [item for item in target_cells if item["text"] ==
                            f"Table {match[1]}. Numeric Range for {entry['title']} Results"]
                page_number = [item for item in target_cells if item["text"] == match[2] and item["rect"][1] > 720]
                if len(captions) == 1 and len(page_number) == 1:
                    targets.append(captions + page_number)
            if len(targets) == 1:
                result.append(region([cell], [cell] + targets[0], entry["id"], "owned-numeric-range-reference/v2",
                                     "The source sentence refers to the uniquely owned numeric-range table on the cited printed page; the referenced constraints remain unparsed."))
    return result


def resolve_all(context):
    """Return patches for unresolved Volume 5 records without mutating inputs."""
    if context["publication"] != "26569":
        return {}
    funcs = context["funcs"]
    belongs = funcs["mnemonic_belongs"]
    entries = {entry["id"]: entry for entry in context["baseline"]["entries"]}
    tables = {table["id"]: table for table in context["tables"]}
    groups_by_page = context["groups_by_page"]
    matches = {}
    material = {}
    row_map = {}
    for table in tables.values():
        if len(table["entryIds"]) != 1 or table.get("status") != "located-header-and-columns":
            continue
        entry = entries[table["entryIds"][0]]
        page = table["pdfPage"]
        groups = groups_by_page.get(page, [])
        cells = [cell for group in groups for cell in group["cells"]]
        headers = [cell for cell in cells if cell["id"] in table["headerCells"]]
        if sorted(cell["text"] for cell in headers) != ["Description", "Mnemonic", "Opcode"]:
            continue
        rows = [row for row in context["rows"] if row["table"] == table["id"]
                and row["entryId"] == entry["id"] and row["encodingCells"]]
        if not rows:
            continue
        row_map[table["id"]] = rows
        if page not in matches:
            matches[page] = source_matches(groups, context["layout_pages"][page - 1].splitlines(), funcs["exact_source_line"])
        regions = (_footer_regions(cells, entry)
                   + _diagram_regions(cells, groups, rows, entry, belongs)
                   + _immediate_regions(cells, groups, rows, entry, belongs)
                   + _stack_regions(cells, groups, rows, entry)
                   + _result_regions(cells, groups, rows, entry)
                   + _narration_regions(cells, rows, entry, belongs, groups_by_page))
        material[table["id"]] = regions
    patches = {}
    for record in context["records"]:
        if record["disposition"] != "unresolved" or "legacySource" not in record:
            continue
        source = record["legacySource"]
        page, index = source["pdfPage"], source["line"] - 1
        lines = context["layout_pages"][page - 1].splitlines()
        if not 0 <= index < len(lines) or hashlib.sha256(lines[index].encode()).hexdigest() != source["textSha256"]:
            continue
        line = matches.get(page, {}).get(index)
        if line is None:
            continue
        table_id = record["originalGap"].get("table")
        selected = ids(line["cells"])
        found = [item for item in material.get(table_id, []) if selected <= ids(item["cells"])]
        if len(found) == 1:
            item = found[0]
            patches[record["ordinal"]] = dict(disposition="non-encoding-material", entryId=item["owner"],
                cells=sorted(selected | ids(item["anchors"])), constraintsParsed=False,
                rule=item["rule"], rationale=item["rationale"],
                evidence=dict(item["evidence"], sourceCells=sorted(selected), anchorCells=sorted(ids(item["anchors"]))))
            continue
        continued = [row for row in row_map.get(table_id, []) if row.get("centeredEncodingCells")
                     and any(selected == set(fragment["cells"]) for fragment in row["operandContinuations"])]
        if len(continued) == 1:
            row = continued[0]
            bound = set(row["centeredEncodingCells"]) | set(tables[table_id]["headerCells"])
            patches[record["ordinal"]] = dict(disposition="justified-continuation", entryId=row["entryId"],
                cells=sorted(selected | bound), rule="neighbor-bound-centered-operand/v2",
                rationale="Unique neighboring source lines locate the repeated operand in its already proved centered-opcode row; no opcode is inferred or shared.",
                evidence=dict(row=row["id"], sourceCells=sorted(selected), anchorCells=sorted(bound),
                              headCells=row["headCells"], encodingCells=row["encodingCells"]))
    return patches
