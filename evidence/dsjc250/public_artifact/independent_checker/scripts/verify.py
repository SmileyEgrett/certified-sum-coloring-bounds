#!/usr/bin/env python3
"""Fail-closed verifier for the DSJC250.9 minimum-sum-colouring proof bundle.

Uses only the Python standard library.  All proof arithmetic is integral.
No optimizer, SAT solver, or floating-point tolerance is used by this verifier.
"""
from __future__ import annotations
import argparse, gzip, hashlib, json, os, stat, sys, time
from dataclasses import asdict, dataclass
from pathlib import Path
from itertools import combinations

EXPECTED_RAW='1b90f811e4d44f8937075865790b845e986b08b9da53caea57b2adf1c57383e7'
EXPECTED_CANON='52be422c0065411e126008bf4ee8ee2ba21320bde0a0e94d5ab308c2e34f53a8'
EXPECTED_N=250; EXPECTED_M=27897
D_DEFAULT=10**9

@dataclass(frozen=True)
class LayeredConclusion:
 certificate_id:str;minimum_size:int;bound:int;conditions:tuple
 denominator:int;rhs_numerator:int;kind:str='layered'

@dataclass(frozen=True)
class ResidualConclusion:
 certificate_id:str;bound:int;required_residual_sets:int;slack_budget:int
 denominator:int;rhs_numerator:int;residual_columns:int;tops:tuple
 kind:str='residual'

@dataclass(frozen=True)
class LPBBConclusion:
 certificate_id:str;nodes:int;leaves:int;branches:int;matching_leaves:int
 tops:tuple;caps:tuple;score_by_size:tuple;strict_target:int;kind:str='lpbb'

