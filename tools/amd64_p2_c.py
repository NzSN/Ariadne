#!/usr/bin/env python3
"""Proof-driven P2-C dispositions, separate from the full P2 exit.

Only checks executed against source pages may close an architectural reference.
Source-list interpretations preserve the historical disagreement and do not
assert publisher corrections or enable any production byte/semantic domain.
"""
import copy

import amd64_p2_prefixes as prefixes
import amd64_p2_review as review
import amd64_p2_default64 as default64
import amd64_p2_size_forms as size_forms
import amd64_source_constraints as architecture
from amd64_inventory_xed import canonical, digest

entry = prefixes.entry
require = entry.require
INPUT = prefixes.INPUT.parent / "p2-prefix-interpretations-v1.json"
ROOTS = ("prefix-note-2", "prefix-note-5", "prefix-note-6", "operand-note-2",
         "default64-instruction-exceptions")
C_CLOSURE_CHECKS={"prefix-note-5":"p2-c-instruction-owned-prefix-interpretations",
                  "default64-instruction-exceptions":"p2-c-default64-physical-form-proof"}
ANCHORS = {
    "vol1-lock": ("24592", 116, 22, 32),
    "vol1-repeat": ("24592", 116, 33, 41),
    "vol3-lock": ("24594", 54, 3, 6),
    "cmpxchg-wide-lock": ("24594", 211, 11, 28),
    "repeat-summary-note": ("24594", 49, 74, 75),
    "repeat-count-rule": ("24594", 54, 9, 17),
    "repeat-equal-rule": ("24594", 55, 18, 22),
    "repeat-not-equal-rule": ("24594", 55, 42, 47),
}
LOCK_NAMES = "ADC ADD AND BTC BTR BTS CMPXCHG CMPXCHG8B CMPXCHG16B DEC INC NEG NOT OR SBB SUB XADD XCHG XOR".split()


def interpretations():
    return {
        "p2:lock-list-disagreement": dict(
            state="resolved-source-rule", basis="instruction-owned-qualification-of-summary-list",
            originalVol1Mnemonics=[n for n in LOCK_NAMES if n != "CMPXCHG16B"],
            originalVol3Mnemonics=LOCK_NAMES,
            selectedMnemonics=LOCK_NAMES,
            qualification=dict(selector="CMPXCHG16B mem128", memoryDestination=True,
                               feature="CPUID.Fn0000_0001.ECX.CMPXCHG16B=1", alignmentBytes=16),
            justification="Vol1 explicitly refers to Vol3 for further details; Vol3's dedicated list and the owned CMPXCHG16B entry explicitly support LOCK.",
            publisherCorrection=False, productionAdmission=False),
        "p2:repeat-note-disagreement": dict(
            state="resolved-source-rule", basis="instruction-owned-qualification-of-summary-note",
            originalNoteScope="compare-string-and-scan-string-only;also-opcode-extension",
            countOnly=dict(prefix="f3", families=["INS", "LODS", "MOVS", "OUTS", "STOS"]),
            zfConditioned=dict(prefixes={"f3": "ZF=1", "f2": "ZF=0"}, families=["CMPS", "SCAS"]),
            countBits=[64, 32], countSelectedBy="address-size", mediaOpcodeSelection="separate-inventory",
            justification="Dedicated REP sections in Vol1 and Vol3, the source opcode tables and all seven instruction-owned clauses explicitly distinguish count-only from ZF-conditioned strings.",
            publisherCorrection=False, productionAdmission=False),
    }


