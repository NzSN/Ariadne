"""Source-owned recovery for Vol3 grouped rows and explanatory material.

This pass closes historical transcription records only. It preserves literal
vendor text and never promotes these bindings to parsed architectural contracts.
"""
import re


def _text(value):
    return " ".join(value.split())


def _ids(groups):
    return [cell["id"] for group in groups for cell in group["cells"]]


def _view(context, table):
    funcs = context["funcs"]
    groups = context["groups_by_page"].get(table["pdfPage"], [])
    headers = [group for group in groups if set(funcs["source_ids"](group)) == set(table["headerCells"])]
    if len(headers) != 1 or headers[0]["ambiguous"]:
        return None
    header = headers[0]
    columns = {}
    for name in ("Mnemonic", "Opcode", "Description"):
        cells = [cell for cell in header["cells"] if cell["text"] == name]
        if len(cells) == 1:
            columns[name] = cells[0]["rect"][0]
    if "Mnemonic" not in columns:
        return None
    stop = next((group["y"] for group in groups if group["y"] > header["y"] + 2
                 and (any(cell["text"] == "Mnemonic" for cell in group["cells"])
                      or funcs["STOP"].fullmatch(group["text"].strip()))), float("inf"))
    body = [group for group in groups if header["y"] + 2 < group["y"] < stop]
    entries = {entry["id"]: entry for entry in context["baseline"]["entries"]}
    return dict(table=table, header=header, columns=columns, body=body, entries=entries)


def _owners(context, view, token):
    return [key for key in view["table"]["entryIds"]
            if context["funcs"]["mnemonic_belongs"](token, [view["entries"][key]["title"]])]


def _heads(context, view):
    left = view["columns"]["Mnemonic"]
    found = []
    for group in view["body"]:
        candidates = [cell for cell in group["cells"] if -2 <= cell["rect"][0] - left <= 24]
        if len(candidates) != 1 or group["ambiguous"]:
            continue
        cell = candidates[0]
        owners = _owners(context, view, cell["text"].split()[0])
        if len(owners) == 1:
            found.append((cell, owners[0]))
    return found


def _binding(view, heads, encoding, kind):
    return dict(kind=kind, table=view["table"]["id"], entryId=heads[0][1],
                originalEntryIds=list(view["table"]["entryIds"]),
                headCells=[cell["id"] for cell, _ in heads],
                encodingCells=[cell["id"] for cell in encoding],
                literalEncoding=" ".join(cell["text"] for cell in encoding),
                headerCells=[cell["id"] for cell in view["header"]["cells"]],
                descriptionColumnLeft=view["columns"]["Description"])


def _grouped_bindings(context, view):
    """Require isolated, evenly spaced heads and one centered explicit opcode."""
    if set(view["columns"]) != {"Mnemonic", "Opcode", "Description"}:
        return []
    heads = _heads(context, view)
    clusters = []
    for head in heads:
        if clusters and head[0]["rect"][1] - clusters[-1][-1][0]["rect"][1] <= 12:
            clusters[-1].append(head)
        else:
            clusters.append([head])
    result = []
    for cluster in clusters:
        if len(cluster) not in (2, 3) or len({owner for _, owner in cluster}) != 1:
            continue
        cells = [cell for cell, _ in cluster]
        ys = [cell["rect"][1] for cell in cells]
        if any(abs(right - left - 10) > .6 for left, right in zip(ys, ys[1:])):
            continue
        if any(0 < min(abs(other["rect"][1] - ys[0]), abs(other["rect"][1] - ys[-1])) < 16
               for other, _ in heads if other not in cells):
            continue
        title = view["entries"][cluster[0][1]]["title"]
        tokens = [_text(cell["text"]).replace(", ", ",") for cell in cells]
        cmov = [re.fullmatch(r"(CMOV[A-Z]+) reg(16|32|64),reg/mem\2", text) for text in tokens]
        is_cmov = (title == "CMOVcc" and len(cells) == 3 and all(cmov)
                   and len({match[1] for match in cmov}) == 1
                   and [match[2] for match in cmov] == ["16", "32", "64"])
        is_set = (title == "SETcc" and all(re.fullmatch(r"SET[A-Z]+ reg/mem8", text) for text in tokens)
                  and len(set(tokens)) == len(tokens))
        if not (is_cmov or is_set):
            continue
        band = [group for group in view["body"] if ys[0] - 1.2 <= group["y"] <= ys[-1] + 1.2]
        if any(group["ambiguous"] for group in band):
            continue
        opcode_left, desc = view["columns"]["Opcode"], view["columns"]["Description"]
        encoding = [cell for group in band for cell in group["cells"]
                    if opcode_left - 2 <= cell["rect"][0] < desc - 2]
        if (len(encoding) != 1 or not context["funcs"]["encoding_cell"](encoding[0])
                or abs(encoding[0]["rect"][1] - (ys[0] + ys[-1]) / 2) > .6
                or encoding[0]["rect"][2] >= desc - 2
                or any(cell["rect"][2] >= opcode_left - 2 for cell in cells)):
            continue
        allowed = {cell["id"] for cell in cells + encoding}
        if any(cell["id"] not in allowed and cell["rect"][0] < desc - 2
               for group in band for cell in group["cells"]):
            continue
        result.append(_binding(view, cluster, encoding,
                               "centered-cmov-width-group" if is_cmov else "centered-setcc-alias-group"))
    return result


