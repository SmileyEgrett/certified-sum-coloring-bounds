#!/usr/bin/env python3
"""Generate an exact one-unit residual k-set packing LPBB certificate."""
from __future__ import annotations
import argparse,gzip,json,math,time,hashlib
from pathlib import Path
import numpy as np
from numerical import linprog
from scipy.sparse import csc_matrix,vstack
from common import parse_dimacs,enumerate_stable_sets,enumerate_packings,stable_tuple_hash

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bits(x):
 while x:
  b=x&-x;yield b.bit_length()-1;x^=b
def read_dual(p,res):
 w={}
 for n,line in enumerate(p.read_text().splitlines(),1):
  if not line.strip():continue
  f=line.split()
  if len(f)!=2:raise ValueError('malformed dual')
  v,x=map(int,f)
  if v not in res or v in w or x<0:raise ValueError('invalid dual')
  w[v]=x
 if set(w)!=set(res):raise ValueError('dual residual mismatch')
 return w
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--graph',type=Path,required=True);ap.add_argument('--top-size',type=int,required=True);ap.add_argument('--residual-set-size',type=int,required=True);ap.add_argument('--packing-number',type=int,required=True);ap.add_argument('--dual',type=Path,required=True);ap.add_argument('--dual-denominator',type=int,required=True);ap.add_argument('--leaf-denominator',type=int,default=10**9);ap.add_argument('--time-limit',type=float,default=180);ap.add_argument('--node-limit',type=int,default=10000);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 g=parse_dimacs(a.graph);S=enumerate_stable_sets(g,max(a.top_size,a.residual_set_size));best,packs=enumerate_packings(S[a.top_size]);pack=packs[a.packing_number-1];top=[S[a.top_size][i] for i in pack];removed={v for C in top for v in C};res=sorted(set(range(1,g['n']+1))-removed);ridx={v:i for i,v in enumerate(res)}
 D=a.dual_denominator;Q=a.leaf_denominator;w=read_dual(a.dual,res);total=sum(w.values());B=total//D;slack=total%B if False else total-B*D
 allc=[C for C in S[a.residual_set_size] if set(C).isdisjoint(removed)];exall=[sum(w[v] for v in C)-D for C in allc]
 if not allc or min(exall)<0:raise ValueError('old dual invalid')
 keep=[i for i,e in enumerate(exall) if e<=slack];cols=[allc[i] for i in keep];ex=[int(exall[i]) for i in keep];n=len(cols);inc=[0]*(g['n']+1)
 for j,C in enumerate(cols):
  for v in C:inc[v]|=1<<j
 full=(1<<n)-1;disj=[]
 for C in cols:
  z=0
  for v in C:z|=inc[v]
  disj.append(full&~z)
 rr=[];cc=[]
 for j,C in enumerate(cols):
  for v in C:rr.append(ridx[v]);cc.append(j)
 Aall=csc_matrix((np.ones(len(rr)),(rr,cc)),shape=(len(res),n));records=[];stats={'branches':0,'dual_leaves':0,'count_leaves':0,'budget_leaves':0};calls=0;depthmax=0;t0=time.perf_counter()
 def emit(x):records.append(x);return len(records)-1
 def lp(ii,R):
  A=Aall[:,ii];budget=np.array([ex[i]/D for i in ii]).reshape(1,-1);return linprog(-np.ones(len(ii)),A_ub=vstack([A,csc_matrix(budget)]),b_ub=np.r_[np.ones(len(res)),R/D],bounds=(0,None),method='highs')
 def leaf(r,ii,R,selected,need):
  m=-np.asarray(r.ineqlin.marginals);y=np.maximum(m[:len(res)],0);mu=max(float(m[-1]),0);W=[int(math.ceil(float(z)*Q-1e-10)) for z in y];M=int(math.ceil(mu*Q-1e-10));rep=0
  for j in ii:
   lhs=D*sum(W[ridx[v]] for v in cols[j])+ex[j]*M
   if lhs<D*Q:
    add=(D*Q-lhs+D-1)//D;W[ridx[cols[j][0]]]+=add;rep+=add
  num=D*sum(W)+R*M
  if num>=need*D*Q:return None
  return {'kind':'dual','selected':selected,'remaining_target':need,'remaining_budget':R,'denominator':Q,'budget_multiplier':M,'vertex_weights':[[v,W[ridx[v]]] for v in res if W[ridx[v]]],'numerator':num,'repairs':rep}
 def dfs(active,selected,spent,depth):
  nonlocal calls,depthmax
  calls+=1;depthmax=max(depthmax,depth)
  if (a.node_limit > 0 and calls>a.node_limit) or (a.time_limit > 0 and time.perf_counter()-t0>a.time_limit):raise TimeoutError('generation cap')
  if spent>slack:stats['budget_leaves']+=1;return emit({'kind':'budget','selected':selected,'spent':spent})
  R=slack-spent;need=B-selected
  if need<=0:raise RuntimeError('forbidden packing found')
  filtered=0
  for j in bits(active):
   if ex[j]<=R:filtered|=1<<j
  active=filtered
  if active.bit_count()<need:stats['count_leaves']+=1;return emit({'kind':'count','selected':selected,'remaining_target':need,'remaining_budget':R,'active_count':active.bit_count()})
  ii=list(bits(active));r=lp(ii,R)
  if r.status!=0:raise RuntimeError(r.message)
  L=leaf(r,ii,R,selected,need)
  if L is not None:stats['dual_leaves']+=1;return emit(L)
  frac=[(abs(float(x)-.5),k) for k,x in enumerate(r.x) if 1e-7<float(x)<1-1e-7];k=min(frac)[1] if frac else next(k for k,x in enumerate(r.x) if x>1e-7);j=ii[k]
  one=dfs(active&disj[j],selected+1,spent+ex[j],depth+1);zero=dfs(active&~(1<<j),selected,spent,depth+1);stats['branches']+=1;return emit({'kind':'branch','column':j,'one':one,'zero':zero})
 root=dfs(full,0,0,0);elapsed=time.perf_counter()-t0
 d={'schema':'residual_kset_lpbb_v2','graph_raw_sha256':g['raw_sha256'],'graph_canonical_sha256':g['canonical_sha256'],'vertices':g['n'],'top_set_size':a.top_size,'top_stable_family_sha256':stable_tuple_hash(S[a.top_size]),'maximum_top_packing_size':best,'maximum_top_packing_count':len(packs),'packing_number':a.packing_number,'packing_indices':list(pack),'packing_sets':[list(C) for C in top],'residual_vertices':res,'residual_set_size':a.residual_set_size,'global_residual_set_family_sha256':stable_tuple_hash(S[a.residual_set_size]),'residual_set_family_sha256':stable_tuple_hash(allc),'old_dual_sha256':sha(a.dual),'old_dual_denominator':D,'old_dual_total':total,'old_bound':B,'slack_budget':slack,'allowed_column_count':n,'allowed_columns_sha256':stable_tuple_hash(cols),'claimed_new_bound':B-1,'leaf_denominator':Q,'root':root,'records':records,'statistics':stats|{'records':len(records),'calls':calls,'max_depth':depthmax,'generation_seconds':elapsed},'generator_note':'Floating LP selected branches; integer leaves are replayable exactly.'}
 a.out.parent.mkdir(parents=True,exist_ok=True)
 with a.out.open('wb') as f:
  with gzip.GzipFile(filename='',mode='wb',fileobj=f,mtime=0) as z:z.write((json.dumps(d,sort_keys=True,separators=(',',':'))+'\n').encode())
 print(json.dumps({'packing':a.packing_number,'old_bound':B,'new_bound':B-1,'allowed':n}|d['statistics'],indent=2))
if __name__=='__main__':main()
