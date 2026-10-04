"""Native protocol and isolated SDK negative controls for OQ qualification."""
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
A = "0x0000000000000010"
B = "0xfffffffffffffff0"


def fixture():
    return dict(snapshot="native-controls", addresses=[A, B], locations=[],
                entry_points=[A], slice_seeds=[B], input_kind="dump", captured=[A, B],
                file_backed=[], trusted_fallback=[], decodable=[A, B], instructions=[
                    dict(address=a, kind="return", fall=[], targets=[], targets_complete=True,
                         uses=[], may_defs=[], must_defs=[]) for a in (A, B)])


def envelope(sequence, operation, payload):
    return dict(schema="ariadne.bap-core/v1", session="controls", snapshot="native-controls",
                query="0" * 64, family="recovery", sequence=sequence, operation=operation, payload=payload)


def launch(directory, frames, log):
    env = dict(os.environ)
    for name in ("LD_LIBRARY_PATH", "LD_PRELOAD", "OCAMLPATH", "CAML_LD_LIBRARY_PATH"):
        env.pop(name, None)
    result = subprocess.run([str(directory / "ariadne-bap-core"), "controls", "native-controls",
                             "0" * 64, "recovery"], input=frames, capture_output=True,
                            text=True, env=env, timeout=15)
    log.write_text(result.stdout + "\nSTDERR\n" + result.stderr)
    return result


def native_controls(work):
    directory = ROOT / "target/bap-core-native"
    init = envelope(0, "initialize", {"profile": "normalized-fixed-input/v1", "input": fixture()})
    line = lambda obj: json.dumps(obj, separators=(",", ":")) + "\n"
    observe = envelope(1, "observe", {})
    controls = {}
    for key in ("snapshot", "query", "session", "family"):
        wrong = {**observe, key: "wrong"}
        controls["wrong-" + key] = line(init) + line(wrong)
    for sequence in (0, 2, -1):
        controls["sequence-" + str(sequence)] = line(init) + line({**observe, "sequence": sequence})
    controls["duplicate-envelope-key"] = line(init) + line(observe).replace('"sequence":1', '"sequence":1,"sequence":1')
    controls["duplicate-input-key"] = line(init).replace('"input_kind":"dump"', '"input_kind":"dump","input_kind":"dump"')
    controls["nonfinite"] = line(init).replace('"locations":[]', '"locations":[NaN]')
    controls["malformed"] = "{broken}\n"
    controls["partial"] = line(init).rstrip("\n")
    controls["oversized"] = " " * (8 * 1024 * 1024) + "\n"
    rows = []
    for name, frames in controls.items():
        result = launch(directory, frames, work / (name + ".log"))
        passed = result.returncode == 2 and "fatal:" in result.stderr
        rows.append({"control": name, "rejected": passed, "exitCode": result.returncode})
        if not passed:
            raise RuntimeError("native protocol control accepted: " + name)
    sequence = line(init) + line(envelope(1, "advance", {"action": "Visit", "address": A}))
    sequence += line(envelope(2, "observe", {})) + line(envelope(3, "reset", {}))
    traces = []
    for name in ("bap-core-native", "bap-core-native-clean"):
        result = launch(ROOT / "target" / name, sequence, work / (name + "-trace.log"))
        if result.returncode:
            raise RuntimeError("clean build native trace failed")
        trace = [json.loads(line) for line in result.stdout.splitlines()]
        # BAP TIDs identify terms, not stable machine addresses. Alpha-rename
        # only TIDs for cross-process comparison; all attribution facts remain.
        for response in trace[1:]:
            rows_by_id = {row["term"]: f"term-{i}" for i, row in enumerate(response["attribution"])}
            for row in response["attribution"]:
                row["term"] = rows_by_id[row["term"]]
                row["parents"] = [rows_by_id[x] for x in row["parents"]]
        traces.append(trace)
    if traces[0] != traces[1]:
        raise RuntimeError("clean rebuild handshake/normalized observations differ")
    (work / "native-controls.json").write_text(json.dumps(rows, indent=2) + "\n")
    return {"passed": True, "controls": rows, "rebuildObservationsEqual": True}


def sdk_controls(work):
    prefix = ROOT / "target/bap-core-sdk/prefix/_opam"
    targets = [("library", prefix / "lib/bap/bap.cmxa"),
               ("compiler", prefix / "bin/ocamlopt"),
               ("lock", ROOT / "native/bap-core/sdk.lock.json")]
    rows = []
    for name, target in targets:
        target = target.resolve()
        original = target.read_bytes()
        try:
            if name == "lock":
                changed = json.loads(original)
                changed["compiler"] = "ocaml-base-compiler.0.0.0"
                target.write_text(json.dumps(changed))
            else:
                target.write_bytes(original + b"CONTROLLED-IDENTITY-MISMATCH")
            result = subprocess.run(["python3", "native/bap-core/setup-sdk.py", "--check"],
                                    cwd=ROOT, text=True, capture_output=True, timeout=60)
            text = result.stdout + result.stderr
            (work / ("sdk-" + name + ".log")).write_text(text)
            passed = result.returncode != 0 and "mismatch" in text
            rows.append({"control": name, "rejected": passed})
        finally:
            target.write_bytes(original)
        if not passed:
            raise RuntimeError("SDK identity substitution was accepted: " + name)
    return {"passed": True, "controls": rows}
