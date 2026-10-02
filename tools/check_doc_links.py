#!/usr/bin/env python3
"""Check local documentation links and contextual navigation from the doc map."""
from collections import deque
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "docs/documentation-map.md"


def prose(text):
    """Exclude fenced examples, whose link-like text is not navigation."""
    return re.sub(r"(?ms)^\s*(`{3,}|~{3,})[^\n]*\n.*?^\s*\1\s*$", "", text)


def destinations(path, text):
    for match in re.finditer(r"\]\((<[^>]+>|[^\s)]+)(?:\s+\"[^\"]*\")?\)", prose(text)):
        raw = match.group(1).strip("<>")
        url = urlsplit(raw)
        if url.scheme or url.netloc:
            continue
        target = (path.parent / unquote(url.path)).resolve() if url.path else path
        yield raw, target, unquote(url.fragment)


def context(text):
    match = re.search(r"(?ms)^## Context and follow-up\n(.*?)(?=^## |\Z)", text)
    return match.group(1) if match else None


def anchors(text):
    """GitHub-style anchors for this repository's ATX Markdown headings."""
    result = set()
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*$", prose(text), re.MULTILINE):
        heading = re.sub(r"\[([^]]+)\]\([^)]+\)", r"\1", heading)
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        candidate = slug
        index = 0
        while candidate in result:
            index += 1
            candidate = f"{slug}-{index}"
        result.add(candidate)
    result.update(re.findall(r'(?:id|name)=["\']([^"\']+)["\']', text))
    return result


def main():
    docs = set((ROOT / "docs").rglob("*.md")) | set((ROOT / "Plans").rglob("*.md"))
    docs.update(ROOT / name for name in (
        "README.md", "ROADMAP.md", "CHECKPOINTS.md", "Specs/README.md",
        "Specs/AMD64/README.md", "lean/README.md", "native/bap/README.md",
        "mbt/README.md", "mbt/stage-e/README.md", "evidence/Ariadne/README.md",
    ))
    docs = {p.resolve() for p in docs}
    graph = {p: set() for p in docs}
    errors = []
    links = 0
    sections = {}
    for path in sorted(docs | {ROOT / "AGENTS.md"}):
        name = path.relative_to(ROOT)
        if not path.is_file():
            errors.append(f"{name}: document missing")
            continue
        text = path.read_text()
        for raw, target, fragment in destinations(path, text):
            links += 1
            if not target.exists():
                errors.append(f"{name}: missing link target {raw}")
            elif fragment and target.is_file() and target.suffix == ".md":
                if target not in sections:
                    sections[target] = anchors(target.read_text())
                if fragment not in sections[target]:
                    errors.append(f"{name}: missing section anchor {raw}")
            if path in graph and target in docs:
                graph[path].add(target)
        if path not in docs or path == MAP:
            continue
        block = context(text)
        if block is None:
            errors.append(f"{name}: missing Context and follow-up section")
            continue
        labels = ("Status", "Why this document exists", "What this document establishes",
                  "Where to go next", "What remains unresolved")
        fields = {}
        for label in labels:
            match = re.search(r"\*\*" + re.escape(label) + r"\.\*\*(.*?)(?=\n\*\*|\Z)",
                              block, re.DOTALL)
            if match is None or not match.group(1).strip():
                errors.append(f"{name}: missing explanation: {label}")
            else:
                fields[label] = match.group(1)
        for label in ("Why this document exists", "Where to go next"):
            targets = {target for _, target, _ in destinations(path, fields.get(label, ""))}
            if not targets - {MAP, path}:
                errors.append(f"{name}: {label} needs a direct link beyond the map")
        targets = {target for _, target, _ in destinations(path, block)}
        if path in targets:
            errors.append(f"{name}: context contains a self-link")
    seen = {MAP}
    pending = deque([MAP])
    while pending:
        for target in graph.get(pending.popleft(), set()) - seen:
            seen.add(target)
            pending.append(target)
    for path in sorted(docs - seen):
        errors.append(f"{path.relative_to(ROOT)}: unreachable from documentation map")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Documentation PASS: {len(docs)} connected documents, "
          f"{len(docs) - 1} context sections, {links} local links (including section anchors).")
    print("Relationship meaning and historical scope require editorial review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
