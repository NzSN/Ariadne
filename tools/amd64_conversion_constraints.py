#!/usr/bin/env python3
"""Selected conversion source constraints, with conflicts kept out of admission.

These are source claims and small descriptive query kernels. They neither lift
instructions nor implement IEEE conversion, encoding legality or vector kills.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import tempfile

import amd64_corpus_entry_review as entry
from amd64_inventory_xed import canonical, digest
from run_output import run_output

ROOT = entry.ROOT
INPUT = ROOT / "tests/bap/fixtures/source-migration/conversion-constraints-v1.json"
SCHEMA = "ariadne.amd64-conversion-source-assessment/v1"
require = entry.require
PH = ("VCVTPH2PS", "VCVTPH2PSX")
PS = ("VCVTPS2PH", "VCVTPS2PHX")


def cells(page, first, last=None):
    return [f"pdf:{page}:cell:{i}" for i in range(first, (first if last is None else last)+1)]


def rule(subjects, anchors, parameters, terms):
    return dict(subjects=list(subjects), sourceCells=anchors, parameters=parameters, requiredTerms=terms)


RULES = {
    "ph-lane-payload": rule(PH, cells(942,67,71)+cells(943,4,11),
        dict(sourceElementBits=16, resultElementBits=32, lanes={"128":4,"256":8,"512":16}), ["four","eight","sixteen"]),
    "ps-lane-payload": rule(PS, cells(957,42,53),
        dict(sourceElementBits=32, resultElementBits=16, lanes={"128":4,"256":8,"512":16}), ["four","eight","sixteen"]),
    "ph-base-broadcast": rule(PH[:1],cells(943,13),dict(memoryBroadcast=False),["VCVTPH2PSX","VCVTPH2PS"]),
    "phx-broadcast": rule(PH[1:],cells(942,68,69)+cells(943,10,13),dict(memoryBroadcastBits=16),["broadcast","16-bit"]),
    "ph-base-denormal-prose": rule(PH[:1],cells(942,8,9)+cells(943,14),dict(denormalException=False),["VCVTPH2PS","denormal"]),
    "phx-denormal-prose": rule(PH[1:],cells(943,14),dict(denormalException=True),["VCVTPH2PSX","denormal"]),
    "ph-daz": rule(PH,cells(942,8,9),dict(dazIgnored=True),["MXCSR.DAZ","ignored"]),
    "ph-exact-conversion-prose": rule(PH,cells(942,10,12),dict(roundingApplicable=False),["exactly","rounding"]),
    "ps-base-memory": rule(PS[:1],cells(956,70,72),dict(memoryLoad=False,memoryStore=True),["VCVTPS2PH","store","load"]),
    "psx-memory": rule(PS[1:],cells(956,70,72)+cells(958,40,45),dict(memoryLoad=True,memoryStore=False,memoryBroadcastBits=32),["VCVTPS2PHX","mem32bcst"]),
    "ps-immediate-rounding": rule(PS[:1],cells(957,3,37),dict(selectorBit=2,modeBits=[1,0],immediateModes=["nearest","down","up","truncate"]),["MXCSR.RC","Nearest","Down","Up","Truncate"]),
    "psx-rounding-prose": rule(PS[1:],cells(956,73,74),dict(roundingSourceClaim="MXCSR.RC",claimAlways=True),["VCVTPS2PHX","MXCSR.RC"]),
    "ps-ftz": rule(PS,cells(957,38,39),dict(ftzIgnored=True,halfDenormalsProduced=True),["MXCSR[FTZ]","denormals"]),
    "ph-ymm-clear-statement": rule(PH,cells(943,4,7),dict(resultBits=256,clearLowBit=128,clearHighBit=511),["eight","[511:128]","cleared"]),
    "ph-mask": rule(PH,cells(943,15,16),dict(maskElementBits=32,memoryFaultSuppression=True),["32-bit","suppression"]),
    "ps-mask": rule(PS,cells(957,54,55),dict(maskElementBits=16,memoryFaultSuppression=True),["16-bit","suppression"]),
    "ph-encoding-map": rule(PH,cells(944,21,40)+cells(944,45,81),dict(legacyEvexMap=2,xEvexMap=6,opcode="13"),["RXBR'.2","RXBR'.6","13 /r"]),
    "ps-encoding-map": rule(PS,cells(958,38,45)+cells(958,54,90),dict(legacyEvexMap=3,xEvexMap=5,opcode="1D"),["RXBR'.3","RXBR'.5","1D /r"]),
    "psx-er-encoding-row": rule(PS[1:],cells(958,38,39)+cells(958,71,75),dict(vectorBits=512,registerDecoration="er"),["{er}","z.rc.1.1.aaa"]),
    "ph-f16c-denormal-table": rule(PH[:1],cells(945,96,99)+cells(945,109),dict(denormalExceptionRow=True,applicabilityLabel="F16C"),["(DE)","denormal","F16C"]),
    "phx-feature-table": rule(PH[1:],cells(943,19,30),dict(width128and256=["AVX512VL","AVX512_FP16"],width512=["AVX512_FP16"]),["128,256","512","AVX512_FP16"]),
    "psx-feature-table": rule(PS[1:],cells(958,5,11),dict(listedFeatures=["AVX512VL","AVX512_FP16"],variantWidthNotExplicit=True),["VCVTPS2PHX","AVX512VL, AVX512_FP16"]),
}

BOUNDARIES = {
    "ph-ymm-clear-overlap": dict(kind="source-conflict", rules=["ph-lane-payload","ph-ymm-clear-statement"],
        meaning="The stated clear range overlaps the upper half of the declared eight-lane result; do not generate definite writes."),
    "ph-legacy-denormal-scope": dict(kind="source-conflict",rules=["ph-base-denormal-prose","ph-f16c-denormal-table"],
        meaning="A legacy no-denormal prose claim and a F16C-labelled denormal exception row require adjudication."),
    "psx-rounding-er-scope": dict(kind="unresolved-reference",rules=["psx-rounding-prose","psx-er-encoding-row"],
        meaning="Resolve embedded-rounding applicability before treating the always-MXCSR prose as universal."),
    "psx-feature-width-scope": dict(kind="unresolved-reference",rules=["psx-feature-table"],
        meaning="The aggregate feature row does not separately identify its width-dependent applicability."),
}
META_FIELDS = entry.migration.authority.CELL_FIELDS - {"text"}


class SourceUnknown(ValueError):
    """Source conflict or incomplete scope prevents a precise interpretation."""


def validate_structure(pack):
    entry.migration.corpus.fields(pack,{"schema","publisherSource","entryReviewInput","owners","clauses","sourceCells","boundaries"},"conversion constraint pack")
    require(pack["schema"] == "ariadne.amd64-conversion-source-constraints/v1", "conversion constraint schema")
    publisher=next(row for row in entry.read(entry.migration.authority.INPUT)["sources"] if row["id"]=="vol4-r3.27")
    require(pack["publisherSource"]==dict(id=publisher["id"],publication=publisher["publication"],pdfSha256=publisher["pdf"]["sha256"]),"conversion publisher pin differs")
    require(pack["entryReviewInput"]==dict(path=str(entry.INPUT.relative_to(ROOT)),sha256=entry.migration.sha(entry.INPUT)),"conversion entry-review pin differs")
    reviewed=entry.reviewed_input(entry.read(entry.INPUT))
    expected={"ph":next(link["new"] for link in reviewed["pairedFamilies"] if link["old"]["title"]=="VCVTPH2PS"),
              "ps":next(link["new"] for link in reviewed["pairedFamilies"] if link["old"]["title"]=="VCVTPS2PH")}
    require(pack["owners"]==expected,"conversion section owner/extent differs")
    require(pack["clauses"]==RULES and pack["boundaries"]==BOUNDARIES,"typed conversion rule or unresolved boundary changed")
    anchors={cell for row in RULES.values() for cell in row["sourceCells"]}
    require(set(pack["sourceCells"])==anchors,"conversion source cell omitted or duplicated")
    for identifier,metadata in pack["sourceCells"].items():
        require(set(metadata)==META_FIELDS and metadata["id"]==identifier,"conversion anchor fields/identity differ")
    return anchors


def validate_anchor(expected, actual):
    require({key:actual[key] for key in META_FIELDS}==expected,"actual conversion word geometry/hash differs")
    require(hashlib.sha256(actual["text"].encode()).hexdigest()==actual["unicodeSha256"],"actual conversion text hash differs")


def validate_cells(pack, pages):
    anchors=validate_structure(pack)
    actual={cell["id"]:cell for page in pages for cell in page["cells"] if cell["id"] in anchors}
    require(set(actual)==anchors,"actual conversion source cell omitted")
    for identifier,expected in pack["sourceCells"].items():
        validate_anchor(expected,actual[identifier])
    for name,row in RULES.items():
        owner=pack["owners"]["ph" if row["subjects"][0] in PH else "ps"]
        require(all(owner["pdfPage"]<=actual[i]["pdfPage"]<=owner["pdfEndPage"] for i in row["sourceCells"]),"conversion clause escapes its source owner")
        text=" ".join(actual[i]["text"] for i in row["sourceCells"])
        require(all(term in text for term in row["requiredTerms"]),"conversion clause lacks its actual source terms: "+name)
    claim=RULES["ph-ymm-clear-statement"]["parameters"]
    declared_result=RULES["ph-lane-payload"]["parameters"]
    result_bits=declared_result["lanes"]["256"]*declared_result["resultElementBits"]
    overlap=set(range(result_bits)) & set(range(claim["clearLowBit"],claim["clearHighBit"]+1))
    require(len(overlap)==128,"conversion clear/result overlap witness differs")
    return dict(schema=SCHEMA,typedSourceClauses=len(RULES),sourceCells=len(anchors),
        boundaries=copy.deepcopy(BOUNDARIES),overlappingResultBits=128,
        sourceAdoption=False,wholeSectionSemanticsReviewed=False,legalDomainComplete=False,
        productionAdmission=False,fullAmd64Coverage=False)


def payload_shape(mnemonic, vector_bits, memory_role="register", broadcast=False):
    require(mnemonic in PH+PS and type(vector_bits) is int and vector_bits in (128,256,512),"unreviewed conversion subject/width")
    require(memory_role in ("register","load","store") and type(broadcast) is bool,"unreviewed conversion operand role")
    ph=mnemonic in PH
    require(memory_role != ("store" if ph or mnemonic==PS[1] else "load"),"conversion source memory direction differs")
    is_x=mnemonic.endswith("X")
    require(not broadcast or is_x and memory_role=="load","unreviewed conversion broadcast")
    source_element,result_element=(16,32) if ph else (32,16)
    lanes=vector_bits//32
    residuals=[]
    if ph and vector_bits==256:residuals.append("ph-ymm-clear-overlap")
    if mnemonic==PH[0]:residuals.append("ph-legacy-denormal-scope")
    if mnemonic==PS[1]:residuals.extend(["psx-rounding-er-scope","psx-feature-width-scope"])
    return dict(lanes=lanes,sourcePayloadBits=source_element*lanes,resultPayloadBits=result_element*lanes,
                memoryBroadcastBits=source_element if broadcast else None,
                unresolved=residuals,productionAdmission=False,legalDomainComplete=False)


def rounding_selector(mnemonic, immediate, mxcsr_rc, *, embedded_rounding=False):
    require(mnemonic in PS and type(immediate) is int and 0<=immediate<=255
            and type(mxcsr_rc) is int and 0<=mxcsr_rc<=3 and type(embedded_rounding) is bool,
            "unreviewed rounding selector input")
    if embedded_rounding:
        raise SourceUnknown("embedded-rounding source/applicability remains unresolved")
    if mnemonic==PS[1]:return dict(source="MXCSR.RC",mode=mxcsr_rc,productionAdmission=False)
    return dict(source="MXCSR.RC" if immediate & 4 else "imm8",mode=mxcsr_rc if immediate & 4 else immediate & 3,productionAdmission=False)


def implementation_sources():
    result=entry.implementation_sources()
    result.update({name:entry.migration.sha(ROOT/name) for name in (
        "tools/amd64_conversion_constraints.py","tools/test_amd64_conversion_constraints.py",str(INPUT.relative_to(ROOT)))})
    return dict(sorted(result.items()))


def reconstruct(old_cache,publisher_cache,output):
    output=run_output(output);require(not output.exists(),"conversion review requires fresh output")
    before=implementation_sources();pack=entry.read(INPUT);validate_structure(pack)
    parent=output/"entry-review";original=entry.reconstruct(old_cache,publisher_cache,parent)
    actual=entry.migration.geometry.read_geometry(parent/"migration/replacement/26568/bbox.html")
    result=validate_cells(pack,actual)
    result.update(originalMigrationObligations=copy.deepcopy(original["originalObligations"]),
                  originalHistoricalGaps=original["historicalGapRecords"],implementation=before,
                  packSha256=entry.migration.sha(INPUT),entryReviewSha256=entry.migration.sha(parent/"entry-review.json"))
    require(before==implementation_sources(),"conversion review source/input drift")
    entry.migration._write(output,"conversion-constraints.json",result)
    return result


def check(old_cache,publisher_cache,output):
    output=run_output(output);require(output.is_dir(),"missing conversion review output")
    with tempfile.TemporaryDirectory(prefix="conversion-review-replay-",dir=output.parent) as temporary:
        fresh=Path(temporary)/"fresh";expected=reconstruct(old_cache,publisher_cache,fresh)
        actual={str(p.relative_to(output)):p for p in output.rglob("*") if p.is_file()}
        wanted={str(p.relative_to(fresh)):p for p in fresh.rglob("*") if p.is_file()}
        require(set(actual)==set(wanted),"conversion output omission/extra artifact")
        for name,path in actual.items():
            require(not path.is_symlink() and path.resolve().is_relative_to(output.resolve())
                    and entry.migration.sha(path)==entry.migration.sha(wanted[name]),"conversion output differs from fresh source: "+name)
    return expected


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("extract","check"))
    for key in ("old-cache","publisher-cache","output"):parser.add_argument("--"+key,type=Path,required=True)
    args=parser.parse_args();result=(reconstruct if args.action=="extract" else check)(args.old_cache,args.publisher_cache,args.output)
    print(json.dumps({key:result[key] for key in ("typedSourceClauses","sourceCells","overlappingResultBits","productionAdmission","fullAmd64Coverage")}))


if __name__=="__main__":main()
