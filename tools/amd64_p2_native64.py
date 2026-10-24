#!/usr/bin/env python3
"""Replay Appendix B source inventories for native AMD64 execution.

Summary-table observations are distinct from instruction-owned qualifications.
Neither an operand-size column nor a mnemonic list defines complete semantics,
memory access sizes, legal encodings, or definite register writes.
"""
import copy
import re

import amd64_source_adoption as adoption
from amd64_inventory_xed import canonical, digest

entry = adoption.entry
ROOT = entry.ROOT
INPUT = ROOT/"tests/bap/fixtures/source-migration/p2-native64-inventory-v1.json"
require = entry.require
B5 = [
    ("CALL", "E8, FF /2", True), ("ENTER", "C8", True), ("Jcc", "many", False),
    ("JrCXZ", "E3", False), ("JMP", "E9, EB, FF /4", False), ("LEAVE", "C9", True),
    ("LOOP", "E2", False), ("LOOPcc", "E0, E1", False), ("POP reg/mem", "8F /0", True),
    ("POP reg", "58-5F", True), ("POP FS", "0F A1", True), ("POP GS", "0F A9", True),
    ("POPF, POPFD, POPFQ", "9D", True), ("PUSH imm8", "6A", True), ("PUSH imm32", "68", True),
    ("PUSH reg/mem", "FF /6", True), ("PUSH reg", "50-57", True), ("PUSH FS", "0F A0", True),
    ("PUSH GS", "0F A8", True), ("PUSHF, PUSHFD, PUSHFQ", "9C", True), ("RET", "C2, C3", True),
]
SYSTEM_NO_REX = ["LGDT", "LIDT", "LLDT", "LTR", "MOV CRn", "MOV DRn"]
OWNERS = {
    "CALL": ("0031",178,180), "ENTER": ("0053",224,225), "Jcc": ("0061",245,248),
    "JrCXZ": ("0062",249,249), "JMP": ("0063",250,251), "LEAVE": ("0068",262,262),
    "LOOP": ("0072",269,270), "LOOPcc": ("0072",269,270), "POP": ("0103",327,328),
    "POPF": ("0106",332,334), "PUSH": ("0109",339,340), "PUSHF": ("0111",342,343),
    "RET": ("0119",353,354),
}
QUALIFICATION_CELLS = {
    "CALL": [(178,16,18)], "ENTER": [(224,23,24)], "Jcc": [(245,18,20)],
    "JrCXZ": [(249,10,12),(249,15,16)], "JMP": [(250,14,16)], "LEAVE": [(262,13,14)],
    "LOOP": [(269,12,20),(269,23,24)], "LOOPcc": [(269,12,20),(269,23,24)],
    "POP": [(327,7,19)], "POPF": [(332,15,16),(332,20,29)],
    "PUSH": [(339,7,10),(339,15,17),(339,46,60)],
    "PUSHF": [(342,9,11),(342,18,27)], "RET": [(353,11,12)],
}
MODE_TABLES = {
    "invalid64": (653, 217, 594, [
        ("AAA","37"), ("AAD","D5"), ("AAM","D4"), ("AAS","3F"), ("CALL (far)","9A"),
        ("DAA","27"), ("DAS","2F"), ("INTO","CE"), ("JMP (far)","EA"), ("LDS","C5"),
        ("LES","C4"), ("POP DS","1F"), ("POP ES","07"), ("POP SS","17"), ("POPA, POPAD","61"),
        ("PUSH CS","0E"), ("PUSH DS","1E"), ("PUSH ES","06"), ("PUSH SS","16"),
        ("PUSHA, PUSHAD","60"), ("Redundant Grp1","82 /2"), ("SALC","D6")]),
    "reassigned64": (654,189,341,[
        ("ARPL","63"), ("DEC and INC","40-4F"), ("BOUND","62"), ("LDS","C5"), ("LES","C4")]),
    "invalidLongMode": (654,446,478,[("SYSENTER","0F 34"),("SYSEXIT","0F 35")]),
}


