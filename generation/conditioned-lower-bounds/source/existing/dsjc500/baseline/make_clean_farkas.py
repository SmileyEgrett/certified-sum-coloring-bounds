#!/usr/bin/env python3
from pathlib import Path
import argparse,json,sys
from common import parse_dimacs,enumerate_stable_sets,enumerate_packings,stable_tuple_hash

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--graph',type=Path,required=True);ap.add_argument('--result-dir',type=Path,required=True);ap.add_argument('--out-dir',type=Path,required=True);a=ap.parse_args()
 g=parse_dimacs(a.graph);S=enumerate_stable_sets(g,6);best,packs=enumerate_packings(S[5]);a.out_dir.mkdir(parents=True,exist_ok=True)
 if best!=15 or len(packs)!=8:raise ValueError('packing structure')
 for pi,p in enumerate(packs,1):
  d=json.loads((a.result_dir/f'farkas101_7_P{pi}.json').read_text());c=d['certificate'];z=c['weights']
  top=[S[5][i] for i in p];removed=set().union(*(set(C) for C in top));rem=sorted(set(range(1,g['n']+1))-removed);q=[C for C in S[4] if set(C).isdisjoint(removed)];t=[C for C in S[3] if set(C).isdisjoint(removed)]
  if len(z)!=len(rem)+2:raise ValueError('length')
  w=z[:len(rem)];m4=z[-2];m3=z[-1]
  mins4=min(sum(w[rem.index(v)] for v in C)+m4 for C in q);mins3=min(sum(w[rem.index(v)] for v in C)+m3 for C in t);rhs=sum(w)+101*m4+7*m3
  if min(mins4,mins3)<0 or rhs>=0:raise ValueError('invalid source cert')
  out={'schema':'dsjc5009_exact_cover_farkas_v1','graph_raw_sha256':g['raw_sha256'],'graph_canonical_sha256':g['canonical_sha256'],'vertices':g['n'],'packing_number':pi,'packing_indices':list(p),'packing_sets':[list(C) for C in top],'residual_vertices':rem,'residual4_family_sha256':stable_tuple_hash(q),'residual3_family_sha256':stable_tuple_hash(t),'quad_quota':101,'triple_quota':7,'vertex_weights':[[v,x] for v,x in zip(rem,w) if x],'quad_multiplier':m4,'triple_multiplier':m3,'rhs':rhs,'minimum_quad_column':mins4,'minimum_triple_column':mins3,'source_rounding_denominator':c['denominator'],'meaning':'For Ax=b,x>=0, every column has nonnegative multiplier sum while b^T y is negative.'}
  (a.out_dir/f'P{pi}.farkas.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
  print(pi,len(q),len(t),rhs,mins4,mins3)
if __name__=='__main__':main()
