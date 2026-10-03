#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,hashlib,json,resource,time
from collections import Counter
from pathlib import Path

def sha256_file(p:Path)->str:
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()

def parse_graph(p:Path):
 raw=p.read_bytes(); n=mdecl=None; header=0; records=0; edges=set()
 for ln,b in enumerate(raw.splitlines(),1):
  s=b.decode('ascii').strip()
  if not s: continue
  f=s.split()
  if f[0]=='c': continue
  if f[0]=='p':
   if header or len(f)!=4 or f[1] not in ('edge','edges','col'): raise ValueError(f'line {ln}: bad header')
   n=int(f[2]); mdecl=int(f[3]); header=1
  elif f[0]=='e':
   if not header or len(f)!=3: raise ValueError(f'line {ln}: bad edge')
   u,v=map(int,f[1:]);
   if not(1<=u<=n and 1<=v<=n) or u==v: raise ValueError(f'line {ln}: bad endpoints')
   if u>v:u,v=v,u
   if (u,v) in edges: raise ValueError(f'line {ln}: duplicate edge')
   edges.add((u,v));records+=1
  else: raise ValueError(f'line {ln}: unknown record')
 if not header or records!=mdecl or len(edges)!=mdecl: raise ValueError('edge count mismatch')
 adj=[0]*(n+1); full=sum(1<<v for v in range(1,n+1))
 for u,v in edges: adj[u]|=1<<v;adj[v]|=1<<u
 comp=[0]*(n+1)
 for v in range(1,n+1): comp[v]=full & ~adj[v] & ~(1<<v)
 canon=('independent_graph_v1\n'+f'vertices {n}\n'+''.join(f'{u} {v}\n' for u,v in sorted(edges))).encode()
 return {'n':n,'m':len(edges),'edges':edges,'adj':adj,'comp':comp,'raw_sha256':hashlib.sha256(raw).hexdigest(),'canonical_sha256':hashlib.sha256(canon).hexdigest()}

def enumerate_stable(g,max_size=20):
 fam=[[] for _ in range(max_size+1)]; full=sum(1<<v for v in range(1,g['n']+1));nodes=1
 def rec(prefix,cand):
  nonlocal nodes
  rem=cand
  while rem:
   bit=rem&-rem;v=bit.bit_length()-1;rem^=bit
   child=prefix+(v,); nodes+=1; fam[len(child)].append(child)
   if len(child)<max_size: rec(child, rem & g['comp'][v])
 rec((),full)
 alpha=max(i for i,a in enumerate(fam) if a)
 if alpha==max_size: raise RuntimeError('maximum_size may truncate census')
 return fam[:alpha+1],nodes,alpha

def parse_coloring(p:Path,n:int):
 color={}
 for ln,line in enumerate(p.read_text().splitlines(),1):
  s=line.strip()
  if not s or s.startswith(('#','c')):continue
  f=s.split()
  if len(f)<2 or not f[0].isdigit() or not f[1].isdigit():continue
  v,c=map(int,f[:2])
  if v in color:raise ValueError(f'duplicate vertex {v}')
  color[v]=c
 if set(color)!=set(range(1,n+1)):raise ValueError('coverage failure')
 return color

def verify_coloring(g,color):
 conflicts=[]
 for u,v in g['edges']:
  if color[u]==color[v]: conflicts.append((u,v))
 sizes=Counter(color.values())
 sorted_sizes=sorted(sizes.values(),reverse=True)
 canonical=sum((i+1)*s for i,s in enumerate(sorted_sizes))
 h=Counter(sorted_sizes);alpha=max(sorted_sizes)
 ge=[sum(s>=t for s in sorted_sizes) for t in range(1,alpha+1)]
 conj=sum(x*(x+1)//2 for x in ge)
 direct=sum(color.values())
 return {'proper':not conflicts,'conflicts':conflicts[:10],'direct_label_sum':direct,'canonical_sum':canonical,'conjugate_sum':conj,'nonempty_classes':len(sorted_sizes),'class_sizes_desc':sorted_sizes,'h_by_size':[h.get(t,0) for t in range(1,alpha+1)],'g_ge':[sum(s>=t for s in sorted_sizes) for t in range(1,alpha+1)]}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--graph',type=Path,required=True);ap.add_argument('--coloring',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
 args.out.mkdir(parents=True,exist_ok=True); t0=time.perf_counter()
 g=parse_graph(args.graph); t1=time.perf_counter(); color=parse_coloring(args.coloring,g['n']); cv=verify_coloring(g,color);t2=time.perf_counter()
 fam,nodes,alpha=enumerate_stable(g,10);t3=time.perf_counter()
 counts=[len(fam[i]) for i in range(1,alpha+1)]
 hashes={}
 for size in range(1,alpha+1):
  path=args.out/f'stable_sets_size_{size}.tsv.gz'
  h=hashlib.sha256()
  with gzip.open(path,'wt',encoding='ascii',newline='') as z:
   z.write('id\tsize\tvertices\n')
   for i,S in enumerate(fam[size],1):
    line=f"{i}\t{size}\t{' '.join(map(str,S))}\n";z.write(line);h.update((' '.join(map(str,S))+'\n').encode())
  hashes[str(size)]={'count':len(fam[size]),'semantic_sha256':h.hexdigest(),'file':path.name,'file_sha256':sha256_file(path)}
 result={'schema':'dsjc1000_independent_reconstruction_v1','graph':{'input_name':args.graph.name,'raw_sha256':g['raw_sha256'],'canonical_sha256':g['canonical_sha256'],'vertices':g['n'],'declared_edges':g['m'],'unique_undirected_edges':g['m'],'parsing':'strict DIMACS: one p edge/edges/col header, 1-based vertices, unique undirected e records, no loops'},'coloring':{'input_name':args.coloring.name,'sha256':sha256_file(args.coloring),**cv},'stable_sets':{'alpha':alpha,'nonempty_total':sum(counts),'counts_by_size':counts,'enumeration_nodes':nodes,'families':hashes},'timing_seconds':{'graph_parse':t1-t0,'coloring_parse_verify':t2-t1,'stable_enumeration':t3-t2,'total_before_write':t3-t0},'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}
 (args.out/'reconstruction.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
