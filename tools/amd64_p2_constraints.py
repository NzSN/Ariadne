#!/usr/bin/env python3
"""Replay additive P2 clauses and expose the remaining clause-level work.

The reviewed inventory is independent of PDF extraction. Every original cell
and reference survives; a checked source rule is not a legal-domain or runtime
admission. Public commands reconstruct P1 from the actual seven PDFs first.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import tempfile

import amd64_extended_constraints as extended
import amd64_source_adoption as adoption
import amd64_p2_review as review
import amd64_p2_gf as gf
import amd64_p2_native64 as native64
import amd64_p2_prefixes as prefixes
import amd64_p2_scope as scope
import amd64_p2_sizes as sizes
import amd64_p2_media as media
import amd64_p2_c as p2c
import amd64_p2_legacy_media as legacy_media
from amd64_inventory_xed import canonical, digest
from run_output import run_output

entry = adoption.entry
architecture = extended.architecture
ROOT = entry.ROOT
INPUT = ROOT / "tests/bap/fixtures/source-migration/p2-constraints-v1.json"
require = entry.require
SCHEMA = "ariadne.amd64-p2-constraints/v2"
REVIEW_INPUT = ROOT / "tests/bap/fixtures/source-migration/p2-review-decisions-v1.json"
RESOLUTIONS = {
    "extended:mov-displacement-reference-mismatch": dict(rules=["p2:mov-moffset"],checks=["p2-source-rules"]),
    "p2:special-rex-x-label": dict(rules=["p2:rex-ignored-placeholder-notation"],checks=["p2-source-rules"]),
    "paired:movd-store-opcode": dict(state="excluded-selected-execution-mode",
        rules=["paired:movd-mode-notes", "paired:movd-64-vex-store-row", "paired:movd-non64-vex-store-row"],
        checks=["paired-source-rules", "h64-movd-mode-proof"]),
}


def refs(page, first, last=None, publication="24594"):
    return extended.refs(publication, page, first, first if last is None else last)


def rule(owner, cells, parameters, terms, kind="architectural-rule", dependencies=()):
    return dict(owner=owner, kind=kind, sourceCells=cells, parameters=parameters,
                requiredTerms=terms, dependencies=list(dependencies))


REGISTERS = ["rax", "rcx", "rdx", "rbx", "rsp", "rbp", "rsi", "rdi"] + [f"r{i}" for i in range(8, 16)]
LOCK_NAMES = "ADC ADD AND BTC BTR BTS CMPXCHG CMPXCHG8B CMPXCHG16B DEC INC NEG NOT OR SBB SUB XADD XCHG XOR".split()
NO_REX = ["CALL (Near)", "POP reg/mem", "ENTER", "POP reg", "Jcc", "POP FS", "JrCXZ", "POP GS",
          "JMP (Near)", "POPF, POPFD, POPFQ", "LEAVE", "PUSH imm8", "LGDT", "PUSH imm32", "LIDT",
          "PUSH reg/mem", "LLDT", "PUSH reg", "LOOP", "PUSH FS", "LOOPcc", "PUSH GS", "LTR",
          "PUSHF, PUSHFD, PUSHFQ", "MOV CRn", "RET (Near)", "MOV DRn"]

# These are reviewed claims, not classifications inferred from matching words.
# Table parameters describe source rows; they do not assign every instruction's
# register class, default size, prefix applicability, or encoding legality.
RULES = {
    "rex-ignored-placeholder-notation": rule("24594:Table1-17-note1", refs(69, 42, 44)+refs(69, 80, 82),
        dict(tableLowercaseX="undecoded-extension-placeholder", meansPhysicalRexX=False,
             context="ModRM.r/m", physicalField="REX.B"),
        ["lower-case", "ModRM r/m", "REX-prefix bit is not decoded"]),
    "prefix-modifier-scope": rule("24594:1.2.1", refs(48, 14, 30),
        dict(operandOverride="GPR/non-fixed-size; opcode extension otherwise", addressOverride="memory address",
             lock="selected memory writers", repeat="selected strings or opcode extension", lockRepeatModifiersMutuallyExclusive=True),
        ["repurposed to modify the opcode", "mutually exclusive"]),
    "operand-prefix-applicability": rule("24594:1.2.2", refs(49, 78, 80)+refs(50, 3, 8)+refs(50, 78, 79)+refs(51, 3, 8),
        dict(x87Overrides=["FLDENV", "FNSTENV", "FNSAVE", "FRSTOR"], otherX87="ignored", media3DNow="ignored",
             opcodeExtensionPrefixes=["66", "f2", "f3"], maps=["0f", "0f38", "0f3a"], rexWPrecedes66=True,
             exhaustiveInstructionApplicability=False), ["FLDENV", "FNSTENV", "FNSAVE", "FRSTOR", "3DNow!", "opcode extensions"]),
    "operand-size-table": rule("24594:Table1-2", refs(50, 9, 62),
        dict(long64Default32=[[False, False, 32], [True, False, 16], [False, True, 64], [True, True, 64]],
             legacyAndCompatibility=[dict(defaultBits=d, prefix66=p, effectiveBits=(48-d if p else d)) for d in (16, 32) for p in (False, True)],
             instructionExceptions="required-separate-inventory"), ["Operand-Size Overrides", "Not Appli-"], "table"),
    "address-size-table": rule("24594:Table1-3", refs(51, 21, 66),
        dict(long64=[[False, 64], [True, 32]], legacyAndCompatibility=[dict(defaultBits=d, prefix67=p,
             effectiveBits=(48-d if p else d)) for d in (16, 32) for p in (False, True)]), ["Address-Size Overrides", "Required?"], "table"),
    "segment-default-and-override": rule("24594:1.2.4", refs(53, 3, 46),
        dict(normal="ds", rbpRsp="ss", implicitStack="ss-no-override", stringSource="ds-override-allowed",
             stringDestination="es-no-override", prefixBytes={"cs":"2e", "ds":"3e", "es":"26", "fs":"64", "gs":"65", "ss":"36"},
             long64Qualification="segment-prefix-uai"), ["cannot override their ES-segment", "cannot", "use the segment-override prefix"],
        dependencies=("segment-prefix-uai",)),
    "rex-features": rule("24594:1.3", refs(56, 43, 47)+refs(57, 6, 9),
        dict(extended=["GPR", "XMM/YMM", "control/debug"], gpr64=True, uniformByte=True), ["extended", "64-bit operand size", "uniform byte"]),
    "no-rex-source-list": rule("24594:Table1-9", refs(57, 28, 59),
        dict(sourceEntries=NO_REX, interpretation="default-or-fixed-64-without-REX; not a uniform operand-size override rule"),
        ["defaults to (or is fixed at)", "Not Requiring REX Prefix"], "table"),
    "modrm-roles": rule("24594:1.4", refs(59, 13, 22)+refs(60, 3, 5)+refs(60, 66)+refs(62, 69, 70),
        dict(optional=True, follows="opcode", roles=["register-register", "register-memory", "opcode-extension"], sibFollows="modrm",
             modAndRmBits=5, modAndRmCombinations=32),
        ["optional depending", "additional opcode bits", "SIB byte may appear after"]),
    "modrm-register-table": rule("24594:Table1-10", refs(60, 18, 61),
        dict(gprOrder=REGISTERS[:8], regAndRegisterRmClasses=["GPR", "MMX", "XMM", "YMM"],
             highByteCodes={"4":"AH", "5":"CH", "6":"DH", "7":"BH"}, memoryRm4="sib", memoryRm5="mode/mod-dependent",
             registerClass="instruction-dependent", memoryOffsetMods=[1, 2]),
        ["ModRM.reg and .r/m Field Encodings", "Specific register used is instruction-dependent", "displacement field"], "table"),
    "sib-source-table": rule("24594:Table1-12", refs(62, 3, 28)+refs(62, 30, 31)+refs(62, 33, 38),
        dict(indexOrder=["rax", "rcx", "rdx", "rbx", None, "rbp", "rsi", "rdi"],
             baseCodes0through5=["rax", "rcx", "rdx", "rbx", "rsp", "rbp-or-null"],
             baseCodes6and7="source-conflict; not inferred from this table", rexQualification="separate"),
        ["SIB.index and .base Field Encodings", "register specification is null"], "table"),
    "sib-base-table": rule("24594:Table1-13", refs(62, 39, 65),
        dict(mod3="not-applicable", base5ByMod={"0":"disp32", "1":"rbp+disp8", "2":"rbp+disp32"},
             ordinaryBases=["rax", "rcx", "rdx", "rbx", "rsp", "rsi", "rdi"]), ["SIB.base encodings", "(not applicable)"], "table"),
    "modrm-register-direct-table": rule("24594:Table1-14", refs(64, 3, 32),
        dict(mod=3, registerCodes=REGISTERS[:8], classes=["GPR", "MMX", "XMM", "YMM", "ZMM"],
             byteAliasQualification="REX/instruction-dependent", memoryNotes={"0":"scale=index*(1<<scale)", "1":"base+index", "2":"base+index+disp8", "3":"base+index+disp32"}),
        ["Operand Addressing Using ModRM and SIB Bytes", "ZMM7", "32-bit_offset"], "table"),
    "rex-field-width": rule("24594:1.4.4", refs(65, 5, 12),
        dict(regRmIndexBaseBits=4, fields=["R", "X", "B"], W="GPR operand-width"), ["four bits", "64-bit operand size"]),
    "rip-table": rule("24594:Table1-16", refs(67, 17, 45)+refs(69, 9, 10),
        dict(rip=dict(mod=0, rm=5, sib=False, displacementBits=32), absolute=dict(mod=0, rm=4, sibBase=5, sibIndex=4, rexX=0, displacementBits=32),
             absoluteIndexQualification="index is absent only without REX.X"), ["RIP + disp32", "Zero-based", "set to 0"], "table"),
    "rex-special-aliases": rule("24594:1.8.2", refs(68, 18, 24)+refs(69, 35, 41)+refs(69, 45, 49)+refs(69, 83),
        dict(rbpR13NoDisplacement="encode-mod1-zero-disp8", ignoredExtensionFields="specific-source-rules-only"),
        ["don’t cares", "displacement of 0"]),
    "gpr-diagram": rule("24594:Figure2-3-with-Table1-10-codes", refs(85, 5, 103)+refs(85, 110, 114)+refs(60, 42, 57),
        dict(registerCodes=REGISTERS, highBytes={"4":"ah", "5":"ch", "6":"dh", "7":"bh"},
             highBytesWithRex=False, lowByte4through7RequireRex=True, write32="zero-extend", write8and16="preserve-upper"),
        ["General Registers in 64-Bit Mode", "R15B", "zero-extended", "Not addressable in REX"], "diagram"),
    "rip-rflags-diagram": rule("24594:Figure2-3", refs(85, 3, 4)+refs(85, 104, 109),
        dict(ripBits=64, rflagsBits=64, rflagsHigh32="reserved-write-any-read-zero"), ["RFLAGS", "RIP", "read as zeros"], "diagram"),
    "segment-diagram": rule("24594:Figure2-4", refs(86, 7, 30),
        dict(selectorBits=16, long64={"cs":"attributes", "ds":"ignored", "es":"ignored", "ss":"ignored", "fs":"base", "gs":"base"},
             qualifier="segment-prefix-uai"), ["Segment Registers", "(Base only)", "(Attributes only)"], "diagram", ("segment-prefix-uai",)),
    "segment-prefix-uai": rule("24593:2.5.2", refs(93, 26, 35, "24593"),
        dict(mode=64, normallyNull=["cs", "ds", "es", "ss"], normalSegmentOverrides=["fs", "gs"],
             exception="UAI-qualified-canonicality; cannot globally discard null prefixes"),
        ["Upper Address Ignore (UAI)", "multiple-prefix rules", "FS and GS"], dependencies=("uai-enablement", "uai-canonicality")),
    "uai-enablement": rule("24593:5.10.1", refs(232, 58, 68, "24593"),
        dict(cpuid="80000021.EAX.7", enable="EFER.20", requiredState=["EFER.LMA=1", "CS.L=1"], tagBits=[63, 57]),
        ["UpperAddressIgnore", "EFER.UAIE (bit 20)", "ignored outside"]),
    "uai-canonicality": rule("24593:5.10.2", refs(233, 3, 12, "24593"),
        dict(segments=["ds", "es"], fourLevelCheckedBits=[56, 48], fiveLevelCheckedBits=[],
             excludedSegments=["cs", "ss", "fs", "gs"], excludedImplicit=["IDT", "GDT", "LDT", "TSS"],
             indirectControlTargets="normal-canonicality"), ["bits 56:48", "5-level paging", "IDT, GDT, LDT and TSS"]),
    "uai-tag-observation": rule("24593:5.10.3", refs(233, 13, 26, "24593"),
        dict(tagNotGuaranteed=["CR2", "x87 DP", "IBS Data Cache Linear Address"], debugMatchBits=[56, 0]),
        ["not", "guaranteed", "DR0-3[56:0]"]),
    "segment-bases": rule("24593:4.5.3", refs(144, 11, 31, "24593"),
        dict(mode=64, csBase=0, zeroBases=["ds", "es", "ss"], explicitBases=["fs", "gs"],
             linearArithmeticBits=64, overflow="wrap", capturedFsGsBaseRequired=True,
             canonicality="separate-uai-qualified-check"), ["segment base is 0", "64-bit", "overflow", "wraps"]),
    "fsgs-base-writes": rule("24593:4.5.3", refs(145, 10, 28, "24593"),
        dict(wrmsr=dict(cpl=0, fs="c0000100", gs="c0000101"), wrBase=dict(mode=64, requires="implementation support and CR4.FSGSBASE", cpl="any"),
             operand32="zero-extend", noncanonicalWrite="#GP", nullSelector="unresolved-source-conflict"),
        ["C000_0100h", "C000_0101h", "CR4[FSGSBASE]", "general-protection"], dependencies=("null-selector-conditional",)),
    "null-selector-conditional": rule("24593:4.5.1", refs(142, 32, 40, "24593"),
        dict(cpuid="80000021.EAX.6", featureSet="clear-base-limit-except-privilege-changing-IRET/RETF", featureClear="undefined",
             relationToUnqualifiedFsGsProse="unresolved-source-conflict"), ["NullSelectorClearsBase", "fields are left untouched", "undefined"]),
    "mov-moffset": rule("24594:MOV", refs(282, 8, 12)+refs(283, 28, 71),
        dict(opcodes=["a0", "a1", "a2", "a3"], offsetBits="address-size", defaultOffsetBits=64,
             addressOverrideOffsetBits=32, separateImmediate64Opcodes=["b8", "b9", "ba", "bb", "bc", "bd", "be", "bf"],
             dataBits="operand-size, independent of offset-size"), ["moffsets", "address sized", "64-bit offset", "moffset64"]),
    "lock-vol3-source-set": rule("24594:1.2.5", refs(54, 3, 6),
        dict(mnemonics=LOCK_NAMES, requires="writes-memory", otherUse="#UD", completeLegalEncodingDomain=False),
        ["CMPXCHG16B", "write a memory", "invalid-opcode"]),
    "lock-vol1-source-set": rule("24592:3.5.1.3", refs(116, 22, 32, "24592"),
        dict(mnemonics=[n for n in LOCK_NAMES if n != "CMPXCHG16B"], difference="CMPXCHG16B omitted in this source list"),
        ["read-modify-write", "CMPXCHG8B", "invalid-opcode"]),
    "repeat-specific-source": rule("24594:1.2.6", refs(54, 7, 17)+refs(55, 18, 22)+refs(55, 42, 47),
        dict(rep=["INS", "LODS", "MOVS", "OUTS", "STOS"], repe=["CMPS", "SCAS"], repne=["CMPS", "SCAS"],
             countSize="address-size", repeStops="count-zero-or-ZF-zero", repneStops="count-zero-or-ZF-one"),
        ["INS, LODS, MOVS, OUTS, and STOS", "zero flag", "set to 1"]),
    "default64-general-premise": rule("24593:2.5.1", refs(93, 19, 25, "24593")+refs(114, 4, 16, "24592"),
        dict(groups=["near-branches", "implicit-RSP-except-far-branches"], extendedRegisters="still-require-REX",
             fullOpcodeExceptionInventory=False), ["Near branches", "far branches", "R8–R15", "no 32-bit"]),
}

BOUNDARIES = {
    "rex-diagram-field-selector": dict(kind="source-conflict", sourceCells=refs(70, 15)+refs(70, 23)+refs(70, 51)+refs(69, 6, 8),
        meaning="Figure 1-6 case 2 says ModRM reg field != 100 for memory without SIB; the SIB-presence table selects on r/m. The reg/rm selector conflict is not corrected or used for legality."),
    "sib-base-byte-labels": dict(kind="source-conflict", sourceCells=refs(62, 29)+refs(62, 32),
        meaning="Table 1-12 base rows 110/111 literally include DH/BH byte-register labels. Preserve them; do not derive an address base from these labels."),
    "special-rex-x-label": dict(kind="source-conflict", sourceCells=refs(69, 42, 44)+refs(65, 32, 36),
        meaning="Table 1-17's ModRM base row names extension bit x, whereas the REX field definition uses B. No literal correction is inferred."),
    "lock-list-disagreement": dict(kind="source-conflict", sourceCells=refs(54, 3, 6)+refs(116, 22, 32, "24592"),
        meaning="Vol3 includes CMPXCHG16B in its exclusive LOCK list; Vol1's exclusive list omits it. The source-specific lists are checked separately."),
    "repeat-note-disagreement": dict(kind="source-conflict", sourceCells=refs(49, 74, 75)+refs(54, 14, 17),
        meaning="Table 1-1 note 6 narrows repeat use to compare/scan, while the dedicated REP section also names count-only strings."),
    "null-selector-disagreement": dict(kind="source-conflict", sourceCells=refs(145, 12, 15, "24593")+refs(142, 32, 40, "24593"),
        meaning="The FS/GS subsection unconditionally preserves hidden state on null load; the selector subsection gives feature-dependent clear/undefined behavior. No earlier base is inferred."),
    "opcode-applicability": dict(kind="required-inventory", sourceCells=refs(49, 68, 70)+refs(50, 64, 65),
        meaning="Complete mandatory-prefix, fixed-size, default-size and opcode-specific exception inventories still require instruction-level review."),
}

# Individually reviewed structural/context cells. No regex can classify an
# unknown note, diagram label or normative sentence as harmless.
CONTEXT = {
    **{refs(page, cell)[0]: dict(kind="heading-or-table-label", owner=owner)
       for page, cell, owner in ((49, 65, "24594:Table1-1"), (67, 10, "24594:1.7.1"),
          (67, 11, "24594:1.7.1"), (67, 53, "24594:1.7.3"), (67, 54, "24594:1.7.3"),
          (69, 3, "24594:Table1-17"), (69, 4, "24594:Table1-17"), (69, 5, "24594:Table1-17"),
          (69, 18, "24594:Table1-17"), (69, 19, "24594:Table1-17"), (69, 79, "24594:Table1-17"))},
    refs(62, 66)[0]: dict(kind="forward-reading-pointer", owner="24594:1.4.3"),
    **{key: dict(kind="linker-motivation-prose", owner="24594:1.7") for key in refs(67, 6, 9)},
}

SOURCE_REFERENCES = {
    "rex-addressing-examples": dict(sourceCells=refs(68, 7, 9), targetCells=refs(70, 51),
        requiredText="Figure 1-6", targetText="Encoding Examples Using REX R, X, and B Bits",
        issues=["p2:rex-diagram-field-selector"]),
}

REFERENCE_RULES = {
    "prefix-note-4": ["segment-prefix-uai", "uai-enablement", "uai-canonicality"],
    "null-segment-prefix-exception": ["segment-prefix-uai", "uai-canonicality"],
    "mov64-displacement-exception": ["mov-moffset"],
    "segmented-memory-cross-volume": ["segment-bases", "fsgs-base-writes", "uai-canonicality"],
}


def inputs():
    paths = [adoption.INPUT, architecture.ARCHITECTURE_PACK, extended.INPUT, extended.migration.paired.INPUT,
             extended.migration.paired.conversion.INPUT, entry.INPUT]
    return {str(p.relative_to(ROOT)): entry.migration.sha(p) for p in paths}


def validate_structure(pack):
    entry.migration.corpus.fields(pack, {"schema", "inputs", "selectedSources", "clauses", "boundaries", "context", "references", "referenceRules", "sourceCells"}, "P2 pack")
    require(pack["schema"] == SCHEMA and pack["inputs"] == inputs(), "P2 schema or predecessor input drift")
    require(pack["selectedSources"] == adoption.selected_documents(), "P2 accepted source pool differs")
    for field, wanted in (("clauses", RULES), ("boundaries", BOUNDARIES), ("context", CONTEXT),
                          ("references", SOURCE_REFERENCES), ("referenceRules", REFERENCE_RULES)):
        require(canonical(pack[field]) == canonical(wanted), "P2 reviewed " + field + " differs")
    anchors = {c for r in RULES.values() for c in r["sourceCells"]} | {c for b in BOUNDARIES.values() for c in b["sourceCells"]} | CONTEXT.keys()
    anchors |= {c for r in SOURCE_REFERENCES.values() for c in r["sourceCells"]+r["targetCells"]}
    require(set(pack["sourceCells"]) == anchors, "P2 reviewed anchor omission/extra")
    for key, cell in pack["sourceCells"].items():
        require(set(cell) == extended.migration.paired.META_FIELDS and key.split("/", 1)[1] == cell["id"], "P2 anchor identity/fields")
    for r in RULES.values():
        require(set(r["dependencies"]) <= RULES.keys() and r["kind"] in {"architectural-rule", "table", "diagram"}, "P2 dangling rule dependency or kind")
    return anchors


def actual_cells(pack, pages):
    anchors = validate_structure(pack)
    require(set(pages) == {"24592", "24593", "24594"}, "P2 rule source publication omitted/extra")
    actual = {}
    for pub, content in pages.items():
        require(len(content) == len({p["pdfPage"] for p in content}), "P2 actual duplicate page")
        for page in content:
            for cell in page["cells"]:
                key = pub + "/" + cell["id"]
                if key not in anchors:
                    continue
                require(key not in actual and cell["pdfPage"] == page["pdfPage"], "P2 actual duplicate/wrong-page anchor")
                extended.migration.paired.conversion.validate_anchor(pack["sourceCells"][key], cell)
                require(hashlib.sha256(canonical(cell["wordBoxes"])).hexdigest() == cell["wordBoxesSha256"],
                        "P2 actual physical word boxes differ")
                actual[key] = cell
    require(set(actual) == anchors, "P2 actual source anchor omitted")
    for name, r in RULES.items():
        text = " ".join(" ".join(actual[k]["text"] for k in r["sourceCells"]).split())
        require(all(t in text for t in r["requiredTerms"]), "P2 actual clause terms differ: " + name)
    for reference in SOURCE_REFERENCES.values():
        source = " ".join(actual[k]["text"] for k in reference["sourceCells"])
        target = " ".join(actual[k]["text"] for k in reference["targetCells"])
        require(reference["requiredText"] in source and reference["targetText"] in target,
                "P2 source reference target text differs")
    # Independently bind each complete no-REX table entry, including its extent.
    require([actual[k]["text"] for k in refs(57, 33, 59)] == NO_REX, "P2 no-REX source table row differs")
    return actual


def assess(pack, pages):
    actual = actual_cells(pack, pages)
    original = architecture.validate_architecture_pack_cells(entry.read(architecture.ARCHITECTURE_PACK),
        {p: pages[p] for p in architecture.ARCHITECTURE_SOURCES})
    prior = extended.validate_cells(entry.read(extended.INPUT), {p: pages[p] for p in architecture.ARCHITECTURE_SOURCES})
    used = {c for r in RULES.values() for c in r["sourceCells"]}
    conflicts = {c for b in BOUNDARIES.values() if b["kind"] == "source-conflict" for c in b["sourceCells"]}
    dispositions = []
    for old in original["unparsedSourceCells"]:
        key = old["sourceCell"]
        rules = sorted(n for n, r in RULES.items() if key in r["sourceCells"])
        state = ("source-conflict" if key in conflicts else "reviewed-clause-support" if key in used else
                 "reviewed-source-context" if key in CONTEXT else
                 "reviewed-source-reference" if any(key in r["sourceCells"] for r in SOURCE_REFERENCES.values()) else "unparsed")
        dispositions.append(dict(original=copy.deepcopy(old), originalSha256=digest(old), currentState=state,
                                 rules=rules, context=copy.deepcopy(CONTEXT.get(key)),
                                 references=[n for n,r in SOURCE_REFERENCES.items() if key in r["sourceCells"]],
                                 boundaries=sorted(n for n, b in BOUNDARIES.items() if key in b["sourceCells"])))
    require(len(dispositions) == 516, "P2 original cell denominator changed")
    references = []
    for old in original["references"]:
        if old["status"] == "resolved-location":
            continue
        rules = REFERENCE_RULES.get(old["id"], [])
        if old["id"] == "evex-disp8-scaling":
            rules = ["extended:disp8-access-size-factor"]
        references.append(dict(original=copy.deepcopy(old), originalSha256=digest(old), rules=rules,
            currentState="resolved-source-rule" if rules else "unresolved",
            limits="Clause interpretation under explicit premises only; no complete encoding, state-history, or runtime claim."))
    require(set(prior["remainingArchitecturalReferences"]) == {r["original"]["id"] for r in references if r["original"]["id"] != "evex-disp8-scaling"}, "P2 prior reference inventory differs")
    return dict(schema="ariadne.amd64-p2-constraint-assessment/v1", clauses=copy.deepcopy(RULES), typedClauses=len(RULES),
        sourceAnchors=len(actual), originalUnparsedSourceCells=copy.deepcopy(original["unparsedSourceCells"]),
        cellDispositions=dispositions, cellCounts=dict(sorted(Counter(d["currentState"] for d in dispositions).items())),
        referenceDispositions=references, remainingArchitecturalReferences=[r["original"]["id"] for r in references if r["currentState"] == "unresolved"],
        boundaries=copy.deepcopy(BOUNDARIES), inheritedBoundaries=dict(extended=copy.deepcopy(extended.BOUNDARIES),
            paired=copy.deepcopy(extended.migration.paired.BOUNDARIES), conversion=copy.deepcopy(extended.migration.paired.conversion.BOUNDARIES)),
        p2Complete=False, allRequiredConstraintsParsed=False, legalDomainComplete=False, productionAdmission=False, fullAmd64Coverage=False)


def canonical_address(address, *, virtual_bits, segment, uai_active, implicit_system=False):
    """Descriptive source predicate, given validated UAI/state/segment premises.

    This does not enable UAI, resolve an instruction's segment, modify an
    address, or decide any other memory-access exception.
    """
    require(type(address) is int and 0 <= address < 1 << 64, "invalid address")
    require(type(virtual_bits) is int and virtual_bits in (48, 57), "unreviewed virtual address width")
    require(type(segment) is str and segment in ("cs", "ds", "es", "ss", "fs", "gs"), "invalid segment")
    require(type(uai_active) is bool and type(implicit_system) is bool, "invalid supplied state")
    checked_width = 57 if uai_active and segment in ("ds", "es") and not implicit_system else 64
    sign = (address >> (virtual_bits - 1)) & 1
    high = address >> virtual_bits
    count = checked_width - virtual_bits
    mask = (1 << count) - 1
    return high & mask == (mask if sign else 0)


def linear_address(offset, segment_base):
    """Combine an already address-size-truncated offset with a captured base."""
    require(all(type(v) is int and 0 <= v < 1 << 64 for v in (offset, segment_base)), "invalid captured base/offset")
    return (offset + segment_base) % (1 << 64)


def section_obligations(directory, review):
    """Every added section retains every page/cell, regardless of regex matches."""
    folder = directory / "replacement/26568"
    get = entry.sections(directory, review)
    normalized = entry.read(folder / "normalized.json")
    pages = entry.migration.geometry.read_geometry(folder / "bbox.html")
    by_page = {p["pdfPage"]: p for p in pages}
    reviewed = entry.reviewed_input(entry.read(entry.INPUT))
    result = []
    for owner in reviewed["additionalSections"]:
        section = get("replacement", owner, owner["title"].split())
        cells = [c for i in range(owner["pdfPage"], owner["pdfEndPage"] + 1) for c in by_page[i]["cells"]]
        candidates = [r for r in normalized["constraintReferences"] if owner["id"] in r["entryIds"]]
        result.append(dict(id="amd-p2-section:"+digest(dict(pdfSha256=section["pdfSha256"], owner=owner)), owner=copy.deepcopy(owner),
            section=section, sourceCells=len(cells), sourceCellIdentitiesSha256=digest(cells),
            observedReferences=len(candidates), observedReferencesSha256=digest(candidates),
            state="required-clause-review", constraintsParsed=False))
    require(len(result) == 100 and len({r["id"] for r in result}) == 100, "P2 added section omitted/duplicate")
    return result


def current_review_input():
    value = entry.read(REVIEW_INPUT)
    review.fields(value, {"schema", "p2PackSha256", "sourcePolicySha256", "executionModes", "boundaryDispositions", "reviewedPages"}, "P2 review input")
    require(value["schema"] == "ariadne.amd64-p2-review-decisions/v2"
            and value["p2PackSha256"] == entry.migration.sha(INPUT)
            and value["sourcePolicySha256"] == entry.migration.sha(adoption.INPUT)
            and value["executionModes"] == ["long-64"], "P2 review input/source policy drift")
    return value


def original_boundaries():
    groups = dict(p2=BOUNDARIES, extended=extended.BOUNDARIES, paired=extended.migration.paired.BOUNDARIES,
                  conversion=extended.migration.paired.conversion.BOUNDARIES)
    return {group+":"+name: value for group, rows in groups.items() for name,value in rows.items()}


def review_registry(documents):
    """Source ownership is supplied only by already validated clause owners."""
    pins = {d["publication"]: d["pdfSha256"] for d in documents}
    def keys(cells):
        return {review.cell_key(pins[pub], cell) for pub,cell in (k.split("/", 1) for k in cells)}
    clauses = {}
    for name, rule_value in RULES.items():
        clauses["p2:"+name] = dict(sourceCells=keys(rule_value["sourceCells"]), issues=[
            "p2:"+i for i,b in BOUNDARIES.items() if b["kind"] == "source-conflict" and set(b["sourceCells"]).intersection(rule_value["sourceCells"])])
    for name, rule_value in architecture.ARCHITECTURE_RULES.items():
        clauses["architecture:"+name] = dict(sourceCells=keys(rule_value["sourceCells"]), issues=[
            "architecture-reference:"+i for i in rule_value["dependencies"] if i in architecture.ARCHITECTURE_REFERENCES
            and architecture.ARCHITECTURE_REFERENCES[i]["status"] != "resolved-location"])
    for name in ("movd-mode-notes", "movd-64-vex-store-row", "movd-non64-vex-store-row"):
        rule_value = extended.migration.paired.RULES[name]
        clauses["paired:"+name] = dict(sourceCells=keys(["26568/"+k for k in rule_value["replacement"]]), issues=[])
    contexts = {review.cell_key(pins[k.split("/",1)[0]], k.split("/",1)[1]): value for k,value in CONTEXT.items()}
    for owner, value in architecture.ARCHITECTURE_OWNERS.items():
        for key in keys(value["headingCells"]):
            contexts[key] = dict(kind="section-heading", owner=owner)
    references = {name: dict(sourceCells=keys(v["sourceCells"]), targetCells=keys(v["targetCells"]), issues=v["issues"])
                  for name,v in SOURCE_REFERENCES.items()}
    return clauses, contexts, references


def h64_movd_mode_proof(vector_pages, execution_modes):
    """Only an explicit execution-mode note can exclude the non-64-only row."""
    require(execution_modes == ["long-64"], "MOVD exclusion requires native-64 execution scope")
    for side, page_number, store64, store_other, note1, note2 in (
            ("predecessor",340,29,39,75,76), ("replacement",342,27,37,76,77)):
        selected = [p for p in vector_pages[side] if p["pdfPage"] == page_number]
        require(len(selected) == 1, "MOVD mode proof source page missing/duplicate")
        cells = {c["id"]:c for c in selected[0]["cells"]}
        def text(index):
            return cells[f"pdf:{page_number}:cell:{index}"]["text"]
        require(text(store64) == "VMOVD reg32/mem32, xmm 1" and
                text(store_other) == "VMOVD reg32/mem32, xmm 2" and
                text(note1) == "Note 1: These encodings are only available in 64-bit mode." and
                text(note2) == "Note 2: These encodings are only available in non-64-bit modes.",
                "MOVD row/note execution-mode ownership differs")
    return True


def apply_current_reviews(result, directory, selected):
    """Derive current dispositions without modifying historical source objects."""
    decisions = current_review_input()
    clauses, contexts, references = review_registry(selected["documents"])
    actual_cells(entry.read(INPUT), {p:entry.migration.geometry.read_geometry(directory/"predecessor"/p/"bbox.html")
                                    for p in ("24592", "24593", "24594")})
    paired = extended.migration.paired
    vector_pages = {s:entry.migration.geometry.read_geometry(directory/s/"26568/bbox.html") for s in ("predecessor","replacement")}
    paired.validate_cells(entry.read(paired.INPUT), vector_pages)
    lock = entry.migration.corpus.validate_lock(entry.read(entry.migration.corpus.LOCK))
    require(lock["scope"]["executionModes"] == decisions["executionModes"] == selected["scope"]["executionModes"],
            "H64 selected source execution scope differs")
    checks = {"p2-source-rules": True, "paired-source-rules": True,
              "h64-movd-mode-proof": h64_movd_mode_proof(vector_pages, decisions["executionModes"])}
    dispositions = review.reconcile(original_boundaries(), decisions["boundaryDispositions"], clauses, checks, RESOLUTIONS)
    result["boundaryDispositions"] = dispositions
    p2c.apply_all(result,
        {p: entry.migration.geometry.read_geometry(directory/"predecessor"/p/"bbox.html")
         for p in ("24592", "24594")},
        entry.read(directory/"predecessor/24594/normalized.json"), NO_REX)
    dispositions = result["boundaryDispositions"]
    issues = {d["id"]: d for d in dispositions}
    for d in result["referenceDispositions"]:
        issues["architecture-reference:"+d["original"]["id"]] = dict(state=d["currentState"])
    result["boundaryDispositions"] = dispositions
    result["executionModes"] = list(decisions["executionModes"])
    result["boundaryCounts"] = dict(sorted(Counter(d["state"] for d in dispositions).items()))
    for d in result["cellDispositions"]:
        if d["currentState"] == "source-conflict" and d["boundaries"] and all(
                issues["p2:"+i]["state"] == "resolved-source-rule" for i in d["boundaries"]):
            d["currentState"] = "reviewed-source-interpretation"
    result["cellCounts"] = dict(sorted(Counter(d["currentState"] for d in result["cellDispositions"]).items()))
    wanted = {(d["publication"], d["pdfPage"]) for d in decisions["reviewedPages"]}
    pages = {}
    docs = {d["publication"]: d for d in selected["documents"]}
    for pub in {p for p,_ in wanted}:
        folder = directory/("replacement" if pub in ("26568", "26569") else "predecessor")/pub
        for page in entry.migration.geometry.read_geometry(folder/"bbox.html"):
            if (pub, page["pdfPage"]) in wanted:
                pages[(docs[pub]["pdfSha256"], page["pdfPage"])] = page
    # Reference targets must exist in the verified actual source, even when the
    # target page is not yet a whole-page review candidate.
    needed_pins = {key.split("/",1)[0] for ref in references.values() for key in ref["sourceCells"] | ref["targetCells"]}
    actual_keys = set()
    for pub in {p for p,_ in wanted} | {d["publication"] for d in selected["documents"] if d["pdfSha256"] in needed_pins}:
        folder = directory/("replacement" if pub in ("26568", "26569") else "predecessor")/pub
        actual_keys.update(review.cell_key(docs[pub]["pdfSha256"], c["id"])
                           for page in entry.migration.geometry.read_geometry(folder/"bbox.html") for c in page["cells"])
    for ref in references.values():
        require(set(ref["sourceCells"]) <= actual_keys and set(ref["targetCells"]) <= actual_keys,
                "P2 reviewed reference source/target absent from actual corpus")
    result["sourceRegions"] = review.apply_reviews(result["sourceRegions"], decisions["reviewedPages"], pages,
                                                  docs, clauses, contexts, references, issues)
    for section in result["additionalSections"]:
        owner = section["owner"]
        section.update(review.section_state(section["section"]["pdfSha256"], owner["pdfPage"], owner["pdfEndPage"], result["sourceRegions"]))
    result["reviewDecisionsSha256"] = entry.migration.sha(REVIEW_INPUT)
    return result


def source_regions(directory, selected):
    """Bind the complete accepted page/cell population to its source owners.

    A page having some checked anchors does not establish that every clause,
    diagram, or footnote on that page has been reviewed. These are concrete
    remaining review objects, never an inferred page-completeness flag.
    """
    result = []
    for doc in selected["documents"]:
        pub = doc["publication"]
        folder = directory/("replacement" if pub in ("26568", "26569") else "predecessor")/pub
        outline = entry.read(folder/"outline.json")
        pages = entry.migration.geometry.read_geometry(folder/"bbox.html")
        require(len(pages) == doc["pdfPages"] == outline["pages"] and
                [p["pdfPage"] for p in pages] == list(range(1, doc["pdfPages"]+1)), "P2 selected source page omitted/reordered")
        source_entries = entry.read(folder/"normalized.json")["entries"] if (folder/"normalized.json").exists() else []
        regions = entry.migration.geometry.region_accounting(outline, source_entries)
        for page, region in zip(pages, regions):
            cells = page["cells"]
            require(len({c["id"] for c in cells}) == len(cells) and all(c["pdfPage"] == page["pdfPage"] for c in cells)
                    and sum(len(c["wordBoxes"]) for c in cells) == page["wordCount"], "P2 source cell identity/accounting differs")
            result.append(dict(id="amd-p2-region:"+digest(dict(pdfSha256=doc["pdfSha256"], pdfPage=page["pdfPage"])),
                publication=pub, pdfSha256=doc["pdfSha256"], pdfPage=page["pdfPage"], entryIds=region["entryIds"],
                outlineOwners=region["outlineOwners"], sourceCells=len(cells), words=page["wordCount"],
                sourceCellsSha256=digest(cells), state="required-whole-region-clause-review"))
    require(len(result) == 4340 and len({r["id"] for r in result}) == 4340, "P2 accepted region population differs")
    return result


def incomplete_obligations(result):
    """Compute the strict exit from concrete obligations, never saved flags."""
    return dict(cells=sum(d["currentState"] not in {"reviewed-clause-support", "reviewed-source-context", "reviewed-source-reference", "reviewed-source-interpretation"} for d in result["cellDispositions"]),
        references=sum(r["currentState"] != "resolved-source-rule" for r in result["referenceDispositions"]),
        boundaries=sum(d["id"].startswith("p2:") and d["state"] not in review.CLOSED_STATES for d in result["boundaryDispositions"]) +
                   sum(q["state"] not in review.CLOSED_STATES for q in result.get("cSourceQuestions", [])),
        inheritedBoundaries=sum(not d["id"].startswith("p2:") and d["state"] not in review.CLOSED_STATES for d in result["boundaryDispositions"]),
        addedSections=sum(s["state"] != "reviewed-all-required-clauses" for s in result["additionalSections"]),
        regions=sum(r["state"] != "reviewed-all-required-clauses" for r in result["sourceRegions"]))


def implementation_sources():
    result = adoption.implementation_sources()
    result.update(extended.implementation_sources())
    for p in (INPUT, ROOT/"tools/amd64_p2_constraints.py", ROOT/"tools/test_amd64_p2_constraints.py"):
        result[str(p.relative_to(ROOT))] = entry.migration.sha(p)
    for p in (REVIEW_INPUT, ROOT/"tools/amd64_p2_review.py", ROOT/"tools/test_amd64_p2_review.py"):
        result[str(p.relative_to(ROOT))] = entry.migration.sha(p)
    for p in (gf.INPUT, ROOT/"tools/amd64_p2_gf.py", ROOT/"tools/test_amd64_p2_gf.py",
              gf.INPUT.parent/"p2-gf-table-excerpt.json"):
        result[str(p.relative_to(ROOT))] = entry.migration.sha(p)
    for p in (native64.INPUT, ROOT/"tools/amd64_p2_native64.py", ROOT/"tools/test_amd64_p2_native64.py",
              native64.INPUT.parent/"p2-native64-source-excerpt.json"):
        result[str(p.relative_to(ROOT))] = entry.migration.sha(p)
    for p in (prefixes.INPUT, ROOT/"tools/amd64_p2_prefixes.py", ROOT/"tools/test_amd64_p2_prefixes.py",
              prefixes.INPUT.parent/"p2-prefix-source-excerpt.json", prefixes.CR8_INPUT,
              prefixes.INPUT.parent/"p2-cr8-source-excerpt.json"):
        result[str(p.relative_to(ROOT))] = entry.migration.sha(p)
    for p in (scope.INPUT, ROOT/"tools/amd64_p2_scope.py", ROOT/"tools/test_amd64_p2_scope.py",
              scope.INPUT.parent/"p2-fixed64-source-excerpt.json"):
        result[str(p.relative_to(ROOT))] = entry.migration.sha(p)
    for p in (sizes.INPUT, ROOT/"tools/amd64_p2_sizes.py", ROOT/"tools/test_amd64_p2_sizes.py"):
        result[str(p.relative_to(ROOT))] = entry.migration.sha(p)
    for p in (media.INPUT, media.PRECEDENCE_INPUT, media.XOR_FORMS_INPUT, ROOT/"tools/amd64_p2_media.py", ROOT/"tools/test_amd64_p2_media.py",
              media.INPUT.parent/"p2-media-prefix-source-excerpt.json"):
        result[str(p.relative_to(ROOT))] = entry.migration.sha(p)
    for p in (legacy_media.INPUT, ROOT/"tools/amd64_p2_legacy_media.py", ROOT/"tools/test_amd64_p2_legacy_media.py",
              legacy_media.INPUT.parent/"p2-legacy-media-source-excerpt.json"):
        result[str(p.relative_to(ROOT))] = entry.migration.sha(p)
    for p in (p2c.size_forms.INPUT, ROOT/"tools/amd64_p2_size_forms.py", ROOT/"tools/test_amd64_p2_size_forms.py",
              p2c.size_forms.INPUT.parent/"p2-size-exception-source-excerpt.json",p2c.PARTITION_INPUT):
        result[str(p.relative_to(ROOT))] = entry.migration.sha(p)
    for p in (p2c.default64.INPUT, ROOT/"tools/amd64_p2_default64.py", ROOT/"tools/test_amd64_p2_default64.py",
              p2c.default64.INPUT.parent/"p2-default64-source-excerpt.json"):
        result[str(p.relative_to(ROOT))] = entry.migration.sha(p)
    for p in (p2c.INPUT, ROOT/"tools/amd64_p2_c.py", ROOT/"tools/test_amd64_p2_c.py",
              p2c.INPUT.parent/"p2-prefix-interpretation-source-excerpt.json", p2c.MODE_INPUT,
              p2c.INPUT.parent/"p2-native64-owner-source-excerpt.json"):
        result[str(p.relative_to(ROOT))] = entry.migration.sha(p)
    return dict(sorted(result.items()))


def reconstruct(old_cache, publisher_cache, baseline_root, output):
    output = run_output(output)
    require(not output.exists(), "P2 requires fresh output")
    before = implementation_sources()
    pack = entry.read(INPUT)
    validate_structure(pack)
    parent = output/"source-adoption"
    accepted = adoption.reconstruct(old_cache, publisher_cache, parent, baseline_root=baseline_root)
    base = parent/"entry-review/migration"
    products = {str(p.relative_to(base)): entry.migration.sha(p) for p in base.rglob("*") if p.is_file()}
    pages = {p: entry.migration.geometry.read_geometry(base/"predecessor"/p/"bbox.html") for p in ("24592", "24593", "24594")}
    result = assess(pack, pages)
    paired = extended.migration.paired
    vector_pages = {s: entry.migration.geometry.read_geometry(base/s/"26568/bbox.html") for s in ("predecessor", "replacement")}
    result["previousPackReplays"] = dict(
        paired=paired.validate_cells(entry.read(paired.INPUT), vector_pages),
        conversion=paired.conversion.validate_cells(entry.read(paired.conversion.INPUT), vector_pages["replacement"]))
    result["gfTableReview"] = gf.assess(vector_pages)
    result["native64Inventory"] = native64.assess(pages["24594"], NO_REX,
        entry.read(base/"predecessor/24594/normalized.json")["entries"])
    result["fixed64Projection"] = scope.assess(entry.read(scope.INPUT), pages["24592"],
        result["native64Inventory"]["default64Qualifications"])
    result["sizeRuleInventory"] = sizes.assess(entry.read(sizes.INPUT), result["native64Inventory"]["sizeTable"])
    media_sources = {
        "map": next(p for p in pages["24594"] if p["pdfPage"] == 571),
        "old-xorps": next(p for p in vector_pages["predecessor"] if p["pdfPage"] == 1614),
        "xorps": next(p for p in vector_pages["replacement"] if p["pdfPage"] == 1822),
        "xorpd": next(p for p in vector_pages["replacement"] if p["pdfPage"] == 1819)}
    result["cSourceQuestions"] = [media.project_current_scope(entry.read(media.INPUT), media_sources, entry.read(media.PRECEDENCE_INPUT))]
    result["xorPrefixRows"] = media.assess_xor_forms(entry.read(media.XOR_FORMS_INPUT), media_sources, entry.read(media.PRECEDENCE_INPUT))
    result["legacyMediaPrefixRows"] = legacy_media.assess(entry.read(legacy_media.INPUT),
        entry.migration.geometry.read_geometry(base/"replacement/26569/bbox.html"),
        entry.read(base/"replacement/26569/normalized.json")["entries"], pages["24594"])
    result["lockRepeatInventory"] = prefixes.assess(pages["24594"], entry.read(base/"predecessor/24594/normalized.json"))
    result["cr8OpcodeExtension"] = prefixes.assess_cr8(entry.read(prefixes.CR8_INPUT), pages["24594"],
        entry.read(base/"predecessor/24594/normalized.json")["entries"])
    result["cSourceOwnerCoverage"] = p2c.source_owner_coverage(
        {pub:entry.read(base/("predecessor" if pub=="24594" else "replacement")/pub/"normalized.json")
         for pub in ("24594","26568","26569")},result["legacyMediaPrefixRows"],result["xorPrefixRows"],pages["24594"])
    review = entry.read(base/"migration.json")
    result["additionalSections"] = section_obligations(base, review)
    result["selectedSourcePool"] = copy.deepcopy(accepted["sourceSelection"])
    result["sourceRegions"] = source_regions(base, accepted["sourceSelection"])
    apply_current_reviews(result, base, accepted["sourceSelection"])
    result["incompleteObligations"] = incomplete_obligations(result)
    result["p2Complete"] = not any(result["incompleteObligations"].values())
    result["allRequiredConstraintsParsed"] = result["p2Complete"]
    result["implementation"] = before
    result["reviewInputSha256"] = entry.migration.sha(INPUT)
    require(products == {str(p.relative_to(base)): entry.migration.sha(p) for p in base.rglob("*") if p.is_file()},
            "P2 reconstructed source products changed during review")
    require(before == implementation_sources(), "P2 source/input drift")
    entry.migration._write(output, "p2-constraints.json", result)
    return result


def check(old_cache, publisher_cache, baseline_root, output):
    output = run_output(output)
    require(output.is_dir(), "missing P2 output")
    with tempfile.TemporaryDirectory(prefix="p2-replay-", dir=output.parent) as temporary:
        fresh = Path(temporary)/"fresh"
        expected = reconstruct(old_cache, publisher_cache, baseline_root, fresh)
        actual = {str(p.relative_to(output)): p for p in output.rglob("*") if p.is_file()}
        wanted = {str(p.relative_to(fresh)): p for p in fresh.rglob("*") if p.is_file()}
        require(set(actual) == set(wanted), "P2 output omitted/extra artifact")
        for name, path in actual.items():
            require(not path.is_symlink() and path.resolve().is_relative_to(output.resolve())
                and entry.migration.sha(path) == entry.migration.sha(wanted[name]), "P2 output differs from fresh source: " + name)
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("extract", "check"))
    for name in ("old-cache", "publisher-cache", "baseline-root", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--require-c-complete", action="store_true",
                        help="require P2-C inventories; full P2 review remains a separate exit")
    args = parser.parse_args()
    result = (reconstruct if args.action == "extract" else check)(args.old_cache, args.publisher_cache, args.baseline_root, args.output)
    print(json.dumps(dict(typedClauses=result["typedClauses"], sourceAnchors=result["sourceAnchors"], cellCounts=result["cellCounts"],
        remainingReferences=len(result["remainingArchitecturalReferences"]), additionalSections=len(result["additionalSections"]), p2Complete=result["p2Complete"]), sort_keys=True))
    if args.require_c_complete and not result["p2C"]["complete"]:
        raise SystemExit(2)
    if args.require_complete and not result["p2Complete"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
