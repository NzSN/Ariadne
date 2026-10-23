"""Source accounting for Vol4 material missed by the historical row extractor.

This pass transcribes source cells. It does not repair publisher mistakes, infer
missing bytes, or establish a legal instruction domain. Ownership corrections
are overlays with their literal evidence; the historical outline is immutable.
"""
import re


def _norm(text):
    return "".join(text.split())


def _ids(cells):
    return sorted({cell["id"] for cell in cells})


def _words(cell):
    return cell.get("wordBoxes", [dict(text=cell["text"], rect=cell["rect"])])


def _safe(groups):
    return [group for group in groups if not group["ambiguous"]]


def _line(context, page, index):
    groups = context["groups_by_page"].get(page, [])
    lines = context["layout_pages"][page - 1].splitlines()
    if not 0 <= index < len(lines):
        return None
    found = context["funcs"]["exact_source_line"](groups, lines, index)
    if found is not None:
        return found
    # Detached footnote superscripts shift the mnemonic baseline by 2.7 pt.
    # Require exact full-line text, a unique assignment, and a visible small
    # superscript next to the mnemonic. Arbitrary adjacent rows cannot join.
    candidates = []
    for group in _safe(groups):
        cells = [cell for other in _safe(groups) if abs(other["y"] - group["y"]) <= 3.2
                 for cell in other["cells"]]
        cells.sort(key=lambda cell: (cell["rect"][0], cell["rect"][1]))
        if _norm(" ".join(cell["text"] for cell in cells)) != _norm(lines[index]):
            continue
        markers = [cell for cell in cells if cell["text"] in {"1", "2"}
                   and cell["rect"][3] - cell["rect"][1] < 10]
        heads = [cell for cell in cells if re.match(r"^[A-Z][A-Z0-9]+\s", cell["text"])
                 and any(abs(cell["rect"][2] - marker["rect"][0]) <= 2 for marker in markers)]
        if (len(heads) != 1 or len(markers) != 1
                or abs(heads[0]["rect"][2] - markers[0]["rect"][0]) > 2
                or not 1.5 <= heads[0]["rect"][1] - markers[0]["rect"][1] <= 3.2):
            continue
        key = tuple(_ids(cells))
        if not any(old[0] == key for old in candidates):
            candidates.append((key, dict(text=" ".join(cell["text"] for cell in cells), cells=cells,
                y=min(cell["rect"][1] for cell in cells), ambiguous=False)))
    return candidates[0][1] if len(candidates) == 1 else None


def _patch(kind, rule, rationale, cells, evidence):
    return dict(disposition=kind, cells=_ids(cells), rule=rule + "/v2", rationale=rationale,
                constraintsParsed=False,
                evidence=dict(evidence, constraintsParsed=False, encodingGrammarValidated=False,
                              authoritativeBindingEstablished=False))


