#!/usr/bin/env python3
"""Preserve the source-owned XORPS mandatory-prefix disagreement."""
import copy

import amd64_p2_native64 as native
from amd64_inventory_xed import canonical, digest

entry = native.entry
require = entry.require
INPUT = native.INPUT.parent / "p2-media-prefix-question-v1.json"
PRECEDENCE_INPUT = INPUT.parent / "p2-media-source-precedence-v1.json"
XOR_FORMS_INPUT = INPUT.parent / "p2-xor-prefix-rows-v1.json"
QUESTION = "p2-c:xorps-legacy-prefix-disagreement"


def assess(pack, sources):
    require(set(pack) == {"schema", "sourcePolicySha256", "executionModes", "pages"} and
            pack["schema"] == "ariadne.amd64-media-prefix-question/v1" and
            pack["executionModes"] == ["long-64"] and
            pack["sourcePolicySha256"] == entry.migration.sha(native.adoption.INPUT), "media prefix question scope differs")
    wanted = {"map": ("24594", 571), "old-xorps": ("26568", 1614),
              "xorps": ("26568", 1822), "xorpd": ("26568", 1819)}
    require(set(sources) == set(pack["pages"]) == set(wanted), "media prefix source population differs")
    selected = {d["publication"]: d["pdfSha256"] for d in native.adoption.selected_documents()}
    predecessor = next(d["pdfSha256"] for d in entry.read(entry.migration.corpus.LOCK)["documents"] if d["publication"] == "26568")
    for key, (pub, number) in wanted.items():
        record, page = pack["pages"][key], sources[key]
        require(set(record) == {"publication", "pdfSha256", "pdfPage", "cellsSha256"} and
                record == dict(publication=pub, pdfSha256=predecessor if key == "old-xorps" else selected[pub],
                               pdfPage=number, cellsSha256=digest(page["cells"])) and page["pdfPage"] == number,
                "media prefix actual source identity differs: " + key)
        native.words(page)
    def cell(key, index, expected):
        page = sources[key]
        found = [c for c in page["cells"] if c["id"] == f'pdf:{page["pdfPage"]}:cell:{index}']
        require(len(found) == 1 and found[0]["text"] == expected, "media prefix literal differs")
        return found[0]
    observations = {
        "map-xorps": cell("map", 117, "XORPS"), "map-xorpd": cell("map", 125, "XORPD"),
        "map-none": cell("map", 185, "none"), "map-66": cell("map", 187, "66"),
        "old-mnemonic": cell("old-xorps", 7, "XORPS xmm1, xmm2/mem128"),
        "old-encoding": cell("old-xorps", 8, "66 0F 57 /r"),
        "mnemonic": cell("xorps", 5, "XORPS xmm1, xmm2/mem128"),
        "encoding": cell("xorps", 7, "66 0F 57 /r"),
        "other-mnemonic": cell("xorpd", 5, "XORPD xmm1, xmm2/mem128"),
        "other-encoding": cell("xorpd", 7, "66 0F 57 /r"),
    }
    # The two map names occupy the same opcode column and distinct prefix
    # bands. Bind those relations separately from the exact word/page digests.
    a, b = observations["map-xorps"], observations["map-xorpd"]
    none, prefix = observations["map-none"], observations["map-66"]
    require(abs(a["rect"][0] - b["rect"][0]) < 1 and a["rect"][0] > 500 and
            abs(a["rect"][1] - none["rect"][1]) < 6 and abs(b["rect"][1] - prefix["rect"][1]) < 6 and
            60 < none["rect"][0] < 90 and 60 < prefix["rect"][0] < 90,
            "media prefix map row/column ownership differs")
    return dict(schema="ariadne.amd64-media-prefix-question-assessment/v1", id=QUESTION,
                state="unresolved-source-interpretation", observations=copy.deepcopy(observations),
                interpretations=dict(mapXorps="0f57-without-mandatory-prefix", mapXorpd="66-0f57",
                                     instructionXorps="66-0f57", instructionXorpd="66-0f57"),
                sourceQuestion="Reconcile XORPS's legacy 66h literal with Table A-3, or explicitly select a conditional source-precedence hypothesis.",
                sourceCorrection=False, prefixAdmission=False, productionAdmission=False)


