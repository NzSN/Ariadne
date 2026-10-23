#!/usr/bin/env python3
"""Replay bounded AMD publisher adjudications without adopting a new corpus.

The reviewed input contains small actual source cells, not prior passing flags.
Every invocation rechecks PDF identity and reproduces text/geometry/outline with
the pinned extraction runtime. Old transcription and legal-domain authority are
separate: these corrections neither replace old locks nor implement semantics.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import urlparse

import amd64_manual_geometry as geometry
import amd64_source_corpus as corpus
from amd64_inventory_xed import canonical, digest
from run_output import run_output

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "tests/bap/fixtures/source-authority/adjudications-v1.json"
SCHEMA = "ariadne.amd64-source-authority-input/v1"
CELL_FIELDS = {"id", "pdfPage", "rect", "wordSpan", "wordBoxesSha256", "unicodeSha256", "text"}
ISSUES = {"vaddpd-evex128-operand", "vpmovmskb-mnemonic", "vpmovzxwd-vex-field",
          "sha256msg2-mnemonic", "vpmadcswd-mnemonic"}


def require(value, message):
    if not value:
        raise ValueError(message)


def fields(value, names, label):
    require(isinstance(value, dict) and set(value) == set(names), "unexpected " + label + " fields")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def authority_sources():
    """Current dependency closure for the caller's source-bound execution seal."""
    paths = set(geometry.extractor_sources()) | {
        "tools/amd64_source_authority.py", str(INPUT.relative_to(ROOT)),
        "tools/amd64_manual_outline.js",
        "tests/bap/fixtures/amd64-semantics/source-corpus-v2.lock.json",
        "tests/bap/fixtures/amd64-semantics/manual-inventory.lock.json",
        "tests/bap/fixtures/amd-manuals.lock.json",
    }
    return {path: sha(ROOT / path) for path in sorted(paths)}


def _manifest(value):
    fields(value, {"schema", "oldSource", "extractorLock", "sources", "issues"}, "authority input")
    require(value["schema"] == SCHEMA, "unsupported authority input schema")
    # Only the maintained reviewed source input is admitted. A caller cannot
    # promote a new URL/hash pair by resealing an arbitrary proof JSON file.
    require(canonical(value) == canonical(json.loads(INPUT.read_text())), "unreviewed authority input")
    fields(value["oldSource"], {"publication", "revision", "pdfSha256"}, "old source")
    fields(value["extractorLock"], {"path", "sha256"}, "extractor lock")
    require(value["extractorLock"]["path"] == "tests/bap/fixtures/amd64-semantics/source-corpus-v2.lock.json",
            "unexpected extractor lock")
    require(sha(ROOT / value["extractorLock"]["path"]) == value["extractorLock"]["sha256"], "extractor lock drift")
    require({issue["id"] for issue in value["issues"]} == ISSUES and len(value["issues"]) == 5,
            "missing or duplicate source issue")
    require(len(value["sources"]) == len({source["id"] for source in value["sources"]}), "duplicate authority source")
    for source in value["sources"]:
        fields(source, {"id", "publication", "revision", "officialUrl", "pdf", "products"}, "source")
        fields(source["pdf"], {"filename", "sha256", "bytes"}, "PDF")
        fields(source["products"], {"layout", "geometry", "outline"}, "products")
        url = urlparse(source["officialUrl"])
        require(url.scheme == "https" and url.netloc == "docs.amd.com"
                and url.path.startswith("/api/khub/documents/") and url.path.endswith("/content")
                and not url.query and not url.fragment, "nonpublisher source URL")
        for product in source["products"].values():
            fields(product, {"filename", "sha256"}, "product")
    for issue in value["issues"]:
        fields(issue, {"id", "oldRecords", "oldCells", "anchors"}, "issue")
        for record in issue["oldRecords"]:
            fields(record, {"oldGapId", "ordinal", "originalGapSha256", "originalGap", "headCells", "encodingCells"}, "old record")
        for cell in issue["oldCells"]:
            fields(cell, CELL_FIELDS, "old cell")
        for references in issue["anchors"].values():
            require(isinstance(references, list) and references, "empty source anchor")
            for reference in references:
                fields(reference, {"source", "cell"}, "source anchor")
                fields(reference["cell"], CELL_FIELDS, "source cell")
    return value


