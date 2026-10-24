#!/usr/bin/env python3
"""Source-faithful GF inverse-table replay and independent field checks.

The literal lookup is preserved even when it fails field identities. A numeric
counterexample is not authority to correct AMD's source or admit an instruction.
"""
from collections import Counter
import copy
from pathlib import Path
import re

import amd64_corpus_entry_review as entry
from amd64_inventory_xed import canonical, digest

ROOT = entry.ROOT
INPUT = ROOT/"tests/bap/fixtures/source-migration/p2-gf-table-v1.json"
require = entry.require


def multiply(a, b):
    require(all(type(n) is int and 0 <= n < 256 for n in (a,b)), "GF operands must be bytes")
    product = 0
    for bit in range(8):
        if b >> bit & 1:
            product ^= a << bit
    for bit in range(14,7,-1):
        if product >> bit & 1:
            product ^= 0x11b << (bit-8)
    return product


def inverse(value):
    require(type(value) is int and 0 <= value < 256, "GF inverse operand must be a byte")
    if value == 0:
        return 0
    candidates = [n for n in range(1,256) if multiply(value,n) == 1]
    require(len(candidates) == 1, "GF inverse is not unique")
    return candidates[0]


def center(word):
    rect = word["rect"]
    return (rect[0]+rect[2])/2, (rect[1]+rect[3])/2


def parse_table(page):
    """Use physical word rows/columns, never PDF reading order or cell stride."""
    words = [dict(w, sourceCell=c["id"], wordIndex=i) for c in page["cells"] for i,w in enumerate(c["wordBoxes"])]
    row_headers = [w for w in words if re.fullmatch(r"[0-9A-F]_",w["text"])]
    column_headers = [w for w in words if re.fullmatch(r"[_-][0-9A-F]",w["text"])]
    require(len(row_headers) == len(column_headers) == 16, "GF table omitted/duplicate nibble header")
    rows = {int(w["text"][0],16):w for w in row_headers}
    columns = {int(w["text"][1],16):w for w in column_headers}
    require(set(rows) == set(columns) == set(range(16)), "GF table nibble identity differs")
    require(all(center(rows[n])[1] < center(rows[n+1])[1] and center(columns[n])[0] < center(columns[n+1])[0]
                for n in range(15)), "GF source row/column orientation differs")
    # The selected source has a literal '-C' column label. Its identity is
    # retained; no value word is normalized, replaced or silently corrected.
    require(columns[12]["text"] == "-C" and all(columns[n]["text"] == "_"+format(n,"X") for n in range(16) if n != 12),
            "GF reviewed source column literal differs")
    entries = {}
    for word in words:
        x,y = center(word)
        if not (center(columns[0])[0]-8 < x < center(columns[15])[0]+8 and center(rows[0])[1]-4 < y < center(rows[15])[1]+4):
            continue
        require(re.fullmatch(r"[0-9A-F]{2}",word["text"]) is not None, "GF table unknown/merged value word")
        low = min(columns,key=lambda n:abs(x-center(columns[n])[0]))
        high = min(rows,key=lambda n:abs(y-center(rows[n])[1]))
        require(abs(x-center(columns[low])[0]) < 2 and abs(y-center(rows[high])[1]) < 2, "GF value moved outside its row/column")
        identifier = high*16+low
        require(identifier not in entries, "GF table duplicated value position")
        entries[identifier] = dict(inputByte=identifier, value=int(word["text"],16), sourceCell=word["sourceCell"],
                                   wordIndex=word["wordIndex"], word=dict(text=word["text"],rect=word["rect"]))
    require(set(entries) == set(range(256)), "GF table omitted source value")
    return [entries[n] for n in range(256)]


def literal_table(page, expected_digest, expected_values):
    require(digest(page["cells"]) == expected_digest, "GF actual table source population differs")
    table = parse_table(page)
    require([v["value"] for v in table] == expected_values, "GF source literal lookup differs")
    return table


def assess(pages):
    pack = entry.read(INPUT)
    entry.migration.corpus.fields(pack, {"schema", "entryReviewSha256", "tables", "fieldDefinition", "literalValues"}, "GF source review")
    require(pack["schema"] == "ariadne.amd64-gf-table-review/v1" and pack["entryReviewSha256"] == entry.migration.sha(entry.INPUT),
            "GF reviewed source input drift")
    reviewed = entry.reviewed_input(entry.read(entry.INPUT))
    pins = dict(predecessor=reviewed["oldPdfSha256"], replacement=reviewed["newPdfSha256"])
    require(type(pages) is dict and set(pages) == set(pins), "GF actual source sides omitted/extra")
    require(set(pack["tables"]) == set(pins) and type(pack["literalValues"]) is list and len(pack["literalValues"]) == 256
            and all(type(n) is int and 0 <= n < 256 for n in pack["literalValues"]), "GF source table denominator/scalar type differs")
    observations = {}
    for side,pin in pins.items():
        definition = pack["tables"][side]
        entry.migration.corpus.fields(definition, {"pdfSha256", "pdfPage", "sourceCellsSha256"}, "GF table source identity")
        require(definition["pdfSha256"] == pin and definition["pdfPage"] == (226 if side == "predecessor" else 228), "GF source edition/owner differs")
        actual = [p for p in pages[side] if p["pdfPage"] == definition["pdfPage"]]
        require(len(actual) == 1, "GF actual table source population differs")
        table = literal_table(actual[0],definition["sourceCellsSha256"],pack["literalValues"])
        observations[side] = table
    field = pack["fieldDefinition"]
    entry.migration.corpus.fields(field, {"pdfSha256", "pdfPage", "sourceCellsSha256", "polynomial"}, "GF field definition")
    require(field["pdfSha256"] == pins["replacement"] and type(field["polynomial"]) is int and field["polynomial"] == 0x11b
            and field["pdfPage"] == 233, "GF reviewed field source differs")
    actual = [p for p in pages["replacement"] if p["pdfPage"] == field["pdfPage"]]
    require(len(actual) == 1 and digest(actual[0]["cells"]) == field["sourceCellsSha256"], "GF actual field source differs")
    text = " ".join(c["text"] for c in actual[0]["cells"])
    require(all(t in text for t in ("poly11b_reduce", "0x011b", "14 to 8")), "GF field definition words missing")
    values = pack["literalValues"]
    mismatch = [dict(inputByte=n, sourceValue=value, multiplicativeInverse=inverse(n), product=multiply(n,value),
                     source={side:copy.deepcopy(observations[side][n]) for side in pins})
                for n,value in enumerate(values) if value != inverse(n)]
    duplicates = [dict(outputByte=v, inputs=[n for n in range(1,256) if values[n] == v])
                  for v,count in sorted(Counter(values[1:]).items()) if count > 1]
    return dict(schema="ariadne.amd64-gf-table-assessment/v1", entries=256, observations=observations,
        literalValuesSha256=digest(values), mathematicalPremise="Multiplicative inverse in the adjacent GF2P8MULB source's polynomial-0x11b field; zero maps to zero.",
        mismatches=mismatch, duplicateNonzeroOutputs=duplicates,
        state="source-conflict" if mismatch or duplicates else "checked-literal-and-field-agreement",
        interpretation="Literal values remain unchanged. Derived field inverses are comparison witnesses, not publisher corrections.",
        productionAdmission=False, fullAmd64Coverage=False)
