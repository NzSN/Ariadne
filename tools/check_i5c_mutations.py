#!/usr/bin/env python3
"""Compile the 24 frozen I5c defects with pinned, case-specific positive controls."""
import argparse
from pathlib import Path

from i5a_native_contract import environment
from i5c_qualification import (FIXTURES, ROOT, artifact, build_test, copy_sut,
                               observe, prerequisite_report, read_json, require,
                               sources, unchanged_observers, write_json)

WRAP = "src/investigation/address_wrap.rs"
SCALAR = "src/investigation/scalar_base_displacement.rs"
ZERO = "src/investigation/zero_address.rs"
CLI = "src/bin/ariadne-minidump.rs"
SUM = "i128::from(base) + i128::from(facts.displacement)"
MUTATIONS = {
    "signed-base": [(WRAP, SUM, "i128::from(base as i64) + i128::from(facts.displacement)")],
    "unsigned-displacement": [(WRAP, SUM, "i128::from(base) + i128::from(facts.displacement as u64)")],
    "unsigned-carry": [(WRAP, "} else if sum >= MODULUS {", "} else if base.overflowing_add(facts.displacement as u64).1 {")],
    "absolute-displacement": [(WRAP, SUM, "i128::from(base) + i128::from(facts.displacement.abs())")],
    "strict-upper-bound": [(WRAP, "} else if sum >= MODULUS {", "} else if sum > MODULUS {")],
    "reduced-before-sum": [(WRAP, SUM, "i128::from(base.wrapping_add(facts.displacement as u64))")],
    "disp8-sign": [(SCALAR, "displacement: r.displacement,", "displacement: i64::from(r.displacement as u8),")],
    "disp32-sign": [(SCALAR, "displacement: r.displacement,", "displacement: i64::from(r.displacement as u32),")],
    "bap-ea-agreement": [
        (SCALAR, "|| x.constant != r.displacement as u64", "|| false"),
        (WRAP, "if ea != admitted_ea {", "if false && ea != admitted_ea {")],
    "decoded-base-agreement": [(SCALAR, "|| x.terms[0].bank != bank", "|| false")],
    "zero-index-admission": [(SCALAR, "if r.index.is_some()", "if false"),
                             (SCALAR, "x.terms.len() != 1", "x.terms.is_empty()")],
    "missing-base-validity": [
        (ZERO, 'if let Some(value) = fields.get(format!("reg:{reg}").as_str()) {',
         'if let Some(value) = Some(fields.get(format!("reg:{reg}").as_str()).unwrap_or(&0)) {'),
        (WRAP, 'let Some(&base) = fields.get(format!("reg:{register}").as_str()) else {',
         'let Some(&base) = Some(fields.get(format!("reg:{register}").as_str()).unwrap_or(&0)) else {')],
    "operation-treated-late": [(ZERO, 'd.gaps.insert("access-kind-mismatch".into());', 'let _ = &d.gaps; // missing operation admission')],
    "wrapping-access-end": [(ZERO, "let end = address.checked_add(u64::from(access.access_width / 8));",
                            "let end = Some(address.wrapping_add(u64::from(access.access_width / 8)));")],
    "omit-lower-range": [(ZERO, "if end.is_none_or(|end| end > 0x0000800000000000) {", "if false {")],
    "reported-equals-ea-only": [(ZERO, "at < address || at >= end", "at != address || at >= end")],
    "inclusive-reported-end": [(ZERO, "at < address || at >= end", "at < address || at > end")],
    "unknown-becomes-refuted": [(WRAP,
        "let conclusion = if !d.gaps.is_empty() || d.arithmetic.is_none() {\n            ZeroAddressConclusion::Unknown",
        "let conclusion = if !d.gaps.is_empty() || d.arithmetic.is_none() {\n            ZeroAddressConclusion::RefutedUnderPremises")],
    "evidence-budget-facts": [
        (WRAP, "data.truncate(limits.max_evidence);", "let omitted_fact_source = data.clone();\n    data.truncate(limits.max_evidence);"),
        (WRAP, "let result = AddressWrapAssessment::construct(", "let mut result = AddressWrapAssessment::construct("),
        (WRAP, "result.validate()?;", """if !result.inputs_complete {
        result.arithmetic = decision(&bound.fault.fault.metadata, &bound.question, &omitted_fact_source).arithmetic;
    }
    result.validate()?;""")],
    "claim-budget-facts": [(WRAP, "d.arithmetic = None;", "// deliberately retain arithmetic after mandatory claim omission")],
    "zero-budget-skips-binding": [(WRAP,
        "// Binding validity precedes every output budget, including zero.",
        """if limits.max_evidence == 0 && limits.max_claims == 0 {
        return Ok(AddressWrapAssessment::construct(
            bound.identity().clone(), bound.question.clone(), bound.fault.fault.clone(),
            (bound.fault.fault.digest(), receipt_digest(bound.receipt.as_ref())),
            1 + bound.fault.fault.data.len() + usize::from(bound.receipt.is_some()),
            Vec::new(), limits,
        ));
    }
    // Binding validity incorrectly follows the zero-budget return.""")],
    "skip-wide-recomputation": [(WRAP, "if self != &expected {", """let mut expected = expected;
        expected.arithmetic = self.arithmetic.clone();
        expected.content_id = self.content_id.clone();
        if self != &expected {""")],
    "skip-reference-closure": [(WRAP, "if self != &expected {", """let mut expected = expected;
        expected.claims = self.claims.clone();
        expected.content_id = self.content_id.clone();
        if self != &expected {""")],
    "question-seed-is-root": [(CLI,
        "if let Some(site) = args.assess_wrap_site {\n        args.seeds.insert(site);",
        "if let Some(site) = args.assess_wrap_site {\n        args.entries.insert(site);\n        args.seeds.insert(site);")],
}


