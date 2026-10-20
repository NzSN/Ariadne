#!/usr/bin/env python3
"""Remote-only compiled completion mutations with exact positive controls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
RUST = [
    ("weak-write-kill", "src/completion.rs",
     "for loc in &request.instructions[&va].must_defs {",
     "for loc in &request.instructions[&va].may_defs {",
     "completion", "bounded_completion_avoids_repeated_address_order_waves"),
    ("call-only-flow", "src/completion.rs", "if edge.kind.is_local() {", "if true {",
     "completion", "completion_preserves_cycle_origins_and_excludes_call_only_flow"),
    ("lost-cycle-work", "src/completion.rs", "if changed {", "if false && changed {",
     "completion", "completion_preserves_cycle_origins_and_excludes_call_only_flow"),
    ("unbound-universe", "src/bap/core_protocol.rs",
     "if !expected.iter().eq(universe.iter()) {", "if false {",
     "lib", "bap::core_protocol::dictionary_tests::bitmap_completion_is_lossless_and_rejects_tampered_membership_and_universe"),
]
NATIVE = [
    ("native-weak-write-kill", ")(M.find va i.instructions).must;", ")(M.find va i.instructions).may;"),
    ("native-call-only-flow", 'if kind<>"call" then', "if true then"),
    ("native-entry-loss", "if S.mem va i.roots then S.iter", "if false then S.iter"),
    ("native-bitmap-loss", "then value:= !value lor(1 lsl bit)", "then value:= !value"),
]
NATIVE_TEST = "native_compact_completion_matches_independent_reference_from_every_prefix"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def observe(command, cwd, log, env=None):
    started = time.monotonic()
    try:
        p = subprocess.run(command, cwd=cwd, env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, text=True, timeout=900)
        output, code = p.stdout, p.returncode
    except subprocess.TimeoutExpired as error:
        output, code = error.stdout or b"", None
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
    log.write_text(output)
    binaries = {}
    for line in output.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("reason") == "compiler-artifact" and row.get("executable"):
            binaries[row["executable"]] = sha(row["executable"])
    return {"command": command, "exit": code, "seconds": time.monotonic()-started,
            "log_sha256": sha(log), "executables": binaries}, output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    assert output.is_relative_to(ROOT/"target")
    output.mkdir(parents=True, exist_ok=args.resume)
    records = []
    source = {str(p.relative_to(ROOT)): sha(p) for tree in ("src", "tests", "native", "tools")
              for p in (ROOT/tree).rglob("*") if p.is_file()
              and not {"__pycache__", "target"}.intersection(p.parts)}
    inventory = output/"source-inventory.json"
    if args.resume:
        assert json.loads(inventory.read_text()) == source
    else:
        inventory.write_text(json.dumps(source, indent=2)+"\n")

    def credited(record, text, test, positive):
        assert record["executables"], "no compiled observer"
        if positive:
            assert record["exit"] == 0 and f"test {test} ... ok" in text
        else:
            assert record["exit"] == 101 and "panicked at" in text and "test result: FAILED" in text
            assert re.search(r"^    "+re.escape(test)+r"$", text, re.MULTILINE)

    def save():
        (output/"report.json").write_text(json.dumps({"schema": "ariadne.completion-mutations/v1",
            "passed": len(records)==len(RUST)+len(NATIVE), "records": records}, indent=2)+"\n")

    for name, file, before, after, target, test in RUST:
        case = output/name
        if args.resume and (case/"result.json").is_file():
            records.append(json.loads((case/"result.json").read_text())); save(); continue
        case.mkdir(exist_ok=args.resume)
        sut = case/"sut"
        if sut.exists():
            shutil.rmtree(sut)
        sut.mkdir()
        for tree in ("src", "tests", "native", "Specs"):
            shutil.copytree(ROOT/tree, sut/tree, ignore=shutil.ignore_patterns("__pycache__", "target"))
        for item in ("Cargo.toml", "Cargo.lock"):
            shutil.copyfile(ROOT/item, sut/item)
        manifest = sut/"Cargo.toml"
        manifest.write_text(manifest.read_text().replace('path = "../MirrorRust"',
            'path = '+json.dumps(str(ROOT.parent/"MirrorRust"))))
        command = ["cargo", "test", "--offline", "--locked", "--no-default-features"]
        command += ["--features", "bap", "--lib"] if target=="lib" else ["--test", target]
        command += ["--message-format=json", "--target-dir", str(case/"build"), test,
                    "--", "--exact", "--nocapture", "--test-threads=1"]
        control, text = observe(command, sut, case/"control.log")
        credited(control, text, test, True)
        path = sut/file; original = path.read_text(); assert original.count(before)==1, name
        path.write_text(original.replace(before, after, 1))
        mutant, text = observe(command, sut, case/"mutant.log")
        credited(mutant, text, test, False)
        record = {"name": name, "test": test, "source_sha256": sha(path),
                  "control": control, "mutant": mutant, "behavior_rejected": True}
        (case/"result.json").write_text(json.dumps(record, indent=2)+"\n")
        records.append(record);save();print(name, "compiled behavior rejected", flush=True)

    observer_target = ROOT/"target/qualification-completion-mutant-observers"
    for name, before, after in NATIVE:
        case = output/name
        if args.resume and (case/"result.json").is_file():
            records.append(json.loads((case/"result.json").read_text()));save();continue
        case.mkdir(exist_ok=args.resume)
        command = ["cargo", "test", "--offline", "--locked", "--test", "bap_core_analysis",
                   "--message-format=json", "--target-dir", str(observer_target), NATIVE_TEST,
                   "--", "--exact", "--ignored", "--nocapture", "--test-threads=1"]
        env = dict(os.environ, ARIADNE_BAP_CORE_DIR=str(ROOT/"target/qualification-native"))
        control, text = observe(command, ROOT, case/"control.log", env)
        credited(control, text, NATIVE_TEST, True)
        sut = case/"native-source"
        if sut.exists():shutil.rmtree(sut)
        shutil.copytree(ROOT/"native/bap-core", sut, ignore=shutil.ignore_patterns("__pycache__"))
        path=sut/"dense_completion.ml";text=path.read_text();assert text.count(before)==1,name
        path.write_text(text.replace(before, after, 1))
        helper=case/"helper"
        build, text=observe(["python3",str(ROOT/"native/bap-core/build.py"),"--source-dir",str(sut),
                            "--output",str(helper)], ROOT, case/"build.log")
        assert build["exit"]==0 and (helper/"ariadne-bap-core").is_file(), "mutant did not compile"
        env["ARIADNE_BAP_CORE_DIR"]=str(helper)
        mutant, text=observe(command, ROOT, case/"mutant.log", env)
        credited(mutant, text, NATIVE_TEST, False)
        record={"name":name,"test":NATIVE_TEST,"source_sha256":sha(path),
                "helper_sha256":sha(helper/"ariadne-bap-core"),"control":control,
                "build":build,"mutant":mutant,"behavior_rejected":True}
        (case/"result.json").write_text(json.dumps(record,indent=2)+"\n")
        records.append(record);save();print(name,"compiled behavior rejected",flush=True)
    assert source=={name:sha(ROOT/name) for name in source}, "source changed"
    print("Completion mutation PASS:",len(records),flush=True)


if __name__ == "__main__":
    main()
