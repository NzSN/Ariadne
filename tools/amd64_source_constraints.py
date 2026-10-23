#!/usr/bin/env python3
"""Replay reviewed source constraints against exact pinned AMD source cells.

The original MOV8 pack and additive legacy-encoding inventory are bounded
reviewed derivations, not a general manual parser. Other architectural clauses and source completeness
remain open. Reviewed parameters and exact source roles are separate from the
caller-supplied cell hashes; rehashing an altered claim cannot confer authority.
"""
import argparse
import hashlib
import math
from pathlib import Path
import re

from amd64_domains import ROOT, canonical, fields, read, require, sha

SCHEMA = "ariadne.amd64-source-constraints/v1"
PDF_SHA = "e18bd39ad0ca19d2eb9b9ea25c2635144c5ab368e5d6fbdc7a08345515ea1aee"
BBOX_SHA = "43e40c497076734da2646b57a1632011e6002e726dc77b0cccbe17a3564058dc"
SOURCE_LOCK = "tests/bap/fixtures/amd-manuals.lock.json"
PACK_SCOPE = "amd-mov8-register-constraint-pack/v1"
SOURCE_RANGES = {
    "mov8-direction-88": [(282, 30, 36)],
    "mov8-direction-8a": [(282, 49, 52)],
    "mov-copy-width": [(282, 3, 8)],
    "modrm-register-direct": [(59, 13, 48), (60, 6, 17)],
    "register-code-map": [(60, 18, 62), (85, 5, 5), (85, 8, 103)],
    "rex-placement-bits": [(45, 18, 24), (57, 10, 27), (57, 60, 63)],
    "rex-register-extensions": [(65, 7, 27), (65, 31, 38), (65, 46, 51), (66, 3, 5)],
    "byte-register-alias-preservation": [(68, 10, 17), (84, 68, 72), (85, 3, 3), (85, 110, 111)],
    "flags-unmodified": [(284, 5, 6)],
}
CLAUSE_PARAMETERS = {
    "mov8-direction-88": dict(opcode="88", destination="modrm.rm", source="modrm.reg", operandBits=8),
    "mov8-direction-8a": dict(opcode="8a", destination="modrm.reg", source="modrm.rm", operandBits=8),
    "mov-copy-width": dict(operation="copy", operandBits=8),
    "modrm-register-direct": dict(modBits=[7, 6], regBits=[5, 4, 3], rmBits=[2, 1, 0],
                                  modValues=[3], addressing="register-direct"),
    "register-code-map": dict(legacy=["al", "cl", "dl", "bl", "ah", "ch", "dh", "bh"],
        rex=["al", "cl", "dl", "bl", "spl", "bpl", "sil", "dil"] + ["r" + str(index) + "b" for index in range(8, 16)]),
    "rex-placement-bits": dict(highNibble=4, w=3, r=2, x=1, b=0, maxCount=1,
                               placement="immediately-before-opcode", maxInstructionBytes=15),
    "rex-register-extensions": dict(regExtension="rex.r", rmExtension="rex.b", extensionBit=3),
    "byte-register-alias-preservation": dict(highByteCodes=[4, 5, 6, 7], highByteBanks=["rax", "rcx", "rdx", "rbx"],
                                             highByteOffset=1, highBytesRequireNoRex=True,
                                             rexSelectsLowBytes=True, preserveOtherBits=True),
    "flags-unmodified": dict(changedFlags=[]),
}

# This additive inventory does not change the frozen nine-clause MOV8 pack.
# Rule IDs, ownership and referenced notes are reviewed independently from the
# source-cell extractor. Uncovered cells remain explicit obligations.
ARCHITECTURE_SCHEMA = "ariadne.amd64-architecture-constraints/v1"
ARCHITECTURE_PACK = ROOT / "tests/bap/fixtures/amd64-semantics/architecture-constraints-v1.json"
ARCHITECTURE_SCOPE = "amd-legacy-encoding-constraints/long64-v1"
ARCHITECTURE_SOURCES = {
    "24592": dict(revision="3.25", filename="24592_3.25_APM_Vol1_PUB.pdf",
                  pdfSha256="aed9236b718ae86cdb49f7d628f4ebb1a4bdce1a012df6cf6aad6735776c8a38",
                  bboxSha256="ee4c9561638f7d84f1f30d4fe2764815e71e867f776a61afb33894139db3dfd5"),
    "24594": dict(revision="3.38", filename="24594_3.38_APM_Vol3_PUB.pdf",
                  pdfSha256=PDF_SHA, bboxSha256=BBOX_SHA),
}


def architecture_refs(page, start, end=None, publication="24594"):
    return [f"{publication}/pdf:{page}:cell:{index}" for index in range(start, (end if end is not None else start) + 1)]


ARCHITECTURE_REGIONS = {
    "24592": [(54, 31, 39)],
    "24594": [(45, 18, 24), (46, 25, 34), (48, 7, 30), (49, 3, 80),
              (50, 3, 79), (51, 3, 71), (53, 3, 54), (56, 37, 47),
              (57, 6, 63), (59, 13, 48), (60, 3, 66), (61, 2, 51),
              (62, 3, 70), (63, 3, 66), (64, 3, 53), (65, 2, 51),
              (66, 3, 38), (67, 3, 56), (68, 3, 24), (69, 3, 83),
              (84, 68, 72), (85, 3, 116), (86, 3, 30)],
}


