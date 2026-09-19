#!/usr/bin/env python3
"""Generate or check Rust bindings without regenerating the reviewed oracle."""

import argparse
from pathlib import Path

from binding import GENERATED, TARGET, check_binding
from tools import MBT, mirrors_tools, prepare_model, resolve, run, verify_corpus, work_directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check freshness without rewriting generated files")
    parser.add_argument("--out", type=Path, default=GENERATED)
    args = parser.parse_args()
    verify_corpus()
    work = work_directory("binding")
    _, compiler, _ = mirrors_tools()
    model = prepare_model(work)
    lock = MBT / "corpus/AriadneReplay.lock.json"
    if not args.check:
        fresh_lock = work / "AriadneReplay.lock.json"
        resolve(compiler, model, MBT / "corpus/type-evidence.json", fresh_lock, work / "resolve.log")
        if fresh_lock.read_bytes() != lock.read_bytes():
            raise RuntimeError("interface lock is stale; regenerate and review the oracle separately")
        run([compiler, "generate", "--lock", lock, "--target", TARGET, "--out", args.out],
            log=work / "generate.log")
    check_binding(compiler, model, work / "check.log", args.out)
    print(f"{'Checked' if args.check else 'Generated and checked'} {TARGET}: {args.out}")


if __name__ == "__main__":
    main()
