#!/usr/bin/env python3
"""Replay a narrow reviewed MOV8 source-constraint pack against pinned AMD cells.

This is a typed derivation for one finite register-only slice, not a general
manual parser. Unselected architectural clauses and global source completeness
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pack", type=Path)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--bbox", type=Path, required=True)
    args = parser.parse_args()
    print(canonical(validate_pack(read(args.pack), args.pdf, args.bbox)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
