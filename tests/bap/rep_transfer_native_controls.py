#!/usr/bin/env python3
"""Compile current native policy controls and exercise all proof transports.

Run on the qualified SDK host. Supplied typed BIL checks the extractor contract;
it does not qualify the BAP REP lift or concrete machine execution.
"""
import argparse
import os
import signal
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "native/bap-core/capture.ml"
DRIVER = r'''
open Recovery
let variable name width virtual_ = `Assoc ["name",`String name;"index",`Int 0;
  "virtual",`Bool virtual_;"width",`Int width;"type",`String "imm"]
let read var = `Assoc["kind",`String "var";"var",var]
let number n = `Assoc["kind",`String "int";"value",`String(n^":64u")]
let move var value = `Assoc["kind",`String "move";"var",var;"value",value]
let loop body = `Assoc["kind",`String "while";"condition",number "0";"body",`List body]
let branch yes = `Assoc["kind",`String "if";"condition",number "1";
  "yes",`List yes;"no",`List []]
let key=Capture.tkey
let unknown term = Capture.opname term="unknown"
let constant n term = Capture.tconstant term=Some n
let rax=variable "RAX" 64 false and rbx=variable "RBX" 64 false
let rdx=variable "RDX" 64 false and tmp=variable "temporary" 64 true
let derive statements = Capture.transfer_from_bil "0x0000000000401000" (`List statements)
let baseline () = derive [move rax(number "4096");move tmp(number "8192");
  move rdx(number "12288");loop [move rax(number "16384");
    branch [loop [move tmp(number "20480")]]];move rbx(read tmp);
  `Assoc["kind",`String "jump";"target",read rax]]
let refusal advanced profile expected =
  let request=`Assoc["capture",`Assoc["sites",`List[
    `Assoc["projection",`String profile]]]] in
  try ignore(Capture.admit_resolved ~advanced request "snapshot");false with
  | Invalid message -> message=expected
let rep_target_error = "repeated-string source extension does not admit target resolution"
let rep_composed_error = "repeated-string source extension does not admit composed proof transport"
let capture profile rows = `Assoc["sites",`List rows] |> fun base ->
  match profile with None->base|Some profile->`Assoc(("semantic_profile",`String profile)::fields base)
let projection profile = `Assoc["projection",profile]
let positive_captures = List.concat_map(fun profile->[
  profile^"-overall-empty",capture(Some("producer:"^profile^":runtime"))[];
  profile^"-overall-all-null",capture(Some("producer:"^profile^":runtime"))[projection `Null];
  profile^"-rows-only",capture None[projection(`String profile)];
  profile^"-exact-token",capture(Some profile)[]])
  ["bap-bit-provenance-v12";"bap-bit-provenance-v13";"bap-bit-provenance-v14";"bap-bit-provenance-v15"]
let negative_captures = List.map(fun(label,profile)->label,capture(Some profile)[])[
  "v120","producer:bap-bit-provenance-v120:runtime";
  "v12suffix","producer:bap-bit-provenance-v12suffix:runtime";
  "embedded","producer:prefix-bap-bit-provenance-v12:runtime";
  "v130","producer:bap-bit-provenance-v130:runtime";
  "v13suffix","producer:bap-bit-provenance-v13suffix:runtime";
  "embedded-v13","producer:prefix-bap-bit-provenance-v13:runtime";
  "v140","producer:bap-bit-provenance-v140:runtime";
  "v14suffix","producer:bap-bit-provenance-v14suffix:runtime";
  "embedded-v14","producer:prefix-bap-bit-provenance-v14:runtime";
  "v150","producer:bap-bit-provenance-v150:runtime";
  "v15suffix","producer:bap-bit-provenance-v15suffix:runtime";
  "embedded-v15","producer:prefix-bap-bit-provenance-v15:runtime";
  "v8-v11","producer:bap-bit-provenance-v8:bap-bit-provenance-v11:runtime"]
let direct_target advanced captured expected =
  let has=Capture.has_repeated_projection captured in
  let request=`Assoc["capture",captured]in
  try ignore(Capture.admit_resolved ~advanced request "snapshot");false with
  | Invalid message -> has=expected && ((message=rep_target_error)=expected)
let direct_wrapper checker captured expected =
  let request=`Assoc["capture",captured]in
  try ignore(checker request "snapshot");false with
  | Invalid message -> (message=rep_composed_error)=expected
let run name test =
  let passed=try test() with _ -> false in
  `Assoc["case",`String name;"passed",`Bool passed]
let () =
  let original = [
    run "zero-or-many-iterations-havoc-architectural" (fun () ->
      let outputs,jump,_=baseline() in
      unknown(get outputs(key rax)) && unknown jump);
    run "nested-virtual-write-havocs-later-copy" (fun () ->
      let outputs,_,_=baseline() in unknown(get outputs(key rbx)) &&
      not(List.mem_assoc(key tmp)(fields outputs)));
    run "unwritten-output-retains-constant" (fun () ->
      let outputs,_,_=baseline() in constant 12288L(get outputs(key rdx)));
    run "nested-flag-writes-remain-possible" (fun () ->
      let cf=variable "CF" 1 false and zf=variable "ZF" 1 false in
      let one=`Assoc["kind",`String "int";"value",`String "1:1u"] in
      let outputs,_,_=derive [loop [branch[move cf one;loop[move zf one]]]] in
      unknown(get outputs(key cf)) && unknown(get outputs(key zf)) &&
      Capture.width(get outputs(key cf))=1 && Capture.width(get outputs(key zf))=1);
    run "nested-loop-write-invalidates-stable-address" (fun () ->
      let statements=[loop [branch[loop[move rax(number "1")]]]] in
      Capture.writes_address_bil(S.singleton(key rax))statements &&
      not(Capture.writes_address_bil(S.singleton(key rdx))statements) &&
      Capture.memory_write_bil statements);
    run "non-loop-transfer-keeps-existing-behavior" (fun () ->
      let outputs,jump,_=derive[move tmp(number "8192");move rax(read tmp);
        `Assoc["kind",`String "jump";"target",read rax]] in
      constant 8192L(get outputs(key rax)) && constant 8192L jump);
    run "plain-rep-refused-before-proof-dispatch" (fun () ->
      refusal false "bap-bit-provenance-v12"
        "repeated-string source extension does not admit target resolution");
    run "advanced-rep-refused-before-proof-dispatch" (fun () ->
      refusal true "bap-bit-provenance-v12"
        "repeated-string source extension does not admit target resolution");
    run "basic-v9-refusal-preserved" (fun () ->
      refusal false "bap-bit-provenance-v9"
        "source flag extension does not admit target resolution")
  ] in
  let target_controls = List.concat_map(fun advanced->
    List.concat_map(fun(expected,captures)->List.map(fun(label,captured)->
      run ("direct-target-"^string_of_bool advanced^"-"^label)
        (fun()->direct_target advanced captured expected))captures)
      [true,positive_captures;false,negative_captures])[false;true] in
  let wrapper_controls = List.concat_map(fun(name,checker)->
    List.concat_map(fun(expected,captures)->List.map(fun(label,captured)->
      run ("direct-"^name^"-"^label)
        (fun()->direct_wrapper checker captured expected))captures)
      [true,positive_captures;false,negative_captures])
    ["guard",Guard.admit;"composition",Composition.admit] in
  let rows=original@target_controls@wrapper_controls in
  print_endline(Yojson.Safe.to_string(`List rows));
  if List.exists(fun row->get row "passed"<>`Bool true)rows then exit 1
'''


