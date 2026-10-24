#!/usr/bin/env python3
"""Validate independently reviewed source-cell dispositions for P2.

Review inputs are source decisions, not passing receipts. A whole page can be
complete only after its full actual cell population, owned clauses, references
and unresolved dependencies have been checked. Unknown source stays required.
"""
import copy

from amd64_inventory_xed import canonical, digest

CLOSED_STATES = {"resolved-source-rule", "excluded-selected-execution-mode"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, names, label):
    require(type(value) is dict and set(value) == set(names), label + " fields differ")


def cell_key(pdf_sha, identifier):
    return pdf_sha + "/" + identifier


def furniture(cell, page):
    """Only known running matter at the page edges can have this role."""
    text = cell["text"]
    y = cell["rect"][1]
    if y < 85:
        return text in {"[AMD Public Use]", "[AMD Confidential - Distribution with NDA]", "AMD64 Technology"} or (
            "—Rev. " in text and text[:5].isdigit() and text.count("—") == 2)
    return y > page["size"][1] - 80 and (text.isdigit() or text in {
        "Instruction Encoding", "Instruction Overview", "General-Purpose", "Instruction Reference",
        "General-Purpose Programming", "Segmented Virtual Memory", "Page Translation and Protection"})


def validate_page(decision, page, document, clauses, contexts, references, issues):
    fields(decision, {"publication", "pdfSha256", "pdfPage", "sourceCellsSha256", "inventory", "roles"}, "page review")
    require(decision["publication"] == document["publication"] and decision["pdfSha256"] == document["pdfSha256"]
            and type(decision["pdfPage"]) is int and decision["pdfPage"] == page["pdfPage"], "page review source owner differs")
    require(decision["sourceCellsSha256"] == digest(page["cells"]), "page review source population/geometry differs")
    actual = {c["id"]: c for c in page["cells"]}
    require(len(actual) == len(page["cells"]) and all(c["pdfPage"] == page["pdfPage"] for c in actual.values()),
            "page review source cell duplicate/foreign page")
    require(sum(len(c["wordBoxes"]) for c in actual.values()) == page["wordCount"], "page review word population differs")
    require(type(decision["inventory"]) is list and len(set(decision["inventory"])) == len(decision["inventory"])
            and set(decision["inventory"]) <= clauses.keys(), "page review clause inventory unknown/duplicate")
    require(type(decision["roles"]) is list, "page review role list")
    seen, used, dependencies, reference_ids = set(), set(), set(), set()
    for role in decision["roles"]:
        fields(role, {"cells", "role", "targets"}, "source-cell disposition")
        require(type(role["cells"]) is list and role["cells"] and len(set(role["cells"])) == len(role["cells"])
                and set(role["cells"]) <= actual.keys() and not seen.intersection(role["cells"]), "source-cell role omitted/overlapping/foreign")
        require(type(role["targets"]) is list and len(set(role["targets"])) == len(role["targets"]), "source-cell target list")
        seen.update(role["cells"])
        keys = {cell_key(document["pdfSha256"], c) for c in role["cells"]}
        if role["role"] == "clause":
            require(role["targets"] and set(role["targets"]) <= set(decision["inventory"]), "source-cell clause target missing/unknown")
            owned = set()
            for target in role["targets"]:
                owned.update(clauses[target]["sourceCells"])
                dependencies.update(clauses[target]["issues"])
            require(keys <= owned, "source-cell clause ownership differs")
            # No target can piggyback on another target's source ownership.
            require(all(keys.intersection(clauses[t]["sourceCells"]) for t in role["targets"]), "source-cell clause target has no owned evidence")
            used.update(role["targets"])
        elif role["role"] == "context":
            require(set(role["targets"]) == keys and keys <= contexts.keys(), "source context lacks independently reviewed role")
        elif role["role"] == "reference":
            require(role["targets"] and set(role["targets"]) <= references.keys(), "source reference target missing/unknown")
            for target in role["targets"]:
                require(keys <= set(references[target]["sourceCells"]), "source reference ownership differs")
                dependencies.update(references[target]["issues"])
                reference_ids.add(target)
        elif role["role"] == "furniture":
            require(not role["targets"] and all(furniture(actual[i], page) for i in role["cells"]), "normative source classified as furniture")
        else:
            raise ValueError("unknown source-cell role cannot grant review completeness")
    require(seen == set(actual), "page review omitted source cells")
    require(used == set(decision["inventory"]), "page review inventory clause omitted or unused")
    require(dependencies <= issues.keys(), "page review unresolved dependency has no owner")
    pending = sorted(i for i in dependencies if issues[i]["state"] not in CLOSED_STATES)
    return dict(publication=document["publication"], pdfSha256=document["pdfSha256"], pdfPage=page["pdfPage"],
        sourceCellsSha256=digest(page["cells"]), sourceCells=len(actual), sourceWords=page["wordCount"],
        inventory=list(decision["inventory"]), references=sorted(reference_ids), pendingIssues=pending,
        state="reviewed-all-required-clauses" if not pending else "reviewed-source-with-open-dependencies")