def die(msg): raise ValueError(msg)
def sha256_bytes(b): return hashlib.sha256(b).hexdigest()
def sha256_file(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()

def verify_manifest(root:Path):
 mp=root/'MANIFEST.sha256'; lines=mp.read_text('utf-8').splitlines(); entries={}; prev=''
 for i,line in enumerate(lines,1):
  if len(line)<67 or line[64:66]!='  ':die(f'MANIFEST.sha256:{i}: malformed row')
  h,rel=line[:64],line[66:]
  if any(c not in '0123456789abcdef' for c in h):die(f'MANIFEST.sha256:{i}: malformed hash')
  pp=Path(rel)
  if not rel or pp.is_absolute() or '..' in pp.parts or rel.startswith('./'):die(f'MANIFEST.sha256:{i}: unsafe path')
  if rel<=prev:die('manifest paths are not strictly sorted')
  prev=rel
  if rel in entries:die('duplicate manifest path')
  entries[rel]=h
 actual=[]
 for p in root.rglob('*'):
  if p.name=='MANIFEST.sha256':continue
  st=p.lstat()
  if stat.S_ISLNK(st.st_mode):die(f'symlink rejected: {p.relative_to(root)}')
  if p.is_file():actual.append(p.relative_to(root).as_posix())
 if sorted(actual)!=list(entries):
  die(f'manifest file set mismatch: missing={sorted(set(entries)-set(actual))}, extra={sorted(set(actual)-set(entries))}')
 for rel,h in entries.items():
  if sha256_file(root/rel)!=h:die(f'hash mismatch: {rel}')
 return len(entries)

def parse_graph(path:Path):
 raw=path.read_bytes(); raw_hash=sha256_bytes(raw)
 n=None;decl=None;kind=None;edges=set();records=0;header=False
 for ln,rb in enumerate(raw.splitlines(),1):
  try:s=rb.decode('ascii').strip()
  except UnicodeDecodeError:die(f'{path}:{ln}: non-ASCII input')
  if not s:continue
  f=s.split()
  if f[0]=='c':continue
  if f[0]=='p':
   if header:die(f'{path}:{ln}: duplicate header')
   if len(f)!=4 or f[1] not in ('edge','edges','col'):die(f'{path}:{ln}: malformed header')
   try:n=int(f[2]);decl=int(f[3])
   except:die(f'{path}:{ln}: noninteger header')
   if n<=0 or decl<0:die(f'{path}:{ln}: invalid header values')
   kind=f[1];header=True
  elif f[0]=='e':
   if not header:die(f'{path}:{ln}: edge before header')
   if len(f)!=3:die(f'{path}:{ln}: malformed edge')
   try:a,b=map(int,f[1:])
   except:die(f'{path}:{ln}: noninteger edge')
   if not (1<=a<=n and 1<=b<=n) or a==b:die(f'{path}:{ln}: invalid edge')
   e=(a,b) if a<b else (b,a);records+=1
   if e in edges:die(f'{path}:{ln}: duplicate edge')
   edges.add(e)
  else:die(f'{path}:{ln}: unknown record {f[0]!r}')
 if not header:die('missing DIMACS header')
 if records!=decl or len(edges)!=decl:die('declared/record/unique edge count mismatch')
 canon='exact_mscp_graph_v1\nvertices %d\n'%n+''.join(f'{a} {b}\n' for a,b in sorted(edges))
 return {'n':n,'m':len(edges),'edges':edges,'raw_hash':raw_hash,'canonical_hash':sha256_bytes(canon.encode()),'kind':kind}

def enumerate_stable(g):
 n=g['n']; edges=g['edges'];adj=[0]*(n+1);full=sum(1<<v for v in range(1,n+1))
 for a,b in edges:adj[a]|=1<<b;adj[b]|=1<<a
 comp=[0]*(n+1)
 for v in range(1,n+1):comp[v]=full&~adj[v]&~(1<<v)
 def bits(m):
  while m:
   b=m&-m;yield b.bit_length()-1;m^=b
 S={2:[],3:[],4:[],5:[],6:[]}
 for a in range(1,n+1):
  ca=comp[a]&~((1<<(a+1))-1)
  for b in bits(ca):
   S[2].append((a,b));cb=ca&comp[b]&~((1<<(b+1))-1)
   for c in bits(cb):
    S[3].append((a,b,c));cc=cb&comp[c]&~((1<<(c+1))-1)
    for d in bits(cc):
     S[4].append((a,b,c,d));cd=cc&comp[d]&~((1<<(d+1))-1)
     for e in bits(cd):
      S[5].append((a,b,c,d,e));ce=cd&comp[e]&~((1<<(e+1))-1)
      for z in bits(ce):S[6].append((a,b,c,d,e,z))
 return S,adj

def stable(C,adj):return len(C)==len(set(C)) and all(not (adj[a]>>b)&1 for a,b in combinations(C,2))

def parse_kv_rows(path:Path,row_names):
 props={};rows={k:[] for k in row_names};started=False
 for ln,line in enumerate(path.read_text('utf-8').splitlines(),1):
  s=line.strip()
  if not s or s.startswith('#'):continue
  tag=s.split('\t',1)[0]
  if tag in rows:
   started=True;rows[tag].append((ln,s.split('\t')));continue
  if started:die(f'{path}:{ln}: property after rows')
  if '=' not in s:die(f'{path}:{ln}: expected key=value')
  k,v=map(str.strip,s.split('=',1))
  if not k or k in props:die(f'{path}:{ln}: duplicate/empty key')
  props[k]=v
 return props,rows

def intv(s,ctx,negative=True):
 if not s or (s[0] in '+-' and len(s)==1):die(f'invalid integer for {ctx}')
 if s[0]=='-' and not negative:die(f'negative integer for {ctx}')
 try:v=int(s)
 except:die(f'invalid integer for {ctx}')
 if str(v)!=s and not (s.startswith('+') and str(v)==s[1:]):die(f'noncanonical integer for {ctx}')
 return v

def verify_layered_rational(path,g,S,expected_id):
 props,rows=parse_kv_rows(path,{'condition','weight'})
 keys={'schema','certificate_id','graph_raw_sha256','graph_canonical_sha256','vertices','maximum_class_size','minimum_class_size','claimed_bound','denominator','rhs_numerator','condition_count'}
 if set(props)!=keys:die(f'{path}: property keys mismatch')
 if props['schema']!='exact_mscp_layered_rational_v1' or props['certificate_id']!=expected_id:die(f'{path}: schema/id mismatch')
 if props['graph_raw_sha256']!=g['raw_hash'] or props['graph_canonical_sha256']!=g['canonical_hash']:die(f'{path}: graph hash mismatch')
 if intv(props['vertices'],'vertices')!=g['n'] or intv(props['maximum_class_size'],'alpha')!=5:die(f'{path}: dimensions mismatch')
 mn=intv(props['minimum_class_size'],'minimum size');bound=intv(props['claimed_bound'],'bound');D=intv(props['denominator'],'denominator',False);rhs=intv(props['rhs_numerator'],'rhs')
 if not (1<=mn<=5 and D>0 and rhs>=0):die(f'{path}: invalid conclusion data')
 if intv(props['condition_count'],'condition count')!=len(rows['condition']):die(f'{path}: condition count mismatch')
 mult={};conds={};prev=0
 for ln,f in rows['condition']:
  if len(f)!=4:die(f'{path}:{ln}: malformed condition')
  s=intv(f[1],'condition size');c=intv(f[2],'condition count',False);m=intv(f[3],'multiplier')
  if s<=prev or not (mn<=s<=5):die(f'{path}:{ln}: invalid condition order/range')
  prev=s;conds[s]=c;mult[s]=m
 if len(rows['weight'])!=g['n']:die(f'{path}: wrong weight count')
 w=[0]*(g['n']+1)
 for expected,(ln,f) in enumerate(rows['weight'],1):
  if len(f)!=3 or intv(f[1],'weight vertex')!=expected:die(f'{path}:{ln}: weight order mismatch')
  w[expected]=intv(f[2],'weight',False)
 if sum(w)+sum(mult[s]*conds[s] for s in conds)!=rhs:die(f'{path}: RHS arithmetic mismatch')
 for s in range(mn,6):
  mu=mult.get(s,0)
  for C in S[s]:
   if sum(w[v] for v in C)+mu<D:die(f'{path}: violated stable-column inequality size {s} set {C}')
 if rhs//D!=bound:die(f'{path}: floor bound mismatch')
 return LayeredConclusion(expected_id,mn,bound,tuple(sorted(conds.items())),D,rhs)

def verify_residual_rational(path,g,S,expected_id,expected_top):
 props={};rows={'fixed_top_set':[],'weight':[]};weight_started=False
 for ln,line in enumerate(path.read_text('utf-8').splitlines(),1):
  z=line.strip()
  if not z or z.startswith('#'):continue
  if z.startswith('fixed_top_set\t'):
   if weight_started:die(f'{path}:{ln}: top row after weights')
   rows['fixed_top_set'].append((ln,z.split('\t')));continue
  if z.startswith('weight\t'):
   weight_started=True;rows['weight'].append((ln,z.split('\t')));continue
  if weight_started:die(f'{path}:{ln}: property after weights')
  if '=' not in z:die(f'{path}:{ln}: expected key=value')
  k,v=map(str.strip,z.split('=',1))
  if not k or k in props:die(f'{path}:{ln}: duplicate/empty key')
  props[k]=v
 required={'schema','certificate_id','graph_raw_sha256','graph_canonical_sha256','vertices','stable_set_size','fixed_top_set_count','denominator','rhs_numerator','claimed_bound','required_residual_sets','slack_budget','purpose'}
 if set(props)!=required:die(f'{path}: property keys mismatch')
 if props['schema']!='dsjc2509_residual_k4_dual_v1' or props['certificate_id']!=expected_id:die(f'{path}: schema/id mismatch')
 if props['graph_raw_sha256']!=g['raw_hash'] or props['graph_canonical_sha256']!=g['canonical_hash']:die(f'{path}: graph hash mismatch')
 if intv(props['vertices'],'vertices')!=g['n'] or intv(props['stable_set_size'],'stable size')!=4:die(f'{path}: dimensions mismatch')
 if intv(props['fixed_top_set_count'],'top count')!=len(rows['fixed_top_set']):die(f'{path}: top count mismatch')
 tops=[]
 for ln,f in rows['fixed_top_set']:
  if len(f)!=3:die(f'{path}:{ln}: malformed top row')
  vv=f[2].split()
  if len(vv)!=5:die(f'{path}:{ln}: top row must contain five vertices')
  C=tuple(intv(x,'top vertex') for x in vv);tops.append((f[1],C))
 if [C for _,C in tops]!=[tuple(C) for C in expected_top]:die(f'{path}: fixed top mismatch')
 if len(set().union(*(set(C) for _,C in tops)))!=5*len(tops):die(f'{path}: top sets overlap')
 if any(C not in S[5] for _,C in tops):die(f'{path}: top is not a graph stable 5-set')
 if len(rows['weight'])!=g['n']:die(f'{path}: wrong weight count')
 w=[0]*(g['n']+1)
 for expected,(ln,f) in enumerate(rows['weight'],1):
  if len(f)!=3 or intv(f[1],'weight vertex')!=expected:die(f'{path}:{ln}: weight order mismatch')
  w[expected]=intv(f[2],'weight',False)
 D=intv(props['denominator'],'denominator',False);rhs=intv(props['rhs_numerator'],'rhs',False);bound=intv(props['claimed_bound'],'bound',False)
 required_sets=intv(props['required_residual_sets'],'required residual sets',False)
 slack=intv(props['slack_budget'],'slack budget')
 if D<=0 or sum(w)!=rhs or rhs//D!=bound:die(f'{path}: objective/floor mismatch')
 if required_sets<=0:die(f'{path}: required residual sets must be positive')
 if slack!=rhs-required_sets*D:die(f'{path}: residual slack mismatch')
 used=set().union(*(set(C) for _,C in tops))
 residual=[C for C in S[4] if not used.intersection(C)]
 for C in residual:
  if sum(w[v] for v in C)<D:die(f'{path}: violated residual K4 inequality {C}')
 return ResidualConclusion(expected_id,bound,required_sets,slack,D,rhs,len(residual),tuple(C for _,C in tops))

def model_spec(name,S,n):
 B=n+1;x1,x2,x3=S[5]
 specs={
  'quad_x2':([x2],{}, {4:1},38),
  'env_x2':([x2],{4:37},{4:B,3:1},37*B+30),
  'env_x3':([x3],{4:37},{4:B,3:1},37*B+29),
  'env_x1x2':([x1,x2],{4:34},{4:B,3:1},34*B+32),
  'pair_H1C':([x2],{4:37,3:29},{4:B*B,3:B,2:1},37*B*B+29*B+5),
  'pair_H2F':([x1,x2],{4:34,3:31},{4:B*B,3:B,2:1},34*B*B+31*B+5),
 }
 tops,caps,scores,target=specs[name];used=set().union(*map(set,tops));verts=[v for v in range(1,n+1) if v not in used]
 cols=[]
 for s in sorted(scores,reverse=True):
  for C in S[s]:
   if not used.intersection(C):cols.append((C,s,scores[s],sum(1<<v for v in C)))
 return {'name':name,'tops':tops,'caps':caps,'scores':scores,'target':target,'B':B,'verts':verts,'cols':cols}

def strict_object(pairs):
 d={}
 for k,v in pairs:
  if k in d:die(f'duplicate JSON key: {k}')
  d[k]=v
 return d

def reject_constant(value):die(f'non-finite JSON value: {value}')

def loads_proof_json(data,context):
 try:return json.loads(data,object_pairs_hook=strict_object,parse_constant=reject_constant)
 except ValueError:raise
 except Exception as e:die(f'{context}: invalid JSON: {e}')

def read_gzip_json(path,limit=500_000_000):
 out=bytearray()
 with gzip.open(path,'rb') as f:
  while True:
   b=f.read(1<<20)
   if not b:break
   out.extend(b)
   if len(out)>limit:die(f'{path}: decompressed proof too large')
 return loads_proof_json(out,path)

def verify_lpbb(path,S,n,expected_name):
 d=read_gzip_json(path)
 if set(d)!={'schema','status','model','columns','root','proof','statistics'}:die(f'{path}: top-level keys mismatch')
 if d['schema']!='dsjc2509_lpbb_proof_v1' or d['status']!='PROVED':die(f'{path}: schema/status mismatch')
 m=model_spec(expected_name,S,n);pm=d['model']
 if set(pm)!={'name','n','tops','caps','score_by_size','target','B','counts','five'}:die(f'{path}: model keys mismatch')
 norm=lambda z:{int(k):int(v) for k,v in z.items()}
 if pm['name']!=expected_name or pm['n']!=n or [tuple(x) for x in pm['tops']]!=m['tops'] or norm(pm['caps'])!=m['caps'] or norm(pm['score_by_size'])!=m['scores'] or pm['target']!=m['target'] or pm['B']!=m['B']:die(f'{path}: model specification mismatch')
 if norm(pm['counts'])!={k:len(S[k]) for k in (2,3,4,5)} or [tuple(x) for x in pm['five']]!=S[5]:die(f'{path}: census/five-set mismatch')
 cols=m['cols'];ifcols=[tuple(x) for x in d['columns']]
 if ifcols!=[c[0] for c in cols]:die(f'{path}: column list mismatch')
 proof=d['proof'];root=d['root'];stats=d['statistics']
 if not isinstance(proof,list) or type(root) is not int or not (0<=root<len(proof)) or not isinstance(stats,dict):die(f'{path}: invalid proof/root/statistics')
 for key in ('nodes','branches','leaves'):
  if type(stats.get(key)) is not int or stats[key]<0:die(f'{path}: invalid proof statistics')
 N=len(cols);all_active=(1<<N)-1
 incident={v:0 for v in m['verts']};size_masks={s:0 for s in m['scores']}
 for j,(C,s,sc,mask) in enumerate(cols):
  bit=1<<j;size_masks[s]|=bit
  for v in C:incident[v]|=bit
 conflict=[]
 for C,s,sc,mask in cols:
  z=0
  for v in C:z|=incident[v]
  conflict.append(z)
 seen=set();branch_count=leaf_count=matching_count=0
 def visit(i,active,caps,selected_score,used_mask):
  nonlocal branch_count,leaf_count,matching_count
  if i in seen:die(f'{path}: proof node reused/cyclic at {i}')
  if not (0<=i<len(proof)):die(f'{path}: child index out of range')
  seen.add(i);r=proof[i]
  if not isinstance(r,dict) or 'kind' not in r:die(f'{path}: malformed record {i}')
  if r['kind']=='branch':
   branch_count+=1
   if set(r)!={'kind','var','zero','one'}:die(f'{path}: branch keys mismatch')
   j=r['var']
   if type(j) is not int or not (0<=j<N) or not (active>>j)&1:die(f'{path}: branch variable invalid or inactive')
   zero,one=r['zero'],r['one']
   if type(zero) is not int or type(one) is not int or not (0<=zero<i) or not (0<=one<i):die(f'{path}: invalid strict-postorder child reference')
   visit(zero,active&~(1<<j),dict(caps),selected_score,used_mask)
   C,s,sc,mask=cols[j];caps1=dict(caps)
   if used_mask&mask:die(f'{path}: selected branch overlaps path')
   if s in caps1:
    if caps1[s]<=0:die(f'{path}: selected branch exceeds cap')
    caps1[s]-=1
   a1=active&~conflict[j]
   if s in caps1 and caps1[s]==0:a1&=~size_masks[s]
   visit(one,a1,caps1,selected_score+sc,used_mask|mask)
  elif r['kind']=='leaf':
   leaf_count+=1
   if set(r)!={'kind','denominator','vertex_weights','cap_weights','numerator','selected_score','repairs'}:die(f'{path}: leaf keys mismatch')
   D=r['denominator']
   if type(D) is not int or D<=0 or type(r['selected_score']) is not int or r['selected_score']!=selected_score:die(f'{path}: leaf denominator/score mismatch')
   w={};prev=0
   for item in r['vertex_weights']:
    if not (isinstance(item,list) and len(item)==2):die(f'{path}: malformed vertex weight')
    v,x=item
    if type(v) is not int or type(x) is not int or v<=prev or v not in incident or x<=0:die(f'{path}: invalid vertex weight')
    prev=v;w[v]=x
   lam={};prev=10**9
   for item in r['cap_weights']:
    if not (isinstance(item,list) and len(item)==2):die(f'{path}: malformed cap weight')
    s,x=item
    if type(s) is not int or type(x) is not int or s>=prev or s not in caps or x<=0:die(f'{path}: invalid cap weight')
    prev=s;lam[s]=x
   num=sum(w.values())+sum(caps[s]*lam.get(s,0) for s in caps)
   if type(r['numerator']) is not int or r['numerator']!=num or type(r['repairs']) is not int or r['repairs']<0:die(f'{path}: leaf arithmetic/metadata mismatch')
   a=active
   while a:
    b=a&-a;j=b.bit_length()-1;a^=b;C,s,sc,mask=cols[j]
    if sum(w.get(v,0) for v in C)+lam.get(s,0)<sc*D:die(f'{path}: invalid dual at leaf {i}, column {j}')
   if selected_score*D+num>=m['target']*D:die(f'{path}: leaf does not close target')
  elif r['kind']=='matching_leaf':
   die(f'{path}: matching_leaf records are unsupported by this independent checker')
  else:die(f'{path}: unknown proof record kind')
 visit(root,all_active,dict(m['caps']),0,0)
 if len(seen)!=len(proof):die(f'{path}: unreachable proof records')
 if stats.get('nodes')!=len(proof) or stats.get('branches')!=branch_count or stats.get('leaves')!=leaf_count:die(f'{path}: statistics mismatch')
 return LPBBConclusion(expected_name,len(proof),leaf_count,branch_count,matching_count,
                       tuple(m['tops']),tuple(sorted(m['caps'].items())),
                       tuple(sorted(m['scores'].items())),m['target'])

def verify_coloring(path,g,adj):
 colors={}
 for ln,line in enumerate(path.read_text('utf-8').splitlines(),1):
  s=line.strip()
  if not s or s.startswith('c'):continue
  f=s.split()
  if len(f)!=2:die(f'{path}:{ln}: malformed coloring row')
  v,c=map(int,f)
  if not (1<=v<=g['n'] and c>=1) or v in colors:die(f'{path}:{ln}: invalid/duplicate vertex')
  colors[v]=c
 if set(colors)!=set(range(1,g['n']+1)):die(f'{path}: coloring does not assign every vertex exactly once')
 classes={}
 for v,c in colors.items():classes.setdefault(c,[]).append(v)
 if set(classes)!=set(range(1,max(classes)+1)):die(f'{path}: color labels have gaps')
 for c,C in classes.items():
  if not stable(C,adj):die(f'{path}: color {c} is not stable')
 actual=sum(colors.values());sizes=sorted((len(C) for C in classes.values()),reverse=True);canonical=sum((i+1)*s for i,s in enumerate(sizes))
 h=[sizes.count(s) for s in range(1,6)]
 if max(sizes)>5 or actual!=8277 or canonical!=8277 or h!=[2,4,29,37,1] or len(sizes)!=73:die(f'{path}: coloring value/profile mismatch')
 return {'value':actual,'classes':len(sizes),'h':h,'sizes':sizes}

def verify_witnesses(path,S,adj):
 d=loads_proof_json(path.read_bytes(),path)
 def classes(raw,role,size=None):
  if not isinstance(raw,list):die(f'{path}: {role}: classes must be a list')
  result=[]
  for C in raw:
   if not isinstance(C,list) or not C or (len(C)!=size if size is not None else len(C)>5):die(f'{path}: {role}: invalid class size or shape')
   if any(type(v) is not int or not 1<=v<=250 for v in C):die(f'{path}: {role}: vertex must be an integer in 1..250')
   if len(C)!=len(set(C)) or not stable(C,adj):die(f'{path}: {role}: duplicate vertex or unstable class')
   result.append(tuple(sorted(C)))
  return result
 def disjoint(allc,role,complete=False):
  flat=[v for C in allc for v in C]
  if len(flat)!=len(set(flat)):die(f'{path}: {role}: overlapping classes')
  if complete and sorted(flat)!=list(range(1,251)):die(f'{path}: {role}: incomplete partition')
 if not isinstance(d,dict) or set(d)!={'instance','n','counts','five_sets','envelope','pairmax','optimal_colouring'}:die(f'{path}: keys mismatch')
 if d['instance']!='DSJC250.9' or type(d['n']) is not int or d['n']!=250 or d['counts']!={f'S{k}':len(S[k]) for k in (2,3,4,5)} or classes(d['five_sets'],'five_sets',5)!=S[5]:die(f'{path}: graph metadata mismatch')
 x1,x2,x3=S[5];named_tops={'x2':[x2],'x3':[x3],'x1+x2':[x1,x2]}
 expected_env={'x2':(1,37,29),'x3':(1,37,28),'x1+x2':(2,34,31)}
 if not isinstance(d['envelope'],dict) or set(d['envelope'])!=set(expected_env):die(f'{path}: envelope roles mismatch')
 for name,(nt,nq,nt3) in expected_env.items():
  w=d['envelope'][name]
  if not isinstance(w,dict) or not {'tops','quads','triples','max_triples'}<=set(w):die(f'{path}: envelope {name}: missing witness fields')
  tops=classes(w['tops'],name+' tops',5);qs=classes(w['quads'],name+' quads',4);ts=classes(w['triples'],name+' triples',3)
  if sorted(tops)!=named_tops[name]:die(f'{path}: envelope {name}: named tops mismatch')
  if (len(tops),len(qs),len(ts))!=(nt,nq,nt3):die(f'{path}: envelope {name}: class counts mismatch')
  disjoint(tops+qs+ts,'envelope '+name)
  if type(w['max_triples']) is not int or w['max_triples']!=nt3:die(f'{path}: envelope witness metadata mismatch')
 if not isinstance(d['pairmax'],dict) or set(d['pairmax'])!={'H1-C','H2-F'}:die(f'{path}: pair witness roles mismatch')
 for name,expected_h in {'H1-C':[2,4,29,37,1],'H2-F':[3,4,31,34,2]}.items():
  w=d['pairmax'][name]
  if not isinstance(w,dict) or not {'classes','tops','max_pairs'}<=set(w):die(f'{path}: pair {name}: missing witness fields')
  cls=classes(w['classes'],'pair '+name);tops=classes(w['tops'],'pair '+name+' tops',5)
  expected_tops=named_tops['x2' if name=='H1-C' else 'x1+x2']
  if sorted(tops)!=expected_tops or sorted(C for C in cls if len(C)==5)!=expected_tops:die(f'{path}: pair {name}: named tops mismatch')
  disjoint(cls,'pair '+name,complete=True)
  h=[sum(len(C)==s for C in cls) for s in range(1,6)]
  if h!=expected_h or type(w['max_pairs']) is not int or w['max_pairs']!=4:die(f'{path}: pair witness profile mismatch {name}')
 # Descriptive solver fields and the duplicate optimal_colouring object are
 # historical metadata. They supply no premise to logical_chain; the separate
 # coloring file is checked by verify_coloring, and upper bounds by the proofs.
 return True

def enumerate_top_packings(tops):
 by_count={}
 def search(start,chosen,used):
  by_count.setdefault(len(chosen),[]).append(tuple(chosen))
  for i in range(start,len(tops)):
   C=tops[i]
   if not used.intersection(C):search(i+1,chosen+[C],used|set(C))
 search(0,[],set())
 return {k:tuple(v) for k,v in by_count.items()}

def make_profile(h):
 ge=[0]*len(h);running=0
 for s in range(len(h)-1,0,-1):running+=h[s];ge[s]=running
 objective=sum(ge[s]*(ge[s]+1)//2 for s in range(1,len(h)))
 return {'h':tuple(h),'ge':tuple(ge),'objective':objective}

def enumerate_profiles(vertices,maximum_size,top_packing_number,threshold):
 h=[0]*(maximum_size+1);fam=[]
 def search(size,remaining):
  if size==1:
   h[1]=remaining;p=make_profile(h)
   if p['objective']<=threshold:fam.append(p)
   return
  maximum=remaining//size
  if size==maximum_size:maximum=min(maximum,top_packing_number)
  for count in range(maximum+1):
   h[size]=count;search(size-1,remaining-size*count)
  h[size]=0
 search(maximum_size,vertices)
 fam.sort(key=lambda p:(p['objective'],p['h'][1:]))
 if len({p['h'] for p in fam})!=len(fam):die('profile enumeration produced a duplicate')
 return fam

def layered_rejects(conclusion,profile):
 applies=all(profile['h'][size]==count for size,count in conclusion.conditions)
 rejects=applies and profile['ge'][conclusion.minimum_size]>conclusion.bound
 return applies,rejects

def residual_rejects(conclusion,profile,packing):
 applies=packing==conclusion.tops and profile['h'][5]==len(packing)
 return applies,applies and profile['h'][4]>conclusion.bound

def lpbb_rejects(conclusion,profile,packing):
 applies=packing==conclusion.tops and profile['h'][5]==len(packing)
 if applies and any(profile['h'][size]>cap for size,cap in conclusion.caps):applies=False
 score=sum(profile['h'][size]*coefficient for size,coefficient in conclusion.score_by_size)
 return applies,applies and score>=conclusion.strict_target

def logical_chain(profiles,packings,layered,residual,lpbb):
 conclusions=layered+residual+lpbb
 audit={c.certificate_id:{'applicable':0,'rejected':0} for c in conclusions}
 layered_survivors=[]
 for profile in profiles:
  rejected=False
  for conclusion in layered:
   applies,closes=layered_rejects(conclusion,profile)
   audit[conclusion.certificate_id]['applicable']+=applies
   audit[conclusion.certificate_id]['rejected']+=closes
   rejected|=closes
  if not rejected:layered_survivors.append(profile)

 parent=tuple(residual)+tuple(c for c in lpbb if min(s for s,_ in c.score_by_size)>=4)
 final=tuple(c for c in lpbb if min(s for s,_ in c.score_by_size)<4)
 parent_survivors=[]
 for profile in layered_survivors:
  branches=[]
  for packing in packings.get(profile['h'][5],()):
   rejected=False
   for conclusion in parent:
    fn=residual_rejects if conclusion.kind=='residual' else lpbb_rejects
    applies,closes=fn(conclusion,profile,packing)
    audit[conclusion.certificate_id]['applicable']+=applies
    audit[conclusion.certificate_id]['rejected']+=closes
    rejected|=closes
   if not rejected:branches.append(packing)
  if branches:parent_survivors.append((profile,tuple(branches)))

 eliminated=[];unresolved=[]
 for profile,branches in parent_survivors:
  branch_reasons=[]
  for packing in branches:
   reasons=[]
   for conclusion in final:
    applies,closes=lpbb_rejects(conclusion,profile,packing)
    audit[conclusion.certificate_id]['applicable']+=applies
    audit[conclusion.certificate_id]['rejected']+=closes
    if closes:reasons.append(conclusion.certificate_id)
   if not reasons:unresolved.append((profile,packing))
   branch_reasons.append({'tops':[list(C) for C in packing],'certificates':reasons})
  eliminated.append({'h':list(profile['h'][1:]),'objective':profile['objective'],'branches':branch_reasons})

 unused=[name for name,counts in audit.items() if not counts['applicable'] or not counts['rejected']]
 if unused:die(f'mathematical proof incomplete: certificate conclusions unused or too weak: {unused}')
 if unresolved:
  profile,packing=unresolved[0]
  die(f"mathematical proof incomplete: {len(unresolved)} unresolved profile/top-packing branches; first h={profile['h'][1:]}, tops={packing}")
 return {'threshold_count':len(profiles),'layered_count':len(layered_survivors),
         'parent_count':len(parent_survivors),'profiles':eliminated,'application_audit':audit}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--json-out',type=Path);a=ap.parse_args();root=a.root.resolve();t0=time.time();result={}
 result['manifest_files']=verify_manifest(root)
 g=parse_graph(root/'data/DSJC250.9.col')
 if (g['n'],g['m'],g['raw_hash'],g['canonical_hash'])!=(EXPECTED_N,EXPECTED_M,EXPECTED_RAW,EXPECTED_CANON):die('graph identity mismatch')
 S,adj=enumerate_stable(g);counts={k:len(S[k]) for k in S}
 if counts!={2:3228,3:2869,4:205,5:3,6:0}:die(f'stable-set census mismatch {counts}')
 x1,x2,x3=S[5]
 if set(x1)&set(x2) or set(x1)&set(x3) or not (set(x2)&set(x3)):die('five-set intersection structure mismatch')
 result['graph']={'vertices':g['n'],'edges':g['m'],'raw_sha256':g['raw_hash'],'canonical_sha256':g['canonical_hash'],'stable_sets':counts,'five_sets':S[5]}
 result['coloring']=verify_coloring(root/'witnesses/DSJC250.9_sum8277.coloring',g,adj)
 verify_witnesses(root/'witnesses/witnesses.json',S,adj)
 layered=[];residual=[]
 layered.append(verify_layered_rational(root/'certificates/rational/ge4_global.rational',g,S,'ge4_global'))
 layered.append(verify_layered_rational(root/'certificates/rational/ge4_h5_eq_2.rational',g,S,'ge4_h5_eq_2'))
 residual.append(verify_residual_rational(root/'certificates/rational/dual_h5_1_forbid_x1.rational',g,S,'h5_1_forbid_x1',[x1]))
 residual.append(verify_residual_rational(root/'certificates/rational/dual_h5_1_x3_slack.rational',g,S,'h5_1_x3_slack',[x3]))
 residual.append(verify_residual_rational(root/'certificates/rational/dual_h5_2_forbid_x1_x3.rational',g,S,'h5_2_forbid_x1_x3',[x1,x3]))
 result['rational_conclusions']=[asdict(c) for c in layered+residual]
 lp={}
 for name in ('quad_x2','env_x2','env_x3','env_x1x2','pair_H1C','pair_H2F'):
  lp[name]=verify_lpbb(root/f'certificates/lpbb/{name}.proof.json.gz',S,g['n'],name)
 result['lpbb_proofs']={name:asdict(conclusion) for name,conclusion in lp.items()}
 packings=enumerate_top_packings(S[5]);maximum_top=max(packings)
 fam=enumerate_profiles(g['n'],5,maximum_top,8276)
 chain=logical_chain(fam,packings,layered,residual,list(lp.values()))
 result['profile_counts']={k:chain[k] for k in ('threshold_count','layered_count','parent_count')}
 result['conclusion_application_audit']=chain['application_audit']
 result['profiles']=chain['profiles']
 result['verdict']='OPTIMUM 8277 CERTIFIED'
 result['elapsed_seconds']=time.time()-t0
 text=json.dumps(result,indent=2,sort_keys=True)+'\n'
 if a.json_out:a.json_out.write_text(text,'utf-8')
 print(text,end='')
 print('VERIFIED: DSJC250.9 minimum sum coloring value is exactly 8277.',file=sys.stderr)
 return 0
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as e:
  print(f'VERIFICATION FAILED: {e}',file=sys.stderr);raise SystemExit(1)