def _wrapped_bindings(context, view):
    if set(view["columns"]) != {"Mnemonic", "Opcode", "Description"}:
        return []
    opcode_left, desc = view["columns"]["Opcode"], view["columns"]["Description"]
    result = []
    for head, owner in _heads(context, view):
        band = [group for group in view["body"] if abs(group["y"] - head["rect"][1]) <= 6]
        if any(group["ambiguous"] for group in band):
            continue
        encoding = [cell for group in band for cell in group["cells"]
                    if opcode_left - 2 <= cell["rect"][0] < desc - 2]
        if (len(encoding) != 2 or abs(encoding[0]["rect"][0] - encoding[1]["rect"][0]) > .6
                or abs((encoding[0]["rect"][1] + encoding[1]["rect"][1]) / 2 - head["rect"][1]) > .6
                or not 9.4 <= encoding[1]["rect"][1] - encoding[0]["rect"][1] <= 10.6
                or any(cell["rect"][2] >= desc - 2 for cell in encoding)):
            continue
        literal = tuple(cell["text"] for cell in encoding)
        token = head["text"].split()[0]
        shape = ((token == "CMPXCHG16B" and literal == ("0F C7 /1", "m128"))
                 or (token == "MOVDIRI" and literal == ("REX.W 0F", "3B F9 /r"))
                 or (token == "MOVDIR64B" and literal == ("66 0F 3B F8", "/r")))
        allowed = {head["id"]} | {cell["id"] for cell in encoding}
        if not shape or head["rect"][2] >= opcode_left - 2 or any(cell["id"] not in allowed and cell["rect"][0] < desc - 2
                            for group in band for cell in group["cells"]):
            continue
        result.append(_binding(view, [(head, owner)], encoding, "single-head-wrapped-opcode"))
    return result


def _alternative_bindings(context, view):
    if set(view["columns"]) != {"Mnemonic", "Opcode", "Description"}:
        return []
    result = []
    for head, owner in _heads(context, view):
        if head["text"] != "VMGEXIT":
            continue
        group = next(group for group in view["body"] if head in group["cells"])
        opcode, desc = view["columns"]["Opcode"], view["columns"]["Description"]
        encoding = [cell for cell in group["cells"] if opcode - 2 <= cell["rect"][0] < desc - 2]
        if (len(encoding) == 1 and encoding[0]["text"] == "F2/F3 0F 01 D9"
                and encoding[0]["rect"][2] < desc - 2 and head["rect"][2] < opcode - 2
                and all(cell["id"] in {head["id"], encoding[0]["id"]} or cell["rect"][0] >= desc - 2
                        for cell in group["cells"])):
            result.append(_binding(view, [(head, owner)], encoding, "literal-alternate-prefix-encoding"))
    return result