def _arch_owner(title, references):
    return dict(title=title, headingCells=references)


ARCHITECTURE_OWNERS = {
    "rex-syntax": _arch_owner("1.1.1.2 REX Prefix", architecture_refs(45, 18)),
    "instruction-memory": _arch_owner("Representation in Memory", architecture_refs(46, 29, 30)),
    "prefix-summary": _arch_owner("Summary of Legacy Prefixes", architecture_refs(48, 7, 8)),
    "prefix-table": _arch_owner("Table 1-1. Legacy Instruction Prefixes", architecture_refs(49, 3)),
    "operand-size": _arch_owner("Operand-Size Override Prefix", architecture_refs(49, 76, 77)),
    "address-size": _arch_owner("Address-Size Override Prefix", architecture_refs(51, 9, 10)),
    "rex-prefix": _arch_owner("REX Prefix", architecture_refs(56, 37, 38)),
    "modrm": _arch_owner("ModRM Byte Format", architecture_refs(59, 29, 30)),
    "sib": _arch_owner("SIB Byte Format", architecture_refs(61, 2) + architecture_refs(61, 4)),
    "legacy-addressing": _arch_owner("Operand Addressing in Legacy 32-bit and Compatibility Modes", architecture_refs(62, 67, 68)),
    "long-addressing": _arch_owner("Operand Addressing in 64-bit Mode", architecture_refs(65, 2) + architecture_refs(65, 4)),
    "displacements": _arch_owner("Displacement Bytes", architecture_refs(66, 6, 7)),
    "immediates": _arch_owner("Immediate Bytes", architecture_refs(66, 20, 21)),
    "rip-addressing": _arch_owner("RIP-Relative Addressing", architecture_refs(66, 29, 30)),
    "rex-encodings": _arch_owner("Encoding Considerations Using REX", architecture_refs(68, 5, 6)),
    "byte-registers": _arch_owner("Byte-Register Addressing", architecture_refs(68, 10, 11)),
    "data-segments": _arch_owner("Figure 2-4. Segment Registers", architecture_refs(86, 30)),
    "address-arithmetic": _arch_owner("2.2.3.1 Long-Mode Zero-Extension of 16-Bit and 32-Bit Addresses",
                                       architecture_refs(54, 35, publication="24592")),
}


def _arch_rule(owner, references, parameters, text, dependencies=()):
    return dict(owner=owner, sourceCells=references, parameters=parameters,
                requiredText=list(text), dependencies=list(dependencies))