def _local(root, filename):
    require(Path(filename).name == filename, "source filename must be a basename")
    path = root / filename
    require(not path.is_symlink() and path.resolve().is_relative_to(root.resolve()), "source path escapes root")
    return path


def _reproduce(value, root):
    """Recheck tools and fresh PDF-derived products; return source cells only."""
    lock = corpus.strict_json((ROOT / value["extractorLock"]["path"]).read_bytes())
    executables = {"pdftotext": ROOT / "target/rep-pdf-tools/root/usr/bin/pdftotext",
                   "mutool": ROOT / "target/rep-pdf-tools/root/usr/bin/mutool", "python": Path(sys.executable)}
    missing = [name for name, executable in executables.items() if not executable.is_file()]
    require(not missing, "missing pinned extraction runtime: " + ", ".join(missing))
    env = corpus.environment(ROOT / "target/rep-pdf-tools/root/usr/lib/x86_64-linux-gnu")
    corpus.check_runtime(lock, executables, env)
    wanted = {}
    for issue in value["issues"]:
        for references in issue["anchors"].values():
            for reference in references:
                wanted.setdefault(reference["source"], set()).add(reference["cell"]["pdfPage"])
    checked = {}
    for source in value["sources"]:
        pdf = _local(root, source["pdf"]["filename"])
        require(pdf.stat().st_size == source["pdf"]["bytes"] and sha(pdf) == source["pdf"]["sha256"], "source PDF bytes differ")
        require(pdf.open("rb").read(5) == b"%PDF-", "source is not PDF")
        for product in source["products"].values():
            require(sha(_local(root, product["filename"])) == product["sha256"], "source product drift")
        with tempfile.TemporaryDirectory(prefix="authority-replay-", dir=root) as temporary:
            work = Path(temporary)
            for kind in ("layout", "geometry"):
                command = lock["extractor"]["commands"][kind]
                output = work / source["products"][kind]["filename"]
                args = [str(executables[command[0]])] + [str(pdf.resolve()) if part == "{pdf}" else
                        str(output) if part == "{output}" else part for part in command[1:]]
                subprocess.run(args, env=env, check=True, capture_output=True, timeout=180)
                require(sha(output) == source["products"][kind]["sha256"], "fresh source extraction differs")
            output = work / source["products"]["outline"]["filename"]
            with output.open("wb") as stream:
                subprocess.run([str(executables["mutool"]), "run", str(ROOT / "tools/amd64_manual_outline.js"), str(pdf.resolve())],
                               env=env, stdout=stream, stderr=subprocess.PIPE, check=True, timeout=180)
            require(sha(output) == source["products"]["outline"]["sha256"], "fresh source outline differs")
            if source["id"] in wanted:
                pages = geometry.read_geometry(work / source["products"]["geometry"]["filename"])
                checked[source["id"]] = {cell["id"]: cell for page in pages if page["pdfPage"] in wanted[source["id"]]
                                         for cell in page["cells"]}
    return checked


def _facts(issue, checked):
    facts = {}
    for role, references in issue["anchors"].items():
        selected = []
        for reference in references:
            actual = checked.get(reference["source"], {}).get(reference["cell"]["id"])
            require(actual is not None, "missing source anchor")
            require({key: actual[key] for key in CELL_FIELDS} == reference["cell"], "source anchor content/geometry differs")
            selected.append(actual)
        require(len({cell["id"] for cell in selected}) == len(selected), "duplicate source anchor")
        facts[role] = selected
    return facts


def _one(facts, role, text=None):
    require(role in facts and len(facts[role]) == 1, "missing unique " + role)
    cell = facts[role][0]
    require(text is None or cell["text"] == text, "unexpected " + role)
    return cell


def _row(head, cells):
    require(all(cell["pdfPage"] == head["pdfPage"] and abs(cell["rect"][1] - head["rect"][1]) <= 1.2 for cell in cells),
            "source row baseline mismatch")
    ordered = [head] + cells
    require(all(left["rect"][2] < right["rect"][0] for left, right in zip(ordered, ordered[1:])), "source row column order")


