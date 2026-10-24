#!/usr/bin/env python3
"""Instruction-owned x87/3DNow prefix and width source forms.

These row selectors are not byte grammars. Continuation tables and wrapped
operands are reconstructed independently of the earlier normalized row list.
The earlier list remains untouched and omissions are reported explicitly.
"""
import copy
import re

import amd64_p2_native64 as native
from amd64_inventory_xed import canonical, digest

entry = native.entry
require = entry.require
INPUT = native.INPUT.parent / "p2-legacy-media-forms-v1.json"
THREEDNOW = set("FEMMS PAVGUSB PF2ID PF2IW PFACC PFADD PFCMPEQ PFCMPGE PFCMPGT PFMAX PFMIN PFMUL PFNACC PFPNACC PFRCP PFRCPIT1 PFRCPIT2 PFRSQIT1 PFRSQRT PFSUB PFSUBR PI2FD PI2FW PMULHRW PSWAPD".split())
# Independently reviewed selector/opcode population. A bare mnemonic cannot
# stand in for wrapped environment operands. PDF 265 continues FCOM's table
# without repeating its header and therefore supplies two extra source rows.
SPECS = {
'FEMMS': ('amd-entry:0007', 48, 49, [('FEMMS', '0F 0E')]),
'PAVGUSB': ('amd-entry:0032', 100, 101, [('PAVGUSB mmx1, mmx2/mem64', '0F 0F /r BF')]),
'PF2ID': ('amd-entry:0041', 118, 119, [('PF2ID mmx1, mmx2/mem64', '0F 0F /r 1D')]),
'PF2IW': ('amd-entry:0042', 120, 121, [('PF2IW mmx1, mmx2/mem64', '0F 0F /r 1C')]),
'PFACC': ('amd-entry:0043', 122, 123, [('PFACC mmx1, mmx2/mem64', '0F 0F /r AE')]),
'PFADD': ('amd-entry:0044', 124, 125, [('PFADD mmx1, mmx2/mem64', '0F 0F /r 9E')]),
'PFCMPEQ': ('amd-entry:0045', 126, 127, [('PFCMPEQ mmx1, mmx2/mem64', '0F 0F /r B0')]),
'PFCMPGE': ('amd-entry:0046', 128, 130, [('PFCMPGE mmx1, mmx2/mem64', '0F 0F /r 90')]),
'PFCMPGT': ('amd-entry:0047', 131, 132, [('PFCMPGT mmx1, mmx2/mem64', '0F 0F /r A0')]),
'PFMAX': ('amd-entry:0048', 133, 134, [('PFMAX mmx1, mmx2/mem64', '0F 0F /r A4')]),
'PFMIN': ('amd-entry:0049', 135, 136, [('PFMIN mmx1, mmx2/mem64', '0F 0F /r 94')]),
'PFMUL': ('amd-entry:0050', 137, 138, [('PFMUL mmx1, mmx2/mem64', '0F 0F /r B4')]),
'PFNACC': ('amd-entry:0051', 139, 141, [('PFNACC mmx1, mmx2/mem64', '0F 0F /r 8A')]),
'PFPNACC': ('amd-entry:0052', 142, 144, [('PFPNACC mmx1, mmx2/mem64', '0F 0F /r 8E')]),
'PFRCP': ('amd-entry:0053', 145, 147, [('PFRCP mmx1, mmx2/mem64', '0F 0F /r 96')]),
'PFRCPIT1': ('amd-entry:0054', 148, 150, [('PFRCPIT1 mmx1, mmx2/mem64', '0F 0F /r A6')]),
'PFRCPIT2': ('amd-entry:0055', 151, 153, [('PFRCPIT2 mmx1, mmx2/mem64', '0F 0F /r B6')]),
'PFRSQIT1': ('amd-entry:0056', 154, 156, [('PFRSQIT1 mmx1, mmx2/mem64', '0F 0F /r A7')]),
'PFRSQRT': ('amd-entry:0057', 157, 159, [('PFRSQRT mmx1, mmx2/mem64', '0F 0F /r 97')]),
'PFSUB': ('amd-entry:0058', 160, 161, [('PFSUB mmx1, mmx2/mem64', '0F 0F /r 9A')]),
'PFSUBR': ('amd-entry:0059', 162, 163, [('PFSUBR mmx1, mmx2/mem64', '0F 0F /r AA')]),
'PI2FD': ('amd-entry:0060', 164, 165, [('PI2FD mmx1, mmx2/mem64', '0F 0F /r 0D')]),
'PI2FW': ('amd-entry:0061', 166, 167, [('PI2FW mmx1, mmx2/mem64', '0F 0F /r 0C')]),
'PMULHRW': ('amd-entry:0069', 182, 183, [('PMULHRW mmx1, mmx2/mem64', '0F 0F /r B7')]),
'PSWAPD': ('amd-entry:0093', 231, 232, [('PSWAPD mmx1, mmx2/mem64', '0F 0F /r BB')]),
'F2XM1': ('amd-entry:0101', 248, 249, [('F2XM1', 'D9 F0')]),
'FABS': ('amd-entry:0102', 250, 251, [('FABS', 'D9 E1')]),
'FADD FADDP FIADD': ('amd-entry:0103', 252, 254, [('FADD ST(0),ST(i)', 'D8 C0+i'), ('FADD ST(i),ST(0)', 'DC C0+i'), ('FADD mem32real', 'D8 /0'), ('FADD mem64real', 'DC /0'), ('FADDP', 'DE C1'), ('FADDP ST(i),ST(0)', 'DE C0+i'), ('FIADD mem16int', 'DE /0'), ('FIADD mem32int', 'DA /0')]),
'FBLD': ('amd-entry:0104', 255, 256, [('FBLD mem80dec', 'DF /4')]),
'FBSTP': ('amd-entry:0105', 257, 258, [('FBSTP mem80dec', 'DF /6')]),
'FCHS': ('amd-entry:0106', 259, 259, [('FCHS', 'D9 E0')]),
'FCLEX (FNCLEX)': ('amd-entry:0107', 260, 261, [('FCLEX', '9B DB E2'), ('FNCLEX', 'DB E2')]),
'FCMOVcc': ('amd-entry:0108', 262, 263, [('FCMOVB ST(0),ST(i)', 'DA C0+i'), ('FCMOVBE ST(0),ST(i)', 'DA D0+i'), ('FCMOVE ST(0),ST(i)', 'DA C8+i'), ('FCMOVNB ST(0),ST(i)', 'DB C0+i'), ('FCMOVNBE ST(0),ST(i)', 'DB D0+i'), ('FCMOVNE ST(0),ST(i)', 'DB C8+i'), ('FCMOVNU ST(0),ST(i)', 'DB D8+i'), ('FCMOVU ST(0),ST(i)', 'DA D8+i')]),
'FCOM FCOMP FCOMPP': ('amd-entry:0109', 264, 266, [('FCOM', 'D8 D1'), ('FCOM ST(i)', 'D8 D0+i'), ('FCOM mem32real', 'D8 /2'), ('FCOM mem64real', 'DC /2'), ('FCOMP', 'D8 D9'), ('FCOMP ST(i)', 'D8 D8+i'), ('FCOMP mem32real', 'D8 /3'), ('FCOMP mem64real', 'DC /3'), ('FCOMPP', 'DE D9')]),
'FCOMI FCOMIP': ('amd-entry:0110', 267, 268, [('FCOMI ST(0),ST(i)', 'DB F0+i'), ('FCOMIP ST(0),ST(i)', 'DF F0+i')]),
'FCOS': ('amd-entry:0111', 269, 270, [('FCOS', 'D9 FF')]),
'FDECSTP': ('amd-entry:0112', 271, 272, [('FDECSTP', 'D9 F6')]),
'FDIV FDIVP FIDIV': ('amd-entry:0113', 273, 275, [('FDIV ST(0),ST(i)', 'D8 F0+i'), ('FDIV ST(i),ST(0)', 'DC F8+i'), ('FDIV mem32real', 'D8 /6'), ('FDIV mem64real', 'DC /6'), ('FDIVP', 'DE F9'), ('FDIVP ST(i),ST(0)', 'DE F8+i'), ('FIDIV mem16int', 'DE /6'), ('FIDIV mem32int', 'DA /6')]),
'FDIVR FDIVRP FIDIVR': ('amd-entry:0114', 276, 278, [('FDIVR ST(0),ST(i)', 'D8 F8+i'), ('FDIVR ST(i), ST(0)', 'DC F0+i'), ('FDIVR mem32real', 'D8 /7'), ('FDIVR mem64real', 'DC /7'), ('FDIVRP', 'DE F1'), ('FDIVRP ST(i), ST(0)', 'DE F0 +i'), ('FIDIVR mem16int', 'DE /7'), ('FIDIVR mem32int', 'DA /7')]),
'FFREE': ('amd-entry:0115', 279, 279, [('FFREE ST(i)', 'DD C0+i')]),
'FICOM FICOMP': ('amd-entry:0116', 280, 281, [('FICOM mem16int', 'DE /2'), ('FICOM mem32int', 'DA /2'), ('FICOMP mem16int', 'DE /3'), ('FICOMP mem32int', 'DA /3')]),
'FILD': ('amd-entry:0117', 282, 283, [('FILD mem16int', 'DF /0'), ('FILD mem32int', 'DB /0'), ('FILD mem64int', 'DF /5')]),
'FINCSTP': ('amd-entry:0118', 284, 285, [('FINCSTP', 'D9 F7')]),
'FINIT FNINIT': ('amd-entry:0119', 286, 287, [('FINIT', '9B DB E3'), ('FNINIT', 'DB E3')]),
'FIST FISTP': ('amd-entry:0120', 288, 290, [('FIST mem16int', 'DF /2'), ('FIST mem32int', 'DB /2'), ('FISTP mem16int', 'DF /3'), ('FISTP mem32int', 'DB /3'), ('FISTP mem64int', 'DF /7')]),
'FISTTP': ('amd-entry:0121', 291, 292, [('FISTTP mem16int', 'DF /1'), ('FISTTP mem32int', 'DB /1'), ('FISTTP mem64int', 'DD /1')]),
'FLD': ('amd-entry:0122', 293, 294, [('FLD ST(i)', 'D9 C0+i'), ('FLD mem32real', 'D9 /0'), ('FLD mem64real', 'DD /0'), ('FLD mem80real', 'DB /5')]),
'FLD1': ('amd-entry:0123', 295, 295, [('FLD1', 'D9 E8')]),
'FLDCW': ('amd-entry:0124', 296, 297, [('FLDCW mem2env', 'D9 /5')]),
'FLDENV': ('amd-entry:0125', 298, 299, [('FLDENV mem14/28env', 'D9 /4')]),
'FLDL2E': ('amd-entry:0126', 300, 300, [('FLDL2E', 'D9 EA')]),
'FLDL2T': ('amd-entry:0127', 301, 301, [('FLDL2T', 'D9 E9')]),
'FLDLG2': ('amd-entry:0128', 302, 302, [('FLDLG2', 'D9 EC')]),
'FLDLN2': ('amd-entry:0129', 303, 303, [('FLDLN2', 'D9 ED')]),
'FLDPI': ('amd-entry:0130', 304, 304, [('FLDPI', 'D9 EB')]),
'FLDZ': ('amd-entry:0131', 305, 305, [('FLDZ', 'D9 EE')]),
'FMUL FMULP FIMUL': ('amd-entry:0132', 306, 308, [('FMUL ST(0),ST(i)', 'D8 C8+i'), ('FMUL ST(i),ST(0)', 'DC C8+i'), ('FMUL mem32real', 'D8 /1'), ('FMUL mem64real', 'DC /1'), ('FMULP', 'DE C9'), ('FMULP ST(i),ST(0)', 'DE C8+i'), ('FIMUL mem16int', 'DE /1'), ('FIMUL mem32int', 'DA /1')]),
'FNOP': ('amd-entry:0133', 309, 309, [('FNOP', 'D9 D0')]),
'FPATAN': ('amd-entry:0134', 310, 311, [('FPATAN', 'D9 F3')]),
'FPREM': ('amd-entry:0135', 312, 313, [('FPREM', 'D9 F8')]),
'FPREM1': ('amd-entry:0136', 314, 315, [('FPREM1', 'D9 F5')]),
'FPTAN': ('amd-entry:0137', 316, 317, [('FPTAN', 'D9 F2')]),
'FRNDINT': ('amd-entry:0138', 318, 319, [('FRNDINT', 'D9 FC')]),
'FRSTOR': ('amd-entry:0139', 320, 321, [('FRSTOR mem94/108env', 'DD /4')]),
'FSAVE FNSAVE': ('amd-entry:0140', 322, 323, [('FSAVE mem94/108env', '9B DD /6'), ('FNSAVE mem94/108env', 'DD /6')]),
'FSCALE': ('amd-entry:0141', 324, 325, [('FSCALE', 'D9 FD')]),
'FSIN': ('amd-entry:0142', 326, 327, [('FSIN', 'D9 FE')]),
'FSINCOS': ('amd-entry:0143', 328, 329, [('FSINCOS', 'D9 FB')]),
'FSQRT': ('amd-entry:0144', 330, 331, [('FSQRT', 'D9 FA')]),
'FST FSTP': ('amd-entry:0145', 332, 333, [('FST ST(i)', 'DD D0+i'), ('FST mem32real', 'D9 /2'), ('FST mem64real', 'DD /2'), ('FSTP ST(i)', 'DD D8+i'), ('FSTP mem32real', 'D9 /3'), ('FSTP mem64real', 'DD /3'), ('FSTP mem80real', 'DB /7')]),
'FSTCW (FNSTCW)': ('amd-entry:0146', 334, 335, [('FSTCW mem2env', '9B D9 /7'), ('FNSTCW mem2env', 'D9 /7')]),
'FSTENV (FNSTENV)': ('amd-entry:0147', 336, 337, [('FSTENV mem14/28env', '9B D9 /6'), ('FNSTENV mem14/28env', 'D9 /6')]),
'FSTSW (FNSTSW)': ('amd-entry:0148', 338, 339, [('FSTSW AX', '9B DF E0'), ('FSTSW mem2env', '9B DD /7'), ('FNSTSW AX', 'DF E0'), ('FNSTSW mem2env', 'DD /7')]),
'FSUB FSUBP FISUB': ('amd-entry:0149', 340, 342, [('FSUB ST(0),ST(i)', 'D8 E0+i'), ('FSUB ST(i),ST(0)', 'DC E8+i'), ('FSUB mem32real', 'D8 /4'), ('FSUB mem64real', 'DC /4'), ('FSUBP', 'DE E9'), ('FSUBP ST(i),ST(0)', 'DE E8+i'), ('FISUB mem16int', 'DE /4'), ('FISUB mem32int', 'DA /4')]),
'FSUBR FSUBRP FISUBR': ('amd-entry:0150', 343, 345, [('FSUBR ST(0),ST(i)', 'D8 E8+i'), ('FSUBR ST(i),ST(0)', 'DC E0+i'), ('FSUBR mem32real', 'D8 /5'), ('FSUBR mem64real', 'DC /5'), ('FSUBRP', 'DE E1'), ('FSUBRP ST(i),ST(0)', 'DE E0+i'), ('FISUBR mem16int', 'DE /5'), ('FISUBR mem32int', 'DA /5')]),
'FTST': ('amd-entry:0151', 346, 346, [('FTST', 'D9 E4')]),
'FUCOM FUCOMP FUCOMPP': ('amd-entry:0152', 347, 348, [('FUCOM', 'DD E1'), ('FUCOM ST(i)', 'DD E0+i'), ('FUCOMP', 'DD E9'), ('FUCOMP ST(i)', 'DD E8+i'), ('FUCOMPP', 'DA E9')]),
'FUCOMI FUCOMIP': ('amd-entry:0153', 349, 350, [('FUCOMI ST(0),ST(i)', 'DB E8+i'), ('FUCOMIP ST(0),ST(i)', 'DF E8+i')]),
'FWAIT (WAIT)': ('amd-entry:0154', 351, 351, [('FWAIT', '9B')]),
'FXAM': ('amd-entry:0155', 352, 353, [('FXAM', 'D9 E5')]),
'FXCH': ('amd-entry:0156', 354, 354, [('FXCH', 'D9 C9'), ('FXCH ST(i)', 'D9 C8+i')]),
'FXTRACT': ('amd-entry:0157', 355, 356, [('FXTRACT', 'D9 F4')]),
'FYL2X': ('amd-entry:0158', 357, 358, [('FYL2X', 'D9 F1')]),
'FYL2XP1': ('amd-entry:0159', 359, 362, [('FYL2XP1', 'D9 F9')]),
}
ENVIRONMENT = {"FLDENV": (14,28), "FSTENV": (14,28), "FNSTENV": (14,28),
               "FRSTOR": (94,108), "FSAVE": (94,108), "FNSAVE": (94,108)}
