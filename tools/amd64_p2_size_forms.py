#!/usr/bin/env python3
"""Owned fixed/mixed-width source forms beyond the default64 operand groups.

These include the source-owned RDPID mode-width exception absent from Appendix
B. Width facts remain distinct from prefix-byte legality and definite effects.
"""
import copy
import re

import amd64_p2_default64 as physical
import amd64_p2_native64 as native
import amd64_p2_sizes as sizes
import amd64_p2_prefixes as prefixes
from amd64_inventory_xed import canonical, digest

entry=native.entry
require=entry.require
INPUT=native.INPUT.parent/"p2-size-exception-forms-v1.json"
SPECS={
'BSWAP': ('amd-entry:0025', 167, 167, [('BSWAP reg32', '0F C8 +rd'), ('BSWAP reg64', '0F C8 +rq')]),
'CMPXCHG8B CMPXCHG16B': ('amd-entry:0046', 211, 212, [('CMPXCHG8B mem64', '0F C7 /1 m64'), ('CMPXCHG16B mem128', '0F C7 /1 m128')]),
'CPUID': ('amd-entry:0047', 213, 215, [('CPUID', '0F A2')]),
'LAR': ('amd-entry:0169', 453, 454, [('LAR reg16, reg/mem16', '0F 02 /r'), ('LAR reg32, reg/mem16', '0F 02 /r'), ('LAR reg64, reg/mem16', '0F 02 /r')]),
'LSL': ('amd-entry:0174', 462, 463, [('LSL reg16, reg/mem16', '0F 03 /r'), ('LSL reg32, reg/mem16', '0F 03 /r'), ('LSL reg64, reg/mem16', '0F 03 /r')]),
'LMSW': ('amd-entry:0173', 461, 461, [('LMSW reg/mem16', '0F 01 /6')]),
'MONITOR': ('amd-entry:0176', 466, 467, [('MONITOR', '0F 01 C8')]),
'MWAIT': ('amd-entry:0179', 472, 473, [('MWAIT', '0F 01 C9')]),
'SLDT': ('amd-entry:0199', 516, 517, [('SLDT reg16', '0F 00 /0'), ('SLDT reg32', '0F 00 /0'), ('SLDT reg64', '0F 00 /0'), ('SLDT mem16', '0F 00 /0')]),
'SMSW': ('amd-entry:0200', 518, 518, [('SMSW reg16', '0F 01 /4'), ('SMSW reg32', '0F 01 /4'), ('SMSW reg64', '0F 01 /4'), ('SMSW mem16', '0F 01 /4')]),
'STR': ('amd-entry:0204', 523, 523, [('STR reg16', '0F 00 /1'), ('STR reg32', '0F 00 /1'), ('STR reg64', '0F 00 /1'), ('STR mem16', '0F 00 /1')]),
'VERR': ('amd-entry:0211', 539, 540, [('VERR reg/mem16', '0F 00 /4')]),
'VERW': ('amd-entry:0212', 541, 541, [('VERW reg/mem16', '0F 00 /5')]),
'LDS LES LFS LGS LSS':('amd-entry:0066',258,259,[(name+f' reg{bits}, mem16:{bits}',opcode+' /r') for name,opcode in [('LDS','C5'),('LES','C4'),('LFS','0F B4'),('LGS','0F B5'),('LSS','0F B2')] for bits in (16,32)]),
'RDPID':('amd-entry:0115',349,349,[('RDPID','F3 0F C7/7')]),
}
CLAUSES={
    "LDS LES LFS LGS LSS":[(258,9,15),(258,19,34)],
    "BSWAP":[(167,5,12)],"CMPXCHG8B CMPXCHG16B":[(211,11,28)],"CPUID":[(213,5,8)],
    "LAR":[(453,5,7)],"LSL":[(462,5,9),(462,44,49)],"LMSW":[(461,5,11)],
    "MONITOR":[(466,13,29)],"MWAIT":[(472,20,28)],"SLDT":[(516,5,11)],
    "SMSW":[(518,5,8),(518,12,23)],"STR":[(523,5,10)],"VERR":[(539,5,7)],
    "VERW":[(541,5,7)],"RDPID":[(349,5,12)],
}
CONTINUATIONS={"LSL":{463:(462,50)}}


