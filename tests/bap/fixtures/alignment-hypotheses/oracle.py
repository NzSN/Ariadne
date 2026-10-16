#!/usr/bin/env python3
"""Independent finite aligned16 hypothesis oracle over explicit product vertices.

This enumerates (activation, semantic point, RSP residue) vertices, rather than
using the Rust kernel's node-wise bitset fixed point. It imports no Ariadne/BAP
code or producer result. Capture/decoder/predicate recognition are synthetic
binding premises here; concrete source controls belong to runtime tests.
--check verifies the frozen contract; --write is an intentional reviewed freeze.
"""
from __future__ import annotations

import argparse
from collections import deque
from copy import deepcopy
import hashlib
import json
from pathlib import Path

TOP = list(range(16))
PROFILE = 'captured-site-alignment-hypotheses/v1'
POLICY = 'assumed-reviewed-movaps-alignment16/v1'
HERE = Path(__file__).resolve().parent


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def bindings():
    return dict(snapshot='snapshot-a', artifact='artifact-a', query='query-a', chain='chain-a',
                thread=7, activation='a', root=1, epoch=3, profile=PROFILE)


def source(site, displacement=0):
    return dict(site=site, displacement=displacement, captured=True, reviewed=True, alignment=16,
                predicate='effective-address-aligned-16', bytes_sha256=f'bytes-{site}-{displacement}',
                ast_sha256=f'original-ast-{site}-{displacement}', decoder_sha256=f'decoder-{site}',
                pending_relation_sha256=f'independent-rsp-identity-{site}')


def hypothesis(source):
    return dict(bindings(), point=source['site'], displacement=source['displacement'], alignment=16,
                predicate=source['predicate'], bytes_sha256=source['bytes_sha256'],
                ast_sha256=source['ast_sha256'], decoder_sha256=source['decoder_sha256'],
                pending_relation_sha256=source['pending_relation_sha256'], policy=POLICY)


def graph():
    guard = source(2)
    return dict(bindings=bindings(), nodes=[dict(site=n, transfer='identity', delta=0) for n in range(1, 6)],
                roots=[dict(activation='a', site=1, residues=TOP)],
                edges=[dict(src=n, dst=n+1, kind='next') for n in (1, 2, 3)],
                guards=[guard], hypotheses=[hypothesis(guard)], closed=True, barriers=[],
                max_states=4096, max_transfers=16384, max_closure_rounds=4)


def invalid_reason(g):
    ids = {node['site'] for node in g['nodes']}
    if len(ids) != len(g['nodes']) or not ids:
        return 'invalid-node-domain'
    if any(edge['src'] not in ids or edge['dst'] not in ids for edge in g['edges']):
        return 'invalid-edge-domain'
    primary_roots = [root['site'] for root in g['roots'] if root['activation'] == g['bindings']['activation']]
    if primary_roots != [g['bindings']['root']]:
        return 'invalid-bound-root'
    sources = {guard['site']: guard for guard in g['guards']}
    if len(sources) != len(g['guards']):
        return 'duplicate-guard'
    points = []
    for h in g['hypotheses']:
        if h['point'] in points:
            return 'duplicate-hypothesis'
        points.append(h['point'])
        if h['point'] not in sources:
            return 'hypothesis-not-guard'
        s = sources[h['point']]
        if not s['captured'] or not s['reviewed']:
            return 'unsupported-source'
        for key in ('snapshot', 'artifact', 'query', 'chain', 'thread', 'activation', 'root', 'epoch', 'profile'):
            if h[key] != g['bindings'][key]:
                return 'hypothesis-scope-' + key
        if h['profile'] != PROFILE or h['policy'] != POLICY:
            return 'unsupported-profile'
        for key in ('displacement', 'alignment', 'predicate', 'bytes_sha256', 'ast_sha256', 'decoder_sha256', 'pending_relation_sha256'):
            if h[key] != s[key]:
                return 'hypothesis-source-' + key
        if h['alignment'] != 16 or h['predicate'] != 'effective-address-aligned-16':
            return 'unsupported-predicate'
    return None


def transition(node, residue):
    kind = node['transfer']
    if kind == 'identity':
        return [residue]
    if kind == 'add':
        return [(residue + node['delta']) % 16]
    if kind == 'havoc':
        return TOP
    raise ValueError('unsupported independent transfer')


