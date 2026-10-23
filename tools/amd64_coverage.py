#!/usr/bin/env python3
"""Account for pinned AMD64 inventory obligations without inventing legal forms.

Use --xed INVENTORY and repeated --manual INVENTORY for the existing extractor
products. An optional --survey is rebound to the exact catalogue, native tool
identities and current source, and its summaries are recomputed. --associations
accepts candidate-only exact-byte associations, never authoritative legality:
{schema: ariadne.amd64-form-case-associations/v1, xedRecordsSha256: ...,
 catalogueSha256: ..., associations: [{formId: ..., caseId: ..., bytes: ...}]}.
Even an associated supported byte sample cannot discharge a symbolic template's
concrete domain. Current inputs contain no complete vendor legality model or
authoritative form-to-byte binding, so --require-full returns nonzero. Generated
report/worklists belong under ignored target/ or an external temporary directory.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sys

import amd64_inventory as inventory
import amd64_manual_inventory as manual
from amd64_inventory_xed import digest
import probe_amd64_semantics as probe
from run_output import run_output

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "ariadne.amd64-coverage-accounting/v1"
ASSOCIATIONS = "ariadne.amd64-form-case-associations/v1"
MAX_INPUT_BYTES = 64 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_INPUT_BYTES + 1)
    require(len(data) <= MAX_INPUT_BYTES, "coverage input byte budget")
    value = inventory.strict_json(data)
    require(isinstance(value, dict), "coverage input must be an object")
    return value


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unique_rows(rows, field, description):
    require(isinstance(rows, list), description + " must be a list")
    result = {}
    for row in rows:
        require(isinstance(row, dict) and isinstance(row.get(field), str)
                and row[field] and row[field] not in result,
                "invalid or duplicate " + description)
        result[row[field]] = row
    return result


def validate_catalogue(catalogue):
    require(set(catalogue) == {"schema", "profile", "scope", "exhaustiveEncodingCoverage", "sourcePolicy",
                               "encodingSource", "references", "architecturalSubsets", "families", "cases"},
            "catalogue fields or unsupported completion claim")
    cases = probe.validate_catalogue(catalogue)
    unique_rows(catalogue["references"], "id", "catalogue reference")
    require(len(catalogue["architecturalSubsets"]) == len(probe.SUBSETS),
            "duplicate catalogue subset")
    require(bool(cases), "empty catalogue")
    return cases


def validate_manual(result, pin, xed):
    manual.validate_output(result, pin)
    content = result["content"]
    require(set(content) == {"entries", "tables", "rows", "constraintReferences", "gaps"},
            "manual content fields")
    entries = unique_rows(content["entries"], "id", "manual entry")
    tables = unique_rows(content["tables"], "id", "manual table")
    rows = unique_rows(content["rows"], "id", "manual row")
    for table in tables.values():
        owners = table["entryIds"]
        require(bool(owners) and len(owners) == len(set(owners)) and set(owners) <= set(entries),
                "manual table has invalid entry ownership")
    for row in rows.values():
        require(row["table"] in tables
                and row["entryIds"] == tables[row["table"]]["entryIds"],
                "manual row has invalid table ownership")
    for gap in content["gaps"]:
        require(isinstance(gap, dict) and isinstance(gap.get("kind"), str), "manual gap schema")
        for key, owners in (("entry", entries), ("table", tables), ("row", rows)):
            require(key not in gap or gap[key] in owners, "manual gap has unknown owner")
    require(len({digest(gap) for gap in content["gaps"]}) == len(content["gaps"]),
            "duplicate manual gap")
    comparison = result["xedComparison"]
    if comparison is not None:
        require(comparison == dict(xedRecordsSha256=xed["recordsSha256"],
                                   rows=manual.reconcile(content["rows"], xed)),
                "manual/XED candidates differ from exact source rows")


def validate_survey(catalogue, catalogue_sha, survey, current_sources):
    base_fields = set(probe.summarize(catalogue))
    extra_fields = {"catalogueSha256", "sourceSha256", "sourceStable", "nativeRequested",
                    "operationalFailure", "nativeTools"}
    require(set(survey) == base_fields | extra_fields, "survey fields")
    require(survey["catalogueSha256"] == catalogue_sha, "survey catalogue identity differs")
    require(isinstance(current_sources, dict) and bool(current_sources)
            and all(isinstance(path, str) and isinstance(value, str)
                    and re.fullmatch("[0-9a-f]{64}", value) for path, value in current_sources.items()),
            "current source identity is missing or malformed")
    require(survey["sourceSha256"] == current_sources and survey["sourceStable"] is True,
            "survey source is stale or changed")
    require(survey["operationalFailure"] is None, "survey has an operational failure")
    require(type(survey["nativeRequested"]) is bool, "survey native request flag")
    rows = unique_rows(survey["rows"], "id", "survey case")
    cases = validate_catalogue(catalogue)
    require(set(rows) == set(cases), "survey must contain the exact catalogue cases")
    native_rows = None
    if survey["nativeRequested"]:
        tools = survey["nativeTools"]
        require(isinstance(tools, dict) and set(tools) == {"decoderSha256", "helperSha256"},
                "survey native tool identity fields")
        # The existing binder checks bytes, addresses, order, effect sets, BAP
        # identity and the absence of an LLVM semantic fallback for every row.
        native = dict(schema="ariadne.amd64-semantics-native-probe/v1",
                      catalogueSha256=catalogue_sha, target="windows-amd64", **tools,
                      rows=[row["observation"] for row in survey["rows"]])
        require(all(isinstance(row, dict) for row in native["rows"]),
                "native survey has a missing observation")
        native_rows = probe.bind_native(catalogue, catalogue_sha, native)
    else:
        require(survey["nativeTools"] is None
                and all(row.get("observation") is None for row in rows.values()),
                "unexercised survey carries native observations")
    expected = probe.summarize(catalogue, native_rows)
    require(all(survey[key] == value for key, value in expected.items()),
            "survey rows, classification or completion claims differ from observations")
    return expected


def associate(associations, xed, catalogue_sha, cases):
    if associations is None:
        return {}
    require(set(associations) == {"schema", "xedRecordsSha256", "catalogueSha256", "associations"}
            and associations["schema"] == ASSOCIATIONS,
            "candidate association schema; authoritative claims are unsupported")
    require(associations["xedRecordsSha256"] == xed["recordsSha256"]
            and associations["catalogueSha256"] == catalogue_sha,
            "association inventory/catalogue identity differs")
    forms = {row["id"]: row for row in xed["records"]}
    seen, result = set(), defaultdict(list)
    require(isinstance(associations["associations"], list), "association rows must be a list")
    for row in associations["associations"]:
        require(set(row) == {"formId", "caseId", "bytes"}, "association row fields")
        form, case = row["formId"], row["caseId"]
        require(form in forms and 64 in forms[form]["modeDomain"] and case in cases,
                "unknown or non-long-mode association")
        require(row["bytes"] == cases[case]["bytes"], "association exact bytes differ")
        require((form, case) not in seen, "duplicate form/case association")
        seen.add((form, case))
        result[form].append(case)
    return {form: sorted(names) for form, names in result.items()}


def case_status(status):
    if status == "supported-projection":
        return "supported"
    if status == "conservative-unknown":
        return "opaque"
    if status == "unexercised":
        return "unexercised"
    return "missing"


def report(xed, xed_lock, manuals, manual_lock, catalogue, catalogue_sha,
           survey=None, current_sources=None, associations=None):
    require(isinstance(catalogue_sha, str) and re.fullmatch("[0-9a-f]{64}", catalogue_sha),
            "catalogue SHA256 is missing or malformed")
    inventory.validate_inventory(xed, xed_lock)
    require(manual_lock["schema"] == "ariadne.amd-manual-inventory-lock/v1", "manual lock schema")
    pins = unique_rows(manual_lock["documents"], "publication", "manual publication pin")
    require(bool(pins), "empty manual publication denominator")
    supplied = unique_rows(manuals, "publication", "manual publication")
    for publication, result in supplied.items():
        require(publication in pins, "manual publication is outside pinned denominator")
        validate_manual(result, pins[publication], xed)
    cases = validate_catalogue(catalogue)
    measured = (probe.summarize(catalogue) if survey is None else
                validate_survey(catalogue, catalogue_sha, survey, current_sources))
    links = associate(associations, xed, catalogue_sha, cases)
    exact_cases = []
    for row in measured["rows"]:
        exact_cases.append(dict(id=row["id"], bytes=row["bytes"], family=row["family"],
                                status=case_status(row["status"]), detail=row["status"],
                                independentEffectExpectation=row["independentEffectExpectation"],
                                expectedEffectsMatch=row["expectedEffectsMatch"]))
    by_case = {row["id"]: row for row in exact_cases}
    candidates = defaultdict(list)
    manual_rows, gaps, manual_documents = [], [], []
    for publication, result in sorted(supplied.items()):
        comparison = result["xedComparison"]
        for row in [] if comparison is None else comparison["rows"]:
            for form in row["exactNameCandidates"]:
                candidates[form].append(publication + ":" + row["row"])
        for row in result["content"]["rows"]:
            manual_rows.append(dict(id=publication + ":" + row["id"], mnemonic=row["mnemonic"],
                                    source=row["source"], status="legality-unresolved"))
        for index, gap in enumerate(result["content"]["gaps"]):
            gaps.append(dict(id=f"{publication}:gap:{index:05}", publication=publication, **gap))
        manual_documents.append(dict(publication=publication, revision=result["revision"],
                                     contentSha256=result["contentSha256"],
                                     officialByteIdentity=result["sourceProvenance"]["officialByteIdentity"],
                                     rows=len(result["content"]["rows"]),
                                     transcriptionGaps=len(result["content"]["gaps"])))
    forms = []
    for row in xed["records"]:
        if 64 not in row["modeDomain"]:
            continue
        names = links.get(row["id"], [])
        forms.append(dict(id=row["id"], mnemonic=row["mnemonic"], iform=row["iform"],
                          encodingSpace=row["encodingSpace"], isaSet=row["isaSet"],
                          associationStatus="candidate-only" if names else "absent",
                          authoritativeByteBinding=False,
                          associatedCases=[by_case[name] for name in names],
                          nameOnlyManualCandidates=sorted(candidates[row["id"]]),
                          remainingObligations=["establish-vendor-legality", "verify-form-to-byte-binding",
                                                "expand-and-exercise-concrete-domain"] +
                          ([] if names else ["associate-exact-byte-case"])))
    missing_manuals = sorted(set(pins) - set(supplied))
    gates = [
        dict(id="pinned-symbolic-template-denominator", satisfied=True),
        dict(id="all-pinned-manual-documents-present", satisfied=not missing_manuals),
        dict(id="official-manual-byte-identities", satisfied=not missing_manuals and all(
            row["officialByteIdentity"] == "matches-repository-official-source-pin" for row in manual_documents)),
        dict(id="manual-transcription-gap-free", satisfied=not missing_manuals and not gaps),
        dict(id="complete-vendor-encoding-legality", satisfied=False),
        dict(id="authoritative-form-to-byte-bindings", satisfied=False),
        dict(id="exhaustive-concrete-encoding-domains", satisfied=False),
        dict(id="current-native-byte-observations", satisfied=survey is not None and measured["probeComplete"]),
        dict(id="all-catalogue-bytes-supported", satisfied=all(row["status"] == "supported" for row in exact_cases)),
        dict(id="independent-catalogue-effect-expectations", satisfied=all(
            row["independentEffectExpectation"] and row["expectedEffectsMatch"] is True for row in exact_cases)),
    ]
    return dict(schema=SCHEMA, fullAmd64Support=all(gate["satisfied"] for gate in gates),
                scope="Symbolic XED long-mode candidates, unresolved AMD source rows and exact catalogue byte observations are separate domains.",
                associationMeaning="Candidate-only exact case association; neither vendor legality nor coverage of the symbolic template's concrete domain is verified.",
                inputs=dict(xedRecordsSha256=xed["recordsSha256"], catalogueSha256=catalogue_sha,
                            manualDocuments=manual_documents,
                            surveySourceSha256=None if survey is None else survey["sourceSha256"],
                            associationsSha256=None if associations is None else digest(associations)),
                counts=dict(symbolicTemplates=len(xed["records"]), longModeCandidates=len(forms),
                            longModeExcluded=len(xed["records"]) - len(forms),
                            unboundLongModeCandidates=sum(not links.get(row["id"]) for row in forms),
                            authoritativeBoundForms=0, manualRows=len(manual_rows), manualGaps=len(gaps),
                            pinnedManualRows=sum(pin["counts"]["rows"] for pin in pins.values()),
                            pinnedManualGaps=sum(sum(pin["counts"]["gaps"].values()) for pin in pins.values()),
                            exactByteCases=len(exact_cases),
                            exactByteStatus=dict(sorted(Counter(row["status"] for row in exact_cases).items()))),
                gates=gates, missingManualPublications=missing_manuals,
                formWorklist=forms, manualRowWorklist=manual_rows, manualGapWorklist=gaps,
                exactByteCases=exact_cases)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xed", type=Path, required=True)
    parser.add_argument("--manual", type=Path, action="append", default=[])
    parser.add_argument("--catalogue", type=Path, default=probe.CATALOGUE)
    parser.add_argument("--survey", type=Path)
    parser.add_argument("--associations", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="fresh ignored report directory")
    parser.add_argument("--require-full", action="store_true", help="exit 2 while any full-coverage gate is unmet")
    args = parser.parse_args(argv)
    try:
        result = report(read_json(args.xed), inventory.load_lock(),
                        [read_json(path) for path in args.manual], read_json(manual.LOCK),
                        read_json(args.catalogue), sha(args.catalogue),
                        None if args.survey is None else read_json(args.survey),
                        None if args.survey is None else probe.source_identity(),
                        None if args.associations is None else read_json(args.associations))
        result["checkerSha256"] = sha(Path(__file__))
        output = run_output(args.output)
        output.mkdir(parents=True, exist_ok=False)
        (output / "report.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(json.dumps(dict(counts=result["counts"], fullAmd64Support=result["fullAmd64Support"],
                              unmetGates=[gate["id"] for gate in result["gates"] if not gate["satisfied"]],
                              report=str(output / "report.json")), sort_keys=True))
        return 2 if args.require_full and not result["fullAmd64Support"] else 0
    except (ValueError, OSError, KeyError, TypeError, IndexError, AttributeError) as error:
        print("invalid coverage input: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
