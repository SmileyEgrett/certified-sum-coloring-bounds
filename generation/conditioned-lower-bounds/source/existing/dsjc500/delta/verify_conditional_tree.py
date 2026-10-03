#!/usr/bin/env python3
"""Independent standard-library replay of one conditional tree certificate."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
import exact_mscp_conditional_verify as checked

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--graph',type=Path,required=True);ap.add_argument('--model',type=Path,required=True);ap.add_argument('--proof',type=Path,required=True);ap.add_argument('--stable-node-limit',type=int,default=10_000_000);ap.add_argument('--maximum-json-bytes',type=int,default=100_000_000);ap.add_argument('--maximum-proof-bytes',type=int,default=500_000_000);ap.add_argument('--maximum-proof-records',type=int,default=1_000_000);ap.add_argument('--json-out',type=Path);a=ap.parse_args()
 g=checked.parse_graph(a.graph); raw=checked.load_json(a.model,'conditional model',a.maximum_json_bytes)
 if not isinstance(raw,dict) or not isinstance(raw.get('model_id'),str):checked.fail('model ID missing')
 alpha=raw.get('maximum_class_size')
 if type(alpha) is not int or alpha<=0:checked.fail('maximum class size invalid')
 S=checked.enumerate_stable_sets(g,alpha+1,a.stable_node_limit).by_size
 c=checked.verify_tree_proof(a.proof,a.model,raw['model_id'],g,S,alpha,a.maximum_json_bytes,a.maximum_proof_bytes,a.maximum_proof_records)
 out={'status':'VERIFIED','model_id':c.certificate_id,'fixed_top_classes':[list(x) for x in c.fixed_top_classes],'scores':[list(x) for x in c.score_by_size],'caps':[list(x) for x in c.type_caps],'strict_target':c.strict_target,'method':c.kind,'proof_stats':[list(x) for x in c.proof_stats]}
 if a.json_out:a.json_out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
 print(json.dumps(out,indent=2,sort_keys=True));print('CONDITIONAL TREE VERIFIED')
if __name__=='__main__':
 try:main()
 except Exception as e:print(f'VERIFICATION FAILED: {e}',file=sys.stderr);raise SystemExit(1)
