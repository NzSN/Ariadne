#!/usr/bin/env python3
"""Independent source projection, DFS closure, Tarjan SCC and distance observer.

Reads a self-contained publication; does not invoke an Ariadne algorithm.
Cryptographic admission/replay is a separate Rust public-API check.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sys
sys.setrecursionlimit(100000)

def number(v): return int(v,16) if isinstance(v,str) else v

def node(n): return (n['frame'],number(n['site']))

def edge(e): return (node(e['src']),node(e['dst']),e['kind'])

def closure(start,adj):
    seen=set();stack=[start]
    while stack:
        at=stack.pop()
        if at in seen: continue
        seen.add(at);stack.extend(adj[at])
    return seen

def check(path):
    raw=json.loads(path.read_text());a=raw['assessment'];s=json.loads(raw['source_json'])
    dictionary={e['id']:e['node'] for e in s['evidence']};memo={}
    def resolve(i):
        if i in memo:return memo[i]
        n=dictionary[i]
        if n['kind']=='scalar':v=n['value']
        elif n['kind']=='array':v=[resolve(j) for j in n['items']]
        else:v={k:resolve(j) for k,j in n['members'].items()}
        memo[i]=v;return v
    projection=resolve(s['projection']['id']);chain=resolve(s['chain']['id'])
    maps=[m for m in projection['frames'] if not m['auxiliary'] and a['to_frame']<=m['frame']<=a['from_frame']]
    assert a['conditional_on']==s.get('conditional_on',[])
    expected_nodes=set()
    for m in maps:
        f=chain['frames'][m['frame']]
        for n in m['nodes']:
            va=number(n['va']);begin=f['function_begin'];end=f['function_end']
            if (begin is None or va>=number(begin)) and (end is None or va+len(n['bytes_hex'])//2<=number(end)):
                expected_nodes.add((m['frame'],va))
    assert set(map(node,a['nodes']))==expected_nodes
    active={l['caller']:(l['caller'],number(l['call_site'])) for l in projection['links'] if l['admitted']}
    expected_edges=set();context=[]
    for m in maps:
        for e in m['edges']:
            x,y,k=edge(e)
            if k=='call' or (m['frame']>a['to_frame'] and active.get(m['frame'])==x) or x not in expected_nodes or y not in expected_nodes:
                context.append(edge(e))
            else:expected_edges.add(edge(e))
    for l in projection['links']:
        if l['admitted'] and l['caller']<=a['from_frame'] and l['child']>=a['to_frame']:
            x=(l['caller'],number(l['call_site']));y=(l['child'],number(l['child_entry']))
            if x in expected_nodes and y in expected_nodes:expected_edges.add((x,y,'call'))
    assert set(map(edge,a['edges']))==expected_edges
    assert sorted(edge(e['edge']) for e in a['context_edges'])==sorted(context)
    expected_gaps=[(m['frame'],g) for m in maps for g in m['gaps']]
    assert [(f['frame'],f['gap']) for f in a['frontiers']]==expected_gaps
    adj=defaultdict(list);rev=defaultdict(list)
    for x,y,k in expected_edges:adj[x].append(y);rev[y].append(x)
    corridor=set();forward=set()
    if a['start'] and a['endpoint'] and not a['anchor_gaps']:
        start=node(a['start']);end=node(a['endpoint']);forward=closure(start,adj);backward=closure(end,rev);corridor=forward&backward
        assert set(map(node,a['forward']))==forward;assert set(map(node,a['backward']))==backward;assert set(map(node,a['corridor']))==corridor
        assert a['connection']==('found' if end in forward else 'absent_in_represented_graph')
        for f in a['frontiers']:
            n=(f['frame'],number(f['gap']['site']))
            relation='on_corridor' if n in corridor else 'forward_reachable' if n in forward else 'other_region' if n in expected_nodes else 'unclassified'
            assert f['relation']==relation
    indices={};low={};stack=[];on=set();groups=[]
    def visit(v):
        indices[v]=low[v]=len(indices);stack.append(v);on.add(v)
        for w in adj[v]:
            if w not in indices:visit(w);low[v]=min(low[v],low[w])
            elif w in on:low[v]=min(low[v],indices[w])
        if low[v]==indices[v]:
            group=[]
            while True:
                w=stack.pop();on.remove(w);group.append(w)
                if w==v:break
            groups.append(tuple(sorted(group)))
    for n in sorted(expected_nodes):
        if n not in indices:visit(n)
    assert sorted(groups)==sorted(tuple(map(node,c['members'])) for c in a['components'])
    owner={node(n):c['id'] for c in a['components'] for n in c['members']}
    for c in a['components']:
        assert c['cyclic']==(len(c['members'])>1 or any(x==y==node(c['members'][0]) for x,y,k in expected_edges))
    inter={(x,y,k) for x,y,k in expected_edges if owner[x]!=owner[y]}
    assert inter=={edge(e) for q in a['condensation'] for e in q['original_edges']}
    for q in a['condensation']:
        assert q['source']!=q['destination']
        assert all(owner[edge(e)[0]]==q['source'] and owner[edge(e)[1]]==q['destination'] and edge(e)[2]==q['kind'] for e in q['original_edges'])
    assert len(a['examples'])<a['example_count_bound']
    if a['examples']:
        distance={node(a['start']):0}
        for _ in expected_nodes:
            changed=False
            for x,y,k in sorted(expected_edges):
                if x in distance and distance.get(y,float('inf'))>distance[x]+1:distance[y]=distance[x]+1;changed=True
            if not changed:break
        assert len(a['examples'][0]['edges'])==distance[node(a['endpoint'])]
        assert a['examples'][0]['shortest_in_represented_graph']
    for p in a['examples']:
        ns=list(map(node,p['nodes']));es=list(map(edge,p['edges']))
        assert len(ns)==len(set(ns));assert len(es)+1==len(ns)
        assert ns[0]==node(a['start']) and ns[-1]==node(a['endpoint'])
        assert all(e in expected_edges and e[:2]==(ns[i],ns[i+1]) for i,e in enumerate(es))
    return dict(passed=True,source_binding=s['structure_id'],source_sha256=hashlib.sha256(raw['source_json'].encode()).hexdigest(),publication_binding=raw['publication_binding'],nodes=len(expected_nodes),edges=len(expected_edges),corridor=len(corridor),components=len(groups),cyclic=sum(c['cyclic'] for c in a['components']),frontiers=len(a['frontiers']),examples=len(a['examples']),shortest_edges=len(a['examples'][0]['edges']) if a['examples'] else None)

def main():
    p=argparse.ArgumentParser();p.add_argument('report',type=Path);p.add_argument('--output',type=Path);args=p.parse_args()
    result=check(args.report);text=json.dumps(result,indent=2)+'\n';print(text,end='')
    if args.output:args.output.write_text(text)
if __name__=='__main__':main()
