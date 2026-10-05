"""Shared identity and acceptance checks for native-default I5a qualification.

The native protocol query digest is distinct from the report query ID. CLI
receipts and phase rows must agree on both; neither may replace the other.
"""
import hashlib
import json
import os
from pathlib import Path
import re

from rust_layout import source_files

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "target/bap-core-native"
PROFILE = "captured-fixed-input/v1"
GATES = {
    "fixtures", "format", "root-tests", "core-tests", "clippy",
    "investigation-feature", "layout", "native-corpus-cli", "mutations",
    "equivalence", "measurements", "investigation", "native-contract-regressions",
    "controlled-contract-regressions",
}
TOOL_PATHS = (
    "target/release/ariadne-minidump", "target/release/i5a", "target/ariadne-llvm-mc",
    "target/ariadne-bap-lift", "tmp/bap-setup/stable/usr/local/lib/libbap.so.2.5.0",
    "target/bap-core-native/ariadne-bap-core", "target/bap-core-native/manifest.json",
    "native/bap-core/sdk.lock.json", "target/bap-core-sdk/sdk-manifest.json",
    "native/bap/toolchain.lock.json",
)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def strict_json(text):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON field: " + key)
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError("nonfinite JSON number: " + value)
    return json.loads(text, object_pairs_hook=unique, parse_constant=invalid_constant)


def source_inventory():
    paths = source_files()
    for tree in ("native/bap", "native/bap-core", "native/llvm_mc", "native/crashpad-demo"):
        paths.update(p for p in (ROOT / tree).rglob("*") if p.is_file()
                     and p.suffix != ".md" and "__pycache__" not in p.parts)
    paths.update((ROOT / "tools").glob("*i5a*.py"))
    paths.update(ROOT / name for name in (
        "tools/test_crashpad_assessment.py", "tools/check_rust_layout.py",
        "tools/check_investigation.py", "tools/check_investigation_mutations.py",
        "tools/measure_investigation.py", "tools/investigation_budget.py",
        "tools/test_investigation_budget.py",
        "tools/with_mirrorrust_snapshot.py",
        "tools/investigation_windows_case.py", "tools/test_investigation_windows_case.py",
        "evidence/Ariadne/investigation-windows-workload-case.json",
        "evidence/Ariadne/i4-windows-capture-inspection.json",
        "evidence/Ariadne/bap-windows-workload-inputs.tar.gz",
    ))
    return {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)}


def tool_hashes():
    return {name: sha(ROOT / name) for name in TOOL_PATHS}


def environment():
    return {**os.environ, "ARIADNE_BAP_CORE_DIR": str(CORE),
            "ARIADNE_LLVM_MC": str(ROOT / "target/ariadne-llvm-mc"),
            "ARIADNE_BAP_HELPER": str(ROOT / "target/ariadne-bap-lift"),
            "BAP_RUNTIME_ROOT": str(ROOT / "tmp/bap-setup/stable")}


def manifest_digest(manifest):
    """Canonical JSON hash, matching Rust serde_json::to_vec(Value)."""
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False).encode()).hexdigest()


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def native_manifest():
    manifest = strict_json((CORE / "manifest.json").read_text())
    handshake = manifest["handshake"]
    _require(manifest["schema"] == "ariadne.bap-core-build/v1", "wrong core manifest schema")
    _require(manifest["helper_sha256"] == sha(CORE / "ariadne-bap-core"), "core helper changed")
    _require(manifest["lock_sha256"] == sha(ROOT / "native/bap-core/sdk.lock.json"),
             "core SDK lock changed")
    sdk = ROOT / "target/bap-core-sdk/sdk-manifest.json"
    _require(handshake["sdk_manifest_sha256"] == sha(sdk), "core SDK manifest changed")
    expected = {name: sha(ROOT / "native/bap-core" / name) for name in
                ("recovery.ml", "stateflow.ml", "capture.ml", "project_state.ml", "main.ml")}
    _require(handshake["source_hashes"] == expected, "native core sources changed")
    lock = strict_json((ROOT / "native/bap-core/sdk.lock.json").read_text())
    _require(handshake["bap_revision"] == lock["bapSourceRevision"], "native core revision changed")
    _require(handshake["schema"] == "ariadne.bap-core-ready/v1"
             and type(handshake["abi"]) is int and handshake["abi"] == 2
             and handshake["families"] == ["recovery", "stateflow"]
             and handshake["profiles"] == ["normalized-fixed-input/v1", PROFILE],
             "unsupported core handshake")
    return manifest


def report_query_digest(report):
    digest = hashlib.sha256(b"ariadne-minidump-query-v1\0")
    digest.update(report["identity"]["snapshot_id"].encode())
    for name in ("entries", "seeds"):
        values = report["query"][name]
        _require(isinstance(values, list) and values == sorted(set(values))
                 and all(isinstance(v, str) and re.fullmatch(r"0x[0-9a-f]{16}", v)
                         for v in values), "noncanonical report query")
        digest.update(len(values).to_bytes(8, "little"))
        for value in values:
            digest.update(int(value, 16).to_bytes(8, "little"))
    for name in ("max_starts", "max_candidates", "max_prefix_bytes", "max_decoder_batches", "batch_size"):
        value = report["input"]["prepare_limits"][name]
        _require(type(value) is int and 0 <= value < 2**64, "invalid query limit")
        digest.update(value.to_bytes(8, "little"))
    return digest.hexdigest()