def _materials(context, view):
    """Recognize complete explanatory regions, retaining unparsed constraints."""
    result = []
    rows = [row for row in context["rows"] if row["table"] == view["table"]["id"]]
    last = max((row["rect"][3] for row in rows), default=float("inf"))
    owners = view["table"]["entryIds"]
    if len(owners) != 1:
        return result
    owner = owners[0]
    title = view["entries"][owner]["title"]
    if not rows and title in {"LLWPCB", "LWPINS", "LWPVAL", "SLWPCB"}:
        # These tables center the Mnemonic heading over a wide operand column.
        # Recognize both explicit source rows before locating the prose below.
        encoded = [group for group in view["body"] if not group["ambiguous"]
                   and any(cell["text"].startswith(title + " reg") for cell in group["cells"])
                   and any(cell["text"] == "8F" for cell in group["cells"])]
        labels = [group for group in view["body"] if "XOP" in group["text"]
                  and "RXB.map_select" in group["text"] and "W.vvvv.L.pp" in group["text"]]
        if len(encoded) == 2 and len(labels) == 1 and labels[0]["y"] < encoded[0]["y"]:
            first = [next(cell["text"] for cell in group["cells"]
                          if cell["text"].startswith(title + " reg")) for group in encoded]
            if first[0].replace("reg32", "reg64", 1) == first[1]:
                last = max(group["rect"][3] for group in encoded)
    body = [group for group in view["body"] if group["y"] > last]

    def add(span, kind):
        if not span or any(group["ambiguous"] for group in span):
            return
        if any(group not in span and span[0]["y"] <= group["y"] < span[-1]["rect"][3]
               for group in body):
            return
        result.append(dict(kind=kind, table=view["table"]["id"], entryId=owner,
                           originalEntryIds=list(owners), cells=_ids(span),
                           anchorCells=_ids([span[0], span[-1]]), constraintsParsed=False))

    def sequence(texts, kind):
        expected = [_text(text) for text in texts]
        for index in range(len(body) - len(texts) + 1):
            span = body[index:index + len(texts)]
            if [_text(group["text"]) for group in span] == expected:
                add(span, kind)

    if title == "CALL (Near)":
        sequence(["For details about control-flow instructions, see “Control Transfers” in APM Volume 1, and “Control-",
                  "Transfer Privilege Checks” in APM Volume 2."], "control-transfer-cross-reference")
    elif title == "INT 3":
        sequence(["For complete descriptions of the steps performed by INT instructions, see the following:",
                  "• Legacy-Mode Interrupts: “Legacy Protected-Mode Interrupt Control Transfers” in APM",
                  "Volume 2.", "• Long-Mode Interrupts: “Long-Mode Interrupt Control Transfers” in APM Volume 2."],
                 "interrupt-cross-reference")
    elif title == "CMP":
        sequence(["When interpreting operands as unsigned, flag settings are as follows:", "Operands CF ZF",
                  "dest > source 0 0", "dest = source 0 1", "dest < source 1 0",
                  "When interpreting operands as signed, flag settings are as follows:", "Operands OF ZF",
                  "dest > source SF 0", "dest = source 0 1", "dest < source NOT SF 0"], "comparison-flag-tables")
    elif title == "OR":
        sequence(["The following chart summarizes the effect of this instruction:", "X or Y", "X Y",
                  "0 0 0", "0 1 1", "1 0 1", "1 1 1"], "boolean-truth-table")
    elif title == "CPUID":
        starts = [i for i, group in enumerate(body) if group["text"] == "Testing for the CPUID Instruction"]
        ends = [i for i, group in enumerate(body) if _text(group["text"]) == "pop eax ; store EFLAGS in EAX"]
        if len(starts) == len(ends) == 1 and starts[0] < ends[0]:
            span = body[starts[0]:ends[0] + 1]
            texts = [_text(group["text"]) for group in span]
            if (len(span) == 13 and texts[-2] == "pushfd ; save EFLAGS"
                    and texts[-4].startswith("The following code sample shows how to test for the presence of the CPUID instruction")
                    and texts[-3] == "code."
                    and all(len(group["cells"]) == 1 for group in span[:-2])
                    and not any(context["funcs"]["encoding_cell"](cell)
                                or cell["text"] in {"Mnemonic", "Opcode", "Encoding"}
                                for group in span for cell in group["cells"])):
                add(span, "processor-capability-testing-subsection")
    elif title in {"LLWPCB", "LWPINS", "LWPVAL", "SLWPCB"}:
        paragraphs = {
            "LLWPCB": ["ModRM.reg augments the opcode and is assigned the value 0. ModRM.r/m (augmented by XOP.R)",
                       "specifies the register containing the effective address of the LWPCB. ModRM.mod is 11b."],
            "LWPINS": ["ModRM.reg augments the opcode and is assigned the value 0. The {mod, r/m} field of the ModRM",
                       "byte (augmented by XOP.R) encodes the second operand. A 4-byte immediate field follows ModRM."],
            "LWPVAL": ["ModRM.reg augments the opcode and is assigned the value 001b. The {mod, r/m} field of the",
                       "ModRM byte (augmented by XOP.R) encodes the second operand. A four-byte immediate field", "follows ModRM."],
            "SLWPCB": ["ModRM.reg augments the opcode and is assigned the value 001b. ModRM.r/m (augmented by",
                       "XOP.R) specifies the register in which to put the LWPCB address. ModRM.mod must be 11b."]}
        sequence(paragraphs[title], "encoding-constraint-prose")
    elif title == "MOVD":
        if any(re.match(r"MOVD\s*1 ", row["mnemonic"]) for row in rows):
            sequence(["Note: 1. Also known as MOVQ in some developer tools."], "instruction-naming-footnote")
    return result


