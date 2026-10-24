#!/usr/bin/env python3
"""Typed Appendix B observations, with explicit instruction-specific exceptions.

These are size and prefix contracts, not instruction effects. Mixed rows retain
their subform distinctions. In particular a descriptor base width is not its
memory footprint, and a table's result column cannot create a definite write.
"""
import copy
import re

import amd64_p2_native64 as native
import amd64_p2_scope as scope
from amd64_inventory_xed import canonical, digest

entry = native.entry
require = entry.require
INPUT = native.INPUT.parent / "p2-b1-size-rules-v1.json"

# Independently reviewed row families. There is deliberately no catch-all
# "promoted" case: an unclassified source heading fails rather than inheriting
# a generic default or a neighboring physical band's attributes.
PROMOTED32 = set("ADC ADD AND BSF BSR BSWAP BT BTC BTR BTS CMOVcc CMP CMPXCHG DEC DIV IDIV IMUL INC LEA LZCNT MOVNTI MOVSX MOVZX MUL NEG NOT OR POPCNT RCL RCR ROL ROR SAL SAR SBB SHL SHLD SHR SHRD SUB TEST XADD XCHG XOR".split())
NO_OPERAND_ATTRIBUTE = set("CLC CLD CLFLUSH CLGI CLI CLTS CMC HLT INT INT3 INVD INVLPG INVLPGA LAHF LFENCE MFENCE NOP PAUSE PREFETCH PREFETCHlevel PREFETCHW RDMSR RDPMC RDTSC RDTSCP RSM SAHF SFENCE SKINIT STC STD STGI STI SWAPGS SYSCALL UD2 VMLOAD VMMCALL VMRUN VMSAVE WAIT WBINVD WRMSR".split())
FIXED16 = set("LLDT LMSW LTR VERR VERW".split())
FIXED32 = set("CPUID MONITOR MWAIT".split())
DESCRIPTORS = set("LGDT LIDT SGDT SIDT".split())
IO = set("IN INS OUT OUTS".split())
STRINGS = set("CMPS LODS MOVS SCAS STOS".split())
ALIASES = {"CDQ": "CWD, CDQ, CQO", "CDQE": "CBW, CWDE, CDQE",
           "CDWE": "CBW, CWDE, CDQE", "CQO": "CWD, CDQ, CQO"}
INVALID = set("AAA AAD AAM AAS ARPL BOUND DAA DAS INTO LDS LES POPA PUSHA SYSENTER SYSEXIT".split())


def family(heading):
    # This extracts an inventory key, not an instruction semantics rule.
    return re.split(r"[, —]", heading)[0]


