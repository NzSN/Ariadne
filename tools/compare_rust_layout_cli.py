#!/usr/bin/env python3
"""Compare current CLI reports with preserved pre-consolidation executables."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from rust_layout import ROOT, source_files


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    work = Path(tempfile.mkdtemp(prefix="ariadne-layout-cli-"))
    before = {str(p.relative_to(ROOT)): sha(p) for p in sorted(source_files())}
    old = ROOT / "target/legacy-packages/input/target/release/ariadne-minidump"
    new = ROOT / "target/release/ariadne-minidump"
    decoder = ROOT / "target/ariadne-llvm-mc"
    rows = []
    cases = [
        ("linux", ROOT / "tests/input/fixtures/stage_b_linux.dmp", "0x401000", "0x401006"),
        ("windows", ROOT / "tests/input/fixtures/stage_b_windows.dmp", "0x7ff700001000", "0x7ff700001006"),
        ("not-chain", ROOT / "tests/input/fixtures/bap_precision_linux.dmp", "0x401000", "0x401006"),
        ("real-linux", ROOT / "tmp/priority1/chromium-member-uaf.dmp", "0x566817922dc5", "0x566817922e42"),
    ]
    for case, dump, entry, site in cases:
        for mode in ("analysis", "explanation"):
            for format in ("text", "json", "dot"):
                args = [str(dump), "--decoder-reference", str(decoder), "--entry", entry,
                        "--seed", site, "--format", format]
                if mode == "explanation":
                    args += ["--explain-fault-address", site, "--memory-access", "0", "--explanation-only"]
                outputs = []
                for label, executable in (("before", old), ("after", new)):
                    result = subprocess.run([str(executable), *args], cwd=ROOT,
                                            capture_output=True, timeout=180)
                    assert result.returncode == 0, result.stderr.decode()
                    path = work / f"{case}-{mode}-{format}-{label}.out"
                    path.write_bytes(result.stdout)
                    outputs.append(result.stdout)
                assert outputs[0] == outputs[1], f"Changed {case}/{mode}/{format}: {work}"
                rows.append({"case": case, "mode": mode, "format": format,
                             "artifactSha256": sha(dump), "outputSha256": sha(path),
                             "outputBytes": len(outputs[1]), "identical": True})
        print(f"{case}: all six report/explanation formats identical", flush=True)
    old_ir = ROOT / "target/legacy-packages/ir/target/debug/ariadne-ir"
    new_ir = ROOT / "target/release/ariadne-ir"
    helper = ROOT / "target/ariadne-llvm-ir"
    for fixture in ("diamond.ll", "diamond.bc"):
        for format in ("text", "json", "dot"):
            args = [str(ROOT / "tests/ir/fixtures" / fixture), "--helper", str(helper),
                    "--function", "diamond", "--seed", "i11", "--format", format]
            outputs = []
            for label, executable in (("before", old_ir), ("after", new_ir)):
                result = subprocess.run([str(executable), *args], cwd=ROOT,
                                        capture_output=True, timeout=60)
                assert result.returncode == 0, result.stderr.decode()
                path = work / f"{fixture}-{format}-{label}.out"
                path.write_bytes(result.stdout)
                outputs.append(result.stdout)
            assert outputs[0] == outputs[1], f"Changed {fixture}/{format}: {work}"
            rows.append({"case": fixture, "mode": "ir", "format": format,
                         "outputSha256": sha(path), "identical": True})
    stable = all(sha(ROOT / name) == digest for name, digest in before.items())
    report = {"schema": "ariadne.rust-layout-cli-equivalence/v1", "passed": stable,
              "sourcesStable": stable, "sourceHashes": before, "cases": rows,
              "executables": {str(p.relative_to(ROOT)): sha(p) for p in (old, new, old_ir, new_ir, decoder, helper)},
              "scope": "Exact CLI output equivalence for four minidump workloads and supplied text/bitcode IR; original Windows98 capture remains unavailable."}
    (work / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Report:", work / "report.json", flush=True)
    assert stable, "source changed during comparison"


if __name__ == "__main__":
    main()