def assess_interpretations(pack, sources, normalized):
    """Re-execute complete instruction ownership checks, not supplied statuses."""
    require(set(pack) == {"schema", "sourcePolicySha256", "executionModes", "anchors", "interpretations"}
            and pack["schema"] == "ariadne.amd64-prefix-interpretations/v1"
            and pack["sourcePolicySha256"] == entry.migration.sha(prefixes.native.adoption.INPUT)
            and pack["executionModes"] == ["long-64"]
            and canonical(pack["interpretations"]) == canonical(interpretations())
            and set(pack["anchors"]) == set(ANCHORS), "prefix interpretation identity/scope/rules differ")
    require(set(sources) == {"24592", "24594"}, "prefix interpretation source publications differ")
    pages = {pub: {p["pdfPage"]: p for p in population} for pub, population in sources.items()}
    require(all(len(pages[pub]) == len(sources[pub]) for pub in sources), "prefix interpretation duplicate page")
    pins = {d["publication"]: d["pdfSha256"] for d in prefixes.native.adoption.selected_documents()}
    observed = {}
    for name, (pub, number, first, last) in ANCHORS.items():
        record = pack["anchors"][name]
        require(set(record) == {"publication", "pdfSha256", "clause"} and record["publication"] == pub
                and record["pdfSha256"] == pins[pub], "prefix interpretation anchor owner differs")
        observed[name] = prefixes.clause(record["clause"], pages[pub],
                                        [f"pdf:{number}:cell:{i}" for i in range(first, last+1)])
    # Source-specific lists and the explicit cross-volume reference are kept
    # as evidence; the difference is never repaired by rewriting either list.
    def text(name):
        return " ".join(c["text"] for c in observed[name])
    for name, names in (("vol1-lock", [n for n in LOCK_NAMES if n != "CMPXCHG16B"]),
                        ("vol3-lock", LOCK_NAMES)):
        literal = text(name).split("operand:", 1)[1].split(". An invalid-opcode", 1)[0].strip()
        actual = literal.replace(", and ", ", ").replace(" and ", ", ").split(", ")
        require(actual == names, "prefix interpretation source-specific LOCK list differs")
    require('“Lock Prefix” in Volume 3' in text("vol1-lock") and
            "CMPXCHG8B and CMPXCHG16B instructions support the LOCK prefix" in text("cmpxchg-wide-lock") and
            "Fn0000_0001_ECX[CMPXCHG16B] = 1" in text("cmpxchg-wide-lock") and
            "16-byte aligned" in text("cmpxchg-wide-lock"), "CMPXCHG16B specific premise differs")
    require("only with compare-string and scan-string" in text("repeat-summary-note") and
            all(name in text("vol1-repeat") and name in text("repeat-count-rule")
                for name in ("INS", "LODS", "MOVS", "OUTS", "STOS")), "repeat source discrepancy differs")
    inventory = prefixes.assess(sources["24594"], normalized)
    require(inventory["lockSourceSelectors"] == 195 and inventory["lockSourceMnemonics"] == 19
            and set(inventory["repeat"]) == set(prefixes.REPEAT), "prefix interpretation inventory incomplete")
    return dict(schema="ariadne.amd64-prefix-interpretation-assessment/v1",
                executionModes=["long-64"], sourceClauses=observed,
                instructionInventory=inventory, dispositions=copy.deepcopy(pack["interpretations"]),
                closedReferences=["prefix-note-5"],
                remainingRepeatRoot="prefix-note-6:media-opcode-selectors-require-whole-form-inventory",
                productionAdmission=False)


def apply_interpretations(result, pack, sources, normalized):
    """Derive dispositions from source; never accept a saved proof/status object."""
    proof = assess_interpretations(pack, sources, normalized)
    result["prefixInterpretations"] = proof
    dispositions = proof["dispositions"]
    selected = {r["id"]: r for r in result["boundaryDispositions"] if r["id"] in dispositions}
    require(set(selected) == set(dispositions), "prefix interpretation original boundary omitted")
    recipes = {name: dict(rules=["p2-c:"+name.removeprefix("p2:")],
                          checks=["p2-c-instruction-owned-prefix-interpretations"])
               for name in dispositions}
    decisions = {name: dict(originalSha256=digest(record["original"]),
                            state="resolved-source-rule", **recipes[name],
                            reason=dispositions[name]["justification"])
                 for name, record in selected.items()}
    current = review.reconcile({name: record["original"] for name, record in selected.items()},
                               decisions, {recipe["rules"][0]: {} for recipe in recipes.values()},
                               {"p2-c-instruction-owned-prefix-interpretations": True}, recipes)
    by_id = {record["id"]: record for record in current}
    for record in result["boundaryDispositions"]:
        if record["id"] in by_id:
            previous = {k: copy.deepcopy(v) for k, v in record.items()
                        if k not in {"original", "originalSha256"}}
            record.update(by_id[record["id"]])
            record["previousDisposition"] = previous
            record["interpretation"] = copy.deepcopy(dispositions[record["id"]])
    derive_c_status(result,{"prefix-note-5":dict(check="p2-c-instruction-owned-prefix-interpretations",
                      assessmentSha256=digest(proof),sourceSelectors=195,boundary="p2:lock-list-disagreement")})
    return result


