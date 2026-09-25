#!/usr/bin/env python3
"""Enumerate all h-profiles with Phi<=8276 using exact-size coordinates."""
from __future__ import annotations
import argparse,csv,hashlib,sys
from pathlib import Path
HEADER=['h1','h2','h3','h4','h5','g1','g2','g3','g4','g5','classes','canonical_sum','layered_survivor','selected_top_survivor']
def phi(g): return sum(x*(x+1)//2 for x in g)
def rows():
    out=[]
    for h5 in range(3):
      for h4 in range((250-5*h5)//4+1):
       for h3 in range((250-5*h5-4*h4)//3+1):
        rem=250-5*h5-4*h4-3*h3
        for h2 in range(rem//2+1):
         h1=rem-2*h2; h=(h1,h2,h3,h4,h5); g=tuple(sum(h[t-1:]) for t in range(1,6)); value=phi(g)
         if value<=8276:
          layered=(g[3]<=39 and (h5!=2 or g[3]<=36)); selected=(layered and (h5!=1 or g[3]<=38))
          out.append((*h,*g,g[0],value,int(layered),int(selected)))
    return sorted(out,key=lambda r:r[:5])
def write(path,rs):
    with path.open('w',newline='',encoding='utf-8') as f: w=csv.writer(f,lineterminator='\n');w.writerow(HEADER);w.writerows(rs)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path);ap.add_argument('--verify',action='store_true');a=ap.parse_args();rs=rows()
    if a.verify:
      assert len(rs)==6668; assert sum(r[-2] for r in rs)==45; assert sum(r[-1] for r in rs)==16
      inc=(2,4,29,37,1);g=tuple(sum(inc[t-1:]) for t in range(1,6));assert phi(g)==8277
    if a.output: write(a.output,rs); raw=a.output.read_bytes(); digest=hashlib.sha256(raw).hexdigest()
    else: digest='-'
    print(f'threshold_profiles={len(rs)} layered_survivors={sum(r[-2] for r in rs)} selected_top_frontier={sum(r[-1] for r in rs)} csv_sha256={digest}')
if __name__=='__main__':main()
