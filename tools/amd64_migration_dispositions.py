#!/usr/bin/env python3
"""Derive current migration work from immutable originals and fresh source checks.

Original records never change. P1 source selection and representation review
have executable exits. Detailed source clauses and legal domains retain their
P2/P3 follow-ups; they are not unfinished placeholders in P1 acceptance.
"""
import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import tempfile

import amd64_paired_constraints as paired
import amd64_source_adoption as adoption
from run_output import run_output

entry = paired.entry
ROOT = entry.ROOT
require = entry.require
SCHEMA = "ariadne.amd64-migration-dispositions/v2"
ENTRY_KIND = "instruction-entry-migration-review"
KINDS = {
    "new-and-removed-instruction-entry-review",
    "changed-source-text-and-encoding-review",
    "expanded-extension-and-constraint-review",
    "publisher-source-status-review", ENTRY_KIND,
}


def reduce_requirements(required, established, blockers):
    """A closed facet requires every named premise and no outstanding blocker."""
    require(isinstance(required, list) and required and len(required) == len(set(required))
            and all(isinstance(x, str) and x for x in required), "invalid required premises")
    require(isinstance(established, list) and len(established) == len(set(established))
            and set(established) <= set(required), "foreign/duplicate established premise")
    require(isinstance(blockers, list) and len(blockers) == len(set(blockers))
            and all(isinstance(x, str) and x for x in blockers), "invalid blockers")
    missing = sorted(set(required) - set(established))
    return dict(state="closed" if not missing and not blockers else "open",
                required=sorted(required), established=sorted(established),
                missing=missing, blockers=sorted(blockers))


