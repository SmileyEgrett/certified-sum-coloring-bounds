#!/usr/bin/env python3
"""Standard-library fail-closed verifier for residual_kset_lpbb_v2."""
from __future__ import annotations
import argparse, gzip, hashlib, json, sys
from pathlib import Path
from common import parse_dimacs, enumerate_stable_sets, enumerate_packings, stable_tuple_hash

def fail(s: str) -> None:
    raise ValueError(s)

def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

def bits(x: int):
    while x:
        b=x & -x
        yield b.bit_length()-1
        x ^= b

def read_dual(p: Path, res: list[int]) -> dict[int,int]:
    w={}
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        fields=line.split()
        if len(fields)!=2:
            fail('malformed dual')
        v,x=map(int,fields)
        if v in w or v not in res or x<0:
            fail('invalid dual')
        w[v]=x
    if set(w)!=set(res):
        fail('dual residual mismatch')
    return w

def verify(graph: Path, dual: Path, cert: Path) -> dict:
    with gzip.open(cert,'rt') as f:
        d=json.load(f)
    if d.get('schema')!='residual_kset_lpbb_v2':
        fail('schema')
    g=parse_dimacs(graph)
    if (d['graph_raw_sha256'],d['graph_canonical_sha256'],d['vertices']) != (g['raw_sha256'],g['canonical_sha256'],g['n']):
        fail('graph')
    topk=d['top_set_size']; k=d['residual_set_size']
    S=enumerate_stable_sets(g,max(topk,k))
    best,packs=enumerate_packings(S[topk])
    pi=d['packing_number']
    if not 1<=pi<=len(packs):
        fail('packing number')
    pack=packs[pi-1]
    top=[S[topk][i] for i in pack]
    if (d['top_stable_family_sha256']!=stable_tuple_hash(S[topk]) or
        d['maximum_top_packing_size']!=best or
        d['maximum_top_packing_count']!=len(packs) or
        d['packing_indices']!=list(pack) or
        d['packing_sets']!=[list(C) for C in top]):
        fail('packing')
    removed={v for C in top for v in C}
    res=sorted(set(range(1,g['n']+1))-removed)
    allc=[C for C in S[k] if set(C).isdisjoint(removed)]
    if (d['residual_vertices']!=res or
        d['global_residual_set_family_sha256']!=stable_tuple_hash(S[k]) or
        d['residual_set_family_sha256']!=stable_tuple_hash(allc)):
        fail('families')
    D=d['old_dual_denominator']
    w=read_dual(dual,res)
    total=sum(w.values()); B=total//D; slack=total-B*D
    if (d['old_dual_sha256']!=sha(dual) or
        (d['old_dual_total'],d['old_bound'],d['slack_budget'],d['claimed_new_bound'])!=(total,B,slack,B-1)):
        fail('dual binding')
    exall=[sum(w[v] for v in C)-D for C in allc]
    if not exall or min(exall)<0:
        fail('old dual column')
    keep=[i for i,e in enumerate(exall) if e<=slack]
    cols=[allc[i] for i in keep]
    ex=[exall[i] for i in keep]
    n=len(cols)
    if d['allowed_column_count']!=n or d['allowed_columns_sha256']!=stable_tuple_hash(cols):
        fail('allowed')
    inc=[0]*(g['n']+1); full=(1<<n)-1
    for j,C in enumerate(cols):
        for v in C:
            inc[v] |= 1<<j
    conf=[]
    for C in cols:
        z=0
        for v in C:
            z |= inc[v]
        conf.append(z)
    rec=d['records']; seen=set()
    stats={'branches':0,'dual_leaves':0,'count_leaves':0,'budget_leaves':0}
    md=0; Q=d['leaf_denominator']; rset=set(res)
    def visit(i: int, active: int, selected: int, spent: int, depth: int) -> None:
        nonlocal md
        md=max(md,depth)
        if i in seen or not 0<=i<len(rec):
            fail('tree')
        seen.add(i)
        x=rec[i]
        if x['kind']=='budget':
            if x != {'kind':'budget','selected':selected,'spent':spent} or spent<=slack:
                fail('budget')
            stats['budget_leaves']+=1
            return
        if spent>slack:
            fail('overbudget')
        R=slack-spent; need=B-selected
        if need<=0:
            fail('target reached')
        filt=0
        for j in bits(active):
            if ex[j]<=R:
                filt |= 1<<j
        active=filt
        if x['kind']=='count':
            if (x['selected']!=selected or x['remaining_target']!=need or
                x['remaining_budget']!=R or x['active_count']!=active.bit_count() or
                active.bit_count()>=need):
                fail('count')
            stats['count_leaves']+=1
            return
        if x['kind']=='dual':
            W={}; last=0
            for item in x['vertex_weights']:
                if not isinstance(item,list) or len(item)!=2:
                    fail('weight shape')
                v,z=item
                if type(v) is not int or type(z) is not int or v<=last or v not in rset or z<=0:
                    fail('weight')
                last=v; W[v]=z
            M=x['budget_multiplier']
            if type(M) is not int or M<0:
                fail('budget multiplier')
            num=D*sum(W.values())+R*M
            if (x['selected']!=selected or x['remaining_target']!=need or
                x['remaining_budget']!=R or x['denominator']!=Q or
                x['numerator']!=num or num>=need*D*Q):
                fail('dual meta')
            for j in bits(active):
                if D*sum(W.get(v,0) for v in cols[j])+ex[j]*M < D*Q:
                    fail('dual column')
            stats['dual_leaves']+=1
            return
        if x['kind']=='branch':
            j=x['column']
            if type(j) is not int or not 0<=j<n or not (active>>j)&1 or x['one']>=i or x['zero']>=i:
                fail('branch')
            visit(x['one'],active&~conf[j],selected+1,spent+ex[j],depth+1)
            visit(x['zero'],active&~(1<<j),selected,spent,depth+1)
            stats['branches']+=1
            return
        fail('kind')
    visit(d['root'],full,0,0,0)
    if len(seen)!=len(rec):
        fail('unreachable')
    for k0,v in stats.items():
        if d['statistics'].get(k0)!=v:
            fail('stats')
    if (d['statistics'].get('records')!=len(rec) or
        d['statistics'].get('calls')!=len(rec) or
        d['statistics'].get('max_depth')!=md):
        fail('stats2')
    return {'status':'VERIFIED','packing':pi,'bound':B-1,'records':len(rec),'max_depth':md,'certificate_sha256':sha(cert)}

def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument('--graph',type=Path,required=True)
    ap.add_argument('--dual',type=Path,required=True)
    ap.add_argument('--certificate',type=Path,required=True)
    ap.add_argument('--json-out',type=Path)
    a=ap.parse_args()
    z=verify(a.graph,a.dual,a.certificate)
    if a.json_out:
        a.json_out.write_text(json.dumps(z,indent=2,sort_keys=True)+'\n')
    print(json.dumps(z,indent=2,sort_keys=True))
    print('RESIDUAL K-SET LPBB VERIFIED')

if __name__=='__main__':
    try:
        main()
    except Exception as e:
        print('VERIFICATION FAILED:',e,file=sys.stderr)
        raise SystemExit(1)
