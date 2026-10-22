#!/usr/bin/env python3
"""Survey actual AMD64 projection coverage without equating unknowns with support.

Default: validate the catalogue and report all byte forms as unexercised.
--native: compile/run the production Backend::prepare observer in an isolated
Cargo target directory. Generated JSON/logs belong in a fresh --output directory.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from run_output import run_output

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "tests/bap/fixtures/amd64-semantics/catalogue.json"
SCHEMA = "ariadne.amd64-semantics-catalogue/v1"
SUBSETS = {"general-purpose", "system", "media-128-256-512", "media-64", "x87"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def validate_catalogue(catalogue):
    if catalogue.get("schema") != SCHEMA or catalogue.get("exhaustiveEncodingCoverage") is not False:
        raise ValueError("wrong catalogue schema or exhaustive-coverage claim")
    if set(catalogue.get("architecturalSubsets", [])) != SUBSETS:
        raise ValueError("all five architectural subsets must be named")
    references = {r["id"] for r in catalogue["references"]}
    families = {}
    for family in catalogue["families"]:
        if (family["id"] in families or family["subset"] not in SUBSETS
                or family["reference"] not in references):
            raise ValueError("duplicate or unbound family")
        families[family["id"]] = family
    cases = {}
    covered = set()
    for case in catalogue["cases"]:
        if (not re.fullmatch(r"[a-z0-9-]+", case["id"]) or case["id"] in cases
                or case["family"] not in families or case["mode"] != "long-64"
                or not case["assembly"]
                or not re.fullmatch(r"(?:[0-9a-f]{2}){1,15}", case["bytes"])):
            raise ValueError("invalid, duplicate or unbound byte case")
        effects = case.get("expectedEffects")
        if effects is not None:
            if (set(effects) != {"uses", "mayDefs", "mustDefs"}
                    or any(not isinstance(v, list) or v != sorted(set(v))
                           or any(not isinstance(x, str) for x in v) for v in effects.values())
                    or not set(effects["mustDefs"]) <= set(effects["mayDefs"])
                    or not case.get("expectationBasis")):
                raise ValueError("invalid independent effect expectation")
        cases[case["id"]] = case
        covered.add(case["family"])
    if covered != set(families) or {f["subset"] for f in families.values()} != SUBSETS:
        raise ValueError("family or architectural subset lacks a byte representative")
    return cases


def classify(case, row):
    if row is None:
        return "unexercised"
    if row.get("error") is not None:
        return "query-error"
    semantic = row.get("semantic") or {}
    gaps = semantic.get("gaps", [])
    status = semantic.get("status")
    if status == "projected" and row.get("decodable") is True:
        if row.get("consumedBytes") != case["bytes"] or row.get("length") != len(case["bytes"]) // 2:
            return "encoding-disagreement"
        return "supported-projection"
    if status in {"opaque-ordinary", "opaque-call-return"} and row.get("decodable") is True:
        return "conservative-unknown"
    if any("empty lift is not an admitted no-op" in gap for gap in gaps):
        return "missing-producer-lift"
    if any("namespace" in gap or "architectural variable" in gap for gap in gaps):
        return "unsupported-state"
    if status in {"decode-disagreement", "operand-binding-disagreement", "invalid-decode"}:
        return "encoding-disagreement"
    if status == "normal-flow-terminal":
        return "scoped-terminal"
    return "unsupported-control-or-semantics"


def bind_native(catalogue, catalogue_sha, native):
    cases = validate_catalogue(catalogue)
    if (native.get("schema") != "ariadne.amd64-semantics-native-probe/v1"
            or native.get("catalogueSha256") != catalogue_sha
            or native.get("target") != "windows-amd64"):
        raise ValueError("native probe identity differs")
    for key in ("decoderSha256", "helperSha256"):
        if not re.fullmatch("[0-9a-f]{64}", native.get(key, "")):
            raise ValueError("missing native tool identity")
    rows = {}
    for index, row in enumerate(native["rows"]):
        name = row.get("id")
        if name not in cases or name in rows or row.get("bytes") != cases[name]["bytes"]:
            raise ValueError("native case missing, duplicate or changed")
        if name != catalogue["cases"][index]["id"] or row.get("address") != f"0x{0x401000+index*32:016x}":
            raise ValueError("native case order/address differs")
        if row.get("error") is None:
            semantic = row.get("semantic")
            if semantic is not None:
                if (semantic.get("fallback") is not None
                        or semantic.get("backend") != "bap-x86-legacy"
                        or semantic.get("helperSha256") != native["helperSha256"]):
                    raise ValueError("native semantic source differs")
            effects = row.get("effects", {})
            if (set(effects) != {"uses", "mayDefs", "mustDefs"}
                    or any(not isinstance(v, list) or v != sorted(set(v)) for v in effects.values())
                    or not set(effects["mustDefs"]) <= set(effects["mayDefs"])):
                raise ValueError("invalid native effect sets")
        rows[name] = row
    if set(rows) != set(cases):
        raise ValueError("native probe does not cover the exact catalogue")
    return rows


def summarize(catalogue, native_rows=None):
    validate_catalogue(catalogue)
    native_rows = native_rows or {}
    rows = []
    for case in catalogue["cases"]:
        observed = native_rows.get(case["id"])
        status = classify(case, observed)
        expected = case.get("expectedEffects")
        match = None if expected is None or observed is None else (
            status == "supported-projection" and observed.get("effects") == expected)
        rows.append(dict(id=case["id"], family=case["family"], bytes=case["bytes"],
                         assembly=case["assembly"], status=status,
                         independentEffectExpectation=expected is not None,
                         expectedEffectsMatch=match, observation=observed))
    counts = dict(sorted(Counter(row["status"] for row in rows).items()))
    return dict(
        schema="ariadne.amd64-semantics-survey/v1", profile=catalogue["profile"],
        scope=catalogue["scope"], familyCount=len(catalogue["families"]),
        caseCount=len(rows), statusCounts=counts,
        probeComplete=len(native_rows) == len(rows),
        fullAmd64Support=False, exhaustiveEncodingCoverage=False,
        qualification="Projection observations are not independent ISA-correctness or execution-history proofs.",
        independentExpectations=sum(row["independentEffectExpectation"] for row in rows),
        expectationMismatches=[row["id"] for row in rows if row["expectedEffectsMatch"] is False],
        rows=rows)


def source_identity():
    files = [ROOT / "Cargo.toml", ROOT / "Cargo.lock", Path(__file__),
             ROOT / "tests/bap/amd64_semantics_probe.rs"]
    for directory in ("src", "native/bap", "native/llvm_mc"):
        files.extend(p for p in (ROOT / directory).rglob("*")
                     if p.is_file() and p.suffix in {".rs", ".cpp", ".h", ".json", ".sh", ".py"})
    return {str(path.relative_to(ROOT)): sha(path) for path in sorted(set(files))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogue", type=Path, default=CATALOGUE)
    parser.add_argument("--output", type=Path, required=True, help="fresh disposable work directory")
    parser.add_argument("--native", action="store_true", help="exercise actual production preparation")
    args = parser.parse_args(argv)
    catalogue = strict_json(args.catalogue.read_text())
    validate_catalogue(catalogue)
    output = run_output(args.output)
    output.mkdir(parents=True, exist_ok=False)
    before = source_identity()
    catalogue_sha = sha(args.catalogue)
    native_rows, failure, native = None, None, None
    if args.native:
        env = dict(os.environ,
                   ARIADNE_SEMANTICS_CATALOGUE=str(args.catalogue.resolve()),
                   ARIADNE_SEMANTICS_PROBE_OUTPUT=str(output / "native.json"))
        command = ["cargo", "test", "--offline", "--locked", "--target-dir",
                   str(ROOT / "target/amd64-semantics-probe"), "--test", "bap_amd64_semantics_probe",
                   "--", "--ignored", "--exact", "probe_catalogue", "--nocapture"]
        with (output / "native.stdout").open("w") as stdout, (output / "native.stderr").open("w") as stderr:
            process = subprocess.run(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr, check=False)
        if process.returncode:
            failure = f"native observer exited {process.returncode}; see native.stdout/native.stderr"
        else:
            try:
                native = strict_json((output / "native.json").read_text())
                native_rows = bind_native(catalogue, catalogue_sha, native)
            except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
                failure = "invalid native observer result: " + str(error)
    after = source_identity()
    if before != after or sha(args.catalogue) != catalogue_sha:
        failure = "source/catalogue changed during probe; observations are not accepted"
        native_rows = None
    report = summarize(catalogue, native_rows)
    report.update(catalogueSha256=catalogue_sha, sourceSha256=before,
                  sourceStable=before == after, nativeRequested=args.native,
                  operationalFailure=failure,
                  nativeTools=None if native is None else {
                      k: native.get(k) for k in ("decoderSha256", "helperSha256")})
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"families": report["familyCount"], "cases": report["caseCount"],
                      "statusCounts": report["statusCounts"], "operationalFailure": failure,
                      "fullAmd64Support": False, "report": str(output / "report.json")}))
    return 2 if failure else 1 if report["expectationMismatches"] else 0


if __name__ == "__main__":
    sys.exit(main())