def derive(original_review, source_assessment, p1_evidence=None):
    """Pure derivation; public CLI supplies freshly reconstructed source checks.

Selected-clause facts and P1 adoption evidence are produced by fresh validators.
The CLI has no saved-adoption input. Without the owning P1 replay this pure
layer reports the missing executable prerequisite, not an impossible review.
    """
    review = entry.reviewed_input(entry.read(entry.INPUT))
    original = original_review["originalObligations"]
    require(len(original) == 115 and len({r["id"] for r in original}) == 115,
            "original migration record omitted/duplicated")
    require(all(r["kind"] in KINDS and r["state"] == "unresolved" for r in original),
            "original migration kind/state changed")
    aggregates = {(publication, kind) for publication, kinds in (
        ("26568", ("new-and-removed-instruction-entry-review", "changed-source-text-and-encoding-review", "expanded-extension-and-constraint-review")),
        ("26569", ("publisher-source-status-review", "changed-source-text-and-encoding-review"))) for kind in kinds}
    require({r["id"] for r in original if r["kind"] != ENTRY_KIND}
            == {f"migration:{p}:{k}" for p, k in aggregates}, "document migration identity omitted/substituted")
    require(all(r["kind"] == r["id"].split(":", 2)[-1]
                for r in original if r["kind"] != ENTRY_KIND), "document migration kind differs from original ID")
    require(original_review["structuralEntryMappingComplete"] is True
            and all(original_review[k] is False for k in (
                "sourceAdoption", "semanticEquivalenceEstablished", "constraintsParsed",
                "legalDomainComplete", "fullAmd64Coverage")), "source entry scope promoted")
    require(entry.canonical(source_assessment["originalMigrationObligations"]) == entry.canonical(original)
            and source_assessment["originalHistoricalGaps"] == 2657,
            "paired assessment changed original migration/gap denominator")
    require(source_assessment["typedSourceClauses"] == len(paired.RULES)
            and entry.canonical(source_assessment["boundaries"]) == entry.canonical(paired.BOUNDARIES)
            and all(source_assessment[k] is False for k in (
                "sourceAdoption", "wholeSectionSemanticsReviewed", "legalDomainComplete",
                "productionAdmission", "fullAmd64Coverage")), "paired source scope promoted")
    by_id = {row["id"]: row for row in original}
    by_section = {}
    for row in original:
        if row["kind"] == ENTRY_KIND:
            require(row["direction"] in ("added", "removed"), "entry migration direction differs")
            require(row["id"] == "migration-entry:" + entry.digest(dict(
                publication="26568", direction=row["direction"], entry=row["entry"])), "entry migration stable identity differs")
            key = (row["direction"], entry.canonical(row["entry"]))
            require(key not in by_section, "duplicate original section occurrence")
            by_section[key] = row
    require(Counter(row["direction"] for row in original if row["kind"] == ENTRY_KIND)
            == {"added": 105, "removed": 5}, "entry migration direction denominator differs")
    family_records = {}
    selected_clauses = {}
    boundaries = {}
    for link in review["pairedFamilies"]:
        for side, direction in (("old", "removed"), ("new", "added")):
            key = (direction, entry.canonical(link[side]))
            require(key in by_section, "reviewed family source occurrence omitted")
            identifier = by_section[key]["id"]
            family_records[identifier] = link["old"]["title"]
            name = link["old"]["title"]
            if name in paired.FAMILIES.values():
                owner = next(k for k, v in paired.FAMILIES.items() if v == name)
                clauses = [k for k, v in paired.RULES.items() if v["owner"] == owner]
                blocked = ["paired:" + k for k, b in paired.BOUNDARIES.items()
                           if set(b["rules"]) & set(clauses)]
                selected_clauses[identifier] = ["paired:" + k for k in clauses]
            else:
                # The conversion source pack owns replacement facts only.
                prefix = "ph" if name == "VCVTPH2PS" else "ps"
                require(name in ("VCVTPH2PS", "VCVTPS2PH"), "unknown reviewed family")
                clauses = [k for k in paired.conversion.RULES if k.startswith(prefix)] if side == "new" else []
                blocked = ["conversion:" + k for k, b in paired.conversion.BOUNDARIES.items()
                           if set(b["rules"]) & set(clauses)]
                selected_clauses[identifier] = ["conversion:" + k for k in clauses]
            boundaries[identifier] = blocked
    additional = set()
    for section in review["additionalSections"]:
        key = ("added", entry.canonical(section))
        require(key in by_section, "additional source occurrence omitted")
        additional.add(by_section[key]["id"])
    require(len(family_records) == 10 and len(additional) == 100
            and not set(family_records) & additional
            and set(family_records) | additional == {r["id"] for r in by_section.values()},
            "family/additional migration partition differs")
    p1_ids=set()
    if p1_evidence is not None:
        policy=adoption.reviewed_policy(entry.read(adoption.INPUT))
        require(p1_evidence.get("schema")==adoption.SCHEMA
                and p1_evidence.get("p1Complete") is True and p1_evidence.get("sourceAdoption") is True
                and p1_evidence.get("sourceAuthorityEstablished") is True, "missing owning P1 adoption evidence")
        require(entry.canonical(p1_evidence["originalObligations"])==entry.canonical(original)
                and p1_evidence["sourceSelection"]["policyInputSha256"]==entry.migration.sha(adoption.INPUT),
                "P1 evidence is bound to different originals or policy")
        require(p1_evidence["counts"]==dict(p1MigrationClosed=115,p1MigrationRemaining=0,
            originalConflictAdjudications=7,tableRelations=33,historicalGaps=2657,additionalSectionsRetained=100),
            "P1 evidence omitted structural exits")
        selected=p1_evidence["sourceSelection"]["documents"]
        require(len(selected)==5 and [{k:d[k] for k in expected} for d,expected in zip(selected,policy["selectedDocuments"])]
                ==policy["selectedDocuments"],"P1 evidence selected a different source edition")
        require(p1_evidence["volume5Variant"]["rule"]==adoption.VARIANT_RULE
                and [p["pdfPage"] for p in p1_evidence["volume5Variant"]["pages"]]==list(range(1,369)),
                "P1 evidence omitted publisher variant comparison")
        require(all(p1_evidence[k] is False for k in ("constraintsParsed","legalDomainComplete","productionAdmission","fullAmd64Coverage")),
            "P1 evidence promoted later-stage claims")
        for row in p1_evidence["p1Dispositions"]:
            require(row["originalId"] in by_id and row["originalId"] not in p1_ids
                    and row["originalSha256"]==entry.digest(by_id[row["originalId"]]) and row["stage"]=="P1"
                    and row["state"]=="closed" and row["rule"]==adoption.migration_rule(by_id[row["originalId"]]["kind"],policy),
                    "P1 disposition identity/rule differs")
            p1_ids.add(row["originalId"])
        require(p1_ids==set(by_id),"P1 adoption omitted a migration record")
    rows = []
    for old in original:
        identifier, kind = old["id"], old["kind"]
        structural = kind == ENTRY_KIND or kind == "new-and-removed-instruction-entry-review"
        required = ["fresh-exact-source", "structural-scope", "p1-source-selection-replay"]
        established = ["fresh-exact-source"] + (["structural-scope"] if structural or identifier in p1_ids else [])
        if identifier in p1_ids:established.append("p1-source-selection-replay")
        blockers = []
        if kind == "publisher-source-status-review":
            required.append("publisher-variant-decision-reviewed")
            if identifier in p1_ids:established.append("publisher-variant-decision-reviewed")
            else:blockers.append("publisher:26569:variant-selection-replay-required")
        disposition = reduce_requirements(required, established, blockers)
        rows.append(dict(originalId=identifier, originalSha256=entry.digest(old), kind=kind,
            scope="paired-family" if identifier in family_records else
                  "additional-section" if identifier in additional else "document-review",
            sourceEntry=copy.deepcopy(old.get("entry")),
            selectedSourceClauses=sorted(selected_clauses.get(identifier, [])),
            followUpStages=[] if kind=="publisher-source-status-review" else ["P2","P3"],
            followUpBlockers=sorted(boundaries.get(identifier, [])),
            structural=reduce_requirements(["source-entry-accounted"],
                ["source-entry-accounted"] if structural else [], []),
            acceptance=disposition))
    require({r["originalId"] for r in rows} == set(by_id), "current disposition lost original ID")
    accepted = sum(r["acceptance"]["state"] == "closed" for r in rows)
    requirement_counts = Counter(k for r in rows for k in r["acceptance"]["missing"])
    return dict(schema=SCHEMA, originalObligations=copy.deepcopy(original), dispositions=rows,
        counts=dict(originalRecords=len(original), structurallyAccountedEntryRecords=110,
            structuralFacetsClosed=sum(r["structural"]["state"] == "closed" for r in rows),
            pairedEntryRecords=len(family_records), additionalSourceSections=len(additional),
            recordsWithSelectedClauses=sum(bool(r["selectedSourceClauses"]) for r in rows),
            acceptanceClosed=accepted, acceptanceRemaining=len(original)-accepted,
            missingPremises=dict(sorted(requirement_counts.items()))),
        acceptanceScope="P1-source-selection-and-representation-review",sourceAdoption=accepted == len(original),
        limits=["P1 adoption does not complete P2 clauses, P3 legality or runtime semantics.",
                "Original IDs and unresolved objects are immutable; current dispositions are derived separately.",
                "Downstream legal domains, runtime semantics and consumer qualification are separate gates."])


