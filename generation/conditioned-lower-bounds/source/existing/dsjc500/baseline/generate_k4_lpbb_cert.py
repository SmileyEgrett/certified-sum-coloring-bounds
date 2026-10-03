#!/usr/bin/env python3
"""Generate exact residual-quad branch certificates for selected DSJC500.9 packings.

The optimizer is only a certificate-construction oracle. Every emitted leaf is
repaired and checked in integer arithmetic. The final verifier is independent
of SciPy/HiGHS.
"""
from __future__ import annotations
from pathlib import Path
import argparse,gzip,json,math,time
import numpy as np
from numerical import linprog
from scipy.sparse import csc_matrix,vstack
from common import parse_dimacs,enumerate_stable_sets,enumerate_packings,stable_tuple_hash,sha256_file
D=10**12; Q=10**9

def read_weights(path,residual):
 w={}
 for ln,line in enumerate(path.read_text('utf-8').splitlines(),1):
  f=line.split()
  if len(f)!=2:raise ValueError(f'{path}:{ln}: malformed')
  v,x=map(int,f)
  if v in w or v not in residual or x<0:raise ValueError(f'{path}:{ln}: invalid')
  w[v]=x
 if set(w)!=set(residual):raise ValueError('dual residual mismatch')
 return w

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--graph',type=Path,required=True);ap.add_argument('--dual',type=Path,required=True);ap.add_argument('--packing',type=int,required=True);ap.add_argument('--time-limit',type=float,default=120);ap.add_argument('--node-limit',type=int,default=10000);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 g=parse_dimacs(a.graph);S=enumerate_stable_sets(g,6);best,packs=enumerate_packings(S[5])
 if best!=15 or len(packs)!=8 or a.packing not in (1,3,5,6,7,8):raise ValueError('unexpected packing request')
 pack=packs[a.packing-1];top=[S[5][i] for i in pack];removed=set().union(*(set(C) for C in top));residual=sorted(set(range(1,g['n']+1))-removed);ridx={v:i for i,v in enumerate(residual)}
 w0=read_weights(a.dual,residual);total=sum(w0.values());old_bound=total//D;slack=total%D
 if old_bound!=102:raise ValueError('this generator is for old bound 102 cases')
 allq=[C for C in S[4] if set(C).isdisjoint(removed)];exall=[sum(w0[v] for v in C)-D for C in allq]
 if min(exall)<0:raise ValueError('old dual invalid')
 keep=[i for i,e in enumerate(exall) if e<=slack];q=[allq[i] for i in keep];qe=np.array([exall[i] for i in keep],dtype=np.int64);nq=len(q)
 inc=[0]*(g['n']+1)
 for j,C in enumerate(q):
  for v in C:inc[v]|=1<<j
 full=(1<<nq)-1;disj=[]
 for C in q:
  conf=0
  for v in C:conf|=inc[v]
  disj.append(full&~conf)
 rr=[];cc=[]
 for j,C in enumerate(q):
  for v in C:rr.append(ridx[v]);cc.append(j)
 Afull=csc_matrix((np.ones(len(rr)),(rr,cc)),shape=(len(residual),nq))
 records=[];stats={'branches':0,'dual_leaves':0,'count_leaves':0,'budget_leaves':0};calls=0;maxdepth=0;t0=time.perf_counter()
 def inds(active):
  z=[]
  while active:
   b=active&-active;z.append(b.bit_length()-1);active^=b
  return z
 def lp(ii,R):
  A=Afull[:,ii];budget=np.array([qe[i]/D for i in ii],dtype=float).reshape(1,-1);Aub=vstack([A,csc_matrix(budget)],format='csc');bub=np.r_[np.ones(len(residual)),R/D]
  return linprog(-np.ones(len(ii)),A_ub=Aub,b_ub=bub,bounds=(0,None),method='highs')
 def leaf(res,ii,R,selected,need):
  marg=-np.asarray(res.ineqlin.marginals);y=np.maximum(marg[:len(residual)],0.0);mu=max(float(marg[-1]),0.0)
  W=[int(math.ceil(float(z)*Q-1e-10)) for z in y];M=int(math.ceil(mu*Q-1e-10));repairs=0
  for j in ii:
   lhs=D*sum(W[ridx[v]] for v in q[j])+int(qe[j])*M
   if lhs<D*Q:
    add=(D*Q-lhs+D-1)//D;W[ridx[q[j][0]]]+=add;repairs+=add
  if any(D*sum(W[ridx[v]] for v in q[j])+int(qe[j])*M<D*Q for j in ii):raise AssertionError('repair failed')
  numerator=D*sum(W)+R*M
  if numerator>=need*D*Q:return None
  return {'kind':'dual','selected':selected,'remaining_target':need,'remaining_budget':R,'denominator':Q,'budget_multiplier':M,'vertex_weights':[[v,W[ridx[v]]] for v in residual if W[ridx[v]]],'numerator':numerator,'repairs':repairs}
 def emit(r):records.append(r);return len(records)-1
 def dfs(active,selected,spent,depth):
  nonlocal calls,maxdepth
  calls+=1;maxdepth=max(maxdepth,depth)
  if (a.node_limit > 0 and calls>a.node_limit) or (a.time_limit > 0 and time.perf_counter()-t0>a.time_limit):raise TimeoutError('certificate generation cap')
  if spent>slack:stats['budget_leaves']+=1;return emit({'kind':'budget','selected':selected,'spent':spent})
  R=slack-spent;need=old_bound-selected
  if need<=0:raise RuntimeError('forbidden packing found')
  aa=0;x=active
  while x:
   b=x&-x;j=b.bit_length()-1;x^=b
   if qe[j]<=R:aa|=b
  active=aa
  if active.bit_count()<need:stats['count_leaves']+=1;return emit({'kind':'count','selected':selected,'remaining_target':need,'remaining_budget':R,'active_count':active.bit_count()})
  ii=inds(active);res=lp(ii,R)
  if res.status!=0:raise RuntimeError(f'optimizer failed during generation: {res.status} {res.message}')
  L=leaf(res,ii,R,selected,need)
  if L is not None:stats['dual_leaves']+=1;return emit(L)
  vals=res.x;frac=[(abs(float(x)-.5),k) for k,x in enumerate(vals) if 1e-7<float(x)<1-1e-7]
  if frac:k=min(frac)[1]
  else:
   pos=[k for k,x in enumerate(vals) if x>1e-7]
   if not pos:raise AssertionError('nonclosing zero LP')
   k=pos[0]
  j=ii[k]
  one=dfs(active&disj[j],selected+1,spent+int(qe[j]),depth+1);zero=dfs(active&~(1<<j),selected,spent,depth+1);stats['branches']+=1
  return emit({'kind':'branch','column':j,'one':one,'zero':zero})
 root=dfs(full,0,0,0);elapsed=time.perf_counter()-t0
 cert={'schema':'dsjc5009_residual_k4_lpbb_v1','graph_raw_sha256':g['raw_sha256'],'graph_canonical_sha256':g['canonical_sha256'],'vertices':g['n'],'packing_number':a.packing,'packing_indices':list(pack),'packing_sets':[list(C) for C in top],'stable4_family_sha256':stable_tuple_hash(S[4]),'residual4_family_sha256':stable_tuple_hash(allq),'old_dual_sha256':sha256_file(a.dual),'old_dual_denominator':D,'old_dual_total':total,'old_bound':old_bound,'slack_budget':slack,'allowed_column_count':nq,'allowed_columns_sha256':stable_tuple_hash(q),'claimed_new_bound':101,'leaf_denominator':Q,'root':root,'records':records,'statistics':stats|{'records':len(records),'calls':calls,'max_depth':maxdepth,'generation_seconds':elapsed},'generator_note':'Floating-point LP was used only to construct branches and candidate duals. Stored leaves were repaired and checked with integer arithmetic.'}
 a.out.parent.mkdir(parents=True,exist_ok=True);payload=(json.dumps(cert,separators=(',',':'),sort_keys=True)+'\n').encode()
 with a.out.open('wb') as f:
  with gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0) as z:z.write(payload)
 print(json.dumps({'packing':a.packing,'allowed':nq,'new_bound':101}|cert['statistics'],indent=2))
if __name__=='__main__':main()
