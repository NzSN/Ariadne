"""Active Windows I4 case, independent provenance and capture-only inputs."""
import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]
CASE_RELATIVE = "evidence/Ariadne/investigation-windows-workload-case.json"
INSPECTION_RELATIVE = "evidence/Ariadne/i4-windows-capture-inspection.json"
ARCHIVE_RELATIVE = "evidence/Ariadne/bap-windows-workload-inputs.tar.gz"
CASE_SCHEMA = "ariadne.investigation-windows-workload-case/v1"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def case_digest(case):
    raw = json.dumps(case, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def validate_case(case):
    import re
    digest = lambda x: isinstance(x, str) and re.fullmatch(r"[0-9a-f]{64}", x) is not None
    address = lambda x: isinstance(x, str) and re.fullmatch(r"0x[0-9a-f]{16}", x) is not None
    if (case.get("schema") != CASE_SCHEMA
            or case.get("id") != "crashpad-windows-checksum-98-i4-v1"
            or case.get("captureKind") != "controlled-crashpad-windows"):
        raise ValueError("wrong active Windows I4 case identity")
    capture, query, expected = case["capture"], case["query"], case["expectations"]
    if (not digest(capture.get("sha256")) or type(capture.get("bytes")) is not int
            or capture["bytes"] <= 0 or capture.get("platform") != "windows"
            or capture.get("architecture") != "amd64"
            or any(not address(query.get(k)) for k in ("entry_va", "seed_va", "producer_va"))
            or type(query.get("memory_access_index")) is not int or query["memory_access_index"] != 0):
        raise ValueError("invalid Windows I4 artifact or query")
    if (type(expected.get("decodedStarts")) is not int or expected["decodedStarts"] != 98
            or type(expected.get("windowsBudgetMs")) is not int or expected["windowsBudgetMs"] != 2000
            or expected.get("timingPolicy") != "bounded"):
        raise ValueError("Windows I4 requires 98 starts and the fixed 2000 ms contract")
    archive = case["inputArchive"]
    if (archive.get("path") != ARCHIVE_RELATIVE or not digest(archive.get("sha256"))
            or archive.get("captureMember") != "capture.dmp"
            or archive.get("companionMember") != "ariadne_crash_demo.exe"
            or not isinstance(archive.get("entries"), dict)):
        raise ValueError("invalid Windows I4 input bundle")
    inspection = case["independentInspection"]
    if inspection.get("path") != INSPECTION_RELATIVE or not digest(inspection.get("sha256")):
        raise ValueError("invalid Windows I4 independent inspection pin")
    return case


def load_case():
    return validate_case(json.loads((ROOT / CASE_RELATIVE).read_text()))


def materialize(case, directory, override=None):
    """Validate all bundled inputs; the PE is comparison evidence, never fallback."""
    validate_case(case)
    archive_path = ROOT / ARCHIVE_RELATIVE
    if sha(archive_path) != case["inputArchive"]["sha256"]:
        raise ValueError("Windows I4 input archive digest mismatch")
    inspection_path = ROOT / INSPECTION_RELATIVE
    if sha(inspection_path) != case["independentInspection"]["sha256"]:
        raise ValueError("Windows I4 independent inspection changed")
    inspection = json.loads(inspection_path.read_text())
    if (inspection.get("passed") is not True or inspection.get("independently_decoded_starts") != 98
            or any(inspection["query"].get(k) != case["query"][k]
                   for k in ("entry_va", "seed_va", "producer_va"))
            or inspection["inputs"]["dump"]["sha256"] != case["capture"]["sha256"]
            or inspection["inputs"]["executable"]["sha256"] != case["companion"]["sha256"]
            or inspection["query"].get("memory_access_index") != case["query"]["memory_access_index"]):
        raise ValueError("Windows I4 independent witness disagrees with the active pin")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    entries = case["inputArchive"]["entries"]
    with tarfile.open(archive_path, "r:gz") as bundle:
        members = bundle.getmembers()
        if (len(members) != len(entries) or {m.name for m in members} != set(entries)
                or any(not m.isfile() for m in members)):
            raise ValueError("Windows I4 bundle inventory mismatch")
        for member in members:
            relative = Path(member.name)
            if relative.is_absolute() or ".." in relative.parts or member.size > 8 * 1024 * 1024:
                raise ValueError("unsafe Windows I4 bundle member")
            raw = bundle.extractfile(member).read()
            if hashlib.sha256(raw).hexdigest() != entries[member.name]:
                raise ValueError("Windows I4 bundle member digest mismatch: " + member.name)
            output = directory / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(raw)
    dump = directory / "capture.dmp"
    if sha(dump) != case["capture"]["sha256"] or dump.stat().st_size != case["capture"]["bytes"]:
        raise ValueError("Windows I4 capture identity mismatch")
    if (sha(directory / "ariadne_crash_demo.exe") != case["companion"]["sha256"]
            or sha(directory / "witness.json") != inspection["inputs"]["witness"]["sha256"]):
        raise ValueError("Windows I4 companion or witness identity mismatch")
    if override is not None:
        dump = Path(override).resolve()
        if sha(dump) != case["capture"]["sha256"] or dump.stat().st_size != case["capture"]["bytes"]:
            raise ValueError("Windows I4 override does not match the active capture")
    return dump
