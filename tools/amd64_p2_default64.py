#!/usr/bin/env python3
"""Complete source-form qualification of the B5/default64/no-REX population.

The default64 cross-reference names near branches and implicit RSP operations,
not every exception to the usual 32-bit data default. Appendix B's other fixed
or unusual data forms remain the distinct operand-note-2 inventory. All source
rows survive, including old-mode rows and the selected-out near16 alternatives.
"""
from collections import Counter
import copy
import re

import amd64_p2_native64 as native
import amd64_p2_scope as scope
import amd64_p2_prefixes as prefixes
from amd64_inventory_xed import canonical, digest

entry=native.entry
require=entry.require
INPUT=native.INPUT.parent/"p2-default64-forms-v1.json"
# Exact owned source-table selectors and fields, including source aliases and
# repeated LEAVE rows. LLDT's wrapped operand does not erase its physical opcode.
SPECS={
'CALL (Near)': ('amd-entry:0031', 178, 180, [('CALL rel16off', 'E8 iw'), ('CALL rel32off', 'E8 id'), ('CALL reg/mem16', 'FF /2'), ('CALL reg/mem32', 'FF /2'), ('CALL reg/mem64', 'FF /2')]),
'ENTER': ('amd-entry:0053', 224, 225, [('ENTER imm16, 0', 'C8 iw 00'), ('ENTER imm16, 1', 'C8 iw 01'), ('ENTER imm16, imm8', 'C8 iw ib')]),
'Jcc': ('amd-entry:0061', 245, 248, [('JO rel8off', '70 cb'), ('JO rel16off', '0F 80 cw'), ('JO rel32off', '0F 80 cd'), ('JNO rel8off', '71 cb'), ('JNO rel16off', '0F 81 cw'), ('JNO rel32off', '0F 81 cd'), ('JB rel8off', '72 cb'), ('JB rel16off', '0F 82 cw'), ('JB rel32off', '0F 82 cd'), ('JC rel8off', '72 cb'), ('JC rel16off', '0F 82 cw'), ('JC rel32off', '0F 82 cd'), ('JNAE rel8off', '72 cb'), ('JNAE rel16off', '0F 82 cw'), ('JNAE rel32off', '0F 82 cd'), ('JNB rel8off', '73 cb'), ('JNB rel16off', '0F 83 cw'), ('JNB rel32off', '0F 83 cd'), ('JNC rel8off', '73 cb'), ('JNC rel16off', '0F 83 cw'), ('JNC rel32off', '0F 83 cd'), ('JAE rel8off', '73 cb'), ('JAE rel16off', '0F 83 cw'), ('JAE rel32off', '0F 83 cd'), ('JZ rel8off', '74 cb'), ('JZ rel16off', '0F 84 cw'), ('JZ rel32off', '0F 84 cd'), ('JE rel8off', '74 cb'), ('JE rel16off', '0F 84 cw'), ('JE rel32off', '0F 84 cd'), ('JNZ rel8off', '75 cb'), ('JNZ rel16off', '0F 85 cw'), ('JNZ rel32off', '0F 85 cd'), ('JNE rel8off', '75 cb'), ('JNE rel16off', '0F 85 cw'), ('JNE rel32off', '0F 85 cd'), ('JBE rel8off', '76 cb'), ('JBE rel16off', '0F 86 cw'), ('JBE rel32off', '0F 86 cd'), ('JNA rel8off', '76 cb'), ('JNA rel16off', '0F 86 cw'), ('JNA rel32off', '0F 86 cd'), ('JNBE rel8off', '77 cb'), ('JNBE rel16off', '0F 87 cw'), ('JNBE rel32off', '0F 87 cd'), ('JA rel8off', '77 cb'), ('JA rel16off', '0F 87 cw'), ('JA rel32off', '0F 87 cd'), ('JS rel8off', '78 cb'), ('JS rel16off', '0F 88 cw'), ('JS rel32off', '0F 88 cd'), ('JNS rel8off', '79 cb'), ('JNS rel16off', '0F 89 cw'), ('JNS rel32off', '0F 89 cd'), ('JP rel8off', '7A cb'), ('JP rel16off', '0F 8A cw'), ('JP rel32off', '0F 8A cd'), ('JPE rel8off', '7A cb'), ('JPE rel16off', '0F 8A cw'), ('JPE rel32off', '0F 8A cd'), ('JNP rel8off', '7B cb'), ('JNP rel16off', '0F 8B cw'), ('JNP rel32off', '0F 8B cd'), ('JPO rel8off', '7B cb'), ('JPO rel16off', '0F 8B cw'), ('JPO rel32off', '0F 8B cd'), ('JL rel8off', '7C cb'), ('JL rel16off', '0F 8C cw'), ('JL rel32off', '0F 8C cd'), ('JNGE rel8off', '7C cb'), ('JNGE rel16off', '0F 8C cw'), ('JNGE rel32off', '0F 8C cd'), ('JNL rel8off', '7D cb'), ('JNL rel16off', '0F 8D cw'), ('JNL rel32off', '0F 8D cd'), ('JGE rel8off', '7D cb'), ('JGE rel16off', '0F 8D cw'), ('JGE rel32off', '0F 8D cd'), ('JLE rel8off', '7E cb'), ('JLE rel16off', '0F 8E cw'), ('JLE rel32off', '0F 8E cd'), ('JNG rel8off', '7E cb'), ('JNG rel16off', '0F 8E cw'), ('JNG rel32off', '0F 8E cd'), ('JNLE rel8off', '7F cb'), ('JNLE rel16off', '0F 8F cw'), ('JNLE rel32off', '0F 8F cd'), ('JG rel8off', '7F cb'), ('JG rel16off', '0F 8F cw'), ('JG rel32off', '0F 8F cd')]),
'JCXZ JECXZ JRCXZ': ('amd-entry:0062', 249, 249, [('JCXZ rel8off', 'E3 cb'), ('JECXZ rel8off', 'E3 cb'), ('JRCXZ rel8off', 'E3 cb')]),
'JMP (Near)': ('amd-entry:0063', 250, 251, [('JMP rel8off', 'EB cb'), ('JMP rel16off', 'E9 cw'), ('JMP rel32off', 'E9 cd'), ('JMP reg/mem16', 'FF /4'), ('JMP reg/mem32', 'FF /4'), ('JMP reg/mem64', 'FF /4')]),
'LEAVE': ('amd-entry:0068', 262, 262, [('LEAVE', 'C9'), ('LEAVE', 'C9'), ('LEAVE', 'C9')]),
'LOOP LOOPE LOOPNE LOOPNZ LOOPZ': ('amd-entry:0072', 269, 270, [('LOOP rel8off', 'E2 cb'), ('LOOPE rel8off', 'E1 cb'), ('LOOPNE rel8off', 'E0 cb'), ('LOOPNZ rel8off', 'E0 cb'), ('LOOPZ rel8off', 'E1 cb')]),
'POP': ('amd-entry:0103', 327, 328, [('POP reg/mem16', '8F /0'), ('POP reg/mem32', '8F /0'), ('POP reg/mem64', '8F /0'), ('POP reg16', '58 +rw'), ('POP reg32', '58 +rd'), ('POP reg64', '58 +rq'), ('POP DS', '1F'), ('POP ES', '07'), ('POP SS', '17'), ('POP FS', '0F A1'), ('POP GS', '0F A9')]),
'POPF POPFD POPFQ': ('amd-entry:0106', 332, 334, [('POPF', '9D'), ('POPFD', '9D'), ('POPFQ', '9D')]),
'PUSH': ('amd-entry:0109', 339, 340, [('PUSH reg/mem16', 'FF /6'), ('PUSH reg/mem32', 'FF /6'), ('PUSH reg/mem64', 'FF /6'), ('PUSH reg16', '50 +rw'), ('PUSH reg32', '50 +rd'), ('PUSH reg64', '50 +rq'), ('PUSH imm8', '6A ib'), ('PUSH imm16', '68 iw'), ('PUSH imm32', '68 id'), ('PUSH imm64', '68 id'), ('PUSH CS', '0E'), ('PUSH SS', '16'), ('PUSH DS', '1E'), ('PUSH ES', '06'), ('PUSH FS', '0F A0'), ('PUSH GS', '0F A8')]),
'PUSHF PUSHFD PUSHFQ': ('amd-entry:0111', 342, 343, [('PUSHF', '9C'), ('PUSHFD', '9C'), ('PUSHFQ', '9C')]),
'RET (Near)': ('amd-entry:0119', 353, 354, [('RET', 'C3'), ('RET imm16', 'C2 iw')]),
'LGDT': ('amd-entry:0170', 455, 456, [('LGDT mem16:32', '0F 01 /2'), ('LGDT mem16:64', '0F 01 /2')]),
'LIDT': ('amd-entry:0171', 457, 458, [('LIDT mem16:32', '0F 01 /3'), ('LIDT mem16:64', '0F 01 /3')]),
'LLDT': ('amd-entry:0172', 459, 460, [('LLDT reg/mem16', '0F 00 /2')]),
'LTR': ('amd-entry:0175', 464, 465, [('LTR reg/mem16', '0F 00 /3')]),
'MOV CRn': ('amd-entry:0177', 468, 469, [('MOV CRn, reg32', '0F 22 /r'), ('MOV CRn, reg64', '0F 22 /r'), ('MOV reg32, CRn', '0F 20 /r'), ('MOV reg64, CRn', '0F 20 /r'), ('MOV CR8, reg32', 'F0 0F 22/r'), ('MOV CR8, reg64', 'F0 0F 22/r'), ('MOV reg32, CR8', 'F0 0F 20/r'), ('MOV reg64, CR8', 'F0 0F 20/r')]),
'MOV DRn': ('amd-entry:0178', 470, 471, [('MOV reg32, DRn', '0F 21 /r'), ('MOV reg64, DRn', '0F 21 /r'), ('MOV DRn, reg32', '0F 23 /r'), ('MOV DRn, reg64', '0F 23 /r')]),
'SGDT': ('amd-entry:0196',512,512,[('SGDT mem16:32','0F 01 /0'),('SGDT mem16:64','0F 01 /0')]),
'SIDT': ('amd-entry:0197',513,513,[('SIDT mem16:32','0F 01 /1'),('SIDT mem16:64','0F 01 /1')]),
}
STACK={"ENTER","LEAVE","POP","POPF POPFD POPFQ","PUSH","PUSHF PUSHFD PUSHFQ"}
NEAR_OWNERS={"CALL (Near)":"CALL","Jcc":"Jcc","JCXZ JECXZ JRCXZ":"JrCXZ","JMP (Near)":"JMP",
             "LOOP LOOPE LOOPNE LOOPNZ LOOPZ":"LOOPcc","RET (Near)":"RET"}