def _material(context, record, group, old_table):
    page = record["legacySource"]["pdfPage"]
    groups = _safe(context["groups_by_page"].get(page, []))
    text = group["text"].strip()
    header = _line(context, page, old_table["headerLine"] - 1)
    if header is None:
        return None
    anchors = list(header["cells"])
    kind = None
    if (group["y"] > 700 and "Instruction Reference" in text
            and re.match(r"^(?:\d+\s.+Instruction Reference|Instruction Reference\s.+\d+)$", text)):
        kind = "running-page-footer"
    elif re.match(r"^Note(?:\s+[1-9][0-9]*)?:\s+\S", text):
        kind = "literal-instruction-note"
    else:
        notes = [other for other in groups if 0 < group["y"] - other["y"] <= 12
                 and re.match(r"^Note\s+[1-9][0-9]*:\s+", other["text"])
                 and group["cells"][0]["rect"][0] > other["cells"][0]["rect"][0] + 15]
        if len(notes) == 1 and re.match(r"^[a-z].*[.]$", text):
            kind = "wrapped-literal-instruction-note"
            anchors.extend(notes[0]["cells"])
    if kind is None and text in {
            "For more on using the CPUID instruction to obtain processor feature support information, see",
            "Appendix E of Volume 3."}:
        first = [other for other in groups if other["text"] ==
                 "For more on using the CPUID instruction to obtain processor feature support information, see"]
        second = [other for other in groups if other["text"] == "Appendix E of Volume 3."]
        pairs = [(one, two) for one in first for two in second if 10 <= two["y"] - one["y"] <= 16
                 and (set(_ids(group["cells"])) == set(_ids(one["cells"]))
                      or set(_ids(group["cells"])) == set(_ids(two["cells"])))]
        if len(pairs) == 1:
            kind = "explicit-feature-support-cross-reference"
            anchors += pairs[0][0]["cells"] + pairs[0][1]["cells"]
    if kind is None and text in {"Loads:", "Stores:", "Selection by source register or memory:",
                                 "Selection by immediate byte operand:"}:
        following = [row for row in context["rows"] if row["table"] == old_table["id"]
                     and row["encodingCells"] and 0 < row["rect"][1] - group["y"] <= 24]
        if following:
            kind = "literal-encoding-table-subsection-label"
            wanted = set(following[0]["headCells"] + following[0]["encodingCells"])
            anchors += [cell for other in groups for cell in other["cells"] if cell["id"] in wanted]
    if kind is None:
        # These literal headers identify semantic/alias tables, not opcode
        # tables. Their trailing prose remains an unparsed semantic obligation.
        h = header["text"]
        semantic = ("Implied Value of imm8" in h or
                    ("Imm[0]" in h and "Imm[4]" in h and "Quadword Operands Selected" in h))
        rounding = [other for other in groups if other["text"] ==
                    "Rounding Control with Immediate Byte Operand" and 0 < header["y"] - other["y"] < 60]
        if rounding and "Mnemonic" in h and "(RS)" in h and "(RC)" in h:
            semantic = True
            anchors += rounding[0]["cells"]
        later_encoding = [other["y"] for other in groups if other["y"] > header["y"] + 2
                          and (other["text"] == "Instruction Encoding" or
                               ("Mnemonic" in other["text"] and
                                ("Opcode" in other["text"] or "Encoding" in other["text"])))]
        footers = [other["y"] for other in groups if other["y"] > 700 and
                   "Instruction Reference" in other["text"]]
        limit = min(later_encoding + footers, default=730)
        foreign = (re.search(r"\b[0-9A-Fa-f]{2}\s+/[0-7r]\b", text)
                   or re.search(r"\b[A-Z][A-Z0-9]+\s+(?:[0-9A-Fa-f]{2}\s+){2}[0-9A-Fa-f]{2}\b", text))
        if (semantic and header["y"] <= group["y"]
                and (group["y"] < limit or text == "Instruction Encoding")
                and not foreign and not ("Mnemonic" in text and ("Opcode" in text or "Encoding" in text))):
            kind = "source-identified-semantic-table-and-prose"
    if kind is None:
        return None
    return _patch("non-encoding-material", kind,
                  "Literal source anchors identify non-opcode material; its semantic constraints remain unparsed.",
                  group["cells"] + anchors, dict(materialKind=kind, anchorCells=_ids(anchors),
                    literalSource=text, historicalEntryIds=old_table["entryIds"]))


