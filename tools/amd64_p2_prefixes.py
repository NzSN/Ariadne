#!/usr/bin/env python3
"""Instruction-owned LOCK/REP applicability, separate from prefix byte legality.

The reviewed source selectors retain every register, memory and old-mode form.
Memory-writing predicates cannot be widened to all uses of a mnemonic. F2/F3
opcode selectors in media instructions remain a different required inventory.
"""
import copy
import re

import amd64_p2_native64 as native
from amd64_inventory_xed import canonical, digest

entry = native.entry
ROOT = entry.ROOT
INPUT = ROOT/"tests/bap/fixtures/source-migration/p2-lock-repeat-v1.json"
require = entry.require
# Exact owner, physical clause cells, and independently reviewed form counts.
LOCK = {
    "ADC": ("0004",127,17,18,19), "ADD": ("0006",131,14,15,19),
    "AND": ("0008",135,27,28,19), "BTC": ("0027",170,15,17,6),
    "BTR": ("0028",172,15,17,6), "BTS": ("0029",174,15,17,6),
    "CMPXCHG": ("0045",209,13,14,4), "CMPXCHG8B CMPXCHG16B": ("0046",211,18,19,2),
    "DEC": ("0051",220,8,9,6), "INC": ("0057",232,9,10,6),
    "NEG": ("0094",312,9,10,4), "NOT": ("0096",315,7,8,4), "OR": ("0097",316,10,11,19),
    "SBB": ("0128",374,14,15,19), "SUB": ("0142",398,11,12,19),
    "XADD": ("0149",410,8,9,4), "XCHG": ("0150",412,5,8,14), "XOR": ("0153",415,8,9,19),
}
REPEAT = {
    "CMPS": ("0044",207,26,28,[8,16,32,64]), "INS": ("0058",234,19,27,[8,16,32]),
    "LODS": ("0071",267,20,25,[8,16,32,64]), "MOVS": ("0087",301,20,24,[8,16,32,64]),
    "OUTS": ("0099",320,19,21,[8,16,32]), "SCAS": ("0129",376,20,23,[8,16,32,64]),
    "STOS": ("0141",396,17,18,[8,16,32,64]),
}
COMMON = {"address-size": (51,21,66), "lock-list": (54,3,6), "repeat-count": (54,9,17),
          "repe": (55,18,22), "repne": (55,42,47)}


def source_selectors(name):
    """Reviewed source-table operand selectors, not a byte grammar."""
    if name in {"ADC","ADD","AND","OR","SBB","SUB","XOR"}:
        operands = ["AL, imm8","AX, imm16","EAX, imm32","RAX, imm32"]
        operands += [f"reg/mem{b}, imm{min(b,32)}" for b in (8,16,32,64)]
        operands += [f"reg/mem{b}, imm8" for b in (16,32,64)]
        operands += [f"reg/mem{b}, reg{b}" for b in (8,16,32,64)]
        operands += [f"reg{b}, reg/mem{b}" for b in (8,16,32,64)]
    elif name in {"BTC","BTR","BTS"}:
        operands = [f"reg/mem{b}, reg{b}" for b in (16,32,64)] + [f"reg/mem{b}, imm8" for b in (16,32,64)]
    elif name in {"CMPXCHG","XADD"}:
        operands = [f"reg/mem{b}, reg{b}" for b in (8,16,32,64)]
    elif name in {"CMPXCHG8B","CMPXCHG16B"}:
        operands = ["mem64" if name == "CMPXCHG8B" else "mem128"]
    elif name in {"INC","DEC","NEG","NOT"}:
        operands = [f"reg/mem{b}" for b in (8,16,32,64)]
        if name in {"INC","DEC"}: operands += ["reg16","reg32"]
    elif name == "XCHG":
        operands = [item for acc,b in (("AX",16),("EAX",32),("RAX",64)) for item in (f"{acc}, reg{b}",f"reg{b}, {acc}")]
        operands += [item for b in (8,16,32,64) for item in (f"reg/mem{b}, reg{b}",f"reg{b}, reg/mem{b}")]
    else:
        raise ValueError("LOCK instruction has no reviewed owner")
    return [name+" "+o for o in operands]


