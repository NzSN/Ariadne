#!/usr/bin/env python3
"""Checked current-scope projection; historical source qualifications survive."""
import copy

import amd64_p2_native64 as native
from amd64_inventory_xed import canonical, digest

entry = native.entry
require = entry.require
INPUT = native.INPUT.parent / "p2-fixed64-scope-v1.json"
NEAR = ("CALL", "Jcc", "JrCXZ", "JMP", "LOOP", "LOOPcc", "RET")
DISPLACEMENTS = {"CALL": [32], "Jcc": [8, 32], "JrCXZ": [8],
                 "JMP": [8, 32], "LOOP": [8], "LOOPcc": [8], "RET": []}


def selected_contract(name):
    require(name in NEAR, "fixed64 projection has no near-branch owner")
    owner, extent, _ = native.qualification_contract(name)
    return dict(mnemonic=name, owner=owner, ownerPages=extent,
                selectedOperandBits=64, excludedOperandAlternatives=[16],
                operand32="unavailable;not-address32", addressBits=[64, 32],
                countBits=[64, 32] if name in ("JrCXZ", "LOOP", "LOOPcc") else [],
                countSelectedBy="address-size" if name in ("JrCXZ", "LOOP", "LOOPcc") else "no-implicit-loop-counter",
                relativeDisplacementBits=DISPLACEMENTS[name],
                indirectTargetBits=64 if name in ("CALL", "JMP", "RET") else None,
                returnAddressStackBits=64 if name in ("CALL", "RET") else None,
                prefix66="no-byte-removal-or-automatic-admission",
                basis="user-selected-fixed64-hypothesis;not-publisher-correction")


def assess(pack, pages, qualifications):
    require(set(pack) == {"schema", "sourcePolicySha256", "executionModes", "decision",
                          "contracts", "sourcePages", "sourceClauses"}, "fixed64 scope fields differ")
    require(pack["schema"] == "ariadne.amd64-fixed64-scope/v1" and
            pack["sourcePolicySha256"] == entry.migration.sha(native.adoption.INPUT) and
            pack["executionModes"] == ["long-64"] and
            pack["decision"] == "user-selected-fixed64-near-branches-2026-10-24" and
            canonical(pack["contracts"]) == canonical([selected_contract(n) for n in NEAR]),
            "fixed64 selected contract/mode/owner differs")
    selected = next(d for d in native.adoption.selected_documents() if d["publication"] == "24592")
    require(set(pack["sourcePages"]) == {"128", "129"}, "fixed64 source page population differs")
    by_number = {p["pdfPage"]: p for p in pages}
    require(len(by_number) == len(pages), "fixed64 duplicate actual page")
    for number, pin in pack["sourcePages"].items():
        require(int(number) in by_number and pin == dict(pdfSha256=selected["pdfSha256"],
                cellsSha256=digest(by_number[int(number)]["cells"])), "fixed64 actual source page differs")
        native.words(by_number[int(number)])
    wanted = [f"pdf:128:cell:{i}" for i in range(15, 57)] + [f"pdf:129:cell:{i}" for i in range(3, 19)]
    actual = {c["id"]: c for n in (128, 129) for c in by_number[n]["cells"]}
    require(set(pack["sourceClauses"]) == set(wanted) and all(pack["sourceClauses"][k] == actual[k]["text"] for k in wanted),
            "fixed64 conflicting source observation omitted/changed")
    require([q["mnemonic"] for q in qualifications] == [r[0] for r in native.B5],
            "fixed64 original qualification population differs")
    result = []
    for q in qualifications:
        name = q["mnemonic"]
        owner, extent, properties = native.qualification_contract(name)
        require(q["owner"] == owner and q["ownerPages"] == extent and
                canonical(q["properties"]) == canonical(properties), "fixed64 original qualification changed")
        # The original object and its digest are retained even for selected forms.
        record = dict(original=copy.deepcopy(q), originalSha256=digest(q),
                      disposition="unchanged-other-instruction")
        if name in NEAR:
            record.update(disposition="selected-fixed64-hypothesis", currentScope=selected_contract(name))
        result.append(record)
    return dict(schema="ariadne.amd64-fixed64-projection/v1", executionModes=["long-64"],
                decision=pack["decision"], qualifications=result, selectedGroups=len(NEAR),
                sourceDisagreementPreserved=True, prefixAdmission=False, productionAdmission=False)
