"""One pinned capture-only regression workload; no prior-run result is consumed."""
import hashlib
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CASE_RELATIVE = "tests/input/fixtures/workloads/real-capture-workload-case.json"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_case():
    case = json.loads((ROOT / CASE_RELATIVE).read_text())
    if case.get("schema") != "ariadne.real-capture-workload-case/v1":
        raise ValueError("unsupported active real-capture manifest")
    capture, query, expected = case["capture"], case["query"], case["expectations"]
    if (capture["platform"] not in {"windows", "linux"}
            or capture["architecture"] != "amd64"
            or type(capture["bytes"]) is not int or capture["bytes"] <= 0
            or re.fullmatch(r"[0-9a-f]{64}", capture["sha256"]) is None
            or any(re.fullmatch(r"0x[0-9a-f]{16}", query[key]) is None
                   for key in ["entry_va", "seed_va", "producer_va"])
            or query["memory_access_index"] != 0
            or query["address_register"] not in {"r8", "rbx"}
            or type(expected["decodedStarts"]) is not int or expected["decodedStarts"] <= 1
            or expected["phaseBudgetMs"] != 250):
        raise ValueError("invalid active capture identity/query/budget")
    # Explicit regression expectations identify the selected test input. No old
    # inspector's passed flag or output log can stand in for a fresh test.
    if (capture["sha256"] != "0333e29bfed1608ac877395d191642947aacc58dd81d0b786e0fd0df1a131f90"
            or capture["bytes"] != 516256
            or query["entry_va"] != "0x00007ff63cba6c50"):
        raise ValueError("active capture differs from the regression input")
    return case


def source_paths():
    case = load_case()
    return [Path(__file__), ROOT / CASE_RELATIVE]


def selected_dump(case, hash_file=sha):
    path = Path(os.environ.get("ARIADNE_REAL_CAPTURE_DUMP") or ROOT / case["capture"]["path"])
    if (hash_file(path) != case["capture"]["sha256"]
            or path.stat().st_size != case["capture"]["bytes"]):
        raise ValueError("active real-capture bytes do not match the selected pin")
    return path


def validate_report(report, case):
    query, expected = case["query"], case["expectations"]
    analysis = report["analysis"]
    if (report["identity"]["artifact_sha256"] != case["capture"]["sha256"]
            or report["identity"]["platform"] != case["capture"]["platform"]
            or report["query"]["entries"] != [query["entry_va"]]
            or report["query"]["seeds"] != [query["seed_va"]]
            or len(analysis["decoded"]) != expected["decodedStarts"]
            or len(set(analysis["decoded"])) != expected["decodedStarts"]
            or len(analysis["edges"]) != expected["edges"]
            or analysis["missing_slice_seeds"]
            or query["seed_va"] not in analysis["decoded"]
            or query["producer_va"] not in analysis["slice"]):
        raise ValueError("active real-capture query/producer/coverage mismatch")
    sites = {site["va"]: site for site in report["preparation"]["sites"]}
    if any(sites[va]["byte_source"] != "captured" for va in analysis["decoded"]):
        raise ValueError("active real-capture decoded bytes lack captured provenance")
    for va, key in [(query["producer_va"], "producerBytesHex"), (query["seed_va"], "faultBytesHex")]:
        if sites[va]["bytes_hex"] != expected[key]:
            raise ValueError("active real-capture independent instruction witness differs")
    definitions = next(row["definitions"] for row in analysis["reaching"]
                       if row["before"] == query["seed_va"])
    if not all(any(d["loc"] == f"gpr:{query['address_register']}:{byte}"
                   and d["site"] == query["producer_va"] and d["origin"] == "instruction"
                   for d in definitions) for byte in range(8)):
        raise ValueError("active real-capture address origins omit the independent producer")
