"""Derive Windows I4 qualification from bound explanation-CLI measurements."""
import math
import re
import statistics
from investigation_windows_case import case_digest, validate_case

WINDOWS_BUDGET_MS = 2000
WORKLOAD_SCHEMA = "ariadne.investigation-workload/v3"


def _timing(value):
    if type(value) not in (int, float) or value < 0:
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def windows_qualification(workload, case):
    """Recompute the budget outcome; stored medians/success flags are not authority.

    The caller separately checks source/tool identities and other acceptance gates.
    Old or incomplete records cannot establish full Windows acceptance.
    """
    result = dict(checked=workload.get("windows98Checked") is True, status="unavailable",
                  valid=False, samples=0, medianMs=None, budgetMs=WINDOWS_BUDGET_MS,
                  caseId=case.get("id"), captureKind=case.get("captureKind"),
                  targetMet=False, reason="Active pinned Windows I4 capture has not been exercised.")
    if not result["checked"]:
        return result

    def invalid(reason):
        result.update(status="invalid", reason="Windows timing evidence invalid or incomplete: " + reason)
        return result

    try:
        validate_case(case)
    except (ValueError, KeyError, TypeError):
        return invalid("active Windows I4 case is malformed")

    if workload.get("schema") != WORKLOAD_SCHEMA:
        return invalid("a v3 workload record with raw CLI samples is required")
    if workload.get("windowsCaseDigest") != case_digest(case) or workload.get("windowsCaseId") != case["id"]:
        return invalid("Windows workload belongs to another capture pin")
    if workload.get("passed") is not True or workload.get("sourcesStable") is not True:
        return invalid("workload checks and source stability must pass")
    if workload.get("analysisBackend") != "bap" or workload.get("toolsStable") is not True:
        return invalid("native BAP selection and stable measured tools are required")
    if workload.get("profile") != "release" or workload.get("windows98BudgetMs") != WINDOWS_BUDGET_MS:
        return invalid("release profile and the fixed 2000 ms budget are required")
    repeats, warmups = workload.get("repeats"), workload.get("warmups")
    if type(repeats) is not int or repeats < 5 or type(warmups) is not int or warmups < 1:
        return invalid("at least five measured repeats after warm-up are required")
    records = workload.get("records")
    if not isinstance(records, list) or any(not isinstance(r, dict) for r in records):
        return invalid("missing workload records")
    selected = [r for r in records if r.get("workload") == "real-windows-98"
                and r.get("mode") == "explanation"]
    if len(selected) != 1:
        return invalid("exactly one real-windows-98 explanation-CLI record is required")
    record = selected[0]
    if record.get("analysisBackend") != "bap" or record.get("decodedStarts") != 98:
        return invalid("the active native 98-instruction explanation workload is required")
    identity, query = record.get("identity"), record.get("query")
    question = record.get("question")
    if not isinstance(identity, dict) or not isinstance(query, dict):
        return invalid("missing artifact/query identity")
    if (record.get("artifactSha256") != case["capture"]["sha256"]
            or identity.get("artifact_sha256") != case["capture"]["sha256"]
            or not _digest(identity.get("query_id"))
            or not _digest(record.get("outputSha256"))
            or query.get("entries") != [case["query"]["entry_va"]]
            or query.get("seeds") != [case["query"]["seed_va"]]
            or not isinstance(question, dict) or type(question.get("memory_access")) is not int
            or question != {"site": case["query"]["seed_va"], "memory_access": 0}):
        return invalid("artifact, entry, seed or selected question does not match the pinned query")
    samples, warmup_samples = record.get("elapsedSamplesMs"), record.get("warmupSamplesMs")
    if (not isinstance(samples, list) or len(samples) != repeats
            or not isinstance(warmup_samples, list) or len(warmup_samples) != warmups
            or not all(_timing(x) for x in samples + warmup_samples)):
        return invalid("sample counts must match and all timings must be finite and nonnegative")
    median = statistics.median(samples)
    summary = record.get("elapsedMs")
    expected = {"median": median, "min": min(samples), "max": max(samples)}
    if (not isinstance(summary, dict) or type(summary.get("samples")) is not int
            or summary["samples"] != len(samples)
            or any(not _timing(summary.get(k)) or summary[k] != v
                   for k, v in expected.items())):
        return invalid("summary does not match the raw measured samples")
    met = median <= WINDOWS_BUDGET_MS
    result.update(status="met" if met else "over-budget", valid=True,
                  samples=len(samples), medianMs=median, targetMet=met,
                  reason="" if met else f"Windows explanation-CLI median {median:g} ms exceeds the fixed 2000 ms budget.")
    return result