PROOF_PROFILES = [
    "captured-indirect-targets/v1", "captured-guarded-input/v1",
    "captured-guarded-targets/v1", "captured-guarded-targets/v2",
    "captured-guarded-input/v2", "captured-guarded-targets/v3",
    "captured-indirect-targets/v2", "captured-guarded-input/v3",
    "captured-guarded-targets/v4",
]
REFUSAL = "repeated-string source extension does not admit composed proof transport"
SOURCE_NAMES = ["capture.ml", "guard.ml", "composition.ml", "main.ml"]
REPEATED_PROFILES = ["bap-bit-provenance-v12", "bap-bit-provenance-v13", "bap-bit-provenance-v14", "bap-bit-provenance-v15"]
UNIT_CONTROLS = 125
DISPATCH_CONTROLS = 216


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def profile_query(snapshot, profile, value):
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(b"ariadne.bap-core-query/v1\0")
    for part in (snapshot, "recovery", profile, canonical):
        encoded = part.encode()
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    return digest.hexdigest()


def bounded_run(command, directory, environment, text=None, timeout=120):
    process = subprocess.Popen(command, cwd=directory, env=environment, text=True,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, start_new_session=True)
    try:
        stdout, stderr = process.communicate(text, timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        return {"status": "timeout", "returncode": process.returncode,
                "stdout": stdout, "stderr": stderr}
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
    return {"status": "completed", "returncode": process.returncode,
            "stdout": stdout, "stderr": stderr}


def dispatch_control(helper, profile, repeated_profile, capture_kind, malformed, environment, output):
    label = "-".join((profile.replace("/", "-"), repeated_profile, capture_kind,
                      "malformed-proof" if malformed else "missing-proof"))
    if capture_kind == "rows-only":
        capture = {"sites": [{"projection": repeated_profile}]}
    else:
        capture = {"semantic_profile": "producer:" + repeated_profile + ":runtime",
                   "sites": [] if capture_kind == "empty" else [{"projection": None}]}
    value = {"capture": capture}
    if malformed:
        value.update(target_resolution=[], guard_admission=None, composition={})
    snapshot = "rep-policy-snapshot"
    session = "rep-policy-" + label
    query = profile_query(snapshot, profile, value)
    request = {"schema": "ariadne.bap-core/v1", "session": session,
               "snapshot": snapshot, "query": query, "family": "recovery",
               "sequence": 0, "operation": "initialize",
               "payload": {"profile": profile, "input": value}}
    observation = bounded_run([str(helper), session, snapshot, query, "recovery"],
                              output, environment, json.dumps(request) + "\n", timeout=5)
    for stream in ("stdout", "stderr"):
        (output / (label + "." + stream)).write_text(observation[stream])
    passed = False
    try:
        frames = [json.loads(line) for line in observation["stdout"].splitlines()]
        ready, response = frames
        passed = (observation["status"] == "completed" and observation["returncode"] == 0
                  and ready["schema"] == "ariadne.bap-core-ready/v1"
                  and all(response[key] == request[key] for key in
                          ("schema", "session", "snapshot", "query", "family", "sequence"))
                  and response["error"] == {"kind": "semantic", "message": REFUSAL}
                  and response["generation"] == 1 and response["action_index"] == 0
                  and response["changed"] is False and response["result"] is None)
    except (ValueError, KeyError, TypeError):
        pass
    return {"case": label, "passed": passed, "status": observation["status"],
            "returncode": observation["returncode"], "query": query}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-dir", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, default=ROOT / "native/bap-core")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    native, source, output = (args.native_dir.resolve(), args.source_dir.resolve(),
                              args.output.resolve())
    if not output.is_relative_to(ROOT / "target"):
        raise SystemExit("native control products must remain under target/")
    output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((native / "manifest.json").read_text())
    source_hashes = {name: sha(source / name) for name in SOURCE_NAMES}
    if any(manifest["handshake"]["source_hashes"][name] != digest
           for name, digest in source_hashes.items()):
        raise SystemExit("native helper does not match selected policy source")
    helper = native / "ariadne-bap-core"
    if manifest["helper_sha256"] != sha(helper):
        raise SystemExit("native helper identity does not match its build manifest")
    spec = importlib.util.spec_from_file_location("rep_sdk", ROOT / "native/bap-core/setup-sdk.py")
    sdk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sdk)
    environment = sdk.environment()
    environment["OCAMLFIND_CONF"] = str(sdk.PREFIX / "lib/findlib.conf")
    compiler = str(sdk.PREFIX / "bin/ocamlfind")
    (output / "rep_controls.ml").write_text(DRIVER)
    report = {
        "schema": "ariadne.rep-transfer-native-controls/v1",
        "source_hashes": source_hashes, "runner_sha256": sha(Path(__file__)),
        "driver_sha256": hashlib.sha256(DRIVER.encode()).hexdigest(),
        "native_manifest_sha256": sha(native / "manifest.json"),
        "helper_sha256": sha(helper),
        "scope": "Supplied typed BIL extraction and direct/full-transport profile refusal.",
        "passed": False,
    }
    command = [compiler, "ocamlopt", "-linkpkg", "-package", "bap,yojson",
               "-I", str(native), "-o", "rep-controls",
               *[str(native / (name + ".cmx")) for name in
                 ("build_identity", "recovery", "terminal", "legacy_capture", "capture",
                  "legacy_guard", "guard", "legacy_composition", "loop_closure",
                  "legacy_composition_v2", "composition")], "rep_controls.ml"]
    try:
        compilation = bounded_run(command, output, environment)
        for stream in ("stdout", "stderr"):
            (output / ("compile." + stream)).write_text(compilation[stream])
        if compilation["status"] != "completed" or compilation["returncode"]:
            report.update(status="compile-failed", returncode=compilation["returncode"])
        else:
            observed = bounded_run([str(output / "rep-controls")], output, environment)
            for stream in ("stdout", "stderr"):
                (output / ("direct." + stream)).write_text(observed[stream])
            controls = json.loads(observed["stdout"])
            dispatch = [dispatch_control(helper, profile, repeated_profile, capture_kind, malformed,
                                         environment, output)
                        for profile in PROOF_PROFILES
                        for repeated_profile in REPEATED_PROFILES
                        for capture_kind in ("empty", "all-null", "rows-only")
                        for malformed in (False, True)]
            report.update(status="observed", controls=controls, dispatch_controls=dispatch,
                          passed=(observed["status"] == "completed"
                                  and observed["returncode"] == 0
                                  and len(controls) == UNIT_CONTROLS
                                  and len(dispatch) == DISPATCH_CONTROLS
                                  and all(row["passed"] is True for row in controls + dispatch)))
    except (ValueError, KeyError, TypeError, OSError) as error:
        report.update(status="unqualified", error=str(error))
    report["sources_stable"] = all(sha(source / name) == digest
                                    for name, digest in source_hashes.items())
    report["passed"] = report["passed"] and report["sources_stable"]
    (output / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "status": report.get("status"),
                      "controls": len(report.get("controls", [])),
                      "dispatch_controls": len(report.get("dispatch_controls", []))}))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
