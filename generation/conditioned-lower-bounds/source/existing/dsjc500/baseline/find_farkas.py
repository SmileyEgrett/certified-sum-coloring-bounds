#!/usr/bin/env python3
from pathlib import Path
import argparse,json,time,math
import numpy as np
from numerical import linprog
from scipy.sparse import csc_matrix,hstack,vstack
from common import *

def build(graph,packing):
 g=parse_dimacs(graph);S=enumerate_stable_sets(g,6);_,packs=enumerate_packings(S[5]);removed=set().union(*(set(S[5][i]) for i in packs[packing-1]));rem=sorted(set(range(1,501))-removed);q=[C for C in S[4] if set(C).isdisjoint(removed)];t=[C for C in S[3] if set(C).isdisjoint(removed)];cols=q+t;nq=len(q)
 rr=[];cc=[];dd=[];b=[]
 for i,v in enumerate(rem):
  for j,C in enumerate(cols):
   if v in C:rr.append(i);cc.append(j);dd.append(1.)
  b.append(1.)
 row=len(rem)
 for js,need in [(range(nq),101),(range(nq,len(cols)),7)]:rr.extend([row]*len(js));cc.extend(js);dd.extend([1.]*len(js));b.append(need);row+=1
 A=csc_matrix((dd,(rr,cc)),shape=(row,len(cols)));return g,S,packs,rem,q,t,A,np.array(b,dtype=float)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--graph',type=Path,required=True);ap.add_argument('--packing',type=int,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();g,S,packs,rem,q,t,A,b=build(a.graph,a.packing);r=A.shape[0]
 # y = p-n. Need A^T y >= 0 => -A^T p + A^T n <=0. b^T y <= -1.
 Aub=vstack([hstack([-A.T,A.T]),csc_matrix(np.r_ [b,-b].reshape(1,-1))],format='csc');bub=np.r_[np.zeros(A.shape[1]),-1.0]
 c=np.ones(2*r);st=time.perf_counter();res=linprog(c,A_ub=Aub,b_ub=bub,bounds=(0,None),method='highs')
 out={'packing':a.packing,'status':int(res.status),'message':res.message,'seconds':time.perf_counter()-st}
 if res.x is not None:
  y=res.x[:r]-res.x[r:];aty=A.T@y;bt=float(b@y)
  vals=sorted(set(round(float(x),12) for x in y if abs(x)>1e-9))
  out.update({'bt':bt,'min_aty':float(aty.min()),'nonzero':int(sum(abs(y)>1e-9)),'distinct_values':vals[:100],'max_abs':float(max(abs(y)))})
  # try denominator grids
  cert=None
  for D in [10,100,1000,10000,100000,1000000,10**7,10**8,10**9,10**10,10**12]:
   z=[int(round(float(val)*D)) for val in y]
   # Monotone exact repair: every column contains vertex rows with b_i=1.
   repairs=0
   for j in range(A.shape[1]):
    inds=A[:,j].indices
    ss=sum(z[i] for i in inds)
    if ss<0:
     # repair on the first vertex row, never on a quota row
     i=next(i for i in inds if i < len(rem))
     z[i] += -ss; repairs += -ss
   mn=min(sum(z[i] for i in A[:,j].indices) for j in range(A.shape[1]))
   btz=sum(z[i]*int(b[i]) for i in range(r))
   if mn>=0 and btz<0:
    cert={'denominator':D,'weights':z,'bt':btz,'min_column':mn,'repairs':repairs};break
  if cert:out['certificate']=cert
 a.out.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='certificate'}|{'cert_found':'certificate'in out,'cert_bt':out.get('certificate',{}).get('bt')},indent=2))
if __name__=='__main__':main()
