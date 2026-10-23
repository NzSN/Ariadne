"""Actual minimized PDF word-box regressions and source-omission controls."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import amd64_manual_geometry as geometry

FIXTURES = ROOT / "tests/bap/fixtures/manual-geometry"


def fixture(name):
    return json.loads((FIXTURES / (name + ".json")).read_text())


def analyze(item):
    layout = [""] * item["pdfPage"]
    layout[-1] = item["layoutPage"]
    tables, rows, groups = geometry.table_geometry(item["baseline"], layout,
        [dict(pdfPage=item["pdfPage"], cells=item["cells"])])
    records = geometry.dispositions(item["publication"], item["baseline"], layout, tables, rows, groups)
    return dict(content=dict(sourceCells=item["cells"], tables=tables, rows=rows, oldGapDispositions=records),
                contentSha256=geometry.digest(dict(tables=tables, rows=rows, dispositions=records)))


def group(text, y, ambiguous=False):
    return dict(text=text, y=y, ambiguous=ambiguous, cells=[dict(id=text + str(y), text=text, rect=[10, y, 100, y + 10])])


class ManualGeometryControls(unittest.TestCase):
    def test_actual_evex_operand_wraps_keep_all_five_gap_obligations(self):
        result = analyze(fixture("addpd"))["content"]
        self.assertEqual([row["disposition"] for row in result["oldGapDispositions"]],
                         ["justified-continuation", "unresolved", "unresolved", "justified-continuation", "justified-continuation"])
        self.assertEqual(len(result["rows"]), 4)
        self.assertTrue(all(len(row["encodingCells"]) == 5 for row in result["rows"]))
        for record in result["oldGapDispositions"]:
            self.assertEqual(record["legacySource"]["pdfPage"], 78)
            self.assertTrue(record["cells"])
            self.assertIn("originalGap", record)
        # A literal malformed source operand is retained, never corrected by a mnemonic guess.
        self.assertIn("VGETEXPPD", result["oldGapDispositions"][1]["originalGap"]["sourceText"])

    def test_actual_centered_cmov_opcode_never_fills_blank_neighbors(self):
        result = analyze(fixture("cmov"))["content"]
        self.assertEqual([bool(row["encodingCells"]) for row in result["rows"]], [False, True, False])
        self.assertEqual([row["disposition"] for row in result["oldGapDispositions"]], ["unresolved", "unresolved"])
        self.assertEqual(len(result["oldGapDispositions"]), 2)

    def test_actual_outline_owner_mismatch_is_refused(self):
        item = fixture("aesenc")
        self.assertEqual(item["baseline"]["entries"][0]["title"], "AESDECLAST VAESDECLAST")
        self.assertTrue(any(cell["text"].startswith("AESENC ") for cell in item["cells"]))
        result = analyze(item)["content"]
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["oldGapDispositions"][0]["disposition"], "unresolved")

    def test_actual_vol5_centered_opcode_belongs_to_one_wrapped_operand(self):
        result = analyze(fixture("cvtps2pi"))["content"]
        self.assertEqual([row["disposition"] for row in result["oldGapDispositions"]],
                         ["justified-continuation"] * 3 + ["non-encoding-material"] * 2)
        row = result["rows"][0]
        self.assertEqual(row["encodingCells"], ["pdf:40:cell:21"])
        self.assertEqual(row["centeredEncodingCells"],
                         ["pdf:40:cell:19", "pdf:40:cell:20", "pdf:40:cell:21"])
        self.assertEqual(analyze(fixture("frstor"))["content"]["oldGapDispositions"][0]["disposition"],
                         "justified-continuation")

    def test_centered_opcode_rejects_moved_duplicate_and_mnemonic_neighbor(self):
        for attack in ("moved", "duplicate", "mnemonic", "column", "intervening"):
            item = fixture("cvtps2pi")
            opcode = next(cell for cell in item["cells"] if cell["id"] == "pdf:40:cell:21")
            operand = next(cell for cell in item["cells"] if cell["id"] == "pdf:40:cell:20")
            if attack == "moved":
                opcode["rect"][1] += 2
                opcode["rect"][3] += 2
            elif attack == "duplicate":
                duplicate = copy.deepcopy(opcode)
                duplicate["id"] = "attack-duplicate-opcode"
                item["cells"].append(duplicate)
            elif attack == "mnemonic":
                operand["text"] = "CVTPS2PI xmm/mem64"
            elif attack == "column":
                opcode["rect"][0] -= 30
                opcode["rect"][2] -= 30
            else:
                extra = copy.deepcopy(operand)
                extra.update(id="attack-intervening", text="unknown row", rect=[69, 366.4, 100, 375.7])
                item["cells"].append(extra)
            result = analyze(item)["content"]
            self.assertFalse(result["rows"][0]["encodingCells"], attack)
            self.assertTrue(all(row["disposition"] == "unresolved" for row in result["oldGapDispositions"][:3]), attack)

    def test_actual_diagram_disposition_retains_semantic_constraint_obligation(self):
        result = analyze(fixture("paddb-diagram"))["content"]
        self.assertEqual(len(result["oldGapDispositions"]), 5)
        self.assertTrue(all(row["disposition"] == "non-encoding-material" for row in result["oldGapDispositions"]))
        self.assertTrue(all(row["constraintsParsed"] is False for row in result["oldGapDispositions"]))
        region = result["tables"][0]["materialRegions"][0]
        self.assertFalse(region["constraintsParsed"])
        self.assertEqual(region["kind"], "source-owned-register-bit-diagram")
        self.assertTrue(region["anchorCells"])

    def test_diagram_requires_owner_label_bit_geometry_and_no_encoding_or_note(self):
        for attack in ("missing-label", "wrong-owner", "no-bit-indices", "new-opcode", "new-note", "duplicate"):
            item = fixture("paddb-diagram")
            label = next(cell for cell in item["cells"] if cell["text"].endswith(".eps"))
            if attack == "missing-label":
                item["cells"].remove(label)
            elif attack == "wrong-owner":
                label["text"] = "psubb-64.eps"
            elif attack == "no-bit-indices":
                item["cells"] = [cell for cell in item["cells"]
                                 if not all(word.isdecimal() for word in cell["text"].split())]
            else:
                extra = copy.deepcopy(label)
                extra["id"] = "attack-diagram"
                if attack != "duplicate":
                    extra.update(text="0F AA /r" if attack == "new-opcode" else "Note: unparsed constraint",
                                 rect=[100, label["rect"][1] - 15, 200, label["rect"][3] - 15])
                item["cells"].append(extra)
            result = analyze(item)["content"]
            self.assertEqual(result["tables"][0]["materialRegions"], [], attack)
            self.assertTrue(all(row["disposition"] == "unresolved" for row in result["oldGapDispositions"]), attack)

    def test_staggered_layout_columns_need_unique_nearby_complete_source_cells(self):
        item = fixture("cvtps2pi")
        lines = item["layoutPage"].splitlines()
        groups = geometry.physical_lines(item["cells"])
        matched = geometry.exact_source_line(groups, lines, 21)
        self.assertEqual(geometry.source_ids(matched), ["pdf:40:cell:19", "pdf:40:cell:22"])
        self.assertIsNone(geometry.staggered_source_line(groups, lines[21].replace("CVTPS2PI", "CVTUNKNOWN")))
        moved = copy.deepcopy(groups)
        next(group for group in moved if any(cell["id"] == "pdf:40:cell:22" for cell in group["cells"]))["cells"][0]["rect"][1] -= 10
        self.assertIsNone(geometry.staggered_source_line(moved, lines[21]))

    def test_actual_wrapped_3dnow_encoding_retains_both_explicit_opcode_parts(self):
        for name, cells, gap_count in (("pfacc", ["pdf:122:cell:21", "pdf:122:cell:22"], 3),
                                       ("pf2id", ["pdf:118:cell:23", "pdf:118:cell:24"], 1)):
            result = analyze(fixture(name))["content"]
            self.assertEqual(result["rows"][0]["encodingCells"], cells)
            self.assertEqual(result["rows"][0]["status"], "explicit-wrapped-3dnow-encoding-row")
            self.assertTrue(all(row["rule"] == "single-mnemonic-wrapped-3dnow-encoding/v2"
                                for row in result["oldGapDispositions"][:gap_count]))

    def test_wrapped_3dnow_encoding_rejects_byte_omission_extra_cell_and_wrong_column(self):
        for attack in ("omitted", "duplicate", "wrong-column", "wrong-prefix", "wrong-owner", "second-head"):
            item = fixture("pfacc")
            suffix = next(cell for cell in item["cells"] if cell["id"] == "pdf:122:cell:22")
            if attack == "omitted":
                item["cells"].remove(suffix)
            elif attack == "duplicate":
                duplicate = copy.deepcopy(suffix)
                duplicate["id"] = "attack-duplicate-suffix"
                item["cells"].append(duplicate)
            elif attack == "wrong-column":
                suffix["rect"][0] += 10
                suffix["rect"][2] += 10
            elif attack == "wrong-prefix":
                next(cell for cell in item["cells"] if cell["id"] == "pdf:122:cell:21")["text"] = "0F 38 /r"
            elif attack == "wrong-owner":
                item["baseline"]["entries"][0]["title"] = "PFADD"
            else:
                extra = copy.deepcopy(suffix)
                extra.update(id="attack-second-head", text="PFACC mmx1, mmx2/mem64", rect=[69, 406.5, 201, 415.7])
                item["cells"].append(extra)
            result = analyze(item)["content"]
            self.assertFalse(any(row.get("wrappedEncodingCells") for row in result["rows"]), attack)
            self.assertTrue(all(row["disposition"] == "unresolved" for row in result["oldGapDispositions"][:3]), attack)

    def test_orphan_operand_cannot_attach_without_source_owned_head(self):
        item = fixture("addpd")
        item["cells"] = [cell for cell in item["cells"] if cell["id"] != "pdf:78:cell:35"]
        result = analyze(item)["content"]["oldGapDispositions"]
        self.assertEqual(result[0]["disposition"], "unresolved")
        self.assertEqual(result[-1]["disposition"], "justified-continuation")

    def test_far_or_wrong_column_operand_is_unresolved(self):
        for axis, change in ((0, 60), (1, 12)):
            item = fixture("addpd")
            cell = next(cell for cell in item["cells"] if cell["id"] == "pdf:78:cell:36")
            cell["rect"][axis] += change
            cell["rect"][axis + 2] += change
            self.assertEqual(analyze(item)["content"]["oldGapDispositions"][0]["disposition"], "unresolved")

    def test_unknown_intervening_line_breaks_operand_continuity(self):
        item = fixture("addpd")
        cell = copy.deepcopy(next(cell for cell in item["cells"] if cell["id"] == "pdf:78:cell:36"))
        cell.update(id="attack-orphan-line", text="unparsed source construct", rect=[82.98, 305, 180, 316])
        item["cells"].append(cell)
        self.assertEqual(analyze(item)["content"]["oldGapDispositions"][0]["disposition"], "unresolved")

    def test_repeated_headers_need_equal_occurrences_and_neighbor_anchors(self):
        groups = [group("before", 0), group("Mnemonic Encoding", 10), group("VEX Opcode", 20),
                  group("row", 30), group("Mnemonic Encoding", 40), group("EVEX Opcode", 50)]
        lines = ["before", "Mnemonic Encoding", "VEX Opcode", "row", "Mnemonic Encoding", "EVEX Opcode"]
        self.assertEqual(geometry.exact_source_line(groups, lines, 1)["y"], 10)
        self.assertEqual(geometry.exact_source_line(groups, lines, 4)["y"], 40)
        self.assertIsNone(geometry.exact_source_line(groups[:-2] + groups[-1:], lines, 4))
        crossed = copy.deepcopy(groups)
        crossed[2]["y"] = 5
        self.assertIsNone(geometry.exact_source_line(crossed, lines, 1))

    def test_overprinted_source_geometry_is_ambiguous(self):
        item = fixture("addpd")
        duplicate = copy.deepcopy(next(cell for cell in item["cells"] if cell["id"] == "pdf:78:cell:36"))
        duplicate["id"] = "overprint"
        item["cells"].append(duplicate)
        self.assertEqual(analyze(item)["content"]["oldGapDispositions"][0]["disposition"], "unresolved")

    def test_wrong_page_or_historical_line_digest_is_rejected(self):
        item = fixture("addpd")
        item["baseline"]["gaps"][0]["source"]["textSha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "historical gap source/line"):
            analyze(item)

    def test_resealed_output_omissions_cannot_suppress_gap_cells_or_owners(self):
        expected = analyze(fixture("addpd"))
        geometry.validate_output(expected, expected)
        for change in ("gap", "source-cell", "owner", "rectangle"):
            changed = copy.deepcopy(expected)
            if change == "gap":
                changed["content"]["oldGapDispositions"].pop()
            elif change == "source-cell":
                changed["content"]["sourceCells"].pop()
            elif change == "owner":
                changed["content"]["rows"][0]["entryId"] = "wrong-source-owner"
            else:
                changed["content"]["sourceCells"][0]["rect"][0] += 1
            changed["contentSha256"] = geometry.digest(changed["content"])
            with self.assertRaisesRegex(ValueError, "source reconstruction"):
                geometry.validate_output(changed, expected)

    def test_gap_stable_identity_retains_identical_original_obligations(self):
        gap = fixture("cmov")["baseline"]["gaps"][0]
        first = geometry.old_gap_id("24594", 0, gap)
        self.assertEqual(first, geometry.old_gap_id("24594", 0, copy.deepcopy(gap)))
        self.assertNotEqual(first, geometry.old_gap_id("24594", 1, gap))
        self.assertNotEqual(first, geometry.old_gap_id("26568", 0, gap))

    def test_geometry_preserves_xml_invalid_source_control_scalar(self):
        xml = '<doc><page width="200" height="100"><line><word xMin="10" yMin="20" xMax="30" yMax="30">x\x03y</word></line></page></doc>'
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bbox.html"
            path.write_text(xml)
            pages = geometry.read_geometry(path)
            cell = pages[0]["cells"][0]
            self.assertEqual(cell["text"], "x\x03y")
            self.assertEqual(cell["unicodeSha256"], hashlib.sha256(b"x\x03y").hexdigest())
            self.assertEqual(cell["wordSpan"], [0, 1])
            self.assertIsNone(cell["glyphSpan"])
            path.write_text(xml.replace('xMax="30"', 'xMax="9"'))
            with self.assertRaisesRegex(ValueError, "word geometry"):
                geometry.read_geometry(path)

    def test_every_source_page_has_an_explicit_unresolved_region(self):
        outline = dict(pages=4, outline=[dict(title="Prefix rules", pdfPage=1),
                                        dict(title="Instruction Reference", pdfPage=2),
                                        dict(title="Appendix maps", pdfPage=4)])
        regions = geometry.region_accounting(outline, [dict(id="entry", pdfPage=2, pdfEndPage=3)])
        self.assertEqual([row["pdfPage"] for row in regions], [1, 2, 3, 4])
        self.assertEqual(regions[-1]["outlineOwners"], ["Appendix maps"])
        self.assertTrue(all(row["geometryAccounted"] for row in regions))
        self.assertFalse(any(row["allConstraintsParsed"] for row in regions))
        self.assertIn("global-rules", regions[0]["status"])

    def test_cross_page_ownership_alone_cannot_create_table_continuation(self):
        item = fixture("cmov")
        second = copy.deepcopy(item["baseline"]["tables"][0])
        second.update(id="next-table", pdfPage=201)
        second["headerLine"] = 1
        item["baseline"]["tables"].append(second)
        layout = [""] * 201
        layout[199] = item["layoutPage"]
        layout[200] = "Mnemonic Opcode Description"
        tables, _, _ = geometry.table_geometry(item["baseline"], layout,
                                               [dict(pdfPage=200, cells=item["cells"]), dict(pdfPage=201, cells=[])])
        self.assertEqual(len(tables[0]["continuations"]), 1)
        self.assertTrue(tables[0]["continuations"][0]["status"].startswith("unresolved:"))

    def test_all_five_global_region_products_reject_omission_and_geometry_drift(self):
        # Synthetic transport controls; these are never qualification products.
        candidate = json.loads((ROOT / "tests/bap/fixtures/amd64-semantics/source-corpus-v2.lock.json").read_text())
        with tempfile.TemporaryDirectory() as temp:
            work = Path(temp)
            for row in candidate["documents"]:
                row["pdfPages"] = 1
            lock = work / "lock.json"
            lock.write_text(json.dumps(candidate))
            products = dict(schema="ariadne.amd64-source-corpus-products/v2",
                            corpusSha256=geometry.digest(candidate), extractor=candidate["extractor"],
                            requiredPublications=[row["publication"] for row in candidate["documents"]],
                            reproducedPublications=[])
            for row in candidate["documents"]:
                directory = work / row["publication"]
                directory.mkdir()
                (directory / "bbox.html").write_text('<doc><page width="200" height="100"></page></doc>')
                (directory / "layout.txt").write_text("Global source rule\n\f")
                (directory / "outline.json").write_text(json.dumps(dict(pages=1, outline=[dict(title="Global rules", pdfPage=1)])))
                products["reproducedPublications"].append(dict(publication=row["publication"], pdfSha256=row["pdfSha256"],
                    products={name: geometry.sha_file(directory / name) for name in ("bbox.html", "layout.txt", "outline.json")}))
            manifest = work / "products.json"
            manifest.write_text(json.dumps(products))
            good = geometry.audit_regions(work, lock)
            self.assertEqual(good["counts"]["documents"], 5)
            self.assertEqual(good["counts"]["requiredRegionClauses"], 11)
            self.assertFalse(good["acceptance"]["c2Complete"])
            self.assertFalse(good["acceptance"]["sourceCompletenessEstablished"])
            omitted = copy.deepcopy(products)
            omitted["reproducedPublications"].pop(0)
            manifest.write_text(json.dumps(omitted))
            with self.assertRaisesRegex(ValueError, "omits/duplicates"):
                geometry.audit_regions(work, lock)
            manifest.write_text(json.dumps(products))
            (work / candidate["documents"][0]["publication"] / "bbox.html").write_text("omitted geometry")
            with self.assertRaisesRegex(ValueError, "product identity"):
                geometry.audit_regions(work, lock)

    def test_source_manifest_cannot_change_required_scope_with_resealed_digest(self):
        candidate = json.loads((ROOT / "tests/bap/fixtures/amd64-semantics/source-corpus-v2.lock.json").read_text())
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            lock = directory / "lock.json"
            lock.write_text(json.dumps(candidate))
            products = dict(schema="ariadne.amd64-source-corpus-products/v2", corpusSha256=geometry.digest(candidate),
                            extractor=candidate["extractor"], requiredPublications=["24594", "26568", "26569"])
            (directory / "products.json").write_text(json.dumps(products))
            with self.assertRaisesRegex(ValueError, "candidate lock"):
                geometry.verified_corpus_products(directory, lock)


if __name__ == "__main__":
    unittest.main()
