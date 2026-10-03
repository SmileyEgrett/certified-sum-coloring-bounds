#!/usr/bin/env python3
"""One-sweep warm-start validation; no search for a target improvement."""
import hashlib,json,subprocess,sys,time
from pathlib import Path
def check(graph,coloring):
    colors={}
    for line in coloring.read_text().splitlines():
        s=line.split()
        if not s or s[0].lower()=='c':continue
        assert len(s)==2
        v,c=map(int,s);assert v not in colors and c>0;colors[v]=c
    edges=0
    with graph.open() as f:
        for line in f:
            s=line.split()
            if not s or s[0].lower()=='c':continue
            if s[0]=='p':n,m=map(int,s[2:]);continue
            u,v=map(int,s[1:]);assert colors[u]!=colors[v];edges+=1
    expected_edges=m//2 if graph.name=='DSJC500.9.col' else m
    assert set(colors)==set(range(1,n+1)) and edges==expected_edges
    return sum(colors.values()),sorted(colors.items())
def main():
    exe=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(exist_ok=False)
    inputs=Path(__file__).resolve().parent/'benchmark-input'
    companion=Path(sys.argv[3]) if len(sys.argv)>3 else None
    witnesses={
        'DSJC250.9':'dsjc250/public_artifact/integrated_checker/data/DSJC250.9_sum8277.coloring',
        'DSJC500.9':'dsjc500/dsjc500_integrated/data/DSJC500.9_sum29848.coloring',
        'DSJC1000.9':'dsjc1000/DSJC1000.9_EXACT_CONDITIONAL_RELEASE_20260728/witness/DSJC1000.9_best.coloring',
        'C2000.9':'c2000_9/upper_witness/best.coloring'
    }
    records=[]
    for name,expected in [('DSJC250.9',8277),('DSJC500.9',29848),('DSJC1000.9',103256),('C2000.9',382379)]:
        graph=inputs/'graphs'/f'{name}.col';initial=inputs/'witnesses'/f'{name}.coloring'
        if companion:
            graph=companion/'graphs'/f'{name}.col'
            initial=companion/'evidence'/witnesses[name]
        assert check(graph,initial)[0]==expected
        for plain in [1,0]:
            repeats=[]
            for repeat in [0,1]:
                label=f'{name}-plain{plain}-{repeat}';color=out/(label+'.coloring')
                argv=[str(exe),'--graph',str(graph),'--initial-coloring',str(initial),'--save-best',str(color),
                      '--plain-sa',str(plain),'--replicas',str(1 if plain else 2),'--threads','1',
                  '--sweeps','1','--size-factor','1','--seed','20261001','--legal-repair','auto']
                if name=='DSJC500.9':argv+=['--edge-count','incidences']
                (out/(label+'.command.json')).write_text(json.dumps(argv)+'\n')
                start=time.monotonic()
                with (out/(label+'.stdout')).open('w') as stdout,(out/(label+'.stderr')).open('w') as stderr:
                    rc=subprocess.call(argv,stdout=stdout,stderr=stderr)
                assert rc==0,label
                value,assignment=check(graph,color);assert value<=expected
                stats=dict(s.split('=',1) for s in (out/(label+'.stdout')).read_text().splitlines() if s.count('=')==1 and not s.startswith('wall_seconds='))
                assert int(stats['best_phi'])==value and int(stats['verified_best_conflicts'])==0
                repeats.append((assignment,stats))
                records.append({'case':label,'verified_sum':value,'starting_sum':expected,'wall_seconds':time.monotonic()-start})
                print(label,value,flush=True)
            assert repeats[0]==repeats[1],f'{name} repeatability'
    (out/'summary.json').write_text(json.dumps({'runs':records,'repeat_pairs':8,'all_proper':True},indent=2)+'\n')

if __name__=='__main__':main()