def qualification_contract(name):
    family = name.split()[0].split(",")[0]
    key = family if family in OWNERS else name
    ident, first, last = OWNERS[key]
    properties = dict(defaultOperandBits=64, operand32Encoding="unavailable",
        operand16="summary-66h-rule;requires-form-qualification", requiresRexForDefault64=False,
        definiteGprWrites="not-derived-from-size-table")
    if name in ("Jcc", "JrCXZ", "LOOP", "LOOPcc"):
        properties["operand32Encoding"] = "not-defined-by-instruction-prose;summary-prohibits"
    if name in ("JrCXZ", "LOOP", "LOOPcc"):
        properties.update(countBits="address-size:64-or-32;separate-from-operand-size", displacementBits=8)
    if name == "JrCXZ":
        properties["excludedAlias"] = "JCXZ:address16-unavailable"
    if name in ("LOOP", "LOOPcc"):
        properties["zf"] = "ignored-by-LOOP;tested-but-not-written-by-LOOPE-LOOPNE"
    if family == "PUSH":
        properties["addressSize"] = "explicit-memory-location;not-stack-payload-width"
        if name == "PUSH imm32":
            properties["immediateEncoding"] = "32-bit-sign-extended-to-default-64;16-bit-under-66h"
        if name == "PUSH imm8":
            properties["immediateEncoding"] = "8-bit-sign-extended-to-operand-width"
    return "amd-entry:"+ident, [first,last], properties


def center(item):
    r = item["rect"]
    return (r[0]+r[2])/2, (r[1]+r[3])/2


def words(page):
    """Keep physical word identities, including words in merged PDF lines."""
    require(len({c["id"] for c in page["cells"]}) == len(page["cells"]), "native64 duplicate cell")
    result = []
    for cell in page["cells"]:
        require(cell["pdfPage"] == page["pdfPage"] and
                digest(cell["wordBoxes"]) == cell["wordBoxesSha256"] and
                cell["text"] == " ".join(w["text"] for w in cell["wordBoxes"]), "native64 word geometry differs")
        for i, word in enumerate(cell["wordBoxes"]):
            result.append(dict(word, sourceCell=cell["id"], wordIndex=i))
    return result


def ordered_text(items):
    # Source words in distinct columns must be separated before reading order
    # is restored. Cell reading order is not physical table order.
    return " ".join(w["text"] for w in sorted(items, key=lambda w:(round(w["rect"][1], 1), w["rect"][0])))


def parse_b5(page):
    require(page["pdfPage"] == 655, "native64 default table page differs")
    population = words(page)
    centers = sorted([w for w in population if w["text"] in {"yes", "no"} and 270 < center(w)[0] < 305], key=lambda w:center(w)[1])
    require(len(centers) == 21, "native64 default table row population differs")
    body = [w for w in population if 167 < w["rect"][1] < 515]
    rows = [[] for _ in centers]
    for word in body:
        y = center(word)[1]
        index = min(range(len(centers)), key=lambda n:abs(y-center(centers[n])[1]))
        require(abs(y-center(centers[index])[1]) <= 6.1, "native64 default table unowned word")
        rows[index].append(word)
    result = []
    for cells in rows:
        columns = [[], [], [], []]
        for word in cells:
            x = center(word)[0]
            col = 0 if x < 190 else 1 if x < 260 else 2 if x < 315 else 3
            columns[col].append(word)
        text = [ordered_text(c) for c in columns]
        require(all(text) and text[2] in {"yes", "no"}, "native64 default table column omission")
        result.append(dict(mnemonic=text[0], opcode=text[1], implicitlyReferencesRsp=text[2] == "yes",
                           description=text[3], sourceWords=cells))
    require([(r["mnemonic"], r["opcode"], r["implicitlyReferencesRsp"]) for r in result] == B5,
            "native64 default table reviewed rows differ")
    return result


def no_rex_relation(default_rows, source_entries):
    aliases = {"CALL":"CALL (Near)", "JMP":"JMP (Near)", "RET":"RET (Near)"}
    default = [aliases.get(r["mnemonic"], r["mnemonic"]) for r in default_rows]
    require(len(source_entries) == len(set(source_entries)) == 27 and len(default) == 21 and
            set(source_entries) == set(default) | set(SYSTEM_NO_REX) and not set(default) & set(SYSTEM_NO_REX),
            "native64 no-REX/default64 population or ownership differs")
    return dict(default64=default, otherFixedOrSystemEntries=list(SYSTEM_NO_REX),
                interpretation="No-REX availability does not imply one uniform operand-size override rule.")


