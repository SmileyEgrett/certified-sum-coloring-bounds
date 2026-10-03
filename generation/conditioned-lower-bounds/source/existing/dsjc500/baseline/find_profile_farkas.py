#!/usr/bin/env python3
"""Construct an integer Farkas certificate for a fixed residual profile LP."""
from pathlib import Path
import argparse,json,time
import numpy as np
from numerical import linprog
from scipy.sparse import csc_matrix,hstack,vstack
from common import parse_dimacs,enumerate_stable_sets,enumerate_packings,stable_tuple_hash

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--graph',type=Path,required=True);ap.add_argument('--packing',type=int,required=True)
 for k in range(1,5):ap.add_argument(f'--h{k}',type=int,required=True)
 ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();quota={k:getattr(a,f'h{k}') for k in range(1,5)}
 g=parse_dimacs(a.graph);S=enumerate_stable_sets(g,6);best,packs=enumerate_packings(S[5]);p=packs[a.packing-1];top=[S[5][i] for i in p];removed=set().union(*(set(C) for C in top));rem=sorted(set(range(1,501))-removed)
 fam={1:[(v,) for v in rem]}
 for k in (2,3,4):fam[k]=[C for C in S[k] if set(C).isdisjoint(removed)]
 cols=[];types=[]
 for k in range(1,5):cols.extend(fam[k]);types.extend([k]*len(fam[k]))
 rr=[];cc=[];dd=[];b=[]
 for i,v in enumerate(rem):
  for j,C in enumerate(cols):
   if v in C:rr.append(i);cc.append(j);dd.append(1.)
  b.append(1.)
 row=len(rem)
 for k in range(1,5):
  js=[j for j,t in enumerate(types) if t==k];rr.extend([row]*len(js));cc.extend(js);dd.extend([1.]*len(js));b.append(float(quota[k]));row+=1
 A=csc_matrix((dd,(rr,cc)),shape=(row,len(cols)));b=np.array(b);r=A.shape[0]
 Aub=vstack([hstack([-A.T,A.T]),csc_matrix(np.r_[b,-b].reshape(1,-1))],format='csc');bub=np.r_[np.zeros(A.shape[1]),-1.0];st=time.perf_counter();res=linprog(np.ones(2*r),A_ub=Aub,b_ub=bub,bounds=(0,None),method='highs')
 if res.status!=0:raise RuntimeError(res.message)
 y=res.x[:r]-res.x[r:];cert=None
 for D in [10,100,1000,10000,100000,1000000,10**7,10**8,10**9,10**10,10**12]:
  z=[int(round(float(v)*D)) for v in y];repairs=0
  for j in range(A.shape[1]):
   inds=A[:,j].indices;ss=sum(z[i] for i in inds)
   if ss<0:
    i=next(i for i in inds if i<len(rem));z[i]+=-ss;repairs+=-ss
  mn=min(sum(z[i] for i in A[:,j].indices) for j in range(A.shape[1]));rhs=sum(z[i]*int(b[i]) for i in range(r))
  if mn>=0 and rhs<0:cert=(D,z,rhs,mn,repairs);break
 if cert is None:raise RuntimeError('integer repair failed')
 D,z,rhs,mn,repairs=cert;w=z[:len(rem)];mult={k:z[len(rem)+k-1] for k in range(1,5)}
 minima={k:min(sum(w[rem.index(v)] for v in C)+mult[k] for C in fam[k]) for k in range(1,5)}
 out={'schema':'dsjc5009_profile_farkas_v1','graph_raw_sha256':g['raw_sha256'],'graph_canonical_sha256':g['canonical_sha256'],'vertices':500,'packing_number':a.packing,'packing_indices':list(p),'packing_sets':[list(C) for C in top],'residual_vertices':rem,'family_sha256':{str(k):stable_tuple_hash(fam[k]) for k in range(1,5)},'quota':{str(k):quota[k] for k in range(1,5)},'vertex_weights':[[v,x] for v,x in zip(rem,w) if x],'size_multipliers':{str(k):mult[k] for k in range(1,5)},'rhs':rhs,'minimum_columns':{str(k):minima[k] for k in range(1,5)},'source_rounding_denominator':D,'repairs':repairs,'generation_seconds':time.perf_counter()-st}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps({'packing':a.packing,'quota':quota,'rhs':rhs,'minima':minima,'seconds':out['generation_seconds']},indent=2))
if __name__=='__main__':main()
