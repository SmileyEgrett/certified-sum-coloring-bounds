#!/usr/bin/env python3
from pathlib import Path
import hashlib, os, stat, sys
root=Path(sys.argv[1] if len(sys.argv)>1 else Path(__file__).resolve().parents[1]).resolve()
rows=[]
for p in root.rglob('*'):
 if p.name=='MANIFEST.sha256':continue
 st=p.lstat()
 if stat.S_ISLNK(st.st_mode):raise SystemExit(f'symlink rejected: {p}')
 if p.is_file():
  h=hashlib.sha256(p.read_bytes()).hexdigest();rows.append((p.relative_to(root).as_posix(),h))
(root/'MANIFEST.sha256').write_text(''.join(f'{h}  {rel}\n' for rel,h in sorted(rows)),'utf-8')
print(f'wrote {len(rows)} entries')
