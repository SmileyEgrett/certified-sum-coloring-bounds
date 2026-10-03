#!/usr/bin/env python3
"""Create one deterministic conditional weighted-packing model."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import exact_mscp_conditional_discover as discover
import exact_mscp_conditional_verify as checked

def parse_map(text:str)->dict[int,int]:
 out={}
 if not text:return out
 for item in text.split(','):
  k,v=item.split(':',1); k=int(k);v=int(v)
  if k in out:raise ValueError('duplicate key')
  out[k]=v
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--graph',type=Path,required=True);ap.add_argument('--maximum-class-size',type=int,required=True);ap.add_argument('--packing-number',type=int,required=True);ap.add_argument('--scores',required=True);ap.add_argument('--caps',default='');ap.add_argument('--strict-target',type=int,required=True);ap.add_argument('--radix',type=int,required=True);ap.add_argument('--stable-node-limit',type=int,default=10_000_000);ap.add_argument('--top-packing-limit',type=int,default=100_000);ap.add_argument('--out-dir',type=Path,required=True);a=ap.parse_args()
 g=checked.parse_graph(a.graph); enum=checked.enumerate_stable_sets(g,a.maximum_class_size+1,a.stable_node_limit); S=enum.by_size
 if S.get(a.maximum_class_size+1):raise ValueError('maximum class size is not exact')
 best,packs=checked.enumerate_top_packings(S[a.maximum_class_size],g.vertices,a.top_packing_limit)
 if not 1<=a.packing_number<=len(packs[best]):raise ValueError('packing number out of range')
 scores=parse_map(a.scores);caps=parse_map(a.caps)
 desc=discover.create_model(a.out_dir,g,S,a.maximum_class_size,packs[best][a.packing_number-1],scores,caps,a.strict_target,a.radix)
 model=a.out_dir/desc['model_file'];columns=a.out_dir/desc['columns_file']
 print(json.dumps({'model':str(model),'columns':str(columns),'model_id':desc['model_id'],'column_count':desc['column_count'],'top_packing_size':best},indent=2))
if __name__=='__main__':
 try:main()
 except Exception as e:print(f'MODEL GENERATION FAILED: {e}',file=sys.stderr);raise SystemExit(1)