ENV_CLAUSES = {298:(7,14), 320:(6,12), 322:(6,12), 336:(9,15)}


def word_id(word):
    return word["sourceCell"]+"/word:"+str(word["wordIndex"])


def lexical(value):
    return re.sub(r"\s+", " ", value).strip()


def source_tables(pages, owner):
    """Only reviewed physical table shapes; no neighbor encoding inheritance."""
    ident, first, last, expected = SPECS[owner]
    names = {selector.split()[0] for selector, _ in expected}
    tables = []
    for page in pages:
        number = page["pdfPage"]
        if not first <= number <= last:
            continue
        words = native.words(page)
        headers = [w for w in words if w["text"] == "Mnemonic" and 60 < w["rect"][0] < 80]
        if number == 265:
            require(owner == "FCOM FCOMP FCOMPP" and not headers, "x87 continuation owner/header differs")
            headers = [dict(text="continued",rect=[64,95,114,100],sourceCell=None,wordIndex=None)]
        for h in headers:
            top = h["rect"][1]
            bottom = min([w["rect"][1] for w in words if w["rect"][1] > top+1 and w["rect"][0] < 65
                          and w["text"] in {"Related", "rFLAGS", "Exceptions", "x87"}] + [710])
            starts = sorted([w for w in words if top+1 < w["rect"][1] < bottom and
                             68 < w["rect"][0] < 70 and w["text"] in names], key=lambda w:w["rect"][1])
            require(starts, "legacy media source table has no owned forms")
            # The selected Vol5 tables use fixed mnemonic/opcode/description
            # columns. All words in their selector/opcode span must be owned.
            boundaries = [w for w in words if w["text"] == "Opcode" and abs(w["rect"][1]-top)<.1]
            description = [w for w in words if w["text"] == "Description" and abs(w["rect"][1]-top)<.1]
            if number == 265:
                opcode_x, description_x = 181,273
            else:
                require(len(boundaries)==len(description)==1, "legacy media source table column headers differ")
                opcode_x, description_x = boundaries[0]["rect"][0],description[0]["rect"][0]
            rows=[]
            for i,start in enumerate(starts):
                low=start["rect"][1]-.1
                high=starts[i+1]["rect"][1]-.1 if i+1<len(starts) else min(bottom,low+22)
                selector_words=sorted([w for w in words if 64 < w["rect"][0] < opcode_x-1 and low <= w["rect"][1] < high],
                                      key=lambda w:(round(w["rect"][1],2),w["rect"][0]))
                encoding_words=sorted([w for w in words if opcode_x <= w["rect"][0] < description_x-1
                                       and low-6 <= w["rect"][1] < high], key=lambda w:(round(w["rect"][1],2),w["rect"][0]))
                require(selector_words and encoding_words, "legacy media source selector/opcode absent")
                rows.append(dict(pdfPage=number,selector=native.ordered_text(selector_words),
                                 sourceEncoding=native.ordered_text(encoding_words),
                                 selectorWords=selector_words,encodingWords=encoding_words))
            last_y=max(w["rect"][1] for r in rows for w in r["selectorWords"]+r["encodingWords"])
            field_words=[w for w in words if top+1 < w["rect"][1] <= last_y+.1 and 64 < w["rect"][0] < description_x-1]
            owned=[w for row in rows for w in row["selectorWords"]+row["encodingWords"]]
            require(len({word_id(w) for w in owned}) == len(owned) and
                    {word_id(w) for w in owned} == {word_id(w) for w in field_words},
                    "legacy media table has unowned/duplicate selector or opcode words")
            tables.append(dict(pdfPage=number,header=None if number==265 else word_id(h),
                               continuationOf=264 if number==265 else None,
                               sourceFieldWordsSha256=digest(field_words),rows=rows))
    # Independent omission scan does not require a repeated table header or
    # a mnemonic in the expected family. A physical leading selector with an
    # aligned opcode must be represented, including continuation pages.
    physical_starts = set()
    for page in pages:
        if not first <= page["pdfPage"] <= last:
            continue
        words = native.words(page)
        for word in words:
            if (60 < word["rect"][0] < 140 and
                abs(word["rect"][3]-word["rect"][1]-9.213) < .02 and
                re.fullmatch(r"[FP][A-Z0-9]+", word["text"])
                and any(140 < w["rect"][0] < 300 and re.fullmatch(r"[0-9A-F]{2}", w["text"])
                        and abs(w["rect"][1]-word["rect"][1]) < 6 for w in words)):
                physical_starts.add(word_id(word))
    covered_starts = {word_id(r["selectorWords"][0]) for t in tables for r in t["rows"]}
    require(physical_starts == covered_starts, "legacy media independent physical form omission/extra: "+owner)
    actual=[(lexical(r["selector"]),lexical(r["sourceEncoding"])) for t in tables for r in t["rows"]]
    require(actual == [(lexical(m),lexical(e)) for m,e in expected], "legacy media full form population/literal differs: "+owner)
    return tables


