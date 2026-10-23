#!/usr/bin/env python3
"""Reconstruct the AMD source-obligation graph without adopting source claims.

Reviewed inputs name immutable source evidence and narrowly justified decisions.
Generated ledgers live in ignored work. A check reconstructs source inputs and
the entire graph; neither a saved passing flag nor a resealed digest is proof.
"""
import argparse
from collections import Counter
import contextlib
import io
import json
from pathlib import Path
import sys

from amd64_inventory import strict_json
from amd64_inventory_xed import canonical, digest
import amd64_manual_geometry as geometry
import amd64_source_corpus as corpus
from run_output import run_output

ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / 'tests/bap/fixtures/amd64-semantics/source-obligations-v1.json'
SCHEMA = 'ariadne.amd-source-obligations/v1'
REVIEW_SCHEMA = 'ariadne.amd-source-obligation-decisions/v1'
PUBLICATIONS = ('24594', '26568', '26569')


def stable_id(kind, identity):
    """Identity depends on source addresses, never a mutable resolution state."""
    return 'amd-' + kind + ':' + digest(identity)


def source_cell_identity(cell):
    return {name: cell[name] for name in ('id', 'pdfPage', 'pdfSha256', 'rect', 'text',
                                         'unicodeSha256', 'wordBoxesSha256')}


def source_closure(root=ROOT):
    result = geometry.extractor_sources(root)
    for name in ('amd64_source_obligations.py', 'amd64_manual_outline.js'):
        result['tools/' + name] = corpus.sha_file(Path(root) / 'tools' / name)
    return result


def _fields(value, expected, label):
    corpus.fields(value, expected, label)


def _unique(rows, key, label):
    result = {}
    for row in rows:
        identity = row[key]
        if identity in result:
            raise ValueError('duplicate ' + label + ': ' + str(identity))
        result[identity] = row
    return result


def _maps(value):
    result = {}
    for entry in value:
        publication, separator, path = entry.partition('=')
        if not separator or publication not in PUBLICATIONS or publication in result:
            raise ValueError('expected one PUBLICATION=PATH for each instruction volume')
        result[publication] = Path(path)
    if set(result) != set(PUBLICATIONS):
        raise ValueError('all three instruction publications are required')
    return result


def load_sources(source_directory, pdf_cache, geometry_directories, baseline_directories,
                 executables, tool_environment, corpus_lock=corpus.LOCK):
    """Validate exact current source inputs and reconstruct existing geometry.

    C1 reproduction remains a separate executable prerequisite. This method
    checks every tool/library, PDF and product identity, then actually reruns
    geometry derivation rather than trusting a stored acceptance map.
    """
    source_directory, pdf_cache, corpus_lock = map(Path, (source_directory, pdf_cache, corpus_lock))
    if set(geometry_directories) != set(PUBLICATIONS) or set(baseline_directories) != set(PUBLICATIONS):
        raise ValueError('source graph requires all three historical instruction publications')
    before = source_closure()
    lock = corpus.validate_lock(strict_json(corpus_lock.read_bytes()))
    manifest = source_directory / 'products.json'
    products = strict_json(manifest.read_bytes())
    corpus.check_products(lock, products, source_directory, pdf_cache, executables, tool_environment, require_all=True)
    original_lock = geometry.LOCK
    provenance = dict(corpusLockSha256=corpus.sha_file(corpus_lock),
        historicalLockSha256=corpus.sha_file(original_lock), sourceProductsSha256=corpus.sha_file(manifest),
        extractorSources=before, documents={}, geometry={}, baselines={})
    for document in lock['documents']:
        publication = document['publication']
        provenance['documents'][publication] = dict(pdfSha256=corpus.sha_file(pdf_cache / document['filename']),
            products=next(row['products'] for row in products['reproducedPublications']
                          if row['publication'] == publication))
    reconstructed = {}
    baseline_entries = {}
    for publication in PUBLICATIONS:
        work = Path(geometry_directories[publication])
        baseline = Path(baseline_directories[publication])
        path = work / 'geometry.json'
        before_geometry = corpus.sha_file(path)
        before_baseline = {name: corpus.sha_file(baseline / name) for name in ('inventory.json', 'layout.txt')}
        document = next(row for row in lock['documents'] if row['publication'] == publication)
        with contextlib.redirect_stdout(io.StringIO()):
            geometry.main(['check', '--publication', publication, '--baseline', str(baseline),
                '--corpus', str(source_directory / publication), '--pdf', str(pdf_cache / document['filename']),
                '--corpus-lock', str(corpus_lock), '--output', str(work)])
        if before_geometry != corpus.sha_file(path) or before_baseline != {
                name: corpus.sha_file(baseline / name) for name in before_baseline}:
            raise ValueError('source or geometry changed during reconstruction')
        reconstructed[publication] = strict_json(path.read_bytes())
        baseline_entries[publication] = strict_json((baseline / 'inventory.json').read_bytes())['content']['entries']
        provenance['geometry'][publication] = dict(fileSha256=before_geometry,
            contentSha256=reconstructed[publication]['contentSha256'])
        provenance['baselines'][publication] = before_baseline
    regions = geometry.audit_regions(source_directory, corpus_lock)
    if (before != source_closure() or provenance['corpusLockSha256'] != corpus.sha_file(corpus_lock)
            or provenance['historicalLockSha256'] != corpus.sha_file(original_lock)
            or provenance['sourceProductsSha256'] != corpus.sha_file(manifest)):
        raise ValueError('source dependency closure or manifest changed during reconstruction')
    # Check products again to detect input changes during the three derivations.
    corpus.check_products(lock, products, source_directory, pdf_cache, executables, tool_environment, require_all=True)
    return dict(corpusLock=lock, geometries=reconstructed, regions=regions, provenance=provenance, baselineEntries=baseline_entries)


