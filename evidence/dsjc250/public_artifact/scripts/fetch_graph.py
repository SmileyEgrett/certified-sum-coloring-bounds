#!/usr/bin/env python3
"""Retrieve the authoritative COLOR03 DSJC250.9 DIMACS file and verify it."""
from __future__ import annotations
import argparse, os, tempfile, urllib.request
from pathlib import Path
from check_graph import parse
URL="https://mat.tepper.cmu.edu/COLOR03/INSTANCES/DSJC250.9.col"
def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("output",type=Path); ap.add_argument("--url",default=URL); ap.add_argument("--replace",action="store_true")
    a=ap.parse_args(); out=a.output.resolve()
    if out.exists() and not a.replace: raise SystemExit(f"refusing to overwrite {out}; use --replace")
    out.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=out.name+".",dir=out.parent); os.close(fd); p=Path(tmp)
    try:
        with urllib.request.urlopen(a.url,timeout=60) as response, p.open("wb") as stream:
            while True:
                block=response.read(1<<20)
                if not block: break
                stream.write(block)
        result=parse(p); os.replace(p,out)
        print(f"verified graph written to {out}")
        print(f"raw_sha256={result['raw_sha256']}")
        print(f"canonical_sha256={result['canonical_sha256']}")
    finally:
        p.unlink(missing_ok=True)
    return 0
if __name__=="__main__": raise SystemExit(main())