def derive_c_status(result,root_proofs):
    """Reset every C root from fresh proof, including previously promoted ones."""
    require(set(root_proofs)<=set(C_CLOSURE_CHECKS) and
            all(p.get("check")==C_CLOSURE_CHECKS[name] for name,p in root_proofs.items()),
            "C reference closure has no matching executed-check recipe")
    records=[r for r in result["referenceDispositions"] if r["original"]["id"] in ROOTS]
    require(len(records)==len(ROOTS) and {r["original"]["id"] for r in records}==set(ROOTS),
            "C original reference population omitted/duplicated")
    for record in records:
        name=record["original"]["id"]
        record["currentState"]="resolved-source-rule" if name in root_proofs else "unresolved"
        record["rules"]=[]
        record.pop("cProof",None)
        if name in root_proofs:record["cProof"]=copy.deepcopy(root_proofs[name])
    result["remainingArchitecturalReferences"]=[r["original"]["id"] for r in result["referenceDispositions"]
                                                if r["currentState"]!="resolved-source-rule"]
    pending=[name for name in ROOTS if name not in root_proofs]
    result["p2C"]=dict(schema="ariadne.amd64-p2-c-status/v1",executionModes=["long-64"],
        remainingReferences=pending,complete=not pending,
        completedChecks=sorted({p["check"] for p in root_proofs.values()}),
        referenceDependencies={name:list(proof.get("sharedRequirementsRemainAt",[])) for name,proof in root_proofs.items()
                               if proof.get("sharedRequirementsRemainAt")},
        limits=dict(byteDomains="P3",wholeRegionReview="P2-F/G",productionAdmission=False))
    return result


def apply_all(result,sources,normalized,no_rex):
    """Both closures execute their actual source checks in this call."""
    apply_interpretations(result,entry.read(INPUT),sources,normalized)
    size=default64.assess(entry.read(default64.INPUT),sources,normalized["entries"],no_rex)
    result["default64Forms"]=size
    exceptions=size_forms.assess(entry.read(size_forms.INPUT),sources["24594"],normalized["entries"],no_rex)
    result["sizeExceptionForms"]=exceptions
    partition=assess_size_partition(entry.read(PARTITION_INPUT),result["referenceDispositions"],size,exceptions)
    result["sizeReferencePartition"]=partition
    proofs={r["original"]["id"]:r["cProof"] for r in result["referenceDispositions"] if "cProof" in r}
    proofs["default64-instruction-exceptions"]=dict(check="p2-c-default64-physical-form-proof",
        assessmentSha256=digest(size),sourceOwners=size["sourceOwners"],sourceForms=size["sourceForms"],
        b5Groups=len(size["b5Groups"]),noRexEntries=27,partitionSha256=digest(partition),
        scope=copy.deepcopy(size["normalOperandAttributeScope"]),
        sharedRequirementsRemainAt=["operand-note-2","prefix-note-2"],globalDefaultFixedCensusComplete=False)
    derive_c_status(result,proofs)
    result["b1FamilyCoverage"]=b1_family_coverage(result["sizeRuleInventory"],size,exceptions,
        result["cSourceOwnerCoverage"]["wholeOwnerModeExclusions"],result["legacyMediaPrefixRows"])
    return result


