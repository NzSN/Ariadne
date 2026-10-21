#!/usr/bin/env python3
"""Export exact W2/W3 runtime streams selected by their original qualified receipts.

--campaign-root is the retained host directory previously mounted as /campaign.
This copies old evidence only; it does not execute historical controller commands.
"""
import argparse
from pathlib import Path
import shutil

from i5c_qualification import (ROOT, artifact, read_json, require, retained_path,
                               sha, write_json)


def export(campaign, output):
    campaign, output = Path(campaign).resolve(), Path(output).resolve()
    require(campaign.is_dir(), "retained campaign directory is unavailable")
    require(not output.is_relative_to(campaign), "export must be outside the retained campaign")
    output.mkdir(parents=True, exist_ok=False)
    stages = {}
    for stage, relative in (("W2", "20261020/w2"), ("W3", "20261021/w3")):
        qualified = ROOT / "evidence/Ariadne/address-wrap" / relative / "qualification.json"
        payload = retained_path(qualified)
        original = read_json(payload)
        require(original.get("passed") is True and original.get("records"), "retained stage did not qualify")
        stage_root = output / stage
        stage_root.mkdir()
        shutil.copyfile(payload, stage_root / "qualification.json")
        for metadata in sorted(qualified.parent.iterdir()):
            if metadata.is_file() and metadata.name != "qualification.json":
                shutil.copyfile(retained_path(metadata), stage_root / metadata.name)
        for receipt in original["records"]:
            selected = [(receipt[stream]["path"], receipt[stream]) for stream in ("stdout", "stderr")]
            if receipt.get("case_records"):
                path = receipt["case_records"]["path"]
                item = artifact(retained_path(qualified.parent / Path(path).name))
                selected.append((path, {"bytes": item["bytes"], "sha256": item["sha256"]}))
            for original_name, expected in selected:
                name = Path(original_name).relative_to("/campaign")
                source = (campaign / name).resolve()
                require(source.is_relative_to(campaign), "retained stream escapes campaign root")
                item = artifact(source)
                require(item["bytes"] == expected["bytes"] and item["sha256"] == expected["sha256"],
                        "originally bound runtime stream differs: " + original_name)
                target = stage_root / "campaign" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    require(sha(target) == item["sha256"], "conflicting retained stream destinations")
                else:
                    shutil.copyfile(source, target)
                require(sha(target) == item["sha256"], "retained stream changed during export")
        files = {}
        for path in sorted(stage_root.rglob("*")):
            if path.is_file():
                item = artifact(path)
                files[str(path.relative_to(stage_root))] = {"bytes": item["bytes"], "sha256": item["sha256"]}
        stages[stage] = {"root": str(stage_root), "qualificationSha256": sha(payload), "files": files}
    index = output / "runtime-export.json"
    write_json(index, {"schema": "ariadne.i5c-w2-w3-runtime-export/v1", "stages": stages,
                       "qualificationRefreshed": False})
    from check_i5c import runtime_files
    runtime_files(index, sha(index))
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        index = export(args.campaign_root, args.output)
    except (OSError, ValueError, KeyError) as error:
        print("Retained runtime export failed:", error)
        return 1
    print("Runtime index:", index)
    print("Runtime index SHA256:", sha(index))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