def _owner(context, table, token):
    entries = {entry["id"]: entry for entry in context["baseline"]["entries"]}
    owners = [entries[key] for key in table["entryIds"]]
    belongs = context["funcs"]["mnemonic_belongs"]
    if len([owner for owner in owners if belongs(token, [owner["title"]])]) == 1:
        return dict(kind="historical-outline-owner", cells=[], historicalEntryIds=table["entryIds"])
    # An exact source heading or explicit assembly prototype may supplement an
    # incomplete bookmark. Never use a footer or Related Instructions list.
    heading_evidence, prototype_evidence, section_headings = [], [], []
    for page in range(max(1, table["pdfPage"] - 4, min(owner["pdfPage"] for owner in owners)), table["pdfPage"] + 1):
        for group in _safe(context["groups_by_page"].get(page, [])):
            for cell in group["cells"]:
                if (cell["rect"][1] <= 190 and cell["rect"][0] < 260
                        and cell["rect"][3] - cell["rect"][1] >= 16
                        and re.fullmatch(r"[A-Z][A-Z0-9]+", cell["text"])):
                    section_headings.append(cell)
                    if cell["text"] == token:
                        heading_evidence.append(cell)
            if (re.match(r"^" + re.escape(token) + r"\s+(?:dest|src[1-3])\b", group["text"])
                    or re.match(r"^There are four operands:\s+" + re.escape(token) + r"\s+dest\b", group["text"])):
                prototype_evidence.append(group["cells"])
    if len(heading_evidence) > 1 or len(prototype_evidence) > 1:
        return None
    evidence = heading_evidence + [cell for cells in prototype_evidence for cell in cells]
    if evidence:
        last = max((cell["pdfPage"], cell["rect"][1]) for cell in evidence)
        if any((cell["pdfPage"], cell["rect"][1]) > last and cell["text"] not in {token, "V" + token, token.removeprefix("V")}
               for cell in section_headings):
            return None
        return dict(kind="literal-heading-or-prototype-overlay", cells=evidence,
                    historicalEntryIds=table["entryIds"], literalMnemonic=token,
                    historicalOwnershipSupersededForThisRow=True)
    # A literal near-spelling disagreement with an actual section heading is a
    # source conflict, not authority to correct the mnemonic.
    candidates = []
    for owner in owners:
        for group in _safe(context["groups_by_page"].get(owner["pdfPage"], [])):
            for cell in group["cells"]:
                name = cell["text"]
                if (cell["rect"][1] <= 130 and cell["rect"][3] - cell["rect"][1] >= 16
                        and re.fullmatch(r"[A-Z][A-Z0-9]+", name) and _one_edit(token, name)):
                    candidates.append(cell)
    if candidates and len({cell["text"] for cell in candidates}) == len(candidates):
        return dict(kind="literal-mnemonic-heading-conflict", cells=candidates,
                    historicalEntryIds=table["entryIds"], literalMnemonic=token,
                    conflictingHeadings=sorted({cell["text"] for cell in candidates}), correctedMnemonic=None)
    return None


def _one_edit(left, right):
    if len(left) == len(right):
        return sum(a != b for a, b in zip(left, right)) == 1
    if len(left) > len(right):
        left, right = right, left
    return len(right) == len(left) + 1 and any(right[:i] + right[i + 1:] == left for i in range(len(right)))


def _row_heads(context, table, header, groups):
    labels = [word for cell in header["cells"] for word in _words(cell) if word["text"] == "Mnemonic"]
    if len(labels) != 1:
        return []
    left = labels[0]["rect"][0]
    stops = [group["y"] for group in groups if group["y"] > header["y"] + 2
             and (group["text"] in {"Related Instructions", "rFLAGS Affected", "Exceptions"}
                  or any(cell["text"] == "Mnemonic" for cell in group["cells"]))]
    stop = min(stops, default=700)
    heads = []
    for group in groups:
        if not header["y"] + 2 < group["y"] < stop:
            continue
        for cell in group["cells"]:
            if not -2 <= cell["rect"][0] - left <= 8:
                continue
            match = re.match(r"^([A-Z][A-Z0-9]+)(?=\s|xmm|ymm|zmm|$)", cell["text"])
            if match and (owner := _owner(context, table, match[1])):
                heads.append((cell, match[1], owner))
    return heads


