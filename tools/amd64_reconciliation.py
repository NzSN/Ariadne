#!/usr/bin/env python3
"""Bidirectional finite source/XED relations with every wider domain left open.

The two MOV8 relations prove only membership of their reviewed finite points.
No translation of XED's complete prefix grammar is implemented. All frozen
long-mode candidates, including these two, retain a full-domain obligation.
"""
import argparse
from pathlib import Path

import amd64_inventory as inventory_tool
from amd64_domains import (ROOT, MOV8_FORMS, MEMORY_FORMS, MEMORY_SCHEMA, canonical, digest,
                           fields, read, require, sha, validate_mov8_domain,
                           validate_memory_mov8_domain, decode_memory_mov8)
from run_output import run_output

SCHEMA = "ariadne.amd64-template-relations/v1"
WORKLIST = "ariadne.amd64-domain-reconciliation/v1"
XED_LOCK = "tests/bap/fixtures/amd64-semantics/inventory.lock.json"
MOV8_CANDIDATES = {
    "mov8-register-88": "xed:fbf4d5ee2e910cb571d6336c65078f0c9771b337d9174e52f11dc930f304c795:1",
    "mov8-register-8a": "xed:cdbff980cfe27f2447fd04d5f0dc9a9414714d015d0ff265254217927d87fe9b:1",
}
PATTERNS = {
    "mov8-register-88": "0x88 MOD[0b11] MOD=3 REG[rrr] RM[nnn]",
    "mov8-register-8a": "0x8A MOD[0b11] MOD=3 REG[rrr] RM[nnn]",
}
OPERANDS = {
    "mov8-register-88": "REG0=GPR8_B():w REG1=GPR8_R():r",
    "mov8-register-8a": "REG0=GPR8_R():w REG1=GPR8_B():r",
}
MEMORY_CANDIDATES = {
    "mov8-memory-store-88": "xed:0dbf63812e034614081608a43038fa54efc2448bc96770c3bb38a4c7c2d4644c:1",
    "mov8-memory-load-8a": "xed:f44bf67b38fc1f2fafc876a5db2d02394a2e22ed808f94b860723e1603c72f11:1",
}
MEMORY_PATTERNS = {name: f"0x{opcode.upper()} MOD[mm] MOD!=3 REG[rrr] RM[nnn] MODRM()"
                   for name, opcode in MEMORY_FORMS.items()}
MEMORY_OPERANDS = {"mov8-memory-store-88": "MEM0:w:b REG0=GPR8_R():r",
                   "mov8-memory-load-8a": "REG0=GPR8_R():w MEM0:r:b"}


def validate_relation_claims(document, points, relations, xed, *, root=ROOT):
    """Validate the finite relationships; caller separately pins full XED input."""
    memory = document.get("schema") == MEMORY_SCHEMA
    source_key = "sourcePacksSha256" if memory else "sourcePackSha256"
    source_digest = digest(document["sourcePacks"]) if memory else document["sourcePack"]["sha256"]
    form_opcodes = MEMORY_FORMS if memory else MOV8_FORMS
    candidate_ids = MEMORY_CANDIDATES if memory else MOV8_CANDIDATES
    patterns, operands = (MEMORY_PATTERNS, MEMORY_OPERANDS) if memory else (PATTERNS, OPERANDS)
    fields(relations, {"schema", "domainSha256", source_key, "xedLockSha256", "xedRecordsSha256", "relations", "sourceOnlyObligations"}, "template relations")
    require(relations["schema"] == ("ariadne.amd64-template-relations/v2" if memory else SCHEMA)
            and relations["domainSha256"] == digest(document)
            and relations[source_key] == source_digest
            and relations["xedLockSha256"] == sha(Path(root) / XED_LOCK)
            and relations["xedRecordsSha256"] == xed["recordsSha256"], "stale source/domain/XED relations")
    require(isinstance(relations["relations"], list) and isinstance(relations["sourceOnlyObligations"], list), "relation arrays")
    forms = {form["id"]: form for form in document["forms"]}
    candidates = {row["id"]: row for row in xed["records"]}
    require(len(candidates) == len(xed["records"]), "duplicate XED candidate")
    seen, covered, source_only, links = set(), set(), {}, {}
    for relation in relations["relations"]:
        fields(relation, {"id", "form", "candidate", "kind", "sourceRule", "candidateRemainder", "completeTemplateDomain"}, "finite relation")
        name, candidate = relation["form"], relation["candidate"]
        require(isinstance(relation["id"], str) and relation["id"] and relation["id"] not in seen, "duplicate relation identity")
        seen.add(relation["id"])
        require(name in forms and name not in covered and candidate in candidates and candidate == candidate_ids.get(name), "orphan/duplicate/wrong MOV8 relation")
        require(relation["kind"] == "partial-finite-domain" and relation["completeTemplateDomain"] is False
                and relation["candidateRemainder"] == "unresolved"
                and relation["sourceRule"] == "mov8-direction-" + form_opcodes[name]
                and relation["sourceRule"] in forms[name]["sourceRules"], "finite witness cannot promote complete symbolic domain")
        row = candidates[candidate]
        require(64 in row["modeDomain"] and row["source"]["pattern"] == patterns[name]
                and row["source"]["operands"] == operands[name], "candidate opcode/ModRM/operand direction differs")
        selected = [point for point in points if point["form"] == name]
        require(bool(selected), "empty related finite domain")
        for point in selected:
            if memory:
                decoded = decode_memory_mov8(point["bytes"])
                require(decoded["operation"] == ("store" if form_opcodes[name] == "88" else "load")
                        and decoded["addressBits"] == point["environment"]["addressBits"],
                        "finite memory point differs from related candidate")
                continue
            code = bytes.fromhex(point["bytes"])
            require(len(code) in {2, 3} and code[-2] == int(MOV8_FORMS[name], 16)
                    and code[-1] & 0xc0 == 0xc0 and (len(code) == 2 or code[0] in {0x40, 0x41, 0x44, 0x45}),
                    "finite point is not a member of restricted candidate pattern")
        covered.add(name)
        links[candidate] = dict(form=name, relation=relation["id"], finitePoints=len(selected),
                               candidateRemainder="unresolved", completeTemplateDomain=False)
    for obligation in relations["sourceOnlyObligations"]:
        fields(obligation, {"form", "status", "reason"}, "source-only obligation")
        name = obligation["form"]
        require(name in forms and name not in covered and name not in source_only
                and obligation["status"] == "unresolved-template-relation"
                and isinstance(obligation["reason"], str) and obligation["reason"], "source-only obligation identity/status")
        source_only[name] = obligation
    require(covered | set(source_only) == set(forms), "manual legal form omitted from bidirectional accounting")
    return links, source_only