def form_contract(selector, owner):
    name=selector.split()[0]
    is_three=owner in THREEDNOW
    env=ENVIRONMENT.get(name)
    result=dict(prefix66="environment-size-override" if env else "ignored",
                prefixF2="no-repeat-or-opcode-selector-role-in-this-source-form",
                prefixF3="no-repeat-or-opcode-selector-role-in-this-source-form",
                rexW="does-not-promote-fixed-media-data", extraPrefixAdmission=False,
                addressBits=[64,32], operandAndAddressSizeDistinct=True,
                family="3DNow" if is_three else "x87", definiteWrites="not-derived")
    if env:
        result.update(environmentBytes={"operand16":env[0],"operand32":env[1],"operand64":env[1]},
                      pointerImage="does-not-save-full64-bit-instruction-and-data-pointers")
    else:
        # The source's numeric suffixes denote different kinds of widths.
        # mem2env is two bytes, whereas mem80real is an 80-bit data format.
        matches=re.findall(r"mem(\d+)(real|int|dec|env)?",selector)
        result["explicitMemory"]= [dict(value=int(v),unit="bytes" if typ=="env" else "bits",
                                       kind=typ or "media-data") for v,typ in matches]
    if name in {"FSAVE","FSTENV","FCLEX","FINIT","FSTCW","FSTSW"}:
        no_wait={"FSAVE":"FNSAVE","FSTENV":"FNSTENV","FCLEX":"FNCLEX",
                 "FINIT":"FNINIT","FSTCW":"FNSTCW","FSTSW":"FNSTSW"}[name]
        result["waitSequence"]="9b-WAIT-followed-by-no-wait-operation;not-a-66-f2-f3-prefix-role"
        result["sequenceComponents"]=["WAIT",no_wait]
        if env:
            result["prefix66"]="environment-size-override-on-no-wait-component"
            result["prefix66AppliesTo"]=no_wait
            result["prefix66BeforeWait"]="belongs-to-WAIT;does-not-select-following-environment-size"
    if name == "FWAIT":
        result["mnemonicAliases"]=["WAIT"]
    return result