def _encoding_binding(context, record, group, table):
    page = record["legacySource"]["pdfPage"]
    groups = _safe(context["groups_by_page"].get(page, []))
    header = _line(context, page, table["headerLine"] - 1)
    if header is None or not ("Opcode" in header["text"] or "Encoding" in header["text"]):
        return None
    heads = _row_heads(context, table, header, groups)
    within = [(head, token, owner) for head, token, owner in heads if head["id"] in _ids(group["cells"])]
    continuation = not within
    if not within:
        # Forward attachment is permitted only for one vertically centered
        # mnemonic; a normal continuation always uses the preceding row.
        preceding = [(head, token, owner) for head, token, owner in heads
                     if 0 < group["y"] - head["rect"][1] <= 25]
        following = [(head, token, owner) for head, token, owner in heads
                     if 0 < head["rect"][1] - group["y"] <= 6]
        if preceding and following:
            return None
        if preceding:
            within = [max(preceding, key=lambda item: item[0]["rect"][1])]
        else:
            within = following
    if len(within) != 1:
        return None
    head, token, owner = within[0]
    others = [cell for cell, _, _ in heads if cell["id"] != head["id"]]
    before = max((cell["rect"][1] + 6 for cell in others if cell["rect"][1] < head["rect"][1]), default=header["y"] + 2)
    after = min((cell["rect"][1] - 3.3 for cell in others if cell["rect"][1] > head["rect"][1]), default=head["rect"][1] + 32)
    after = min([after] + [other["y"] for other in groups if other["y"] > head["rect"][1]
                and (re.match(r"^Note(?:\s+[0-9]+)?:", other["text"])
                     or other["text"] in {"Related Instructions", "rFLAGS Affected", "Exceptions"}
                     or any(cell["text"] == "Mnemonic" for cell in other["cells"]))])
    band = [other for other in groups if max(before, head["rect"][1] - 6) < other["y"]
            < min(after, head["rect"][1] + 26)]
    # The transcription target must actually be in this uniquely owned band.
    band_ids = {cell["id"] for other in band for cell in other["cells"]}
    if not set(_ids(group["cells"])) <= band_ids:
        return None
    if any(other["ambiguous"] and max(before, head["rect"][1] - 6) < other["y"] < min(after, head["rect"][1] + 26)
           for other in context["groups_by_page"].get(page, [])):
        return None
    labels = [word for cell in header["cells"] for word in _words(cell)]
    subheaders = [other for other in groups if header["y"] < other["y"] < head["rect"][1]
                  and any(word["text"] in {"VEX", "EVEX", "XOP", "Opcode"}
                          for cell in other["cells"] for word in _words(cell))]
    labels += [word for other in subheaders for cell in other["cells"] for word in _words(cell)]
    encoding_label = [word for word in labels if word["text"] in {"VEX", "EVEX", "XOP", "Opcode"}]
    if not encoding_label:
        return None
    vector = any(word["text"] in {"VEX", "EVEX", "XOP"} for word in labels)
    cells = [cell for other in band for cell in other["cells"]]
    encoded = []
    word_spans = []
    if vector:
        first = min(word["rect"][0] for word in encoding_label) - 12
        notes = [word["rect"][0] for word in labels if word["text"] in {"Notes", "Description"}]
        last = min(notes) - 3 if notes else max(word["rect"][2] for word in encoding_label) + 30
        encoded = [cell for cell in cells if cell["rect"][0] >= first
                   and cell["rect"][2] <= last
                   and abs(cell["rect"][1] - head["rect"][1]) <= 13
                   and not re.match(r"^(?:Note|Related|Instruction)\b", cell["text"])]
        # Require the explicit prefix byte and terminal opcode on the row.
        if not (sum(cell["text"] in {"C4", "C5", "62", "8F"} for cell in encoded) == 1
                and sum(bool(re.match(r"^[0-9A-Fa-f]{2}\s+/r(?:\s|$)", cell["text"])) for cell in encoded) == 1):
            return None
    else:
        # Word-box splitting preserves combined PDF text cells and every raw
        # token. It does not invent absent prefixes/maps or remove (W0)/(W1).
        code = re.compile(r"^(?:[0-9A-Fa-f]{2}|/[0-7r]|[ic][bwdq]|\(W[01]\))$")
        opcode_labels = [word for word in labels if word["text"] == "Opcode"]
        if len(opcode_labels) != 1:
            return None
        opcode_center = (opcode_labels[0]["rect"][0] + opcode_labels[0]["rect"][2]) / 2
        for cell in cells:
            words = _words(cell)
            for index, word in enumerate(words):
                if not re.fullmatch(r"[0-9A-Fa-f]{2}", word["text"]):
                    continue
                end = index + 1
                while end < len(words) and code.fullmatch(words[end]["text"]):
                    end += 1
                seq = words[index:end]
                if (len(seq) >= 2 and abs(word["rect"][1] - head["rect"][1]) <= 6
                        and seq[0]["rect"][0] <= opcode_center <= seq[-1]["rect"][2] + 8):
                    encoded.append(cell)
                    word_spans.append(dict(cell=cell["id"], wordRange=[index, end],
                                           text=" ".join(word["text"] for word in seq)))
                    break
        if len(encoded) != 1:
            return None
        # Preserve an explicit /r wrapped onto the following baseline.
        encoded += [cell for cell in cells if cell["text"] == "/r"
                    and 0 < cell["rect"][1] - head["rect"][1] <= 12.1
                    and cell["rect"][0] <= opcode_center <= cell["rect"][2]]
        if group["text"] == "/r" and not set(_ids(group["cells"])) <= set(_ids(encoded)):
            return None
        first = min(word["rect"][0] for cell in encoded for word in _words(cell)
                    if re.fullmatch(r"[0-9A-Fa-f]{2}", word["text"]))
    # Every cell before the explicit encoding column participates in row
    # ownership. Unknown material cannot disappear between head and operands.
    for cell in cells:
        if cell["id"] == head["id"] or cell["rect"][0] >= first:
            continue
        operand = (-2 <= cell["rect"][0] - head["rect"][0] <= 24 and
                   (re.match(r"^(?:[xyz]mm[0-9]|mm[0-9]|imm[0-9]|reg[0-9]|mem[0-9])", cell["text"])
                    or re.match(r"^[xyz]mm[A-Z][A-Z0-9]+[0-9],?$", cell["text"])))
        operand_end = max((word["rect"][2] for word in _words(head) if word["rect"][2] < first), default=head["rect"][2])
        marker = (cell["text"] in {"1", "2"} and
                  abs(cell["rect"][0] - operand_end) <= 3.2 and
                  cell["rect"][3] - cell["rect"][1] < 10)
        if not (operand or marker or cell in encoded):
            return None
    anchors = header["cells"] + [cell for other in subheaders for cell in other["cells"]]
    evidence = dict(historicalEntryIds=table["entryIds"], literalMnemonic=token,
                    literalRowText=head["text"], headCells=[head["id"]], encodingCells=_ids(encoded),
                    sourceWordSpans=word_spans, ownership={key: value for key, value in owner.items() if key != "cells"},
                    ownershipEvidenceCells=_ids(owner["cells"]), anchorCells=_ids(anchors))
    conflict = owner["kind"] == "literal-mnemonic-heading-conflict"
    # A corrupt operand or bitfield is retained as a source conflict. Attaching
    # its neighboring continuation cannot validate or silently repair it.
    malformed_operands = [cell for cell in cells if re.match(r"^[xyz]mm[A-Z][A-Z0-9]+[0-9],?$", cell["text"])]
    malformed_fields = [cell for cell in encoded if re.search(r"[0-9]r[0-9]", cell["text"])]
    if malformed_operands or malformed_fields:
        conflict = True
        evidence["conflictKind"] = "literal-malformed-operand-or-field"
        evidence["literalConflicts"] = [dict(cell=cell["id"], text=cell["text"])
                                        for cell in malformed_operands + malformed_fields]
        evidence["correction"] = None
    if conflict:
        kind, rule = "source-conflict", "literal-encoding-source-conflict"
    else:
        kind = "justified-continuation" if continuation else "resolved-cell"
        rule = "explicit-source-row-with-retained-geometry"
    return _patch(kind, rule,
                  "Exact source cells transcribe a uniquely bounded row and retain ownership disagreements and literal defects; legal encoding constraints remain open.",
                  group["cells"] + [head] + encoded + anchors + owner["cells"] + malformed_operands,
                  evidence)


def resolve_all(context):
    """Return patches for currently unresolved Vol4 records without mutation."""
    if str(context["publication"]) != "26568":
        return {}
    tables = {table["id"]: table for table in context["baseline"]["tables"]}
    rows = {row["id"]: row for row in context["baseline"]["rows"]}
    result = {}
    for record in context["records"]:
        if record["disposition"] != "unresolved" or "legacySource" not in record:
            continue
        gap = record["originalGap"]
        table = tables.get(gap.get("table") or rows.get(gap.get("row"), {}).get("table"))
        if table is None:
            continue
        source = record["legacySource"]
        group = _line(context, source["pdfPage"], source["line"] - 1)
        if group is None:
            continue
        patch = _material(context, record, group, table) or _encoding_binding(context, record, group, table)
        if patch is not None:
            result[record["ordinal"]] = patch
    return result