def source_owner_coverage(normalized, legacy_assessment, xor_assessment, source_pages):
    """Expose the *owner* denominator without pretending it counts all forms.

    Normalized opcode-row counts are deliberately not the completeness oracle:
    the x87 continuation demonstrates that that extraction can omit forms.
    All instruction owners still provide concrete remaining review objects.
    """
    require(set(normalized)=={"24594","26568","26569"}, "C owner source publications differ")
    expected_counts={"24594":224,"26568":779,"26569":160}
    reviewed={}
    for name, record in legacy_assessment["owners"].items():
        reviewed[("26569",record["owner"])]=dict(check="legacy-media-physical-form-proof",
            sourceForms=record["sourceForms"], title=name)
    require(len(reviewed)==84 and legacy_assessment["sourceForms"]==176, "C legacy owner proof population differs")
    require(xor_assessment["sourceRows"]==12 and len(xor_assessment["rows"])==12,
            "C XOR owner proof population differs")
    for family in ("XORPS","XORPD"):
        owners=[e for e in normalized["26568"]["entries"] if e["title"]==family+" V"+family]
        require(len(owners)==1, "C XOR source owner omitted/duplicate")
        reviewed[("26568",owners[0]["id"])]=dict(check="xor-physical-form-proof",sourceForms=6,title=owners[0]["title"])
    mode_proof=assess_mode_exclusions(entry.read(MODE_INPUT),source_pages,normalized["24594"])
    excluded={("24594",r["owner"]):r for r in mode_proof["owners"].values()}
    require(not (set(excluded)&set(reviewed)),"C owner is both reviewed and wholly mode-excluded")
    obligations=[]
    for pub,source in normalized.items():
        entries=source["entries"]
        require(len(entries)==expected_counts[pub] and len({e["id"] for e in entries})==len(entries),
                "C source owner denominator omitted/duplicate")
        for owner in entries:
            key=(pub,owner["id"])
            proof=reviewed.get(key)
            require(proof is None or proof["title"]==owner["title"], "C reviewed owner/title collision")
            obligations.append(dict(publication=pub,owner=copy.deepcopy(owner),ownerSha256=digest(owner),
                state="reviewed-source-form-prefix-roles" if proof else
                      "excluded-selected-execution-mode" if key in excluded else "required-source-form-prefix-review",
                proof=copy.deepcopy(proof if proof else excluded.get(key))))
    require(len(obligations)==1163 and len(reviewed)==86, "C source owner coverage differs")
    return dict(schema="ariadne.amd64-p2-c-owner-coverage/v1",sourceOwners=1163,reviewedPrefixOwners=86,
                unreviewedSourceOwners=1077,modeExcludedSourceOwners=13,remainingNativeRequiredPrefixOwners=1064,
                remainingPrefixOwners=1064,reviewedPhysicalPrefixForms=188,obligations=obligations,
                wholeOwnerModeExclusions=mode_proof,
                wholeSourceFormDenominator="requires-complete-physical-row-and-shared-cell-inventory",
                b1TypedFamilies=172,b1FullFormQualification="required",
                complete=False,productionAdmission=False)


MODE_INPUT=prefixes.INPUT.parent/"p2-native64-owner-exclusions-v1.json"
# Whole-operation exclusions only. CALL/JMP far, LDS/LES/LFS/LGS/LSS,
# INC/DEC, POP/PUSH and MOVD are mixed owners and cannot enter this list.
WHOLE_MODE_OWNERS={
    "AAA":("0000",123,123,"invalid64","AAA",[16]),
    "AAD":("0001",124,124,"invalid64","AAD",[16]),
    "AAM":("0002",125,125,"invalid64","AAM",[16]),
    "AAS":("0003",126,126,"invalid64","AAS",[13]),
    "BOUND":("0022",163,164,"reassigned64","BOUND",[25,30]),
    "DAA":("0049",218,218,"invalid64","DAA",[14]),
    "DAS":("0050",219,219,"invalid64","DAS",[14]),
    "INTO":("0060",244,244,"invalid64","INTO",[9]),
    "POPA POPAD":("0104",329,329,"invalid64","POPA, POPAD",[9]),
    "PUSHA PUSHAD":("0110",341,341,"invalid64","PUSHA, PUSHAD",[9]),
    "ARPL":("0154",421,422,"reassigned64","ARPL",[21]),
    "SYSENTER":("0207",530,531,"invalidLongMode","SYSENTER",[5,6,7]),
    "SYSEXIT":("0208",532,533,"invalidLongMode","SYSEXIT",[7,8,9]),
}


