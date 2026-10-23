#!/usr/bin/env python3
"""Reproduce the candidate AMD source corpus without adopting historical pins.

fetch/reproduce products must be under target/ or a temporary workspace. The
candidate records source identities and unresolved obligations, never coverage
acceptance. migration checks a versioned, input-bound review of every changed
representation; it does not confer source completeness or semantic support.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

from amd64_inventory import strict_json
from amd64_inventory_xed import canonical, digest
import amd64_manual_inventory as manual
from run_output import run_output

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "tests/bap/fixtures/amd64-semantics/source-corpus-v2.lock.json"
SCHEMA = "ariadne.amd64-source-corpus-lock/v2"
PRODUCT = "ariadne.amd64-source-corpus-products/v2"
MIGRATION = "ariadne.amd64-source-corpus-migration-review/v1"
SUBSETS = ["general-purpose", "system", "media-128-256-512", "media-64", "x87"]
REVIEW_DIMENSIONS = ["pdf-identity", "full-text", "geometry", "outline", "source-regions",
                     "normalized-rows", "encoding-constraints", "extensions-and-scope"]
SHA = re.compile(r"[0-9a-f]{64}\Z")


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while block := stream.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def sha(value):
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ValueError("missing or invalid SHA256 identity")
    return value


def fields(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(label + " fields")


def official_url(value):
    url = urllib.parse.urlsplit(value)
    if url.scheme != "https" or url.hostname not in {"docs.amd.com", "www.amd.com", "amd.com"}:
        raise ValueError("official source must use an AMD HTTPS origin")
    return value


def validate_lock(lock):
    fields(lock, {"schema", "corpusVersion", "decision", "predecessors", "scope", "documents",
                  "extractor", "migrationPolicy"}, "source corpus")
    if lock["schema"] != SCHEMA or lock["corpusVersion"] != 2:
        raise ValueError("unsupported source corpus schema or version")
    if lock["decision"] != "candidate-proposed-unreviewed":
        raise ValueError("candidate lock cannot self-assert reviewed adoption")
    scope = lock["scope"]
    fields(scope, {"vendor", "executionModes", "softwareDomains", "architecturalSubsets",
                   "candidateDispositions", "extensionManifest", "sourceRegionAudit"}, "scope")
    if (scope["vendor"] != "AMD" or scope["executionModes"] != ["long-64"]
            or scope["softwareDomains"] != ["application", "privileged-system"]
            or scope["architecturalSubsets"] != SUBSETS):
        raise ValueError("candidate scope changed; create a new versioned scope")
    if scope["candidateDispositions"] != ["intel-only", "future", "undocumented", "unresolved"]:
        raise ValueError("candidate dispositions cannot silently disappear")
    extensions = scope["extensionManifest"]
    fields(extensions, {"status", "policy", "entries", "unresolved"}, "extension manifest")
    if extensions["status"] != "open" or not extensions["unresolved"]:
        raise ValueError("extension discovery is not a closed source audit")
    names = []
    for row in extensions["entries"]:
        fields(row, {"name", "disposition", "sourcePublications"}, "extension")
        if row["disposition"] != "source-listed-candidate" or not row["sourcePublications"]:
            raise ValueError("extension candidate needs source ownership")
        names.append(row["name"])
    if len(set(names)) != len(names) or not names:
        raise ValueError("duplicate or empty extension manifest")
    fields(scope["sourceRegionAudit"], {"status", "required"}, "source-region audit")
    if scope["sourceRegionAudit"]["status"] != "open":
        raise ValueError("source-region coverage remains an independent open audit")
    documents = lock["documents"]
    if [row["volume"] for row in documents] != [1, 2, 3, 4, 5]:
        raise ValueError("all five APM volumes are source obligations")
    publications = {row["publication"] for row in documents}
    if len(publications) != 5:
        raise ValueError("duplicate publication")
    for row in documents:
        fields(row, {"volume", "publication", "revision", "publisher", "filename", "pdfSha256",
                     "bytes", "pdfPages", "retrievalUrl", "officialIdentity", "requiredRegions"}, "document")
        if row["publisher"] != "Advanced Micro Devices" or not row["revision"]:
            raise ValueError("missing publisher or revision identity")
        if Path(row["filename"]).name != row["filename"]:
            raise ValueError("source filename must be a basename")
        sha(row["pdfSha256"])
        if (not isinstance(row["bytes"], int) or row["bytes"] <= 0
                or not isinstance(row["pdfPages"], int) or row["pdfPages"] <= 0):
            raise ValueError("missing exact PDF size or page count")
        if urllib.parse.urlsplit(row["retrievalUrl"]).scheme != "https":
            raise ValueError("source retrieval must use HTTPS")
        identity = row["officialIdentity"]
        fields(identity, {"byteStatus", "contentUrl", "metadataStatus", "metadataUrl"}, "official identity")
        official_url(identity["contentUrl"])
        official_url(identity["metadataUrl"])
        if identity["byteStatus"] not in {"repository-official-pin", "unverified"}:
            raise ValueError("official byte status is not an input-bound live verification")
        regions = row["requiredRegions"]
        if not regions or any(region.get("status") != "unmapped" for region in regions):
            raise ValueError("source regions require an independent complete audit")
        for region in regions:
            fields(region, {"kind", "selector", "status"}, "source region")
        if row["volume"] in {1, 2} and not any(region["kind"] == "global-rules" for region in regions):
            raise ValueError("Vol1/2 global rules cannot be omitted")
    for row in extensions["entries"]:
        if not set(row["sourcePublications"]) <= publications:
            raise ValueError("unknown extension source publication")
    extractor = lock["extractor"]
    fields(extractor, {"schema", "normalizationSchema", "environment", "sources", "tools", "commands"}, "extractor")
    if extractor["schema"] != PRODUCT or extractor["normalizationSchema"] != "ariadne.amd-manual-inventory/v1":
        raise ValueError("unknown extraction or normalization schema")
    if extractor["environment"] != {"LC_ALL": "C", "LANG": "C", "TZ": "UTC"}:
        raise ValueError("unbound extraction locale")
    if set(extractor["tools"]) != {"pdftotext", "mutool", "python"}:
        raise ValueError("missing extraction tool")
    for tool in extractor["tools"].values():
        fields(tool, {"sha256", "version", "versionArgs", "libraries"}, "tool")
        sha(tool["sha256"])
        if not tool["version"] or not tool["versionArgs"] or not tool["libraries"]:
            raise ValueError("missing tool version or runtime library pins")
        for key, value in tool["libraries"].items():
            if Path(key).name != key:
                raise ValueError("runtime library name")
            sha(value)
    expected_commands = {"layout": ["pdftotext", "-layout", "-enc", "UTF-8", "{pdf}", "{output}"],
                         "geometry": ["pdftotext", "-bbox-layout", "-enc", "UTF-8", "{pdf}", "{output}"],
                         "outline": ["mutool", "run", "tools/amd64_manual_outline.js", "{pdf}"]}
    if extractor["commands"] != expected_commands:
        raise ValueError("unreviewed extractor options; create a separate corpus candidate")
    for source, value in extractor["sources"].items():
        if not source.startswith("tools/") or ".." in Path(source).parts:
            raise ValueError("extractor source path")
        sha(value)
    if set(extractor["sources"]) != {"tools/amd64_source_corpus.py", "tools/amd64_manual_inventory.py",
                                      "tools/amd64_manual_outline.js", "tools/amd64_inventory.py",
                                      "tools/amd64_inventory_xed.py", "tools/run_output.py"}:
        raise ValueError("source corpus extractor dependency identities missing")
    if not lock["predecessors"] or lock["migrationPolicy"] != REVIEW_DIMENSIONS:
        raise ValueError("missing versioned migration review dimensions")
    for previous in lock["predecessors"]:
        fields(previous, {"path", "schema", "sha256"}, "predecessor")
        sha(previous["sha256"])
    return lock


def environment(libdir=None):
    env = dict(os.environ, LC_ALL="C", LANG="C", TZ="UTC")
    env.pop("LD_PRELOAD", None)
    if libdir:
        env["LD_LIBRARY_PATH"] = str(Path(libdir).resolve())
    else:
        env.pop("LD_LIBRARY_PATH", None)
    return env


def tool_identity(executable, version_args, env):
    path = Path(executable).resolve()
    version = subprocess.run([str(path), *version_args], env=env, capture_output=True,
                             check=True, timeout=30)
    first = (version.stdout + version.stderr).decode("utf-8").splitlines()[0]
    linked = subprocess.run(["ldd", str(path)], env=env, capture_output=True, check=True, timeout=30)
    libraries = {}
    for line in linked.stdout.decode().splitlines():
        if "not found" in line:
            raise ValueError("unresolved extraction runtime library")
        match = re.search(r"(?:=>\s+)?(/[^\s]+)\s+\(0x", line)
        if match:
            library = Path(match[1]).resolve()
            libraries[Path(match[1]).name] = sha_file(library)
    return dict(sha256=sha_file(path), version=first, versionArgs=version_args, libraries=libraries)


def check_runtime(lock, executables, env):
    validate_lock(lock)
    for relative, expected in lock["extractor"]["sources"].items():
        if sha_file(ROOT / relative) != expected:
            raise ValueError("extractor source drift: " + relative)
    for name, pin in lock["extractor"]["tools"].items():
        if tool_identity(executables[name], pin["versionArgs"], env) != pin:
            raise ValueError("extractor tool or runtime library drift: " + name)
    for previous in lock["predecessors"]:
        if sha_file(ROOT / previous["path"]) != previous["sha256"]:
            raise ValueError("historical predecessor changed")


def verify_pdf(path, document):
    path = Path(path)
    if path.stat().st_size != document["bytes"] or sha_file(path) != document["pdfSha256"]:
        raise ValueError("PDF size or digest mismatch: " + document["publication"])
    with path.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise ValueError("source is not a PDF")


def fetch(lock, cache, official=False, opener=urllib.request.urlopen):
    validate_lock(lock)
    cache = run_output(cache)
    cache.mkdir(parents=True, exist_ok=True)
    receipts = []
    for document in lock["documents"]:
        url = document["officialIdentity"]["contentUrl"] if official else document["retrievalUrl"]
        path = cache / ("official" if official else ".") / document["filename"]
        path.parent.mkdir(parents=True, exist_ok=True)
        receipt = dict(publication=document["publication"], requestedUrl=url, expectedSha256=document["pdfSha256"])
        temporary = path.with_suffix(".part")
        try:
            with opener(url, timeout=45) as response, temporary.open("wb") as stream:
                receipt["finalUrl"] = response.url
                if official:
                    official_url(response.url)
                received = 0
                while block := response.read(1024 * 1024):
                    received += len(block)
                    if received > document["bytes"]:
                        raise ValueError("publisher payload exceeds exact source size")
                    stream.write(block)
            verify_pdf(temporary, document)
            temporary.replace(path)
            receipt.update(status="exact-bytes-retrieved", observedSha256=sha_file(path))
        except (OSError, ValueError) as error:
            temporary.unlink(missing_ok=True)
            receipt.update(status="unverified", error=str(error))
        receipts.append(receipt)
    (cache / ("official-retrievals.json" if official else "retrievals.json")).write_bytes(canonical(receipts) + b"\n")
    return receipts


def reproduce(lock, cache, output, executables, env, publications=None):
    check_runtime(lock, executables, env)
    output = run_output(output)
    output.mkdir(parents=True, exist_ok=True)
    selected = set(publications or [row["publication"] for row in lock["documents"]])
    if not selected <= {row["publication"] for row in lock["documents"]}:
        raise ValueError("unknown requested publication")
    rows = []
    for document in lock["documents"]:
        if document["publication"] not in selected:
            continue
        pdf = Path(cache).resolve() / document["filename"]
        verify_pdf(pdf, document)
        work = output / document["publication"]
        work.mkdir(exist_ok=True)
        if not work.resolve().is_relative_to(output):
            raise ValueError("reproduction directory escapes output")
        expected_files = {"layout.txt", "bbox.html", "outline.json"}
        if any(row["kind"] == "instruction-reference" for row in document["requiredRegions"]):
            expected_files.add("normalized.json")
        if any(item.name not in expected_files or item.is_symlink() for item in work.iterdir()):
            raise ValueError("unexpected old reproduction product; use a fresh output")
        for key, filename in (("layout", "layout.txt"), ("geometry", "bbox.html")):
            command = lock["extractor"]["commands"][key]
            arguments = [str(executables[command[0]])] + [
                str(pdf) if value == "{pdf}" else str(work / filename) if value == "{output}" else value
                for value in command[1:]]
            subprocess.run(arguments, check=True, env=env, capture_output=True, timeout=180)
        with (work / "outline.json").open("wb") as stream:
            subprocess.run([str(executables["mutool"]), "run", str(ROOT / "tools/amd64_manual_outline.js"), str(pdf)],
                           stdout=stream, stderr=subprocess.PIPE, check=True, env=env, timeout=180)
        outline = strict_json((work / "outline.json").read_bytes())
        if outline["pages"] != document["pdfPages"]:
            raise ValueError("PDF page identity mismatch")
        chapters = [row["selector"] for row in document["requiredRegions"] if row["kind"] == "instruction-reference"]
        if chapters:
            content = manual.extract((work / "layout.txt").read_text(), outline, chapters)
            (work / "normalized.json").write_bytes(canonical(content) + b"\n")
        rows.append(dict(publication=document["publication"], pdfSha256=document["pdfSha256"],
                         products={item.name: sha_file(item) for item in sorted(work.iterdir()) if item.is_file()}))
    result = dict(schema=PRODUCT, corpusSha256=digest(lock), requiredPublications=[row["publication"] for row in lock["documents"]],
                  reproducedPublications=rows, extractor=lock["extractor"], scopeDecision=lock["decision"],
                  unresolved=obligations(lock), legalEncodingCompleteness="not-established")
    (output / "products.json").write_bytes(canonical(result) + b"\n")
    return result



def check_products(lock, result, output, cache, executables, env, require_all=False):
    check_runtime(lock, executables, env)
    fields(result, {"schema", "corpusSha256", "requiredPublications", "reproducedPublications", "extractor",
                    "scopeDecision", "unresolved", "legalEncodingCompleteness"}, "reproduction products")
    if (result["schema"] != PRODUCT or result["corpusSha256"] != digest(lock)
            or result["extractor"] != lock["extractor"] or result["scopeDecision"] != lock["decision"]
            or result["unresolved"] != obligations(lock) or result["legalEncodingCompleteness"] != "not-established"):
        raise ValueError("reproduction identity, environment or completion claims changed")
    required = [row["publication"] for row in lock["documents"]]
    if result["requiredPublications"] != required:
        raise ValueError("required source denominator changed")
    observed = [row.get("publication") for row in result["reproducedPublications"]]
    if not observed or observed != [name for name in required if name in observed]:
        raise ValueError("unknown, duplicated or reordered publication products")
    missing = [name for name in required if name not in observed]
    if require_all and missing:
        raise ValueError("required source publications not reproduced: " + ", ".join(missing))
    output = Path(output).resolve()
    by_publication = {row["publication"]: row for row in lock["documents"]}
    for row in result["reproducedPublications"]:
        fields(row, {"publication", "pdfSha256", "products"}, "publication products")
        document = by_publication[row["publication"]]
        if row["pdfSha256"] != document["pdfSha256"]:
            raise ValueError("product PDF identity changed")
        verify_pdf(Path(cache) / document["filename"], document)
        expected = {"layout.txt", "bbox.html", "outline.json"}
        if any(region["kind"] == "instruction-reference" for region in document["requiredRegions"]):
            expected.add("normalized.json")
        if set(row["products"]) != expected:
            raise ValueError("missing full-text, geometry, outline or normalization product")
        for filename, expected_sha in row["products"].items():
            sha(expected_sha)
            actual = output / row["publication"] / filename
            if not actual.resolve().is_relative_to(output) or actual.is_symlink():
                raise ValueError("reproduction product escapes output")
            if sha_file(actual) != expected_sha:
                raise ValueError("reproduction product drift: " + filename)
    return dict(schema=PRODUCT, reproduced=observed, missingPublications=missing,
                unresolved=obligations(lock), corpusAdoption="not-established")


def obligations(lock):
    result = ["scope-and-extension-manifest-review", "complete-global-rule-and-source-region-audit",
              "input-bound-full-text-geometry-and-normalization-migration-review"]
    result.extend("official-byte-identity:" + row["publication"] for row in lock["documents"]
                  if row["officialIdentity"]["byteStatus"] == "unverified")
    return result


def migration(old_bytes, new_bytes, review, evidence_root):
    old, new = strict_json(old_bytes), validate_lock(strict_json(new_bytes))
    if old.get("schema") != "ariadne.amd-manual-inventory-lock/v1":
        raise ValueError("unsupported migration predecessor schema")
    fields(review, {"schema", "fromSha256", "toSha256", "dimensions"}, "migration review")
    old_sha, new_sha = hashlib.sha256(old_bytes).hexdigest(), hashlib.sha256(new_bytes).hexdigest()
    if (review["schema"] != MIGRATION or review["fromSha256"] != old_sha or review["toSha256"] != new_sha):
        raise ValueError("migration review is not bound to exact versioned inputs")
    if not any(row["schema"] == old["schema"] and row["sha256"] == old_sha for row in new["predecessors"]):
        raise ValueError("candidate predecessor does not match old corpus")
    if set(review["dimensions"]) != set(REVIEW_DIMENSIONS):
        raise ValueError("migration review omits required comparison dimensions")
    evidence_root = Path(evidence_root).resolve()
    for row in review["dimensions"].values():
        fields(row, {"oldProduct", "newProduct", "reviewedDelta"}, "review dimension")
        for product in row.values():
            fields(product, {"path", "sha256"}, "review product")
            sha(product["sha256"])
            relative = Path(product["path"])
            actual = (evidence_root / relative).resolve()
            if relative.is_absolute() or not actual.is_relative_to(evidence_root):
                raise ValueError("migration evidence escapes review root")
            if sha_file(actual) != product["sha256"]:
                raise ValueError("migration product or reviewed delta drift")
    return dict(fromSha256=old_sha, toSha256=new_sha, reviewSha256=digest(review),
                migrationReview="input-bound-dimensions-present", corpusAdoption="not-established", unresolved=obligations(new))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=LOCK)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check-lock")
    fetch_parser = commands.add_parser("fetch")
    fetch_parser.add_argument("--cache", type=Path, required=True)
    fetch_parser.add_argument("--official", action="store_true")
    repro = commands.add_parser("reproduce")
    repro.add_argument("--cache", type=Path, required=True)
    repro.add_argument("--output", type=Path, required=True)
    repro.add_argument("--publication", action="append")
    repro.add_argument("--pdftotext", type=Path, required=True)
    repro.add_argument("--mutool", type=Path, required=True)
    repro.add_argument("--tool-libdir", type=Path)
    product_check = commands.add_parser("check-products")
    product_check.add_argument("products", type=Path)
    product_check.add_argument("--cache", type=Path, required=True)
    product_check.add_argument("--require-all", action="store_true")
    product_check.add_argument("--pdftotext", type=Path, required=True)
    product_check.add_argument("--mutool", type=Path, required=True)
    product_check.add_argument("--tool-libdir", type=Path)
    migrate = commands.add_parser("migration")
    migrate.add_argument("old", type=Path)
    migrate.add_argument("new", type=Path)
    migrate.add_argument("--review", type=Path, required=True)
    migrate.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args(argv)
    lock = validate_lock(strict_json(args.lock.read_bytes()))
    if args.command == "check-lock":
        result = dict(schema=SCHEMA, decision=lock["decision"], unresolved=obligations(lock))
    elif args.command == "fetch":
        result = fetch(lock, args.cache, args.official)
        print(json.dumps(result, sort_keys=True))
        return 0 if all(row["status"] == "exact-bytes-retrieved" for row in result) else 1
    elif args.command == "check-products":
        executables = dict(pdftotext=args.pdftotext.resolve(), mutool=args.mutool.resolve(), python=Path(sys.executable).resolve())
        result = check_products(lock, strict_json(args.products.read_bytes()), args.products.parent, args.cache,
                                executables, environment(args.tool_libdir), args.require_all)
    elif args.command == "reproduce":
        executables = dict(pdftotext=args.pdftotext.resolve(), mutool=args.mutool.resolve(), python=Path(sys.executable).resolve())
        result = reproduce(lock, args.cache, args.output, executables, environment(args.tool_libdir), args.publication)
        result = dict(schema=result["schema"], publications=[row["publication"] for row in result["reproducedPublications"]], unresolved=result["unresolved"])
    else:
        result = migration(args.old.read_bytes(), args.new.read_bytes(), strict_json(args.review.read_bytes()), args.evidence_root)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