def selected_precedence():
    """The user's decision is specific to the two compared legacy forms."""
    source = next(d for d in native.adoption.selected_documents() if d["publication"] == "24594")
    return dict(schema="ariadne.amd64-media-source-precedence/v1",
                decision="user-selected-vol3-xorps-xorpd-2026-10-24",
                question=QUESTION, questionInputSha256=entry.migration.sha(INPUT),
                sourcePolicySha256=entry.migration.sha(native.adoption.INPUT), executionModes=["long-64"],
                authority=dict(publication="24594", revision=source["revision"], pdfSha256=source["pdfSha256"],
                               pdfPage=571, table="A-3", mnemonicCells=["pdf:571:cell:117", "pdf:571:cell:125"],
                               prefixCells=["pdf:571:cell:185", "pdf:571:cell:187"]),
                forms=[dict(selector=name+" xmm1, xmm2/mem128", mandatoryPrefix=prefix,
                            opcodeBytes=["0f", "57"], modrm="/r", dataBits=128,
                            prefixRole="opcode-selector;not-operand16", otherPrefixAdmission=False)
                       for name,prefix in (("XORPS", None), ("XORPD", "66"))],
                limits=dict(otherSourceQuestions="unchanged", vexEvex="separate-form-contracts",
                            featureAdmission="separate-instruction-owned-contract",
                            sourceLiterals="preserved", publisherCorrection=False, productionAdmission=False))


def project_current_scope(pack, sources, precedence):
    # Source reconstruction is mandatory even after a precedence decision.
    # A saved passing state or a supplied replacement observation is not proof.
    original = assess(pack, sources)
    require(canonical(precedence) == canonical(selected_precedence()),
            "unreviewed media source precedence/scope/form/authority")
    return dict(schema="ariadne.amd64-media-current-scope/v1", id=QUESTION,
                state="resolved-source-rule", resolutionBasis=precedence["decision"],
                originalAssessment=copy.deepcopy(original), originalAssessmentSha256=digest(original),
                selectedAuthority=copy.deepcopy(precedence["authority"]),
                currentForms=copy.deepcopy(precedence["forms"]),
                limits=copy.deepcopy(precedence["limits"]),
                precedenceInputSha256=entry.migration.sha(PRECEDENCE_INPUT),
                sourceCorrection=False, prefixAdmission=False, productionAdmission=False)


def xor_form_specs():
    """Independent source-row population for the two instruction-owned tables."""
    rows = []
    for family,page in (("XORPS",1822), ("XORPD",1819)):
        rows.append((family,page,"legacy",128,[5],[7]))
        rows.extend((family,page,"VEX",bits,[selector],fields) for bits,selector,fields in (
            (128,9,[28,29,26,27]), (256,10,[32,33,30,31])))
        rows.extend((family,page,"EVEX",bits,selectors,fields) for bits,selectors,fields in (
            (128,[14,15],[13,38,39,40,41]), (256,[16,17],[42,43,44,45,46]),
            (512,[18,19],[47,48,49,50,51])))
    return rows


def xor_form_contract(family, encoding, bits):
    require(family in ("XORPS", "XORPD") and (encoding,bits) in (
        ("legacy",128), ("VEX",128), ("VEX",256), ("EVEX",128), ("EVEX",256), ("EVEX",512)),
        "unreviewed XOR source form")
    pp = "00" if family == "XORPS" else "01"
    return dict(family=family, encoding=encoding, vectorBits=bits, opcodeMap="0f", opcode="57", modrm="/r",
                mandatoryPrefix=(None if family == "XORPS" else "66") if encoding == "legacy" else None,
                embeddedPp=None if encoding == "legacy" else pp,
                W=None if encoding == "legacy" else "X" if encoding == "VEX" else (0 if family == "XORPS" else 1),
                L=None if encoding != "VEX" else (0 if bits == 128 else 1),
                LL=None if encoding != "EVEX" else {128:"00",256:"01",512:"10"}[bits],
                broadcastElementBits=(32 if family == "XORPS" else 64) if encoding == "EVEX" else None,
                prefix66Role="opcode-selector;not-operand16",
                sourceRule="selected-vol3-precedence" if encoding == "legacy" else "instruction-owned-vol4-fields",
                extraPrefixAdmission=False)


