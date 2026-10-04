#!/usr/bin/env python3
"""Mutate actual OCaml state/serialization and Rust sequence validation."""
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from rust_layout import copy_sut

ROOT = Path(__file__).resolve().parents[1]


def sources():
    names = ["src/bap/core_session.rs", "src/bap/core_protocol.rs", "src/bap/mod.rs",
             "tests/bap/core_bootstrap.rs", "Cargo.toml", "Cargo.lock",
             "tools/check_bap_ocaml_mutations.py", "tools/rust_layout.py"]
    paths = [ROOT / name for name in names]
    paths.extend(p for p in (ROOT / "native/bap-core").iterdir() if p.is_file())
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def run(command, log, env=None):
    result = subprocess.run([str(x) for x in command], cwd=ROOT, env=env,
                            text=True, capture_output=True, timeout=600)
    text = result.stdout + result.stderr
    log.write_text(text)
    return result.returncode, text


def main():
    before = sources()
    base = ROOT / "target/bap-core-mutations"
    base.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="run-", dir=base))
    source = ROOT / "native/bap-core"
    test_source = ROOT / "tests/bap/core_bootstrap.rs"
    observer_hash = hashlib.sha256(test_source.read_bytes()).hexdigest()
    env = {**os.environ, "ARIADNE_BAP_CORE_DIR": os.environ.get("ARIADNE_BAP_CORE_DIR", str(ROOT / "target/bap-core-native"))}
    cmd = ["cargo", "test", "--offline", "--locked", "--test", "bap_core_bootstrap"]
    code, _ = run(cmd + ["--", "--ignored"], work / "baseline.log", env)
    if code:
        raise SystemExit("mutation baseline failed: " + str(work))
    cache = str(work / "stale-state.bin")
    mutants = [
        ("lost-term-snapshot", "project_state.ml", "Term.set_attr block snapshot_tag snapshot",
         'Term.set_attr block snapshot_tag "wrong"', "native_full_observations"),
        ("omit-visit", "recovery.ml", "let visited = S.add a s.visited in",
         "let visited = s.visited in", "native_full_observations"),
        ("previous-observation", "main.ml", "Recovery.observe i s, Project_state.attribution p snapshot",
         "Recovery.observe i (Recovery.init i), Project_state.attribution p snapshot", "native_full_observations"),
        ("signed-address-order", "recovery.ml", "module S = Set.Make(String)",
         "module S = Set.Make(struct type t = string let compare x y = if String.length x=18 && String.length y=18 && String.sub x 0 2=\"0x\" && String.sub y 0 2=\"0x\" then Int64.compare (Int64.of_string x) (Int64.of_string y) else String.compare x y end)",
         "native_failures_and_unsigned_schedule"),
        ("collapse-parallel-edges", "recovery.ml",
         "module E = Set.Make(struct type t = string * string * string let compare = compare",
         "module E = Set.Make(struct type t = string * string * string let compare (a,b,_) (x,y,_) = compare (a,b) (x,y)",
         "native_full_observations"),
        ("observe-mutates", "main.ml", '| "observe" -> exact payload []',
         '| "observe" -> exact payload []; let i,s,p = match Option.get !owned with Core (i,s,p) -> i,s,p | _ -> raise (Invalid \"family\") in owned := Some (Core (i,{s with pending=S.empty},p))',
         "native_full_observations"),
        ("reset-preserves-state", "main.ml", "Core (input, Recovery.init input, Project_state.create ~sites snapshot input_json)",
         'let state = if Sys.file_exists ' + json.dumps(cache) + ' then (let c = open_in_bin '
         + json.dumps(cache) + ' in let s = Marshal.from_channel c in close_in c; s) else Recovery.init input in\n'
         + '            Core (input, state, Project_state.create ~sites snapshot input_json)', "native_rejections_and_fresh_sessions"),
    ]
    rows = []
    for name, file, old, new, test in mutants:
        directory = work / name
        directory.mkdir()
        for item in source.glob("*.ml"):
            shutil.copyfile(item, directory / item.name)
        path = directory / file
        original = path.read_text()
        if original.count(old) != 1:
            raise SystemExit("nonunique mutation anchor: " + name)
        mutated = original.replace(old, new)
        if name == "reset-preserves-state":
            old_reset = '| "reset" -> exact payload []; reset := true'
            assert mutated.count(old_reset) == 1
            mutated = mutated.replace(old_reset,
                '| "reset" -> exact payload []; let s = match Option.get !owned with Core (_,s,_) -> s | _ -> raise (Invalid "family") in let c = open_out_bin '
                + json.dumps(cache) + ' in Marshal.to_channel c s []; close_out c; reset := true')
        path.write_text(mutated)
        (directory / "mutation.diff").write_text("".join(difflib.unified_diff(
            original.splitlines(True), mutated.splitlines(True), fromfile=file, tofile=file)))
        code, _ = run(["python3", source / "build.py", "--source-dir", directory,
                       "--output", directory / "build"], directory / "compile.log")
        if code:
            raise SystemExit("mutant did not build: " + name)
        mutant_env = {**env, "ARIADNE_BAP_CORE_DIR": str(directory / "build")}
        code, output = run(cmd + [test, "--", "--exact", "--ignored", "--nocapture"],
                           directory / "assertion.log", mutant_env)
        assertion = "signed scheduling accepted" if name == "signed-address-order" else "assertion"
        killed = code == 101 and f"test {test} ... FAILED" in output and (assertion in output or "panicked at" in output) and "could not compile" not in output
        rows.append({"mutation": name, "assertionRejected": killed, "test": test,
                     "buildPassed": True, "exitCode": code})
        print(name, "rejected" if killed else "NOT DETECTED", flush=True)
    sut = work / "rust-sut"
    manifest = copy_sut(sut)
    path = sut / "src/bap/core_session.rs"
    original = path.read_text()
    old = "|| response.sequence != self.sequence"
    assert original.count(old) == 1
    mutated = original.replace(old, "|| false")
    path.write_text(mutated)
    (work / "stale-sequence.diff").write_text("".join(difflib.unified_diff(
        original.splitlines(True), mutated.splitlines(True), fromfile=str(path), tofile=str(path))))
    rust_cmd = ["cargo", "test", "--offline", "--locked", "--manifest-path", manifest,
                "--target-dir", work / "rust-build", "--test", "bap_core_bootstrap",
                "transport_failure_controls", "--", "--exact", "--ignored", "--nocapture"]
    code, output = run(rust_cmd, work / "stale-sequence.log", env)
    killed = (code == 101 and "accepted transport fault: sequence" in output
              and "could not compile" not in output)
    rows.append({"mutation": "accept-stale-sequence", "assertionRejected": killed,
                 "test": "transport_failure_controls", "exitCode": code})
    unchanged = observer_hash == hashlib.sha256(test_source.read_bytes()).hexdigest()
    unchanged &= observer_hash == hashlib.sha256((sut / "tests/bap/core_bootstrap.rs").read_bytes()).hexdigest()
    stable = before == sources()
    report = {"schema": "ariadne.bap-core-bootstrap-mutations/v1", "mutations": rows,
              "sourcesStable": stable, "sourceHashes": before,
              "observersUnchanged": unchanged, "observerSha256": observer_hash,
              "passed": stable and unchanged and all(row["assertionRejected"] for row in rows)}
    (work / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print("Report:", work / "report.json")
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
