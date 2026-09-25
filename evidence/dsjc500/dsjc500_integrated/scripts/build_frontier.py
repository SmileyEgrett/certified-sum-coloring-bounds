#!/usr/bin/env python3
"""Construct and verify the splitting-maximal packing/profile frontier."""
from __future__ import annotations
import argparse,csv,json,hashlib
from collections import deque
from pathlib import Path

SPLITS={
 'pair_to_1_1':(2,-1,0,0),
 'triple_to_2_1':(1,1,-1,0),
 'triple_to_1_1_1':(3,0,-1,0),
 'quad_to_3_1':(1,0,1,-1),
 'quad_to_2_2':(0,2,0,-1),
 'quad_to_2_1_1':(2,1,0,-1),
 'quad_to_1_1_1_1':(4,0,0,-1),
}
def T(x):return x*(x+1)//2
def objective(h):
 h1,h2,h3,h4,h5=h;q=sum(h)
 g=(q,q-h1,q-h1-h2,h4+h5,h5)
 return sum(T(x) for x in g)
def enumerate_profiles(limit=29847):
 # The initial certificate stage establishes that every
 # unresolved threshold coloring has strength 124..132 and h5=15.
 # Enumerate that exact certified domain directly.
 out=[];h5=15
 for q in range(124,133):
  for h4 in range(102):
   for h3 in range((425-4*h4)//3+1):
    h2=500-q-2*h3-3*h4-4*h5
    h1=2*q-500+h3+2*h4+3*h5
    if min(h1,h2)<0:continue
    h=(h1,h2,h3,h4,h5);v=objective(h)
    if v<=limit:out.append((v,q,h))
 return sorted(out)
def admissible(pi,rows):
 bound=100 if pi in (2,4) else 101
 eliminated={(0,0,7,101)}
 if pi==1:eliminated.add((1,1,6,101))
 if pi==3:eliminated.update({(1,1,6,101),(0,3,5,101)})
 return [r for r in rows if r[2][4]==15 and r[2][3]<=bound and r[2][:4] not in eliminated]
def step(h,delta):return tuple(h[i]+delta[i] for i in range(4))
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out-dir',type=Path,required=True);a=ap.parse_args();a.out_dir.mkdir(parents=True,exist_ok=True)
 rows=enumerate_profiles(); all_cells=[];frontier=[];paths=[]
 per={}
 for pi in range(1,9):
  fam=admissible(pi,rows); by={r[2][:4]:r for r in fam}; keys=set(by)
  succ={h:[] for h in keys}
  for h in sorted(keys):
   for name,d in SPLITS.items():
    z=step(h,d)
    if min(z)>=0 and z in keys:succ[h].append((name,z))
  maxima=sorted(h for h in keys if not succ[h])
  expected=20 if pi in (2,4) else 23
  if len(maxima)!=expected:raise RuntimeError(f'P{pi}: frontier {len(maxima)} != {expected}')
  maxset=set(maxima)
  # Reverse BFS gives deterministic shortest coverage path to a maximal profile.
  rev={h:[] for h in keys}
  for h,edges in succ.items():
   for name,z in edges:rev[z].append((h,name))
  dist={h:0 for h in maxima};choice={};dq=deque(maxima)
  while dq:
   z=dq.popleft()
   for h,name in sorted(rev[z]):
    cand=(dist[z]+1,name,z)
    if h not in dist or cand<(dist[h],choice[h][0],choice[h][1]):
     dist[h]=dist[z]+1;choice[h]=(name,z);dq.append(h)
  if set(dist)!=keys:raise RuntimeError(f'P{pi}: uncovered profiles')
  per[str(pi)]={'cells':len(keys),'frontier':len(maxima),'h4_bound':100 if pi in (2,4) else 101}
  for h in sorted(keys):
   r=by[h]; all_cells.append({'packing':pi,'objective':r[0],'strength':r[1],'h1':h[0],'h2':h[1],'h3':h[2],'h4':h[3],'h5':15})
   chain=[list(h)];ops=[];cur=h
   while cur not in maxset:
    name,nxt=choice[cur];ops.append(name);chain.append(list(nxt));cur=nxt
   paths.append({'packing':pi,'source':list(h),'operations':ops,'profiles':chain,'frontier_target':list(cur)})
  for h in maxima:
   r=by[h];frontier.append({'packing':pi,'objective':r[0],'strength':r[1],'h1':h[0],'h2':h[1],'h3':h[2],'h4':h[3],'h5':15})
 # Independent path replay.
 cellsets={pi:{(r['h1'],r['h2'],r['h3'],r['h4']) for r in all_cells if r['packing']==pi} for pi in range(1,9)}
 frontsets={pi:{(r['h1'],r['h2'],r['h3'],r['h4']) for r in frontier if r['packing']==pi} for pi in range(1,9)}
 for p in paths:
  cur=tuple(p['source'])
  if p['profiles'][0]!=list(cur) or len(p['profiles'])!=len(p['operations'])+1:raise RuntimeError('path shape')
  for name,zlist in zip(p['operations'],p['profiles'][1:]):
   z=step(cur,SPLITS[name])
   if list(z)!=zlist or z not in cellsets[p['packing']]:raise RuntimeError('invalid path step')
   cur=z
  if cur!=tuple(p['frontier_target']) or cur not in frontsets[p['packing']]:raise RuntimeError('bad frontier endpoint')
 if len(all_cells)!=1195 or len(frontier)!=178 or len(paths)!=1195:raise RuntimeError('global census mismatch')
 with (a.out_dir/'frontier_cells.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['packing','objective','strength','h1','h2','h3','h4','h5']);w.writeheader();w.writerows(frontier)
 with (a.out_dir/'admissible_cells_before_delta.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['packing','objective','strength','h1','h2','h3','h4','h5']);w.writeheader();w.writerows(all_cells)
 (a.out_dir/'coverage_paths.json').write_text(json.dumps(paths,indent=2,sort_keys=True)+'\n')
 payload={'schema':'dsjc5009_splitting_frontier_v1','objective_limit':29847,'input_cells':len(all_cells),'frontier_cells':len(frontier),'coverage_paths':len(paths),'per_packing':per,'split_operations':{k:list(v) for k,v in SPLITS.items()},'frontier_csv':'frontier_cells.csv','admissible_csv':'admissible_cells_before_delta.csv','coverage_file':'coverage_paths.json'}
 (a.out_dir/'frontier_summary.json').write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
 print(json.dumps(payload,indent=2,sort_keys=True))
if __name__=='__main__':main()
