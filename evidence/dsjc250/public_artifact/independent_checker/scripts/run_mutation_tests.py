#!/usr/bin/env python3
from pathlib import Path
import copy,gzip,json,shutil,subprocess,tempfile,sys
src=Path(__file__).resolve().parents[1]

def manifest(root):
 subprocess.run([sys.executable,str(root/'scripts/make_manifest.py'),str(root)],check=True,stdout=subprocess.DEVNULL)
def expect_fail(name,mutate,remake=True,marker=None):
 with tempfile.TemporaryDirectory(prefix='dsjc2509-mutation-') as td:
  root=Path(td)/'proof';shutil.copytree(src,root)
  mutate(root)
  if remake:manifest(root)
  p=subprocess.run([sys.executable,str(root/'scripts/verify.py'),'--root',str(root)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
  if p.returncode!=1 or not p.stderr.startswith('VERIFICATION FAILED: '):raise SystemExit(f'{name}: not a completed verifier rejection (exit {p.returncode}): {p.stderr.strip()}')
  if marker is not None and marker not in p.stderr:raise SystemExit(f'{name}: wrong rejection reason: {p.stderr.strip()}')
  print(f'PASS {name}: {p.stderr.strip().splitlines()[-1]}')

def extra(root):(root/'unexpected.txt').write_text('unexpected\n')
def graph(root):
 p=root/'data/DSJC250.9.col';p.write_text(p.read_text()+'c changed bytes\n')
def coloring(root):
 p=root/'witnesses/DSJC250.9_sum8277.coloring';s=p.read_text();p.write_text(s.replace('\n1 38\n','\n1 999\n',1))
def proof(root):
 p=root/'certificates/lpbb/env_x3.proof.json.gz'
 with gzip.open(p,'rt') as f:d=json.load(f)
 for r in d['proof']:
  if r['kind']=='leaf':r['numerator']+=1;break
 with gzip.open(p,'wt') as f:json.dump(d,f,separators=(',',':'))

def duplicate_status(root):
 p=root/'certificates/lpbb/env_x3.proof.json.gz'
 with gzip.open(p,'rt') as f:s=f.read()
 if not s.startswith('{"schema":'):raise SystemExit('unexpected proof serialization')
 with gzip.open(p,'wt') as f:f.write('{"status":"PROVED",'+s[1:])

def boolean_child(root):
 p=root/'certificates/lpbb/env_x3.proof.json.gz'
 with gzip.open(p,'rt') as f:d=json.load(f)
 d['proof'][d['root']]['zero']=False
 with gzip.open(p,'wt') as f:json.dump(d,f,separators=(',',':'))

def negative_variable(root):
 p=root/'certificates/lpbb/env_x3.proof.json.gz'
 with gzip.open(p,'rt') as f:d=json.load(f)
 d['proof'][d['root']]['var']=-1
 with gzip.open(p,'wt') as f:json.dump(d,f,separators=(',',':'))

def replace_property(lines,key,value):
 prefix=key+'='
 matches=[i for i,line in enumerate(lines) if line.startswith(prefix)]
 if len(matches)!=1:raise SystemExit(f'expected one {key} property')
 lines[matches[0]]=prefix+str(value)

def weak_rational(root,name,condition_count=None,repair_slack=True):
 p=root/'certificates/rational'/name;lines=p.read_text().splitlines()
 replace_property(lines,'denominator',1);replace_property(lines,'rhs_numerator',250);replace_property(lines,'claimed_bound',250)
 for i,line in enumerate(lines):
  if line.startswith('weight\t'):
   fields=line.split('\t');lines[i]=f'weight\t{fields[1]}\t1'
  elif line.startswith('condition\t'):
   fields=line.split('\t');lines[i]=f'condition\t{fields[1]}\t{condition_count if condition_count is not None else fields[2]}\t0'
 if any(line.startswith('slack_budget=') for line in lines) and repair_slack:
  required=int(next(line.split('=',1)[1] for line in lines if line.startswith('required_residual_sets=')))
  replace_property(lines,'slack_budget',250-required)
 p.write_text('\n'.join(lines)+'\n')

def weak_global(root):weak_rational(root,'ge4_global.rational')
def weak_residual_x1(root):weak_rational(root,'dual_h5_1_forbid_x1.rational')
def nonapplicable_condition(root):weak_rational(root,'ge4_h5_eq_2.rational',condition_count=3)
def inconsistent_slack(root):
 p=root/'certificates/rational/dual_h5_1_x3_slack.rational';lines=p.read_text().splitlines()
 current=int(next(line.split('=',1)[1] for line in lines if line.startswith('slack_budget=')))
 replace_property(lines,'slack_budget',current+1);p.write_text('\n'.join(lines)+'\n')

def matching_root(name):
 def mutate(root):
  p=root/f'certificates/lpbb/{name}.proof.json.gz'
  with gzip.open(p,'rt') as f:d=json.load(f)
  tops={v for C in d['model']['tops'] for v in C}
  residual=[v for v in range(1,d['model']['n']+1) if v not in tops]
  d['proof']=[{'kind':'matching_leaf','selected_score':0,'residual':residual,
               'matching_upper':len(residual)//2,'barrier':[],
               'odd_components':[residual]}]
  d['root']=0
  d['statistics'].update(nodes=1,branches=0,leaves=1)
  with gzip.open(p,'wt') as f:json.dump(d,f,separators=(',',':'))
 return mutate

expect_fail('unexpected-file',extra,False)
expect_fail('changed-graph-with-rehashed-manifest',graph,True)
expect_fail('changed-coloring-with-rehashed-manifest',coloring,True)
expect_fail('invalid-proof-leaf-with-rehashed-manifest',proof,True)
expect_fail('duplicate-proof-status-key',duplicate_status,True,'duplicate JSON key: status')
expect_fail('boolean-child-reference',boolean_child,True,'invalid strict-postorder child reference')
expect_fail('negative-branch-variable',negative_variable,True,'branch variable invalid or inactive')
incomplete='mathematical proof incomplete:'
expect_fail('valid-weak-global-rational',weak_global,True,incomplete)
expect_fail('valid-weak-residual-x1-rational',weak_residual_x1,True,incomplete)
expect_fail('nonapplicable-layered-condition',nonapplicable_condition,True,incomplete)
expect_fail('inconsistent-residual-slack',inconsistent_slack,True,'residual slack mismatch')
unsupported='matching_leaf records are unsupported by this independent checker'
expect_fail('reported-env-x2-root-matching-leaf',matching_root('env_x2'),True,unsupported)
expect_fail('non-pair-quad-x2-root-matching-leaf',matching_root('quad_x2'),True,unsupported)

def witness_mutation(change):
 def mutate(root):
  p=root/'witnesses/witnesses.json';d=json.loads(p.read_text())
  change(d);p.write_text(json.dumps(d)+'\n')
 return mutate

for role in ('x2','x3','x1+x2'):
 for kind in ('quads','triples'):
  expect_fail(f'{role}-short-{kind}',witness_mutation(lambda d,r=role,k=kind:d['envelope'][r][k][0].pop()),marker='invalid class size or shape')

def wrong_named_top(d):
 d['envelope']['x3']=copy.deepcopy(d['envelope']['x2'])
 d['envelope']['x3']['triples'].pop()
 d['envelope']['x3']['max_triples']=28
 d['envelope']['x3']['g3']=66
expect_fail('stable-disjoint-wrong-named-top',witness_mutation(wrong_named_top),marker='named tops mismatch')

for tag,vertex in [('zero',0),('negative',-1),('too-large',251),('boolean',True),('float',1.0),('string','1'),('null',None)]:
 expect_fail('envelope-vertex-'+tag,witness_mutation(lambda d,v=vertex:d['envelope']['x2']['quads'][0].__setitem__(-1,v)),marker='vertex must be an integer in 1..250')

def compensated_sizes(d):
 quads=d['envelope']['x2']['quads'];quads[1].append(quads[0].pop())
expect_fail('compensating-short-long-classes',witness_mutation(compensated_sizes),marker='invalid class size or shape')
expect_fail('duplicate-envelope-vertex',witness_mutation(lambda d:d['envelope']['x2']['quads'][0].__setitem__(1,d['envelope']['x2']['quads'][0][0])),marker='duplicate vertex or unstable class')
expect_fail('repeated-stable-envelope-class',witness_mutation(lambda d:d['envelope']['x2']['quads'].__setitem__(1,d['envelope']['x2']['quads'][0])),marker='overlapping classes')
expect_fail('envelope-classes-not-list',witness_mutation(lambda d:d['envelope']['x2'].__setitem__('quads',{})),marker='classes must be a list')
expect_fail('missing-envelope-role',witness_mutation(lambda d:d['envelope'].pop('x3')),marker='envelope roles mismatch')
expect_fail('extra-envelope-role',witness_mutation(lambda d:d['envelope'].__setitem__('other',d['envelope']['x2'])),marker='envelope roles mismatch')
expect_fail('extra-pair-role',witness_mutation(lambda d:d['pairmax'].__setitem__('other',d['pairmax']['H1-C'])),marker='pair witness roles mismatch')
for role in ('H1-C','H2-F'):
 expect_fail(role+'-empty-extra-class',witness_mutation(lambda d,r=role:d['pairmax'][r]['classes'].append([])),marker='invalid class size or shape')
 expect_fail(role+'-wrong-declared-top',witness_mutation(lambda d,r=role:d['pairmax'][r].__setitem__('tops',[d['five_sets'][2]])),marker='named tops mismatch')
 expect_fail(role+'-vertex-float',witness_mutation(lambda d,r=role:d['pairmax'][r]['classes'][0].__setitem__(0,float(d['pairmax'][r]['classes'][0][0]))),marker='vertex must be an integer in 1..250')

def missing_singleton(d):
 cls=d['pairmax']['H1-C']['classes'];cls.remove(next(C for C in cls if len(C)==1))
expect_fail('pair-missing-singleton',witness_mutation(missing_singleton),marker='incomplete partition')

def positive_witness_variants(root):
 p=root/'witnesses/witnesses.json';d=json.loads(p.read_text())
 for w in d['envelope'].values():
  for key in ('tops','quads','triples'):w[key]=[list(reversed(C)) for C in reversed(w[key])]
  w['status']='UNVERIFIED HISTORICAL METADATA';w['dual_bound']=-123.5
 for w in d['pairmax'].values():
  for key in ('tops','classes'):w[key]=[list(reversed(C)) for C in reversed(w[key])]
  w['status']='UNVERIFIED HISTORICAL METADATA';w['dual_bound']=-123.5
 d['optimal_colouring']={'unverified_historical_metadata':True}
 p.write_text(json.dumps(d)+'\n')
with tempfile.TemporaryDirectory(prefix='dsjc2509-positive-witness-') as td:
 root=Path(td)/'proof';shutil.copytree(src,root);positive_witness_variants(root);manifest(root)
 p=subprocess.run([sys.executable,str(root/'scripts/verify.py'),'--root',str(root)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 if p.returncode!=0 or 'OPTIMUM 8277 CERTIFIED' not in p.stdout:raise SystemExit(f'positive witness permutations/metadata failed: {p.stderr}')
 print('PASS positive-witness-permutations-and-metadata-nonauthority: exit 0; exact proof unchanged')
print('ALL MUTATION TESTS PASSED')
