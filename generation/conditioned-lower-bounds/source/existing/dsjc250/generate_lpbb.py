#!/usr/bin/env python3
from pathlib import Path
import sys,time,math,json,gzip,hashlib,os
import numpy as np
from numerical import linprog
from scipy.sparse import csc_matrix, vstack

GRAPH=Path(os.environ['DSJC2509_GRAPH'])
print('GRAPH_SHA256',hashlib.sha256(GRAPH.read_bytes()).hexdigest(),flush=True)
D=10**9
TOL=1e-7

def parse_graph(path):
 n=0; edges=set()
 for ln,raw in enumerate(path.read_text().splitlines(),1):
  p=raw.split()
  if not p or p[0]=='c': continue
  if p[0]=='p':
   if len(p)!=4 or p[1] not in ('edge','edges'): raise ValueError(('header',ln))
   n=int(p[2]); declared=int(p[3])
  elif p[0]=='e':
   a,b=map(int,p[1:]);
   if a==b: raise ValueError(('loop',ln))
   edges.add((a,b) if a<b else (b,a))
  else: raise ValueError(('record',ln,p[0]))
 if len(edges)!=declared: raise ValueError(('edgecount',declared,len(edges)))
 return n,edges

def enumerate_stable(n,edges):
 adj=[0]*(n+1); full=sum(1<<v for v in range(1,n+1))
 for a,b in edges: adj[a]|=1<<b; adj[b]|=1<<a
 comp=[0]*(n+1)
 for v in range(1,n+1):comp[v]=full&~adj[v]&~(1<<v)
 def bits(m):
  while m:
   b=m&-m;yield b.bit_length()-1;m^=b
 S={2:[],3:[],4:[],5:[]}
 for a in range(1,n+1):
  ca=comp[a]&~((1<<(a+1))-1)
  for b in bits(ca):
   S[2].append((a,b));cb=ca&comp[b]&~((1<<(b+1))-1)
   for c in bits(cb):
    S[3].append((a,b,c));cc=cb&comp[c]&~((1<<(c+1))-1)
    for d in bits(cc):
     S[4].append((a,b,c,d));cd=cc&comp[d]&~((1<<(d+1))-1)
     for e in bits(cd):S[5].append((a,b,c,d,e))
 return S

def build_model(name):
 n,e=parse_graph(GRAPH); S=enumerate_stable(n,e); B=n+1
 specs={
  'quad_x2':([S[5][1]],{},{4:1},38),
  'env_x2':([S[5][1]],{4:37},{4:B,3:1},37*B+30),
  'env_x3':([S[5][2]],{4:37},{4:B,3:1},37*B+29),
  'env_x1x2':([S[5][0],S[5][1]],{4:34},{4:B,3:1},34*B+32),
  'pair_H1C':([S[5][1]],{4:37,3:29},{4:B*B,3:B,2:1},37*B*B+29*B+5),
  'pair_H2F':([S[5][0],S[5][1]],{4:34,3:31},{4:B*B,3:B,2:1},34*B*B+31*B+5),
 }
 tops,caps,score_by_size,target=specs[name]
 used=set().union(*map(set,tops)); verts=[v for v in range(1,n+1) if v not in used]; vi={v:i for i,v in enumerate(verts)}
 cols=[]
 for s in sorted(score_by_size,reverse=True):
  for C in S[s]:
   if not used.intersection(C):
    mask=sum(1<<v for v in C)
    cols.append({'set':C,'mask':mask,'size':s,'score':score_by_size[s]})
 # deterministic ids in size descending then lex
 return {'name':name,'n':n,'tops':tops,'caps':caps,'score_by_size':score_by_size,'target':target,'verts':verts,'vi':vi,'cols':cols,'B':B,'counts':{k:len(v) for k,v in S.items()},'five':S[5]}