def assess_mode_owner(name,record,pages,normalized,mode_tables):
    require(name in WHOLE_MODE_OWNERS,"whole-mode exclusion is not a reviewed complete owner")
    ident,first,last,table,mnemonic,clause_ids=WHOLE_MODE_OWNERS[name]
    owner="amd-entry:"+ident
    require(set(record)=={"owner","title","pages","pageDigests","clause","sourceRowsSha256","modeTable","modeMnemonic"}
            and record["owner"]==owner and record["title"]==name and record["pages"]==[first,last]
            and record["modeTable"]==table and record["modeMnemonic"]==mnemonic,"whole-mode exclusion owner/scope differs")
    entries=[e for e in normalized["entries"] if e["id"]==owner]
    require(len(entries)==1 and entries[0]["title"]==name and
            [entries[0]["pdfPage"],entries[0]["pdfEndPage"]]==[first,last],"whole-mode actual owner differs")
    by_number={p["pdfPage"]:p for p in pages if first<=p["pdfPage"]<=last}
    require(set(by_number)==set(range(first,last+1)) and record["pageDigests"]=={
        str(n):digest(p["cells"]) for n,p in by_number.items()},"whole-mode owner actual pages differ")
    cells=prefixes.clause(record["clause"],by_number,[f"pdf:{first}:cell:{i}" for i in clause_ids])
    rows=[r for r in normalized["rows"] if owner in r["entryIds"]]
    require(rows and digest(rows)==record["sourceRowsSha256"],"whole-mode source forms omitted/changed")
    summary=[r for r in mode_tables[table] if r["mnemonic"]==mnemonic]
    require(len(summary)==1,"whole-mode B3 source operation omitted/duplicate")
    return dict(owner=owner,title=name,sourceForms=len(rows),originalRows=copy.deepcopy(rows),
                modeTable=table,modeMnemonic=mnemonic,sourceClause=cells,sourceModeRow=copy.deepcopy(summary[0]),
                state="excluded-selected-execution-mode",scope="whole-old-operation-owner;not-leading-byte-exclusion",
                replacementEncodingOwnersExcluded=False)


def assess_mode_exclusions(pack,pages,normalized):
    require(set(pack)=={"schema","sourcePolicySha256","publication","pdfSha256","executionModes","owners"}
            and pack["schema"]=="ariadne.amd64-native64-owner-exclusions/v1" and pack["publication"]=="24594"
            and pack["sourcePolicySha256"]==entry.migration.sha(prefixes.native.adoption.INPUT)
            and pack["pdfSha256"]==next(d["pdfSha256"] for d in prefixes.native.adoption.selected_documents() if d["publication"]=="24594")
            and pack["executionModes"]==["long-64"] and set(pack["owners"])==set(WHOLE_MODE_OWNERS),
            "whole-mode exclusion source scope/population differs")
    by_number={p["pdfPage"]:p for p in pages}
    require(len(by_number)==len(pages),"whole-mode actual page duplicate")
    pins=entry.read(prefixes.native.INPUT)["pages"]
    mode_tables={}
    for name,spec in prefixes.native.MODE_TABLES.items():
        require(spec[0] in by_number and digest(by_number[spec[0]]["cells"])==pins[str(spec[0])],
                "whole-mode actual B3 table source differs")
        mode_tables[name]=prefixes.native.parse_mode_table(by_number[spec[0]],name)
    owners={name:assess_mode_owner(name,record,pages,normalized,mode_tables) for name,record in pack["owners"].items()}
    require(len(owners)==13 and sum(r["sourceForms"] for r in owners.values())==18,"whole-mode owner/form denominator differs")
    return dict(schema="ariadne.amd64-native64-owner-exclusion-assessment/v1",executionModes=["long-64"],
                owners=owners,excludedSourceOwners=13,preservedExcludedSourceForms=18,
                mixedOwners="remain-required;row-exclusions-do-not-exclude-whole-owner",productionAdmission=False)