def assess_owner(record, pages, entries):
    owner=record.get("title")
    require(owner in SPECS, "legacy media unreviewed owner")
    ident,first,last,expected=SPECS[owner]
    selected=[e for e in entries if e["id"]==ident]
    require(len(selected)==1 and selected[0]["title"]==owner and
            [selected[0]["pdfPage"],selected[0]["pdfEndPage"]]==[first,last], "legacy media actual instruction ownership differs")
    require(set(record)=={"title","owner","pages","sourcePageDigests","tables","forms"} and record["owner"]==ident and
            record["pages"]==[first,last], "legacy media reviewed owner differs")
    actual_pages={p["pdfPage"]:p for p in pages if first <= p["pdfPage"] <= last}
    require(set(actual_pages)==set(range(first,last+1)) and
            record["sourcePageDigests"]=={str(n):digest(p["cells"]) for n,p in actual_pages.items()},
            "legacy media whole owner source page population differs")
    if owner == "FWAIT (WAIT)":
        require(any(c["id"] == "pdf:351:cell:12" and c["text"] == "FWAIT and WAIT are synonyms for the same opcode."
                    for c in actual_pages[351]["cells"]), "WAIT source alias premise differs")
    tables=source_tables(pages,owner)
    require(canonical(record["tables"])==canonical(tables), "legacy media physical selector/encoding ownership differs")
    wanted=[dict(selector=m,sourceEncoding=e,properties=form_contract(m,owner)) for m,e in expected]
    require(canonical(record["forms"])==canonical(wanted), "legacy media size/prefix contract differs")
    return dict(record, sourceForms=len(wanted))