SYSTEM={"LGDT","LIDT","LLDT","LTR","MOV CRn","MOV DRn","SGDT","SIDT"}
COMMON_CLAUSES={
    "typical-and-default64":("24594",50,64,77),
    "normal-prefix-domain-begin":("24594",50,78,79),
    "normal-prefix-domain-end":("24594",51,3,8),
    "native-stack-address":("24594",51,11,20),
    "vol1-stack-pointer":("24592",58,20,25),
    "segment-register-width":("24594",86,7,30),
}
SYSTEM_CLAUSES={"SGDT":[(512,5,13)],"SIDT":[(513,5,13)],"LGDT":[(455,5,17)],"LIDT":[(457,5,17)],"LLDT":[(459,5,16)],
                "LTR":[(464,5,16)],"MOV CRn":[(468,5,21)],"MOV DRn":[(470,5,15)]}
QUALIFIERS={
    ("ENTER",0):(224,5,9), ("ENTER",1):(224,5,9), ("ENTER",2):(224,5,9),
    ("LEAVE",0):(262,20,21), ("LEAVE",1):(262,24,26), ("LEAVE",2):(262,29,30),
    ("PUSH",8):(339,55,56), ("PUSH",9):(339,59,60),
}


def word_id(word):
    return word["sourceCell"]+"/word:"+str(word["wordIndex"])


