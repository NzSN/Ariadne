#!/usr/bin/env python3
"""Reproduce and compare publisher replacements without adopting their scope.

Every page and every occurrence is retained. Exact representation deltas are
separate from instruction legality, constraint parsing and source adoption.
The immutable predecessor and its historical gap identifiers remain intact.
"""
import argparse
from collections import defaultdict, deque
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import amd64_manual_geometry as geometry
import amd64_manual_inventory as manual
import amd64_source_authority as authority
import amd64_source_corpus as corpus
from amd64_inventory_xed import canonical, digest
from run_output import run_output

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "tests/bap/fixtures/source-migration/publisher-replacements-v1.json"
SCHEMA = "ariadne.amd64-corpus-migration/v1"
DIMENSIONS = ("full-text", "geometry", "outline", "source-regions", "instruction-entries",
              "normalized-rows", "constraint-references", "extraction-gaps",
              "whole-document-rule-references", "pdf-identity", "extensions-and-scope")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return corpus.sha_file(path)


def implementation_sources():
    paths = set(authority.authority_sources()) | {
        "tools/amd64_corpus_migration.py", str(INPUT.relative_to(ROOT))}
    return {path: sha(ROOT / path) for path in sorted(paths)}


def reviewed_inputs(value):
    corpus.fields(value, {"schema", "predecessor", "publisherInputs", "extentPolicy", "decision",
                          "replacements", "sourceStatusConflict"}, "migration input")
    require(canonical(value) == canonical(corpus.strict_json(INPUT.read_bytes())), "unreviewed migration input")
    require(value["schema"] == "ariadne.amd64-corpus-migration-review-input/v1"
            and value["decision"] == "compare-and-retain-unresolved-candidate"
            and value["extentPolicy"] == "retain-every-publisher-page-and-outline-entry",
            "migration cannot self-assert adoption or shrink publisher extent")
    for key, expected in (("predecessor", corpus.LOCK), ("publisherInputs", authority.INPUT)):
        pin = value[key]
        corpus.fields(pin, {"path", "sha256"}, key)
        require(pin["path"] == str(expected.relative_to(ROOT)) and sha(expected) == pin["sha256"],
                "migration predecessor or publisher input drift")
    require([row["publication"] for row in value["replacements"]] == ["26568", "26569"],
            "replacement denominator changed")
    for row in value["replacements"]:
        corpus.fields(row, {"publication", "publisherSource", "reviewObligations"}, "replacement")
        require(row["reviewObligations"] and len(set(row["reviewObligations"])) == len(row["reviewObligations"]),
                "missing or duplicate review obligations")
    conflict = value["sourceStatusConflict"]
    corpus.fields(conflict, {"publication", "kind", "oldCell", "newCell"}, "source status conflict")
    require(conflict["publication"] == "26569"
            and conflict["kind"] == "public-use-versus-confidential-nda-marking", "source status conflict changed")
    for side, literal in (("oldCell", "[AMD Public Use]"),
                          ("newCell", "[AMD Confidential - Distribution with NDA]")):
        corpus.fields(conflict[side], authority.CELL_FIELDS, "status source cell")
        require(conflict[side]["pdfPage"] == 1 and conflict[side]["text"] == literal,
                "source status literal or page changed")
    return value


def representation_delta(old, new):
    """Match equal values occurrence by occurrence, retaining both locations.

    Content equality never erases movement, ordering or duplicate occurrences.
    Full values live in the referenced, freshly reproduced source products.
    """
    for rows in (old, new):
        require(len(rows) == len({canonical(row["reference"]) for row in rows}), "duplicate source address")
    available = defaultdict(deque)
    for index, row in enumerate(old):
        available[digest(row["value"])].append(index)
    matched, added, used = [], [], set()
    for index, row in enumerate(new):
        key = digest(row["value"])
        if available[key]:
            previous = available[key].popleft()
            require(old[previous]["value"] == row["value"], "representation digest collision")
            used.add(previous)
            matched.append(dict(valueSha256=key, old=old[previous]["reference"], new=row["reference"],
                                oldOrdinal=previous, newOrdinal=index))
        else:
            added.append(dict(valueSha256=key, reference=row["reference"], ordinal=index))
    removed = [dict(valueSha256=digest(row["value"]), reference=row["reference"], ordinal=index)
               for index, row in enumerate(old) if index not in used]
    require(len(matched) + len(removed) == len(old) and len(matched) + len(added) == len(new),
            "representation comparison lost an occurrence")
    return dict(oldCount=len(old), newCount=len(new), matched=matched, removed=removed, added=added,
                orderedValuesEqual=[row["value"] for row in old] == [row["value"] for row in new])


