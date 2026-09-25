#!/usr/bin/env python3
"""Fail-closed verification of the exact artifact file set and hashes."""
from pathlib import Path
import argparse, hashlib, re, stat, sys
ROW=re.compile(r'^([0-9a-f]{64})  ([^\r\n]+)$')
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('root',type=Path,nargs='?',default=Path(__file__).resolve().parents[1]); a=ap.parse_args(); root=a.root.resolve(); mf=root/'MANIFEST.sha256'
    expected={}; previous=''
    for no,line in enumerate(mf.read_text('utf-8').splitlines(),1):
        m=ROW.fullmatch(line)
        if not m: raise ValueError(f'MANIFEST.sha256:{no}: malformed row')
        h,rel=m.groups()
        if rel.startswith('/') or '..' in Path(rel).parts or rel in expected or rel<=previous: raise ValueError(f'MANIFEST.sha256:{no}: unsafe, duplicate, or unsorted path')
        expected[rel]=h; previous=rel
    actual=set()
    for p in root.rglob('*'):
        rel=p.relative_to(root).as_posix(); st=p.lstat()
        if stat.S_ISLNK(st.st_mode): raise ValueError(f'symlink rejected: {rel}')
        if p.is_file() and rel!='MANIFEST.sha256': actual.add(rel)
    if actual!=set(expected): raise ValueError(f'file-set mismatch: missing={sorted(set(expected)-actual)}, unexpected={sorted(actual-set(expected))}')
    for rel,h in expected.items():
        if digest(root/rel)!=h: raise ValueError(f'hash mismatch: {rel}')
    print(f'MANIFEST VERIFIED: {len(expected)} files')
    return 0
if __name__=='__main__':
    try: raise SystemExit(main())
    except Exception as exc: print(f'MANIFEST VERIFICATION FAILED: {exc}',file=sys.stderr); raise SystemExit(2)