def reach(g, conditional):
    """Explicit finite product BFS; unvisited hypotheses never seed vertices."""
    nodes = {node['site']: node for node in g['nodes']}
    masks = {(h['activation'], h['point']): (-h['displacement']) % 16 for h in g['hypotheses']} if conditional else {}
    outgoing = {site: [edge['dst'] for edge in g['edges'] if edge['src'] == site and edge['kind'] != 'call'] for site in nodes}
    roots = {(r['activation'], r['site'], residue) for r in g['roots'] for residue in r['residues']}
    pending = deque(sorted(roots))
    seen = set()
    transfers = 0
    while pending:
        item = pending.popleft()
        if item in seen:
            continue
        if conditional and len(seen) >= g['max_states']:
            return None, 'product-state-limit'
        seen.add(item)
        activation, site, residue = item
        if (activation, site) in masks and residue != masks[(activation, site)]:
            continue
        for target in outgoing[site]:
            if conditional and transfers >= g['max_transfers']:
                return None, 'product-transfer-limit'
            transfers += 1
            pending.extend((activation, target, after) for after in transition(nodes[site], residue))
    return seen, None


def verdict(residues, displacement, closed=True):
    address = sorted({(r+displacement) % 16 for r in residues})
    if not closed:
        return 'unknown', address
    if not residues:
        return 'unreached', address
    if address == [0]:
        return 'aligned', address
    if 0 not in address:
        return 'misaligned', address
    return 'unknown', address


def expected(g):
    invalid = invalid_reason(g)
    if invalid:
        return dict(status='invalid', reason=invalid)
    baseline, _ = reach(g, False)
    stopped = ('open-coverage' if not g['closed'] or g['barriers'] else
               'closure-epoch-limit' if g['bindings']['epoch'] >= g['max_closure_rounds'] else
               'zero-work' if not g['max_states'] or not g['max_transfers'] else None)
    conditional = None
    if stopped is None:
        conditional, stopped = reach(g, True)
    activations = sorted({root['activation'] for root in g['roots']})
    masks = {(h['activation'], h['point']): (-h['displacement']) % 16 for h in g['hypotheses']}
    facts = []
    baseline_facts = []
    decisions = []
    selections = []
    for activation in activations:
        for node in g['nodes']:
            site = node['site']
            original = sorted(r for a,n,r in baseline if a == activation and n == site)
            baseline_facts.append(dict(activation=activation, site=site, residues=original))
            if stopped is None:
                incoming = sorted(r for a,n,r in conditional if a == activation and n == site)
                filtered = [r for r in incoming if (activation, site) not in masks or r == masks[(activation, site)]]
                facts.append(dict(activation=activation, site=site, incoming=incoming, residues=filtered))
        for guard in g['guards']:
            site = guard['site']
            original = sorted(r for a,n,r in baseline if a == activation and n == site)
            base, _ = verdict(original, guard['displacement'], g['closed'] and not g['barriers'])
            values = next((row['residues'] for row in facts if row['activation'] == activation and row['site'] == site), [])
            current, address = verdict(values, guard['displacement'], stopped is None)
            basis = ('proved' if current == 'aligned' and base == 'aligned' else
                     'assumed' if current == 'aligned' else
                     'unreachable' if current == 'unreached' else 'unknown')
            decisions.append(dict(activation=activation, site=site, baseline_verdict=base, verdict=current,
                                  basis=basis, input_residues=values, address_residues=address,
                                  normal_selected=current == 'aligned'))
            if current == 'aligned':
                selections.extend(dict(activation=activation, src=site, dst=edge['dst'], basis=basis)
                                  for edge in g['edges'] if edge['src'] == site and edge['kind'] != 'call')
    return dict(status='unknown' if stopped else 'complete', reason=stopped, baseline_facts=baseline_facts,
                facts=facts, decisions=decisions, normal_edges=selections,
                hypothesis_context=[digest(h) for h in g['hypotheses']],
                roots=g['roots'])