def parse_mode_table(page, name):
    number, top, bottom, expected = MODE_TABLES[name]
    require(page["pdfPage"] == number, "native64 mode table page differs")
    population = words(page)
    opcode_cells = sorted([c for c in page["cells"] if 220 < c["rect"][0] < 265 and
                           top < c["rect"][1] < bottom], key=lambda c:center(c)[1])
    require(len(opcode_cells) == len(expected), "native64 mode table row population differs")
    rows = [[] for _ in opcode_cells]
    for word in population:
        if not top < word["rect"][1] < bottom:
            continue
        index = min(range(len(rows)), key=lambda n:abs(center(word)[1]-center(opcode_cells[n])[1]))
        require(abs(center(word)[1]-center(opcode_cells[index])[1]) <= 12.1, "native64 mode table unowned word")
        rows[index].append(word)
    result = []
    for row in rows:
        columns = [[w for w in row if (0 if center(w)[0]<215 else 1 if center(w)[0]<275 else 2) == col] for col in range(3)]
        text = [ordered_text(c) for c in columns]
        require(all(text), "native64 mode table column omission")
        result.append(dict(mnemonic=text[0],opcode=text[1],description=text[2],sourceWords=row,
            disposition="reassigned-encoding;old-operation-unavailable" if name == "reassigned64" else "old-operation-invalid-in-selected-mode",
            encodingDomainComplete=False))
    require([(r["mnemonic"],r["opcode"]) for r in result] == expected, "native64 mode table reviewed rows differ")
    return result


def parse_b1(page, headings):
    """Reconstruct every body word and every repeated physical note occurrence.

    Heading identities are an independently reviewed per-page input, not the
    parser's regex match count. Some table rows are aliases or span multiple
    opcode subrows; the output retains that granularity and makes no form count.
    """
    require(628 <= page["pdfPage"] <= 652, "native64 size table page differs")
    population = words(page)
    by_id = {c["id"]:c for c in page["cells"]}
    require(type(headings) is list and headings and len(headings) == len({h["id"] for h in headings}),
            "native64 size table heading denominator differs")
    markers = []
    for h in headings:
        require(set(h) == {"id", "text"} and h["id"] in by_id and by_id[h["id"]]["text"] == h["text"],
                "native64 size table heading source differs")
        cell = by_id[h["id"]]
        require(cell["rect"][0] < 70, "native64 size table heading column differs")
        markers.append(cell)
    require(markers == sorted(markers, key=lambda c:c["rect"][1]), "native64 size table heading order differs")
    source_headings = [c["id"] for c in sorted(page["cells"], key=lambda c:c["rect"][1])
                       if c["rect"][0] < 70 and c["rect"][1] > 150 and (re.match(r"^[A-Za-z0-9(), /]+(?:—| - |Q- Store)", c["text"])
                       or c["text"] in {"CDQ", "CDQE (new mnemonic)", "CDWE", "CQO (new mnemonic)"})]
    require(source_headings == [h["id"] for h in headings], "native64 size table omitted/extra source heading")
    note = [c for c in page["cells"] if c["text"] == "Notes:"]
    require(len(note) == 1, "native64 size table notes omitted/duplicated")
    ceiling = note[0]["rect"][1]
    # Right-hand text can start above the instruction heading. Keep it. These
    # are physical bands only: vertically merged source cells (LOOP, INT) do
    # not establish semantic row ownership or inheritance.
    header_ids = {c["id"] for c in page["cells"] if c["text"] in {
        "Instruction and", "Opcode (hex) 1", "Type of", "Operation 2", "Default", "Operand", "Size 3",
        "For 32-Bit", "For 64-Bit", "Operand Size 4"}}
    body = [w for w in population if markers[0]["rect"][1]-6.1 <= w["rect"][1] < ceiling and w["sourceCell"] not in header_ids]
    buckets = [[] for _ in markers]
    for word in body:
        eligible = [n for n,h in enumerate(markers) if h["rect"][1]-6.1 <= word["rect"][1]]
        buckets[max(eligible)].append(word)
    result = []
    for heading, body_words in zip(markers, buckets):
        columns = [[] for _ in range(5)]
        for word in body_words:
            x = center(word)[0]
            column = 0 if x < 250 else 1 if x < 317 else 2 if x < 382 else 3 if x < 467 else 4
            columns[column].append(word)
        require(columns[0], "native64 size table empty instruction row")
        result.append(dict(heading=dict(id=heading["id"],text=heading["text"]),
            physicalColumns=[ordered_text(c) for c in columns], sourceWords=body_words,
            state="checked-physical-band;semantic-row-ownership-separate"))
    notes = [w for w in population if ceiling <= w["rect"][1] < 710]
    # Physical note references 1..6 must survive on every continuation page.
    require([w["text"] for w in notes if w["rect"][0] < 85 and re.fullmatch(r"[1-6]\.", w["text"])] ==
            [f"{i}." for i in range(1,7)], "native64 size table repeated note population differs")
    return dict(pdfPage=page["pdfPage"], sourceBands=result, notes=notes,
                bodyWordCount=len(body), bodyWordsSha256=digest(body))