def assess(pack, pages, entries, generic_pages):
    require(set(pack)=={"schema","publication","pdfSha256","sourcePolicySha256","executionModes","owners","genericClauses","environmentClauses"}
            and pack["schema"]=="ariadne.amd64-legacy-media-forms/v1" and pack["publication"]=="26569"
            and pack["pdfSha256"]==next(d["pdfSha256"] for d in native.adoption.selected_documents() if d["publication"]=="26569")
            and pack["sourcePolicySha256"]==entry.migration.sha(native.adoption.INPUT)
            and pack["executionModes"]==["long-64"], "legacy media source identity/scope differs")
    require(len({p["pdfPage"] for p in pages})==len(pages), "legacy media duplicate actual page")
    require(set(pack["owners"])==set(SPECS), "legacy media reviewed owner population differs")
    # The entire actual x87 chapter is an independent owner denominator;
    # instruction names alone or the old extractor's row counts cannot prove it.
    actual_x87={e["title"] for e in entries if e["chapter"]=="2 x87 Floating-Point Instruction Reference"}
    require(actual_x87==set(SPECS)-THREEDNOW, "legacy media independent x87 owner denominator differs")
    actual_three=set()
    for owner in entries:
        if owner["chapter"] != "1 64-Bit Media Instruction Reference":
            continue
        title=owner["title"]
        texts=[c["text"] for p in pages if p["pdfPage"]==owner["pdfPage"] for c in p["cells"]]
        if any("3DNow!" in text and (title+" instruction is" in text or title+" is a 3DNow! instruction" in text)
               for text in texts):
            actual_three.add(title)
    require(actual_three==THREEDNOW, "legacy media independent 3DNow owner denominator differs")
    from amd64_p2_prefixes import clause
    by_generic={p["pdfPage"]:p for p in generic_pages}
    require(set(pack["genericClauses"])=={"operand-prefix"}, "legacy media generic clause population differs")
    clause(pack["genericClauses"]["operand-prefix"],by_generic,
           [f"pdf:50:cell:{i}" for i in range(78,80)]+[f"pdf:51:cell:{i}" for i in range(3,9)])
    by_number={p["pdfPage"]:p for p in pages}
    require(set(pack["environmentClauses"])==set(map(str,ENV_CLAUSES)), "legacy media environment clause population differs")
    for number,(first,last) in ENV_CLAUSES.items():
        clause(pack["environmentClauses"][str(number)],by_number,[f"pdf:{number}:cell:{i}" for i in range(first,last+1)])
    checked={name:assess_owner(pack["owners"][name],pages,entries) for name in SPECS}
    return dict(schema="ariadne.amd64-legacy-media-assessment/v1",owners=checked,sourceOwners=84,
                sourceForms=sum(r["sourceForms"] for r in checked.values()), x87SourceForms=151,threednowSourceForms=25,
                recoveredContinuationRows=["FCOMP mem64real","FCOMPP"],
                state="checked-x87-and-3dnow-source-form-prefix-inventory",
                wholePrefixInventoryComplete=False,legalDomainsComplete=False,productionAdmission=False)