def field_text(words):
    # Roman and italic operands share a baseline but have different top
    # coordinates. Sorting by top puts CRn before a preceding italic reg32.
    return " ".join(w["text"] for w in sorted(words,key=lambda w:(round(w["rect"][3],1),w["rect"][0])))


def source_tables(pages, owner, *, specifications=None, continuations=None):
    specifications=SPECS if specifications is None else specifications
    continuations={} if continuations is None else continuations
    ident,first,last,expected=specifications[owner]
    names={s.split()[0] for s,_ in expected}
    tables=[]
    for page in pages:
        if not first<=page["pdfPage"]<=last:continue
        words=native.words(page)
        headers=[w for w in words if w["text"]=="Mnemonic" and 60<w["rect"][0]<80]
        previous_header=None
        if page["pdfPage"] in continuations:
            previous_page,cell=continuations[page["pdfPage"]]
            require(not headers,"reviewed continuation unexpectedly has a repeated header")
            earlier=[p for p in pages if p["pdfPage"]==previous_page]
            require(len(earlier)==1,"continuation source header page omitted/duplicate")
            earlier_words=native.words(earlier[0])
            previous=[w for w in earlier_words if word_id(w)==f"pdf:{previous_page}:cell:{cell}/word:0"]
            require(len(previous)==1 and previous[0]["text"]=="Mnemonic","continuation source header owner differs")
            previous_header=previous[0]
            headers=[dict(text="continued",rect=[64,95,114,109])]
        for header in headers:
            top=header["rect"][1]
            bottom=min([w["rect"][1] for w in words if w["rect"][1]>top+1 and w["rect"][0]<65
                        and w["text"] in {"Related","Action","rFLAGS","Exceptions"}]+[710])
            header_words=earlier_words if previous_header else words
            header_y=previous_header["rect"][1] if previous_header else top
            opcode=[w for w in header_words if w["text"]=="Opcode" and abs(w["rect"][1]-header_y)<.1]
            description=[w for w in header_words if w["text"]=="Description" and abs(w["rect"][1]-header_y)<.1]
            require(len(opcode)==len(description)==1,"default64 source table column/header differs")
            ox,dx=opcode[0]["rect"][0],description[0]["rect"][0]
            starts=sorted([w for w in words if top+1<w["rect"][1]<bottom and 68<w["rect"][0]<70
                           and w["text"] in names],key=lambda w:w["rect"][1])
            require(starts,"default64 source table contains no owned selectors")
            rows=[]
            for i,start in enumerate(starts):
                low=start["rect"][1]-.1
                high=starts[i+1]["rect"][1]-.1 if i+1<len(starts) else min(bottom,low+22)
                sel=sorted([w for w in words if 64<w["rect"][0]<ox-1 and low<=w["rect"][1]<high],
                           key=lambda w:(round(w["rect"][1],1),w["rect"][0]))
                enc=sorted([w for w in words if ox<=w["rect"][0]<dx-1 and low-6<=w["rect"][1]<(high-6 if i+1<len(starts) else high)],
                           key=lambda w:(round(w["rect"][1],1),w["rect"][0]))
                require(sel and enc,"default64 selector/opcode is missing; no shared-cell inheritance")
                rows.append(dict(pdfPage=page["pdfPage"],selector=field_text(sel),sourceEncoding=field_text(enc),
                                 selectorWords=sel,encodingWords=enc))
            last_y=max(w["rect"][1] for r in rows for w in r["selectorWords"]+r["encodingWords"])
            actual=[w for w in words if top+1<w["rect"][1]<=last_y+.1 and 64<w["rect"][0]<dx-1]
            assigned=[w for r in rows for w in r["selectorWords"]+r["encodingWords"]]
            require(len({word_id(w) for w in assigned})==len(assigned) and
                    {word_id(w) for w in actual}=={word_id(w) for w in assigned},"default64 unowned/duplicate table field word")
            table=dict(pdfPage=page["pdfPage"],header=None if previous_header else word_id(header),
                       sourceFieldWordsSha256=digest(actual),rows=rows)
            if previous_header:table["continuationOfHeader"]=word_id(previous_header)
            tables.append(table)
    # This scan uses neither the table headers nor the expected mnemonic set.
    # It searches the full mnemonic column with the source's table typography.
    candidates=set()
    for page in pages:
        if not first<=page["pdfPage"]<=last:continue
        words=native.words(page)
        for word in words:
            if (60<word["rect"][0]<150 and word["wordIndex"]==0 and
                abs(word["rect"][3]-word["rect"][1]-13.65)<.02 and
                re.fullmatch(r"[A-Z][A-Z0-9]+",word["text"]) and
                any(150<w["rect"][0]<300 and re.fullmatch(r"[0-9A-F]{2}",w["text"])
                    and abs(w["rect"][1]-word["rect"][1])<6 for w in words)):
                candidates.add(word_id(word))
    represented={word_id(r["selectorWords"][0]) for t in tables for r in t["rows"]}
    require(candidates==represented,"default64 independent physical form omitted/extra: "+owner)
    actual=[(r["selector"],r["sourceEncoding"]) for t in tables for r in t["rows"]]
    require(actual==expected,"default64 full owned form population/literals differ: "+owner)
    return tables


