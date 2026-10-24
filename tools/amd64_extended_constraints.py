#!/usr/bin/env python3
"""Replay bounded cross-volume EVEX and immediate source rules.

The displacement kernels require a supplied memory-access size. They do not
infer instruction legality, tuple types, CPUID admission or production effects.
The frozen architectural pack and its original references stay unchanged.
"""
import argparse
import copy
import json
from pathlib import Path
import tempfile

import amd64_migration_dispositions as migration
import amd64_source_constraints as architecture
from run_output import run_output

entry = migration.entry
ROOT = entry.ROOT
INPUT = ROOT/"tests/bap/fixtures/source-migration/extended-constraints-v1.json"
require = entry.require
FACTORS = (1, 2, 4, 8, 16, 32, 64)


def refs(publication, page, first, last):
    return [f"{publication}/pdf:{page}:cell:{i}" for i in range(first,last+1)]


RULES = {
    "disp8-source-reference": dict(sourceCells=refs("24594",66,18,19),
        parameters=dict(reference="Volume1:4.13.8",encoding="EVEX",widthBytes=1),
        requiredTerms=["one-byte displacements", "scaled by a factor 'N'", "4.13.8"]),
    "disp8-access-size-factor": dict(sourceCells=refs("24592",275,20,26),
        parameters=dict(factor="memory-access-size-in-bytes",signedDisplacementBits=8,
                        operation="signed-disp8-times-N",applicability="AVX512-EVEX-memory"),
        requiredTerms=["memory access in bytes", "multiplied", "every AVX512 EVEX-encoded"]),
    "disp8-wide-fallback": dict(sourceCells=refs("24592",275,37,38),
        parameters=dict(nonMultipleDisplacementBytes=4), requiredTerms=["not a multiple", "4-byte displacement"]),
    "disp8-positive-example": dict(sourceCells=refs("24592",275,27,30),
        parameters=dict(encodedByte=6,factor=64,result=384), requiredTerms=["06h", "6 * 64 = 384"]),
    "disp8-broadcast-example": dict(sourceCells=refs("24592",275,31,36),
        parameters=dict(encodedByte=208,factor=4,result=-192), requiredTerms=["broadcast", "D0h(-48 * 4 = -192)"]),
    "embedded-rounding-scope": dict(sourceCells=refs("24592",275,3,11),
        parameters=dict(memoryAllowed=False,modrmMod=3,evexB=1,roundingField="EVEX.L'L",
            suppressFloatingExceptions=True,vectorBits=512,scalarBits=128),
        requiredTerms=["ModR/M.mod == 11b", "{er}", "EVEX.b", "512 bits", "128 bits"]),
    "sae-scope": dict(sourceCells=refs("24592",275,12,19),
        parameters=dict(memoryAllowed=False,evexB=1,lengthFieldIgnored=True,vectorBits=512,scalarBits=128),
        requiredTerms=["{sae}", "non-memory", "EVEX.L'L field is ignored"]),
    "mov-immediate-64": dict(sourceCells=refs("24592",80,70,77)+refs("24592",81,3,4),
        parameters=dict(ordinaryMaximumImmediateBits=32,exception="MOV-GPR64-imm64",
                        opcodeRange=[184,191],requiresRex=True),
        requiredTerms=["64-bit immediates", "B8h through BFh", "requires a REX"]),
    "mov-displacement-unresolved-reference": dict(sourceCells=refs("24594",66,13,17),
        parameters=dict(displacementClaim=True,referencedSection="Immediate Operand Size",adjudicated=False),
        requiredTerms=["64-bit displacement", "Immediate Operand Size"]),
}
BOUNDARIES = {
    "memory-shape-admission": dict(kind="unresolved-applicability",rules=["disp8-access-size-factor"],
        meaning="The caller must establish the actual instruction/operand memory-access size and EVEX applicability; this kernel supplies neither tuple decoding nor legality."),
    "mov-displacement-reference-mismatch": dict(kind="unresolved-source-scope",rules=["mov-immediate-64","mov-displacement-unresolved-reference"],
        meaning="The cited immediate section establishes GPR immediates but does not specify every 64-bit memory displacement/address encoding; no moffs or displacement rule is inferred."),
    "specific-er-prose-conflict": dict(kind="unresolved-source-scope",rules=["embedded-rounding-scope"],
        meaning="The generic embedded-rounding rule locates the mechanism; conflicting instruction-specific always-MXCSR prose still needs a reviewed scope/adjudication."),
}


