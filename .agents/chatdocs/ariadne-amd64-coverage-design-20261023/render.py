#!/usr/bin/env python3
"""Render the canonical AMD64 coverage design into its dated HTML reading view."""
from __future__ import annotations

import hashlib
import html
import os
from pathlib import Path
import re
import shutil
from urllib.parse import unquote, urlsplit, urlunsplit

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'docs/Ariadne/amd64-coverage-design.md'
DEST = Path(__file__).resolve().parent
DATE = '2026-10-23'
BASELINE = 'e44ce2b plus uncommitted v12 REP work'


def slugify(text: str) -> str:
    return re.sub(r'[^\w\- ]', '', text.lower()).replace(' ', '-')


def render() -> None:
    source_bytes = SOURCE.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    source_text = source_bytes.decode('utf-8')
    parser = MarkdownIt('commonmark', {'html': True}).enable('table')
    tokens = parser.parse(source_text)
    used = set()
    toc = []
    title = 'AMD64 coverage and REP design'
    for index, token in enumerate(tokens):
        if token.type == 'heading_open':
            inline = tokens[index + 1]
            heading = ''.join(t.content for t in (inline.children or []) if t.type in {'text', 'code_inline'})
            slug = slugify(heading)
            candidate = slug
            ordinal = 0
            while candidate in used:
                ordinal += 1
                candidate = f'{slug}-{ordinal}'
            used.add(candidate)
            token.attrSet('id', candidate)
            if token.tag == 'h1':
                title = heading
            if token.tag in {'h2', 'h3'}:
                toc.append((token.tag, candidate, heading))
        if token.type != 'inline':
            continue
        for child in token.children or []:
            attribute = 'href' if child.type == 'link_open' else ('src' if child.type == 'image' else None)
            if not attribute:
                continue
            value = child.attrGet(attribute)
            if not value:
                continue
            split = urlsplit(value)
            if split.scheme or split.netloc or not split.path:
                continue
            resolved = (SOURCE.parent / unquote(split.path)).resolve()
            if resolved == (SOURCE.parent / 'amd64-coverage-architecture.svg').resolve():
                child.attrSet(attribute, 'architecture.svg')
            else:
                relative = os.path.relpath(resolved, DEST)
                child.attrSet(attribute, urlunsplit(('', '', relative, split.query, split.fragment)))
    diagram = SOURCE.parent / 'amd64-coverage-architecture.svg'
    shutil.copyfile(diagram, DEST / 'architecture.svg')
    svg = diagram.read_text()
    default_image = parser.renderer.rules['image']

    def image_rule(image_tokens, index, options, env):
        if image_tokens[index].attrGet('src') == 'architecture.svg':
            return svg
        return default_image(image_tokens, index, options, env)

    parser.renderer.rules['image'] = image_rule
    content = parser.renderer.render(tokens, parser.options, {})
    content = re.sub(r'<p>(<svg\b.*?</svg>)\s*</p>', r'<figure class="diagram"><div class="diagram-scroll" tabindex="0" role="region" aria-label="Scrollable architecture diagram">\1</div><figcaption>Two lanes connect source obligations with consumer qualification. Scroll horizontally for readable labels, or <a href="architecture.svg">open the full diagram</a>.</figcaption></figure>', content, flags=re.S)
    content = content.replace('<table>',  '<div class="table-scroll" tabindex="0" role="region" aria-label="Scrollable table"><table>').replace('</table>', '</table></div>')
    toc_html = '\n'.join(f'<li class="{level}"><a href="#{slug}">{html.escape(text)}</a></li>' for level, slug, text in toc)
    source_href = os.path.relpath(SOURCE, DEST)
    css = '''
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}body{margin:0;background:#f4f7fa;color:#1d2b3b;font:17px/1.7 system-ui,-apple-system,"Segoe UI",sans-serif}a{color:#075b9b;text-underline-offset:3px}a:hover{color:#053b67}a:focus-visible,[tabindex]:focus-visible{outline:3px solid #c7871d;outline-offset:4px}.top{background:#102d47;color:#eef6fe;padding:20px max(24px,calc((100vw - 1390px)/2))}.top strong{font-size:1.1rem;letter-spacing:.3px}.top nav{display:flex;gap:24px;flex-wrap:wrap;margin-top:7px}.top a{color:#b9ddfa;font-size:.91rem}.layout{display:grid;grid-template-columns:260px minmax(0,1fr);gap:38px;max-width:1390px;margin:0 auto;padding:30px 24px 70px}.toc{position:sticky;top:24px;align-self:start;max-height:calc(100vh - 48px);overflow:auto;padding:4px 18px 20px 0}.toc strong{display:block;font-size:.88rem;text-transform:uppercase;letter-spacing:.8px;color:#52667a;margin-bottom:12px}.toc ul{list-style:none;margin:0;padding:0}.toc li{margin:5px 0;font-size:.87rem;line-height:1.45}.toc li.h3{padding-left:15px;font-size:.81rem}.toc a{color:#465c70;text-decoration:none;display:block;padding:3px 0}.toc a:hover{text-decoration:underline}article{min-width:0;background:white;border:1px solid #d7e1e9;border-radius:12px;padding:35px 44px 60px;box-shadow:0 3px 14px #132f4610}.provenance{background:#edf4fb;border:1px solid #c2d5e6;border-radius:7px;padding:15px 19px;margin:0 0 28px;font-size:.9rem;line-height:1.55}.provenance p{margin:5px 0}.label{color:#315674;text-transform:uppercase;letter-spacing:.8px;font-size:.78rem;font-weight:700}h1{font-size:2.15rem;line-height:1.2;letter-spacing:-.7px;margin:0 0 26px;color:#142d44}h2{font-size:1.55rem;line-height:1.3;margin:50px 0 18px;padding-top:18px;border-top:1px solid #dbe4eb;color:#183f5e}h3{font-size:1.15rem;line-height:1.4;margin:30px 0 12px;color:#244b69}p,ul,ol{margin:15px 0}li{padding-left:3px;margin:6px 0}code,pre{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}code{font-size:.85em;background:#f0f4f7;padding:2px 5px;border-radius:4px;overflow-wrap:anywhere}pre{white-space:pre;overflow:auto;font-size:.84rem;line-height:1.6;padding:18px 20px;background:#f3f6f9;border:1px solid #dbe4ed;border-radius:7px}pre code{background:none;padding:0;overflow-wrap:normal}blockquote{border-left:4px solid #bd8d30;background:#fff9ed;padding:4px 20px;margin:24px 0}.table-scroll{overflow:auto;max-width:100%;margin:24px 0;border:1px solid #d4dfe8;border-radius:7px}table{border-collapse:collapse;width:100%;font-size:.88rem;line-height:1.55}th,td{text-align:left;vertical-align:top;padding:12px 14px;border-bottom:1px solid #dbe4eb}th{background:#edf3f8;font-weight:650}tr:last-child td{border-bottom:none}td:nth-child(1){font-weight:550}img,svg{max-width:100%;height:auto}.diagram{margin:24px 0}.diagram-scroll{overflow:auto;border:1px solid #d4dfe8;border-radius:9px}.diagram-scroll svg{min-width:1200px;max-width:none;width:100%;margin:0;border:0;border-radius:0}figcaption{font-size:.84rem;color:#52667a;margin-top:8px}svg{display:block;border:1px solid #d4dfe8;border-radius:9px;margin:22px 0}.foot{margin-top:45px;padding-top:20px;border-top:1px solid #dbe4eb;font-size:.84rem;color:#52667a}.hash{display:block;word-break:break-all;font-family:ui-monospace,Consolas,monospace;font-size:.76rem}strong{font-weight:650}hr{border:0;border-top:1px solid #dbe4eb;margin:35px 0}@media(max-width:1050px){.layout{grid-template-columns:205px minmax(0,1fr);gap:24px}article{padding:28px}.toc{padding-right:0}}@media(max-width:800px){.layout{display:block;padding:16px 14px 45px}.toc{position:static;max-height:none;padding:12px 10px 20px}.toc ul{columns:2;column-gap:24px}.toc li{break-inside:avoid}.toc li.h3{display:none}article{padding:25px 20px;border-radius:8px}h1{font-size:1.75rem}h2{font-size:1.35rem}.top{padding:17px 23px}}@media(max-width:480px){.toc ul{columns:1}body{font-size:16px}.top nav{gap:14px}.table-scroll{font-size:.83rem}th,td{padding:10px}}@media print{body{background:white;font-size:10pt}.top,.toc{display:none}.layout{display:block;padding:0;max-width:none}article{border:0;padding:0;box-shadow:none}.provenance{break-inside:avoid}h2,h3{break-after:avoid}table,svg{break-inside:avoid}.diagram-scroll{overflow:visible}.diagram-scroll svg{min-width:0;max-width:100%}a{color:inherit}}
'''
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Design proposal for remaining REP forms and complete, scoped AMD64 coverage with authoritative form bindings and consumer-specific qualification."><title>{html.escape(title)}</title><style>{css}</style></head>
<body><header class="top"><strong>Ariadne · design reading view</strong><nav aria-label="Document navigation"><a href="../ariadne-reports-index.html">Report archive</a><a href="{html.escape(source_href)}">Canonical design</a><a href="architecture.svg">Full architecture diagram</a></nav></header>
<div class="layout"><aside class="toc"><nav aria-label="Table of contents"><strong>Contents</strong><ul>{toc_html}</ul></nav></aside><article><div class="provenance"><span class="label">Design proposal · {DATE}</span><p>Canonical source: <a href="{html.escape(source_href)}"><code>docs/Ariadne/amd64-coverage-design.md</code></a>.</p><p>Baseline: <strong>{html.escape(BASELINE)}</strong>. This dated reading view presents the design; creating it does not execute implementation or qualification.</p></div>{content}<footer class="foot"><p>This HTML is a presentation of the canonical Markdown, with relative links adapted for the archive. Edit the canonical source and run <code>render.py</code> to refresh it.</p><p>Canonical source SHA-256:<span class="hash">{source_sha}</span></p></footer></article></div></body></html>
'''
    (DEST / 'index.html').write_text(document)
    print(f'Rendered {DEST / "index.html"}')
    print(f'Canonical SHA-256 {source_sha}')


if __name__ == '__main__':
    render()