def form_contract(owner,index):
    selector,encoding=SPECS[owner][3][index]
    name=selector.split()[0]
    props=dict(state="native64-source-form",addressBits=[64,32],implicitStackAddressBits=None,
               sourceOperandBits=None,currentOperandBits=[],extraPrefixAdmission=False,
               rexW="not-required-for-default-or-fixed64;other-prefix-combinations-separate",
               definiteWrites="not-derived",memoryAccessFootprint="not-derived-from-stack-slot-or-size-summary")
    def exclude(reason):
        props.update(state="excluded-selected-execution-mode",exclusion=reason,currentOperandBits=[])
    if owner in NEAR_OWNERS:
        group="LOOP" if name=="LOOP" else NEAR_OWNERS[owner]
        props.update(default64Group=group,currentOperandBits=[64],
                     prefix66="selected-fixed64-case;no-byte-removal-or-automatic-admission",
                     fixed64Decision="user-selected-fixed64-near-branches-2026-10-24")
        if owner in {"CALL (Near)","RET (Near)"}:
            props.update(implicitStackAddressBits=64,returnAddressSlotBits=64)
        relative=re.search(r"rel(8|16|32)off",selector)
        indirect=re.search(r"reg/mem(16|32|64)",selector)
        if relative:props["relativeDisplacementBits"]=int(relative[1])
        if indirect:props["indirectTargetBits"]=int(indirect[1])
        if (relative and relative[1]=="16") or (indirect and indirect[1]=="16"):
            props.update(state="excluded-selected-fixed64-hypothesis",currentOperandBits=[],
                         exclusion="preserved-original-near16-source-form")
        if indirect and indirect[1]=="32":exclude("no-native64-operand32-encoding")
        if owner=="JCXZ JECXZ JRCXZ":
            count={"JCXZ":16,"JECXZ":32,"JRCXZ":64}[name]
            props.update(countBits=[count],countSelectedBy="address-size",addressBits=[count])
            if count==16:exclude("address16-unavailable-in-native64")
        elif owner=="LOOP LOOPE LOOPNE LOOPNZ LOOPZ":
            props.update(countBits=[64,32],countSelectedBy="address-size",
                         zf="not-a-size-selector;ignored-by-LOOP;tested-by-LOOPcc")
        if selector=="RET imm16":props.update(encodedImmediateBits=16,immediateRole="stack-adjustment;not-return-target-size")
    elif owner in STACK:
        props.update(implicitStackAddressBits=64,defaultOperandBits=64,
                     prefix66="operand-size-override-to16;full-prefix-combinations-separate")
        if owner=="ENTER":
            props.update(currentOperandBits=[16,64],stackSlotBits=[16,64],encodedImmediateBits=[16,8],
                         immediateRoles=["allocation-byte-count","nesting-level-masked-to5-bits"],
                         constantNestingLevel=0 if index==0 else 1 if index==1 else None)
        elif owner=="LEAVE":
            bits=(16,32,64)[index]
            props.update(sourceOperandBits=bits,currentOperandBits=[bits],stackSlotBits=[bits],
                         framePointerDataBits=bits,stackPointerBits=64,sourceDescriptionStackPointerBits=bits,
                         native64StackAddressRule="vol1-stack-pointer;native-stack-address")
            if bits==32:exclude("no-native64-operand32-encoding")
        elif owner in {"POPF POPFD POPFQ","PUSHF PUSHFD PUSHFQ"}:
            bits=(16,32,64)[index]
            props.update(sourceOperandBits=bits,currentOperandBits=[bits],stackSlotBits=[bits],
                         flagsImageBits=bits,flagsWriteMask="separate-privilege-and-state-contract")
            if bits==32:exclude("no-native64-operand32-encoding")
        else:
            operand=selector.split(" ",1)[1]
            if operand in {"CS","DS","ES","SS","FS","GS"}:
                props.update(currentOperandBits=[16,64],stackSlotBits=[16,64],selectorBits=16,
                             stackSlotIsSelectorWidth=False)
                if operand in {"CS","DS","ES","SS"}:exclude("old-segment-form-invalid-in-native64")
            elif operand=="imm8":
                props.update(currentOperandBits=[16,64],stackSlotBits=[16,64],encodedImmediateBits=8,
                             immediateExtension="sign-extend-to-selected-stack-slot")
            else:
                bits=int(re.search(r"(16|32|64)$",operand)[1])
                props.update(sourceOperandBits=bits,currentOperandBits=[bits],stackSlotBits=[bits])
                if operand.startswith("imm"):
                    props.update(encodedImmediateBits=32 if bits==64 else bits,
                                 immediateExtension="sign-extend32-to64" if bits==64 else "none")
                if bits==32:exclude("no-native64-operand32-encoding")
    elif owner in {"LGDT","LIDT","SGDT","SIDT"}:
        props.update(prefix66="ignored-in-native64",native64BaseBits=64,limitBits=16,native64PseudoDescriptorBytes=10,
                     sourcePseudoDescriptorBytes=6 if index==0 else 10,
                     sourceOperandBits=32 if index==0 else 64,currentOperandBits=[64])
        if index==0:exclude("legacy-or-compatibility-pseudo-descriptor-form")
    elif owner in {"LLDT","LTR"}:
        props.update(prefix66="does-not-alter-fixed-selector-or-native64-descriptor-base",sourceOperandBits=16,
                     currentOperandBits=[16],selectorBits=16,descriptorBaseBits=64,descriptorObjectBytes=16,
                     implicitDescriptorAccessFootprint="separate;not-derived-from-object-size")
    elif owner in {"MOV CRn","MOV DRn"}:
        bits=32 if "reg32" in selector else 64
        props.update(prefix66="does-not-alter-fixed-native64-data-width",sourceOperandBits=bits,currentOperandBits=[64],
                     registerOnly=True,cplRequired=0)
        if bits==32:exclude("non64-only-fixed32-transfer")
        if encoding.startswith("F0"):
            props.update(prefixF0="AltMovCr8-opcode-extension;not-memory-lock",
                         featureRequired="CPUID.Fn8000_0001.ECX.AltMovCr8=1")
    else:raise ValueError("unreviewed default64 owner")
    return props


