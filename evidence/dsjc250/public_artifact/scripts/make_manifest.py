#!/usr/bin/env python3
"""Create the artifact SHA-256 manifest, rejecting symbolic links."""
from pathlib import Path
import argparse, hashlib, stat

def digest(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument('root',type=Path,nargs='?',default=Path(__file__).resolve().parents[1]); a=ap.parse_args(); root=a.root.resolve()
    rows=[]
    for p in sorted(root.rglob('*')):
        rel=p.relative_to(root).as_posix(); st=p.lstat()
        if stat.S_ISLNK(st.st_mode): raise SystemExit(f'symlink rejected: {rel}')
        if p.is_file() and rel!='MANIFEST.sha256': rows.append((rel,digest(p)))
    (root/'MANIFEST.sha256').write_text(''.join(f'{h}  {rel}\n' for rel,h in rows),encoding='utf-8')
    print(f'wrote {len(rows)} entries to {root/"MANIFEST.sha256"}')
    return 0
if __name__=='__main__': raise SystemExit(main())