def lock_memory_positions(selector):
    require(type(selector) is str and " " in selector, "LOCK selector is malformed")
    name, operands = selector.split(" ",1)
    require(selector in source_selectors(name), "LOCK selector is outside reviewed source forms")
    operands = [o.strip() for o in operands.split(",")]
    require(all(re.fullmatch(r"(?:reg/mem|reg|mem|imm)(?:8|16|32|64|128)|AL|AX|EAX|RAX",o) for o in operands),
            "LOCK selector operand is unsupported")
    possible = [i for i,o in enumerate(operands) if o.startswith(("reg/mem","mem"))]
    return [i for i in possible if i == 0 or name == "XCHG"]


def lock_applicable(selector, memory_positions, execution_mode="long-64"):
    require(execution_mode == "long-64", "LOCK inventory requires native-64 execution")
    eligible = lock_memory_positions(selector)
    operands = [o.strip() for o in selector.split(" ",1)[1].split(",")]
    require(type(memory_positions) is list and all(type(p) is int and 0 <= p < len(operands) for p in memory_positions) and
            len(set(memory_positions)) == len(memory_positions), "LOCK operand positions differ")
    require(all(operands[p].startswith(("reg/mem","mem")) for p in memory_positions), "LOCK memory position is not a memory alternative")
    return bool(set(eligible) & set(memory_positions))


def repeat_contract(name):
    require(name in REPEAT, "repeat instruction has no reviewed owner")
    compare = name in {"CMPS","SCAS"}
    return dict(prefixes=["f3-repe-repz","f2-repne-repnz"] if compare else ["f3-rep"],
        operandBits=REPEAT[name][4], countBits=[64,32], countSelectedBy="address-size;not-operand-size",
        zf="post-iteration-repeat-condition" if compare else "not-a-repeat-condition",
        zeroCountAndIteration="requires-separate-contract", encodingRole="repeat;not-media-opcode-selection",
        faultRestart="requires-separate-contract", sourceScopeConflict="p2:repeat-note-disagreement")


def clause(record, pages, expected_cells):
    require(set(record) == {"cells","text"} and record["cells"] == expected_cells,
            "prefix instruction clause owner/population differs")
    actual = []
    for key in expected_cells:
        number = int(key.split(":")[1])
        require(number in pages, "prefix actual source page missing")
        native.words(pages[number])
        matches = [c for c in pages[number]["cells"] if c["id"] == key]
        require(len(matches) == 1, "prefix actual source clause missing/duplicate")
        actual.append(matches[0])
    require(" ".join(c["text"] for c in actual) == record["text"], "prefix instruction clause source differs")
    return copy.deepcopy(actual)


def assess_lock_owner(name, record, pages, entries, source_rows):
    ident,page,first,last,count = LOCK[name]
    owner = "amd-entry:"+ident
    require(set(record) == {"owner","clause","forms"} and record["owner"] == owner, "LOCK reviewed owner differs")
    selected = [e for e in entries if e["id"] == owner]
    require(len(selected) == 1 and selected[0]["title"] == name and selected[0]["pdfPage"] == page,
            "LOCK actual instruction owner differs")
    source_clause = clause(record["clause"],pages,[f"pdf:{page}:cell:{n}" for n in range(first,last+1)])
    rows = [r for r in source_rows if r["entryIds"] == [owner]]
    require(len(rows) == count and [r["mnemonic"] for r in rows] ==
            [s for instruction in name.split() for s in source_selectors(instruction)] == [f["selector"] for f in record["forms"]],
            "LOCK source form omitted/reordered")
    checked = []
    for r,f in zip(rows,record["forms"]):
        require(set(f) == {"selector","sourceCell","memoryPositions"} and
                canonical(f["memoryPositions"]) == canonical(lock_memory_positions(r["mnemonic"])),
                "LOCK memory-writing predicate differs")
        actual = [c for p in range(selected[0]["pdfPage"],selected[0]["pdfEndPage"]+1)
                  for c in pages[p]["cells"] if c["id"] == f["sourceCell"]]
        require(len(actual) == 1 and actual[0]["text"] == f["selector"] and 68 < actual[0]["rect"][0] < 71,
                "LOCK selector physical source owner differs")
        checked.append(dict(f, originalRow=copy.deepcopy(r), sourceCell=copy.deepcopy(actual[0]),
            registerAlternativeLock=False, automaticallyLockedMemory=(r["mnemonic"].startswith("XCHG ") and bool(f["memoryPositions"])),
            executionModeState="old-single-byte-form-reassigned-to-REX" if name in {"INC","DEC"} and not f["memoryPositions"] else "native64-source-form",
            encodingAndFeatureLegality="separate-P3-obligation"))
    return dict(owner=owner,sourceClause=source_clause,forms=checked,sourceScopeConflict="p2:lock-list-disagreement")


