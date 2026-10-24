#!/usr/bin/env python3
"""P1 source selection with fresh structural and publisher proof replay.

P1 accepts identified source editions and accounts for their migration. Detailed
clause interpretation, legal domains and runtime coverage remain later stages.
Neither original migration objects nor publisher markings are rewritten.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

import amd64_corpus_entry_review as entry
import amd64_source_obligations as obligations
from amd64_inventory_xed import canonical, digest
from run_output import run_output

ROOT = entry.ROOT
INPUT = ROOT / "tests/bap/fixtures/source-migration/p1-source-policy-v1.json"
require = entry.require
SCHEMA = "ariadne.amd64-p1-source-adoption/v1"
POLICY = "select-exact-publisher-editions-preserve-history-and-markings"
VARIANT_RULE = "equal-page-word-box-multisets-with-exact-reviewed-variant-deltas/v1"
LAYOUT = ROOT/"tests/bap/fixtures/source-migration/volume5-layout-change-v1.json"


def selected_documents():
    lock = entry.read(entry.migration.corpus.LOCK)
    sources = {s["publication"]: s for s in entry.read(entry.migration.authority.INPUT)["sources"]}
    result = []
    for old in lock["documents"]:
        pub = old["publication"]
        if pub in ("26568", "26569"):
            source = sources[pub]
            result.append(dict(publication=pub, volume=old["volume"], revision=source["revision"],
                officialUrl=source["officialUrl"], filename=source["pdf"]["filename"],
                pdfSha256=source["pdf"]["sha256"], bytes=source["pdf"]["bytes"]))
        else:
            result.append(dict(publication=pub, volume=old["volume"], revision=old["revision"],
                officialUrl=old["officialIdentity"]["contentUrl"], filename=old["filename"],
                pdfSha256=old["pdfSha256"], bytes=old["bytes"]))
    return result


def migration_rule(kind, policy):
    require(kind in {"instruction-entry-migration-review", "new-and-removed-instruction-entry-review",
        "publisher-source-status-review", "changed-source-text-and-encoding-review",
        "expanded-extension-and-constraint-review"}, "unknown P1 migration kind")
    key=("entryRecords" if kind in ("instruction-entry-migration-review","new-and-removed-instruction-entry-review") else
         "publisherStatus" if kind=="publisher-source-status-review" else
         "additionalSections" if kind=="expanded-extension-and-constraint-review" else "documentRepresentations")
    return policy["migrationRules"][key]


def reviewed_policy(value):
    require(canonical(value) == canonical(entry.read(INPUT)), "unreviewed P1 source-selection policy")
    entry.migration.corpus.fields(value, {"schema", "decision", "corpusVersion", "inputs", "scopeSha256",
        "selectedDocuments", "volume5VariantRule", "markingWords", "layoutChanges", "migrationRules", "stageBoundary"}, "P1 policy")
    require(value["schema"] == "ariadne.amd64-p1-source-policy/v1" and value["decision"] == POLICY
            and type(value["corpusVersion"]) is int and value["corpusVersion"] == 3, "P1 selection schema/decision")
    expected_inputs = [entry.migration.corpus.LOCK, entry.INPUT, entry.migration.authority.INPUT, obligations.REVIEW,
                       ROOT/"tests/bap/fixtures/source-migration/source-status-pages.json", LAYOUT]
    require(value["inputs"] == {str(p.relative_to(ROOT)): entry.migration.sha(p) for p in expected_inputs}, "P1 predecessor input drift")
    require(value["scopeSha256"] == digest(entry.read(entry.migration.corpus.LOCK)["scope"])
            and value["selectedDocuments"] == selected_documents(), "P1 source scope or edition identity differs")
    require(value["volume5VariantRule"] == VARIANT_RULE, "unreviewed publisher-variant rule")
    marking_fixture = entry.read(ROOT/"tests/bap/fixtures/source-migration/source-status-pages.json")
    conflict = entry.read(entry.migration.INPUT)["sourceStatusConflict"]
    expected_words = {}
    for side, key in (("old", "oldCell"), ("new", "newCell")):
        cell = next(c for c in marking_fixture[side]["page"]["cells"] if c["id"] == conflict[key]["id"])
        require({k: cell[k] for k in entry.migration.authority.CELL_FIELDS} == conflict[key], "reviewed marking source differs")
        require(hashlib.sha256(canonical(cell["wordBoxes"])).hexdigest()==cell["wordBoxesSha256"], "reviewed marking word-box hash differs")
        expected_words[side] = cell["wordBoxes"]
    require(value["markingWords"] == expected_words, "P1 marking word identity differs")
    layout=entry.read(LAYOUT)
    require(value["layoutChanges"] == layout and layout["schema"]=="ariadne.amd64-reviewed-word-relocations/v1"
            and layout["publication"]=="26569" and layout["pdfPage"]==29
            and [m["old"]["text"] for m in layout["moves"]]==["Addison","Wesley,","NY,","1996."]
            and all(m["old"]["text"]==m["new"]["text"] for m in layout["moves"]), "unreviewed Volume5 layout movement")
    require(value["migrationRules"] == {
        "entryRecords": "preserve-all-110-original-identities-and-map-all-added-removed-sections",
        "documentRepresentations": "retain-all-eleven-comparison-dimensions-and-all-source-pages",
        "additionalSections": "retain-all-100-sections-for-required-P2-and-P3-work",
        "publisherStatus": "select-publisher-origin-retain-both-markings-and-check-every-other-word-box"},
        "P1 migration rule changed or scope narrowed")
    require(value["stageBoundary"] == {
        "P1": "source-edition-identity-structural-migration-and-bounded-original-adjudications",
        "P2": "required-clause-interpretation-source-conflicts-and-reference-completeness",
        "P3": "legal-domain-and-vendor-reconciliation",
        "runtime": "no-production-admission-or-full-coverage-claim"}, "P1/P2 stage boundary changed")
    return value


def compare_volume5(old_pages, new_pages, marking_words, layout_changes):
    """Remove only the exact reviewed words, never a footer rectangle or region.

    Every other word, position and multiplicity must agree, after replaying
    the four individually reviewed bibliography-word relocations on page 29.
