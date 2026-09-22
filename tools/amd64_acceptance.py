"""Evidence-backed closure checks for the AMD64 coverage ledger.

This validates an explicit reviewed coverage claim; it cannot infer that prose
has been interpreted correctly. Machine checks still run in the check scripts.
In particular, a component proof is not an instruction-coverage certificate.
"""

import hashlib
from pathlib import Path
import re


INTEGRATION_OBLIGATIONS = {
    "machine-state-composition", "decoded-form-dispatch", "analysis-projection",
    "old-subset-correspondence", "exception-priority", "restart",
    "memory-ordering", "profile-dependent-behavior",
}


def index_rows(rows, label):
    result = {row["id"]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"Duplicate {label} IDs")
    return result


def checked_path(root, name):
    if Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError("Evidence source paths must be repository-relative")
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError(f"Missing or external evidence source: {name}")
    return path


def check_evidence(record, root):
    if record["result"] != "passed" or not record.get("command") or not record.get("summary"):
        raise ValueError(f"Validation record lacks a passed check: {record['id']}")
    if not record.get("sources"):
        raise ValueError(f"Validation record has no source hashes: {record['id']}")
    paths = set()
    for source in record["sources"]:
        name = source["path"]
        if name in paths:
            raise ValueError("Duplicate validation source")
        paths.add(name)
        if not re.fullmatch(r"[a-f0-9]{64}", source["sha256"]):
            raise ValueError("Invalid validation source hash")
        actual = hashlib.sha256(checked_path(root, name).read_bytes()).hexdigest()
        if actual != source["sha256"]:
            raise ValueError(f"Stale validation source: {name}")
    return paths