def validate_backend_receipt(report, manifest):
    """Validate a complete native report; never remove an unchecked receipt."""
    try:
        receipt = report["analysis_backend"]
        _require(isinstance(receipt, dict) and set(receipt) == {
            "schema", "backend", "snapshot", "query", "family", "profile", "build",
        }, "missing or unknown backend receipt field")
        _require(receipt["schema"] == "ariadne.analysis-backend/v1"
                 and receipt["backend"] == "bap" and receipt["profile"] == PROFILE
                 and receipt["family"] == "recovery", "wrong native backend/profile/family")
        _require(receipt["build"] == manifest and manifest_digest(receipt["build"]) == manifest_digest(manifest)
                 and manifest["schema"] == "ariadne.bap-core-build/v1"
                 and _digest(manifest["helper_sha256"]), "native build differs from pinned manifest")
        identity = report["identity"]
        _require(_digest(identity["artifact_sha256"])
                 and identity["snapshot_id"] == "minidump-captured-amd64-v1:" + identity["artifact_sha256"]
                 and receipt["snapshot"] == identity["snapshot_id"], "native snapshot/artifact mismatch")
        _require(_digest(receipt["query"]) and _digest(identity["query_id"])
                 and identity["query_id"] == report_query_digest(report), "native/report query identity mismatch")
        _require(report["analysis"]["phase"] == "done", "native analysis is not complete")
        return receipt
    except (KeyError, TypeError, OverflowError) as error:
        raise ValueError("malformed native backend receipt/report") from error


def validate_performance_contract(contract):
    for name, expected in (("warmups", 1), ("repeats", 5),
                           ("phaseMedianBudgetMs", 10), ("cliMedianBudgetMs", 1500)):
        _require(type(contract.get(name)) is int and contract[name] == expected,
                 "changed I5a performance contract: " + name)


def validate_phase_rows(rows, report, manifest, contract, *, conclusion=None, output_sha256=None):
    receipt = validate_backend_receipt(report, manifest)
    validate_performance_contract(contract)
    _require(len(rows) == contract["warmups"] + contract["repeats"], "missing phase samples")
    _require(len(report["query"]["entries"]) == len(report["query"]["seeds"]) == 1,
             "phase benchmark requires one entry and site")
    expected = {
        "artifact_sha256": report["identity"]["artifact_sha256"],
        "analysis_backend": "bap", "analysis_profile": PROFILE, "analysis_family": "recovery",
        "snapshot_id": report["identity"]["snapshot_id"], "query_id": report["identity"]["query_id"],
        "backend_query": receipt["query"], "helper_sha256": manifest["helper_sha256"],
        "manifest_sha256": manifest_digest(manifest), "entry": report["query"]["entries"][0],
        "site": report["query"]["seeds"][0], "memory_access": "0",
    }
    hashes = set()
    stable_fields = set()
    measured = []
    for index, row in enumerate(rows):
        _require(all(row.get(k) == v for k, v in expected.items()), "phase backend/query/build binding mismatch")
        _require(row.get("run") == str(index), "phase run sequence mismatch")
        values = {}
        for field in ("binding_ns", "assessment_ns", "render_ns", "total_ns", "evidence", "claims"):
            value = row.get(field)
            _require(isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]*", value),
                     "invalid phase count or timing: " + field)
            values[field] = int(value)
        _require(values["total_ns"] == sum(values[k] for k in ("binding_ns", "assessment_ns", "render_ns")),
                 "phase total differs from measured interval")
        _require(row.get("conclusion") in {"ConsistentWithEvidence", "RefutedUnderPremises", "Unknown"},
                 "invalid phase conclusion")
        if conclusion is not None:
            _require(row["conclusion"] == conclusion, "phase conclusion differs from independent oracle")
        _require(_digest(row.get("output_sha256")), "invalid phase output hash")
        if output_sha256 is not None:
            _require(row["output_sha256"] == output_sha256, "phase output differs from CLI assessment")
        hashes.add(row["output_sha256"])
        stable_fields.add((row["evidence"], row["claims"], row["conclusion"]))
        if index >= contract["warmups"]:
            measured.append(values["total_ns"] / 1e6)
    _require(len(hashes) == len(stable_fields) == 1, "nonrepeatable phase result")
    return measured


def validate_source_fixture_record(record, sources, tools, *, qualification_environment=None):
    _require(record.get("qualificationEnvironment") == qualification_environment,
             "source fixture qualification dependency differs")
    _require(record.get("schema") == "ariadne.i5a-acceptance/v2", "source fixture record must be native v2")
    for key in ("passed", "sourceFixtureAcceptancePassed", "sourcesStable", "toolsStable", "defaultNativeVerified"):
        _require(record.get(key) is True, "source fixture record did not pass: " + key)
    _require(record.get("analysisBackend") == "bap" and record.get("analysisProfile") == PROFILE,
             "source fixture record used another backend/profile")
    _require(record.get("sourceHashes") == sources and bool(sources), "source fixture inventory differs")
    _require(record.get("tools") == tools and set(tools) == set(TOOL_PATHS), "source fixture tool inventory differs")
    gates = record.get("gates", [])
    _require(len(gates) == len(GATES) and {g.get("gate") for g in gates} == GATES
             and all(type(g.get("exitCode")) is int and g["exitCode"] == 0 for g in gates),
             "source fixture gates incomplete")
    for name in ("measurements", "equivalence"):
        nested = record.get("records", {}).get(name, {})
        _require(nested.get("passed") is True and nested.get("defaultNativeVerified") is True
                 and nested.get("analysisBackend") == "bap" and nested.get("analysisProfile") == PROFILE,
                 "source fixture native evidence missing: " + name)
