#!/usr/bin/env python3
"""Measure one real minidump query, the Stage B startup case, and core scaling."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
STAGE_B = ROOT / "tests/input/fixtures/stage_b_windows.dmp"
STAGE_B_ENTRY = "0x7ff700001000"
STAGE_B_SEED = "0x7ff700001006"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def source_hashes():
    paths = set()
    for directory in ("src", "src/input", "src/bench", "native/llvm_mc"):
        paths.update(p for p in (ROOT / directory).rglob("*") if p.is_file())
    paths.update(ROOT / name for name in (
        "Cargo.toml", "Cargo.lock", "Cargo.toml", "Cargo.lock",
        "Cargo.toml", "Cargo.lock", "tools/measure_priority4.py",
        "tools/check_priority4_real_capture.py", "tools/check_priority1_real_capture.py",
        "evidence/Ariadne/priority-4-real-capture-case.json",
        "tests/support/scanning_engine.rs",
    ))
    return {str(p.relative_to(ROOT)): digest(p) for p in sorted(paths)}


def command(args, timeout=120):
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True,
                          timeout=timeout)


def summary(values):
    return {"median": statistics.median(values), "min": min(values),
            "max": max(values), "samples": len(values)}


def cli_runs(label, dump, entry, seed, args, output):
    rows = []
    expected_report_hash = None
    expected_identity = None
    for run in range(args.warmups + args.runs):
        report_dir = output / f"{label}-{run}"
        metrics = output / f"{label}-{run}.time"
        invocation = [str(args.cli), str(dump), "--decoder", str(args.decoder),
                      "--entry", entry, "--seed-exception-rip",
                      "--output-dir", str(report_dir)]
        start = time.perf_counter_ns()
        process = command(["/usr/bin/time", "-f", "%e,%M", "-o", str(metrics)]
                          + invocation)
        elapsed_ns = time.perf_counter_ns() - start
        if process.returncode:
            raise RuntimeError(f"{label} CLI run {run} failed: {process.stderr[-800:]}")
        wall_seconds, peak_rss_kib = metrics.read_text().strip().split(",")
        report = json.loads((report_dir / "report.json").read_text())
        identity = report["identity"]
        if identity["artifact_sha256"] != digest(dump):
            raise RuntimeError(f"{label} artifact identity mismatch")
        if report["query"]["entries"] != [f"0x{int(entry, 16):016x}"] or \
                report["query"]["seeds"] != [f"0x{int(seed, 16):016x}"]:
            raise RuntimeError(f"{label} query identity mismatch")
        report_hash = tuple(digest(report_dir / name) for name in
                            ("report.txt", "report.dot", "report.json"))
        if expected_report_hash is None:
            expected_report_hash = report_hash
            expected_identity = identity
        elif report_hash != expected_report_hash or identity != expected_identity:
            raise RuntimeError(f"{label} report changed across identical runs")
        rows.append({
            "workload": label, "run": run, "warmup": run < args.warmups,
            "elapsed_ns": elapsed_ns, "time_wall_seconds": wall_seconds,
            "peak_rss_kib": int(peak_rss_kib),
            "decoded": len(report["analysis"]["decoded"]),
            "edges": len(report["analysis"]["edges"]),
            "slice": len(report["analysis"]["slice"]),
            "obligations": len(report["analysis"]["obligations"]),
            "query_id": identity["query_id"],
            "artifact_sha256": identity["artifact_sha256"],
        })
    measured = [row for row in rows if not row["warmup"]]
    return rows, {
        "identity": expected_identity,
        "report_sha256": dict(zip(("text", "dot", "json"), expected_report_hash)),
        "elapsed_ms": summary([row["elapsed_ns"] / 1_000_000 for row in measured]),
        "peak_rss_kib": summary([row["peak_rss_kib"] for row in measured]),
        "decoded": measured[0]["decoded"], "edges": measured[0]["edges"],
        "slice": measured[0]["slice"], "obligations": measured[0]["obligations"],
    }


def stage_runs(args):
    process = command([str(args.stage_bench), str(args.dump), str(args.decoder),
                       args.entry, args.seed, str(args.warmups + args.runs)])
    if process.returncode:
        raise RuntimeError(f"stage benchmark failed: {process.stderr[-800:]}")
    rows = list(csv.DictReader(io.StringIO(process.stdout)))
    if len(rows) != args.warmups + args.runs:
        raise RuntimeError("stage benchmark row count mismatch")
    expected_sha = digest(args.dump)
    for row in rows:
        if row["artifact_sha256"] != expected_sha or \
                int(row["entry_va"], 16) != int(args.entry, 16) or \
                int(row["seed_va"], 16) != int(args.seed, 16):
            raise RuntimeError("stage benchmark query identity mismatch")
    measured = rows[args.warmups:]
    medians = {key: summary([int(row[key]) / 1_000_000 for row in measured])
               for key in ("open_ns", "prepare_ns", "analysis_ns", "render_ns",
                           "total_ns")}
    counts = {key: summary([int(row[key]) for row in measured])
              for key in ("allocations", "allocated_bytes", "actions",
                          "incoming_evaluations", "edge_scans",
                          "transfer_evaluations", "max_reaching_at_site",
                          "total_reaching")}
    return process.stdout, {"stage_ms": medians, "counts": counts,
                            "decoded": int(measured[0]["decoded"]),
                            "slice": int(measured[0]["slice"])}


def synthetic_runs(args, output):
    outputs = []
    outcomes = []
    for nodes in args.synthetic_sizes:
        phase = "warmup"
        bound = 120
        try:
            warm = command([str(args.synthetic_bench), str(nodes), "1"], timeout=bound)
            if warm.returncode:
                raise RuntimeError(f"synthetic warmup {nodes} failed: {warm.stderr[-800:]}")
            phase, bound = "measured", 180
            measured = command([str(args.synthetic_bench), str(nodes),
                                str(args.runs)], timeout=bound)
            if measured.returncode:
                raise RuntimeError(f"synthetic {nodes} failed: {measured.stderr[-800:]}")
            rows = list(csv.DictReader(io.StringIO(measured.stdout)))
            if len(rows) != 5 * args.runs:
                raise RuntimeError(f"synthetic {nodes} row count mismatch")
            outputs.append(measured.stdout)
            outcomes.append({"nodes": nodes, "status": "complete", "rows": len(rows)})
        except subprocess.TimeoutExpired as error:
            partial = error.stdout or b""
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", errors="replace")
            (output / f"synthetic-{nodes}-{phase}-partial.csv").write_text(partial)
            outcomes.append({"nodes": nodes, "status": "timeout", "phase": phase,
                             "timeout_seconds": bound,
                             "partial_csv": f"synthetic-{nodes}-{phase}-partial.csv"})
        # Retain each completed size before attempting the next bounded size.
        (output / "synthetic.csv").write_text(
            outputs[0] + "".join(part.split("\n", 1)[1] for part in outputs[1:])
            if outputs else "")
        (output / "synthetic-outcomes.json").write_text(json.dumps(outcomes, indent=2) + "\n")
    return outcomes


def qualifies(record, args, identity, tools, sources):
    """Measurement counts alone cannot qualify an unanchored dump query."""
    try:
        return bool(record and record.get("passed") and record.get("source_stable") and
                    record.get("dump_sha256") == digest(args.dump) and
                    number_va(record.get("entry_va")) == number_va(args.entry) and
                    number_va(record.get("seed_va")) == number_va(args.seed) and
                    record.get("tool_sha256", {}).get("cli") == tools["cli"] and
                    record.get("tool_sha256", {}).get("decoder") == tools["decoder"] and
                    record.get("source_sha256") == sources and
                    record.get("report_identity") == identity and
                    record.get("observations", {}).get("decoded", 0) >= 64 and
                    record.get("observations", {}).get("slice", 0) > 1)
    except (AttributeError, KeyError, TypeError, ValueError):
        return False


def number_va(value):
    return int(value, 16) if isinstance(value, str) else value


def save_csv(path, rows):
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]),
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", type=Path, required=True)
    parser.add_argument("--decoder", type=Path, required=True)
    parser.add_argument("--entry", required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--cli", type=Path,
                        default=ROOT / "target/release/ariadne-minidump")
    parser.add_argument("--stage-bench", type=Path,
                        default=ROOT / "target/release/real_minidump")
    parser.add_argument("--synthetic-bench", type=Path,
                        default=ROOT / "target/release/ariadne-bench")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--synthetic-sizes", default="128,256,512",
                        help="ascending comma-separated bounded node counts")
    parser.add_argument("--latency-budget-ms", type=float, required=True)
    parser.add_argument("--qualification", type=Path,
                        help="source/tool-bound independent real-capture acceptance record")
    args = parser.parse_args()
    try:
        args.synthetic_sizes = tuple(int(part) for part in
                                     args.synthetic_sizes.split(","))
    except ValueError:
        parser.error("--synthetic-sizes needs positive comma-separated integers")
    if args.output_dir.exists() or args.runs < 5 or args.warmups < 1 or \
            args.latency_budget_ms <= 0 or not args.synthetic_sizes or \
            any(size <= 0 for size in args.synthetic_sizes) or \
            tuple(sorted(set(args.synthetic_sizes))) != args.synthetic_sizes:
        parser.error("output directory must be new; use at least 5 runs, 1 warmup and a positive budget")
    args.output_dir.mkdir(parents=True)
    before = source_hashes()
    tool_sha = {label: digest(path) for label, path in (
        ("cli", args.cli), ("decoder", args.decoder),
        ("stage_bench", args.stage_bench),
        ("synthetic_bench", args.synthetic_bench))}
    qualification = json.loads(args.qualification.read_text()) if args.qualification else None
    cpu_model = next((line.split(":", 1)[1].strip() for line in
                      Path("/proc/cpuinfo").read_text().splitlines()
                      if line.startswith("model name")), platform.processor())
    record = {"schema": "ariadne-priority-4-measurement-v1",
              "recorded_utc": datetime.now(timezone.utc).isoformat(),
              "host": platform.platform(), "python": sys.version.split()[0],
              "rustc": command(["rustc", "--version"]).stdout.strip(),
              "latency_budget_ms": args.latency_budget_ms,
              "runs": args.runs, "warmups": args.warmups,
              "synthetic_sizes": args.synthetic_sizes,
              "tool_sha256": tool_sha, "source_sha256": before,
              "artifact_sha256": digest(args.dump),
              "cpu": {"model": cpu_model, "logical_cpus": os.cpu_count()},
              "build_profile": "release",
              "query": {"entry": args.entry, "seed": args.seed, "open_limits": "default",
                        "prepare_limits": "default", "formats": ["text", "dot", "json"]},
              "qualification_sha256": digest(args.qualification) if args.qualification else None,
              "passed": False}
    try:
        real_rows, real = cli_runs("real_capture", args.dump, args.entry,
                                   args.seed, args, args.output_dir)
        record["real"] = real
        save_csv(args.output_dir / "cli.csv", real_rows)
        stage_rows, stage = stage_runs(args)
        if stage["decoded"] != real["decoded"] or stage["slice"] != real["slice"]:
            raise RuntimeError("stage and CLI semantic counts disagree")
        record["stage"] = stage
        (args.output_dir / "stage.csv").write_text(stage_rows)
        startup_rows, startup = cli_runs("stage_b_windows", STAGE_B,
                                         STAGE_B_ENTRY, STAGE_B_SEED,
                                         args, args.output_dir)
        save_csv(args.output_dir / "cli.csv", real_rows + startup_rows)
        record["startup"] = startup
        record["synthetic_outcomes"] = synthetic_runs(args, args.output_dir)
        qualified = qualifies(qualification, args, real["identity"], tool_sha, before)
        record.update({"real": real, "stage": stage, "startup": startup,
                       "real_workload_target_met": qualified,
                       "decision": "no_change_within_budget" if qualified and
                       real["elapsed_ms"]["median"] <= args.latency_budget_ms
                       else "optimize_candidate" if qualified
                       else "larger_real_capture_required" if real["decoded"] < 64
                       else "real_capture_qualification_required",
                       "csv_sha256": {name: digest(args.output_dir / name)
                                      for name in ("cli.csv", "stage.csv", "synthetic.csv")}})
        record["sources_stable"] = before == source_hashes()
        record["tools_stable"] = tool_sha == {label: digest(path)
                                               for label, path in (("cli", args.cli),
                                                                   ("decoder", args.decoder),
                                                                   ("stage_bench", args.stage_bench),
                                                                   ("synthetic_bench", args.synthetic_bench))}
        record["passed"] = record["sources_stable"] and record["tools_stable"]
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        record["failure"] = str(error)
    (args.output_dir / "validation.json").write_text(json.dumps(record, indent=2,
                                                                  sort_keys=True) + "\n")
    print("Priority 4 measurement:", "PASS" if record["passed"] else "FAIL")
    print("Decision:", record.get("decision", "incomplete"))
    print("Record:", args.output_dir / "validation.json")
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