def apply_reviews(records, decisions, actual_pages, documents, clauses, contexts, references, issues):
    """Overlay only source-validated decisions on the complete required population."""
    populations = {(r["pdfSha256"], r["pdfPage"]): r for r in records}
    require(len(populations) == len(records), "duplicate required source region")
    verified = {}
    for decision in decisions:
        key = (decision["pdfSha256"], decision["pdfPage"])
        require(key in populations and key not in verified and key in actual_pages, "reviewed region missing/duplicate/foreign")
        require(decision["publication"] in documents, "reviewed publication missing")
        verified[key] = validate_page(decision, actual_pages[key], documents[decision["publication"]],
                                     clauses, contexts, references, issues)
    result = []
    for record in records:
        updated = copy.deepcopy(record)
        key = (record["pdfSha256"], record["pdfPage"])
        if key in verified:
            require(record["sourceCellsSha256"] == verified[key]["sourceCellsSha256"], "required region/review digest differs")
            updated["review"] = verified[key]
            updated["state"] = verified[key]["state"]
        else:
            updated["state"] = "required-whole-region-clause-review"
        result.append(updated)
    return result


def section_state(pdf_sha, first, last, regions):
    wanted = list(range(first, last + 1))
    selected = [r for r in regions if r["pdfSha256"] == pdf_sha and first <= r["pdfPage"] <= last]
    require(sorted(r["pdfPage"] for r in selected) == wanted, "source section missing/duplicate required page")
    complete = all(r["state"] == "reviewed-all-required-clauses" for r in selected)
    return dict(state="reviewed-all-required-clauses" if complete else "required-clause-review", constraintsParsed=complete,
        reviewedPages=sum(r["state"] == "reviewed-all-required-clauses" for r in selected), requiredPages=len(wanted))


def reconcile(originals, decisions, clauses, checks, recipes):
    """Preserve original boundaries and count only checked current dispositions."""
    require(set(originals) == set(decisions), "current boundary disposition omitted/extra")
    result = []
    for identifier, original in sorted(originals.items()):
        decision = decisions[identifier]
        fields(decision, {"originalSha256", "state", "rules", "checks", "reason"}, "boundary disposition")
        require(decision["originalSha256"] == digest(original) and type(decision["reason"]) is str and decision["reason"],
                "original boundary identity or disposition reason differs")
        require(type(decision["rules"]) is list and type(decision["checks"]) is list
                and set(decision["rules"]) <= clauses.keys() and set(decision["checks"]) <= checks.keys(),
                "boundary disposition rule/check missing")
        require(decision["state"] in CLOSED_STATES | {"unresolved"}, "unreviewed boundary promotion")
        if decision["state"] in CLOSED_STATES:
            recipe = recipes.get(identifier, {})
            require(decision["state"] == recipe.get("state", "resolved-source-rule") and
                    canonical(dict(rules=decision["rules"],checks=decision["checks"])) == canonical({k:v for k,v in recipe.items() if k != "state"}),
                    "boundary resolution has no matching source-proof recipe")
            require(decision["rules"] and decision["checks"] and all(checks[c] is True for c in decision["checks"]),
                    "boundary resolution lacks executed source check")
        result.append(dict(id=identifier, original=copy.deepcopy(original), originalSha256=digest(original), **{
            k: copy.deepcopy(v) for k,v in decision.items() if k != "originalSha256"}))
    return result