def form_contract(owner,index):
    selector,encoding=SPECS[owner][3][index]
    result=dict(executionModes=["long-64"],state="native64-source-form",extraPrefixAdmission=False,
                definiteWrites="not-derived",addressBits=[64,32] if "mem" in selector or owner=="MONITOR" else [],
                memoryAccessFootprint="not-derived-from-register-result-or-operand-attribute")
    if owner=="BSWAP":
        bits=(32,64)[index]
        result.update(kind="byte-swap",defaultAttributeBits=32,operandBits=bits,registerDataBits=bits,
                      undefinedOperandBits=[16],prefix66="does-not-create-supported16-bit-swap",
                      rexW="select64;not-required-for32")
    elif owner=="CMPXCHG8B CMPXCHG16B":
        wide=index==1
        result.update(kind="wide-compare-exchange",effectiveAttributeBits=[64] if wide else [16,32],
                      memoryDataBits=128 if wide else 64,gprComponentBits=64 if wide else 32,
                      prefix66="does-not-select-word-memory-data",rexW="selects-CMPXCHG16B",
                      featureRequired="CPUID.CMPXCHG16B" if wide else "CPUID.CMPXCHG8B",
                      requiredAlignmentBytes=16 if wide else None)
    elif owner in {"CPUID","MONITOR","MWAIT"}:
        fields={"CPUID":["EAX","EBX","ECX","EDX"],"MONITOR":["ECX","EDX"],"MWAIT":["EAX","ECX"]}[owner]
        result.update(kind="fixed-implicit-data",implicitGprBits={name:32 for name in fields},
                      prefix66="does-not-resize-fixed-implicit-data",rexW="does-not-promote-fixed-implicit-data")
        if owner=="MONITOR":
            result.update(addressRegister="rAX",addressSelectedBy="address-size;not-fixed32-data-operands",
                          monitoredRangeBytes="CPUID-function5;not-an-operand-width",segmentationPagingCheckBytes=1)
    elif owner in {"LAR","LSL"}:
        bits=(16,32,64)[index]
        result.update(kind="descriptor-query",defaultAttributeBits=32,sourceSelectorBits=16,destinationRegisterBits=bits,
                      operandAttributeBits=bits,prefix66="selects16-bit-destination;not-source-selector-width",
                      rexW="selects64-bit-destination",destinationModification="conditional-on-valid-descriptor")
        if owner=="LSL":result["computedLimitBits"]=32
    elif owner in {"LMSW","VERR","VERW"}:
        result.update(kind="fixed-explicit-word",operandBits=16,prefix66="does-not-resize-fixed-word",rexW="does-not-promote-fixed-word")
        if owner=="LMSW":result["cr0SourceFieldBits"]=4
        else:result["sourceSelectorBits"]=16
    elif owner in {"SLDT","STR","SMSW"}:
        memory=selector.endswith("mem16")
        bits=16 if memory else (16,32,64)[index]
        result.update(kind="machine-status-store" if owner=="SMSW" else "selector-store",
                      destinationKind="memory" if memory else "register",destinationBits=bits,defaultAttributeBits=32,
                      operandAttributeBits=[16,32,64] if memory else [bits],
                      prefix66="does-not-resize-memory-word" if memory else "selects16-bit-register-result",
                      rexW="does-not-resize-memory-word" if memory else "selects64-bit-register-result")
        if owner=="SMSW":result["cr0SourceBits"]=bits
        else:result["sourceSelectorBits"]=16
    elif owner=="LDS LES LFS LGS LSS":
        name=selector.split()[0]
        bits=16 if "reg16," in selector else 32
        result.update(kind="far-pointer-load",sourceSelectorBits=16,offsetBits=bits,memoryPointerBits=16+bits,
                      operandAttributeBits=bits,defaultAttributeBits=32,operand64="not-supported-by-owned-prose",
                      prefix66="selects16-bit-offset;not-address16",rexW="does-not-supply-a-supported64-bit-offset-form")
        if name in {"LDS","LES"}:
            result.update(state="excluded-selected-execution-mode",exclusion="old-operation-reassigned-to-VEX-in-native64",
                          replacementEncodingOwnersExcluded=False)
    elif owner=="RDPID":
        result.update(kind="mode-fixed-update;not-B1-listed",currentDestinationRegisterBits=64,
                      non64SourceUpdateBits=32,operandWidthSelectedBy="execution-mode;not-66-or-REX.W",
                      prefix66="normal-operand-size-prefix-does-not-apply",prefixF3="opcode-selector;not-repeat",
                      rexW="does-not-select-update-width",sourceValueBits="not-derived-from-update-width",
                      featureRequired="CPUID.Fn0000_0007.ECX_x0.RDPID=1",sourceSelectorHasPrintedOperands=False)
    else:raise ValueError("unreviewed size-exception owner")
    return result