def relation_identity(publication, pdf_sha, first, second):
    return dict(publication=publication, pdfSha256=pdf_sha, fromTable=first['id'], toTable=second['id'])


def _cell_index(document):
    cells = _unique(document['content']['sourceCells'], 'id', 'source cell')
    for cell in cells.values():
        if cell['pdfSha256'] != document['pdfSha256']:
            raise ValueError('source cell belongs to another PDF')
    return cells


def _headers(table, cells):
    if not table['headerCells'] or not set(table['headerCells']) <= cells.keys():
        raise ValueError('table header has missing source cells')
    values = [cells[key] for key in table['headerCells']]
    if any(cell['pdfPage'] != table['pdfPage'] for cell in values):
        raise ValueError('table header belongs to another page')
    return sorted(values, key=lambda cell: (cell['rect'][0], cell['rect'][1], cell['id']))


def _header_kind(headers):
    text = ' '.join(cell['text'] for cell in headers)
    if 'Mnemonic' not in text:
        return 'unrecognized'
    if 'Implied Value of imm8' in text:
        return 'immediate-aliases'
    if all(part in text for part in ('Imm[0]', 'Imm[4]', 'Quadword Operands Selected')):
        return 'immediate-selection'
    if '(RS)' in text and '(RC)' in text:
        return 'rounding-controls'
    if 'Opcode' in text and 'Description' in text:
        return 'opcode-encoding'
    if 'Encoding' in text:
        return 'structured-encoding'
    return 'unrecognized'


def _actual_candidates(bundle):
    result = {}
    for publication, document in bundle['geometries'].items():
        tables = _unique(document['content']['tables'], 'id', 'source table')
        for first in tables.values():
            for old_relation in first['continuations']:
                if old_relation['table'] not in tables:
                    raise ValueError('continuation points to absent table')
                second = tables[old_relation['table']]
                common = sorted(set(first['entryIds']) & set(second['entryIds']))
                if (second['pdfPage'] != first['pdfPage'] + 1 or not common
                        or old_relation['entryIds'] != common):
                    raise ValueError('table candidate adjacency or historical ownership differs')
                identity = relation_identity(publication, document['pdfSha256'], first, second)
                key = stable_id('table-relation', identity)
                if key in result:
                    raise ValueError('duplicate table-relation obligation')
                result[key] = dict(identity=identity, first=first, second=second,
                                   originalRelation=old_relation, entryIds=common)
    return result


def _column_signature(table, cells):
    headers = _headers(table, cells)
    subheaders = [cells[key] for key in table.get('columnHeaderCells', [])]
    ordered = sorted(subheaders, key=lambda cell: (cell['rect'][1], cell['rect'][0], cell['id']))
    return (_header_kind(headers), tuple(cell['text'] for cell in headers),
            tuple(' '.join(cell['text'] for cell in ordered).split()))