def implementation_sources():
    result = paired.implementation_sources()
    result.update(adoption.implementation_sources())
    for name in ("tools/amd64_migration_dispositions.py", "tools/test_amd64_migration_dispositions.py"):
        result[name] = entry.migration.sha(ROOT/name)
    return dict(sorted(result.items()))


def reconstruct(old_cache, publisher_cache, output):
    output = run_output(output)
    require(not output.exists(), "migration dispositions require fresh output")
    before = implementation_sources()
    parent = output/"paired-source"
    assessed = paired.reconstruct(old_cache, publisher_cache, parent)
    source = entry.read(parent/"conversion-review/entry-review/entry-review.json")
    p1=adoption.assess_reconstruction(source,parent/"conversion-review/entry-review/migration",
                                    old_cache,publisher_cache,ROOT/"target",output/"p1")
    result = derive(source, assessed, p1)
    entry.migration._write(output/"p1","source-adoption.json",p1)
    result.update(implementation=before, pairedSourceSha256=entry.migration.sha(parent/"paired-constraints.json"))
    require(before == implementation_sources(), "migration disposition source/input drift")
    entry.migration._write(output, "migration-dispositions.json", result)
    return result


def check(old_cache, publisher_cache, output):
    output = run_output(output)
    require(output.is_dir(), "missing migration disposition output")
    with tempfile.TemporaryDirectory(prefix="migration-disposition-replay-", dir=output.parent) as temporary:
        fresh = Path(temporary)/"fresh"
        expected = reconstruct(old_cache, publisher_cache, fresh)
        actual = {str(p.relative_to(output)): p for p in output.rglob("*") if p.is_file()}
        wanted = {str(p.relative_to(fresh)): p for p in fresh.rglob("*") if p.is_file()}
        require(set(actual) == set(wanted), "migration disposition product omitted/extra")
        for name, path in actual.items():
            require(not path.is_symlink() and path.resolve().is_relative_to(output.resolve())
                    and entry.migration.sha(path) == entry.migration.sha(wanted[name]),
                    "migration disposition differs from fresh source: " + name)
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("extract", "check"))
    for name in ("old-cache", "publisher-cache", "output"):
        parser.add_argument("--"+name, type=Path, required=True)
    parser.add_argument("--require-adoption", action="store_true")
    args = parser.parse_args()
    result = (reconstruct if args.action == "extract" else check)(args.old_cache, args.publisher_cache, args.output)
    print(json.dumps(dict(counts=result["counts"], sourceAdoption=result["sourceAdoption"]), sort_keys=True))
    return 2 if args.require_adoption and not result["sourceAdoption"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
