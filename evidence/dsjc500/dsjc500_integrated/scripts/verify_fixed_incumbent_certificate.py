#!/usr/bin/env python3
"""Fail-closed standard-library verifier for the fixed-incumbent certificate."""
from __future__ import annotations
import argparse,hashlib,json,sys
from functools import lru_cache
from pathlib import Path
from common import parse_dimacs,parse_coloring,enumerate_stable_sets,stable_tuple_hash,objective_from_sizes

def fail(s):raise ValueError(s)
def max_packings(rows):
 masks=[sum(1<<v for v in C) for C in rows];order=sorted(range(len(rows)),key=lambda i:(-sum(bool(masks[i]&masks[j]) for j in range(len(rows))),i));best=0;sols=set();nodes=0
 def dfs(pos,used,chosen):
  nonlocal best,sols,nodes;nodes+=1
  if len(chosen)+len(order)-pos<best:return
  if pos==len(order):
   z=tuple(sorted(chosen))
   if len(z)>best:best=len(z);sols={z}
   elif len(z)==best:sols.add(z)
   return
  i=order[pos]
  if not used&masks[i]:dfs(pos+1,used|masks[i],chosen+(i,))
  dfs(pos+1,used,chosen)
 dfs(0,0,());return best,sorted(sols),nodes
def odd_components(vertices,barrier,pairs):
 rem=set(vertices)-set(barrier);out=[]
 while rem:
  s=min(rem);rem.remove(s);q=[s];c=[]
  while q:
   v=q.pop();c.append(v)
   for u in list(rem):
    if tuple(sorted((u,v))) in pairs:rem.remove(u);q.append(u)
  if len(c)%2:out.append(sorted(c))
 return sorted(out)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--graph',type=Path,required=True);ap.add_argument('--coloring',type=Path,required=True);ap.add_argument('--certificate',type=Path,required=True);ap.add_argument('--json-out',type=Path);a=ap.parse_args();d=json.loads(a.certificate.read_text())
 expected={'schema','graph_raw_sha256','graph_canonical_sha256','coloring_sha256','vertices','fixed_top_classes','fixed_class_counts','residual_vertices','residual_family_sha256','residual_family_counts','maximum_triple_packing','maximum_triple_packing_count','triple_packing_search_nodes','maximum_triple_packings','improving_profiles_with_fixed_top','conclusion'}
 if set(d)!=expected or d['schema']!='dsjc5009_fixed_incumbent_structure_v1':fail('schema/key mismatch')
 g=parse_dimacs(a.graph);assign,ch=parse_coloring(a.coloring,g['n'])
 if (d['graph_raw_sha256'],d['graph_canonical_sha256'],d['coloring_sha256'],d['vertices'])!=(g['raw_sha256'],g['canonical_sha256'],ch,g['n']):fail('identity mismatch')
 classes={}
 for v,c in assign.items():classes.setdefault(c,[]).append(v)
 top=tuple(sorted((tuple(sorted(C)) for C in classes.values() if len(C)>=4),key=lambda C:(-len(C),C)))
 if d['fixed_top_classes']!=[list(C) for C in top] or d['fixed_class_counts']!={'5':15,'4':96}:fail('top classes mismatch')
 used={v for C in top for v in C};res=tuple(v for v in range(1,g['n']+1) if v not in used)
 if d['residual_vertices']!=list(res) or len(res)!=41:fail('residual mismatch')
 S=enumerate_stable_sets(g,4);fam={k:[C for C in S[k] if set(C).issubset(res)] for k in (2,3,4)}
 if d['residual_family_sha256']!={str(k):stable_tuple_hash(fam[k]) for k in (2,3,4)} or d['residual_family_counts']!={str(k):len(fam[k]) for k in (2,3,4)} or fam[4]:fail('family mismatch')
 best,packs,nodes=max_packings(fam[3])
 if best!=10 or len(packs)!=12 or d['maximum_triple_packing']!=best or d['maximum_triple_packing_count']!=len(packs) or d['triple_packing_search_nodes']!=nodes:fail('triple packing mismatch')
 pairset=set(fam[2]);items=d['maximum_triple_packings']
 if len(items)!=len(packs):fail('packing detail count')
 for item,p in zip(items,packs):
  triples=[fam[3][i] for i in p];left=tuple(v for v in res if all(v not in C for C in triples))
  if item['triple_indices']!=list(p) or item['triples']!=[list(C) for C in triples] or item['residual_vertices']!=list(left):fail('packing detail mismatch')
  edges=[];seen=set()
  for e in item['matching']:
   if not isinstance(e,list) or len(e)!=2:fail('matching shape')
   z=tuple(sorted(e))
   if z not in pairset or any(v not in left or v in seen for v in z):fail('invalid matching')
   seen.update(z);edges.append(z)
  if len(edges)!=item['matching_size'] or not (0<=item['matching_size']<=4):fail('matching lower bound mismatch')
  B=item['barrier'];odd=odd_components(left,B,pairset)
  if odd!=item['odd_components']:fail('odd components mismatch')
  num=len(left)+len(B)-len(odd)
  if num<0 or num%2 or num//2!=item['matching_size']:fail('Tutte-Berge upper bound mismatch')
 profiles=[]
 for h3 in range(14):
  for h2 in range(21):
   h1=41-3*h3-2*h2
   if h1<0:continue
   sizes=[5]*15+[4]*96+[3]*h3+[2]*h2+[1]*h1;obj=objective_from_sizes(sizes)
   if obj<=29847:profiles.append({'objective':obj,'h1':h1,'h2':h2,'h3':h3,'h4':96,'h5':15,'reason':'triple_bound' if h3>best else 'matching_bound'})
 profiles.sort(key=lambda x:(x['objective'],x['h1'],x['h2'],x['h3']))
 if max(item['matching_size'] for item in items)!=4:fail('global matching maximum mismatch')
 if profiles!=d['improving_profiles_with_fixed_top'] or len(profiles)!=9 or any(x['reason']=='matching_bound' and not (x['h3']==10 and x['h2']==5) for x in profiles):fail('profile conclusion mismatch')
 out={'status':'VERIFIED','residual_vertices':41,'maximum_triples':10,'maximum_triple_packings':12,'maximum_pairs_after_10_triples':4,'excluded_profiles':9,'conclusion':d['conclusion']}
 if a.json_out:a.json_out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
 print(json.dumps(out,indent=2,sort_keys=True));print('FIXED-INCUMBENT CERTIFICATE VERIFIED')
if __name__=='__main__':
 try:main()
 except Exception as e:print(f'VERIFICATION FAILED: {e}',file=sys.stderr);raise SystemExit(1)