def _local_row(document, table, side, cells):
    """Select an actual locally complete boundary row; never inherit a cell."""
    if table['rows']:
        rows = {row['id']: row for row in document['content']['rows']}
        row = rows[table['rows'][-1 if side == 'left' else 0]]
        heads, encoded = list(row['headCells']), list(row['encodingCells'])
        operands = [key for part in row['operandContinuations'] for key in part['cells']]
        if not encoded:
            proofs = {}
            for record in document['content']['oldGapDispositions']:
                evidence = record.get('evidence', {})
                if (record['disposition'] in {'resolved-cell', 'justified-continuation'}
                        and evidence.get('table') == table['id']
                        and set(heads) <= set(evidence.get('headCells', [])) and evidence.get('encodingCells')):
                    value = {key: evidence[key] for key in ('headCells', 'encodingCells', 'entryId')}
                    proofs[digest(value)] = value
            if len(proofs) != 1:
                raise ValueError('boundary row lacks a unique local explicit encoding')
            proof = next(iter(proofs.values()))
            if proof['entryId'] != row['entryId']:
                raise ValueError('boundary row recovery changes source ownership')
            heads, encoded = proof['headCells'], proof['encodingCells']
        wanted = heads + encoded + operands
        if not set(wanted) <= cells.keys() or any(cells[key]['pdfPage'] != table['pdfPage'] for key in wanted):
            raise ValueError('boundary row borrows a missing or cross-page source cell')
        syntax = ' '.join(cells[key]['text'] for key in heads + operands).strip()
        if syntax.endswith(',') or syntax.count('{') != syntax.count('}'):
            raise ValueError('boundary row has an unfinished operand fragment')
        labels = {cell['text']: cell for cell in _headers(table, cells)}
        if _header_kind(_headers(table, cells)) == 'opcode-encoding':
            lo, hi = labels['Opcode']['rect'][0] - 4, labels['Description']['rect'][0] - 2
            if not labels['Mnemonic']['rect'][0] < lo < hi:
                raise ValueError('boundary columns do not have their named source order')
            if any(not (lo <= cells[key]['rect'][0] and cells[key]['rect'][2] < hi) for key in encoded):
                raise ValueError('boundary opcode lies outside its named column')
            if not all(geometry.encoding_cell(cells[key]) for key in encoded):
                raise ValueError('boundary encoding is not an explicit byte-bearing source cell')
        else:
            subheaders = [cells[key] for key in table['columnHeaderCells']]
            prefixes = [cell for cell in subheaders if cell['text'] in {'VEX', 'EVEX', 'XOP'}]
            if len(prefixes) != 1:
                raise ValueError('boundary structured row has no unique prefix column')
            lo, hi = prefixes[0]['rect'][0] - 12, max(cell['rect'][2] for cell in subheaders) + 2
            if any(not (lo <= cells[key]['rect'][0] and cells[key]['rect'][2] <= hi) for key in encoded):
                raise ValueError('boundary structured encoding escapes named columns')
            if (sum(cells[key]['text'] in {'C4', 'C5', '62', '8F'} for key in encoded) != 1
                    or sum(bool(__import__('re').match(r'^[0-9A-F]{2}\s+/r(?:\s|$)', cells[key]['text'])) for key in encoded) != 1):
                raise ValueError('boundary structured row lacks explicit prefix or opcode')
        return dict(kind='explicit-local-encoding-row', row=row['id'], entryId=row['entryId'],
                    headCells=heads, encodingCells=encoded, operandCells=operands,
                    allCells=sorted(set(wanted)), inheritsCells=False)
    if _header_kind(_headers(table, cells)) != 'immediate-aliases':
        raise ValueError('boundary table has no complete source rows')
    import re
    page_cells = [cell for cell in cells.values() if cell['pdfPage'] == table['pdfPage']]
    groups = geometry.physical_lines(page_cells)
    top = max(cell['rect'][1] for cell in _headers(table, cells))
    later_headers = [cell['rect'][1] for cell in page_cells if cell['text'] in
                     {'Instruction Support', 'Instruction Encoding', 'Mnemonic'} and cell['rect'][1] > top + 2]
    stop = min(later_headers, default=730)
    found = []
    for group in groups:
        if group['ambiguous'] or not top + 2 < group['y'] < stop:
            continue
        heads = [cell for cell in group['cells'] if re.fullmatch(r'\(V\)CMP[A-Z]+PD', cell['text'])]
        values = [cell for cell in group['cells'] if re.fullmatch(r'[0-9A-F]{2}h(?:, [0-9A-F]{2}h){3}', cell['text'])]
        if len(heads) == len(values) == 1 and heads[0]['rect'][2] < values[0]['rect'][0]:
            found.append((heads[0], values[0]))
    if not found:
        raise ValueError('alias boundary lacks complete explicit mnemonic/value cells')
    head, value = found[-1 if side == 'left' else 0]
    return dict(kind='explicit-local-alias-row', row=None, entryId=table['entryIds'][0],
                headCells=[head['id']], encodingCells=[value['id']], operandCells=[],
                allCells=sorted([head['id'], value['id']]), inheritsCells=False)