def _continuation(head, tail, max_baseline=18):
    require(tail["pdfPage"] == head["pdfPage"]
            and 0 < tail["rect"][1] - head["rect"][1] <= max_baseline
            and head["rect"][0] - 1 <= tail["rect"][0] < head["rect"][2],
            "source continuation page, baseline or column mismatch")


def _one_source(issue, roles):
    require(len({reference["source"] for role in roles for reference in issue["anchors"][role]}) == 1,
            "source proof relation crosses publications")


def _map(facts, kind, map_number, high, low, pp, mnemonic, operands):
    title = _one(facts, "mapTitle")
    require(title["text"].startswith(f"{kind} Opcode Map {map_number}"), "opcode map selection")
    low_cell = _one(facts, "mapLow", "x" + low)
    high_cell = _one(facts, "mapHigh", high + "x")
    prefix = _one(facts, "mapPrefix", pp)
    name = _one(facts, "mapName", mnemonic)
    operand = _one(facts, "mapOperands", operands)
    require(len({cell["pdfPage"] for cell in (title, low_cell, high_cell, prefix, name, operand)}) == 1,
            "map anchors cross pages")
    center = (low_cell["rect"][0] + low_cell["rect"][2]) / 2
    require(name["rect"][0] < center < name["rect"][2]
            and operand["rect"][0] < center < operand["rect"][2], "map column does not contain named operation")
    require(title["rect"][1] < low_cell["rect"][1] < name["rect"][1]
            and abs(high_cell["rect"][1] - name["rect"][1]) < 20
            and abs(prefix["rect"][1] - name["rect"][1]) < 12
            and 0 < operand["rect"][1] - name["rect"][1] < 12
            and prefix["rect"][2] < high_cell["rect"][0] < name["rect"][0], "map row/prefix geometry")


