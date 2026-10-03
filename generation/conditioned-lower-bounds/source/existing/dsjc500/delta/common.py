from __future__ import annotations
from pathlib import Path
from itertools import combinations
import hashlib

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20), b''):
            h.update(chunk)
    return h.hexdigest()

def parse_dimacs(path: Path):
    raw=path.read_bytes(); n=declared=None; edges=set(); records=0; header_seen=False
    for lineno, rb in enumerate(raw.splitlines(),1):
        try: line=rb.decode('ascii').strip()
        except UnicodeDecodeError as e: raise ValueError(f'{path}:{lineno}: non-ASCII') from e
        if not line: continue
        f=line.split()
        tag=f[0]
        if tag=='c': continue
        if tag=='p':
            if header_seen or len(f)!=4 or f[1] not in {'edge','edges','col'}:
                raise ValueError(f'{path}:{lineno}: malformed/duplicate header')
            n=int(f[2]); declared=int(f[3]); header_seen=True
            if n<=0 or declared<0: raise ValueError(f'{path}:{lineno}: invalid header values')
        elif tag=='e':
            if not header_seen or len(f)!=3: raise ValueError(f'{path}:{lineno}: malformed edge')
            a,b=map(int,f[1:]); records += 1
            if not (1<=a<=n and 1<=b<=n) or a==b: raise ValueError(f'{path}:{lineno}: invalid edge')
            e=(a,b) if a<b else (b,a)
            if e in edges: raise ValueError(f'{path}:{lineno}: duplicate edge {e}')
            edges.add(e)
        else: raise ValueError(f'{path}:{lineno}: unknown record {tag!r}')
    if not header_seen: raise ValueError('missing header')
    adj=[0]*(n+1)
    for a,b in edges:
        adj[a] |= 1<<b; adj[b] |= 1<<a
    canon=('exact_mscp_graph_v1\nvertices %d\n'%n + ''.join(f'{a} {b}\n' for a,b in sorted(edges))).encode()
    return {
        'n':n,'declared':declared,'records':records,'edges':edges,'adj':adj,
        'raw_sha256':sha256_bytes(raw),'canonical_sha256':sha256_bytes(canon),
    }

def parse_coloring(path: Path, n: int):
    raw=path.read_bytes(); assign={}
    for lineno, rb in enumerate(raw.splitlines(),1):
        try: line=rb.decode('ascii').strip()
        except UnicodeDecodeError as e: raise ValueError(f'{path}:{lineno}: non-ASCII') from e
        if not line or line.startswith('c'): continue
        f=line.split()
        if len(f)!=2: raise ValueError(f'{path}:{lineno}: malformed coloring row')
        v,c=map(int,f)
        if not (1<=v<=n) or c<=0 or v in assign: raise ValueError(f'{path}:{lineno}: invalid/duplicate assignment')
        assign[v]=c
    if set(assign)!=set(range(1,n+1)): raise ValueError('coloring does not assign exactly all vertices')
    return assign, sha256_bytes(raw)

def bit_vertices(mask: int):
    while mask:
        b=mask & -mask
        yield b.bit_length()-1
        mask ^= b

def enumerate_stable_sets(g, max_k=6):
    n=g['n']; adj=g['adj']; full=sum(1<<v for v in range(1,n+1))
    comp=[0]*(n+1); gt=[0]*(n+1)
    for v in range(1,n+1):
        comp[v]=full & ~adj[v] & ~(1<<v)
        gt[v]=comp[v] & ~((1<<(v+1))-1)
    out={k:[] for k in range(2,max_k+1)}
    def rec(prefix, cand, target):
        need=target-len(prefix)
        while cand.bit_count()>=need:
            b=cand & -cand; v=b.bit_length()-1; cand ^= b
            if need==1: out[target].append(prefix+(v,))
            else: rec(prefix+(v,), cand & gt[v], target)
    for k in range(2,max_k+1): rec((), full, k)
    return out

def enumerate_packings(sets):
    masks=[sum(1<<v for v in S) for S in sets]
    # conflict-aware branch order: keep canonical indices in solutions
    order=sorted(range(len(sets)), key=lambda i: -sum(bool(masks[i]&masks[j]) for j in range(len(sets))))
    best=0; sols=[]
    def dfs(pos,used,chosen):
        nonlocal best,sols
        if len(chosen)+len(order)-pos<best: return
        if pos==len(order):
            sol=tuple(sorted(chosen))
            if len(sol)>best: best=len(sol);sols=[sol]
            elif len(sol)==best: sols.append(sol)
            return
        i=order[pos]
        if not (used&masks[i]): dfs(pos+1,used|masks[i],chosen+[i])
        dfs(pos+1,used,chosen)
    dfs(0,0,[])
    return best, sorted(set(sols))

def stable_tuple_hash(rows):
    text=''.join(' '.join(map(str,row))+'\n' for row in rows)
    return sha256_bytes(text.encode())

def objective_from_sizes(sizes):
    return sum((i+1)*s for i,s in enumerate(sorted(sizes,reverse=True)))

def triangular(x): return x*(x+1)//2

def profile_objective(q,h1,h2,h3,h4,h5):
    ge=(q,q-h1,q-h1-h2,h4+h5,h5)
    return sum(triangular(x) for x in ge)