def structural_evidence(bundle, candidate):
    """Derive a limited table-series proof from all physical boundary material.

    The relation permits grouping complete rows only. It never authorizes
    opcode, operand, merged-cell or footnote inheritance across a page boundary.
    """
    import re
    publication = candidate['identity']['publication']
    document = bundle['geometries'][publication]
    cells = _cell_index(document)
    first, second = candidate['first'], candidate['second']
    signature = _column_signature(first, cells)
    if signature != _column_signature(second, cells) or signature[0] == 'unrecognized':
        raise ValueError('table-series column semantics differ across the boundary')
    entries = {entry['id']: entry for entry in bundle['baselineEntries'][publication]}
    if len(candidate['entryIds']) != 1:
        raise ValueError('table series has ambiguous section ownership')
    owner = entries[candidate['entryIds'][0]]
    if not owner['pdfPage'] <= first['pdfPage'] < second['pdfPage'] <= owner['pdfEndPage']:
        raise ValueError('table series crosses its source section range')
    headings = [cell for cell in cells.values() if owner['pdfPage'] <= cell['pdfPage'] <= second['pdfPage']
                and 70 < cell['rect'][1] < 300 and cell['rect'][0] < 250
                and cell['rect'][3] - cell['rect'][1] >= 17
                and (cell['pdfPage'] != second['pdfPage']
                     or cell['rect'][1] < min(value['rect'][1] for value in _headers(second, cells)))
                and re.fullmatch(r'[A-Z][A-Z0-9]*(?:cc)?', cell['text'])]
    if not headings or not any(cell['pdfPage'] == owner['pdfPage'] for cell in headings):
        raise ValueError('table series lacks its actual instruction-section heading')
    if any(not geometry.mnemonic_belongs(cell['text'], [owner['title']]) for cell in headings):
        raise ValueError('an intervening instruction heading changes section ownership')
    left, right = _local_row(document, first, 'left', cells), _local_row(document, second, 'right', cells)
    if left['entryId'] != owner['id'] or right['entryId'] != owner['id']:
        raise ValueError('boundary rows disagree with the source section owner')
    left_top = min(cells[key]['rect'][1] for key in left['allCells'])
    right_bottom = max(cells[key]['rect'][3] for key in right['allCells'])
    # Include descriptions following the first row, stopping strictly before
    # the next source-owned row. They remain text, not parsed ISA semantics.
    if signature[0] == 'opcode-encoding':
        rows = {row['id']: row for row in document['content']['rows']}
        subsequent = [min(cells[key]['rect'][1] for key in rows[row]['headCells'])
                      for row in second['rows'] if row != right['row']
                      and not set(rows[row]['headCells']) <= set(right['headCells'])]
        right_bottom = min(right_bottom + 18, min(subsequent, default=right_bottom + 18) - 1.2)
    boundary = [cell for cell in cells.values()
                if (cell['pdfPage'] == first['pdfPage'] and cell['rect'][1] >= left_top - 1.2)
                or (cell['pdfPage'] == second['pdfPage'] and cell['rect'][1] < right_bottom)]
    labels = {side: {cell['text']: cell for cell in _headers(table, cells)}
              for side, table in (('left', first), ('right', second))}
    known = set(left['allCells'] + right['allCells'] + first['headerCells'] + second['headerCells']
                + first.get('columnHeaderCells', []) + second.get('columnHeaderCells', []))
    roles = {}
    for cell in boundary:
        key, text, y = cell['id'], cell['text'], cell['rect'][1]
        if key in known:
            roles[key] = 'explicit-local-row-or-header'
        elif y < 85 and (text == '[AMD Public Use]' or text == 'AMD64 Technology'
                         or re.fullmatch(re.escape(publication) + r'—Rev\. [0-9.]+—[A-Za-z]+ [0-9]{4}', text)):
            roles[key] = 'running-document-header'
        elif y > 720 and (text.isdecimal() or text in {'General-Purpose', 'Instruction Reference',
                                                       'System Instruction Reference', 'General-Purpose Instruction Reference'}
                          or all(geometry.mnemonic_belongs(word, [owner['title']])
                                 for word in text.replace(',', '').split())):
            roles[key] = 'running-page-footer'
        elif signature[0] == 'opcode-encoding':
            side = 'left' if cell['pdfPage'] == first['pdfPage'] else 'right'
            row = left if side == 'left' else right
            desc = labels[side]['Description']['rect'][0]
            latest = max(cells[k]['rect'][3] for k in row['allCells'])
            if cell['rect'][0] >= desc - 2 and y <= latest + 18:
                roles[key] = 'local-row-description'
            else:
                raise ValueError('unaccounted intervening source cell in table series: ' + key)
        else:
            raise ValueError('unaccounted intervening source cell in table series: ' + key)
    evidence_cells = sorted(set(roles) | {cell['id'] for cell in headings}
                            | set(first['headerCells'] + second['headerCells'])
                            | set(first.get('columnHeaderCells', []) + second.get('columnHeaderCells', [])))
    return dict(kind='same-section-complete-row-series', ownerEntry=owner,
        ownerHeadingCells=sorted(cell['id'] for cell in headings), columnSignature=signature,
        leftRow=left, rightRow=right, boundaryCellRoles=roles,
        evidenceCells=evidence_cells,
        sourceCellIdentities={key: digest(source_cell_identity(cells[key])) for key in evidence_cells},
        inheritsOpcodes=False, inheritsOperands=False, inheritsMergedCells=False, inheritsFootnotes=False,
        constraintsParsed=False)


