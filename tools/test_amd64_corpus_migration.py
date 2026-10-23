"""Publisher migration must retain source changes, ambiguity and old identities."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import amd64_corpus_migration as migration


def atoms(*values):
    return [dict(reference=dict(pdfPage=1, line=index), value=value) for index, value in enumerate(values)]


def review():
    return json.loads(migration.INPUT.read_text())


def status_pages():
    path = migration.INPUT.parent / "source-status-pages.json"
    return json.loads(path.read_text())


class CorpusMigrationControls(unittest.TestCase):
    def test_duplicate_occurrences_cannot_disappear_into_a_set(self):
        delta = migration.representation_delta(atoms("same", "same", "removed"), atoms("same", "added"))
        self.assertEqual(migration.summary(delta), dict(oldCount=3, newCount=2, orderedValuesEqual=False,
                                                        matched=1, removed=2, added=1))
        self.assertEqual([row["ordinal"] for row in delta["removed"]], [1, 2])

    def test_reordering_retains_both_source_addresses(self):
        delta = migration.representation_delta(atoms("A", "B"), atoms("B", "A"))
        self.assertFalse(delta["orderedValuesEqual"])
        self.assertEqual([(row["oldOrdinal"], row["newOrdinal"]) for row in delta["matched"]], [(1, 0), (0, 1)])
        self.assertEqual(delta["removed"], [])
        self.assertEqual(delta["added"], [])

    def test_duplicate_source_addresses_fail_even_with_different_text(self):
        old = atoms("A", "B")
        old[1]["reference"] = old[0]["reference"]
        with self.assertRaisesRegex(ValueError, "duplicate source address"):
            migration.representation_delta(old, atoms("A"))

    def test_raw_text_keeps_whitespace_blank_pages_and_line_endings(self):
        a = migration.page_text("A  B\r\n\n\f\f", 2)
        b = migration.page_text("A B\n\n\f\f", 2)
        self.assertEqual(a[-1], dict(reference=dict(pdfPage=2, line=1), value=""))
        delta = migration.representation_delta(a, b)
        self.assertEqual((len(delta["removed"]), len(delta["added"])), (1, 1))
        with self.assertRaisesRegex(ValueError, "page count"):
            migration.page_text("single page\f", 2)

    def test_document_reader_preserves_file_line_endings_before_comparison(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            raw = b"Source line\r\nSecond line\r\n\f"
            (directory / "layout.txt").write_bytes(raw)
            (directory / "outline.json").write_text('{"pages":1,"outline":[]}')
            with patch.object(migration.manual, "extract", return_value={}) as extract:
                document = migration._read_document(directory, [])
            self.assertEqual(document["layout"].encode(), raw)
            self.assertEqual(extract.call_args.args[0].encode(), raw)

    def test_outline_comparison_keeps_child_nodes_and_rejects_out_of_pdf_destinations(self):
        outline = dict(pages=5, outline=[dict(pdfPage=2, title="chapter", uri="#page=2",
                        children=[dict(pdfPage=3, title="new instruction", uri="#page=3")])])
        rows = migration.outline_rows(outline)
        self.assertEqual([row["reference"]["path"] for row in rows], [[0], [0, 0]])
        outline["outline"][0]["children"][0]["pdfPage"] = 6
        with self.assertRaisesRegex(ValueError, "escapes PDF"):
            migration.outline_rows(outline)

    def test_region_partition_preserves_unoutlined_front_matter_and_every_page(self):
        outline = dict(pages=10, outline=[dict(pdfPage=3, title="Contents"), dict(pdfPage=6, title="Instructions")])
        regions = migration.regions(outline)
        self.assertEqual([(row["reference"]["firstPdfPage"], row["reference"]["lastPdfPage"]) for row in regions],
                         [(1, 2), (3, 5), (6, 10)])
        self.assertEqual(regions[0]["value"]["kind"], "unoutlined-frontmatter")

    def test_global_rule_scan_includes_non_instruction_pages(self):
        source = dict(layout="Preface: CPUID information.\fInstruction: REX prefix.\f", outline=dict(pages=2))
        self.assertEqual([row["reference"]["pdfPage"] for row in migration.whole_document_rules(source)], [1, 2])

    def test_unchanged_lexical_rows_do_not_hide_changed_raw_text(self):
        def content(text):
            return dict(entries=[dict(id="e", chapter="chapter", title="MOV")], constraintReferences=[dict(
                entryIds=["e"], categories=["prefix"], sourceText=text, pdfPage=1, line=1, textSha256="a" * 64)])
        a, b = content("REX   prefix"), content("REX prefix")
        delta = migration.representation_delta(migration.normalized_rows(a, "constraintReferences"),
                                               migration.normalized_rows(b, "constraintReferences"))
        self.assertTrue(delta["orderedValuesEqual"])
        self.assertFalse(migration.representation_delta(atoms("REX   prefix"), atoms("REX prefix"))["orderedValuesEqual"])

    def test_exact_source_status_pages_expose_same_revision_marking_conflict(self):
        pages = status_pages()
        result = migration.source_status(review()["sourceStatusConflict"], [pages["old"]["page"]], [pages["new"]["page"]])
        self.assertEqual(result["status"], "unresolved")
        self.assertNotEqual(pages["old"]["pdfSha256"], pages["new"]["pdfSha256"])
        self.assertEqual(result["newCell"]["text"], "[AMD Confidential - Distribution with NDA]")

    def test_source_status_needs_actual_exact_cell_not_just_revision_or_flag(self):
        for attack in ("literal", "geometry", "page", "omission"):
            pages = status_pages()
            expected = review()["sourceStatusConflict"]
            page = pages["new"]["page"]
            cell = next(row for row in page["cells"] if row["id"] == expected["newCell"]["id"])
            if attack == "literal":
                cell["text"] = "[AMD Public Use]"
            elif attack == "geometry":
                cell["rect"][0] += 1
            elif attack == "page":
                page["pdfPage"] += 1
            else:
                page["cells"].remove(cell)
            with self.subTest(attack=attack), self.assertRaisesRegex(ValueError, "anchor differs"):
                migration.source_status(expected, [pages["old"]["page"]], [page])

    def test_resealed_replacement_scope_adoption_and_omission_are_rejected(self):
        for attack in ("adoption", "shrink", "omission", "unreviewed-source", "status-label"):
            value = review()
            if attack == "adoption":
                value["decision"] = "adopted"
            elif attack == "shrink":
                value["extentPolicy"] = "old-instruction-entries-only"
            elif attack == "omission":
                value["replacements"].pop()
            elif attack == "unreviewed-source":
                value["replacements"][0]["publisherSource"] = "different-vendor"
            else:
                value["sourceStatusConflict"]["newCell"]["text"] = "[AMD Public Use]"
            with self.subTest(attack=attack), self.assertRaises(ValueError):
                migration.reviewed_inputs(value)

    def test_review_binds_immutable_predecessor_and_publisher_inputs(self):
        migration.reviewed_inputs(review())
        with patch.object(migration, "sha", return_value="0" * 64):
            with self.assertRaisesRegex(ValueError, "input drift"):
                migration.reviewed_inputs(review())

    def test_candidate_preserves_all_five_publications_global_scope_and_expanded_pages(self):
        lock = migration.corpus.strict_json(migration.corpus.LOCK.read_bytes())
        sources = [row for row in json.loads(migration.authority.INPUT.read_text())["sources"] if row["publication"] in {"26568", "26569"}]
        documents = [dict(publication="26568", newSource=dict(pages=1973)), dict(publication="26569", newSource=dict(pages=368))]
        before = copy.deepcopy((lock, sources, documents))
        candidate = migration.derive_candidate(lock, sources, documents)
        self.assertEqual([row["volume"] for row in candidate["documents"]], [1, 2, 3, 4, 5])
        self.assertEqual(candidate["scope"], lock["scope"])
        self.assertEqual(candidate["documents"][3]["pdfPages"], 1973)
        self.assertEqual(candidate["documents"][3]["requiredRegions"], lock["documents"][3]["requiredRegions"])
        self.assertFalse(candidate["sourceAdoption"])
        self.assertFalse(candidate["legalDomainComplete"])
        self.assertFalse(candidate["constraintsParsed"])
        self.assertEqual(before, (lock, sources, documents))
        with self.assertRaisesRegex(ValueError, "missing or duplicate"):
            migration.derive_candidate(lock, sources, documents[:1])

    def test_output_replay_cannot_accept_missing_directory_or_write_maintained_products(self):
        with self.assertRaisesRegex(ValueError, "test output must"):
            migration.reconstruct(Path("unused"), Path("unused"), migration.INPUT.parent / "output")
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "missing migration output"):
                migration.check(Path("unused"), Path("unused"), Path(temporary) / "absent")

    def test_output_checker_rejects_omissions_resealed_changes_forged_adoption_and_symlinks(self):
        # Exercise check() against actual files. Only costly PDF reconstruction
        # is replaced; it independently writes the original small source page.
        expected = status_pages()
        def reconstruct(_old, _new, output):
            output.mkdir()
            artifact = migration._write(output, "source.json", expected)
            result = dict(sourceAdoption=False, source=artifact)
            migration._write(output, "migration.json", result)
            return result
        for attack in ("none", "omit", "reseal", "adoption", "extra", "symlink"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / "output"
                reconstruct(None, None, output)
                if attack == "omit":
                    (output / "source.json").unlink()
                elif attack == "reseal":
                    artifact = migration._write(output, "source.json", dict(forged="different source page"))
                    migration._write(output, "migration.json", dict(sourceAdoption=False, source=artifact))
                elif attack == "adoption":
                    report = json.loads((output / "migration.json").read_text())
                    report["sourceAdoption"] = True
                    migration._write(output, "migration.json", report)
                elif attack == "extra":
                    (output / "unbound-acceptance.json").write_text('{"passed":true}')
                elif attack == "symlink":
                    original = output / "source.json"
                    external = Path(temporary) / "outside.json"
                    original.rename(external)
                    original.symlink_to(external)
                with patch.object(migration, "reconstruct", side_effect=reconstruct):
                    if attack == "none":
                        self.assertFalse(migration.check(None, None, output)["sourceAdoption"])
                    else:
                        with self.assertRaises(ValueError):
                            migration.check(None, None, output)


if __name__ == "__main__":
    unittest.main()
