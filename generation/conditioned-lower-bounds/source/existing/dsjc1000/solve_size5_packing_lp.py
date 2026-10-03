#!/usr/bin/env python3
import argparse,gzip,json,itertools,time,resource
from pathlib import Path
import numpy as np
from numerical import linprog
from scipy.sparse import coo_matrix
TOPS=((52,54,175,319,501,704),(76,145,184,672,793,805),(129,150,181,321,456,762))
a=argparse.ArgumentParser();a.add_argument('--sets',type=Path,required=True);a.add_argument('--scenario',required=True);a.add_argument('--out',type=Path,required=True);args=a.parse_args()
used=set(itertools.chain.from_iterable(TOPS[i] for i,c in enumerate(args.scenario) if c=='1'));res=[v for v in range(1,1001) if v not in used];row={v:i for i,v in enumerate(res)}
sets=[]
with gzip.open(args.sets/'stable_sets_size_5.tsv.gz','rt') as f:
 next(f)
 for line in f:
  _,_,vs=line.rstrip().split('\t');S=tuple(map(int,vs.split()))
  if used.isdisjoint(S):sets.append(S)
rows=[];cols=[]
for j,S in enumerate(sets):
 for v in S:rows.append(row[v]);cols.append(j)
A=coo_matrix((np.ones(len(rows)),(rows,cols)),shape=(len(res),len(sets))).tocsr()
t=time.time();r=linprog(-np.ones(len(sets)),A_ub=A,b_ub=np.ones(len(res)),bounds=(0,None),method='highs',options={'presolve':True,'dual_feasibility_tolerance':1e-9,'primal_feasibility_tolerance':1e-9});elapsed=time.time()-t
out={'scenario':args.scenario,'eligible_size5_sets':len(sets),'status':int(r.status),'success':bool(r.success),'message':str(r.message),'packing_lp_optimum':None if r.fun is None else -float(r.fun),'elapsed':elapsed,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
if r.x is not None:
 np.savez_compressed(args.out.with_suffix('.npz'),x=r.x,ineqlin_marginals=r.ineqlin.marginals,ineqlin_residual=r.ineqlin.residual,residual=np.array(res,dtype=np.int16))
args.out.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