ARCHITECTURE_RULES = {
    "prefix-group-order": _arch_rule("prefix-summary", architecture_refs(48, 9, 13),
        dict(groups=5, maximumPerGroup=1, order="any-within-legacy-prefix-position", duplicateGroupOutcome="undefined",
             applicability="effective-prefix-groups; instruction/null-prefix exceptions require separate resolution"),
        ["five groups", "maximum of one", "any order", "undefined"], ("null-segment-prefix-exception", "prefix-note-2", "prefix-note-6")),
    "legacy-prefix-byte-groups": _arch_rule("prefix-table", architecture_refs(49, 4, 64),
        dict(operandSize=["66"], addressSize=["67"], segment=["2e", "3e", "26", "64", "65", "36"],
             lock=["f0"], repeat=["f2", "f3"], applicability="instruction-dependent"),
        ["66 2", "67 3", "F0 5", "F3 6", "F2 6"], ("prefix-note-1", "prefix-note-2", "prefix-note-3", "prefix-note-4", "prefix-note-5", "prefix-note-6")),
    "rex-placement-count": _arch_rule("rex-prefix", architecture_refs(56, 39, 42) + architecture_refs(57, 10, 27) + architecture_refs(57, 60, 63),
        dict(byteMin=64, byteMax=79, highNibble=4, maximumCount=1, position="immediately-before-opcode-or-first-escape", mode=64),
        ["40h to 4Fh", "only one REX prefix", "immediately precede"]),
    "rex-extended-prefix-exclusion": _arch_rule("rex-syntax", architecture_refs(45, 19, 24),
        dict(forbiddenTogether=["VEX", "XOP", "EVEX"], outcome="#UD"), ["not allowed", "VEX, XOP, or EVEX", "#UD"]),
    "instruction-length-limit": _arch_rule("instruction-memory", architecture_refs(46, 31, 34),
        dict(maximumBytes=15, excessOutcome="#GP", byteOrder="little-endian"),
        ["little-endian", "less than or equal to 15", "general-protection exception"]),
    "operand-size-override": _arch_rule("operand-size", architecture_refs(50, 9, 43) + architecture_refs(50, 63, 77) + architecture_refs(65, 40, 45),
        dict(typicalDefaultBits=32, prefix66Bits=16, rexWBits=64, rexWOverrides66=True,
             byteOperationsUnaffected=True, default64Exceptions="instruction-dependent",
             applicability="general-purpose operand-size modifier; SIMD opcode extensions are separate"),
        ["default operand", "takes precedence", "no effect on byte", "REX.W"], ("operand-note-2", "operand-note-3", "default64-instruction-exceptions")),
    "address-size-override": _arch_rule("address-size", architecture_refs(51, 11, 20) + architecture_refs(51, 67, 71),
        dict(defaultBits=64, prefix67Bits=32, permittedBits=[32, 64], implicitCountAffected=True, implicitStackBits=64),
        ["all stack references have a 64-bit address size", "16-bit addresses are not supported", "RCX"], ("address-note-1",)),
    "address-size-truncation": _arch_rule("address-arithmetic", architecture_refs(54, 31, 39, "24592") + architecture_refs(67, 55, 56) + architecture_refs(68, 3, 4),
        dict(effectiveAddressBits=[32, 64], arithmetic="truncate-to-effective-address-size-then-zero-extend-to-64",
             ripRelativeStillEnabledWith67=True),
        ["first truncated", "then zero-extended", "truncate and zero-extend", "does not disable RIP-relative"]),
    "modrm-fields": _arch_rule("modrm", architecture_refs(59, 23, 48) + architecture_refs(60, 6, 17),
        dict(modBits=[7, 6], regBits=[5, 4, 3], rmBits=[2, 1, 0], registerMod=3, memoryMods=[0, 1, 2],
             regRole="instruction-dependent-register-or-opcode-extension"),
        ["Bits[7:6]", "Bits[5:3]", "Bits[2:0]", "11b specifies the register-direct"]),
    "modrm-memory-displacements": _arch_rule("legacy-addressing", architecture_refs(63, 3, 66) + architecture_refs(64, 33, 53),
        dict(normalModDisplacementBytes={"0": 0, "1": 1, "2": 4}, exceptionalMod0Selectors=["rm=5", "rm=4,sib.base=5"],
             mode64ReinterpretsRm5="rip-relative"),
        ["[rAX]+disp8", "[rAX]+disp32", "one- or 4-byte", "changed to RIP-relative"], ("modrm-sib-note-1", "modrm-sib-note-2", "modrm-sib-note-3")),
    "sib-presence": _arch_rule("legacy-addressing", architecture_refs(64, 41, 50) + architecture_refs(69, 6, 8) + architecture_refs(69, 20, 34),
        dict(memoryMods=[0, 1, 2], rmLowBits=4, rexBDoesNotRemoveSib=True, order="after-modrm"),
        ["mod ≠ 11b, r/m = 100b", "SIB byte is present", "also required for R12-"], ("modrm-note-3",)),
    "sib-fields-scale": _arch_rule("sib", architecture_refs(61, 5, 51),
        dict(scaleBits=[7, 6], indexBits=[5, 4, 3], baseBits=[2, 1, 0], scaleFactors=[1, 2, 4, 8]),
        ["SIB.scale (Bits[7:6])", "SIB.index (Bits[5:3])", "SIB.base (Bits[2:0])"]),
    "sib-address-equation": _arch_rule("sib", architecture_refs(61, 8, 11) + architecture_refs(64, 41, 50),
        dict(equation="scale*index+base+signed-displacement", absentTerms=0),
        ["effective_address = scale * index + base + offset", "set one or more elements of the sum to zero"], ("signed-displacement",)),
    "rex-register-extension": _arch_rule("long-addressing", architecture_refs(65, 13, 39) + architecture_refs(65, 46, 49),
        dict(rexBit=2, field="modrm.reg", extensionBit=3, opcodeExtensionUnaffected=True),
        ["REX.R", "ModRM.reg", "extend the opcode", "ignored in such cases"], ("rex-field-note-1",)),
    "rex-index-extension": _arch_rule("long-addressing", architecture_refs(65, 28, 31) + architecture_refs(65, 50, 51),
        dict(rexBit=1, field="sib.index", extensionBit=3), ["REX.X", "SIB.index"], ("rex-field-note-1",)),
    "rex-base-extension": _arch_rule("long-addressing", architecture_refs(65, 32, 36) + architecture_refs(66, 3, 5),
        dict(rexBit=0, fields=["modrm.rm", "sib.base", "opcode.reg"], extensionBit=3),
        ["REX.B", "ModRM.r/m", "SIB.base", "opcode reg field"], ("rex-field-note-1", "sib-base5-no-base", "rip-relative-selector")),
    "rex-high-byte-exclusion": _arch_rule("byte-registers", architecture_refs(68, 12, 17) + architecture_refs(84, 68, 72) + architecture_refs(85, 3) + architecture_refs(85, 110, 111),
        dict(highBytes=["ah", "bh", "ch", "dh"], highBytesAllowedWithRex=False,
             rexLowByteRegisters=["spl", "bpl", "sil", "dil"], byteWritesPreserveOtherBits=True),
        ["not available if the REX prefix is used", "high bits of word and byte operands are not modified"], ("byte-high-note", "byte-low-note")),
    "rip-relative-selector": _arch_rule("rip-addressing", architecture_refs(67, 12, 16) + architecture_refs(67, 46, 52),
        dict(mod=0, rmLowBits=5, sibPresent=False, displacementBytes=4, rexBIgnored=True),
        ["00101b", "RIP + disp32", "not affected by the REX prefix", "REX.B = 1"]),
    "rip-relative-next-ip": _arch_rule("rip-addressing", architecture_refs(66, 31, 38) + architecture_refs(67, 3, 5),
        dict(base="next-instruction-rip", signedDisplacementBits=32), ["RIP of the next instruction", "signed 32-bit displacement"]),
    "sib-base5-no-base": _arch_rule("rex-encodings", architecture_refs(62, 24, 26) + architecture_refs(62, 36, 38) + architecture_refs(62, 48, 57) + architecture_refs(69, 15, 17) + architecture_refs(69, 61, 78),
        dict(mod=0, sibBaseLowBits=5, baseAbsent=True, displacementBytes=4, rexBIgnored=True),
        ["ModRM.mod = 00b", "register specification is null", "disp32", "not decoded (don’t care)"], ("sib-base-note-2", "special-rex-note-1")),
    "sib-index4-no-index": _arch_rule("rex-encodings", architecture_refs(62, 21, 23) + architecture_refs(62, 34, 35) + architecture_refs(69, 12, 14) + architecture_refs(69, 50, 60),
        dict(indexLowBits=4, absentWhenRexX=0, rexX1Register="r12", ignoredScaleWhenAbsent=True),
        ["scale*index", "set to 0", "bit (x), which is decoded", "allowing R12 to"], ("sib-index-note-1", "special-rex-note-1")),
    "signed-displacement": _arch_rule("displacements", architecture_refs(66, 8, 19),
        dict(documentedBytes=[1, 2, 4], longModeModrmBytes=[1, 4], signed=True, long64SignExtendTo=64, order="after-opcode-modrm-or-sib",
             evexCompressedDisplacement="separate-unresolved-rule"),
        ["signed value", "sign-extended to 64 bits", "one-byte displacements are scaled"], ("modrm-memory-displacements", "evex-disp8-scaling", "mov64-displacement-exception")),
    "flat-data-segments": _arch_rule("data-segments", architecture_refs(85, 115, 116) + architecture_refs(86, 3, 6),
        dict(mode=64, zeroBaseSegments=["ds", "es", "ss"], segmentLimitsChecked=False,
             fsGs="separate-explicit-base-premise"), ["base for each of these segments is assumed to be zero", "neither their segment limit nor attributes are checked"], ("segmented-memory-cross-volume",)),
    "immediate-order-width": _arch_rule("immediates", architecture_refs(66, 22, 28) + architecture_refs(46, 25, 28),
        dict(bytes=[1, 2, 4, 8], order="after-opcode-modrm-sib-or-displacement", eightBytes="specific-mov-gpr-only"),
        ["64-bit immediates are allowed", "MOV instructions that load GPRs", "follow the opcode, ModRM, SIB, or displacement"], ("mov64-displacement-exception",)),
}


