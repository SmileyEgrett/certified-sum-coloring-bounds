#!/usr/bin/env python3
"""Independent small-partition and saved C2000 finishing-stage checks."""
import importlib.util,itertools,json,subprocess,sys
from pathlib import Path
package=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(exist_ok=False)
spec=importlib.util.spec_from_file_location('tail',package/'solve_frozen_tail.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
from benchmark_checks import check
def exact_sum(n,edges):
    best=n*(n+1)//2
    labels=[0]*n
    def search(v,largest):
        nonlocal best
        if v==n:
            counts=sorted([labels.count(i) for i in range(largest+1)],reverse=True)
            best=min(best,sum((i+1)*c for i,c in enumerate(counts)));return
        for c in range(largest+2):
            if any(labels[u]==c and (u,v) in edges for u in range(v)):continue
            labels[v]=c;search(v+1,max(largest,c))
    search(0,-1);return best
def run_case(name,n,edges,colors=None,error=False,build_only=False):
    graph=out/(name+'.col');color=out/(name+'.coloring');target=out/name
    graph.write_text(f'p edge {n} {len(edges)}\n'+''.join(f'e {u+1} {v+1}\n' for u,v in sorted(edges)))
    color.write_text(''.join(f'{v+1} {(colors or list(range(1,n+1)))[v]}\n' for v in range(n)))
    old=sys.argv;sys.argv=['solve_frozen_tail','--graph',str(graph),'--coloring',str(color),'--output-dir',str(target),'--threads','1']+(['--build-only'] if build_only else [])
    try:
        try:mod.main()
        except ValueError:
            if error:return
            raise
        assert not error,name
    finally:sys.argv=old
    if build_only:
        assert (target/'frozen_tail.lp').exists() and not (target/'result.json').exists();return
    value,_=check(graph,target/'best.coloring')
    assert value==exact_sum(n,edges),(name,value)
    return json.loads((target/'result.json').read_text())
base=list(itertools.combinations(range(4),2))
for mask in range(64):run_case(f'graph4-{mask}',4,{e for i,e in enumerate(base) if mask>>i&1})
run_case('empty-tail',5,set(),[1]*5)
run_case('frozen-prefix',8,{(u,v) for u in range(5) for v in range(5,8)},[1]*5+[2,3,4])
run_case('invalid-prefix-order',11,set(),[1]*5+list(range(2,8)),error=True)
run_case('model-only',4,{(0,1)},build_only=True)

# Exercise malformed full inputs through the executable interface.
for name,text,assignment in [
    ('duplicate','p edge 2 2\ne 1 2\ne 2 1\n','1 1\n2 2\n'),
    ('missing-edge','p edge 2 1\n','1 1\n2 2\n'),
    ('loop','p edge 2 1\ne 1 1\n','1 1\n2 2\n'),
    ('zero-color','p edge 2 1\ne 1 2\n','1 0\n2 1\n'),
    ('conflict','p edge 2 1\ne 1 2\n','1 1\n2 1\n'),
    ('duplicate-vertex','p edge 2 1\ne 1 2\n','1 1\n1 2\n'),
]:
    g=out/(name+'.col');c=out/(name+'.coloring');g.write_text(text);c.write_text(assignment)
    p=subprocess.run([sys.executable,str(package/'solve_frozen_tail.py'),'--graph',str(g),'--coloring',str(c),'--output-dir',str(out/name)],capture_output=True,text=True)
    assert p.returncode!=0,name
    (out/(name+'.stderr')).write_text(p.stderr)

graph=Path(sys.argv[3]) if len(sys.argv)>3 else package.parent/'benchmark-input/graphs/C2000.9.col'
old=sys.argv;sys.argv=['solve_frozen_tail','--graph',str(graph),'--coloring',str(package/'source-382384.coloring'),'--output-dir',str(out/'c2000'),'--threads','1']
try:mod.main()
finally:sys.argv=old
value,_=check(graph,out/'c2000/best.coloring');assert value==382379
meta=json.loads((out/'c2000/metadata.json').read_text())
assert (meta['tail_vertices'],meta['tail_alpha'],meta['tail_stable_sets'],meta['model_rows'],meta['model_columns'],meta['model_nonzeros'])==(138,4,2051,142,2338,9949)
(out/'summary.json').write_text(json.dumps({'small_graphs_checked_against_bruteforce':64,'empty_tail_passed':True,'frozen_prefix_passed':True,'invalid_prefix_rejected':True,'build_only_passed':True,'malformed_inputs_rejected':6,'c2000_verified_sum':value,'tail_metadata':meta},indent=2)+'\n')
print('TAIL_VALIDATION_PASSED',flush=True)