def _adjudicate(value, old_source_bundle, checked):
    """Pure proof replay, also exercised with damaged actual-source controls."""
    source = value["oldSource"]
    old = old_source_bundle.get(source["publication"])
    require(old is not None and old["publication"] == source["publication"]
            and old["revision"] == source["revision"] and old["pdfSha256"] == source["pdfSha256"], "old source identity")
    records = old["content"]["oldGapDispositions"]
    require(len(records) == len({record["oldGapId"] for record in records}), "duplicate old gap identity")
    record_map = {record["oldGapId"]: record for record in records}
    cells = old["content"]["sourceCells"]
    require(len(cells) == len({cell["id"] for cell in cells}), "duplicate old source cell")
    old_cells = {cell["id"]: cell for cell in cells}
    sources = {item["id"]: item for item in value["sources"]}
    result = {}
    for issue in value["issues"]:
        for expected in issue["oldCells"]:
            actual = old_cells.get(expected["id"])
            require(actual is not None and {key: actual[key] for key in CELL_FIELDS} == expected, "old literal or geometry changed")
        rows = []
        for expected in issue["oldRecords"]:
            record = record_map.get(expected["oldGapId"])
            require(record is not None and record["disposition"] == "source-conflict", "missing immutable conflict")
            require(record["ordinal"] == expected["ordinal"]
                    and record["originalGap"] == expected["originalGap"]
                    and digest(record["originalGap"]) == expected["originalGapSha256"]
                    and geometry.old_gap_id(source["publication"], record["ordinal"], record["originalGap"]) == expected["oldGapId"],
                    "old gap identity/content differs")
            require(record["evidence"]["headCells"] == expected["headCells"]
                    and record["evidence"]["encodingCells"] == expected["encodingCells"], "old row binding differs")
            require(set(expected["headCells"] + expected["encodingCells"]) <= set(record["cells"]), "old row cells absent")
            head = [old_cells[key]["text"] for key in expected["headCells"]]
            require(len(head) == 1, "old mnemonic ambiguity")
            encoding = sorted((old_cells[key] for key in expected["encodingCells"]), key=lambda cell: (cell["rect"][0], cell["rect"][1]))
            rows.append((record, head[0], [cell["text"] for cell in encoding]))
        facts = _facts(issue, checked)
        name = issue["id"]
        if name == "vaddpd-evex128-operand":
            require(set(facts) == {"newHead", "newOperand", "newEncoding"}, "VADDPD proof roles")
            _one_source(issue, facts)
            head = _one(facts, "newHead", "VADDPD xmm1 {k}{z}, xmm2,")
            operand = _one(facts, "newOperand", "xmm3/mem128/mem64bcst")
            _continuation(head, operand, 12)
            _row(head, facts["newEncoding"])
            encoding = [cell["text"] for cell in facts["newEncoding"]]
            require(encoding == ["62", "RXBR'.1", "1.vvvv.01", "z.00.b.V'.aaa", "58 /r"]
                    and len(rows) == 2 and all(old_head == "VADDPD xmm1 {k}{z}," and code == encoding for _, old_head, code in rows),
                    "VADDPD revision does not preserve the affected encoding")
            require(any(cell["text"] == "xmmVGETEXPPD2," for cell in issue["oldCells"]), "missing original malformed operand")
            correction = dict(field="operand", literal="xmmVGETEXPPD2,", replacement="xmm2,")
            resolution = "corrected-in-publisher-revision"
        elif name == "sha256msg2-mnemonic":
            require(set(facts) == {"newHead", "newOpcode", "newDescription", "newSupport"}, "SHA proof roles")
            _one_source(issue, facts)
            head = _one(facts, "newHead", "SHA256MSG2 xmm1, xmm2/m128")
            opcode = _one(facts, "newOpcode", "0F 38 CD /r")
            description = _one(facts, "newDescription", "Calculate Message Intermediate 2")
            support = _one(facts, "newSupport", "SHA256MSG2")
            require(support["pdfPage"] == head["pdfPage"] and support["rect"][1] < head["rect"][1],
                    "SHA support belongs to another source section")
            _row(head, [opcode, description])
            require(len(rows) == 1 and rows[0][1:] == ("SHA256MSG1 xmm1, xmm2/m128", [opcode["text"]]), "SHA original row mismatch")
            correction = dict(field="mnemonic", literal="SHA256MSG1", replacement="SHA256MSG2")
            resolution = "corrected-in-publisher-revision"
        elif name in {"vpmovmskb-mnemonic", "vpmadcswd-mnemonic"}:
            require(set(facts) == {"mapTitle", "mapLow", "mapHigh", "mapPrefix", "mapName", "mapOperands"}, "map proof roles")
            _one_source(issue, facts)
            if name == "vpmovmskb-mnemonic":
                _map(facts, "VEX", "1,", "D", "7", "01", "VPMOVMSKB", "Gw, Ux")
                require(len(rows) == 2 and {(head, tuple(code)) for _, head, code in rows} == {
                    ("VMOVMSKB reg64, xmm1", ("C4", "RXB.01", "X.1111.0.01", "D7 /r")),
                    ("VMOVMSKB reg64, ymm1", ("C4", "RXB.01", "X.1111.1.01", "D7 /r"))}, "VPMOVMSKB map/encoding mismatch")
                correction = dict(field="mnemonic", literal="VMOVMSKB", replacement="VPMOVMSKB")
            else:
                _map(facts, "XOP", "8h,", "B", "6", "00", "VPMADCSWD", "Vo,Ho,Wo,Lo")
                require(len(rows) == 1 and rows[0][1:] == ("PMADCSWD xmm1, xmm2, xmm3/mem128, xmm4",
                        ["8F", "RXB.08", "0.src1.0.00", "B6 /r ib"]), "VPMADCSWD map/encoding mismatch")
                correction = dict(field="mnemonic", literal="PMADCSWD", replacement="VPMADCSWD")
            resolution = "adjudicated-by-publisher-encoding-map"
        elif name == "vpmovzxwd-vex-field":
            require(set(facts) == {"newHead", "newPrefix", "newField", "newOpcode", "newFieldHeader", "exceptionHeading", "vvvvConstraint", "lengthRule"}, "VEX field proof roles")
            _one_source(issue, set(facts) - {"lengthRule"})
            _one_source(issue, {"lengthRule"})
            head = _one(facts, "newHead", "VPMOVZXWD ymm1, xmm2/mem128")
            require([cell["text"] for cell in facts["newPrefix"]] == ["C4", "RXB.02"]
                    and [cell["text"] for cell in facts["newField"]] == ["X.1323r33111.", "1.01"], "changed VEX source field")
            opcode = _one(facts, "newOpcode", "33 /r")
            _row(head, facts["newPrefix"] + [facts["newField"][0], opcode])
            _continuation(*facts["newField"], max_baseline=12)
            header = _one(facts, "newFieldHeader", "VEX RXB.map_select W.vvvv.L.pp Opcode")
            require(header["pdfPage"] == head["pdfPage"] and header["rect"][1] < head["rect"][1]
                    and header["rect"][0] <= facts["newPrefix"][0]["rect"][0]
                    and header["rect"][2] >= opcode["rect"][2], "foreign VEX field header")
            require([cell["text"] for cell in facts["exceptionHeading"]] == ["Exceptions", "Invalid opcode, #UD"], "missing invalid-opcode premise")
            constraint = _one(facts, "vvvvConstraint", "VEX.vvvv ! = 1111b.")
            exception, invalid = facts["exceptionHeading"]
            require(all(cell["pdfPage"] == head["pdfPage"] for cell in (exception, invalid, constraint))
                    and head["rect"][1] < exception["rect"][1] < invalid["rect"][1] < constraint["rect"][1]
                    and invalid["rect"][2] < constraint["rect"][0], "foreign VEX constraint")
            length = " ".join(cell["text"] for cell in facts["lengthRule"])
            require(len(facts["lengthRule"]) == 2
                    and facts["lengthRule"][0]["text"].startswith("VEX/XOP.L (Bit 2).")
                    and "L=1 specifies 256-bit vector length (YMM registers/256-bit memory locations)." in length
                    and len(rows) == 1 and rows[0][1:] == (head["text"], ["C4", "RXB.02", "X.1323r33111.", "1.01", "33 /r"]),
                    "VEX vector-length/source relation")
            _continuation(*facts["lengthRule"])
            correction = dict(field="W.vvvv.L.pp", literal="X.1323r33111. 1.01", replacement="X.1111.1.01")
            resolution = "adjudicated-by-explicit-publisher-field-constraints"
        else:
            raise ValueError("unknown authority rule")
        evidence = [dict(source=reference["source"], pdfSha256=sources[reference["source"]]["pdf"]["sha256"],
                         officialUrl=sources[reference["source"]]["officialUrl"], **reference["cell"])
                    for references in issue["anchors"].values() for reference in references]
        for record, _, _ in rows:
            require(record["oldGapId"] not in result, "duplicate adjudication")
            result[record["oldGapId"]] = dict(resolution=resolution, issueId=name, correction=correction,
                evidenceCells=evidence, sourceAuthorityBound=True, corpusAdoption=False,
                legalDomainComplete=False, constraintsParsed=False, originalSourceRetained=True)
    return result


def validate_adjudications(old_source_bundle, source_inputs):
    """Validate reviewed inputs and compute one result per immutable old gap ID."""
    fields(source_inputs, {"manifest", "root"}, "source inputs")
    value = _manifest(source_inputs["manifest"])
    root = run_output(source_inputs["root"])
    require(root.is_dir(), "missing source-authority work directory")
    before = authority_sources()
    result = _adjudicate(value, old_source_bundle, _reproduce(value, root))
    require(authority_sources() == before, "authority implementation/source input drift")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-geometry", required=True, type=Path)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--inputs", type=Path, default=INPUT)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = run_output(args.output)
    old = corpus.strict_json(args.old_geometry.read_bytes())
    result = validate_adjudications({old["publication"]: old},
        dict(manifest=corpus.strict_json(args.inputs.read_bytes()), root=args.source_dir))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(canonical(dict(schema="ariadne.amd64-source-adjudications/v1", records=result,
                                         corpusAdoption=False, sources=authority_sources())) + b"\n")
    print(json.dumps({"adjudications": len(result), "corpusAdoption": False}))


if __name__ == "__main__":
    main()
