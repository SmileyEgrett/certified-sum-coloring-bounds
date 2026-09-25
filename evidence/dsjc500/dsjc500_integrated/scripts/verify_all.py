#!/usr/bin/env python3
"""Standalone fail-closed verifier for the integrated DSJC500.9 delta release.

The verifier uses only the Python standard library. It validates the release
manifest, replays the initial certificate stage, reconstructs graph/stable-set
and top-packing data, checks all delta proof trees and explicit conclusion
mappings, verifies the P2/P4 one-unit residual-four-set certificates, rebuilds
and byte-compares the updated census and 178-cell frontier, and verifies the
fixed-incumbent structural certificate.
"""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import exact_mscp_conditional_verify as checked
import verify_residual_kset_lpbb as residual_verify

def fail(msg: str) -> None: raise RuntimeError(msg)
def progress(msg: str) -> None: print(f'[verify] {msg}',flush=True)
def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path: Path): return json.loads(path.read_text())

def check_manifest(root: Path) -> None:
 manifest=root/'MANIFEST.sha256'; expected={}
 for line in manifest.read_text().splitlines():
  if not line.strip(): continue
  if '  ' not in line: fail('malformed manifest line')
  digest,name=line.split('  ',1)
  if len(digest)!=64 or name in expected or name.startswith('/') or '..' in Path(name).parts: fail('unsafe/duplicate manifest entry')
  expected[name]=digest
 actual=[]
 for p in sorted(root.rglob('*')):
  if p.is_symlink(): fail(f'symlink forbidden: {p.relative_to(root)}')
  if p.is_file() and p!=manifest: actual.append(p.relative_to(root).as_posix())
 if sorted(expected)!=actual: fail(f'manifest file set mismatch: missing={sorted(set(expected)-set(actual))}, extra={sorted(set(actual)-set(expected))}')
 for name,digest in expected.items():
  if sha(root/name)!=digest: fail(f'manifest digest mismatch: {name}')

