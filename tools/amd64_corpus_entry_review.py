#!/usr/bin/env python3
"""Fresh source-entry migration review, never semantic equivalence or adoption.

The comparison is reconstructed from pinned PDFs before its obligations can be
consumed. Reviewed family links preserve both source bodies and every original
obligation. Reports and complete source products stay in disposable run output.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import tempfile

import amd64_corpus_migration as migration
from amd64_inventory_xed import canonical, digest
from run_output import run_output

ROOT = migration.ROOT
INPUT = ROOT / "tests/bap/fixtures/source-migration/entry-review-v1.json"
SCHEMA = "ariadne.amd64-source-entry-review/v1"
REF_FIELDS = {"id", "chapter", "title", "pdfPage", "pdfEndPage"}
require = migration.require


def read(path):
    return migration.corpus.strict_json(Path(path).read_bytes())


def reviewed_input(value):
    require(canonical(value) == canonical(read(INPUT)), "unreviewed entry-migration decision")
    require(value["schema"] == "ariadne.amd64-entry-migration-review-input/v1"
            and value["decision"] == "map-source-entry-changes-without-semantic-adoption"
            and value["scopePolicy"] == "retain-every-original-obligation-and-every-added-source-section",
            "entry review cannot adopt or shrink source scope")
    pin = value["migrationInput"]
    require(pin == {"path": str(migration.INPUT.relative_to(ROOT)), "sha256": migration.sha(migration.INPUT)},
            "entry review predecessor/publisher migration input differs")
    for link in value["pairedFamilies"]:
        for side in ("old", "new"):
            migration.corpus.fields(link[side], REF_FIELDS, "entry source reference")
        require(link["reason"] and link["requiredOldText"] and link["requiredNewText"],
                "source-family link lacks reviewed reasons or source terms")
    return value


def classify_changes(comparison, review, section):
    """Map every original obligation. `section` reads actual verified products.

    Unit tests can supply small sections; only reconstruct() establishes the
    pinned source boundary required by the public CLI.
    """
    require(comparison["sourceAdoption"] is False and comparison["constraintsParsed"] is False
            and comparison["legalDomainComplete"] is False, "comparison cannot grant semantic adoption")
    docs = comparison["documents"]
    require(len(docs) == 2 and {d["publication"] for d in docs} == {"26568", "26569"},
            "entry review omitted a publisher document")
    original = [row for doc in docs for row in doc["obligations"]]
    require(len(original) == len({row["id"] for row in original}), "duplicate original obligation")
    require(all(row["state"] == "unresolved" for row in original), "original obligation status was rewritten")
    vol4 = next(doc for doc in docs if doc["publication"] == review["publication"])
    require(vol4["oldSource"]["pdfSha256"] == review["oldPdfSha256"]
            and vol4["newSource"]["pdfSha256"] == review["newPdfSha256"], "reviewed PDF identity differs")
    entries = [row for row in original if row["kind"] == "instruction-entry-migration-review"]
    added = {canonical(row["entry"]): row for row in entries if row["direction"] == "added"}
    removed = {canonical(row["entry"]): row for row in entries if row["direction"] == "removed"}
    require(len(added)+len(removed) == len(entries), "invalid/duplicate entry source identity")
    counts = review["expectedCounts"]
    require((len(added), len(removed), len(entries), len(original), comparison["historicalGapRecords"])
            == (counts["added"], counts["removed"], counts["entryObligations"],
                counts["originalObligations"], counts["historicalGaps"]), "entry-review denominator changed")
    paired, seen_old, seen_new = [], set(), set()
    for link in review["pairedFamilies"]:
        old, new = canonical(link["old"]), canonical(link["new"])
        require(old in removed and new in added and old not in seen_old and new not in seen_new,
                "missing, duplicated or wrong-owner prior-family link")
        seen_old.add(old); seen_new.add(new)
        paired.append(dict(oldObligation=copy.deepcopy(removed[old]), newObligation=copy.deepcopy(added[new]),
            reason=link["reason"], oldSection=section("predecessor", link["old"], link["requiredOldText"]),
            newSection=section("replacement", link["new"], link["requiredNewText"]),
            semanticEquivalenceEstablished=False, legalDomainComplete=False))
    require(seen_old == set(removed) and len(paired) == counts["priorFamilies"],
            "unmapped removed source entry")
    additional, observed = [], set()
    for reference in review["additionalSections"]:
        key = canonical(reference)
        require(key in added and key not in seen_new and key not in observed,
                "additional section omitted, duplicated or overlaps prior family")
        observed.add(key)
        additional.append(dict(originalObligation=copy.deepcopy(added[key]),
            section=section("replacement", reference, reference["title"].split()),
            disposition="additional-source-section-retained-for-constraint-and-implementation-review"))
    require(observed == set(added)-seen_new and len(additional) == counts["additionalSections"],
            "additional publisher source scope lost")
    vol5 = next(doc for doc in docs if doc["publication"] == "26569")
    require(vol5["sourceStatusConflict"] is not None and vol5["sourceStatusConflict"]["status"] == "unresolved",
            "publisher source-status conflict omitted or treated as resolved")
    return dict(schema=SCHEMA, structuralEntryMappingComplete=True, originalObligations=copy.deepcopy(original),
        counts=dict(originalObligations=len(original), entryRecordsMapped=len(entries), priorFamilies=len(paired),
                    additionalSections=len(additional), broaderReviewItems=len(original)-len(entries),
                    originalUnresolvedObligations=len(original)),
        priorFamilyLinks=paired, additionalSections=additional,
        sourceStatusConflict=copy.deepcopy(vol5["sourceStatusConflict"]),
        sourceAdoption=False, semanticEquivalenceEstablished=False, constraintsParsed=False,
        legalDomainComplete=False, fullAmd64Coverage=False,
        limits=["Source-entry continuity is not whole-section semantic equivalence.",
                "Normalized rows are incomplete observations, not a legal-domain proof.",
                "Every original adoption/semantic obligation remains unresolved.",
                "Additional source sections remain inside the selected scope."])


def sections(directory, comparison):
    """Read every raw page/cell in each selected section, including footers.

    No revision/header stripping can conceal a changed source word. Whole PDF
    and extraction identity is established by the preceding source replay.
    """
    data = {}
    doc = next(doc for doc in comparison["documents"] if doc["publication"] == "26568")
    for side in ("predecessor", "replacement"):
        folder = directory / side / "26568"
        normalized = read(folder / "normalized.json")
        layout = (folder / "layout.txt").read_bytes().decode("utf-8")
        pages = layout.split("\f")
        geometry = migration.geometry.read_geometry(folder / "bbox.html")
        by_page = {page["pdfPage"]: page for page in geometry}
        entries = {row["id"]: row for row in normalized["entries"]}
        require(len(entries) == len(normalized["entries"]), "duplicate actual section identity")
        data[side] = (normalized, pages, by_page, entries)

    def get(side, reference, required):
        normalized, pages, by_page, entries = data[side]
        entry = entries.get(reference["id"])
        require(entry is not None and {k: entry[k] for k in REF_FIELDS} == reference,
                "actual source entry title/extent/owner differs")
        first, last = entry["pdfPage"], entry["pdfEndPage"]
        require(1 <= first <= last <= len(by_page) and all(i in by_page for i in range(first,last+1)),
                "source section escapes actual publisher extent")
        raw = "\f".join(pages[first-1:last])
        text = " ".join(raw.split())
        require(all(" ".join(term.split()) in text for term in required), "reviewed family term missing from actual section")
        rows = [row for row in normalized["rows"] if entry["id"] in row["entryIds"]]
        constraints = [row for row in normalized["constraintReferences"] if entry["id"] in row["entryIds"]]
        return dict(sourceEntry=copy.deepcopy(reference),
            pdfSha256=doc["oldSource" if side == "predecessor" else "newSource"]["pdfSha256"],
            rawSectionSha256=hashlib.sha256(raw.encode()).hexdigest(),
            rawWordGeometrySha256=digest([by_page[i] for i in range(first,last+1)]),
            normalizedRowsSha256=digest(rows), normalizedRows=len(rows),
            constraintObservationsSha256=digest(constraints), constraintObservations=len(constraints),
            fullSemanticReviewEstablished=False)
    return get


def implementation_sources():
    result = migration.implementation_sources()
    result.update({name: migration.sha(ROOT / name) for name in (
        "tools/amd64_corpus_entry_review.py", "tools/test_amd64_corpus_entry_review.py", str(INPUT.relative_to(ROOT)))})
    return dict(sorted(result.items()))


def reconstruct(old_cache, publisher_cache, output):
    output = run_output(output)
    require(not output.exists(), "entry review requires fresh disposable output")
    before = implementation_sources()
    review = reviewed_input(read(INPUT))
    source = output / "migration"
    comparison = migration.reconstruct(old_cache, publisher_cache, source)
    result = classify_changes(comparison, review, sections(source, comparison))
    result.update(reviewInputSha256=migration.sha(INPUT), implementation=before,
                  historicalGapArtifact=copy.deepcopy(comparison["historicalGapArtifact"]),
                  historicalGapRecords=comparison["historicalGapRecords"],
                  migrationSha256=migration.sha(source / "migration.json"))
    require(before == implementation_sources(), "source-entry review implementation/input drift")
    migration._write(output, "entry-review.json", result)
    return result


def check(old_cache, publisher_cache, output):
    output = run_output(output)
    require(output.is_dir(), "missing source-entry review output")
    with tempfile.TemporaryDirectory(prefix="entry-review-replay-", dir=output.parent) as temporary:
        fresh = Path(temporary) / "fresh"
        expected = reconstruct(old_cache, publisher_cache, fresh)
        actual = {str(p.relative_to(output)): p for p in output.rglob("*") if p.is_file()}
        wanted = {str(p.relative_to(fresh)): p for p in fresh.rglob("*") if p.is_file()}
        require(set(actual) == set(wanted), "entry-review output omission or extra artifact")
        for name, path in actual.items():
            require(not path.is_symlink() and path.resolve().is_relative_to(output.resolve())
                    and migration.sha(path) == migration.sha(wanted[name]), "source-entry review differs from fresh replay: " + name)
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("extract", "check"))
    parser.add_argument("--old-cache", type=Path, required=True)
    parser.add_argument("--publisher-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = (reconstruct if args.action == "extract" else check)(args.old_cache,args.publisher_cache,args.output)
    print(json.dumps(dict(structuralEntryMappingComplete=result["structuralEntryMappingComplete"],
                         counts=result["counts"], sourceAdoption=False, fullAmd64Coverage=False),sort_keys=True))


if __name__ == "__main__":
    main()