def validate_structure(pack):
    entry.migration.corpus.fields(pack,{"schema","corpusLockSha256","architecturePackSha256","sources","clauses","sourceCells","boundaries"},"extended source pack")
    require(pack["schema"] == "ariadne.amd64-extended-source-constraints/v1", "extended source schema")
    require(pack["corpusLockSha256"] == entry.migration.sha(entry.migration.corpus.LOCK)
            and pack["architecturePackSha256"] == entry.migration.sha(architecture.ARCHITECTURE_PACK), "extended predecessor source pin differs")
    lock = entry.read(entry.migration.corpus.LOCK)
    expected = {r["publication"]:r["pdfSha256"] for r in lock["documents"] if r["publication"] in {"24592","24594"}}
    require(pack["sources"] == expected, "extended source PDF identity differs")
    require(entry.canonical(pack["clauses"]) == entry.canonical(RULES)
            and entry.canonical(pack["boundaries"]) == entry.canonical(BOUNDARIES), "extended source rule/boundary differs")
    anchors = {i for rule in RULES.values() for i in rule["sourceCells"]}
    require(set(pack["sourceCells"]) == anchors, "extended source anchor omitted/extra")
    for identifier,cell in pack["sourceCells"].items():
        publication,identifier_cell = identifier.split("/",1)
        require(set(cell) == migration.paired.META_FIELDS and cell["id"] == identifier_cell
                and publication in expected, "extended source anchor identity/fields differ")
    return anchors


def validate_cells(pack,pages):
    anchors = validate_structure(pack)
    actual = {}
    require(set(pages) == set(pack["sources"]), "extended source publication omitted")
    for publication,content in pages.items():
        for page in content:
            for cell in page["cells"]:
                identifier = publication+"/"+cell["id"]
                if identifier not in anchors:continue
                require(identifier not in actual and cell["pdfPage"] == page["pdfPage"], "extended actual source duplicate/wrong page")
                migration.paired.conversion.validate_anchor(pack["sourceCells"][identifier],cell)
                actual[identifier] = cell
    require(set(actual) == anchors, "extended actual source anchor omitted")
    for name,rule in RULES.items():
        text=" ".join(" ".join(actual[i]["text"] for i in rule["sourceCells"]).split())
        require(all(t in text for t in rule["requiredTerms"]), "extended source terms missing: "+name)
    for name in ("disp8-positive-example","disp8-broadcast-example"):
        example=RULES[name]["parameters"]
        require(scaled_disp8(example["encodedByte"],example["factor"]) == example["result"], "source displacement witness differs")
    original=entry.read(architecture.ARCHITECTURE_PACK)
    unresolved=[r["id"] for r in original["references"] if r["status"] != "resolved-location"]
    require(len(unresolved)==10 and "evex-disp8-scaling" in unresolved,"architectural reference denominator differs")
    return dict(schema="ariadne.amd64-extended-source-assessment/v1",typedSourceClauses=len(RULES),sourceCells=len(anchors),
        referenceDispositions=[dict(originalId="evex-disp8-scaling",originalState="unresolved-architectural-rule",
            currentState="resolved-source-rule",rule="disp8-access-size-factor",scope="Signed scaling equation given the actual admitted memory-access size; no instruction tuple/legality claim.")],
        remainingArchitecturalReferences=[r for r in unresolved if r!="evex-disp8-scaling"],
        boundaries=copy.deepcopy(BOUNDARIES),sourceAdoption=False,legalDomainComplete=False,
        productionAdmission=False,fullAmd64Coverage=False)