def cases():
    rows = []
    def add(name, edit=None):
        g = graph()
        if edit:
            edit(g)
        rows.append(dict(name=name, input=g, expected=expected(g)))
    add('unknown-becomes-assumed')
    add('aligned-remains-proved', lambda g: g['roots'][0].update(residues=[0]))
    add('misaligned-conditional-branch-unreachable', lambda g: g['roots'][0].update(residues=[4]))
    add('mixed-incoming-filtered', lambda g: g['roots'][0].update(residues=[0,4]))
    add('unreached-point-is-not-seeded', lambda g: g.update(edges=[dict(src=2,dst=3,kind='next')]))
    def self_support(g):
        g.update(roots=[dict(activation='a',site=5,residues=TOP)],edges=[dict(src=2,dst=3,kind='next'),dict(src=3,dst=2,kind='jump')])
        g['bindings']['root']=5;g['hypotheses'][0]['root']=5
    add('cycle-without-entrance-is-not-self-support', self_support)
    add('open-coverage-stays-unknown', lambda g: g.update(closed=False))
    add('barrier-stays-unknown', lambda g: g.update(barriers=[3]))
    add('closure-epoch-below-boundary', lambda g:g.update(max_closure_rounds=2))
    add('closure-epoch-exact-boundary', lambda g:g.update(max_closure_rounds=3))
    add('closure-epoch-above-boundary', lambda g:g.update(max_closure_rounds=4))
    add('zero-state-budget-stays-unknown', lambda g: g.update(max_states=0))
    add('zero-transfer-budget-stays-unknown', lambda g: g.update(max_transfers=0))
    add('aligned-baseline-survives-stopped-conditional', lambda g: (g['roots'][0].update(residues=[0]),g.update(max_states=0)))
    add('finite-state-budget-stop-discards-partial-facts', lambda g: g.update(max_states=1))
    def signed(g):
        g['guards'][0]['displacement']=-8;g['hypotheses']=[hypothesis(g['guards'][0])]
    add('signed-displacement-minus-eight', signed)
    def two(g):
        g['nodes'][2].update(transfer='add',delta=8);g['guards'].append(source(4,8));g['edges'].append(dict(src=4,dst=5,kind='next'));g['hypotheses']=[hypothesis(s) for s in g['guards']]
    add('two-point-hypotheses', two)
    def bypass(g):
        g['edges'].append(dict(src=1,dst=3,kind='next'));g['guards'].append(source(4));g['edges'].append(dict(src=4,dst=5,kind='next'))
    add('bypass-merge-is-not-globally-filtered', bypass)
    def clobber(g):
        g['nodes'][2].update(transfer='havoc');g['guards'].append(source(4));g['edges'].append(dict(src=4,dst=5,kind='next'))
    add('clobber-after-hypothesis-is-unknown', clobber)
    def loop(g):
        g['nodes'][2].update(transfer='add',delta=8);g['edges'].append(dict(src=3,dst=2,kind='jump'))
    add('hypothesis-applies-every-loop-visit', loop)
    add('recursive-activation-hypothesis-does-not-leak', lambda g:g['roots'].append(dict(activation='b',site=1,residues=TOP)))
    add('call-target-is-not-local-work', lambda g:g['edges'].append(dict(src=1,dst=5,kind='call')))
    add('no-hypotheses-default-mathematical-projection', lambda g:g.update(hypotheses=[]))
    for field,value in [('snapshot','other'),('artifact','other'),('query','other'),('chain','other'),('thread',8),('activation','b'),('root',5),('epoch',4),('profile','wrong'),('predicate','aligned-8'),('bytes_sha256','changed'),('ast_sha256','changed'),('decoder_sha256','changed'),('pending_relation_sha256','changed')]:
        add('reject-changed-'+field, lambda g,field=field,value=value:g['hypotheses'][0].update({field:value}))
    add('reject-uncaptured-source',lambda g:g['guards'][0].update(captured=False))
    add('reject-unsupported-source',lambda g:g['guards'][0].update(reviewed=False))
    return rows


def contract():
    return dict(schema='ariadne.alignment-hypothesis-oracle/v1',
                scope='Independent finite product graph; no Rust/BAP evaluator or ISA proof; source identity checks are synthetic premises',
                model='Specs/AriadneAlignmentHypothesis.tla', facts_semantics='incoming before point filter; residues after point filter',
                hypothesis_quantifier='every visit in selected physical activation; never an entry root',
                cases=cases())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--check',action='store_true')
    mode.add_argument('--write',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    data=contract();text=json.dumps(data,indent=2)+'\n';path=HERE/'contract.json'
    if args.write:
        path.write_text(text)
    elif not path.exists() or path.read_text()!=text:
        raise SystemExit('frozen independent alignment hypothesis contract differs')
    result=dict(schema='ariadne.alignment-hypothesis-oracle-check/v1',cases=len(data['cases']),
                complete_cases=sum(row['expected']['status']=='complete' for row in data['cases']),
                invalid_cases=sum(row['expected']['status']=='invalid' for row in data['cases']),
                fixture_sha256=hashlib.sha256(text.encode()).hexdigest(),passed=True)
    if args.output:args.output.write_text(json.dumps(result,indent=2)+'\n')
    print('Independent alignment hypothesis oracle PASS:',result['cases'],'cases')


if __name__=='__main__':main()