def _arch_reference(kind, owner, origins, targets, status, description, marker=None):
    return dict(kind=kind, owner=owner, sourceCells=origins, targetCells=targets,
                status=status, description=description, marker=marker)


ARCHITECTURE_REFERENCES = {
    "prefix-note-1": _arch_reference("footnote", "prefix-table", architecture_refs(49, 4), architecture_refs(49, 66, 67), "resolved-location", "One prefix per override group; lock/repeat modifier restriction.", "1."),
    "prefix-note-2": _arch_reference("footnote", "prefix-table", architecture_refs(49, 12), architecture_refs(49, 68, 70), "unresolved-applicability", "Opcode-extension and instruction-specific operand-size exclusions remain to be enumerated.", "2."),
    "prefix-note-3": _arch_reference("footnote", "prefix-table", architecture_refs(49, 16), architecture_refs(49, 71), "resolved-location", "Address override also changes an implied RCX count.", "3."),
    "prefix-note-4": _arch_reference("footnote", "prefix-table", architecture_refs(49, 20) + architecture_refs(49, 24) + architecture_refs(49, 28) + architecture_refs(49, 40), architecture_refs(49, 72), "unresolved-applicability", "Upper Address Ignore qualifies the ignored segment-override rule.", "4."),
    "prefix-note-5": _arch_reference("footnote", "prefix-table", architecture_refs(49, 44), architecture_refs(49, 73), "unresolved-instruction-set", "The exact instruction set admitting LOCK is outside this slice.", "5."),
    "prefix-note-6": _arch_reference("footnote", "prefix-table", architecture_refs(49, 55, 56), architecture_refs(49, 74, 75), "unresolved-source-scope", "The note narrows repeat use to compare/scan while the table also lists count-only string operations; do not infer a universal correction.", "6."),
    "operand-note-2": _arch_reference("footnote", "operand-size", architecture_refs(50, 16), architecture_refs(50, 64, 65), "unresolved-instruction-set", "Typical32-bit default has instruction-dependent exceptions in Appendix B.", "2."),
    "operand-note-3": _arch_reference("footnote", "operand-size", architecture_refs(50, 34), architecture_refs(50, 66), "resolved-location", "REX source section located explicitly.", "3."),
    "address-note-1": _arch_reference("footnote", "address-size", architecture_refs(51, 40), architecture_refs(51, 68), "resolved-location", "Table no means default address size.", "1."),
    "modrm-note-3": _arch_reference("footnote", "modrm", architecture_refs(60, 45), architecture_refs(60, 62), "resolved-location", "SIB follows ModRM for indexed addressing.", "3."),
    "modrm-note-4": _arch_reference("footnote", "modrm", architecture_refs(60, 49), architecture_refs(60, 63, 65), "resolved-location", "Mod0/rm5 is replaced by RIP-relative addressing in64-bit mode.", "4."),
    "sib-index-note-1": _arch_reference("footnote", "sib", architecture_refs(62, 22), architecture_refs(62, 34, 35), "resolved-location", "Absent index contributes zero; REX.X qualification is separately bound.", "1."),
    "sib-base-note-2": _arch_reference("footnote", "sib", architecture_refs(62, 26), architecture_refs(62, 36, 38), "resolved-location", "Base5 contributes zero only when ModRM.mod=0.", "2."),
    "modrm-sib-note-1": _arch_reference("footnote", "legacy-addressing", architecture_refs(63, 19), architecture_refs(63, 60, 62), "resolved-location", "No-displacement SIB form except base5 special case.", "1."),
    "modrm-sib-note-2": _arch_reference("footnote", "legacy-addressing", architecture_refs(63, 35), architecture_refs(63, 63, 64), "resolved-location", "Mod1SIB form has one-byte displacement.", "2."),
    "modrm-sib-note-3": _arch_reference("footnote", "legacy-addressing", architecture_refs(63, 51), architecture_refs(63, 65, 66), "resolved-location", "Mod2SIB form has four-byte displacement.", "3."),
    "rex-field-note-1": _arch_reference("footnote", "long-addressing", architecture_refs(65, 27) + architecture_refs(65, 30) + architecture_refs(65, 35), architecture_refs(65, 38, 39), "resolved-location", "REX field descriptions refer back to ModRM/SIB.", "1."),
    "special-rex-note-1": _arch_reference("footnote", "rex-encodings", architecture_refs(69, 8) + architecture_refs(69, 11) + architecture_refs(69, 13, 14), architecture_refs(69, 80, 82), "resolved-location", "Fourth extension bit notation and ignored ModRM selector bit.", "1."),
    "byte-high-note": _arch_reference("footnote", "byte-registers", architecture_refs(85, 16) + architecture_refs(85, 22) + architecture_refs(85, 28) + architecture_refs(85, 34), architecture_refs(85, 110), "resolved-location", "High-byte registers excluded by REX.", "*"),
    "byte-low-note": _arch_reference("footnote", "byte-registers", architecture_refs(85, 40) + architecture_refs(85, 45) + architecture_refs(85, 50) + architecture_refs(85, 55), architecture_refs(85, 111), "resolved-location", "Uniform byte registers require REX.", "**"),
    "default64-instruction-exceptions": _arch_reference("cross-reference", "operand-size", architecture_refs(50, 64, 77), [], "unresolved-instruction-set", "Appendix B and Volume1 near-branch/stack clauses require full exception inventory."),
    "evex-disp8-scaling": _arch_reference("cross-reference", "displacements", architecture_refs(66, 18, 19), [], "unresolved-architectural-rule", "Volume1Section4.13.8 Disp8*N requires a separate EVEX rule; ordinary signed displacement is insufficient."),
    "mov64-displacement-exception": _arch_reference("cross-reference", "displacements", architecture_refs(66, 15, 17) + architecture_refs(66, 24, 25), [], "unresolved-instruction-set", "Volume1 Immediate Operand Size exceptions for64-bit MOV forms remain unparsed."),
    "segmented-memory-cross-volume": _arch_reference("cross-reference", "data-segments", architecture_refs(86, 6), [], "unresolved-architectural-rule", "Volume2 Segmented Virtual Memory and FS/GS base/state premises require their own clause inventory."),
    "null-segment-prefix-exception": _arch_reference("cross-reference", "prefix-summary", architecture_refs(48, 24, 25), architecture_refs(53, 47, 54), "unresolved-applicability", "Nearby null-prefix prose omits the Upper Address Ignore qualification in the table note; do not apply prefix-group repetition rules universally."),
    "address-arithmetic-cross-volume": _arch_reference("cross-reference", "rip-addressing", architecture_refs(67, 55, 56) + architecture_refs(68, 3, 4), architecture_refs(54, 35, 39, "24592"), "resolved-location", "Volume1 explicitly specifies truncate then zero-extend for effective-address calculations."),
}