def summary(delta):
    return {key: delta[key] for key in ("oldCount", "newCount", "orderedValuesEqual")} | {
        key: len(delta[key]) for key in ("matched", "removed", "added")}


def page_text(layout, page_count):
    pages = layout.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    require(len(pages) == page_count, "layout page count differs")
    # Include blank lines and empty pages: layout is an exact representation.
    return [dict(reference=dict(pdfPage=page, line=line), value=text)
            for page, content in enumerate(pages, 1)
            for line, text in enumerate(content.splitlines(keepends=True) or [""], 1)]


def whole_document_rules(value):
    result = []
    for row in page_text(value["layout"], value["outline"]["pages"]):
        categories = [name for name, pattern in manual.CONSTRAINTS.items() if pattern.search(row["value"])]
        if categories:
            result.append(dict(reference=row["reference"],
                               value=dict(categories=categories, text=" ".join(row["value"].split()))))
    return result


def outline_rows(outline):
    result = []
    def visit(rows, parent):
        for index, row in enumerate(rows):
            address = [*parent, index]
            require(1 <= row["pdfPage"] <= outline["pages"], "outline page escapes PDF")
            result.append(dict(reference=dict(path=address, pdfPage=row["pdfPage"]),
                               value={key: value for key, value in row.items() if key not in {"children", "pdfPage"}}))
            visit(row.get("children", []), address)
    visit(outline["outline"], [])
    return result


def regions(outline):
    """Partition the whole document, including unoutlined front matter."""
    starts = sorted({1, outline["pages"] + 1, *(row["pdfPage"] for row in outline["outline"])})
    require(starts[0] == 1 and starts[-1] == outline["pages"] + 1, "invalid source region boundary")
    result = []
    for first, following in zip(starts, starts[1:]):
        titles = [row["title"] for row in outline["outline"] if row["pdfPage"] == first]
        result.append(dict(reference=dict(firstPdfPage=first, lastPdfPage=following - 1),
                           value=dict(titles=titles, kind="outlined-region" if titles else "unoutlined-frontmatter")))
    require(sum(row["reference"]["lastPdfPage"] - row["reference"]["firstPdfPage"] + 1 for row in result)
            == outline["pages"], "source region coverage is incomplete")
    return result


def normalized_rows(content, kind):
    entries = {entry["id"]: (entry["chapter"], entry["title"]) for entry in content["entries"]}
    require(len(entries) == len(content["entries"]), "duplicate instruction entry identity")
    rows = []
    for index, row in enumerate(content[kind]):
        if kind == "entries":
            value = dict(chapter=row["chapter"], title=row["title"])
            reference = dict(id=row["id"], pdfPage=row["pdfPage"], pdfEndPage=row["pdfEndPage"], **value)
        elif kind == "rows":
            value = dict(owners=[entries[key] for key in row["entryIds"]], mnemonic=row["mnemonic"],
                         encodingCells=row["encodingCells"])
            reference = dict(id=row["id"], source=row["source"])
        elif kind == "constraintReferences":
            value = dict(owners=[entries[key] for key in row["entryIds"]], categories=row["categories"],
                         sourceText=" ".join(row["sourceText"].split()))
            reference = dict(ordinal=index, pdfPage=row["pdfPage"], line=row["line"], textSha256=row["textSha256"])
        else:
            require(kind == "gaps", "unknown normalized comparison kind")
            value = row
            reference = dict(ordinal=index, originalGap=row)
        rows.append(dict(reference=reference, value=value))
    return rows


def source_status(conflict, old_geometry, new_geometry):
    result = dict(publication=conflict["publication"], kind=conflict["kind"], status="unresolved",
                  oldCell=conflict["oldCell"], newCell=conflict["newCell"])
    for side, pages in (("oldCell", old_geometry), ("newCell", new_geometry)):
        expected = conflict[side]
        actual = [cell for page in pages if page["pdfPage"] == expected["pdfPage"]
                  for cell in page["cells"] if cell["id"] == expected["id"]]
        require(len(actual) == 1 and {key: actual[0][key] for key in authority.CELL_FIELDS} == expected,
                "publisher source-status anchor differs")
    require(result["oldCell"]["text"] == "[AMD Public Use]"
            and result["newCell"]["text"] == "[AMD Confidential - Distribution with NDA]",
            "source-status text cannot be inferred from PDF revision")
    return result