def assess(pages, normalized):
    pack = entry.read(INPUT)
    entry.migration.corpus.fields(pack, {"schema","publication","pdfSha256","executionModes","sourcePolicySha256",
        "pages","lock","repeat","commonClauses","sourceRowsSha256"}, "prefix inventory")
    require(pack["schema"] == "ariadne.amd64-lock-repeat-inventory/v1" and pack["publication"] == "24594" and
        pack["executionModes"] == ["long-64"] and pack["sourcePolicySha256"] == entry.migration.sha(native.adoption.INPUT) and
        pack["pdfSha256"] == next(d["pdfSha256"] for d in native.adoption.selected_documents() if d["publication"] == "24594"),
        "prefix inventory source identity/scope differs")
    by_number = {p["pdfPage"]:p for p in pages}
    require(len(by_number) == len(pages), "prefix duplicate actual page")
    owned_entries = {"amd-entry:"+value[0] for value in list(LOCK.values())+list(REPEAT.values())}
    entries = [e for e in normalized["entries"] if e["id"] in owned_entries]
    require(len(entries) == len(owned_entries), "prefix instruction source owners omitted/duplicate")
    wanted_pages = {p for e in entries for p in range(e["pdfPage"],e["pdfEndPage"]+1)} | {v[0] for v in COMMON.values()}
    require(set(pack["pages"]) == {str(p) for p in wanted_pages}, "prefix reviewed page denominator differs")
    for key,pin in pack["pages"].items():
        require(int(key) in by_number and digest(by_number[int(key)]["cells"]) == pin,
                "prefix actual source page differs: "+key)
    source_rows = [r for r in normalized["rows"] if set(r["entryIds"]) & owned_entries]
    require(digest(source_rows) == pack["sourceRowsSha256"], "prefix source row population differs")
    require(set(pack["lock"]) == set(LOCK) and set(pack["repeat"]) == set(REPEAT), "prefix owner population differs")
    require(set(pack["commonClauses"]) == set(COMMON), "prefix common clauses omitted/extra")
    common = {name:clause(pack["commonClauses"][name],by_number,[f"pdf:{p}:cell:{i}" for i in range(first,last+1)])
              for name,(p,first,last) in COMMON.items()}
    lock = {name:assess_lock_owner(name,pack["lock"][name],by_number,entries,source_rows) for name in LOCK}
    repeat = {}
    for name,(ident,page,first,last,_) in REPEAT.items():
        record = pack["repeat"][name]
        owner = "amd-entry:"+ident
        require(set(record) == {"owner","clause","properties"} and record["owner"] == owner and
                canonical(record["properties"]) == canonical(repeat_contract(name)), "repeat instruction contract differs")
        selected = [e for e in entries if e["id"] == owner]
        require(len(selected) == 1 and selected[0]["title"].split()[0] == name and selected[0]["pdfPage"] == page,
                "repeat actual instruction owner differs")
        source_clause = clause(record["clause"],by_number,[f"pdf:{page}:cell:{n}" for n in range(first,last+1)])
        repeat[name] = dict(record,sourceClause=source_clause)
    return dict(schema="ariadne.amd64-lock-repeat-assessment/v1", executionModes=["long-64"], lock=lock, repeat=repeat, commonClauses=common,
        lockSourceSelectors=sum(len(v["forms"]) for v in lock.values()), lockSourceMnemonics=sum(len(k.split()) for k in lock),
        state="checked-instruction-owned-scope;source-list-conflicts-retained",
        remaining=["p2:lock-list-disagreement","p2:repeat-note-disagreement","media-mandatory-prefix-inventory"],
        completePrefixInventory=False, productionAdmission=False)
