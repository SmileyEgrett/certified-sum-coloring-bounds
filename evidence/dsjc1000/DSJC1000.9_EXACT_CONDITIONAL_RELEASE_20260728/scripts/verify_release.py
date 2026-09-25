#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,itertools,json,math,sys,time
from pathlib import Path
from typing import NamedTuple
class Bad(Exception):pass
class PackingContract(NamedTuple):
 scenario:str
 fixed_size6_classes:tuple[tuple[int,...],...]
 residual_vertices:tuple[int,...]
 denominator:int
 strict_upper_threshold:int
 integer_cap:int
def req(x,msg):
 if not x:raise Bad(msg)
def sha(b):return hashlib.sha256(b).hexdigest()
def loadj(p):
 def dup(pairs):
  d={}
  for k,v in pairs:
   if k in d:raise Bad(f'{p}: duplicate JSON key {k}')
   d[k]=v
  return d
 def nofloat(x):raise Bad(f'{p}: floats forbidden')
 return json.loads(p.read_text(),object_pairs_hook=dup,parse_float=nofloat)
def parse_graph(p):
 raw=p.read_bytes();n=m=None;edges=set();seen=False
 for ln,b in enumerate(raw.splitlines(),1):
  f=b.decode('ascii').split()
  if not f or f[0]=='c':continue
  if f[0]=='p':req(not seen and len(f)==4 and f[1] in ('edge','edges','col'),f'bad header {ln}');n=int(f[2]);m=int(f[3]);seen=True
  elif f[0]=='e':
   req(seen and len(f)==3,f'bad edge {ln}');u,v=map(int,f[1:]);req(1<=u<=n and 1<=v<=n and u!=v,f'bad endpoints {ln}');u,v=sorted((u,v));req((u,v) not in edges,f'duplicate edge {ln}');edges.add((u,v))
  else:raise Bad(f'unknown DIMACS record {ln}')
 req(seen and len(edges)==m,'edge count mismatch');adj=[0]*(n+1);full=sum(1<<v for v in range(1,n+1))
 for u,v in edges:adj[u]|=1<<v;adj[v]|=1<<u
 comp=[0]*(n+1)
 for v in range(1,n+1):comp[v]=full&~adj[v]&~(1<<v)
 canon=('independent_graph_v1\n'+f'vertices {n}\n'+''.join(f'{u} {v}\n' for u,v in sorted(edges))).encode()
 return n,edges,adj,comp,sha(raw),sha(canon)
def enumerate_stable(n,comp,maxsize=7):
 fam={s:[] for s in range(1,maxsize+1)};full=sum(1<<v for v in range(1,n+1))
 def rec(pre,cand):
  rem=cand
  while rem:
   bit=rem&-rem;v=bit.bit_length()-1;rem^=bit;ch=pre+(v,);fam[len(ch)].append(ch)
   if len(ch)<maxsize:rec(ch,rem&comp[v])
 rec((),full);return fam