def assess_xor_forms(pack, sources, precedence):
    selection = project_current_scope(entry.read(INPUT), sources, precedence)
    require(set(pack) == {"schema", "questionInputSha256", "precedenceInputSha256", "executionModes", "rows"} and
            pack["schema"] == "ariadne.amd64-xor-prefix-rows/v1" and pack["executionModes"] == ["long-64"] and
            pack["questionInputSha256"] == entry.migration.sha(INPUT) and
            pack["precedenceInputSha256"] == entry.migration.sha(PRECEDENCE_INPUT), "XOR prefix row source/scope differs")
    specs = xor_form_specs()
    require(len(pack["rows"]) == len(specs), "XOR source row omitted/duplicated")
    checked = []
    for record,(family,page,encoding,bits,selector_ids,encoding_ids) in zip(pack["rows"],specs):
        require(set(record) == {"publication", "pdfPage", "selectorCells", "encodingCells", "selector", "sourceEncoding", "properties"} and
                record["publication"] == "26568" and record["pdfPage"] == page and
                record["selectorCells"] == [f"pdf:{page}:cell:{i}" for i in selector_ids] and
                record["encodingCells"] == [f"pdf:{page}:cell:{i}" for i in encoding_ids] and
                canonical(record["properties"]) == canonical(xor_form_contract(family,encoding,bits)),
                "XOR prefix row form/owner/width/field contract differs")
        key = "xorps" if family == "XORPS" else "xorpd"
        cells = {c["id"]:c for c in sources[key]["cells"]}
        selector = " ".join(cells[k]["text"] for k in record["selectorCells"])
        fields = [cells[k]["text"] for k in record["encodingCells"]]
        require(selector == record["selector"] and " ".join(fields) == record["sourceEncoding"] and
                selector.startswith(("" if encoding == "legacy" else "V")+family+" "),
                "XOR instruction-owned selector/encoding literal differs")
        y = cells[record["selectorCells"][0]]["rect"][1]
        require(all(abs(cells[k]["rect"][1]-y) < .1 for k in record["encodingCells"]),
                "XOR prefix field physical row differs")
        pp = "00" if family == "XORPS" else "01"
        if encoding == "legacy":
            # Both raw legacy literals survive. Only XORPS's current rule
            # differs, through the independently reconstructed selection.
            require(fields == ["66 0F 57 /r"], "XOR original legacy literal changed")
            current = next(f for f in selection["currentForms"] if f["selector"] == selector)
            require(record["properties"]["mandatoryPrefix"] == current["mandatoryPrefix"], "XOR selected prefix differs")
        elif encoding == "VEX":
            require(fields == ["C4", "RXB.01", f'X.src1.{0 if bits == 128 else 1}.{pp}', "57 /r"],
                    "XOR VEX source fields differ")
        else:
            w = 0 if family == "XORPS" else 1
            require(fields == ["62", "RXBR'.1", f"{w}.vvvv.{pp}",
                               "z."+{128:"00",256:"01",512:"10"}[bits]+".b.V'.aaa", "57 /r"] and
                    f"/mem{32 if family == 'XORPS' else 64}bcst" in selector,
                    "XOR EVEX pp/W/length/broadcast fields differ")
        checked.append(dict(record, sourceCells=[copy.deepcopy(cells[k]) for k in record["selectorCells"]+record["encodingCells"]]))
    return dict(schema="ariadne.amd64-xor-prefix-row-assessment/v1", rows=checked,
                sourceRows=12, legacyRows=2, vexRows=4, evexRows=6,
                state="checked-two-instruction-source-row-inventory",
                legacyPrecedence=selection["resolutionBasis"], rawLiteralsPreserved=True,
                wholePrefixInventoryComplete=False, legalDomainsComplete=False, productionAdmission=False)