def run(cmd: list[str], cwd: Path, env: dict[str,str]|None=None) -> str:
 e=os.environ.copy(); e['PYTHONDONTWRITEBYTECODE']='1'
 if env: e.update(env)
 p=subprocess.run(cmd,cwd=cwd,env=e,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 if p.returncode: fail(f"command failed ({p.returncode}): {' '.join(cmd)}\n{p.stdout}")
 return p.stdout

def compare_files(a: Path,b: Path,what: str) -> None:
 if a.read_bytes()!=b.read_bytes(): fail(f'{what} reconstruction mismatch')

def main() -> None:
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=ROOT);ap.add_argument('--skip-manifest',action='store_true');a=ap.parse_args();root=a.root.resolve()
 if not a.skip_manifest:
  progress('checking top-level manifest'); check_manifest(root)
 graph=root/'data/DSJC500.9.col'; coloring=root/'data/DSJC500.9_sum29848.coloring'
 with tempfile.TemporaryDirectory(prefix='dsjc5009-final-replay-') as td:
  temp=Path(td)
  progress('replaying initial certificate stage')
  # Initial profile-reduction replay.
  baseline=root/'baseline/dsjc5009-open-exact-investigation'
  baseline_out=temp/'baseline.json'
  run([sys.executable,str(baseline/'scripts/verify.py'),'--root',str(baseline),'--json-out',str(baseline_out)],baseline)
  bz=load(baseline_out)
  br=bz.get('profile_reduction',{})
  inc=bz.get('incumbent',{})
  if br.get('certified_chromatic_sum_lower_bound')!=29785 or inc.get('canonical_sum')!=29848 or br.get('unresolved_cells')!=1269: fail('baseline conclusion mismatch')
  progress('checking fixed-incumbent structural certificate')
  fixed_out=temp/'fixed.json'
  run([sys.executable,str(root/'scripts/verify_fixed_incumbent_certificate.py'),'--graph',str(graph),'--coloring',str(coloring),'--certificate',str(root/'certificates/structural/fixed_incumbent.json'),'--json-out',str(fixed_out)],root)
  fz=load(fixed_out)
  if fz.get('status')!='VERIFIED' or fz.get('maximum_triples')!=10 or fz.get('maximum_pairs_after_10_triples')!=4: fail('fixed-incumbent conclusion')
  progress('reconstructing graph, stable sets, and maximum top packings')
  # Reconstruct instance once for all conditional trees.
  g=checked.parse_graph(graph)
  if g.raw_sha256!='95276841dffcde7c04de2fc1ae8e43b6c7b84173b4a9646b1cc6b392a3bd7b39' or g.canonical_sha256!='69e7453e2a389197f67fe0e02cf661bc71132b4ea457a434b4726a4b7489b618': fail('graph identity')
  enum=checked.enumerate_stable_sets(g,6,200000);S=enum.by_size
  expected_counts={2:12313,3:19901,4:2428,5:23,6:0}
  if {k:len(S.get(k,())) for k in expected_counts}!=expected_counts: fail('stable-set census')
  best,packings_by_count=checked.enumerate_top_packings(S[5],g.vertices,1_000_000)
  packings=packings_by_count[best]
  if best!=15 or len(packings)!=8: fail('top packing census')
  progress('checking P2/P4 residual four-set certificates')
  # Residual-four-set one-unit bounds.
  h4=[]
  for pi in (2,4):
   z=residual_verify.verify(graph,root/f'certificates/old_duals/k4dual_P{pi}.txt',root/f'certificates/residual_kset_lpbb/P{pi}_h4_le_100.proof.json.gz')
   if z.get('status')!='VERIFIED' or z.get('bound')!=100 or z.get('packing')!=pi: fail(f'P{pi} residual bound')
   h4.append(z)
  progress('checking 17 conditional trees and mappings')
  # Conditional trees and explicit mappings.
  registry=load(root/'certificates/conditional_registry.json')
  if set(registry)!={'schema','entry_count','mapped_cell_count','entries'} or registry['schema']!='dsjc5009_delta_conditional_registry_v1' or registry['entry_count']!=17 or registry['mapped_cell_count']!=30: fail('conditional registry header')
  mapped=set();tree_stats=[]
  for e in registry['entries']:
   expected_keys={'tag','packing','model','columns','proof','model_id','model_sha256','columns_sha256','proof_sha256','mapped_profiles'}
   if set(e)!=expected_keys: fail(f"registry keys: {e.get('tag')}")
   model=root/e['model']; columns=root/e['columns']; proof=root/e['proof']
   if sha(model)!=e['model_sha256'] or sha(columns)!=e['columns_sha256'] or sha(proof)!=e['proof_sha256']: fail(f"registry artifact hash: {e['tag']}")
   raw=checked.load_json(model,'conditional model',100_000_000)
   if raw.get('model_id')!=e['model_id']: fail(f"model id: {e['tag']}")
   conclusion=checked.verify_tree_proof(proof,model,e['model_id'],g,S,5,100_000_000,500_000_000,1_000_000)
   pi=e['packing']
   if type(pi) is not int or not 1<=pi<=8: fail('packing in registry')
   packing=packings[pi-1]
   for hlist in e['mapped_profiles']:
    if not isinstance(hlist,list) or len(hlist)!=5 or any(type(x) is not int or x<0 for x in hlist): fail('mapped profile shape')
    key=(pi,tuple(hlist))
    if key in mapped: fail('duplicate mapped cell')
    mapped.add(key)
    profile=checked.profile_from_h((0,*hlist))
    if profile.objective>29847 or not conclusion.rejects(profile,packing): fail(f"conclusion mapping not justified: {e['tag']} P{pi} {hlist}")
   tree_stats.append({'tag':e['tag'],'packing':pi,'mapped_cells':len(e['mapped_profiles']),'proof_stats':dict(conclusion.proof_stats),'proof_sha256':e['proof_sha256']})
  if len(mapped)!=30: fail('mapped-cell census')
  progress('rebuilding updated unresolved-cell census')
  # Deterministic census reconstruction and byte comparison.
  census=temp/'census'; census.mkdir()
  run([sys.executable,str(root/'scripts/build_updated_census.py'),'--registry',str(root/'certificates/conditional_registry.json'),'--out-dir',str(census)],root)
  for name in ('census.json','unresolved_cells.csv','delta_eliminated_cells.csv','baseline_eliminated_cells.csv'):
   compare_files(census/name,root/'results/census'/name,f'census {name}')
  cz=load(census/'census.json')
  if cz['updated_unresolved_cells']!=1165 or cz['updated_certified_lower_bound']!=29791 or len(cz['lowest_unresolved_cells'])!=3: fail('updated census conclusion')
  progress('rebuilding splitting frontier and supporting normals')
  # Splitting frontier and exact positive supporting normals.
  front=temp/'frontier';front.mkdir()
  run([sys.executable,str(root/'scripts/build_frontier.py'),'--out-dir',str(front)],root)
  for name in ('admissible_cells_before_delta.csv','frontier_cells.csv','coverage_paths.json','frontier_summary.json'):
   compare_files(front/name,root/'results/frontier'/name,f'frontier {name}')
  normals=temp/'supporting_normals.json'
  run([sys.executable,str(root/'scripts/build_supporting_normals.py'),'--frontier-csv',str(front/'frontier_cells.csv'),'--out',str(normals)],root)
  compare_files(normals,root/'results/frontier/supporting_normals.json','supporting normals')
  result={'schema':'dsjc5009_integrated_delta_replay_v1','status':'VERIFIED','certified_interval':[29791,29848],'baseline_unresolved_cells':1269,'h4_bound_eliminations':74,'conditional_mapped_eliminations':30,'updated_unresolved_cells':1165,'splitting_frontier_cells':178,'coverage_paths':1195,'conditional_tree_count':17,'lowest_unresolved_cells':cz['lowest_unresolved_cells'],'residual_h4_certificates':h4,'conditional_trees':tree_stats,'fixed_incumbent':fz}
  print(json.dumps(result,indent=2,sort_keys=True));print('DSJC500.9 INTEGRATED DELTA CHECK PASSED')
if __name__=='__main__':
 try: main()
 except Exception as exc:
  print(f'VERIFICATION FAILED: {exc}',file=sys.stderr);raise SystemExit(1)