def b5_group(owner,selector):
    name=selector.split()[0]
    if owner in SYSTEM:return None
    if owner in NEAR_OWNERS:
        return "LOOP" if name=="LOOP" else NEAR_OWNERS[owner]
    if owner in {"ENTER","LEAVE"}:return owner
    if owner in {"POPF POPFD POPFQ","PUSHF PUSHFD PUSHFQ"}:
        return "POPF, POPFD, POPFQ" if name.startswith("POP") else "PUSHF, PUSHFD, PUSHFQ"
    operand=selector.split(" ",1)[1]
    if operand in {"CS","DS","ES","SS"}:return None
    if operand in {"FS","GS"}:return name+" "+operand
    if operand.startswith("reg/mem"):return name+" reg/mem"
    if operand.startswith("reg"):return name+" reg"
    if operand=="imm8":return "PUSH imm8"
    if operand.startswith("imm"):return "PUSH imm32"
    raise ValueError("unmapped B5 source form")


def assess_owner(record,pages,entries):
    owner=record.get("title")
    require(owner in SPECS,"default64 unreviewed owner")
    ident,first,last,expected=SPECS[owner]
    actual=[e for e in entries if e["id"]==ident]
    require(len(actual)==1 and actual[0]["title"]==owner and
            [actual[0]["pdfPage"],actual[0]["pdfEndPage"]]==[first,last],"default64 actual owner extent differs")
    require(set(record)=={"title","owner","pages","pageDigests","tables","forms","qualifiers"} and record["owner"]==ident and
            record["pages"]==[first,last],"default64 owner identity/fields differ")
    by_number={p["pdfPage"]:p for p in pages if first<=p["pdfPage"]<=last}
    require(set(by_number)==set(range(first,last+1)) and
            record["pageDigests"]=={str(n):digest(p["cells"]) for n,p in by_number.items()},"default64 owner page population differs")
    tables=source_tables(pages,owner)
    require(canonical(record["tables"])==canonical(tables),"default64 physical ownership differs")
    wanted=[dict(selector=s,sourceEncoding=e,sourceRowOrdinal=i,b5Group=b5_group(owner,s),properties=form_contract(owner,i))
            for i,(s,e) in enumerate(expected)]
    require(canonical(record["forms"])==canonical(wanted),"default64 exact source-form qualification differs")
    wanted_q={str(i):v for (name,i),v in QUALIFIERS.items() if name==owner}
    require(set(record["qualifiers"])==set(wanted_q),"default64 physical row qualifier population differs")
    for index,(page,first_cell,last_cell) in wanted_q.items():
        prefixes.clause(record["qualifiers"][index],by_number,[f"pdf:{page}:cell:{i}" for i in range(first_cell,last_cell+1)])
    return dict(record,sourceForms=len(wanted))


