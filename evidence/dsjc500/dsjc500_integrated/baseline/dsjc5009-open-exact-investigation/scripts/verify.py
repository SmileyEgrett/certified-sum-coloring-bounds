#!/usr/bin/env python3
"""Fail-closed exact verifier for the DSJC500.9 initial profile-reduction stage.

The verifier uses only the Python standard library and integer arithmetic.
It does not call HiGHS, SciPy, a SAT solver, or any optimizer.
"""
from __future__ import annotations
import argparse,gzip,hashlib,json,os,stat,sys,time
from pathlib import Path

EXPECTED_RAW='95276841dffcde7c04de2fc1ae8e43b6c7b84173b4a9646b1cc6b392a3bd7b39'
EXPECTED_CANON='69e7453e2a389197f67fe0e02cf661bc71132b4ea457a434b4726a4b7489b618'
EXPECTED_COLORING='3f948845ad75ea1ed742916229e6060cab99d6839b7a109af59825e496804760'
EXPECTED_N=500; EXPECTED_RECORDS=112437; EXPECTED_DECLARED=224874
EXPECTED_COUNTS={2:12313,3:19901,4:2428,5:23,6:0}
OLD_D=10**12
PROVED_OLD102=(1,3,5,6,7,8)

def die(s):raise ValueError(s)
def sha256_bytes(b):return hashlib.sha256(b).hexdigest()
def sha256_file(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()

def verify_manifest(root:Path):
 p=root/'MANIFEST.sha256'
 if not p.is_file():die('missing MANIFEST.sha256')
 entries={};prev=''
 for ln,line in enumerate(p.read_text('utf-8').splitlines(),1):
  if len(line)<67 or line[64:66]!='  ':die(f'MANIFEST.sha256:{ln}: malformed')
  h,rel=line[:64],line[66:]
  if len(h)!=64 or any(c not in '0123456789abcdef' for c in h):die(f'MANIFEST.sha256:{ln}: bad hash')
  q=Path(rel)
  if not rel or q.is_absolute() or '..' in q.parts or rel.startswith('./'):die(f'MANIFEST.sha256:{ln}: unsafe path')
  if rel<=prev or rel in entries:die('manifest paths not unique and strictly sorted')
  prev=rel;entries[rel]=h
 actual=[]
 for x in root.rglob('*'):
  if x.name=='MANIFEST.sha256':continue
  st=x.lstat()
  if stat.S_ISLNK(st.st_mode):die(f'symlink rejected: {x.relative_to(root)}')
  if x.is_file():actual.append(x.relative_to(root).as_posix())
 if sorted(actual)!=list(entries):die(f'manifest file-set mismatch missing={sorted(set(entries)-set(actual))} extra={sorted(set(actual)-set(entries))}')
 for rel,h in entries.items():
  if sha256_file(root/rel)!=h:die(f'manifest hash mismatch: {rel}')
 return len(entries)

def parse_graph(path:Path):
 raw=path.read_bytes();n=decl=None;records=0;edges=set();header=False
 for ln,rb in enumerate(raw.splitlines(),1):
  try:s=rb.decode('ascii').strip()
  except UnicodeDecodeError:die(f'{path}:{ln}: non-ASCII')
  if not s:continue
  f=s.split()
  if f[0]=='c':continue
  if f[0]=='p':
   if header or len(f)!=4 or f[1] not in ('edge','edges','col'):die(f'{path}:{ln}: malformed/duplicate header')
   try:n=int(f[2]);decl=int(f[3])
   except Exception:die(f'{path}:{ln}: noninteger header')
   if n<=0 or decl<0:die(f'{path}:{ln}: invalid header')
   header=True
  elif f[0]=='e':
   if not header or len(f)!=3:die(f'{path}:{ln}: malformed edge')
   try:a,b=map(int,f[1:])
   except Exception:die(f'{path}:{ln}: noninteger edge')
   if not (1<=a<=n and 1<=b<=n) or a==b:die(f'{path}:{ln}: invalid edge')
   e=(a,b) if a<b else (b,a);records+=1
   if e in edges:die(f'{path}:{ln}: duplicate unordered edge')
   edges.add(e)
  else:die(f'{path}:{ln}: unknown record')
 if not header:die('missing graph header')
 canon=('exact_mscp_graph_v1\nvertices %d\n'%n+''.join(f'{a} {b}\n' for a,b in sorted(edges))).encode()
 adj=[0]*(n+1)
 for a,b in edges:adj[a]|=1<<b;adj[b]|=1<<a
 return {'n':n,'declared':decl,'records':records,'edges':edges,'adj':adj,'raw':sha256_bytes(raw),'canon':sha256_bytes(canon)}

def enumerate_stable(g,max_k=6):
 n=g['n'];adj=g['adj'];full=sum(1<<v for v in range(1,n+1));gt=[0]*(n+1)
 for v in range(1,n+1):gt[v]=(full&~adj[v]&~(1<<v))&~((1<<(v+1))-1)
 out={k:[] for k in range(2,max_k+1)}
 def rec(prefix,cand,target):
  need=target-len(prefix)
  while cand.bit_count()>=need:
   b=cand&-cand;v=b.bit_length()-1;cand^=b
   if need==1:out[target].append(prefix+(v,))
   else:rec(prefix+(v,),cand&gt[v],target)
 for k in range(2,max_k+1):rec((),full,k)
 return out

def tuple_hash(rows):return sha256_bytes(''.join(' '.join(map(str,r))+'\n' for r in rows).encode())
def mask(C):return sum(1<<v for v in C)

def enumerate_packings(sets):
 masks=[mask(C) for C in sets];order=sorted(range(len(sets)),key=lambda i:-sum(bool(masks[i]&masks[j]) for j in range(len(sets))))
 best=0;sols=[]
 def dfs(pos,used,chosen):
  nonlocal best,sols
  if len(chosen)+len(order)-pos<best:return
  if pos==len(order):
   z=tuple(sorted(chosen))
   if len(z)>best:best=len(z);sols=[z]
   elif len(z)==best:sols.append(z)
   return
  i=order[pos]
  if not used&masks[i]:dfs(pos+1,used|masks[i],chosen+[i])
  dfs(pos+1,used,chosen)
 dfs(0,0,[])
 return best,sorted(set(sols))

def verify_coloring(path,g,S,packs):
 if sha256_file(path)!=EXPECTED_COLORING:die('coloring raw hash mismatch')
 a={}
 for ln,line in enumerate(path.read_text('utf-8').splitlines(),1):
  s=line.strip()
  if not s or s.startswith('c'):continue
  f=s.split()
  if len(f)!=2:die(f'{path}:{ln}: malformed row')
  try:v,c=map(int,f)
  except Exception:die(f'{path}:{ln}: noninteger row')
  if not (1<=v<=g['n'] and c>0) or v in a:die(f'{path}:{ln}: invalid/duplicate assignment')
  a[v]=c
 if set(a)!=set(range(1,g['n']+1)):die('coloring vertex set mismatch')
 classes={}
 for v,c in a.items():classes.setdefault(c,[]).append(v)
 if set(classes)!=set(range(1,max(classes)+1)):die('color labels are not contiguous')
 for c,C in classes.items():
  for i,u in enumerate(C):
   for v in C[i+1:]:
    if (g['adj'][u]>>v)&1:die(f'color {c} contains graph edge {u}-{v}')
 sizes=sorted((len(C) for C in classes.values()),reverse=True);canonical=sum((i+1)*s for i,s in enumerate(sizes));actual=sum(a.values());h=[sizes.count(k) for k in range(1,6)]
 if len(classes)!=128 or max(sizes)!=5 or h!=[3,4,10,96,15] or canonical!=29848 or actual!=29848:die('incumbent profile/value mismatch')
 s5_index={C:i for i,C in enumerate(S[5])};five=tuple(sorted(s5_index[tuple(sorted(C))] for C in classes.values() if len(C)==5))
 if five not in packs:die('incumbent five-classes are not a reconstructed maximum packing')
 return {'classes':128,'profile':h,'canonical_sum':canonical,'packing_number':packs.index(five)+1}

def parse_old_dual(path,residual):
 w={};last=0
 for ln,line in enumerate(path.read_text('utf-8').splitlines(),1):
  f=line.split()
  if len(f)!=2:die(f'{path}:{ln}: malformed')
  try:v,x=map(int,f)
  except Exception:die(f'{path}:{ln}: noninteger')
  if v<=last or v not in residual or x<0:die(f'{path}:{ln}: invalid vertex/order/weight')
  last=v;w[v]=x
 if set(w)!=set(residual):die(f'{path}: residual vertex set mismatch')
 return w

def packing_data(pi,S,packs):
 p=packs[pi-1];top=[S[5][i] for i in p];removed=set().union(*(set(C) for C in top));residual=sorted(set(range(1,501))-removed);q=[C for C in S[4] if set(C).isdisjoint(removed)];t=[C for C in S[3] if set(C).isdisjoint(removed)]
 return p,top,removed,residual,q,t

def verify_old_duals(root,g,S,packs):
 out={}
 for pi in range(1,9):
  p,top,removed,residual,q,t=packing_data(pi,S,packs);path=root/f'certificates/old_k4_duals/k4dual_P{pi}.txt';w=parse_old_dual(path,residual)
  mn=min(sum(w[v] for v in C) for C in q)
  if mn<OLD_D:die(f'P{pi}: old k4 dual violates a residual quad')
  total=sum(w.values());bound=total//OLD_D;slack=total%OLD_D
  expected=101 if pi in (2,4) else 102
  if bound!=expected:die(f'P{pi}: unexpected old dual bound')
  out[pi]={'weights':w,'sha256':sha256_file(path),'total':total,'bound':bound,'slack':slack,'residual':residual,'quads':q,'triples':t,'top':top,'packing':p,'minimum_column':mn}
 return out

def require_int(x,ctx,nonnegative=False):
 if type(x) is not int:die(f'{ctx}: expected integer')
 if nonnegative and x<0:die(f'{ctx}: negative integer')
 return x

def verify_lpbb(path,pi,g,S,packs,old):
 try:
  with gzip.open(path,'rt',encoding='utf-8') as f:d=json.load(f)
 except Exception as e:die(f'{path}: unreadable certificate: {e}')
 required={'schema','graph_raw_sha256','graph_canonical_sha256','vertices','packing_number','packing_indices','packing_sets','stable4_family_sha256','residual4_family_sha256','old_dual_sha256','old_dual_denominator','old_dual_total','old_bound','slack_budget','allowed_column_count','allowed_columns_sha256','claimed_new_bound','leaf_denominator','root','records','statistics','generator_note'}
 if set(d)!=required:die(f'{path}: top-level keys mismatch')
 if d['schema']!='dsjc5009_residual_k4_lpbb_v1' or d['graph_raw_sha256']!=g['raw'] or d['graph_canonical_sha256']!=g['canon'] or d['vertices']!=500 or d['packing_number']!=pi:die(f'{path}: identity mismatch')
 o=old[pi];p=o['packing'];top=o['top'];allq=o['quads'];w0=o['weights']
 if d['packing_indices']!=list(p) or d['packing_sets']!=[list(C) for C in top]:die(f'{path}: conditioning top mismatch')
 if d['stable4_family_sha256']!=tuple_hash(S[4]) or d['residual4_family_sha256']!=tuple_hash(allq):die(f'{path}: stable family hash mismatch')
 if d['old_dual_sha256']!=o['sha256'] or d['old_dual_denominator']!=OLD_D or d['old_dual_total']!=o['total'] or d['old_bound']!=o['bound'] or d['slack_budget']!=o['slack']:die(f'{path}: old-dual binding mismatch')
 if d['old_bound']!=102 or d['claimed_new_bound']!=101:die(f'{path}: unsupported conclusion')
 excess=[sum(w0[v] for v in C)-OLD_D for C in allq]
 keep=[i for i,e in enumerate(excess) if e<=o['slack']];cols=[allq[i] for i in keep];qe=[excess[i] for i in keep]
 if d['allowed_column_count']!=len(cols) or d['allowed_columns_sha256']!=tuple_hash(cols):die(f'{path}: allowed-column binding mismatch')
 Q=require_int(d['leaf_denominator'],'leaf denominator',True)
 if Q<=0:die(f'{path}: zero denominator')
 n=len(cols);full=(1<<n)-1;inc=[0]*501
 for j,C in enumerate(cols):
  for v in C:inc[v]|=1<<j
 conflict=[]
 for C in cols:
  z=0
  for v in C:z|=inc[v]
  conflict.append(z)
 rec=d['records'];root_i=require_int(d['root'],'root')
 if not isinstance(rec,list) or not (0<=root_i<len(rec)):die(f'{path}: malformed records/root')
 seen=set();stats={'branches':0,'dual_leaves':0,'count_leaves':0,'budget_leaves':0};maxdepth=0
 def visit(i,active,selected,spent,depth):
  nonlocal maxdepth
  maxdepth=max(maxdepth,depth)
  if i in seen or not (0<=i<len(rec)):die(f'{path}: reused/cyclic/out-of-range node {i}')
  seen.add(i);r=rec[i]
  if not isinstance(r,dict) or 'kind' not in r:die(f'{path}: malformed node {i}')
  if r['kind']=='budget':
   if set(r)!={'kind','selected','spent'} or r['selected']!=selected or r['spent']!=spent or spent<=o['slack']:die(f'{path}: invalid budget leaf {i}')
   stats['budget_leaves']+=1;return
  if spent>o['slack']:die(f'{path}: non-budget node beyond budget')
  R=o['slack']-spent;need=o['bound']-selected
  if need<=0:die(f'{path}: path reaches forbidden target')
  # Same exact individual-budget filtering used by the generator.
  filtered=0;x=active
  while x:
   b=x&-x;j=b.bit_length()-1;x^=b
   if qe[j]<=R:filtered|=b
  active=filtered
  if r['kind']=='count':
   if set(r)!={'kind','selected','remaining_target','remaining_budget','active_count'} or r['selected']!=selected or r['remaining_target']!=need or r['remaining_budget']!=R or r['active_count']!=active.bit_count() or active.bit_count()>=need:die(f'{path}: invalid count leaf {i}')
   stats['count_leaves']+=1;return
  if r['kind']=='dual':
   keys={'kind','selected','remaining_target','remaining_budget','denominator','budget_multiplier','vertex_weights','numerator','repairs'}
   if set(r)!=keys or r['selected']!=selected or r['remaining_target']!=need or r['remaining_budget']!=R or r['denominator']!=Q:die(f'{path}: dual metadata mismatch at {i}')
   M=require_int(r['budget_multiplier'],'budget multiplier',True);W={};last=0
   for item in r['vertex_weights']:
    if not (isinstance(item,list) and len(item)==2):die(f'{path}: malformed weight at {i}')
    v,x=item
    if type(v) is not int or type(x) is not int or v<=last or v not in o['residual'] or x<=0:die(f'{path}: invalid weight at {i}')
    last=v;W[v]=x
   num=OLD_D*sum(W.values())+R*M
   if r['numerator']!=num or require_int(r['repairs'],'repairs',True)<0:die(f'{path}: dual arithmetic mismatch at {i}')
   a=active
   while a:
    b=a&-a;j=b.bit_length()-1;a^=b
    if OLD_D*sum(W.get(v,0) for v in cols[j])+qe[j]*M<OLD_D*Q:die(f'{path}: invalid leaf inequality at node {i}, column {j}')
   if num>=need*OLD_D*Q:die(f'{path}: leaf does not close target at {i}')
   stats['dual_leaves']+=1;return
  if r['kind']=='branch':
   if set(r)!={'kind','column','one','zero'}:die(f'{path}: branch keys mismatch at {i}')
   j=require_int(r['column'],'branch column');one=require_int(r['one'],'one child');zero=require_int(r['zero'],'zero child')
   if not (active>>j)&1 or one>=i or zero>=i:die(f'{path}: inactive branch or non-postorder child at {i}')
   visit(one,active&~conflict[j],selected+1,spent+qe[j],depth+1)
   visit(zero,active&~(1<<j),selected,spent,depth+1)
   stats['branches']+=1;return
  die(f'{path}: unknown node kind')
 visit(root_i,full,0,0,0)
 if len(seen)!=len(rec):die(f'{path}: unreachable records')
 meta=d['statistics']
 for k in ('branches','dual_leaves','count_leaves','budget_leaves'):
  if meta.get(k)!=stats[k]:die(f'{path}: statistics mismatch {k}')
 if meta.get('records')!=len(rec) or meta.get('calls')!=len(rec) or meta.get('max_depth')!=maxdepth:die(f'{path}: record/depth statistics mismatch')
 return {'bound':101,'records':len(rec),'leaves':stats['dual_leaves']+stats['count_leaves']+stats['budget_leaves'],'max_depth':maxdepth}

def verify_farkas(path,pi,g,S,packs,old):
 try:d=json.loads(path.read_text('utf-8'))
 except Exception as e:die(f'{path}: unreadable: {e}')
 keys={'schema','graph_raw_sha256','graph_canonical_sha256','vertices','packing_number','packing_indices','packing_sets','residual_vertices','residual4_family_sha256','residual3_family_sha256','quad_quota','triple_quota','vertex_weights','quad_multiplier','triple_multiplier','rhs','minimum_quad_column','minimum_triple_column','source_rounding_denominator','meaning'}
 if set(d)!=keys:die(f'{path}: keys mismatch')
 if d['schema']!='dsjc5009_exact_cover_farkas_v1' or d['graph_raw_sha256']!=g['raw'] or d['graph_canonical_sha256']!=g['canon'] or d['vertices']!=500 or d['packing_number']!=pi:die(f'{path}: identity mismatch')
 o=old[pi]
 if d['packing_indices']!=list(o['packing']) or d['packing_sets']!=[list(C) for C in o['top']] or d['residual_vertices']!=o['residual']:die(f'{path}: conditioning mismatch')
 if d['residual4_family_sha256']!=tuple_hash(o['quads']) or d['residual3_family_sha256']!=tuple_hash(o['triples']):die(f'{path}: family hash mismatch')
 h4=require_int(d['quad_quota'],'quad quota',True);h3=require_int(d['triple_quota'],'triple quota',True)
 if (h4,h3)!=(101,7):die(f'{path}: certificate conclusion is not the consumed profile')
 W={};last=0
 for item in d['vertex_weights']:
  if not (isinstance(item,list) and len(item)==2):die(f'{path}: malformed vertex weight')
  v,x=item
  if type(v) is not int or type(x) is not int or v<=last or v not in o['residual'] or x==0:die(f'{path}: invalid vertex weight')
  last=v;W[v]=x
 m4=require_int(d['quad_multiplier'],'quad multiplier');m3=require_int(d['triple_multiplier'],'triple multiplier')
 min4=min(sum(W.get(v,0) for v in C)+m4 for C in o['quads']);min3=min(sum(W.get(v,0) for v in C)+m3 for C in o['triples'])
 if min4<0 or min3<0 or d['minimum_quad_column']!=min4 or d['minimum_triple_column']!=min3:die(f'{path}: a Farkas column is negative')
 rhs=sum(W.values())+h4*m4+h3*m3
 if d['rhs']!=rhs or rhs>=0:die(f'{path}: Farkas RHS is not exactly negative')
 require_int(d['source_rounding_denominator'],'source denominator',True)
 return {'quad_quota':h4,'triple_quota':h3,'rhs':rhs,'min_quad':min4,'min_triple':min3}

def verify_profile_farkas(path,pi,g,S,packs,old):
 try:d=json.loads(path.read_text('utf-8'))
 except Exception as e:die(f'{path}: unreadable: {e}')
 keys={'schema','graph_raw_sha256','graph_canonical_sha256','vertices','packing_number','packing_indices','packing_sets','residual_vertices','family_sha256','quota','vertex_weights','size_multipliers','rhs','minimum_columns','source_rounding_denominator','repairs','generation_seconds'}
 if set(d)!=keys:die(f'{path}: keys mismatch')
 if d['schema']!='dsjc5009_profile_farkas_v1' or d['graph_raw_sha256']!=g['raw'] or d['graph_canonical_sha256']!=g['canon'] or d['vertices']!=500 or d['packing_number']!=pi:die(f'{path}: identity mismatch')
 o=old[pi]
 if d['packing_indices']!=list(o['packing']) or d['packing_sets']!=[list(C) for C in o['top']] or d['residual_vertices']!=o['residual']:die(f'{path}: conditioning mismatch')
 fam={1:[(v,) for v in o['residual']],2:[C for C in S[2] if set(C).isdisjoint(set().union(*(set(X) for X in o['top'])))],3:o['triples'],4:o['quads']}
 if d['family_sha256']!={str(k):tuple_hash(fam[k]) for k in range(1,5)}:die(f'{path}: family hash mismatch')
 if set(d['quota'])!={str(k) for k in range(1,5)} or set(d['size_multipliers'])!={str(k) for k in range(1,5)} or set(d['minimum_columns'])!={str(k) for k in range(1,5)}:die(f'{path}: size-key mismatch')
 quota={k:require_int(d['quota'][str(k)],f'quota {k}',True) for k in range(1,5)}
 if sum(quota.values())+15!=124 or sum(k*quota[k] for k in range(1,5))!=425:die(f'{path}: quota is not a residual partition profile')
 W={};last=0
 for item in d['vertex_weights']:
  if not (isinstance(item,list) and len(item)==2):die(f'{path}: malformed vertex weight')
  v,x=item
  if type(v) is not int or type(x) is not int or v<=last or v not in o['residual'] or x==0:die(f'{path}: invalid vertex weight')
  last=v;W[v]=x
 mult={k:require_int(d['size_multipliers'][str(k)],f'multiplier {k}') for k in range(1,5)}
 minima={k:min(sum(W.get(v,0) for v in C)+mult[k] for C in fam[k]) for k in range(1,5)}
 if any(minima[k]<0 for k in minima) or d['minimum_columns']!={str(k):minima[k] for k in range(1,5)}:die(f'{path}: negative or mismatched Farkas column')
 rhs=sum(W.values())+sum(quota[k]*mult[k] for k in range(1,5))
 if d['rhs']!=rhs or rhs>=0:die(f'{path}: nonnegative/mismatched Farkas RHS')
 require_int(d['source_rounding_denominator'],'source denominator',True);require_int(d['repairs'],'repairs',True)
 if not isinstance(d['generation_seconds'],(int,float)) or d['generation_seconds']<0:die(f'{path}: invalid generation metadata')
 return {'quota':tuple(quota[k] for k in range(1,5)),'rhs':rhs,'minima':minima}

def T(x):return x*(x+1)//2
def profile_value(q,h1,h2,h3,h4,h5):
 g=(q,q-h1,q-h1-h2,h4+h5,h5)
 val=sum(T(x) for x in g)
 sizes=[5]*h5+[4]*h4+[3]*h3+[2]*h2+[1]*h1
 if len(sizes)!=q or sum(sizes)!=500:die('internal profile equation error')
 direct=sum((i+1)*s for i,s in enumerate(sizes))
 if val!=direct:die('GE/direct objective disagreement')
 return val

def enumerate_threshold_profiles(limit,max_h5):
 qmin=(500+5-1)//5;qmax=0
 while T(qmax+1)<=limit:qmax+=1
 rows=[]
 # Enumerate Ferrers column heights g5<=g4<=g3<=g2<=g1,
 # sum(g)=500. For fixed g3,g4,g5, the remaining g2 interval is
 # monotone toward balance, so a binary search finds all threshold points.
 for g5 in range(max_h5+1):
  for g4 in range(g5,126):
   for g3 in range(g4,167):
    R=500-g3-g4-g5
    lo=g3;hi=R//2
    if lo>hi:continue
    fixed=T(g3)+T(g4)+T(g5)
    def value(g2):
     g1=R-g2
     return T(g1)+T(g2)+fixed
    if value(hi)>limit:continue
    a,b=lo,hi
    while a<b:
     m=(a+b)//2
     if value(m)<=limit:b=m
     else:a=m+1
    for g2 in range(a,hi+1):
     g1=R-g2
     h1=g1-g2;h2=g2-g3;h3=g3-g4;h4=g4-g5;h5=g5;q=g1
     val=value(g2)
     # Independent direct canonical-sum check on every retained profile.
     sizes=[5]*h5+[4]*h4+[3]*h3+[2]*h2+[1]*h1
     if len(sizes)!=q or sum(sizes)!=500 or sum((i+1)*z for i,z in enumerate(sizes))!=val:die('internal profile equation error')
     rows.append((val,q,h1,h2,h3,h4,h5))
 return sorted(rows),qmin,qmax

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--json-out',type=Path);a=ap.parse_args();root=a.root.resolve();t0=time.perf_counter();out={}
 out['manifest_files']=verify_manifest(root)
 g=parse_graph(root/'data/DSJC500.9.col')
 if (g['n'],g['records'],g['declared'],g['raw'],g['canon'])!=(EXPECTED_N,EXPECTED_RECORDS,EXPECTED_DECLARED,EXPECTED_RAW,EXPECTED_CANON):die('graph identity/header mismatch')
 if g['declared']!=2*g['records'] or len(g['edges'])!=g['records']:die('unexpected DIMACS header convention')
 S=enumerate_stable(g,6);counts={k:len(S[k]) for k in S}
 if counts!=EXPECTED_COUNTS:die(f'stable-set census mismatch: {counts}')
 best,packs=enumerate_packings(S[5])
 if best!=15 or len(packs)!=8:die(f'five-set packing mismatch: best={best}, count={len(packs)}')
 forced=set.intersection(*(set(p) for p in packs));covered=[set().union(*(set(S[5][i]) for i in p)) for p in packs]
 if len(forced)!=12 or len(set.intersection(*covered))!=66 or len(set.union(*covered))!=84:die('maximum-packing structure mismatch')
 out['graph']={'vertices':500,'edge_records':g['records'],'header_edge_count':g['declared'],'raw_sha256':g['raw'],'canonical_sha256':g['canon'],'stable_sets':counts,'stable_family_sha256':{str(k):tuple_hash(S[k]) for k in S},'alpha':5,'maximum_five_set_packing':best,'maximum_packing_count':len(packs),'forced_five_sets':len(forced),'always_covered_vertices':len(set.intersection(*covered)),'ever_covered_vertices':len(set.union(*covered))}
 out['incumbent']=verify_coloring(root/'witnesses/DSJC500.9_sum29848.coloring',g,S,packs)
 old=verify_old_duals(root,g,S,packs);bounds={pi:old[pi]['bound'] for pi in range(1,9)};out['old_k4_bounds']={str(pi):{'bound':old[pi]['bound'],'total':old[pi]['total'],'slack':old[pi]['slack'],'residual_quads':len(old[pi]['quads']),'minimum_column':old[pi]['minimum_column']} for pi in range(1,9)}
 lpbb={}
 for pi in PROVED_OLD102:
  z=verify_lpbb(root/f'certificates/k4_lpbb/P{pi}.proof.json.gz',pi,g,S,packs,old);lpbb[str(pi)]=z;bounds[pi]=z['bound']
 if set(bounds.values())!={101}:die(f'universal residual four-set bound was not derived: {bounds}')
 out['new_k4_lpbb']=lpbb;out['derived_k4_bounds']={str(k):v for k,v in bounds.items()}
 farkas={}
 for pi in range(1,9):farkas[str(pi)]=verify_farkas(root/f'certificates/farkas/P{pi}.farkas.json',pi,g,S,packs,old)
 out['farkas_101_quads_7_triples']=farkas
 profile_farkas={}
 profile_specs=[(1,'P1_h1-1_h2-1_h3-6_h4-101.json'),(3,'P3_h1-1_h2-1_h3-6_h4-101.json'),(3,'P3_h1-0_h2-3_h3-5_h4-101.json')]
 for pi,name in profile_specs:
  z=verify_profile_farkas(root/f'certificates/profile_farkas/{name}',pi,g,S,packs,old);profile_farkas[(pi,z['quota'])]=z
 out['additional_profile_farkas']={f'P{pi}:{q}':z for (pi,q),z in profile_farkas.items()}
 profiles,qmin,qmax=enumerate_threshold_profiles(29847,best)
 if len(profiles)!=230 or {r[6] for r in profiles}!={15} or min(r[1] for r in profiles)!=122 or max(r[1] for r in profiles)!=132:die('global threshold profile census mismatch')
 by_packing={};unresolved=[];eliminated=[]
 for pi in range(1,9):
  admiss=[r for r in profiles if r[5]<=bounds[pi]]
  if len(admiss)!=160:die(f'P{pi}: expected 160 profiles after h4 bound, got {len(admiss)}')
  for r in admiss:
   val,q,h1,h2,h3,h4,h5=r
   if q<124:
    cert=farkas[str(pi)]
    if not (q==123 and h1==0 and h2==0 and h3==cert['triple_quota'] and h4==cert['quad_quota'] and h5==15):die(f'P{pi}: low-strength profile not bound to exact certificate: {r}')
    eliminated.append((pi,r,'q123_farkas'))
   elif (pi,(h1,h2,h3,h4)) in profile_farkas:
    eliminated.append((pi,r,'profile_farkas'))
   else:unresolved.append((pi,r))
  by_packing[str(pi)]={'after_k4_bound':len(admiss),'exactly_eliminated_total':sum(x[0]==pi for x in eliminated),'unresolved':sum(x[0]==pi for x in unresolved)}
 if len(eliminated)!=11 or len(unresolved)!=1269 or {r[1] for _,r in unresolved}!=set(range(124,133)) or min(r[0] for _,r in unresolved)!=29785:die('final profile-reduction arithmetic mismatch')
 out['profile_reduction']={'objective_threshold':29847,'graph_free_q_range_checked':[qmin,qmax],'arithmetic_profiles_after_h5_le_15':len(profiles),'derived_strength_range_before_k4':[min(r[1] for r in profiles),max(r[1] for r in profiles)],'profiles_per_packing_after_h4_le_101':160,'exactly_eliminated_cells':len(eliminated),'q123_farkas_cells':sum(x[2]=='q123_farkas' for x in eliminated),'additional_profile_farkas_cells':sum(x[2]=='profile_farkas' for x in eliminated),'unresolved_cells':len(unresolved),'unresolved_strengths':[124,132],'certified_chromatic_sum_lower_bound':29785,'incumbent_upper_bound':29848,'per_packing':by_packing,'conclusion':'Every coloring of canonical sum at most 29847, if one exists, has 124 through 132 classes and belongs to one of 1269 explicitly reconstructed packing/profile cells.'}
 out['verdict']='INITIAL PROFILE REDUCTION CERTIFIED; INTEGER OPTIMUM UNRESOLVED'
 out['verification_seconds']=time.perf_counter()-t0
 if a.json_out:a.json_out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
 print('DSJC500.9 INITIAL PROFILE REDUCTION CHECK PASSED')
 print('Incumbent: 29848 (proper, not proved optimal)')
 print('Certified chromatic-sum interval: 29785..29848')
 print('Certified: any <=29847 coloring has strength 124..132')
 print('Certified unresolved packing/profile cells: 1269')
 print('Verdict:',out['verdict'])
 print(f"Verification time: {out['verification_seconds']:.3f} s")

if __name__=='__main__':
 try:main()
 except Exception as e:
  print(f'VERIFICATION FAILED: {e}',file=sys.stderr);sys.exit(1)
