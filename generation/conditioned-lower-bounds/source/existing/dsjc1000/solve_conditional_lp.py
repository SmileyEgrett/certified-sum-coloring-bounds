#!/usr/bin/env python3
from __future__ import annotations
import argparse,gzip,json,resource,time,itertools
from pathlib import Path
import numpy as np
import scipy
from numerical import linprog
from scipy.optimize import Bounds
from scipy.sparse import coo_matrix
TOPS=((52,54,175,319,501,704),(76,145,184,672,793,805),(129,150,181,321,456,762))

def load_eligible(root:Path, used:set[int]):
    sets=[];sizes=[]
    for s in range(1,6):
        with gzip.open(root/f'stable_sets_size_{s}.tsv.gz','rt',encoding='ascii') as f:
            next(f)
            for line in f:
                _,_,vs=line.rstrip('\n').split('\t');S=tuple(map(int,vs.split()))
                if used.isdisjoint(S):sets.append(S);sizes.append(s)
    return sets,np.asarray(sizes,dtype=np.int16)

def build(sets,sizes,residual,k):
    row_by_v={v:i for i,v in enumerate(residual)}; nres=len(residual); alpha=5
    caps=[0]+[nres//t for t in range(1,alpha+1)]
    N=len(sets); yidx={};nv=N
    for t in range(1,alpha+1):
        for j in range(1,caps[t]+1):yidx[t,j]=nv;nv+=1
    rows=[];cols=[];data=[]
    for col,S in enumerate(sets):
        for v in S:rows.append(row_by_v[v]);cols.append(col);data.append(1.)
        for t in range(1,len(S)+1):rows.append(nres+t-1);cols.append(col);data.append(1.)
    for (t,j),col in yidx.items():rows.append(nres+t-1);cols.append(col);data.append(-1.)
    A=coo_matrix((np.asarray(data),(np.asarray(rows),np.asarray(cols))),shape=(nres+alpha,nv)).tocsr()
    b=np.zeros(nres+alpha);b[:nres]=1
    c=np.zeros(nv)
    for (t,j),col in yidx.items():c[col]=k+j
    const=6*k*(k+1)//2
    return A,b,c,yidx,caps,const

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--sets',type=Path,required=True);ap.add_argument('--scenario',required=True,help='three bits selecting the three size-6 sets');ap.add_argument('--out-root',type=Path,required=True);ap.add_argument('--time-limit',type=float,default=1800);args=ap.parse_args()
    if len(args.scenario)!=3 or any(c not in '01' for c in args.scenario):raise SystemExit('bad scenario')
    selected=[TOPS[i] for i,c in enumerate(args.scenario) if c=='1'];used=set(itertools.chain.from_iterable(selected));k=len(selected);residual=[v for v in range(1,1001) if v not in used]
    out=args.out_root/args.scenario;out.mkdir(parents=True,exist_ok=True)
    t0=time.perf_counter();sets,sizes=load_eligible(args.sets,used);t1=time.perf_counter();A,b,c,yidx,caps,const=build(sets,sizes,residual,k);t2=time.perf_counter()
    print(json.dumps({'stage':'built','scenario':args.scenario,'k':k,'eligible_sets':len(sets),'variables':A.shape[1],'constraints':A.shape[0],'nnz':A.nnz,'constant':const}),flush=True)
    lb=np.zeros(A.shape[1]);ub=np.ones(A.shape[1]);ub[:len(sets)]=np.inf
    r=linprog(c,A_eq=A,b_eq=b,bounds=np.column_stack((lb,ub)),method='highs',options={'disp':True,'presolve':True,**({'time_limit':args.time_limit} if args.time_limit > 0 else {}),'dual_feasibility_tolerance':1e-9,'primal_feasibility_tolerance':1e-9,'ipm_optimality_tolerance':1e-10});t3=time.perf_counter()
    summary={'schema':'dsjc1000_conditional_lp_numerical_v1','scenario':args.scenario,'selected_top_classes':[list(x) for x in selected],'k':k,'residual_vertices':len(residual),'eligible_sets':len(sets),'variables':A.shape[1],'constraints':A.shape[0],'nonzeros':A.nnz,'constant':const,'status':int(r.status),'success':bool(r.success),'message':str(r.message),'variable_objective':None if r.fun is None else float(r.fun),'total_objective':None if r.fun is None else float(r.fun+const),'iterations':int(r.nit),'timing_seconds':{'load_filter':t1-t0,'build':t2-t1,'solve':t3-t2,'total':t3-t0},'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'scipy':scipy.__version__}
    if r.x is not None:
        x=r.x[:len(sets)];summary['q_residual_by_threshold']=[float(x[sizes>=t].sum()) for t in range(1,6)];summary['x_positive']=int(np.count_nonzero(x>1e-9))
        np.savez_compressed(out/'numerical_solution.npz',x=x,eqlin_marginals=r.eqlin.marginals,upper_marginals=r.upper.marginals,lower_marginals=r.lower.marginals,sizes=sizes,residual=np.asarray(residual,dtype=np.int16))
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print('FINAL',json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':main()