def gamma(B,D,k):
 q=B-k*D
 if q<=D:return 0
 r=(q-1)//D
 return r*B-D*(r*k+r*(r+1)//2)
def ceildiv(a,b):return -(-a//b)
def verify_coloring(p,n,edges):
 col={}
 for ln,line in enumerate(p.read_text().splitlines(),1):
  f=line.split()
  if len(f)>=2 and f[0].isdigit() and f[1].isdigit():v,c=map(int,f[:2]);req(v not in col,f'duplicate coloring vertex {v}');req(v>=1 and c>=1,f'bad coloring record {ln}');col[v]=c
 req(set(col)==set(range(1,n+1)),'incomplete coloring');req(all(col[u]!=col[v] for u,v in edges),'color conflict')
 sizes=sorted(__import__('collections').Counter(col.values()).values(),reverse=True);obj=sum((i+1)*s for i,s in enumerate(sizes));direct=sum(col.values());h=[sizes.count(s) for s in range(1,max(sizes)+1)];return obj,direct,h,len(sizes)
def graph_binding(c,raw,canon,counts):
 g=c['graph'];req(g['raw_sha256']==raw and g['canonical_sha256']==canon,'certificate graph hash mismatch');req(g['vertices']==1000 and g['unique_edges']==449449 and g['stable_counts']==counts,'certificate graph dimensions mismatch')
def verify_master(c,fam,raw,canon,counts):
 req(c['schema']=='dsjc1000_full_master_dual_certificate_v1','master schema');graph_binding(c,raw,canon,counts);D=c['denominator'];W=c['vertex_weights_num'];B=c['threshold_slopes_num'];req(type(D) is int and D>0 and len(W)==1000 and len(B)==6,'master dimensions');req(all(type(x)is int for x in W+B),'master integer data')
 mins=[]
 for s in range(1,7):
  cap=sum(B[:s]);mn=min(cap-sum(W[v-1] for v in S) for S in fam[s]);req(mn>=0,f'master stable inequality size {s}');mins.append(mn)
 lb=sum(W)-sum(gamma(x,D,0) for x in B);req(lb==c['lower_bound_num'] and D==c['lower_bound_den'],'master lower bound arithmetic');req(ceildiv(lb,D)==c['integer_lower_bound'],'master ceiling');req(mins==c['minimum_slack_num_by_size'],'master slack record');return lb,D
def verify_packing(c,fam,tops,raw,canon,counts):
 req(c['schema']=='dsjc1000_size5_packing_dual_certificate_v1','packing schema');graph_binding(c,raw,canon,counts);fixed=tuple(map(tuple,c['fixed_size6_classes']));req(c['scenario']=='111' and fixed==tops,'packing scenario');D=c['denominator'];threshold=c['strict_upper_threshold'];integer_cap=c['integer_packing_cap'];req(type(D)is int and D>0 and type(threshold)is int and threshold>0 and type(integer_cap)is int and integer_cap>=0,'packing scale/cap types');W=c['residual_vertex_cover_weights_num'];req(len(W)==1000 and all(type(x)is int and x>=0 for x in W),'packing weights');used=set(itertools.chain.from_iterable(fixed));residual=tuple(v for v in range(1,1001) if v not in used);req(all(W[v-1]==0 for v in used),'top packing weights nonzero');sur=[]
 for S in fam[5]:
  if used.isdisjoint(S):sur.append(sum(W[v-1] for v in S)-D)
 mn=min(sur);req(mn>=0,'packing dual column violation');req(mn==c['minimum_column_surplus_num'],'packing surplus record');total=sum(W);req(total==c['dual_objective_num'] and c['dual_objective_den']==D,'packing objective');req(total<threshold*D,'packing strict threshold');req(integer_cap==threshold-1,'packing threshold/cap relation');return PackingContract(c['scenario'],fixed,residual,D,threshold,integer_cap)
def verify_cond(c,fam,tops,raw,canon,counts,packing):
 req(c['schema']=='dsjc1000_conditional_dual_certificate_v1','conditional schema');graph_binding(c,raw,canon,counts);s=c['scenario'];req(type(s)is str and len(s)==3 and set(s)<={'0','1'},'scenario bits');selected=tuple(tops[i] for i,b in enumerate(s) if b=='1');fixed=tuple(map(tuple,c['fixed_size6_classes']));req(fixed==selected,'fixed top mismatch');req(tuple(map(tuple,c['forbidden_unselected_size6_classes']))==tuple(tops[i] for i,b in enumerate(s) if b=='0'),'forbidden top mismatch');k=sum(b=='1' for b in s);req(c['k']==k,'k mismatch');D=c['denominator'];W=c['residual_vertex_weights_num'];B=c['threshold_slopes_num'];req(type(D)is int and D>0 and len(W)==1000 and len(B)==5 and all(type(x)is int for x in W+B),'conditional dimensions');used=set(itertools.chain.from_iterable(fixed));residual=tuple(v for v in range(1,1001) if v not in used);req(all(W[v-1]==0 for v in used),'selected-top weight nonzero');qcap=c['q5_cap'];delta=c['q5_cap_multiplier_num'];inactive=qcap is None and type(delta)is int and delta==0;active=type(qcap)is int and type(delta)is int and delta>0 and qcap==packing.integer_cap and s==packing.scenario and fixed==packing.fixed_size6_classes and residual==packing.residual_vertices and D==packing.denominator;req(inactive or active,'conditional q5 cap contract');mins=[]
 for size in range(1,6):
  cap=sum(B[:size])+(delta if size==5 else 0);eligible=[S for S in fam[size] if used.isdisjoint(S)];mn=min(cap-sum(W[v-1] for v in S) for S in eligible);req(mn>=0,f'conditional {s} stable inequality size {size}');mins.append(mn)
 const=6*k*(k+1)//2*D;req(c['constant_num']==const,'conditional constant');lb=const+sum(W)-sum(gamma(x,D,k) for x in B)-delta*(qcap or 0);req(lb==c['lower_bound_num'] and c['lower_bound_den']==D,'conditional lower bound arithmetic');req(ceildiv(lb,D)==c['integer_lower_bound'],'conditional ceiling');req(mins==c['minimum_slack_num_by_size'],'conditional slack record');return s,lb,D
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--release-root',type=Path,required=True);ap.add_argument('--json-out',type=Path);a=ap.parse_args();R=a.release_root;t=time.time();n,edges,adj,comp,raw,canon=parse_graph(R/'instance/DSJC1000.9.col');req(n==1000 and len(edges)==449449,'graph identity');fam=enumerate_stable(n,comp,7);counts=[len(fam[s]) for s in range(1,7)];req(counts==[1000,50051,167104,41659,869,3] and len(fam[7])==0,'stable census/alpha');tops=tuple(fam[6]);req(all(set(tops[i]).isdisjoint(tops[j]) for i in range(3) for j in range(i)),'top sets overlap');obj,direct,h,classes=verify_coloring(R/'witness/DSJC1000.9_best.coloring',n,edges);req((obj,direct,h,classes)==(103256,103256,[2,4,17,74,125,3],225),'coloring profile')
 master=loadj(R/'certificates/full_master_dual.json');mlb,D=verify_master(master,fam,raw,canon,counts);packing=loadj(R/'certificates/size5_packing_cap_111.json');packing_contract=verify_packing(packing,fam,tops,raw,canon,counts);conds={}
 for s in ('000','001','010','011','100','101','110','111'):
  p=R/'certificates'/('conditional_111_q5cap134.json' if s=='111' and (R/'certificates/conditional_111_q5cap134.json').exists() else f'conditional_{s}.json');c=loadj(p);ss,lb,dd=verify_cond(c,fam,tops,raw,canon,counts,packing_contract);req(ss==s and dd==D,'conditional identity');conds[s]=lb
 req(set(conds)=={f'{i:03b}' for i in range(8)},'scenario exhaustion');glb=min(conds.values());final=loadj(R/'results/final_bound.json');req(final['denominator']==D and final['scenario_lower_bound_num']==conds,'final scenario record');req(final['scenario_integer_lower_bound']=={s:ceildiv(v,D) for s,v in conds.items()},'final scenario ceilings');req(final['global_conditional_lower_bound_num']==glb and final['global_conditional_lower_bound_den']==D,'final bound record');integer=ceildiv(glb,D);req(final['baseline_lower_bound_num']==mlb and final['baseline_lower_bound_den']==D and final['baseline_integer_lower_bound']==ceildiv(mlb,D),'baseline record');req(final['global_conditional_integer_lower_bound']==integer and final['upper_bound']==103256 and final['certified_interval']==[integer,103256],'final interval record');req(integer>ceildiv(mlb,D),'no strict improvement')
 out={'schema':'dsjc1000_release_verification_v1','status':'PASS','graph':{'raw_sha256':raw,'canonical_sha256':canon,'vertices':n,'unique_edges':len(edges)},'stable_counts':counts,'alpha':6,'coloring_upper_bound':obj,'full_master_exact_lower_bound_num':mlb,'denominator':D,'full_master_integer_lower_bound':ceildiv(mlb,D),'conditional_scenario_lower_bound_num':conds,'final_integer_lower_bound':integer,'final_interval':[integer,obj],'elapsed_seconds':time.time()-t}
 text=json.dumps(out,indent=2)+'\n';print(text,end='');
 if a.json_out:a.json_out.write_text(text)
if __name__=='__main__':
 try:main()
 except (Bad,AssertionError,KeyError,TypeError,ValueError) as e:print(f'VERIFICATION_FAILED: {e}',file=sys.stderr);raise SystemExit(1)