PARTITION_INPUT=INPUT.parent/"p2-size-reference-partition-v1.json"


def original_architecture_reference(name):
    return dict(id=name,**copy.deepcopy(architecture.ARCHITECTURE_REFERENCES[name]))


def size_partition_policy():
    names=["default64-instruction-exceptions","operand-note-2","prefix-note-2"]
    return dict(schema="ariadne.amd64-size-reference-partition/v1",
        sourcePolicySha256=entry.migration.sha(prefixes.native.adoption.INPUT),executionModes=["long-64"],
        originalReferencesSha256={name:digest(original_architecture_reference(name)) for name in names},
        root="default64-instruction-exceptions",
        coveredRequirement=dict(sourceCells=[f"24594/pdf:50:cell:{i}" for i in range(67,78)],
            premise="normal-operand-size-attribute;near-branches-under-accepted-fixed64-hypothesis",
            domain="near-branches-and-implicit-RSP-operations-except-far-transfers",
            proof="complete-owned-B5-and-Vol1-attribute-subproof"),
        sharedRequirements=[dict(owner="operand-note-2",sourceCells=["24594/pdf:50:cell:64","24594/pdf:50:cell:65"],
            requirement="complete-current-manual-default-and-fixed-size-form-qualification;Appendix-B-is-not-the-entire-current-census"),
            dict(owner="prefix-note-2",sourceCells=[f"24594/pdf:49:cell:{i}" for i in range(68,71)],
                 domainPremiseCells=["24594/pdf:50:cell:78","24594/pdf:50:cell:79"]+[f"24594/pdf:51:cell:{i}" for i in range(3,9)],
                 requirement="nonstandard-prefix-and-fixed-size-applicability;no-generic-override-assumption")],
        locatedReference=dict(owner="operand-note-3",sourceCells=["24594/pdf:50:cell:66"],state="resolved-location"),
        additionalCounterexample=dict(owner="amd-entry:0115",title="RDPID",publication="24594",pdfPage=349,
            clauseCells=[f"pdf:349:cell:{i}" for i in range(5,13)],encodingCell="pdf:349:cell:17",
            currentSourceRule="mode-fixed64-update;normal-size-prefixes-do-not-apply;F3-opcode-selector",
            requirementOwners=["operand-note-2","prefix-note-2"],inAppendixB=False),
        globalDefaultFixedCensusComplete=False,wholeCComplete=False,productionAdmission=False)


def assess_size_partition(pack,references,default_proof,exception_proof):
    """Preserve every broad requirement when closing the normal-attribute part.

    The broad Appendix B pointer is literally the same source target as
    operand-note-2. It remains owned there; it is not declared globally solved.
    """
    require(canonical(pack)==canonical(size_partition_policy()),"unreviewed size reference partition/scope")
    refs={r["original"]["id"]:r for r in references}
    for name,pin in pack["originalReferencesSha256"].items():
        require(name in refs and digest(refs[name]["original"])==refs[name]["originalSha256"]==pin,
                "size partition original reference identity differs")
    root=refs[pack["root"]]["original"]
    covered=pack["coveredRequirement"]["sourceCells"]
    shared=pack["sharedRequirements"][0]["sourceCells"]
    located=pack["locatedReference"]["sourceCells"]
    require(len(set(covered+shared+located))==len(covered+shared+located) and
            set(covered+shared+located)==set(root["sourceCells"]),"size partition drops/duplicates original source requirements")
    require(shared==refs["operand-note-2"]["original"]["targetCells"] and
            pack["sharedRequirements"][1]["sourceCells"]==refs["prefix-note-2"]["original"]["targetCells"] and
            located==architecture.ARCHITECTURE_REFERENCES["operand-note-3"]["targetCells"] and
            architecture.ARCHITECTURE_REFERENCES["operand-note-3"]["status"]=="resolved-location",
            "size partition successor/source target ownership differs")
    require(default_proof["state"]=="checked-default64-operand-attribute-subproof" and
            default_proof["normalOperandAttributeScope"]["sourceCells"]==covered and
            len(default_proof["b5Groups"])==21 and default_proof["sourceForms"]==172 and
            default_proof["globalDefaultFixedCensusComplete"] is False,"size partition lacks actual attribute-domain proof")
    rdpid=exception_proof["owners"]["RDPID"]
    require(rdpid["owner"]=="amd-entry:0115" and rdpid["sourceForms"]==1 and
            rdpid["forms"][0]["sourceEncoding"]=="F3 0F C7/7" and
            rdpid["forms"][0]["properties"]["currentDestinationRegisterBits"]==64 and
            rdpid["forms"][0]["properties"]["operandWidthSelectedBy"]=="execution-mode;not-66-or-REX.W" and
            rdpid["clauses"]["cells"]==pack["additionalCounterexample"]["clauseCells"],
            "size partition erased the extra-B1 fixed-size counterexample")
    return dict(schema="ariadne.amd64-size-reference-partition-assessment/v1",policy=copy.deepcopy(pack),
                state="resolved-normal-operand-attribute-subrule;shared-global-requirements-remain",
                currentReferenceState="resolved-source-rule",openSuccessorReferences=["operand-note-2","prefix-note-2"],
                default64SubproofSha256=digest(default_proof),sizeExceptionSubproofSha256=digest(exception_proof),
                originalBroadReferencePreserved=True,globalDefaultFixedCensusComplete=False,wholeCComplete=False,
                productionAdmission=False)