def _decision(candidate, review, cells, bundle):
    _fields(review, {'id', 'identity', 'historicalEntryIds', 'fromHeaderCells', 'toHeaderCells',
                     'sourceCellIdentities', 'boundaryCells', 'decision', 'rule', 'rationale', 'structure'}, 'table decision')
    if (review['identity'] != candidate['identity'] or review['historicalEntryIds'] != candidate['entryIds']
            or not review['rationale']):
        raise ValueError('table decision identity or historical ownership differs')
    first, second = candidate['first'], candidate['second']
    a, b = _headers(first, cells), _headers(second, cells)
    if (review['fromHeaderCells'] != [cell['id'] for cell in a]
            or review['toHeaderCells'] != [cell['id'] for cell in b]):
        raise ValueError('reviewed table header source differs')
    required = set(review['fromHeaderCells'] + review['toHeaderCells'] + review['boundaryCells'])
    if not required <= cells.keys() or set(review['sourceCellIdentities']) != required:
        raise ValueError('review omits or introduces source evidence cells')
    for key in required:
        if digest(source_cell_identity(cells[key])) != review['sourceCellIdentities'][key]:
            raise ValueError('reviewed source text, geometry or PDF identity drift')
    source_kind, target_kind = _header_kind(a), _header_kind(b)
    if review['decision'] != 'continuation' and review['structure'] is not None:
        raise ValueError('only a checked table-series decision may carry structural evidence')
    if review['decision'] == 'unresolved':
        if review['rule'] != 'no-independent-structural-proof/v1' or review['boundaryCells']:
            raise ValueError('unresolved relation cannot import an adjudication')
        state = 'accounted'
    elif review['decision'] == 'independent-table':
        if review['rule'] == 'different-explicit-prefix-field-columns/v1':
            expected_fields = first.get('columnHeaderCells', []) + second.get('columnHeaderCells', [])
            from_signature, to_signature = _column_signature(first, cells), _column_signature(second, cells)
            if (source_kind != 'structured-encoding' or target_kind != 'structured-encoding'
                    or review['boundaryCells'] != expected_fields
                    or from_signature[2] != ('VEX', 'RXB.map_select', 'W.vvvv.L.pp', 'Opcode')
                    or to_signature[2] != ('EVEX', "RXBR'.Map", 'W.vvvv.pp', "z.L'L.b.V'.aaa", 'Opcode')):
                raise ValueError('independent table lacks different explicit prefix-field columns')
        else:
            if (review['rule'] != 'semantic-to-explicit-encoding-section/v1'
                    or source_kind not in {'immediate-aliases', 'immediate-selection', 'rounding-controls'}
                    or target_kind not in {'opcode-encoding', 'structured-encoding'}
                    or len(review['boundaryCells']) != 1):
                raise ValueError('independent-table decision has no distinct source column purposes')
            marker = cells[review['boundaryCells'][0]]
            top = min(cell['rect'][1] for cell in b)
            if (marker['text'] != 'Instruction Encoding' or marker['pdfPage'] != second['pdfPage']
                    or not 0 < top - marker['rect'][1] < 40 or marker['rect'][3] > top + 1):
                raise ValueError('independent table lacks its exact preceding encoding-section marker')
            competing = [cell for cell in cells.values() if cell['pdfPage'] == second['pdfPage']
                         and marker['rect'][1] < cell['rect'][1] < top
                         and cell['id'] not in required and cell['text'] in
                         {'Mnemonic', 'Instruction Encoding', 'Instruction Support', 'Related Instructions'}]
            if competing:
                raise ValueError('intervening source heading invalidates table boundary')
        state = 'adjudicated'
    elif review['decision'] == 'continuation':
        if review['rule'] != 'same-section-complete-row-series/v1' or review['boundaryCells']:
            raise ValueError('unproved table continuation rule')
        actual_structure = structural_evidence(bundle, candidate)
        if canonical(review['structure']) != canonical(actual_structure):
            raise ValueError('table-series source boundary or local-row evidence differs')
        state = 'adjudicated'
    else:
        raise ValueError('unsupported or unproved table-relation decision')
    return dict(id=review['id'], kind='table-relation', identity=candidate['identity'],
        state=state, resolution=review['decision'], historicalEntryIds=candidate['entryIds'],
        originalRelation=candidate['originalRelation'], sourceHeaderKind=source_kind,
        targetHeaderKind=target_kind, sourceCells=sorted(required), sourceCellIdentities=review['sourceCellIdentities'],
        rule=review['rule'], rationale=review['rationale'], structure=review['structure'], constraintsParsed=False)