def source_ids(kind):
    return [f"pdf:{page}:cell:{index}" for page, start, end in SOURCE_RANGES[kind] for index in range(start, end + 1)]


def validate_pack_structure(pack, *, root=ROOT):
    from amd64_manual_geometry import extractor_sources
    root = Path(root)
    fields(pack, {"schema", "scope", "source", "extractor", "sourceCells", "clauses", "review"}, "source constraints")
    require(pack["schema"] == SCHEMA, "source constraint schema")
    fields(pack["scope"], {"id", "vendor", "mode", "selectedConstraintKinds", "sourceComplete", "allArchitecturalConstraintsParsed"}, "constraint scope")
    require(canonical(pack["scope"]) == canonical(dict(id=PACK_SCOPE, vendor="AMD", mode=64,
        selectedConstraintKinds=sorted(SOURCE_RANGES), sourceComplete=False, allArchitecturalConstraintsParsed=False)),
        "source pack cannot narrow reviewed clauses or assert whole-source completeness")
    source = pack["source"]
    fields(source, {"lockPath", "lockSha256", "publication", "revision", "pdfSha256"}, "source pin")
    require(source == dict(lockPath=SOURCE_LOCK, lockSha256=sha(root / SOURCE_LOCK), publication="24594", revision="3.38", pdfSha256=PDF_SHA),
            "source publication/lock pin differs")
    pin = [row for row in read(root / SOURCE_LOCK)["sources"] if row["publication"] == source["publication"]]
    require(len(pin) == 1 and pin[0]["sha256"] == PDF_SHA and pin[0]["revision"] == "3.38", "official source identity")
    fields(pack["extractor"], {"bboxSha256", "sourceSha256"}, "source geometry extractor")
    require(pack["extractor"] == dict(bboxSha256=BBOX_SHA, sourceSha256=extractor_sources(root)), "stale source geometry/extractor")
    fields(pack["review"], {"derivation", "premises", "limits"}, "source review")
    require(pack["review"]["derivation"] == "reviewed-amd-mov8-register-rules/v1" and
            all(isinstance(pack["review"][key], str) and pack["review"][key] for key in ("premises", "limits")), "missing source-addressed review")
    expected_ids = {key for kind in SOURCE_RANGES for key in source_ids(kind)}
    require(isinstance(pack["sourceCells"], list), "source cell array")
    cells = {}
    for cell in pack["sourceCells"]:
        fields(cell, {"id", "pdfSha256", "pdfPage", "rect", "wordSpan", "unicodeSha256", "wordBoxesSha256"}, "source cell")
        require(cell["id"] in expected_ids and cell["id"] not in cells and cell["pdfSha256"] == PDF_SHA
                and type(cell["pdfPage"]) is int and cell["id"].startswith(f"pdf:{cell['pdfPage']}:cell:"), "duplicate/orphan source cell")
        require(isinstance(cell["rect"], list) and len(cell["rect"]) == 4 and
                all(type(value) in {int, float} and math.isfinite(value) for value in cell["rect"]) and
                0 <= cell["rect"][0] < cell["rect"][2] and 0 <= cell["rect"][1] < cell["rect"][3], "source rectangle")
        require(isinstance(cell["wordSpan"], list) and len(cell["wordSpan"]) == 2 and
                all(type(value) is int for value in cell["wordSpan"]) and 0 <= cell["wordSpan"][0] < cell["wordSpan"][1]
                and all(re.fullmatch(r"[0-9a-f]{64}", cell[key] or "") for key in ("unicodeSha256", "wordBoxesSha256")), "source word/hash identity")
        cells[cell["id"]] = cell
    require(set(cells) == expected_ids, "reviewed source cells omitted")
    require(isinstance(pack["clauses"], list) and len(pack["clauses"]) == len(SOURCE_RANGES), "source clause count")
    seen = set()
    for clause in pack["clauses"]:
        fields(clause, {"id", "kind", "parameters", "sourceCells"}, "typed source clause")
        kind = clause["kind"]
        require(kind in SOURCE_RANGES and clause["id"] == kind and kind not in seen, "unknown/duplicate typed source clause")
        seen.add(kind)
        require(canonical(clause["parameters"]) == canonical(CLAUSE_PARAMETERS[kind]), "typed source constraint differs from reviewed derivation")
        require(clause["sourceCells"] == source_ids(kind), "source role differs from exact reviewed cells")
    require(seen == set(SOURCE_RANGES), "typed source clause omission")
    return cells