def _write(root, relative, value):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value) + b"\n")
    return dict(path=relative, sha256=sha(path))


def _read_document(directory, chapters):
    outline = corpus.strict_json((directory / "outline.json").read_bytes())
    layout = (directory / "layout.txt").read_bytes().decode("utf-8")
    normalized = manual.extract(layout, outline, chapters)
    return dict(outline=outline, layout=layout, normalized=normalized)


def _replacement_products(source, cache, output, lock, tools, env):
    pdf = authority._local(cache, source["pdf"]["filename"])
    corpus.verify_pdf(pdf, dict(publication=source["publication"], pdfSha256=source["pdf"]["sha256"],
                                bytes=source["pdf"]["bytes"]))
    output.mkdir(parents=True)
    for kind, filename in (("layout", "layout.txt"), ("geometry", "bbox.html")):
        command = lock["extractor"]["commands"][kind]
        args = [str(tools[command[0]]), *[str(pdf.resolve()) if part == "{pdf}" else
                str(output / filename) if part == "{output}" else part for part in command[1:]]]
        subprocess.run(args, env=env, check=True, capture_output=True, timeout=180)
        require(sha(output / filename) == source["products"][kind]["sha256"], "publisher extraction product drift")
    with (output / "outline.json").open("wb") as stream:
        subprocess.run([str(tools["mutool"]), "run", str(ROOT / "tools/amd64_manual_outline.js"), str(pdf.resolve())],
                       env=env, check=True, stdout=stream, stderr=subprocess.PIPE, timeout=180)
    require(sha(output / "outline.json") == source["products"]["outline"]["sha256"], "publisher outline drift")


def _compare_document(review, predecessor, source, old_dir, new_dir, output, conflict):
    publication = predecessor["publication"]
    chapters = [row["selector"] for row in predecessor["requiredRegions"] if row["kind"] == "instruction-reference"]
    old, new = (_read_document(directory, chapters) for directory in (old_dir, new_dir))
    _write(output, f"replacement/{publication}/normalized.json", new["normalized"])
    dimensions = {}
    changes = {}
    simple = {"full-text": lambda value: page_text(value["layout"], value["outline"]["pages"]),
              "outline": lambda value: outline_rows(value["outline"]),
              "source-regions": lambda value: regions(value["outline"]),
              "instruction-entries": lambda value: normalized_rows(value["normalized"], "entries"),
              "normalized-rows": lambda value: normalized_rows(value["normalized"], "rows"),
              "constraint-references": lambda value: normalized_rows(value["normalized"], "constraintReferences"),
              "extraction-gaps": lambda value: normalized_rows(value["normalized"], "gaps"),
              "whole-document-rule-references": whole_document_rules}
    for kind, compare in simple.items():
        delta = representation_delta(compare(old), compare(new))
        dimensions[kind] = dict(summary=summary(delta), artifact=_write(output, f"deltas/{publication}/{kind}.json", delta))
        if kind == "instruction-entries":
            changes = {key: [row["reference"] for row in delta[key]] for key in ("removed", "added")}
    old_geometry, new_geometry = (geometry.read_geometry(directory / "bbox.html") for directory in (old_dir, new_dir))
    def cell_rows(pages):
        return [dict(reference=dict(id=cell["id"], pdfPage=cell["pdfPage"]),
                     value={key: value for key, value in cell.items() if key not in {"id", "pdfPage"}})
                for page in pages for cell in page["cells"]]
    delta = representation_delta(cell_rows(old_geometry), cell_rows(new_geometry))
    def page_rows(pages):
        return [dict(reference=dict(pdfPage=page["pdfPage"]),
                     value=dict(size=page["size"], wordCount=page["wordCount"], cells=len(page["cells"]))) for page in pages]
    delta["pageDescriptors"] = representation_delta(page_rows(old_geometry), page_rows(new_geometry))
    dimensions["geometry"] = dict(summary=summary(delta), artifact=_write(output, f"deltas/{publication}/geometry.json", delta))
    identity = dict(old=predecessor, new=source)
    dimensions["pdf-identity"] = dict(summary=dict(exactOldIdentity=True, exactPublisherIdentity=True,
        pdfBytesEqual=predecessor["pdfSha256"] == source["pdf"]["sha256"]),
        artifact=_write(output, f"deltas/{publication}/pdf-identity.json", identity))
    scope = dict(requiredRegions=predecessor["requiredRegions"], selectedChapters=chapters,
                 oldWholeDocumentPages=old["outline"]["pages"], newWholeDocumentPages=new["outline"]["pages"],
                 instructionEntryChanges=changes, extensionSemanticsReviewed=False,
                 policy="All publisher pages and instruction entries remain included; no new entry is silently excluded.")
    dimensions["extensions-and-scope"] = dict(summary=dict(addedInstructionEntries=len(changes["added"]),
        removedInstructionEntries=len(changes["removed"]), sourceRegionSelectorsPreserved=True, extensionSemanticsReviewed=False),
        artifact=_write(output, f"deltas/{publication}/extensions-and-scope.json", scope))
    require(set(dimensions) == set(DIMENSIONS), "migration comparison dimension missing")
    status = source_status(conflict, old_geometry, new_geometry) if publication == conflict["publication"] else None
    del old_geometry, new_geometry
    obligations = [dict(id=f"migration:{publication}:{name}", kind=name, state="unresolved")
                   for name in review["reviewObligations"]]
    for direction in ("added", "removed"):
        for entry in changes[direction]:
            obligations.append(dict(id="migration-entry:" + digest(dict(publication=publication, direction=direction, entry=entry)),
                kind="instruction-entry-migration-review", state="unresolved", direction=direction, entry=entry))
    return dict(publication=publication,
        oldSource=dict(revision=predecessor["revision"], pdfSha256=predecessor["pdfSha256"], pages=old["outline"]["pages"]),
        newSource=dict(revision=source["revision"], pdfSha256=source["pdf"]["sha256"], pages=new["outline"]["pages"],
                       officialUrl=source["officialUrl"]),
        dimensions=dimensions, instructionEntryChanges=changes, obligations=obligations,
        sourceStatusConflict=status, sourceAdoption=False, constraintsParsed=False, legalDomainComplete=False)