def assess(pages, no_rex_entries, source_entries):
    pack = entry.read(INPUT)
    entry.migration.corpus.fields(pack, {"schema", "sourcePolicySha256", "executionModes", "publication", "pdfSha256",
        "pages", "sizeTableHeadings", "default64Qualifications"}, "native64 reviewed inventory")
    require(pack["schema"] == "ariadne.amd64-native64-inventory/v1" and pack["executionModes"] == ["long-64"] and
            pack["sourcePolicySha256"] == entry.migration.sha(adoption.INPUT) and pack["publication"] == "24594" and
            pack["pdfSha256"] == next(d["pdfSha256"] for d in adoption.selected_documents() if d["publication"] == "24594"),
            "native64 source identity/scope differs")
    by_number = {p["pdfPage"]:p for p in pages}
    owner_pages = {n for _,first,last in OWNERS.values() for n in range(first,last+1)}
    require(len(by_number) == len(pages) and set(pack["pages"]) == {str(n) for n in set(range(627,657)) | owner_pages} and
            set(pack["sizeTableHeadings"]) == {str(n) for n in range(628,653)}, "native64 source page population differs")
    for number, pin in pack["pages"].items():
        require(int(number) in by_number and digest(by_number[int(number)]["cells"]) == pin,
                "native64 actual source page differs: "+number)
    default = parse_b5(by_number[655])
    relation = no_rex_relation(default, no_rex_entries)
    size = [parse_b1(by_number[n], pack["sizeTableHeadings"][str(n)]) for n in range(628,653)]
    qualifications = qualify_default64(pack["default64Qualifications"], by_number, default, source_entries)
    mode_tables = {name:parse_mode_table(by_number[spec[0]],name) for name,spec in MODE_TABLES.items()}
    return dict(schema="ariadne.amd64-native64-assessment/v1", executionModes=["long-64"],
        publication="24594", pdfSha256=pack["pdfSha256"], default64=default, noRexRelation=relation,
        default64Qualifications=qualifications, sizeTable=size,
        modeTables=mode_tables,
        sizeTableHeadings=sum(len(p["sourceBands"]) for p in size),
        sizeTableBodyWords=sum(p["bodyWordCount"] for p in size), repeatedSizeTableNotes=len(size)*6,
        state="checked-source-inventories;full-C-inventory-incomplete",
        remaining=["instruction-specific B1 qualifications", "mandatory-prefix form inventory", "LOCK/REP form inventory"],
        constraintsComplete=False, legalDomainsComplete=False, productionAdmission=False)


def qualify_default64(qualifications, pages, default_rows, source_entries):
    require(len(qualifications) == len(default_rows) and [q["mnemonic"] for q in qualifications] == [r["mnemonic"] for r in default_rows],
            "native64 instruction qualification omitted/reordered")
    result = []
    for q in qualifications:
        require(set(q) == {"mnemonic", "owner", "ownerPages", "clauses", "properties"}, "native64 qualification fields differ")
        owner, extent, properties = qualification_contract(q["mnemonic"])
        require(q["owner"] == owner and q["ownerPages"] == extent and canonical(q["properties"]) == canonical(properties),
                "native64 reviewed qualification contract differs")
        family = q["mnemonic"].split()[0].split(",")[0]
        key = family if family in OWNERS else q["mnemonic"]
        require([c["cells"] for c in q["clauses"]] ==
                [[f"pdf:{p}:cell:{n}" for n in range(first,last+1)] for p,first,last in QUALIFICATION_CELLS[key]],
                "native64 instruction qualification clause omitted/swapped")
        matching = [e for e in source_entries if e["id"] == owner]
        require(len(matching) == 1 and [matching[0]["pdfPage"], matching[0]["pdfEndPage"]] == extent,
                "native64 instruction source owner differs")
        first, last = q["ownerPages"]
        require(0 < first <= last < 627 and q["clauses"], "native64 qualification owner differs")
        observations = []
        for clause in q["clauses"]:
            require(set(clause) == {"cells", "text"} and clause["cells"], "native64 qualification clause fields differ")
            observed = []
            for key in clause["cells"]:
                match = re.fullmatch(r"pdf:(\d+):cell:(\d+)", key)
                require(match is not None and first <= int(match[1]) <= last and int(match[1]) in pages,
                        "native64 qualification clause owner/page differs")
                matches = [c for c in pages[int(match[1])]["cells"] if c["id"] == key]
                require(len(matches) == 1, "native64 qualification clause missing/duplicate")
                words(pages[int(match[1])])
                observed.append(matches[0])
            require(" ".join(c["text"] for c in observed) == clause["text"], "native64 instruction clause source differs")
            observations.append(dict(clause, sourceCells=copy.deepcopy(observed)))
        result.append(dict(q, clauses=observations))
    return result