def validate_pack_cells(pack, pages, *, root=ROOT):
    """Replay geometry, independent of metadata hashes supplied by the pack."""
    references = validate_pack_structure(pack, root=root)
    require(isinstance(pages, list) and len({page["pdfPage"] for page in pages}) == len(pages), "duplicate source pages")
    selected = [cell for page in pages for cell in page["cells"] if cell["id"] in references]
    actual = {cell["id"]: cell for cell in selected}
    require(len(actual) == len(selected), "duplicate actual source cells")
    require(set(actual) == set(references), "actual source cells omitted")
    for key, reference in references.items():
        require(actual[key]["unicodeSha256"] == hashlib.sha256(actual[key]["text"].encode()).hexdigest()
                and actual[key]["wordBoxesSha256"] == hashlib.sha256(canonical(actual[key]["wordBoxes"]).encode()).hexdigest(),
                "actual source text/word boxes do not reproduce their hashes")
        observed = {name: actual[key][name] for name in reference if name != "pdfSha256"}
        require(canonical(observed) == canonical({name: value for name, value in reference.items() if name != "pdfSha256"}),
                "actual source bytes/geometry disagree with reviewed anchors")
    return len(references)


def validate_pack(pack, pdf_path, bbox_path, *, root=ROOT):
    from amd64_manual_geometry import read_geometry
    validate_pack_structure(pack, root=root)
    require(sha(pdf_path) == PDF_SHA, "actual AMD PDF differs from official source pin")
    require(sha(bbox_path) == BBOX_SHA, "actual word-box product differs from reviewed extraction")
    count = validate_pack_cells(pack, read_geometry(bbox_path), root=root)
    return dict(status="checked", sourceCellsReplayed=count, typedClauses=len(SOURCE_RANGES),
                sourceComplete=False, allArchitecturalConstraintsParsed=False, fullAmd64Coverage=False,
                derivationTrust="Reviewed finite MOV8 source rules; not an automated whole-manual legality proof")


def architecture_scope_ids():
    return {key for publication, ranges in ARCHITECTURE_REGIONS.items()
            for page, start, end in ranges for key in architecture_refs(page, start, end, publication)}


def architecture_clauses():
    return [dict(id=name, kind=name, **{key: value for key, value in rule.items() if key != "requiredText"})
            for name, rule in ARCHITECTURE_RULES.items()]


def architecture_references():
    return [dict(id=name, **reference) for name, reference in ARCHITECTURE_REFERENCES.items()]