def _validate_review(bundle, reviewed):
    _fields(reviewed, {'schema', 'corpusLockSha256', 'historicalLockSha256', 'scopeSha256',
                       'conflictIssues', 'tableDecisions'}, 'source decisions')
    if reviewed['schema'] != REVIEW_SCHEMA:
        raise ValueError('unsupported source decisions schema')
    for field in ('corpusLockSha256', 'historicalLockSha256'):
        if reviewed[field] != bundle['provenance'][field]:
            raise ValueError('reviewed corpus identity drift')
    if reviewed['scopeSha256'] != digest(bundle['corpusLock']['scope']):
        raise ValueError('reviewed scope identity drift')


def build_ledger(bundle, reviewed):
    """Pure graph derivation from a load_sources() bundle and reviewed decisions.

    Small tests supply source excerpts directly to this pure layer. CLI and
    production callers use load_sources() to establish the full input contract.
    """
    _validate_review(bundle, reviewed)
    lock = bundle['corpusLock']
    if set(bundle['geometries']) != set(PUBLICATIONS):
        raise ValueError('source graph omits a required instruction volume')
    historical, actual_conflicts, cells = {}, {}, {}
    for publication, document in bundle['geometries'].items():
        cells[publication] = _cell_index(document)
        historical[publication] = document['content']['oldGapDispositions']
        records = _unique(historical[publication], 'oldGapId', 'historical gap')
        for key, record in records.items():
            if record['disposition'] == 'source-conflict':
                actual_conflicts[key] = (publication, record)
    nodes, edges = [], []
    scope_id = stable_id('coverage-scope', lock['scope'])
    nodes.append(dict(id=scope_id, kind='coverage-scope', state='accounted', resolution='unresolved',
                      sourceScope=lock['scope'], adoption='not-established'))
    authority_ids = {}
    for document in lock['documents']:
        publication = document['publication']
        key = stable_id('source-authority', dict(publication=publication, pdfSha256=document['pdfSha256']))
        authority_ids[publication] = key
        nodes.append(dict(id=key, kind='source-authority', state='accounted', resolution='unresolved',
            publication=publication, pdfSha256=document['pdfSha256'], originalIdentityClaim=document['officialIdentity'],
            requiredEvidence=['publisher-byte-identity', 'input-bound-migration-review', 'reviewed-corpus-adoption']))
        edges.append(dict(source=scope_id, target=key, relation='requires-source-authority'))
    for extension in lock['scope']['extensionManifest']['entries']:
        key = stable_id('extension-scope', dict(scope=scope_id, extension=extension))
        nodes.append(dict(id=key, kind='extension-scope', state='accounted', resolution='unresolved',
                          originalCandidate=extension, supplementaryDiscovery='open'))
        edges.append(dict(source=scope_id, target=key, relation='requires-scope-adjudication'))
    issue_rows = _unique(reviewed['conflictIssues'], 'id', 'source issue')
    assigned = set()
    for issue in issue_rows.values():
        _fields(issue, {'id', 'title', 'oldGapIds', 'recordDigests', 'requiredAuthority'}, 'source issue')
        if not issue['title'] or not issue['requiredAuthority'] or not issue['oldGapIds']:
            raise ValueError('source issue lacks a concrete unresolved requirement')
        ids = issue['oldGapIds']
        if (len(ids) != len(set(ids)) or set(ids) != set(issue['recordDigests'])
                or assigned & set(ids) or not set(ids) <= actual_conflicts.keys()
                or issue['id'] != stable_id('source-issue', sorted(ids))):
            raise ValueError('source issue omits, duplicates or substitutes a conflict record')
        assigned.update(ids)
        nodes.append(dict(id=issue['id'], kind='source-issue', state='accounted', resolution='unresolved',
            title=issue['title'], oldGapIds=ids, requiredAuthority=issue['requiredAuthority'], correction=None))
        for key in ids:
            publication, record = actual_conflicts[key]
            if digest(record) != issue['recordDigests'][key]:
                raise ValueError('source-conflict object or disposition differs from reviewed input')
            if not set(record['cells']) <= cells[publication].keys():
                raise ValueError('source-conflict references absent source cells')
            nodes.append(dict(id=key, kind='source-conflict', state='accounted', resolution='unresolved',
                publication=publication, originalRecord=record, constraintsParsed=False, authoritativeCorrection=None))
            edges.extend([dict(source=issue['id'], target=key, relation='groups-source-record'),
                          dict(source=key, target=authority_ids[publication], relation='requires-source-authority')])
    if assigned != actual_conflicts.keys():
        raise ValueError('reviewed conflict ledger omits actual source conflicts')
    candidates = _actual_candidates(bundle)
    decisions = _unique(reviewed['tableDecisions'], 'id', 'table decision')
    if set(candidates) != set(decisions):
        raise ValueError('reviewed relation ledger omits or introduces an actual table candidate')
    for key, candidate in candidates.items():
        publication = candidate['identity']['publication']
        node = _decision(candidate, decisions[key], cells[publication], bundle)
        nodes.append(node)
        edges.append(dict(source=key, target=authority_ids[publication], relation='uses-source-corpus'))
    region_documents = _unique(bundle['regions']['content']['documents'], 'publication', 'source-region document')
    if set(region_documents) != set(authority_ids):
        raise ValueError('source constraints omit a required publication')
    for document in lock['documents']:
        publication = document['publication']
        actual = region_documents[publication]
        expected_regions = document['requiredRegions']
        if ([{key: row[key] for key in ('kind', 'selector', 'status')} for row in actual['requiredRegions']]
                != expected_regions or actual['pdfSha256'] != document['pdfSha256']):
            raise ValueError('source constraint regions differ from the declared corpus')
        if [row['pdfPage'] for row in actual['pages']] != list(range(1, document['pdfPages'] + 1)):
            raise ValueError('source region page enumeration omits or duplicates a page')
        for region in expected_regions:
            key = stable_id('source-constraint-region', dict(publication=publication,
                            pdfSha256=document['pdfSha256'], selector=region))
            nodes.append(dict(id=key, kind='source-constraint-region', state='accounted', resolution='unresolved',
                publication=publication, originalRegion=region, constraintsParsed=False,
                requiredWork=['clause-inventory', 'typed-constraints', 'footnote-and-cross-reference-ownership',
                              'independent-source-omission-review']))
            edges.extend([dict(source=scope_id, target=key, relation='requires-constraint-coverage'),
                          dict(source=key, target=authority_ids[publication], relation='uses-source-corpus')])
    node_map = _unique(nodes, 'id', 'graph node')
    if any(edge['source'] not in node_map or edge['target'] not in node_map for edge in edges):
        raise ValueError('obligation graph contains a dangling dependency')
    content = dict(nodes=sorted(nodes, key=lambda node: node['id']),
        edges=sorted(edges, key=lambda edge: (edge['source'], edge['target'], edge['relation'])),
        historicalGapRecords=historical, sourceRegionAccounting=bundle['regions']['content'])
    counts = dict(nodeKinds=dict(sorted(Counter(node['kind'] for node in nodes).items())),
        historicalGapRecords=sum(len(rows) for rows in historical.values()),
        sourceConflictRecords=len(actual_conflicts), sourceIssues=len(issue_rows), tableCandidates=len(candidates),
        tableResolutions=dict(sorted(Counter(node['resolution'] for node in nodes if node['kind'] == 'table-relation').items())),
        unresolvedNodes=sum(node['resolution'] == 'unresolved' for node in nodes))
    return dict(schema=SCHEMA, provenance=bundle['provenance'], reviewedInputSha256=digest(reviewed),
        content=content, contentSha256=digest(content), counts=counts,
        acceptance=dict(initialObligationsAccounted=True,
                        structuralRelationsAdjudicated=all(node['resolution'] != 'unresolved' for node in nodes if node['kind'] == 'table-relation'),
                        sourceConflictsAdjudicated=not actual_conflicts,
                        sourceAuthorityEstablished=False, selectedConstraintsParsed=False, p1Complete=False, c2Complete=False,
                        legalEncodingCompletenessEstablished=False))