def derive_candidate(lock, publishers, documents):
    """Keep the complete predecessor scope and every replacement source page."""
    selected = {row["publication"]: row for row in documents}
    sources = {row["publication"]: row for row in publishers}
    require(len(selected) == len(documents) == len(sources) == len(publishers) == 2
            and set(selected) == set(sources) == {"26568", "26569"}, "missing or duplicate publisher replacement")
    result = copy.deepcopy(lock["documents"])
    for row in result:
        if row["publication"] not in selected:
            continue
        source, evidence = sources[row["publication"]], selected[row["publication"]]
        row.update(revision=source["revision"], filename=source["pdf"]["filename"],
                   pdfSha256=source["pdf"]["sha256"], bytes=source["pdf"]["bytes"], pdfPages=evidence["newSource"]["pages"],
                   retrievalUrl=source["officialUrl"], officialIdentity=dict(contentUrl=source["officialUrl"],
                   byteStatus="exact-reviewed-publisher-input", sourceStatus="review-required"))
    require([row["publication"] for row in result] == [row["publication"] for row in lock["documents"]],
            "candidate lost predecessor publication")
    return dict(schema="ariadne.amd64-publisher-corpus-candidate/v1", predecessorSha256=digest(lock),
                decision="candidate-migration-review-required", scope=copy.deepcopy(lock["scope"]),
                documents=result, extractor=copy.deepcopy(lock["extractor"]), sourceAdoption=False,
                legalDomainComplete=False, constraintsParsed=False)