def architecture_source_closure(root=ROOT):
    from amd64_manual_geometry import extractor_sources
    result = extractor_sources(root)
    for relative in ("tools/amd64_source_constraints.py", "tools/amd64_domains.py",
                     "tests/bap/fixtures/amd64-semantics/architecture-constraints-v1.json"):
        result[relative] = sha(Path(root) / relative)
    return result


def validate_architecture_pack_structure(pack, *, root=ROOT):
    from amd64_manual_geometry import extractor_sources
    from amd64_source_corpus import LOCK, validate_lock
    root = Path(root)
    fields(pack, {"schema", "scope", "corpusLockSha256", "sources", "extractorSources", "regions",
                  "owners", "sourceCells", "clauses", "references", "review"}, "architecture constraints")
    expected_scope = dict(id=ARCHITECTURE_SCOPE, vendor="AMD", mode=64, encoding="legacy-with-optional-rex",
                          sourceComplete=False, allArchitecturalConstraintsParsed=False)
    require(pack["schema"] == ARCHITECTURE_SCHEMA and canonical(pack["scope"]) == canonical(expected_scope),
            "architecture scope differs or promotes source completeness")
    lock_path = root / LOCK.relative_to(ROOT)
    require(pack["corpusLockSha256"] == sha(lock_path), "architecture corpus pin differs")
    lock = validate_lock(read(lock_path))
    require(pack["sources"] == ARCHITECTURE_SOURCES, "architecture selected publication/product identities differ")
    for publication, source in ARCHITECTURE_SOURCES.items():
        document = next(row for row in lock["documents"] if row["publication"] == publication)
        require(all(document[key] == source[key] for key in ("revision", "filename", "pdfSha256")),
                "architecture source does not match its exact corpus document")
    require(pack["extractorSources"] == extractor_sources(root), "architecture geometry implementation drift")
    require(canonical(pack["regions"]) == canonical(ARCHITECTURE_REGIONS), "architecture selected region omission or substitution")
    require(canonical(pack["owners"]) == canonical(ARCHITECTURE_OWNERS), "architecture source owner differs")
    require(canonical(pack["clauses"]) == canonical(architecture_clauses()), "architecture typed clause omission, parameters or ownership differ")
    require(canonical(pack["references"]) == canonical(architecture_references()), "architecture footnote/cross-reference omission, target or status differs")
    fields(pack["review"], {"derivation", "limits"}, "architecture review")
    require(pack["review"]["derivation"] == "reviewed-legacy-prefix-modrm-sib-rules/v1"
            and isinstance(pack["review"]["limits"], str) and pack["review"]["limits"], "architecture review missing")
    require(isinstance(pack["sourceCells"], list), "architecture source cell list")
    references = {}
    expected = architecture_scope_ids()
    for cell in pack["sourceCells"]:
        fields(cell, {"publication", "id", "pdfSha256", "pdfPage", "rect", "wordSpan", "unicodeSha256", "wordBoxesSha256"},
               "architecture source cell")
        key = cell["publication"] + "/" + cell["id"]
        require(key in expected and key not in references and cell["pdfSha256"] == ARCHITECTURE_SOURCES[cell["publication"]]["pdfSha256"],
                "architecture source cell duplicate, owner or PDF identity")
        require(type(cell["pdfPage"]) is int and cell["id"].startswith(f"pdf:{cell['pdfPage']}:cell:"), "architecture source page identity")
        require(isinstance(cell["rect"], list) and len(cell["rect"]) == 4
                and all(type(v) in {int, float} and math.isfinite(v) for v in cell["rect"])
                and 0 <= cell["rect"][0] < cell["rect"][2] and 0 <= cell["rect"][1] < cell["rect"][3],
                "architecture source rectangle")
        require(isinstance(cell["wordSpan"], list) and len(cell["wordSpan"]) == 2
                and all(type(v) is int for v in cell["wordSpan"]) and 0 <= cell["wordSpan"][0] < cell["wordSpan"][1]
                and all(re.fullmatch(r"[0-9a-f]{64}", cell[key] or "") for key in ("unicodeSha256", "wordBoxesSha256")),
                "architecture source word/hash identity")
        references[key] = cell
    require(set(references) == expected, "architecture selected source cells omitted")
    for owner in ARCHITECTURE_OWNERS.values():
        require(set(owner["headingCells"]) <= expected, "architecture owner heading outside scope")
    available_dependencies = set(ARCHITECTURE_RULES) | set(ARCHITECTURE_REFERENCES)
    for rule in ARCHITECTURE_RULES.values():
        require(rule["owner"] in ARCHITECTURE_OWNERS and set(rule["sourceCells"]) <= expected
                and set(rule["dependencies"]) <= available_dependencies, "architecture rule has a dangling source or dependency")
    for reference in ARCHITECTURE_REFERENCES.values():
        require(set(reference["sourceCells"] + reference["targetCells"]) <= expected, "architecture reference outside scope")
    return references