def default_b1_forms(record,proof):
    """Crosswalk a B1 family only to its actual qualified source rows."""
    heading=record["heading"]["text"]
    family=size_forms.sizes.family(heading)
    kind=record["properties"]["kind"]
    owner=None
    if kind=="selected-near-branch":
        owner={"CALL":"CALL (Near)","Jcc":"Jcc","JCXZ":"JCXZ JECXZ JRCXZ","JMP":"JMP (Near)",
               "LOOP":"LOOP LOOPE LOOPNE LOOPNZ LOOPZ","LOOPZ":"LOOP LOOPE LOOPNE LOOPNZ LOOPZ",
               "LOOPNZ":"LOOP LOOPE LOOPNE LOOPNZ LOOPZ","RET":"RET (Near)"}[family]
    elif kind=="default64-stack-subforms":
        owner={"POPF":"POPF POPFD POPFQ","PUSHF":"PUSHF PUSHFD PUSHFQ"}.get(family,family)
    elif kind=="fixed-descriptor-base" or kind=="fixed-explicit-selector-or-word" and family in {"LLDT","LTR"}:
        owner=family
    elif kind=="fixed-control-or-debug-transfer":owner={"MOV(CRn)":"MOV CRn","MOV(DRn)":"MOV DRn"}[family]
    if owner is None:return None
    require(owner in proof["owners"],"B1 default family lost its qualified source owner")
    source=proof["owners"][owner]
    forms=source["forms"]
    if family in {"POP","PUSH"}:
        segment="segment" in heading.lower()
        forms=[r for r in forms if (r["selector"].split(" ",1)[1] in {"CS","DS","ES","SS","FS","GS"})==segment]
    elif family in {"LOOP","LOOPZ","LOOPNZ"}:
        names={"LOOP":{"LOOP"},"LOOPZ":{"LOOPZ","LOOPE"},"LOOPNZ":{"LOOPNZ","LOOPNE"}}[family]
        forms=[r for r in forms if r["selector"].split()[0] in names]
    require(forms,"B1 family has no actual qualified subforms")
    return dict(check="default64-attribute-and-bounded-fixed-source-forms",publication="24594",owner=source["owner"],
                sourceRowOrdinals=[r["sourceRowOrdinal"] for r in forms],selectors=[r["selector"] for r in forms],
                formStates=[r["properties"]["state"] for r in forms],sourceForms=len(forms))