def source_tables(pages,owner):
    return physical.source_tables(pages,owner,specifications=SPECS,continuations=CONTINUATIONS.get(owner,{}))


def assess_owner(record,pages,entries):
    owner=record.get("title")
    require(owner in SPECS,"unreviewed size-exception owner")
    ident,first,last,expected=SPECS[owner]
    actual=[e for e in entries if e["id"]==ident]
    require(len(actual)==1 and actual[0]["title"]==owner and
            [actual[0]["pdfPage"],actual[0]["pdfEndPage"]]==[first,last],"size-exception actual source owner differs")
    require(set(record)=={"title","owner","pages","pageDigests","tables","forms","clauses"} and
            record["owner"]==ident and record["pages"]==[first,last],"size-exception owner fields differ")
    by_number={p["pdfPage"]:p for p in pages if first<=p["pdfPage"]<=last}
    require(set(by_number)==set(range(first,last+1)) and record["pageDigests"]=={
        str(n):digest(p["cells"]) for n,p in by_number.items()},"size-exception actual owner page omitted/changed")
    tables=source_tables(pages,owner)
    require(canonical(tables)==canonical(record["tables"]),"size-exception physical field ownership differs")
    wanted=[dict(selector=s,sourceEncoding=e,sourceRowOrdinal=i,properties=form_contract(owner,i)) for i,(s,e) in enumerate(expected)]
    require(canonical(record["forms"])==canonical(wanted),"size-exception per-form width/prefix contract differs")
    prefixes.clause(record["clauses"],by_number,[f"pdf:{p}:cell:{i}" for p,a,b in CLAUSES[owner] for i in range(a,b+1)])
    return dict(record,sourceForms=len(wanted))


def assess(pack,pages,entries,no_rex):
    require(set(pack)=={"schema","sourcePolicySha256","publication","pdfSha256","executionModes","owners"}
            and pack["schema"]=="ariadne.amd64-size-exception-forms/v1" and pack["publication"]=="24594"
            and pack["sourcePolicySha256"]==entry.migration.sha(native.adoption.INPUT)
            and pack["pdfSha256"]==next(d["pdfSha256"] for d in native.adoption.selected_documents() if d["publication"]=="24594")
            and pack["executionModes"]==["long-64"] and set(pack["owners"])==set(SPECS),"size-exception inventory identity/scope differs")
    require(len({p["pdfPage"] for p in pages})==len(pages),"size-exception duplicate actual page")
    summary=native.assess(pages,no_rex,entries)
    typed=sizes.assess(entry.read(sizes.INPUT),summary["sizeTable"])
    families={}
    for owner in SPECS:
        if owner=="RDPID":continue
        keys=owner.split() if owner=="LDS LES LFS LGS LSS" else ["CMPXCHG8B" if owner=="CMPXCHG8B CMPXCHG16B" else owner]
        for key in keys:
            rows=[r for r in typed["rows"] if sizes.family(r["heading"]["text"])==key]
            require(len(rows)==1,"size-exception B1 family owner omitted/duplicate")
            selectors=[selector for selector,_ in SPECS[owner][3] if owner!="LDS LES LFS LGS LSS" or selector.split()[0]==key]
            families[key]=dict(sourceFamily=copy.deepcopy(rows[0]),sourceOwner=SPECS[owner][0],sourceFormSelectors=selectors)
    require(all(sizes.family(r["heading"]["text"])!="RDPID" for r in typed["rows"]),
            "RDPID is no longer an extra-B1 source owner")
    checked={name:assess_owner(record,pages,entries) for name,record in pack["owners"].items()}
    require(len(checked)==15 and sum(r["sourceForms"] for r in checked.values())==39,
            "size-exception source owner/form population differs")
    return dict(schema="ariadne.amd64-size-exception-form-assessment/v1",owners=checked,sourceOwners=15,sourceForms=39,
                b1Families=families,additionalSourceOwners=["RDPID"],recoveredContinuationRows=["LSL reg32, reg/mem16","LSL reg64, reg/mem16"],
                state="checked-selected-size-exception-forms;whole-B1-and-current-manual-census-separate",
                closedReferences=[],wholeB1FormInventoryComplete=False,currentManualSizeInventoryComplete=False,
                completeByteDomains=False,productionAdmission=False)