def validate_architecture_pack_cells(pack, source_pages, *, root=ROOT):
    """Replay selected cells, semantic premises and owned footnote locations.

    This pure layer accepts small actual-source excerpts for omission controls.
    Production validation additionally requires the exact PDF and full bbox
    products. Unparsed cells and unresolved references are output obligations.
    """
    references = validate_architecture_pack_structure(pack, root=root)
    require(set(source_pages) == set(ARCHITECTURE_SOURCES), "architecture actual source publication omitted")
    actual = {}
    for publication, pages in source_pages.items():
        require(isinstance(pages, list) and len(pages) == len({p["pdfPage"] for p in pages}), "architecture actual page duplicate")
        for page in pages:
            for cell in page["cells"]:
                key = publication + "/" + cell["id"]
                if key not in references:
                    continue
                require(key not in actual and cell["pdfPage"] == page["pdfPage"], "architecture actual cell duplicate or wrong page")
                require(cell["unicodeSha256"] == hashlib.sha256(cell["text"].encode()).hexdigest(), "architecture actual text hash differs")
                if "wordBoxes" in cell:
                    require(cell["wordBoxesSha256"] == hashlib.sha256(canonical(cell["wordBoxes"]).encode()).hexdigest(),
                            "architecture actual word boxes differ")
                expected = {k: v for k, v in references[key].items() if k not in {"publication", "pdfSha256"}}
                require(canonical({k: cell[k] for k in expected}) == canonical(expected), "architecture actual source geometry or text differs")
                actual[key] = cell
    require(set(actual) == set(references), "architecture actual source cell omission")

    def text(keys):
        return " ".join(" ".join(actual[key]["text"] for key in keys).split())

    used = set()
    for name, owner in ARCHITECTURE_OWNERS.items():
        require(owner["title"] in text(owner["headingCells"]), "architecture source section heading mismatch: " + name)
        used.update(owner["headingCells"])
    for name, rule in ARCHITECTURE_RULES.items():
        evidence = text(rule["sourceCells"])
        require(all(part in evidence for part in rule["requiredText"]), "architecture source does not establish reviewed rule: " + name)
        used.update(rule["sourceCells"])
    for name, reference in ARCHITECTURE_REFERENCES.items():
        used.update(reference["sourceCells"] + reference["targetCells"])
        if reference["kind"] == "footnote":
            origins = [actual[key] for key in reference["sourceCells"]]
            targets = [actual[key] for key in reference["targetCells"]]
            require(targets and targets[0]["text"].split()[0] == reference["marker"], "architecture footnote marker differs: " + name)
            require(len({cell["pdfPage"] for cell in origins + targets}) == 1
                    and max(cell["rect"][1] for cell in origins) < min(cell["rect"][1] for cell in targets),
                    "architecture footnote target precedes or belongs outside its source table: " + name)
    unparsed = []
    for key in sorted(set(actual) - used):
        cell = actual[key]
        # Only recognized running document furniture is harmless. Diagrams,
        # labels, prose and unselected notes remain explicit source obligations.
        if cell["rect"][1] < 85 and (cell["text"] in {"[AMD Public Use]", "AMD64 Technology"}
                or re.fullmatch(r"[0-9]{5}—Rev\. [0-9.]+—[A-Za-z]+ [0-9]{4}", cell["text"])):
            continue
        unparsed.append(dict(sourceCell=key, status="unparsed", unicodeSha256=cell["unicodeSha256"]))
    return dict(schema="ariadne.amd64-architecture-constraint-assessment/v1", status="checked",
                scope=ARCHITECTURE_SCOPE, sourceCellsReplayed=len(actual), typedClauses=len(ARCHITECTURE_RULES),
                clauses=architecture_clauses(), references=architecture_references(),
                unresolvedReferences=[name for name, ref in ARCHITECTURE_REFERENCES.items() if ref["status"] != "resolved-location"],
                unparsedSourceCells=unparsed, sourceComplete=False, allArchitecturalConstraintsParsed=False,
                sourceCellsParsedCompletely=False, fullAmd64Coverage=False, corpusAdoption=False,
                derivationTrust="Reviewed selected legacy encoding clauses; reference location does not discharge instruction applicability or unparsed regions")


def validate_architecture_pack(pack, pdf_path, bbox_path, *, root=ROOT):
    """Validate Vol3 plus its explicitly pinned Vol1 arithmetic reference.

    The supplied Vol3 PDF and bbox are in the complete source-corpus cache/layout:
    Vol1 uses the declared basename in the same PDF cache and the sibling
    publication directory in the corpus. A missing reference is an error.
    """
    from amd64_manual_geometry import read_geometry
    validate_architecture_pack_structure(pack, root=root)
    pdf_path, bbox_path = Path(pdf_path), Path(bbox_path)
    paths = {"24594": (pdf_path, bbox_path),
             "24592": (pdf_path.parent / ARCHITECTURE_SOURCES["24592"]["filename"], bbox_path.parent.parent / "24592" / "bbox.html")}
    pages = {}
    for publication, (pdf, bbox) in paths.items():
        source = ARCHITECTURE_SOURCES[publication]
        require(sha(pdf) == source["pdfSha256"] and sha(bbox) == source["bboxSha256"],
                "architecture actual PDF/geometry product differs: " + publication)
        pages[publication] = read_geometry(bbox)
    return validate_architecture_pack_cells(pack, pages, root=root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", type=Path)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--bbox", type=Path, required=True)
    args = parser.parse_args()
    pack = read(args.pack)
    validator = validate_architecture_pack if pack.get("schema") == ARCHITECTURE_SCHEMA else validate_pack
    print(canonical(validator(pack, args.pdf, args.bbox)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