def frozen_mutations():
    record = read_json(FIXTURES / "mutations.json")
    rows = record["records"]
    names = [row["name"] for row in rows]
    require(record["schema"] == "ariadne.i5c-w0-mutations/v1" and record["count"] == 24,
            "changed frozen mutation contract")
    require(len(names) == len(set(names)) == 24 and set(names) == set(MUTATIONS),
            "mutation inventory must contain all 24 frozen defects")
    return rows


def transformed(root, name):
    result = {}
    for filename, old, new in MUTATIONS[name]:
        text = result.get(filename, (Path(root) / filename).read_text())
        require(text.count(old) == 1, "nonunique mutation seam: " + name + ": " + filename)
        require(old != new, "mutation is a no-op: " + name)
        result[filename] = text.replace(old, new, 1)
    return result


def observer(case):
    if case.startswith("serialization:"):
        return ("test", "reports_address_wrap"), "w5_selected_frozen_serialized_mutation_case"
    if case.startswith("cli:"):
        return ("test", "input_address_wrap_cli"), case.removeprefix("cli:").replace("-", "_")
    return ("lib", "ariadne"), "investigation::address_wrap::unit_tests::w5_selected_frozen_mutation_case"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check-anchors", action="store_true", help="source preparation only; no mutation credit")
    args = parser.parse_args()
    work = args.output.resolve()
    work.mkdir(parents=True, exist_ok=False)
    before = sources()
    rows, failure = [], None
    expected = frozen_mutations()
    preflight = None
    try:
        for row in expected:
            transformed(ROOT, row["name"])
        if not args.check_anchors:
            preflight = prerequisite_report()
            write_json(work / "prerequisites.json", preflight)
            require(preflight["passed"], "native/dependency prerequisites unavailable")
            control = work / "control/sut"
            observers = copy_sut(control)
            binaries = {}
            for row in expected:
                name, case = row["name"], row["observer_case"]
                selector, test = observer(case)
                if selector not in binaries:
                    target = ROOT / "target/i5c-mutations" / work.name / "control"
                    binaries[selector] = build_test(work / "control" / selector[1], selector, target, root=control)
                env = {**environment(), "ARIADNE_I5C_MUTATION_CASE": case,
                       "ARIADNE_CLI_TEST_OUTPUT_ROOT": str(work / name / "cli-artifacts")}
                positive, stdout, _ = observe(work / name / "positive", binaries[selector]["path"], test, env=env)
                if not case.startswith("cli:"):
                    require(('"case":"' + case + '"') in stdout, "positive observer case differs")
                sut = work / name / "sut"
                copied = copy_sut(sut)
                require(copied == observers, "copied observers differ from positive control")
                edits = transformed(sut, name)
                for filename, text in edits.items():
                    (sut / filename).write_text(text)
                changes = {filename: {"before": artifact(ROOT / filename)["sha256"],
                                      "after": artifact(sut / filename)["sha256"]} for filename in edits}
                target = ROOT / "target/i5c-mutations" / work.name / name
                binary = build_test(work / name / "compiled", selector, target, root=sut)
                require(binary["sha256"] != binaries[selector]["sha256"], "mutant executable equals control")
                negative, stdout, _ = observe(work / name / "negative", binary["path"], test, env=env, failed=True)
                if not case.startswith("cli:"):
                    require(('"case":"' + case + '"') in stdout, "mutant observer case differs")
                require(unchanged_observers(sut, observers) and unchanged_observers(control, observers),
                        "independent observer sources changed")
                rows.append({**row, "detected": True, "positive": positive,
                             "negative": negative, "changes": changes})
                write_json(work / "progress.json", {"completed": rows, "expected": 24, "passed": False})
                print(name + ": detected", flush=True)
            require(prerequisite_report()["tools"] == preflight["tools"], "native tools changed")
            require(sources() == before, "source inventory changed")
    except (OSError, ValueError, KeyError) as error:
        failure = str(error)
    passed = not args.check_anchors and failure is None and len(rows) == 24
    record = {"schema": "ariadne.i5c-mutations/v1", "passed": passed,
              "sourcePreparationPassed": failure is None, "executionPerformed": not args.check_anchors and preflight is not None and preflight["passed"],
              "sourceHashes": before, "sourcesStable": sources() == before,
              "expectedMutants": [row["name"] for row in expected], "mutants": rows,
              "compileFailuresCredited": False, "failure": failure,
              "qualificationEnvironment": preflight["qualificationEnvironment"] if preflight else None}
    write_json(work / "report.json", record)
    print("Report:", work / "report.json", flush=True)
    return 0 if passed or args.check_anchors and failure is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