def b1_family_coverage(typed,default_proof,exception_proof,mode_proof,legacy_proof):
    require(len(typed["rows"])==172,"B1 family coverage source population differs")
    require(len(default_proof["owners"])==20 and default_proof["sourceForms"]==172 and
            len(exception_proof["owners"])==15 and exception_proof["sourceForms"]==39 and
            mode_proof["excludedSourceOwners"]==13,"B1 family source proof populations differ")
    rows=[]
    for record in typed["rows"]:
        family=size_forms.sizes.family(record["heading"]["text"])
        link=default_b1_forms(record,default_proof)
        if family in exception_proof["b1Families"]:
            require(link is None,"B1 family receives overlapping qualification owners")
            binding=exception_proof["b1Families"][family]
            require(canonical(binding["sourceFamily"])==canonical(record),"B1 special family/source identity differs")
            owner=next(v for v in exception_proof["owners"].values() if v["owner"]==binding["sourceOwner"])
            forms=[f for f in owner["forms"] if f["selector"] in binding["sourceFormSelectors"]]
            require(len(forms)==len(binding["sourceFormSelectors"]),"B1 special source form omitted/duplicate")
            link=dict(check="owned-size-exception-forms",publication="24594",owner=owner["owner"],
                      sourceRowOrdinals=[f["sourceRowOrdinal"] for f in forms],selectors=[f["selector"] for f in forms],
                      formStates=[f["properties"]["state"] for f in forms],sourceForms=len(forms))
        old_name={"POPA":"POPA POPAD","PUSHA":"PUSHA PUSHAD"}.get(family,family)
        if old_name in mode_proof["owners"]:
            require(link is None,"B1 old-mode family overlaps a current form qualification")
            owner=mode_proof["owners"][old_name]
            link=dict(check="whole-old-operation-mode-exclusion",publication="24594",owner=owner["owner"],
                      sourceRowOrdinals=list(range(owner["sourceForms"])),selectors=[f["mnemonic"] for f in owner["originalRows"]],
                      formStates=["excluded-selected-execution-mode"]*owner["sourceForms"],sourceForms=owner["sourceForms"])
        if family=="WAIT":
            require(link is None,"B1 WAIT source ownership overlaps")
            owner=legacy_proof["owners"]["FWAIT (WAIT)"]
            require(owner["sourceForms"]==1 and owner["forms"][0]["sourceEncoding"]=="9B" and
                    owner["forms"][0]["properties"]["mnemonicAliases"]==["WAIT"],"B1 WAIT lacks owned synonym proof")
            link=dict(check="owned-FWAIT-WAIT-source-alias",publication="26569",owner=owner["owner"],
                      sourceRowOrdinals=[0],selectors=["FWAIT"],formStates=["native64-source-form"],sourceForms=1,
                      originalSummaryLabelPreserved=True)
        state="required-instruction-form-size-qualification"
        if link:
            state="excluded-selected-execution-mode" if all(s=="excluded-selected-execution-mode" for s in link["formStates"]) else "checked-source-form-size-qualification"
        rows.append(dict(pdfPage=record["pdfPage"],heading=copy.deepcopy(record["heading"]),
                         sourceFamilySha256=digest(record),kind=record["properties"]["kind"],state=state,proof=link))
    states={state:sum(r["state"]==state for r in rows) for state in {r["state"] for r in rows}}
    require(states=={"checked-source-form-size-qualification":41,"excluded-selected-execution-mode":15,
                     "required-instruction-form-size-qualification":116},"B1 proved/required family coverage differs")
    physical={(r["proof"]["publication"],r["proof"]["owner"],i) for r in rows if r["proof"] for i in r["proof"]["sourceRowOrdinals"]}
    require(len(physical)==229,"B1 reviewed physical source-form population differs")
    return dict(schema="ariadne.amd64-b1-family-form-coverage/v1",sourceFamilies=172,qualifiedFamilies=56,
                modeExcludedFamilies=15,remainingFamilies=116,reviewedPhysicalSourceForms=229,rows=rows,
                additionalOwnedSourceFormsOutsideB1=[dict(publication="24594",owner="amd-entry:0115",title="RDPID",sourceForms=1)],
                completeB1FormInventory=False,currentManualCensusComplete=False,productionAdmission=False)
