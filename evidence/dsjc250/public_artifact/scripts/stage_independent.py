#!/usr/bin/env python3
"""Copy the source-only second checker to scratch, add the external graph, and bind a scratch manifest."""
from pathlib import Path
import argparse, shutil, subprocess, sys
from check_graph import parse
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('graph',type=Path); ap.add_argument('destination',type=Path); a=ap.parse_args()
    root=Path(__file__).resolve().parents[1]; parse(a.graph)
    dst=a.destination.resolve()
    if dst.exists(): raise SystemExit(f'destination exists: {dst}')
    shutil.copytree(root/'independent_checker',dst)
    (dst/'data').mkdir(); shutil.copyfile(a.graph,dst/'data/DSJC250.9.col')
    subprocess.run([sys.executable,str(dst/'scripts/make_manifest.py'),str(dst)],check=True)
    print(dst)
if __name__=='__main__': main()
