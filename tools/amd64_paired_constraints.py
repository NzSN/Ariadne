#!/usr/bin/env python3
"""Selected predecessor/publisher claims for the other three paired families.

Literal source agreement is scoped to named clauses. It confers neither whole
section equivalence nor encoding legality, numeric semantics or runtime admission.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import tempfile

import amd64_conversion_constraints as conversion
from run_output import run_output

entry = conversion.entry
ROOT = entry.ROOT
INPUT = ROOT / "tests/bap/fixtures/source-migration/paired-constraints-v1.json"
require = entry.require
cells = conversion.cells
META_FIELDS = conversion.META_FIELDS
FAMILIES = {
    "gf": "VGF2P8AFFINEINVQB",
    "movd": "MOVD, VMOVD",
    "fma": "VFNMADDSS VFNMADD132SS VFNMADD213SS VFNMADD213SS",
}


def rule(owner, old, new, parameters, terms, same=True):
    return dict(owner=owner, predecessor=old, replacement=new, parameters=parameters,
                requiredTerms=terms, selectedTextEqual=same)


RULES = {
    "gf-equation": rule("gf", cells(226,7,14), cells(228,7,14),
        dict(blockBits=64, elementBits=8, matrixByteIndex="7-bit_n", immediateBits=8),
        ["odd_parity", "inverse", "7-bit_n", "imm8"]),
    "gf-legacy-destination": rule("gf", cells(226,309,311), cells(228,293,295),
        dict(firstSourceIsDestination=True, upperBits="preserved"), ["also the destination", "not affected"]),
    "gf-extended-operands": rule("gf", cells(227,3,16), cells(229,3,16),
        dict(widths=[128,256,512], broadcastBits=64, broadcastEncoding="EVEX", destination="third-register"),
        ["128-", "256-bit", "512-bit", "broadcast 64-bit", "third"]),
    "gf-mask": rule("gf", cells(227,17,18), cells(229,17,18),
        dict(maskElementBits=8, memoryFaultSuppression=False), ["8-bit", "do not support memory fault suppression"]),
    "gf-feature-rows": rule("gf", cells(227,22,30), cells(229,21,30),
        dict(legacy=["GFNI"], vex=["AVX","GFNI"], evex128and256=["AVX512VL","GFNI"], evex512=["AVX512F","GFNI"]),
        ["AVX, GFNI", "AVX512VL, GFNI", "AVX512F, GFNI"], False),
    "gf-heading": rule("gf", cells(226,315), cells(228,299),
        dict(oldRunningHeading="HADDPD, VHADDPD", newRunningHeading="GF2P8AFFINEINVQB VGF2P8AFFINEINVQB"), [], False),
    "movd-transfer": rule("movd", cells(339,5,7), cells(341,6,8),
        dict(payloadBits=32, xmmZeroExtensionBits=128, directions=["to-xmm","from-xmm"]), ["32-bit", "zero-extension to 128 bits"]),
    "movd-legacy-upper": rule("movd", cells(339,13,17), cells(341,14,18),
        dict(upperBits="preserved"), ["not affected", "32-bit memory"]),
    "movd-extended-upper": rule("movd", cells(339,20,24), cells(341,21,25),
        dict(upperBits="cleared"), ["cleared", "zero-extended to 128 bits"]),
    "movd-mask": rule("movd", cells(339,25,26), cells(341,26,27),
        dict(kMaskAllowed=False, memoryFaultSuppression=False), ["do not allow a k-mask", "do not", "suppression"]),
    "movd-mode-notes": rule("movd", cells(340,75,76), cells(342,76,77),
        dict(note1="64-bit-only", note2="non-64-bit-only"), ["Note 1:", "Note 2:", "non-64-bit"]),
    "movd-64-vex-store-row": rule("movd", cells(340,29,33), cells(342,27,31),
        dict(operandDirection="from-xmm", literalOpcode="7E /r", literalW=0, note=1),
        ["VMOVD reg32/mem32, xmm", "0.1111.0.01", "7E /r"]),
    "movd-non64-vex-store-row": rule("movd", cells(340,39,43), cells(342,37,41),
        dict(operandDirection="from-xmm", literalOpcode="6E /r", literalW=1, note=2),
        ["VMOVD reg32/mem32, xmm", "1.1111.0.01", "6E /r"]),
    "movd-reserved-vex": rule("movd", cells(340,119,122), cells(342,120,123),
        dict(vvvv="1111", L=0, precedingPrefixesForbidden=["REX","F2","F3","66","F0"]),
        ["VEX.vvvv ! = 1111b", "VEX.L = 1", "Lock prefix"]),
    "fma-rounding": rule("fma", cells(1043,9,14), cells(1173,9,14),
        dict(negateUnroundedProduct=True, resultElementBits=32, rounding=["MXCSR.RC","supported-er"]),
        ["unrounded product", "MXCSR[RC]", "{er}"]),
    "fma-operand-equations": rule("fma", cells(1043,15,26), cells(1173,15,26),
        dict(forms=["four-operand","132","213","231"], destination3="src1"),
        ["−(src1* src3/mem) + src2", "−(src2* src1) + src3/mem", "−(src2* src3/mem) + src1"]),
    "fma-vector-prose": rule("fma", cells(1043,27,32), cells(1173,27,32),
        dict(declaredWidths=[128,256,512]), ["YMM", "ZMM", "EVEX.L’L = 10b"]),
    "fma-four-operand-w": rule("fma", cells(1043,33,37), cells(1173,33,37),
        dict(w0MemorySource=2, w1MemorySource=3, memoryBits=32), ["VEX.W = 0", "VEX.W = 1", "32-bit"]),
    "fma-three-operand-w-prose": rule("fma", cells(1043,38,40), cells(1173,38,40),
        dict(declaredW=1, broadcastBits=32), ["(E)VEX.W is 1", "broadcast 32-bit"]),
    "fma-clear-prose": rule("fma", cells(1043,41,42), cells(1173,41,42),
        dict(destination="XMM", clearRanges=[[32,127],[128,512]]), ["[127:32]", "[512:128]", "cleared"]),
    "fma-mask": rule("fma", cells(1043,43,44), cells(1173,43,44),
        dict(maskElementBits=32, memoryFaultSuppression=True), ["32-bit", "support memory fault suppression"]),
    "fma-vex-three-operand-rows": rule("fma", cells(1044,30,44), cells(1174,26,37),
        dict(literalW=0, opcodes=["9D","AD","BD"], map=2), ["0.src2.X.01", "9D /r", "AD /r", "BD /r"], False),
    "fma-evex-rows": rule("fma", cells(1044,51,92), cells(1174,44,85),
        dict(literalW=0, registerRounding="z.rc.1.V'.aaa", ordinary="z.xx.0.V'.aaa"),
        ["0.vvvv.01", "z.rc.1.V'.aaa", "z.xx.0.V'.aaa", "xmm3/mem32"], False),
    "fma-heading": rule("fma", cells(1043,2,5), cells(1173,5,8),
        dict(oldLast="VFNMADD213SS", newLast="VFNMADD231SS"), ["VFNMADDSS", "VFNMADD132SS"], False),
}

BOUNDARIES = {
    "gf-inverse-table": dict(kind="unreviewed-constraint", rules=["gf-equation"],
        meaning="The complete 256-entry inverse table is not adjudicated; the equation cannot implement numeric GF inversion."),
    "gf-exception-scope": dict(kind="unresolved-reference", rules=["gf-mask","gf-feature-rows"],
        meaning="Whole exception and CPUID cross-reference applicability remains outside this selected pack."),
    "movd-store-opcode": dict(kind="source-conflict", rules=["movd-non64-vex-store-row","movd-64-vex-store-row","movd-mode-notes"],
        meaning="The non-64-bit VEX store row literally uses 6E, unlike the other store rows; no opcode correction is inferred."),
    "fma-w": dict(kind="source-conflict", rules=["fma-three-operand-w-prose","fma-vex-three-operand-rows","fma-evex-rows"],
        meaning="Three-operand prose says W=1 while VEX and EVEX encoding rows literally specify W=0."),
    "fma-vector-scope": dict(kind="source-conflict", rules=["fma-vector-prose","fma-clear-prose","fma-evex-rows"],
        meaning="YMM/ZMM vector prose and broadcast claims require reconciliation with scalar XMM/mem32 encoding rows."),
    "fma-clear-range": dict(kind="source-conflict", rules=["fma-clear-prose"],
        meaning="The literal upper clear range includes bit 512, outside a 512-bit register; it supplies no must-def."),
    "fma-exception-scope": dict(kind="unresolved-reference", rules=["fma-rounding","fma-evex-rows"],
        meaning="IEEE arithmetic, NaN/exception behavior and complete embedded-rounding applicability remain unreviewed."),
}


def validate_structure(pack):
    entry.migration.corpus.fields(pack, {"schema","entryReviewInput","sources","owners","clauses","sourceCells","boundaries"}, "paired source pack")
    require(pack["schema"] == "ariadne.amd64-paired-source-constraints/v1", "paired source schema")
    require(pack["entryReviewInput"] == dict(path=str(entry.INPUT.relative_to(ROOT)), sha256=entry.migration.sha(entry.INPUT)), "paired entry-review pin differs")
    review = entry.reviewed_input(entry.read(entry.INPUT))
    owners = {name: {side: link[side] for side in ("old","new")}
              for name,title in FAMILIES.items() for link in review["pairedFamilies"] if link["old"]["title"] == title}
    require(pack["owners"] == owners, "paired source owner/extent differs")
    require(pack["sources"] == {"predecessor":review["oldPdfSha256"],"replacement":review["newPdfSha256"]}, "paired PDF pins differ")
    require(entry.canonical(pack["clauses"]) == entry.canonical(RULES)
            and entry.canonical(pack["boundaries"]) == entry.canonical(BOUNDARIES), "paired rule or boundary differs")
    require(set(pack["sourceCells"]) == {"predecessor","replacement"}, "paired source sides differ")
    for side in ("predecessor","replacement"):
        anchors = {c for r in RULES.values() for c in r[side]}
        require(set(pack["sourceCells"][side]) == anchors, "paired source anchor omitted/extra")
        for identifier,cell in pack["sourceCells"][side].items():
            require(set(cell) == META_FIELDS and cell["id"] == identifier, "paired anchor identity/fields differ")
    return pack


def clause_observation(pack, name, actual):
    clause = RULES[name]
    texts = {}
    for side,key in (("predecessor","old"),("replacement","new")):
        selected = [actual[side][i] for i in clause[side]]
        owner = pack["owners"][clause["owner"]][key]
        require(all(owner["pdfPage"] <= c["pdfPage"] <= owner["pdfEndPage"] for c in selected), "paired clause escapes owner")
        texts[side] = " ".join(" ".join(c["text"] for c in selected).split())
        require(all(t in texts[side] for t in clause["requiredTerms"]), "paired actual source terms missing: " + name)
    equal = texts["predecessor"] == texts["replacement"]
    require(equal == clause["selectedTextEqual"], "paired selected text relation differs: " + name)
    return dict(selectedTextEqual=equal, textSha256={s:hashlib.sha256(t.encode()).hexdigest() for s,t in texts.items()})


def validate_cells(pack, pages):
    validate_structure(pack)
    actual = {}
    for side in ("predecessor","replacement"):
        anchors = pack["sourceCells"][side]
        selected = [c for page in pages[side] for c in page["cells"] if c["id"] in anchors]
        actual[side] = {c["id"]:c for c in selected}
        require(len(selected) == len(actual[side]) and set(actual[side]) == set(anchors), "paired actual anchor omitted/duplicate")
        for identifier,expected in anchors.items():
            conversion.validate_anchor(expected,actual[side][identifier])
    observations = {name:clause_observation(pack,name,actual) for name in RULES}
    return dict(schema="ariadne.amd64-paired-source-assessment/v1", typedSourceClauses=len(RULES),
        sourceCells=sum(len(v) for v in pack["sourceCells"].values()), clauseObservations=observations,
        boundaries=copy.deepcopy(BOUNDARIES), sourceAdoption=False, wholeSectionSemanticsReviewed=False,
        legalDomainComplete=False, productionAdmission=False, fullAmd64Coverage=False)


def implementation_sources():
    result = conversion.implementation_sources()
    result.update({p:entry.migration.sha(ROOT/p) for p in (
        "tools/amd64_paired_constraints.py","tools/test_amd64_paired_constraints.py",str(INPUT.relative_to(ROOT)))})
    return dict(sorted(result.items()))


def reconstruct(old_cache,publisher_cache,output):
    output = run_output(output)
    require(not output.exists(), "paired review requires fresh output")
    before = implementation_sources()
    pack = validate_structure(entry.read(INPUT))
    parent = output/"conversion-review"
    previous = conversion.reconstruct(old_cache,publisher_cache,parent)
    base = parent/"entry-review/migration"
    pages = {s:entry.migration.geometry.read_geometry(base/s/"26568/bbox.html") for s in ("predecessor","replacement")}
    result = validate_cells(pack,pages)
    result.update(originalMigrationObligations=copy.deepcopy(previous["originalMigrationObligations"]),
                  originalHistoricalGaps=previous["originalHistoricalGaps"], implementation=before,
                  packSha256=entry.migration.sha(INPUT), conversionReviewSha256=entry.migration.sha(parent/"conversion-constraints.json"))
    require(before == implementation_sources(), "paired source/input drift")
    entry.migration._write(output,"paired-constraints.json",result)
    return result


def check(old_cache,publisher_cache,output):
    output = run_output(output)
    require(output.is_dir(), "missing paired review output")
    with tempfile.TemporaryDirectory(prefix="paired-review-replay-",dir=output.parent) as temporary:
        fresh = Path(temporary)/"fresh"
        expected = reconstruct(old_cache,publisher_cache,fresh)
        actual = {str(p.relative_to(output)):p for p in output.rglob("*") if p.is_file()}
        wanted = {str(p.relative_to(fresh)):p for p in fresh.rglob("*") if p.is_file()}
        require(set(actual) == set(wanted), "paired output omitted/extra artifact")
        for name,path in actual.items():
            require(not path.is_symlink() and path.resolve().is_relative_to(output.resolve())
                    and entry.migration.sha(path) == entry.migration.sha(wanted[name]), "paired output differs from fresh source: " + name)
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("extract","check"))
    for name in ("old-cache","publisher-cache","output"):
        parser.add_argument("--"+name,type=Path,required=True)
    args = parser.parse_args()
    result = (reconstruct if args.action == "extract" else check)(args.old_cache,args.publisher_cache,args.output)
    print(json.dumps({k:result[k] for k in ("typedSourceClauses","sourceCells","productionAdmission","fullAmd64Coverage")}))


if __name__ == "__main__":
    main()