def check_ledger(result, expected):
    if result != expected:
        raise ValueError('obligation ledger differs from complete source reconstruction')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('extract', 'check'))
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--pdf-cache', type=Path, required=True)
    parser.add_argument('--geometry', action='append', required=True, help='PUBLICATION=directory containing geometry.json')
    parser.add_argument('--baseline', action='append', required=True, help='PUBLICATION=directory containing inventory.json/layout.txt')
    parser.add_argument('--corpus-lock', type=Path, default=corpus.LOCK)
    parser.add_argument('--review', type=Path, default=REVIEW)
    parser.add_argument('--pdftotext', type=Path, required=True)
    parser.add_argument('--mutool', type=Path, required=True)
    parser.add_argument('--tool-libdir', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    before_review = corpus.sha_file(args.review)
    reviewed = strict_json(args.review.read_bytes())
    sources = load_sources(args.corpus, args.pdf_cache, _maps(args.geometry), _maps(args.baseline),
        dict(pdftotext=args.pdftotext, mutool=args.mutool, python=Path(sys.executable)),
        corpus.environment(args.tool_libdir), args.corpus_lock)
    expected = build_ledger(sources, reviewed)
    if before_review != corpus.sha_file(args.review) or sources['provenance']['extractorSources'] != source_closure():
        raise ValueError('reviewed decisions or implementation changed during ledger derivation')
    output = run_output(args.output)
    if args.command == 'extract':
        output.mkdir(parents=True, exist_ok=False)
        (output / 'obligations.json').write_bytes(canonical(expected) + b'\n')
    else:
        check_ledger(strict_json((output / 'obligations.json').read_bytes()), expected)
    print(json.dumps(dict(counts=expected['counts'], acceptance=expected['acceptance']), sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, StopIteration) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
