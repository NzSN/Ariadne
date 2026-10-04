"""Validate the pinned controlled Windows BAP workload and derive its timing result."""
import math
import re
import statistics

WINDOWS_BUDGET_MS = None
WINDOWS_TIMING_POLICY = "unlimited"
WORKLOAD_SCHEMA = "ariadne.bap-workloads/v4"
WINDOWS_CASE_SCHEMA = "ariadne.bap-windows-workload-case/v1"
WINDOWS_WORKLOAD_ID = "crashpad-windows-checksum-98-v1"
WINDOWS_CAPTURE_KIND = "controlled-crashpad-windows"
WINDOWS_ARCHIVE_RELATIVE = "evidence/Ariadne/bap-windows-workload-inputs.tar.gz"


def _timing(value):
    if type(value) not in (int, float) or value < 0:
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _address(value):
    return isinstance(value, str) and re.fullmatch(r"0x[0-9a-f]{16}", value) is not None


def windows_case_error(case):
    """Return an error for an unsupported or malformed active BAP workload pin."""
    if not isinstance(case, dict):
        return "the pinned Windows manifest is malformed"
    if (case.get("schema") != WINDOWS_CASE_SCHEMA or case.get("id") != WINDOWS_WORKLOAD_ID
            or case.get("captureKind") != WINDOWS_CAPTURE_KIND):
        return "the active controlled Windows manifest identity is required"
    capture, query = case.get("capture"), case.get("query")
    if (not isinstance(capture, dict) or not _digest(capture.get("sha256"))
            or type(capture.get("bytes")) is not int or capture["bytes"] <= 0
            or not isinstance(query, dict)
            or any(not _address(query.get(name)) for name in ("entry_va", "seed_va", "producer_va"))):
        return "the pinned Windows artifact digest, size or canonical query is malformed"
    expectations = case.get("expectations")
    if (not isinstance(expectations, dict) or type(expectations.get("decodedStarts")) is not int
            or expectations["decodedStarts"] != 98 or expectations["decodedStarts"] < 64):
        return "the controlled Windows workload requires exactly 98 decoded starts"
    if ("windowsBudgetMs" not in expectations or expectations["windowsBudgetMs"] is not None
            or expectations.get("timingPolicy") != WINDOWS_TIMING_POLICY):
        return "the active Windows pin requires an explicit unlimited timing policy"
    archive = case.get("inputArchive")
    if (not isinstance(archive, dict) or archive.get("path") != WINDOWS_ARCHIVE_RELATIVE
            or not _digest(archive.get("sha256")) or archive.get("captureMember") != "capture.dmp"):
        return "the pinned Windows input archive identity is malformed"
    return None