def check_ledger(coverage, root, forms=None, fields=None):
    """Return counts; reject unsupported accepted claims even before closure."""
    records = index_rows(coverage["validation_records"], "validation")
    evidence_paths = {key: check_evidence(record, root) for key, record in records.items()}
    cases = index_rows(coverage["semantic_cases"], "semantic case")
    foundations = index_rows(coverage.get("foundation_components", []), "foundation component")
    components = index_rows(coverage["state_components"], "state component")
    dependencies = index_rows(coverage["system_dependencies"], "system dependency")
    obligations = index_rows(coverage["integration_obligations"], "integration obligation")
    if set(obligations) != INTEGRATION_OBLIGATIONS:
        raise ValueError("Integration obligations were removed or not inventoried")

    def accepted_leaf(item):
        if item["status"] not in {"pending", "implemented", "accepted"}:
            raise ValueError(f"Unknown leaf status: {item['id']}")
        if item["status"] != "accepted":
            return False
        if not item.get("description") or item.get("open_obligations") != []:
            raise ValueError(f"Accepted item still has unclosed scope: {item['id']}")
        if not item.get("checks") or not item.get("rules"):
            raise ValueError(f"Accepted item lacks rules/checks: {item['id']}")
        kinds = set()
        covered_paths = set()
        paths_by_kind = {}
        for check in item["checks"]:
            if check not in records:
                raise ValueError(f"Missing validation evidence: {check}")
            kinds.add(records[check]["kind"])
            covered_paths.update(evidence_paths[check])
            paths_by_kind.setdefault(records[check]["kind"], set()).update(evidence_paths[check])
        if not {"tla-typecheck", "lean-build", "lean-axiom-audit"} <= kinds:
            raise ValueError(f"Missing TLA+/Lean evidence: {item['id']}")
        if not kinds & {"tlc", "apalache"}:
            raise ValueError(f"Missing executable TLA+ evidence: {item['id']}")
        languages = set()
        for rule in item["rules"]:
            path = checked_path(root, rule["path"])
            if rule["path"] not in covered_paths or not rule.get("symbol"):
                raise ValueError(f"Rule not bound to checked sources: {item['id']}")
            if path.suffix not in {".tla", ".lean"}:
                raise ValueError("A semantic rule must refer to TLA+ or Lean source")
            if path.suffix == ".lean" and not all(
                rule["path"] in paths_by_kind[kind] for kind in ["lean-build", "lean-axiom-audit"]
            ):
                raise ValueError("Lean rule is not bound to both build and axiom-audit evidence")
            if path.suffix == ".tla" and (
                rule["path"] not in paths_by_kind["tla-typecheck"]
                or rule["path"] not in paths_by_kind.get("tlc", set()) | paths_by_kind.get("apalache", set())
            ):
                raise ValueError("TLA+ rule is not bound to typechecking and executable evidence")
            languages.add(path.suffix)
        if languages != {".tla", ".lean"}:
            raise ValueError(f"Accepted item needs both formalizations: {item['id']}")
        return True

    accepted_cases = {key for key, item in cases.items() if accepted_leaf(item)}
    accepted_foundations = {key for key, item in foundations.items() if accepted_leaf(item)}
    accepted_components = {key for key, item in components.items() if accepted_leaf(item)}
    accepted_dependencies = {key for key, item in dependencies.items() if accepted_leaf(item)}
    accepted_obligations = {key for key, item in obligations.items() if accepted_leaf(item)}

    for collection in [foundations, cases, components, dependencies, obligations]:
        for item in collection.values():
            for foundation in item.get("foundations", []):
                if foundation not in foundations:
                    raise ValueError(f"Unknown foundation component: {foundation}")
                if item["status"] == "accepted" and foundation not in accepted_foundations:
                    raise ValueError(f"Accepted item has unaccepted foundation: {item['id']}")
            for dependency in item.get("dependencies", []):
                if dependency not in dependencies:
                    raise ValueError(f"Unknown system dependency: {dependency}")
                if item["status"] == "accepted" and dependency not in accepted_dependencies:
                    raise ValueError(f"Accepted item has unaccepted dependency: {item['id']}")

    forms_by_id = {} if forms is None else {form["form_id"]: form for form in forms["forms"]}
    fields_by_id = {} if fields is None else {field["id"]: field for field in fields["fields"]}
    if forms is not None and len(forms_by_id) != len(forms["forms"]):
        raise ValueError("Duplicate form IDs in accepted source inventory")
    if fields is not None and len(fields_by_id) != len(fields["fields"]):
        raise ValueError("Duplicate state field IDs in accepted source inventory")
    complete_entries = set()
    for entry in coverage["instruction_entries"]:
        if entry["status"] not in {"pending-form-review", "reviewed-forms", "partial", "complete"}:
            raise ValueError("Unknown instruction coverage status")
        if entry["status"] != "complete":
            continue
        if not entry.get("review_complete") or entry.get("open_obligations") != []:
            raise ValueError("Complete instruction needs closed source review")
        expected = {key for key, form in forms_by_id.items() if entry["id"] in form["entry_ids"]}
        if not expected or set(entry.get("form_ids", [])) != expected:
            raise ValueError("Complete instruction does not cover its entire form inventory")
        for form_id in expected:
            review = forms_by_id[form_id]["review"]
            if review["level"] != "semantic-reviewed" or review["status"] != "reviewed":
                raise ValueError("Complete instruction contains an unreviewed form")
        case_ids = entry["semantic_cases"]
        if not case_ids or not set(case_ids) <= accepted_cases:
            raise ValueError("Complete instruction contains unaccepted semantic cases")
        covered = set()
        for case_id in case_ids:
            case = cases[case_id]
            if entry["id"] not in case["source_entry_ids"]:
                raise ValueError("Semantic case belongs to another source entry")
            covered.update(case["form_ids"])
        if not expected <= covered:
            raise ValueError("Complete instruction has forms without accepted semantics")
        complete_entries.add(entry["id"])

    complete_sections = set()
    for section in coverage["volume1_sections"]:
        if section["status"] not in {"pending-state-review", "reviewed", "partial", "complete", "informational"}:
            raise ValueError("Unknown state-section coverage status")
        if section["status"] not in {"complete", "informational"}:
            continue
        if not section.get("review_complete") or not section.get("rationale"):
            raise ValueError("Closed state section needs a reviewed rationale")
        if section.get("open_obligations") != []:
            raise ValueError("Closed state section still has open obligations")
        if section["status"] == "complete":
            field_ids = section.get("field_ids", [])
            if not field_ids or not set(field_ids) <= set(fields_by_id):
                raise ValueError("Closed state section lacks inventoried fields")
            component_ids = section["state_components"]
            if not component_ids or not set(component_ids) <= accepted_components:
                raise ValueError("Closed state section lacks accepted components")
            covered_fields = {field for key in component_ids for field in components[key]["field_ids"]}
            if not set(field_ids) <= covered_fields:
                raise ValueError("Closed state section contains unimplemented fields")
        complete_sections.add(section["id"])

    return {
        "complete_instruction_entries": len(complete_entries),
        "complete_volume1_sections": len(complete_sections),
        "accepted_semantic_cases": len(accepted_cases),
        "accepted_foundation_components": len(accepted_foundations),
        "accepted_state_components": len(accepted_components),
        "accepted_system_dependencies": len(accepted_dependencies),
        "accepted_integration_obligations": len(accepted_obligations),
        "complete": bool(
            len(complete_entries) == len(coverage["instruction_entries"])
            and len(complete_sections) == len(coverage["volume1_sections"])
            and accepted_obligations == set(obligations)
            and set(dependencies) == accepted_dependencies
            and set(cases) == accepted_cases
            and set(components) == accepted_components
            and bool(dependencies)
            and bool(cases) and bool(components)
            and bool(coverage["instruction_entries"]) and bool(coverage["volume1_sections"])
        ),
    }