def resolve_all(context):
    """Return evidence-bearing patches without modifying the supplied context."""
    if str(context["publication"]) != "24594":
        return {}
    tables = {table["id"]: table for table in context["tables"]}
    legacy_rows = {row["id"]: row for row in context["baseline"]["rows"]}
    bindings, materials = {}, {}
    for key, table in tables.items():
        view = _view(context, table)
        if view:
            bindings[key] = (_grouped_bindings(context, view) + _wrapped_bindings(context, view)
                             + _alternative_bindings(context, view))
            materials[key] = _materials(context, view)
    result = {}
    for record in context["records"]:
        if record["disposition"] != "unresolved":
            continue
        gap = record["originalGap"]
        table_id = gap.get("table") or legacy_rows.get(gap.get("row"), {}).get("table")
        source = record.get("legacySource")
        if not source:
            continue
        lines = context["layout_pages"][source["pdfPage"] - 1].splitlines()
        group = context["funcs"]["exact_source_line"](context["groups_by_page"].get(source["pdfPage"], []),
                                                     lines, source["line"] - 1)
        if group is None:
            continue
        ids = set(context["funcs"]["source_ids"](group))
        candidates = []
        for binding in bindings.get(table_id, []):
            cells = set(binding["headCells"] + binding["encodingCells"])
            if (ids & cells and all(cell["id"] in cells or cell["rect"][0] >= binding["descriptionColumnLeft"] - 2
                                   for cell in group["cells"])):
                candidates.append(dict(disposition="resolved-cell", entryId=binding["entryId"],
                    cells=sorted(ids | cells | set(binding["headerCells"])),
                    rule=binding["kind"] + "/v2", evidence=binding,
                    rationale="Named columns, unique source ownership and explicit source geometry bind every retained opcode fragment to these mnemonic cells."))
        for material in materials.get(table_id, []):
            if ids and ids <= set(material["cells"]):
                candidates.append(dict(disposition="non-encoding-material", entryId=material["entryId"],
                    cells=sorted(ids | set(material["anchorCells"])), constraintsParsed=False,
                    rule=material["kind"] + "/v2", evidence=material,
                    rationale="Source-owned explanatory material is bounded and retained; its architectural constraints remain unparsed."))
        if len(candidates) == 1:
            result[record["ordinal"]] = candidates[0]
    return result