def windows_qualification(workload, expected_case):
    """Check record consistency and recompute the measured median under the unlimited timing policy.

    This pure check does not authenticate files, source hashes or tool hashes.
    The caller must verify those bindings and apply its own stage-gate policy.
    Summary timings and stored qualification flags are never authoritative.
    """
    result = dict(checked=False, valid=False, targetMet=False, status="unavailable",
                  reason="Pinned controlled Windows BAP capture has not been exercised.",
                  medianMs=None, samples=0, budgetMs=WINDOWS_BUDGET_MS, timingPolicy=WINDOWS_TIMING_POLICY)

    def invalid(reason):
        result.update(status="invalid", reason="Windows workload evidence invalid or incomplete: " + reason)
        return result

    if not isinstance(workload, dict):
        return invalid("a workload object is required")
    checked = workload.get("windowsWorkloadChecked", False)
    result["checked"] = checked is True
    if type(checked) is not bool:
        return invalid("windowsWorkloadChecked must be a boolean")
    records = workload.get("records", [])
    if not isinstance(records, list) or any(not isinstance(record, dict) for record in records):
        return invalid("workload records must be a list of objects")
    selected = [record for record in records if record.get("workload") == WINDOWS_WORKLOAD_ID]
    if not checked:
        if selected:
            return invalid("a Windows record contradicts windowsWorkloadChecked=false")
        return result
    if workload.get("schema") != WORKLOAD_SCHEMA:
        return invalid("a v4 workload record with raw CLI samples is required")
    if workload.get("passed") is not True or workload.get("sourcesStable") is not True:
        return invalid("workload checks and source stability must pass")
    hashes = workload.get("sourceHashes")
    if (not isinstance(hashes, dict) or not hashes
            or any(not isinstance(path, str) or not path or not _digest(digest)
                   for path, digest in hashes.items())):
        return invalid("sourceHashes must be a nonempty map of source paths to SHA-256 digests")
    if (workload.get("profile") != "release"
            or "windowsWorkloadBudgetMs" not in workload
            or workload["windowsWorkloadBudgetMs"] is not None
            or workload.get("windowsWorkloadTimingPolicy") != WINDOWS_TIMING_POLICY):
        return invalid("release profile and explicit unlimited timing policy with a null budget are required")
    if (workload.get("semanticBackend") != "bap-only"
            or workload.get("llvmSemanticFallback") is not False):
        return invalid("the BAP-only backend without LLVM semantic fallback is required")
    repeats, warmups = workload.get("repeats"), workload.get("warmups")
    if type(repeats) is not int or repeats < 5 or type(warmups) is not int or warmups < 1:
        return invalid("at least five measured repeats and one warm-up are required")
    if len(selected) != 1:
        return invalid("exactly one active controlled Windows workload record is required")
    record = selected[0]
    if (record.get("backend") != "bap" or record.get("historicalCapture") is not False
            or record.get("captureKind") != WINDOWS_CAPTURE_KIND):
        return invalid("the controlled Windows capture must use the BAP backend and its explicit capture kind")

    error = windows_case_error(expected_case)
    if error:
        return invalid(error)
    if hashes.get(WINDOWS_ARCHIVE_RELATIVE) != expected_case["inputArchive"]["sha256"]:
        return invalid("the source-bound Windows input archive digest does not match the manifest")
    capture, case_query = expected_case["capture"], expected_case["query"]
    identity, query = record.get("identity"), record.get("query")
    if not isinstance(identity, dict) or not isinstance(query, dict):
        return invalid("missing artifact/query identity")
    if (record.get("artifactSha256") != capture["sha256"]
            or identity.get("artifact_sha256") != capture["sha256"]
            or not _digest(identity.get("query_id"))
            or identity.get("platform") != "windows"
            or identity.get("decoder_target") != "x86_64-pc-windows-msvc"
            or record.get("entry") != case_query["entry_va"]
            or record.get("seed") != case_query["seed_va"]
            or query.get("entries") != [case_query["entry_va"]]
            or query.get("seeds") != [case_query["seed_va"]]):
        return invalid("artifact, Windows target, entry or seed does not match the pinned query")
    report_hashes = record.get("reportSha256")
    if (not isinstance(report_hashes, dict)
            or any(not _digest(report_hashes.get(name))
                   for name in ("report.json", "report.txt", "report.dot"))):
        return invalid("all three output reports require SHA-256 digests")
    counts = record.get("counts")
    if (not isinstance(counts, dict)
            or any(type(counts.get(name)) is not int or counts[name] < 0
                   for name in ("decoded", "edges", "slice", "obligations"))
            or counts["decoded"] < 64 or counts["decoded"] != expected_case["expectations"]["decodedStarts"]):
        return invalid("nonnegative integer counts and exactly the pinned 98 decoded starts are required")

    samples, warmup_samples = record.get("elapsedSamplesMs"), record.get("warmupSamplesMs")
    if (not isinstance(samples, list) or len(samples) != repeats
            or not isinstance(warmup_samples, list) or len(warmup_samples) != warmups
            or not all(_timing(value) for value in samples + warmup_samples)):
        return invalid("sample counts must match and all timings must be finite and nonnegative")
    median = statistics.median(samples)
    summary = record.get("elapsedMs")
    expected = {"median": median, "min": min(samples), "max": max(samples)}
    if (not isinstance(summary, dict) or type(summary.get("samples")) is not int
            or summary["samples"] != len(samples)
            or any(not _timing(summary.get(name)) or summary[name] != value
                   for name, value in expected.items())):
        return invalid("summary does not match the raw measured samples")
    result.update(status="unlimited", valid=True,
                  samples=len(samples), medianMs=median, targetMet=True, reason="")
    return result