Reading-order changes from PDF layout do not change physical source ownership.
"""
    require(len(old_pages) == len(new_pages) == 368, "Volume5 variant page omission")
    expected_pages = list(range(1, 369))
    require([p["pdfPage"] for p in old_pages] == [p["pdfPage"] for p in new_pages] == expected_pages,
            "Volume5 variant page identity/order differs")
    results = []
    for old, new in zip(old_pages, new_pages):
        require(old["size"] == new["size"], "Volume5 variant page dimensions differ")
        bodies = []
        for page, side in ((old, "old"), (new, "new")):
            words = [w for c in page["cells"] for w in c["wordBoxes"]]
            require(len(words) == page["wordCount"], "Volume5 word-box accounting differs")
            actual, excluded = Counter(map(canonical, words)), Counter(map(canonical, marking_words[side]))
            require(len(excluded) == (3 if side == "old" else 6)
                    and all(actual[key] == count == 1 for key, count in excluded.items()),
                    "Volume5 exact marking missing, duplicated or moved")
            actual.subtract(excluded)
            if side=="old" and page["pdfPage"]==layout_changes["pdfPage"]:
                for move in layout_changes["moves"]:
                    old_word,new_word=canonical(move["old"]),canonical(move["new"])
                    require(move["old"]["text"]==move["new"]["text"] and actual[old_word]==1,
                            "Volume5 reviewed bibliography position/text differs")
                    actual[old_word]-=1;actual[new_word]+=1
            bodies.append(+actual)
        require(bodies[0] == bodies[1], "Volume5 non-marking word/position/multiplicity differs on page " + str(old["pdfPage"]))
        results.append(dict(pdfPage=old["pdfPage"], nonMarkingWords=sum(bodies[0].values()),
                            wordBoxesSha256=digest([(key.decode("utf-8"),count) for key,count in sorted(bodies[0].items())])))
    return dict(rule=VARIANT_RULE, pages=results, reviewedLayoutChanges=copy.deepcopy(layout_changes),
        disposition="publisher-edition-selected-marking-variants-preserved",
        originalMarking="[AMD Public Use]", selectedMarking="[AMD Confidential - Distribution with NDA]",
        meaning="Exact publisher provenance selects the analysis source. Neither marking is corrected or erased; no claim about publisher intent follows.")


def structural_replay(source, old_cache, publisher_cache, baseline_root, output):
    geometry = entry.migration.geometry
    lock = entry.read(entry.migration.corpus.LOCK)
    historical = entry.read(geometry.LOCK)
    bundle = dict(corpusLock=lock, geometries={}, baselineEntries={},
        regions=geometry.audit_regions(source/"predecessor", entry.migration.corpus.LOCK),
        provenance=dict(corpusLockSha256=entry.migration.sha(entry.migration.corpus.LOCK),
                        historicalLockSha256=entry.migration.sha(geometry.LOCK)))
    for pub in obligations.PUBLICATIONS:
        folder = source/"predecessor"/pub
        baseline = Path(baseline_root)/("rep-coverage-manual-"+pub)
        original = entry.read(baseline/"inventory.json")
        pin = next(d for d in historical["documents"] if d["publication"] == pub)
        inputs = dict(baselineSha256=entry.migration.sha(baseline/"inventory.json"),
            baselineLayoutSha256=entry.migration.sha(baseline/"layout.txt"),
            geometrySha256=entry.migration.sha(folder/"bbox.html"), outlineSha256=entry.migration.sha(folder/"outline.json"))
        bundle["geometries"][pub] = geometry.derive(pub, pin, original, (baseline/"layout.txt").read_text(),
            entry.read(folder/"outline.json"), geometry.read_geometry(folder/"bbox.html"), inputs)
        bundle["baselineEntries"][pub] = original["content"]["entries"]
    # Rebuild the authority cache from this reconstruction, then run the owning
    # validator, which independently extracts the publisher PDFs again.
    cache = output/"authority"
    cache.mkdir(parents=True)
    authority = entry.read(entry.migration.authority.INPUT)
    for item in authority["sources"]:
        pub = item["publication"]
        folder = source/("predecessor" if pub == "24594" else "replacement")/pub
        pdf = (Path(old_cache)/next(d["filename"] for d in lock["documents"] if d["publication"] == pub)
               if pub == "24594" else Path(publisher_cache)/item["pdf"]["filename"])
        require(entry.migration.sha(pdf) == item["pdf"]["sha256"], "authority PDF identity differs")
        shutil.copyfile(pdf, cache/item["pdf"]["filename"])
        for kind, product in item["products"].items():
            path = folder/{"layout":"layout.txt", "geometry":"bbox.html", "outline":"outline.json"}[kind]
            require(entry.migration.sha(path) == product["sha256"], "authority source product differs")
            shutil.copyfile(path, cache/product["filename"])
    ledger = obligations.build_ledger(bundle, entry.read(obligations.REVIEW), dict(manifest=authority, root=cache))
    expected = ledger["acceptance"]
    require(expected["structuralRelationsAdjudicated"] is True and expected["sourceConflictsAdjudicated"] is True,
            "P1 original conflict/table adjudications incomplete")
    require(ledger["counts"]["historicalGapRecords"] == 2657
            and ledger["counts"]["sourceConflictsAdjudicated"] == 7
            and ledger["counts"]["tableCandidates"] == 33
            and ledger["counts"]["tableResolutions"] == {"continuation":26,"independent-table":7}, "P1 structural denominator differs")
    entry.migration._write(output, "structural-ledger.json", ledger)
    return ledger


def assess_reconstruction(original_review, source, old_cache, publisher_cache, baseline_root, output):
    """Internal boundary: caller has freshly reconstructed entry/source products."""
    policy = reviewed_policy(entry.read(INPUT))
    retained={str(p.relative_to(source)):entry.migration.sha(p) for p in source.rglob("*") if p.is_file()}
    comparison = entry.read(source/"migration.json")
    require(comparison["comparisonComplete"] is True and original_review["structuralEntryMappingComplete"] is True,
            "P1 source comparison or entry mapping incomplete")
    require(original_review["counts"] == dict(originalObligations=115,entryRecordsMapped=110,priorFamilies=5,
        additionalSections=100,broaderReviewItems=5,originalUnresolvedObligations=115), "P1 migration scope differs")
    for doc in comparison["documents"]:
        require(set(doc["dimensions"]) == set(entry.migration.DIMENSIONS), "P1 comparison dimension omitted")
        for dimension in doc["dimensions"].values():
            artifact=dimension["artifact"]
            path=source/artifact["path"]
            require(path.resolve().is_relative_to(source.resolve()) and not path.is_symlink()
                    and entry.migration.sha(path)==artifact["sha256"], "P1 comparison artifact omitted or changed")
    selected=[]
    for doc in policy["selectedDocuments"]:
        side="replacement" if doc["publication"] in ("26568","26569") else "predecessor"
        folder=source/side/doc["publication"]
        pdf=(Path(publisher_cache) if side=="replacement" else Path(old_cache))/doc["filename"]
        require(pdf.stat().st_size==doc["bytes"] and entry.migration.sha(pdf)==doc["pdfSha256"], "P1 selected PDF differs")
        outline=entry.read(folder/"outline.json")
        selected.append(dict(doc,pdfPages=outline["pages"],products={n:entry.migration.sha(folder/n)
            for n in ("layout.txt","bbox.html","outline.json")}))
    old=entry.migration.geometry.read_geometry(source/"predecessor/26569/bbox.html")
    new=entry.migration.geometry.read_geometry(source/"replacement/26569/bbox.html")
    variant=compare_volume5(old,new,policy["markingWords"],policy["layoutChanges"])
    structural=structural_replay(source,old_cache,publisher_cache,baseline_root,output)
    current=[]
    for original in original_review["originalObligations"]:
        kind=original["kind"]
        rule=migration_rule(kind,policy)
        current.append(dict(originalId=original["id"],originalSha256=digest(original),stage="P1",state="closed",
            rule=rule,followUpStages=[] if kind=="publisher-source-status-review" else ["P2","P3"],
            scope="Source selection and representation ownership only; no clause or legal-domain completion."))
    require(len(current)==115 and len({r["originalId"] for r in current})==115, "P1 original migration identity lost")
    require(retained=={str(p.relative_to(source)):entry.migration.sha(p) for p in source.rglob("*") if p.is_file()},
            "P1 reconstructed source products changed during adoption")
    for doc in policy["selectedDocuments"]:
        pdf=(Path(publisher_cache) if doc["publication"] in ("26568","26569") else Path(old_cache))/doc["filename"]
        require(entry.migration.sha(pdf)==doc["pdfSha256"], "P1 source PDF changed during adoption")
    return dict(schema=SCHEMA,p1Complete=True,sourceAuthorityEstablished=True,sourceAdoption=True,
        sourceSelection=dict(schema="ariadne.amd64-selected-source-corpus/v3",corpusVersion=3,
            policyInputSha256=entry.migration.sha(INPUT),documents=selected,scope=copy.deepcopy(entry.read(entry.migration.corpus.LOCK)["scope"])),
        originalObligations=copy.deepcopy(original_review["originalObligations"]),p1Dispositions=current,
        volume5Variant=variant,counts=dict(p1MigrationClosed=115,p1MigrationRemaining=0,
            originalConflictAdjudications=7,tableRelations=33,historicalGaps=2657,additionalSectionsRetained=100),
        sourceConflicts=copy.deepcopy([n for n in structural["content"]["nodes"] if n["kind"]=="source-conflict"]),
        constraintsParsed=False,legalDomainComplete=False,productionAdmission=False,fullAmd64Coverage=False)


def implementation_sources():
    result=entry.implementation_sources()
    result.update(obligations.source_closure())
    for name in ("tools/amd64_source_adoption.py","tools/test_amd64_source_adoption.py",str(INPUT.relative_to(ROOT))):
        result[name]=entry.migration.sha(ROOT/name)
    result["tests/bap/fixtures/source-migration/source-status-pages.json"]=entry.migration.sha(
        ROOT/"tests/bap/fixtures/source-migration/source-status-pages.json")
    result[str(LAYOUT.relative_to(ROOT))]=entry.migration.sha(LAYOUT)
    return dict(sorted(result.items()))


def reconstruct(old_cache,publisher_cache,output,baseline_root=ROOT/"target"):
    output=run_output(output);require(not output.exists(),"P1 adoption requires fresh output")
    before=implementation_sources();original=entry.reconstruct(old_cache,publisher_cache,output/"entry-review")
    result=assess_reconstruction(original,output/"entry-review/migration",old_cache,publisher_cache,baseline_root,output)
    require(before==implementation_sources(),"P1 adoption source/input drift")
    result["implementation"]=before
    entry.migration._write(output,"source-adoption.json",result)
    return result


def check(old_cache,publisher_cache,output,baseline_root=ROOT/"target"):
    output=run_output(output);require(output.is_dir(),"missing P1 adoption output")
    with tempfile.TemporaryDirectory(prefix="p1-adoption-replay-",dir=output.parent) as temporary:
        fresh=Path(temporary)/"fresh";expected=reconstruct(old_cache,publisher_cache,fresh,baseline_root)
        actual={str(p.relative_to(output)):p for p in output.rglob("*") if p.is_file()}
        wanted={str(p.relative_to(fresh)):p for p in fresh.rglob("*") if p.is_file()}
        require(set(actual)==set(wanted),"P1 adoption product omitted/extra")
        for name,path in actual.items():
            require(not path.is_symlink() and path.resolve().is_relative_to(output.resolve())
                    and entry.migration.sha(path)==entry.migration.sha(wanted[name]),"P1 adoption differs from fresh reconstruction: "+name)
    return expected


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("extract","check"))
    for name in ("old-cache","publisher-cache","output"):parser.add_argument("--"+name,type=Path,required=True)
    parser.add_argument("--baseline-root",type=Path,default=ROOT/"target")
    args=parser.parse_args();r=(reconstruct if args.action=="extract" else check)(args.old_cache,args.publisher_cache,args.output,args.baseline_root)
    print(json.dumps(dict(p1Complete=r["p1Complete"],counts=r["counts"],constraintsParsed=False,fullAmd64Coverage=False),sort_keys=True))


if __name__=="__main__":main()
