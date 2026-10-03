from pathlib import Path
import gzip,hashlib,math
TOPS=((52,54,175,319,501,704),(76,145,184,672,793,805),(129,150,181,321,456,762))
def sha256_file(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def load_sets(root,size):
 out=[]
 with gzip.open(Path(root)/f'stable_sets_size_{size}.tsv.gz','rt',encoding='ascii') as f:
  assert next(f).rstrip()=='id\tsize\tvertices'
  for i,line in enumerate(f,1):
   a,b,c=line.rstrip().split('\t');S=tuple(map(int,c.split()))
   assert int(a)==i and int(b)==size and len(S)==size
   out.append(S)
 return out
def gamma_num(B,D,k):
 q=B-k*D
 if q<=D:return 0
 r=(q-1)//D
 return r*B-D*(r*k+r*(r+1)//2)
def down(x,D):return math.floor(float(x)*D-1e-4)
def up(x,D):return math.ceil(float(x)*D+1e-4)
def graph_info(rec):
 g=rec['graph'];s=rec['stable_sets']
 return {'raw_sha256':g['raw_sha256'],'canonical_sha256':g['canonical_sha256'],'vertices':g['vertices'],'unique_edges':g['unique_undirected_edges'],'stable_counts':s['counts_by_size']}