def scaled_disp8(encoded_byte,access_bytes):
    require(type(encoded_byte) is int and 0<=encoded_byte<256,"invalid encoded displacement byte")
    require(type(access_bytes) is int and access_bytes in FACTORS,"unreviewed memory-access byte size")
    return (encoded_byte if encoded_byte<128 else encoded_byte-256)*access_bytes


def select_displacement(displacement,access_bytes):
    """Describe the scalar encoding choice after instruction applicability is known."""
    require(type(displacement) is int and -(1<<31)<=displacement<(1<<31),"displacement outside selected signed-32 domain")
    require(type(access_bytes) is int and access_bytes in FACTORS,"unreviewed memory-access byte size")
    quotient,remainder=divmod(displacement,access_bytes)
    compressed=remainder==0 and -128<=quotient<128
    return dict(bytes=1 if compressed else 4,encoded=quotient%256 if compressed else displacement%(1<<32),
                productionAdmission=False,legalDomainComplete=False)


def implementation_sources():
    result=migration.implementation_sources()
    for name in ("tools/amd64_extended_constraints.py","tools/test_amd64_extended_constraints.py",str(INPUT.relative_to(ROOT)),
                 "tools/amd64_source_constraints.py",str(architecture.ARCHITECTURE_PACK.relative_to(ROOT))):
        result[name]=entry.migration.sha(ROOT/name)
    return dict(sorted(result.items()))


def reconstruct(old_cache,publisher_cache,output):
    output=run_output(output)
    require(not output.exists(),"extended constraints require fresh output")
    before=implementation_sources();pack=entry.read(INPUT);validate_structure(pack)
    parent=output/"migration-dispositions"
    previous=migration.reconstruct(old_cache,publisher_cache,parent)
    base=parent/"paired-source/conversion-review/entry-review/migration/predecessor"
    pages={p:entry.migration.geometry.read_geometry(base/p/"bbox.html") for p in pack["sources"]}
    result=validate_cells(pack,pages)
    old=architecture.validate_architecture_pack_cells(entry.read(architecture.ARCHITECTURE_PACK),pages)
    result.update(originalArchitecturalReferences=copy.deepcopy(old["unresolvedReferences"]),
        originalUnparsedSourceCells=copy.deepcopy(old["unparsedSourceCells"]),
        originalMigrationObligations=copy.deepcopy(previous["originalObligations"]),implementation=before,
        migrationDispositionsSha256=entry.migration.sha(parent/"migration-dispositions.json"),packSha256=entry.migration.sha(INPUT))
    require(before==implementation_sources(),"extended constraint source/input drift")
    entry.migration._write(output,"extended-constraints.json",result)
    return result


def check(old_cache,publisher_cache,output):
    output=run_output(output);require(output.is_dir(),"missing extended constraint output")
    with tempfile.TemporaryDirectory(prefix="extended-constraints-replay-",dir=output.parent) as temporary:
        fresh=Path(temporary)/"fresh";expected=reconstruct(old_cache,publisher_cache,fresh)
        actual={str(p.relative_to(output)):p for p in output.rglob("*") if p.is_file()}
        wanted={str(p.relative_to(fresh)):p for p in fresh.rglob("*") if p.is_file()}
        require(set(actual)==set(wanted),"extended output omitted/extra artifact")
        for name,path in actual.items():
            require(not path.is_symlink() and path.resolve().is_relative_to(output.resolve())
                    and entry.migration.sha(path)==entry.migration.sha(wanted[name]),"extended output differs from fresh source: "+name)
    return expected


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("extract","check"))
    for name in ("old-cache","publisher-cache","output"):parser.add_argument("--"+name,type=Path,required=True)
    args=parser.parse_args();result=(reconstruct if args.action=="extract" else check)(args.old_cache,args.publisher_cache,args.output)
    print(json.dumps(dict(typedSourceClauses=result["typedSourceClauses"],sourceCells=result["sourceCells"],
        remainingArchitecturalReferences=len(result["remainingArchitecturalReferences"]),
        originalUnparsedSourceCells=len(result["originalUnparsedSourceCells"]),productionAdmission=False),sort_keys=True))


if __name__=="__main__":main()