def assess(pack,sources,entries,no_rex):
    require(set(pack)=={"schema","sourcePolicySha256","pdfSha256","executionModes","owners","commonClauses","systemClauses"}
            and pack["schema"]=="ariadne.amd64-default64-forms/v1" and pack["executionModes"]==["long-64"]
            and pack["sourcePolicySha256"]==entry.migration.sha(native.adoption.INPUT)
            and pack["pdfSha256"]==next(d["pdfSha256"] for d in native.adoption.selected_documents() if d["publication"]=="24594")
            and set(sources)=={"24592","24594"} and set(pack["owners"])==set(SPECS),"default64 inventory identity/scope/owners differ")
    populations={pub:{p["pdfPage"]:p for p in pages} for pub,pages in sources.items()}
    require(all(len(populations[pub])==len(sources[pub]) for pub in sources),"default64 duplicate actual source page")
    # These calls reconstruct the full B1/B3/B5 source populations and the
    # selected hypothesis. Saved inventory flags cannot satisfy this gate.
    inventory=native.assess(sources["24594"],no_rex,entries)
    projection=scope.assess(entry.read(scope.INPUT),sources["24592"],inventory["default64Qualifications"])
    require(set(pack["commonClauses"])==set(COMMON_CLAUSES) and set(pack["systemClauses"])==SYSTEM,
            "default64 required clause population differs")
    for name,(pub,page,a,b) in COMMON_CLAUSES.items():
        prefixes.clause(pack["commonClauses"][name],populations[pub],[f"pdf:{page}:cell:{i}" for i in range(a,b+1)])
    for name,specs in SYSTEM_CLAUSES.items():
        prefixes.clause(pack["systemClauses"][name],populations["24594"],
                       [f"pdf:{page}:cell:{i}" for page,a,b in specs for i in range(a,b+1)])
    checked={name:assess_owner(record,sources["24594"],entries) for name,record in pack["owners"].items()}
    fixed64={band["heading"]["text"].split("—")[0]:band for page in inventory["sizeTable"] for band in page["sourceBands"]
             if band["physicalColumns"][2]=="Operand size fixed at 64 bits."}
    fixed_owners={"LGDT":"LGDT","LIDT":"LIDT","SGDT":"SGDT","SIDT":"SIDT",
                  "MOV(CRn)":"MOV CRn","MOV(DRn)":"MOV DRn"}
    require(set(fixed64)==set(fixed_owners) and set(fixed_owners.values())<=set(checked),
            "default64 full B1 fixed64 source population omitted/extra")
    fixed_links={name:dict(owner=checked[owner]["owner"],sourceBand=copy.deepcopy(fixed64[name]))
                 for name,owner in fixed_owners.items()}
    groups={row["mnemonic"]:[] for row in inventory["default64"]}
    ungrouped=[]
    for name,owner in checked.items():
        for form in owner["forms"]:
            key=dict(owner=owner["owner"],sourceRowOrdinal=form["sourceRowOrdinal"],selector=form["selector"])
            if form["b5Group"] is not None:
                require(form["b5Group"] in groups,"default64 source form has no B5 source owner")
                groups[form["b5Group"]].append(key)
            else:
                require(name in SYSTEM or form["properties"]["exclusion"]=="old-segment-form-invalid-in-native64",
                        "default64 source form escaped the B5 denominator")
                ungrouped.append(key)
    require(len(groups)==21 and all(groups.values()) and sum(map(len,groups.values()))==143 and len(ungrouped)==29,
            "default64 complete B5/source-form relation differs")
    counts=Counter(form["properties"]["state"] for owner in checked.values() for form in owner["forms"])
    require(sum(counts.values())==172,"default64 complete physical source-form denominator differs")
    return dict(schema="ariadne.amd64-default64-form-assessment/v1",owners=checked,sourceOwners=20,sourceForms=172,
                b5Groups=groups,b1Fixed64=fixed_links,otherFixedSystemAndOldSegmentForms=ungrouped,formStates=dict(sorted(counts.items())),
                fixed64ProjectionSha256=digest(projection),noRexRelation=inventory["noRexRelation"],
                subproofForReference="default64-instruction-exceptions",state="checked-default64-operand-attribute-subproof",
                normalOperandAttributeScope=dict(sourceCells=[f"24594/pdf:50:cell:{i}" for i in range(67,78)],
                    groups=["near-branches-under-selected-fixed64-hypothesis","implicit-RSP-operations-except-far-transfers"],
                    census="referenced-B5/Vol1-operand-attribute-domain;not-global-fixed-size-inventory"),
                globalDefaultFixedCensusComplete=False,
                otherDefaultExceptions="operand-note-2-remains-separate",prefixCombinations="P2-prefix/P3-separate",
                completeByteDomains=False,productionAdmission=False)
