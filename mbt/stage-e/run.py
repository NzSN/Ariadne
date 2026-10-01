#!/usr/bin/env python3
"""Exercise Stage E fixture bindings through real negotiated MirrorRust replay."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from tools import ROOT, mirrors_tools, run, sha256, work_directory, write_json  # noqa: E402
from prepare import prepare_model  # noqa: E402


def main():
    run([sys.executable, HERE / "prepare.py", "--check"], timeout=180)
    mirrors, compiler, mirror = mirrors_tools()
    work = work_directory("stage-e-replay")
    model_dir = prepare_model(work)
    print(f"Stage E replay logs: {work}", flush=True)
    executable = HERE / "target/debug/ariadne-stage-e-mbt"
    reports = {}
    sources = [*sorted((ROOT / "src").glob("*.rs")), *sorted((HERE / "src").glob("*.rs")),
               *sorted((HERE / "tests").glob("*.rs")), HERE / "Cargo.toml", HERE / "Cargo.lock",
               HERE / "run.py", HERE / "prepare.py", HERE / "test_projection.py"]
    source_hashes = {str(path.relative_to(ROOT)): sha256(path) for path in sources}
    client = ROOT.parent / "MirrorRust"
    client_sources = [client / "Cargo.toml", *sorted((client / "src").glob("*.rs"))]
    client_hashes = {str(path.relative_to(client)): sha256(path) for path in client_sources}
    corpus_digest = sha256(HERE / "corpus/manifest.json")
    corpus_manifest = json.loads((HERE / "corpus/manifest.json").read_text())
    artifact_hashes = corpus_manifest["artifacts"]
    oracle_hashes = corpus_manifest["oracleSources"]
    checks = [
        [sys.executable, HERE / "test_projection.py"],
        ["cargo", "fmt", "--manifest-path", HERE / "Cargo.toml", "--", "--check"],
        ["cargo", "test", "--offline", "--locked", "--manifest-path", HERE / "Cargo.toml"],
        ["cargo", "clippy", "--offline", "--locked", "--manifest-path", HERE / "Cargo.toml", "--all-targets", "--", "-D", "warnings"],
    ]
    for index, command in enumerate(checks):
        run(command, log=work / f"check-{index}.log", timeout=180)
    run(["cargo", "build", "--offline", "--locked", "--manifest-path", HERE / "Cargo.toml"], log=work / "build.log", timeout=180)
    for engine, model in [("machine-state", "MachineStateReplay"), ("llvm-ir", "LLVMIRReplay")]:
        trace = HERE / "corpus" / f"{model}.itf.json"
        for mode in ("good", "wrong-digest"):
            output = run([executable, engine, mode, mirror, model_dir / f"{model}.tla", HERE / "corpus" / f"{model}.lock.json", trace, trace], expected=(0, 1), log=work / f"{engine}-{mode}.log")
            report = json.loads(output.stdout.splitlines()[-1])
            if output.returncode != 0 or not report["gatePassed"]:
                raise RuntimeError(f"Stage E {engine} {mode} acceptance failed: {report}")
            reports[f"{engine}:{mode}"] = report
            print(f"{engine} {mode}: {report['status']}; {report['observationsDispatched']} observations", flush=True)
    if any(sha256(ROOT / path) != digest for path, digest in source_hashes.items()) or any(sha256(client / path) != digest for path, digest in client_hashes.items()):
        raise RuntimeError("implementation/client sources changed during replay")
    if sha256(HERE / "corpus/manifest.json") != corpus_digest or any(sha256(HERE / path) != digest for path, digest in artifact_hashes.items()) or any(sha256(ROOT / path) != digest for path, digest in oracle_hashes.items()):
        raise RuntimeError("oracle sources/artifacts changed during replay")
    report = {
        "schema": "ariadne.stage-e-mirrorrust-integration/v1", "passed": True,
        "scope": "two existing fixtures, repeated initialization and wrong-digest admission; no Stage E completion claim",
        "reports": reports, "sourceHashes": source_hashes, "mirrorrustSourceHashes": client_hashes,
        "checks": [{"command": [str(part) for part in command], "exitCode": 0} for command in checks],
        "corpusManifestSha256": corpus_digest, "oracleSourceHashes": oracle_hashes,
        "artifactHashes": artifact_hashes,
        "executableSha256": sha256(executable), "logs": str(work),
        "tools": {
            "mirrorrustRevision": run(["git", "rev-parse", "HEAD"], cwd=client).stdout.strip(),
            "mirrorsRevision": run(["git", "rev-parse", "HEAD"], cwd=mirrors).stdout.strip(),
            "mirrorSha256": sha256(mirror), "compilerSha256": sha256(compiler),
            "rustc": run(["rustc", "--version"]).stdout.strip(),
        },
    }
    (HERE / "results").mkdir(exist_ok=True)
    write_json(HERE / "results/latest.json", report)
    print(f"Stage E MirrorRust integration passed: {HERE / 'results/latest.json'}")


if __name__ == "__main__":
    main()