def reconciliation_report(document, points, relations, xed, *, root=ROOT):
    """Pure report constructor; reconcile() supplies validated pinned inputs."""
    links, source_only = validate_relation_claims(document, points, relations, xed, root=root)
    candidate_rows, mode_excluded = [], []
    for row in xed["records"]:
        if 64 not in row["modeDomain"]:
            mode_excluded.append(dict(candidate=row["id"], modeDomain=row["modeDomain"],
                                      disposition="explicit-upstream-mode-exclusion", vendorLegalityEstablished=False))
            continue
        relation = links.get(row["id"])
        candidate_rows.append(dict(candidate=row["id"], mnemonic=row["mnemonic"], iform=row["iform"],
            disposition="partial-finite-source-relation" if relation else "unresolved",
            relation=relation, candidateRemainder="unresolved", completeTemplateDomain=False,
            authoritativeProfileBinding=False,
            remainingObligations=["complete-source-legality", "complete-prefix-and-environment-domain", "producer-consumer-binding"]))
    source_rows = []
    for form in document["forms"]:
        name = form["id"]
        matches = [key for key, link in links.items() if link["form"] == name]
        source_rows.append(dict(form=name, finitePoints=sum(point["form"] == name for point in points),
            candidateRelations=matches, disposition="finite-domain-related" if matches else "unresolved-template-relation",
            sourceOnlyObligation=source_only.get(name), unmatchedTemplateProducerDecoderObligation=not bool(matches),
            producerConsumerBindingEstablished=False,
            remainingObligations=["producer-consumer-binding", "whole-symbolic-domain-reconciliation"]))
    memory = document.get("schema") == MEMORY_SCHEMA
    identities = dict(domainSha256=digest(document), relationsSha256=digest(relations), xedRecordsSha256=xed["recordsSha256"])
    identities.update({"sourcePacksSha256": digest(document["sourcePacks"])} if memory else
                      {"sourcePackSha256": document["sourcePack"]["sha256"]})
    return dict(schema="ariadne.amd64-domain-reconciliation/v2" if memory else WORKLIST, inputs=identities,
        counts=dict(symbolicTemplates=len(xed["records"]), longModeCandidates=len(candidate_rows),
                    modeExcluded=len(mode_excluded), finiteLegalForms=len(source_rows), finitePoints=len(points),
                    partialCandidateRelations=len(links), sourceOnlyObligations=len(source_only),
                    candidateFullDomainBindings=0, remainingCandidateFullDomains=len(candidate_rows)),
        candidateWorklist=candidate_rows, sourceFormWorklist=source_rows, modeExclusions=mode_excluded,
        sourceComplete=False, vendorFullDenominator=False, fullDomainReconciliation=False, fullAmd64Coverage=False,
        proofMethod=("exact finite membership in two explicitly reviewed XED patterns; no SMT or complete XED-prefix/address/displacement translation"
                     if memory else "exact finite membership in two explicitly reviewed XED patterns; no SMT or complete XED-prefix translation"),
        absenceMeaning="No matching relation leaves a source obligation; incomplete manual domains never prove a candidate invalid.")


def reconcile(document, relations, xed, *, root=ROOT, budget=100000):
    root = Path(root)
    inventory_tool.validate_inventory(xed, inventory_tool.load_lock(root / XED_LOCK))
    validator = validate_memory_mov8_domain if document.get("schema") == MEMORY_SCHEMA else validate_mov8_domain
    points = validator(document, root=root, budget=budget)
    return reconciliation_report(document, points, relations, xed, root=root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--domain", type=Path, required=True)
    parser.add_argument("--relations", type=Path, required=True)
    parser.add_argument("--xed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-full", action="store_true")
    args = parser.parse_args()
    # The full pinned inventory exceeds the smaller reviewed-domain input cap.
    require(args.xed.stat().st_size <= inventory_tool.MAX_INVENTORY_BYTES, "XED inventory byte budget")
    xed = inventory_tool.strict_json(args.xed.read_bytes())
    result = reconcile(read(args.domain), read(args.relations), xed)
    output = run_output(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical(result) + "\n")
    print(canonical(result["counts"]))
    return 1 if args.require_full else 0


if __name__ == "__main__":
    raise SystemExit(main())