def reconstruct(old_cache, publisher_cache, output):
    output = run_output(output)
    require(not output.exists(), "migration output must be a fresh directory")
    review = reviewed_inputs(corpus.strict_json(INPUT.read_bytes()))
    lock = corpus.validate_lock(corpus.strict_json(corpus.LOCK.read_bytes()))
    inputs = authority._manifest(corpus.strict_json(authority.INPUT.read_bytes()))
    sources = {row["id"]: row for row in inputs["sources"]}
    before = implementation_sources()
    tool_root = ROOT / "target/rep-pdf-tools/root"
    tools = dict(pdftotext=tool_root / "usr/bin/pdftotext", mutool=tool_root / "usr/bin/mutool", python=Path(sys.executable))
    env = corpus.environment(tool_root / "usr/lib/x86_64-linux-gnu")
    corpus.check_runtime(lock, tools, env)
    output.mkdir(parents=True)
    baseline = output / "predecessor"
    old_products = corpus.reproduce(lock, old_cache, baseline, tools, env)
    corpus.check_products(lock, old_products, baseline, old_cache, tools, env, require_all=True)
    historical = []
    old_manual = corpus.strict_json(manual.LOCK.read_bytes())
    for document in old_manual["documents"]:
        content = corpus.strict_json((baseline / document["publication"] / "normalized.json").read_bytes())
        require(digest(content) == document["contentSha256"], "historical normalized input differs")
        historical.extend(dict(publication=document["publication"], ordinal=index, originalGap=gap,
                               oldGapId=geometry.old_gap_id(document["publication"], index, gap))
                          for index, gap in enumerate(content["gaps"]))
    require(len(historical) == len({row["oldGapId"] for row in historical}), "historical gap identity collision")
    historical_artifact = _write(output, "historical-gap-records.json", historical)
    documents, selected_sources = [], []
    for replacement in review["replacements"]:
        publication = replacement["publication"]
        previous = next(row for row in lock["documents"] if row["publication"] == publication)
        source = sources[replacement["publisherSource"]]
        require(source["publication"] == publication, "publisher publication changed")
        selected_sources.append(source)
        new_dir = output / "replacement" / publication
        _replacement_products(source, Path(publisher_cache), new_dir, lock, tools, env)
        documents.append(_compare_document(replacement, previous, source, baseline / publication, new_dir, output,
                                           review["sourceStatusConflict"]))
    candidate = derive_candidate(lock, selected_sources, documents)
    candidate_artifact = _write(output, "candidate.json", candidate)
    result = dict(schema=SCHEMA, reviewInputSha256=sha(INPUT), predecessorLockSha256=sha(corpus.LOCK),
                  publisherInputSha256=sha(authority.INPUT), implementation=before,
                  historicalGapRecords=len(historical), historicalGapArtifact=historical_artifact,
                  candidate=candidate_artifact, documents=documents,
                  comparisonComplete=True, sourceAdoption=False, constraintsParsed=False, legalDomainComplete=False,
                  limits=["Raw comparison is not a reviewed semantic migration.",
                          "Legacy normalized rows and constraint references are incomplete extraction views.",
                          "Whole-document rule references use lexical patterns; all unmatched text remains in the full-text comparison.",
                          "Geometry compares every Unicode word box and page descriptor; independent glyph extraction remains unavailable.",
                          "All source pages, candidate instruction entries and unresolved changes remain obligations."])
    require(before == implementation_sources(), "migration implementation or reviewed inputs changed during replay")
    _write(output, "migration.json", result)
    return result


def check(old_cache, publisher_cache, output):
    output = run_output(output)
    require(output.is_dir(), "missing migration output")
    with tempfile.TemporaryDirectory(prefix="migration-replay-", dir=output.parent) as temporary:
        fresh = Path(temporary) / "products"
        expected = reconstruct(old_cache, publisher_cache, fresh)
        expected_files = {str(path.relative_to(fresh)): path for path in fresh.rglob("*") if path.is_file()}
        actual_files = {str(path.relative_to(output)): path for path in output.rglob("*") if path.is_file()}
        require(set(actual_files) == set(expected_files), "migration output omission or extra product")
        for relative, path in actual_files.items():
            require(not path.is_symlink() and path.resolve().is_relative_to(output.resolve())
                    and sha(path) == sha(expected_files[relative]), "migration output differs from fresh source replay: " + relative)
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("extract", "check"))
    parser.add_argument("--old-cache", required=True, type=Path)
    parser.add_argument("--publisher-cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = (reconstruct if args.command == "extract" else check)(args.old_cache, args.publisher_cache, args.output)
    print(json.dumps(dict(comparisonComplete=result["comparisonComplete"], sourceAdoption=False,
                         historicalGapRecords=result["historicalGapRecords"],
                         documents=[dict(publication=row["publication"], oldPages=row["oldSource"]["pages"],
                                         newPages=row["newSource"]["pages"],
                                         dimensions={key: value["summary"] for key, value in row["dimensions"].items()},
                                         unresolvedObligations=len(row["obligations"])) for row in result["documents"]]), sort_keys=True))


if __name__ == "__main__":
    main()
