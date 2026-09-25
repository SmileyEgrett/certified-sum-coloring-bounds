#!/usr/bin/env python3
"""Reconstruct the baseline and post-delta DSJC500.9 cell census exactly."""
from __future__ import annotations
import argparse,csv,json
from collections import Counter
from pathlib import Path

def T(x): return x*(x+1)//2
def objective(h):
 h1,h2,h3,h4,h5=h; g1=sum(h);g2=h2+h3+h4+h5;g3=h3+h4+h5;g4=h4+h5;g5=h5
 return sum(map(T,(g1,g2,g3,g4,g5)))
def profiles(limit=29847):
 # Initial-stage replay establishes strength 124..132 and h5=15 for
 # every unresolved threshold cell. Reconstruct that domain directly.
 out=[];h5=15
 for q in range(124,133):
  for h4 in range(102):
   for h3 in range((425-4*h4)//3+1):
    h2=500-q-2*h3-3*h4-4*h5; h1=2*q-500+h3+2*h4+3*h5
    if min(h1,h2)<0: continue
    h=(h1,h2,h3,h4,h5); v=objective(h)
    if v<=limit: out.append((v,q,h))
 return sorted(out)
BASELINE_EXTRA={(1,(1,1,6,101,15)),(3,(1,1,6,101,15)),(3,(0,3,5,101,15))}
def keyrow(pi,v,q,h,status,reason=''):
 return {'packing':pi,'objective':v,'strength':q,'h1':h[0],'h2':h[1],'h3':h[2],'h4':h[3],'h5':h[4],'status':status,'reason':reason}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--registry',type=Path,required=True);ap.add_argument('--out-dir',type=Path,required=True);a=ap.parse_args();a.out_dir.mkdir(parents=True,exist_ok=True)
 rows=profiles(); base=[]; baseline_elim=[]
 for pi in range(1,9):
  for v,q,h in rows:
   if h[4]!=15 or h[3]>101: continue
   if h==(0,0,7,101,15) or (pi,h) in BASELINE_EXTRA:
    baseline_elim.append(keyrow(pi,v,q,h,'eliminated','certified_current'))
   else: base.append((pi,v,q,h))
 if len(base)!=1269 or len(baseline_elim)!=3: raise RuntimeError(f'baseline census {len(base)}/{len(baseline_elim)}')
 after_h4=[]; delta_h4=[]
 for pi,v,q,h in base:
  if pi in (2,4) and h[3]==101: delta_h4.append(keyrow(pi,v,q,h,'eliminated','P2/P4_h4_le_100'))
  else: after_h4.append((pi,v,q,h))
 if len(delta_h4)!=74 or len(after_h4)!=1195: raise RuntimeError('h4 census')
 reg=json.loads(a.registry.read_text()); mapped={}
 for e in reg['entries']:
  for h in e['mapped_profiles']:
   k=(e['packing'],tuple(h))
   if k in mapped: raise RuntimeError('duplicate registry mapping')
   mapped[k]=e['tag']
 if len(mapped)!=30: raise RuntimeError('mapping census')
 unresolved=[];delta_cond=[]
 for pi,v,q,h in after_h4:
  tag=mapped.get((pi,h))
  if tag: delta_cond.append(keyrow(pi,v,q,h,'eliminated',tag))
  else: unresolved.append(keyrow(pi,v,q,h,'unresolved'))
 if len(delta_cond)!=30 or len(unresolved)!=1165: raise RuntimeError(f'delta census {len(delta_cond)}/{len(unresolved)}')
 minobj=min(x['objective'] for x in unresolved)
 layer=[x for x in unresolved if x['objective']==minobj]
 expected={(5,(1,4,4,101,15)),(5,(4,1,5,101,15)),(7,(4,1,5,101,15))}
 got={(x['packing'],tuple(x[f'h{i}'] for i in range(1,6))) for x in layer}
 if minobj!=29791 or got!=expected: raise RuntimeError(f'lowest layer mismatch {minobj} {got}')
 fields=['packing','objective','strength','h1','h2','h3','h4','h5','status','reason']
 def write(name,items):
  with (a.out_dir/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(items)
 write('unresolved_cells.csv',unresolved);write('delta_eliminated_cells.csv',delta_h4+delta_cond);write('baseline_eliminated_cells.csv',baseline_elim)
 by_strength=Counter(x['strength'] for x in unresolved);by_obj=Counter(x['objective'] for x in unresolved)
 summary={'schema':'dsjc5009_updated_census_v1','threshold':29847,'baseline_authority_exact_eliminations':11,'baseline_domain_eliminations':3,'baseline_unresolved_cells':1269,'h4_bound_eliminations':74,'conditional_delta_eliminations':30,'updated_unresolved_cells':1165,'updated_certified_lower_bound':29791,'incumbent_upper_bound':29848,'lowest_unresolved_cells':layer,'unresolved_by_strength':{str(k):v for k,v in sorted(by_strength.items())},'unresolved_by_objective':{str(k):v for k,v in sorted(by_obj.items())}}
 (a.out_dir/'census.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n');print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=='__main__':main()
