#!/usr/bin/env python3
"""Project frozen independent JSON expectations into exact 64-bit TLA cases.

No oracle/SUT module is imported. --emit writes the model/configuration files
under Specs/ and model-cases.json under tests/input/fixtures/i5c/. --check verifies
those files without rewriting them. Both operations are source preparation,
not model qualification. The model checker runs the generated six configs.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests/input/fixtures/i5c"
SPEC_DIR = ROOT / "Specs"


def destination(name):
    return (SPEC_DIR if Path(name).suffix in (".tla", ".cfg") else FIXTURE_DIR) / name
SELECTED = [
    "mov32mi-upper", "mov32mi-upper-boundary", "mov32mi-negative-zero",
    "mov32mi-negative-nonzero", "mov32mi-underflow", "mov32mi-no-displacement",
    "span-end-h32", "span-end-h64", "span-cross-h32", "span-cross-h64",
    "span-wrap32", "span-wrap64", "reported-last32", "reported-last64",
    "reported-before", "reported-after32", "reported-after64", "rsp-sib-upper",
    "missing-integer", "missing-control", "wrong-operation", "indexed-zero",
    "missing-decoded-receipt", "decoder-bap-constant-disagreement",
    "mov32mi-disp8-min", "mov32mi-disp8-max", "mov32mi-disp32-min",
    "mov32mi-disp32-max", "lower-disp32-min",
    "budget-e0-c64", "budget-e32-c64", "budget-e33-c64", "budget-e64-c0",
    "budget-e64-c35", "budget-e64-c36", "budget-max-bundle-e45-c64",
    "budget-max-bundle-e46-c49", "budget-max-bundle-e64-c48",
    "mov64mi32-upper", "mov32rm-upper", "mov64rm-upper", "mov32mr-upper",
    "mov64mr-upper", "payload-immediate-zero", "binding-invalid-full",
    "binding-invalid-zero", "no-context", "no-exception", "vector",
    "multiple-access", "site-not-reached", "missing-decoder-identity",
]
GROUPS = {
    "AddressWrap": SELECTED,
    "AddressWrapArithmetic": SELECTED[:18] + SELECTED[24:29],
    "AddressWrapAdmission": SELECTED[18:24] + SELECTED[46:52],
    "AddressWrapBudgets": SELECTED[29:38] + SELECTED[44:46],
    "AddressWrapForms": [SELECTED[0]] + SELECTED[38:43],
    "AddressWrapPayload": [SELECTED[0], SELECTED[43]],
}
BOOL_FIELDS = {"windows", "exception", "context", "contextSupported", "ordinaryAV", "siteMatches",
               "captured", "reached", "semantics", "prefix", "oneAccess", "receipt", "receiptMatches",
               "baseOnly", "bindingValid", "expectedFacts", "expectedTruncated"}
SEQ_FIELDS = {"base", "displacement", "reported", "bapAddress", "expectedEffective", "payload"}
STR_FIELDS = {"form", "expectedConclusion"}


def limbs(value, count=4):
    return [(value >> (16*index)) & 65535 for index in range(count)]


def convert(value, index):
    name = value["name"]
    facts = value["expected"]["arithmetic"]
    base, disp = int(value["base_value"], 16), value["signed_displacement"]
    actual = value.get("actual_effective_address", f"0x{(base+disp) % (1<<64):016x}")
    actual = int(actual, 16) if isinstance(actual, str) else actual
    if name == "decoder-bap-constant-disagreement":
        actual = (base + disp + 1) % (1 << 64)
    record = dict(id=index, base=limbs(base), displacement=limbs(disp % (1<<32), 2),
                  accessBytes=value["access_size"], form=value["opcode"], operation=value["operation"],
                  baseGroup=1 if value["base_register"] == "rsp" else 2,
                  contextFlags=value["context_flags"], parameters=value["parameter_count"],
                  reported=limbs(int(value["reported"],16)), bapAddress=limbs(actual),
                  windows=value.get("platform", "windows-amd64") == "windows-amd64",
                  exception=value["exception_present"], context=value["context_present"],
                  contextSupported=value["context_supported"], ordinaryAV=True, siteMatches=True,
                  captured=value["captured"], reached=name != "site-not-reached", semantics=True,
                  prefix=True, oneAccess=name != "multiple-access", receipt=value["receipt"],
                  receiptMatches=name != "missing-decoder-identity", baseOnly=name != "indexed-zero",
                  evidenceLimit=value["max_evidence"], claimLimit=value["max_claims"],
                  # The model represents all payloads as64-bit limbs; absent load/vector payloads use the zero word.
                  # The physical fixture retains None; arithmetic never reads it.
                  payload=limbs(0 if value["payload"] is None else value["payload"]),
                  bindingValid=True, expectedConclusion=value["expected"]["conclusion"],
                  expectedFacts=facts is not None, expectedQuotient=facts["quotient"] if facts else 0,
                  expectedEffective=limbs(int(facts["effective_address"],16)) if facts else [0,0,0,0],
                  expectedTruncated=value["expected"]["truncated"],
                  expectedEvidence=value["expected"]["retained_evidence_count"],
                  expectedClaims=value["expected"]["retained_claims"])
    if name.startswith("binding-invalid-"):
        record.update(bindingValid=False, expectedConclusion="error", expectedFacts=False,
                      expectedQuotient=0, expectedEffective=[0,0,0,0], expectedTruncated=False,
                      expectedEvidence=0, expectedClaims=0)
        if name.endswith("zero"):
            record.update(evidenceLimit=0, claimLimit=0)
    return record


def render(value):
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "<<" + ",".join(map(render,value)) + ">>"
    return str(value)


def outputs():
    raw = (FIXTURE_DIR / "manifest.json").read_bytes()
    fixture = json.loads(raw)
    assert fixture["decision_case_count"] == 140
    rows = {row["name"]:row for row in fixture["cases"]}
    for name in ("binding-invalid-full", "binding-invalid-zero"):
        rows[name] = copy.deepcopy(rows["mov32mi-upper"])
        rows[name]["name"] = name
    assert len(SELECTED) == len(set(SELECTED)) == 52
    records = [convert(rows[name], index+1) for index,name in enumerate(SELECTED)]
    types = []
    for key in records[0]:
        type_ = "Bool" if key in BOOL_FIELDS else "Seq(Int)" if key in SEQ_FIELDS else "Str" if key in STR_FIELDS else "Int"
        types.append(f"{key}: {type_}")
    module = ["--------------------- MODULE AriadneAddressWrapCases ---------------------",
              "EXTENDS Integers, Sequences",
              "\\* Generated from the frozen independent fixture JSON. No SUT values are read.",
              "\\* @typeAlias: wrapCase = {" + ", ".join(types) + "};",
              "AddressWrap_typedefs == TRUE", "\\* @type: Seq($wrapCase);", "CaseTable == <<"]
    for index, record in enumerate(records):
        module.append("  \\* " + SELECTED[index])
        module.append("  [" + ", ".join(f"{key} |-> {render(value)}" for key,value in record.items())
                      + ("]" if index == len(records)-1 else "],"))
    module += [">>", "=============================================================================", ""]
    result = {"AriadneAddressWrapCases.tla":"\n".join(module).encode()}
    ids = {name:index+1 for index,name in enumerate(SELECTED)}
    for group, names in GROUPS.items():
        cfg = "SPECIFICATION Spec\nCONSTANT CaseIds = {" + ",".join(str(ids[name]) for name in names) + "}\n"
        cfg += "INVARIANT Safety\nPROPERTY Terminates\nCHECK_DEADLOCK FALSE\n"
        result[group+".cfg"] = cfg.encode()
    manifest = dict(schema="ariadne.i5c-w0-model-case-binding/v1", architectural_width=64,
                    limb_width=16, limb_count=4, independent_fixture_sha256=hashlib.sha256(raw).hexdigest(),
                    scenarios=52, configurations={key:len(value) for key,value in GROUPS.items()},
                    cases=[dict(name=name, **record) for name,record in zip(SELECTED,records)])
    result["model-cases.json"]=(json.dumps(manifest,indent=2,sort_keys=True)+"\n").encode()
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--emit",action="store_true")
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    assert args.emit != args.check, "select --emit or --check"
    result=outputs()
    for name,data in result.items():
        if args.emit:
            destination(name).write_bytes(data)
        else:
            assert destination(name).read_bytes()==data, name
    print(json.dumps({"generated" if args.emit else "checked":True,"scenarios":52,
                      "configurations":{key:len(value) for key,value in GROUPS.items()},
                      "model_executed":False},indent=2))


if __name__=="__main__":
    main()