class Prover:
 def __init__(self,model,node_limit=100000,time_limit=300):
  self.m=model; self.nodes=0; self.leaves=0; self.branches=0; self.start=time.time(); self.node_limit=node_limit; self.time_limit=time_limit; self.proof=[]; self.lp_time=0
  self.incident=[[] for _ in self.m['verts']]
  for j,col in enumerate(self.m['cols']):
   for v in col['set']: self.incident[self.m['vi'][v]].append(j)
 def stop(self):
  if self.node_limit > 0 and self.nodes>=self.node_limit: raise RuntimeError('node limit')
  if self.time_limit > 0 and time.time()-self.start>=self.time_limit: raise RuntimeError('time limit')
 def solve_lp(self,active,caps):
  t=time.time(); m=len(self.m['verts']); cap_sizes=sorted(caps,reverse=True); rows=m+len(cap_sizes); pos={s:m+i for i,s in enumerate(cap_sizes)}
  rr=[];cc=[];dd=[]; c=np.empty(len(active),float)
  for k,j in enumerate(active):
   col=self.m['cols'][j]; c[k]=-float(col['score'])
   for v in col['set']: rr.append(self.m['vi'][v]);cc.append(k);dd.append(1.0)
   if col['size'] in pos: rr.append(pos[col['size']]);cc.append(k);dd.append(1.0)
  A=csc_matrix((dd,(rr,cc)),shape=(rows,len(active)))
  b=np.r_[np.ones(m),[caps[s] for s in cap_sizes]]
  res=linprog(c,A_ub=A,b_ub=b,bounds=(0,None),method='highs-ipm',options={'presolve':False})
  self.lp_time+=time.time()-t
  if not res.success: raise RuntimeError('unexpected LP failure '+res.message)
  dual=-np.asarray(res.ineqlin.marginals)
  return -float(res.fun),np.asarray(res.x),dual,cap_sizes
 def exact_dual(self,active,caps,selected_score,dual,cap_sizes):
  m=len(self.m['verts']); w=[max(0,math.ceil(float(dual[i])*D-1e-5)) for i in range(m)]
  lam={s:max(0,math.ceil(float(dual[m+k])*D-1e-5)) for k,s in enumerate(cap_sizes)}
  # Repair any exact dual deficits by charging a vertex in the deficient column.
  repairs=0
  for j in active:
   col=self.m['cols'][j]
   lhs=sum(w[self.m['vi'][v]] for v in col['set'])+lam.get(col['size'],0)
   req=col['score']*D
   if lhs<req:
    deficit=req-lhs; w[self.m['vi'][col['set'][0]]]+=deficit;repairs+=deficit
  num=sum(w)+sum(caps[s]*lam[s] for s in cap_sizes)
  if selected_score*D+num>=self.m['target']*D:
   return None
  sw=[[self.m['verts'][i],x] for i,x in enumerate(w) if x]
  sl=[[s,lam[s]] for s in cap_sizes if lam[s]]
  return {'kind':'leaf','denominator':D,'vertex_weights':sw,'cap_weights':sl,'numerator':num,'selected_score':selected_score,'repairs':repairs}
 def choose_branch(self,active,x):
  frac=[]
  for k,j in enumerate(active):
   val=x[k]
   if TOL<val<1-TOL:
    col=self.m['cols'][j]
    # prioritize larger score digit, then closest to 0.5, then larger x
    frac.append((col['score'], -abs(val-0.5), val, -j, j))
  if not frac:
   return None
  return max(frac)[-1]
 def rec(self,active,caps,selected_score,depth=0):
  self.stop(); self.nodes+=1
  if self.nodes % 250 == 0:
   print(json.dumps({'progress_nodes':self.nodes,'leaves':self.leaves,'branches':self.branches,'depth':depth,'elapsed':time.time()-self.start,'lp_time':self.lp_time}), flush=True)
  ub,x,dual,cap_sizes=self.solve_lp(active,caps)
  leaf=self.exact_dual(active,caps,selected_score,dual,cap_sizes)
  if leaf is not None:
   self.leaves+=1; self.proof.append(leaf); return len(self.proof)-1
  j=self.choose_branch(active,x)
  if j is None:
   # exact-ish LP solution should imply target counterexample if not pruned
   vals=[(active[k],x[k]) for k in range(len(active)) if x[k]>0.5]
   score=selected_score+sum(self.m['cols'][q]['score'] for q,v in vals)
   raise RuntimeError(f'integral target candidate score {score} >= {self.m["target"]}: {vals[:20]}')
  self.branches+=1
  # 0 branch
  a0=tuple(q for q in active if q!=j)
  left=self.rec(a0,dict(caps),selected_score,depth+1)
  # 1 branch
  col=self.m['cols'][j]; s=col['size']
  if s in caps and caps[s]<=0:
   raise RuntimeError('branched unavailable cap')
  caps1=dict(caps)
  if s in caps1: caps1[s]-=1
  a1=tuple(q for q in active if q!=j and not (self.m['cols'][q]['mask']&col['mask']) and not (self.m['cols'][q]['size'] in caps1 and caps1[self.m['cols'][q]['size']]==0))
  right=self.rec(a1,caps1,selected_score+col['score'],depth+1)
  node={'kind':'branch','var':j,'zero':left,'one':right}
  self.proof.append(node); return len(self.proof)-1
 def run(self):
  active=tuple(range(len(self.m['cols'])))
  root=self.rec(active,dict(self.m['caps']),0)
  return root

def main():
 name=sys.argv[1]; out=Path(sys.argv[2]); node_limit=int(sys.argv[3]) if len(sys.argv)>3 else 100000; time_limit=float(sys.argv[4]) if len(sys.argv)>4 else 300
 m=build_model(name); p=Prover(m,node_limit,time_limit)
 try:
  root=p.run(); status='PROVED'
 except Exception as e:
  root=None; status='INCOMPLETE'; err=repr(e)
 data={'schema':'dsjc2509_lpbb_proof_v1','status':status,'model':{k:m[k] for k in ['name','n','tops','caps','score_by_size','target','B','counts','five']},'columns':[list(c['set']) for c in m['cols']],'root':root,'proof':p.proof,'statistics':{'nodes':p.nodes,'leaves':p.leaves,'branches':p.branches,'elapsed':time.time()-p.start,'lp_time':p.lp_time}}
 if status!='PROVED':data['error']=err
 with gzip.open(out,'wt',encoding='utf-8') as f:json.dump(data,f,separators=(',',':'))
 print(json.dumps({'status':status,'root':root,**data['statistics'],'proof_records':len(p.proof),'out':str(out),'error':data.get('error')},indent=2),flush=True)
 return 0 if status=='PROVED' else 2
if __name__=='__main__':raise SystemExit(main())
