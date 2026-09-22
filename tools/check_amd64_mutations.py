#!/usr/bin/env python3
"""Check that register-view semantic and proof gates reject deliberate defects.

All mutations live in a fresh temporary directory. Repository sources are never
modified. A missing checker, timeout, parser error, or socket failure is not a
successful mutation rejection.
"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(command, directory, log):
    result = subprocess.run(command, cwd=directory, text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=180, check=False)
    log.write_text(result.stdout)
    return result


def main():
    work = Path(tempfile.mkdtemp(prefix="ariadne-amd64-mutations-"))
    print(f"Mutation artifacts: {work}", flush=True)
    source = (ROOT / "Specs/AMD64RegisterViews.tla").read_text()
    mutations = {
        "preserve-dword-upper": ("ELSE IF view = Low32 THEN FALSE ELSE before[bit]", "ELSE before[bit]"),
        "wrong-high-byte": ("High8 == [offset |-> 8, width |-> 8]", "High8 == [offset |-> 0, width |-> 8]"),
    }
    for name, (old, new) in mutations.items():
        if source.count(old) != 1:
            raise SystemExit(f"Mutation anchor changed: {name}")
        directory = work / name
        directory.mkdir()
        (directory / "AMD64RegisterViews.tla").write_text(source.replace(old, new))
        for filename in ["AMD64RegisterViewsChecks.tla", "AMD64RegisterViews.cfg"]:
            shutil.copy2(ROOT / "Specs" / filename, directory / filename)
        result = run([os.environ.get("TLC", "tlc"), "-workers", "1", "-metadir", str(directory / "states"),
                      "-config", "AMD64RegisterViews.cfg", "AMD64RegisterViewsChecks.tla"],
                     directory, directory / "check.log")
        if result.returncode == 0 or "Invariant Safety is violated" not in result.stdout:
            raise SystemExit(f"Expected semantic invariant rejection for {name}; inspect {directory / 'check.log'}")
        print(f"rejected TLA+ mutation: {name}", flush=True)

    lean = (ROOT / "lean/AMD64/RegisterViews.lean").read_text()
    old = "else if view = .low32 then false else before bit"
    if lean.count(old) != 2:
        raise SystemExit("Lean mutation anchor changed")
    mutated = work / "BrokenZeroExtension.lean"
    mutated.write_text(lean.replace(old, "else before bit", 1))
    result = run(["lake", "env", "lean", str(mutated)], ROOT / "lean", work / "lean-proof.log")
    if result.returncode == 0 or "unsolved goals" not in result.stdout:
        raise SystemExit(f"Expected Lean proof failure; inspect {work / 'lean-proof.log'}")
    print("rejected Lean mutation: removed dword zero extension", flush=True)

    audit = (ROOT / "lean/Audit.lean").read_text().replace("import Lean\nimport AMD64\n", "")
    mutated = work / "ForbiddenAxiom.lean"
    mutated.write_text("import Lean\n" + lean + "\naxiom AMD64.unprovedStateClaim : False\n" + audit)
    result = run(["lake", "env", "lean", str(mutated)], ROOT / "lean", work / "lean-axiom.log")
    if result.returncode == 0 or "forbidden axiom AMD64.unprovedStateClaim" not in result.stdout:
        raise SystemExit(f"Expected axiom audit rejection; inspect {work / 'lean-axiom.log'}")
    print("rejected Lean mutation: unused unproved project axiom", flush=True)
    print("All four negative gates rejected their intended defects.", flush=True)


if __name__ == "__main__":
    main()