def contract(heading):
    name = family(heading)
    properties = dict(byteOpcodesPromoted=False, definiteWrites="not-derived",
                      prefixLegality="separate-form-encoding-contract")
    if name in ALIASES:
        properties.update(kind="source-alias-reference", target=ALIASES[name],
                          sourceSpellingPreserved=True)
    elif name in INVALID:
        properties.update(kind="unavailable-old-operation", reassignedLeadingBytesPreserved=True)
    elif name in ("CALL", "JMP", "RET") and "Far" in heading:
        properties.update(kind="far-transfer-subforms", operandBits=[16, 32, 64],
                          directImmediate="unavailable-native64", indirect="instruction-owned-gate-and-pointer-rules",
                          nearHypothesisApplies=False)
    elif name in ("CALL", "Jcc", "JCXZ", "JMP", "LOOP", "LOOPZ", "LOOPNZ", "RET"):
        selected = {"JCXZ": "JrCXZ", "LOOPZ": "LOOPcc", "LOOPNZ": "LOOPcc"}.get(name, name)
        properties.update(kind="selected-near-branch", currentScope=scope.selected_contract(selected),
                          address16="unavailable", originalOverrideNote="preserved-outside-selected-case")
    elif name in ("ENTER", "LEAVE", "POP", "POPF", "PUSH", "PUSHF"):
        properties.update(kind="default64-stack-subforms", defaultBits=64, operandBits=[16, 64],
                          operand32="unavailable", stackAddressBits=64,
                          explicitNonStackAddressBits=[64, 32],
                          invalidSegments=(["DS", "ES", "SS"] + (["CS"] if name == "PUSH" else [])) if name in ("POP", "PUSH") else [],
                          immediateBits="opcode-specific;not-stack-payload-width")
    elif name in DESCRIPTORS:
        properties.update(kind="fixed-descriptor-base", baseBits=64, limitBits=16,
                          memoryBytes=10, operandOverride="ignored")
    elif name in FIXED16:
        properties.update(kind="fixed-explicit-selector-or-word", operandBits=[16],
                          operandOverride="ignored", descriptorBaseBits=64 if name in ("LLDT", "LTR") else None)
    elif name in FIXED32:
        properties.update(kind="fixed-implicit-data", operandBits=[32], operandOverride="ignored",
                          addressBits=[64, 32] if name == "MONITOR" else [])
    elif name in IO or name == "REP" and heading.startswith(("REP INS", "REP OUTS")):
        properties.update(kind="port-io-subforms", dataBits=[8, 16, 32], rexW="does-not-create64-bit-port-data",
                          stringCountAndPointerBits=[64, 32] if name in ("INS", "OUTS", "REP") else [])
    elif name in STRINGS or name in ("REP", "REPx"):
        properties.update(kind="string-subforms", dataBits=[8, 16, 32, 64],
                          pointerAndCountBits=[64, 32], pointerAndCountSelectedBy="address-size",
                          byteOpcodeOperandBits=8, repeated="instruction-owned-prefix-rule;not-opcode-selector")
    elif name == "MOV" and "Segment" in heading:
        properties.update(kind="segment-register-subforms", selectorBits=16,
                          loadOperandBits=[16], storeRegisterBits=[16, 32, 64], storeMemoryBits=16,
                          override="direction-and-operand-alternative-specific")
    elif name in ("MOV(CRn)", "MOV(DRn)"):
        properties.update(kind="fixed-control-or-debug-transfer", operandBits=[64], operandOverride="ignored",
                          prefixF0="AltMovCr8-opcode-extension-not-memory-lock" if name == "MOV(CRn)" else "not-admitted")
    elif name == "MOV":
        properties.update(kind="mov-subforms", defaultBits=32, operandBits=[8, 16, 32, 64],
                          immediate64="B8-BF-only", moffsetBits=[64, 32], moffsetSelectedBy="address-size",
                          c7ImmediateBits=[16, 32], c7Immediate64="sign-extended32")
    elif name == "MOVD":
        properties.update(kind="media-transfer-subforms", gprPayloadBits=[32, 64],
                          mediaRegisterBits=[64, 128], prefix66="opcode-selector;not16-bit-payload",
                          sourceModeNotes="separate-selected-volume4-rows")
    elif name == "CMPXCHG8B":
        properties.update(kind="cmpxchg-wide-subforms", dataBits=[64, 128],
                          rexW="selects-CMPXCHG16B", prefix66="does-not-create-word-memory-compare-exchange")
    elif name in ("CBW", "CWD"):
        properties.update(kind="conversion-aliases", operandBits=[16, 32, 64], defaultBits=32,
                          widths="source-and-destination-distinct")
    elif name in ("LAR", "LSL"):
        properties.update(kind="descriptor-query", sourceSelectorBits=16, destinationRegisterBits=[16, 32, 64], defaultBits=32)
    elif name in ("LFS", "LGS", "LSS"):
        properties.update(kind="far-pointer-load", selectorBits=16, offsetBits=[16, 32],
                          sourcePointerBits=[32, 48], operand64="not-supported-by-instruction-prose")
    elif name in ("SLDT", "STR"):
        properties.update(kind="selector-store", selectorBits=16, registerBits=[16, 32, 64], memoryBits=16)
    elif name == "SMSW":
        properties.update(kind="machine-status-store", registerBits=[16, 32, 64], memoryBits=16)
    elif name == "MOVSXD":
        properties.update(kind="movsxd-subforms", defaultBits=32, rexW=dict(sourceBits=32, destinationBits=64),
                          withoutRexW="32-bit-copy-zero-extended", operand16="copies16-preserves-upper48")
    elif name == "SYSRET":
        properties.update(kind="system-return", defaultBits=32, operandBits=[16, 32, 64],
                          returnMode="64-only-with-operand64;otherwise-compatibility32", nearHypothesisApplies=False)
    elif name == "IRET":
        properties.update(kind="interrupt-return", sourceAliases=["IRET", "IRETD", "IRETQ"],
                          sourceOperandBits=[16, 32, 64], nativeModeAdmission="requires-volume2-interrupt-contract",
                          nearHypothesisApplies=False)
    elif name == "BSWAP":
        properties.update(kind="byte-swap", defaultBits=32, operandBits=[32, 64],
                          operand16="undefined;not-a-supported-word-swap")
    elif name in PROMOTED32:
        properties.update(kind="promoted-nonbyte-subforms", defaultBits=32, operandBits=[16, 32, 64],
                          operandOverride="66-to16;REX.W-precedes66",
                          sourceWidth="separate-for-extension-count-immediate-and-memory-subforms")
    elif name in NO_OPERAND_ATTRIBUTE:
        properties.update(kind="no-generic-operand-size-selection", operandBits="instruction-owned-implicit-and-memory-fields",
                          operandOverride="does-not-promote-implicit-data")
    else:
        raise ValueError("unreviewed B1 size family: " + heading)
    return properties


def assess(pack, size_table):
    require(set(pack) == {"schema", "sourcePolicySha256", "executionModes", "rows"} and
            pack["schema"] == "ariadne.amd64-b1-size-rules/v1" and pack["executionModes"] == ["long-64"] and
            pack["sourcePolicySha256"] == entry.migration.sha(native.adoption.INPUT), "B1 size inventory identity/scope differs")
    rows = [(p["pdfPage"], r) for p in size_table for r in p["sourceBands"]]
    require(len(rows) == len(pack["rows"]) == 172, "B1 size qualification population differs")
    checked = []
    for (number, source), record in zip(rows, pack["rows"]):
        require(set(record) == {"pdfPage", "heading", "sourceWordsSha256", "properties"} and
                record["pdfPage"] == number and record["heading"] == source["heading"] and
                record["sourceWordsSha256"] == digest(source["sourceWords"]) and
                canonical(record["properties"]) == canonical(contract(source["heading"]["text"])),
                "B1 source/size qualification differs")
        checked.append(copy.deepcopy(record))
    return dict(schema="ariadne.amd64-b1-size-assessment/v1", rows=checked,
                state="checked-typed-size-families;instruction-form-qualifications-separate",
                completeInstructionApplicability=False, productionAdmission=False)
