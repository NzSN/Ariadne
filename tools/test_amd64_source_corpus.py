"""Candidate source pins cannot masquerade as reviewed or complete coverage."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import amd64_source_corpus as corpus


def fixture():
    return corpus.strict_json(corpus.LOCK.read_bytes())


class Response(io.BytesIO):
    def __init__(self, content, url):
        super().__init__(content)
        self.url = url


class SourceCorpusControls(unittest.TestCase):
    def test_maintained_candidate_binds_five_volumes_and_keeps_open_obligations(self):
        lock = corpus.validate_lock(fixture())
        self.assertEqual([row["volume"] for row in lock["documents"]], [1, 2, 3, 4, 5])
        self.assertEqual(lock["scope"]["softwareDomains"], ["application", "privileged-system"])
        self.assertEqual(lock["scope"]["architecturalSubsets"], corpus.SUBSETS)
        self.assertEqual(set(corpus.obligations(lock)), {
            "scope-and-extension-manifest-review", "complete-global-rule-and-source-region-audit",
            "input-bound-full-text-geometry-and-normalization-migration-review",
            "official-byte-identity:26568", "official-byte-identity:26569"})
        self.assertTrue(all(row["officialIdentity"]["byteStatus"] == "unverified"
                            for row in lock["documents"][3:]))

    def test_missing_identity_cannot_be_replaced_by_equal_counts(self):
        for field in ("pdfSha256", "revision", "publisher", "pdfPages", "bytes"):
            with self.subTest(field=field):
                lock = fixture()
                del lock["documents"][3][field]
                with self.assertRaisesRegex(ValueError, "document fields"):
                    corpus.validate_lock(lock)
        lock = fixture()
        lock["documents"][3]["pdfSha256"] = "equal-counts"
        with self.assertRaisesRegex(ValueError, "SHA256"):
            corpus.validate_lock(lock)

    def test_forged_closed_scope_adoption_and_passing_flags_are_rejected(self):
        mutations = [lambda lock: lock.update(accepted=True),
                     lambda lock: lock.update(decision="reviewed-adopted"),
                     lambda lock: lock["scope"]["extensionManifest"].update(status="closed"),
                     lambda lock: lock["scope"]["extensionManifest"].update(unresolved=[]),
                     lambda lock: lock["scope"]["sourceRegionAudit"].update(status="complete"),
                     lambda lock: lock["scope"].update(candidateDispositions=[]),
                     lambda lock: lock["documents"].pop(0),
                     lambda lock: lock["documents"][0].update(requiredRegions=[]),
                     lambda lock: lock["documents"][3]["officialIdentity"].update(byteStatus="verified")]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                lock = fixture()
                mutate(lock)
                with self.assertRaises(ValueError):
                    corpus.validate_lock(lock)

    def test_vendor_mode_and_privileged_scope_cannot_silently_shrink(self):
        for key, value in (("vendor", "Intel"), ("executionModes", ["legacy"]),
                           ("softwareDomains", ["application"]), ("architecturalSubsets", ["system"])):
            lock = fixture()
            lock["scope"][key] = value
            with self.assertRaisesRegex(ValueError, "scope changed"):
                corpus.validate_lock(lock)

    def test_tool_options_locale_and_normalization_schema_are_bound(self):
        for mutation in (lambda row: row["commands"]["layout"].remove("-layout"),
                         lambda row: row["environment"].update(LC_ALL="en_US.UTF-8"),
                         lambda row: row.update(normalizationSchema="ariadne.amd-manual-inventory/v900"),
                         lambda row: row["tools"].pop("mutool"),
                         lambda row: row["tools"]["pdftotext"].update(libraries={})):
            lock = fixture()
            mutation(lock["extractor"])
            with self.assertRaises(ValueError):
                corpus.validate_lock(lock)

    def test_publisher_lookalike_and_archive_redirect_do_not_verify_identity(self):
        for value in ("http://docs.amd.com/content", "https://docs.amd.com.example/content",
                      "https://archive.example/amd.pdf"):
            with self.assertRaisesRegex(ValueError, "AMD HTTPS"):
                corpus.official_url(value)
        lock = fixture()
        payload = b"%PDF-1.0\nsmall test source\n"
        for row in lock["documents"]:
            row.update(bytes=len(payload), pdfSha256=hashlib.sha256(payload).hexdigest())
        with tempfile.TemporaryDirectory() as tmp:
            result = corpus.fetch(lock, tmp, official=True,
                                  opener=lambda url, timeout: Response(payload, "https://archive.example/manual.pdf"))
            self.assertTrue(all(row["status"] == "unverified" for row in result))
            self.assertEqual(list(Path(tmp).rglob("*.pdf")), [])

    def test_fetch_requires_exact_official_payload_and_never_mutates_lock(self):
        lock = fixture()
        payload = b"%PDF-1.0\nsmall test source\n"
        for row in lock["documents"]:
            row.update(bytes=len(payload), pdfSha256=hashlib.sha256(payload).hexdigest())
        before = copy.deepcopy(lock)
        with tempfile.TemporaryDirectory() as tmp:
            result = corpus.fetch(lock, tmp, official=True,
                                  opener=lambda url, timeout: Response(payload, url))
            self.assertTrue(all(row["status"] == "exact-bytes-retrieved" for row in result))
            self.assertEqual(len(list(Path(tmp).rglob("*.pdf"))), 5)
            self.assertEqual(lock, before)
        with tempfile.TemporaryDirectory() as tmp:
            result = corpus.fetch(lock, tmp, official=True,
                                  opener=lambda url, timeout: Response(payload.replace(b"small", b"WRONG"), url))
            self.assertTrue(all(row["status"] == "unverified" for row in result))
            self.assertEqual(list(Path(tmp).rglob("*.pdf")), [])

    def test_pdf_tampering_and_non_pdf_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source.pdf"
            path.write_bytes(b"%PDF-unit-test")
            pin = dict(publication="unit", bytes=path.stat().st_size, pdfSha256=corpus.sha_file(path))
            corpus.verify_pdf(path, pin)
            path.write_bytes(b"%PDF-unit-TEST")
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                corpus.verify_pdf(path, pin)
            path.write_bytes(b"publisher HTML")
            pin.update(bytes=path.stat().st_size, pdfSha256=corpus.sha_file(path))
            with self.assertRaisesRegex(ValueError, "not a PDF"):
                corpus.verify_pdf(path, pin)

    def test_source_and_dynamic_library_drift_fail_before_extraction(self):
        lock = fixture()
        def expected_hash(path):
            relative = str(Path(path).relative_to(corpus.ROOT))
            return lock["extractor"]["sources"].get(relative,
                   next((row["sha256"] for row in lock["predecessors"] if row["path"] == relative), None))
        executables = {name: name for name in lock["extractor"]["tools"]}
        def identity(path, args, env):
            return copy.deepcopy(lock["extractor"]["tools"][path])
        with patch.object(corpus, "sha_file", side_effect=expected_hash), patch.object(corpus, "tool_identity", side_effect=identity):
            corpus.check_runtime(lock, executables, {})
        def corrupt_identity(path, args, env):
            result = identity(path, args, env)
            if path == "mutool":
                name = next(iter(result["libraries"]))
                result["libraries"][name] = "a" * 64
            return result
        with patch.object(corpus, "sha_file", side_effect=expected_hash), patch.object(corpus, "tool_identity", side_effect=corrupt_identity):
            with self.assertRaisesRegex(ValueError, "runtime library drift"):
                corpus.check_runtime(lock, executables, {})
        with patch.object(corpus, "sha_file", return_value="b" * 64):
            with self.assertRaisesRegex(ValueError, "source drift"):
                corpus.check_runtime(lock, executables, {})

    def test_partial_reproduction_names_missing_global_rule_sources(self):
        lock = fixture()
        payload = b"%PDF-test"
        for row in lock["documents"]:
            row.update(bytes=len(payload), pdfSha256=hashlib.sha256(payload).hexdigest(), pdfPages=1)
        with tempfile.TemporaryDirectory() as tmp:
            cache, output = Path(tmp) / "cache", Path(tmp) / "products"
            cache.mkdir()
            (cache / lock["documents"][0]["filename"]).write_bytes(payload)
            def run(arguments, **kwargs):
                if "run" in arguments:
                    kwargs["stdout"].write(b'{"pages":1,"outline":[]}')
                else:
                    Path(arguments[-1]).write_text("source page\f" if "-layout" in arguments else "<html>geometry</html>")
            with patch.object(corpus, "check_runtime"), patch.object(corpus.subprocess, "run", side_effect=run):
                result = corpus.reproduce(lock, cache, output, dict(pdftotext="text", mutool="pdf"), {}, ["24592"])
            self.assertEqual(result["requiredPublications"], ["24592", "24593", "24594", "26568", "26569"])
            self.assertEqual([row["publication"] for row in result["reproducedPublications"]], ["24592"])
            self.assertEqual(result["legalEncodingCompleteness"], "not-established")
            self.assertIn("complete-global-rule-and-source-region-audit", result["unresolved"])
            self.assertEqual(set(result["reproducedPublications"][0]["products"]), {"layout.txt", "bbox.html", "outline.json"})
            with patch.object(corpus, "check_runtime"):
                checked = corpus.check_products(lock, result, output, cache, {}, {})
                self.assertEqual(checked["missingPublications"], ["24593", "24594", "26568", "26569"])
                with self.assertRaisesRegex(ValueError, "not reproduced"):
                    corpus.check_products(lock, result, output, cache, {}, {}, require_all=True)
                forged = copy.deepcopy(result)
                forged["legalEncodingCompleteness"] = "complete"
                with self.assertRaisesRegex(ValueError, "completion claims"):
                    corpus.check_products(lock, forged, output, cache, {}, {})
                changed = copy.deepcopy(result)
                del changed["reproducedPublications"][0]["products"]["bbox.html"]
                with self.assertRaisesRegex(ValueError, "missing full-text, geometry"):
                    corpus.check_products(lock, changed, output, cache, {}, {})
                (output / "24592/layout.txt").write_text("tampered source text")
                with self.assertRaisesRegex(ValueError, "product drift"):
                    corpus.check_products(lock, result, output, cache, {}, {})

    def test_outputs_cannot_be_retained_as_source(self):
        with self.assertRaisesRegex(ValueError, "output must be"):
            corpus.fetch(fixture(), corpus.ROOT / "tests/unsafe-generated-products")

    def review(self, evidence):
        old = (corpus.ROOT / "tests/bap/fixtures/amd64-semantics/manual-inventory.lock.json").read_bytes()
        new = corpus.LOCK.read_bytes()
        products = {}
        for kind in ("oldProduct", "newProduct", "reviewedDelta"):
            path = evidence / kind
            path.write_bytes((kind + "\n").encode())
            products[kind] = dict(path=kind, sha256=corpus.sha_file(path))
        return old, new, dict(schema=corpus.MIGRATION, fromSha256=hashlib.sha256(old).hexdigest(),
                              toSha256=hashlib.sha256(new).hexdigest(),
                              dimensions={key: copy.deepcopy(products) for key in corpus.REVIEW_DIMENSIONS})

    def test_input_bound_migration_reviews_do_not_adopt_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            old, new, review = self.review(Path(tmp))
            result = corpus.migration(old, new, review, tmp)
            self.assertEqual(result["corpusAdoption"], "not-established")
            self.assertIn("official-byte-identity:26568", result["unresolved"])

    def test_migration_rejects_versions_missing_dimensions_and_stale_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            old, new, review = self.review(Path(tmp))
            for dimension in corpus.REVIEW_DIMENSIONS:
                changed = copy.deepcopy(review)
                del changed["dimensions"][dimension]
                with self.assertRaisesRegex(ValueError, "comparison dimensions"):
                    corpus.migration(old, new, changed, tmp)
            with self.assertRaisesRegex(ValueError, "exact versioned inputs"):
                corpus.migration(old + b"\n", new, review, tmp)
            changed = json.loads(new)
            changed["schema"] = "ariadne.amd64-source-corpus-lock/v3"
            with self.assertRaisesRegex(ValueError, "unsupported source corpus schema"):
                corpus.migration(old, json.dumps(changed).encode(), review, tmp)
            (Path(tmp) / "reviewedDelta").write_bytes(b"changed review")
            with self.assertRaisesRegex(ValueError, "reviewed delta drift"):
                corpus.migration(old, new, review, tmp)

    def test_duplicate_json_keys_and_review_path_escapes_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            corpus.strict_json(b'{"schema":"v1","schema":"v2"}')
        with tempfile.TemporaryDirectory() as tmp:
            old, new, review = self.review(Path(tmp))
            review["dimensions"]["geometry"]["newProduct"]["path"] = "../outside"
            with self.assertRaisesRegex(ValueError, "escapes review root"):
                corpus.migration(old, new, review, tmp)


if __name__ == "__main__":
    unittest.main()
