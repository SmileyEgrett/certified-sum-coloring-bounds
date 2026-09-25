#!/usr/bin/env python3
"""Independent cumulative-coordinate enumeration of all g-profiles with Phi<=8276."""
from __future__ import annotations
import argparse,csv,hashlib
from pathlib import Path
HEADER=['h1','h2','h3','h4','h5','g1','g2','g3','g4','g5','classes','canonical_sum','layered_survivor','selected_top_survivor']
def T(x):return x*(x+1)//2
def rows():
 out=[]
 for g5 in range(3):
  for g4 in range(g5,63):
   for g3 in range(g4,84):
    # g1+g2 is now determined; g2 lies between g3 and g1.
    remaining=250-g3-g4-g5
    for g2 in range(g3,remaining//2+1):
     g1=remaining-g2
     value=T(g1)+T(g2)+T(g3)+T(g4)+T(g5)
     if value>8276:continue
     g=(g1,g2,g3,g4,g5);h=(g1-g2,g2-g3,g3-g4,g4-g5,g5)
     if min(h)<0:continue
     layered=(g4<=39 and (h[4]!=2 or g4<=36));selected=(layered and (h[4]!=1 or g4<=38))
     out.append((*h,*g,g1,value,int(layered),int(selected)))
 return sorted(out,key=lambda r:r[:5])
def write(path,rs):
 with path.open('w',newline='',encoding='utf-8') as f:w=csv.writer(f,lineterminator='\n');w.writerow(HEADER);w.writerows(rs)
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path);ap.add_argument('--verify',action='store_true');a=ap.parse_args();rs=rows()
 if a.verify:assert (len(rs),sum(r[-2] for r in rs),sum(r[-1] for r in rs))==(6668,45,16)
 if a.output:write(a.output,rs);d=hashlib.sha256(a.output.read_bytes()).hexdigest()
 else:d='-'
 print(f'threshold_profiles={len(rs)} layered_survivors={sum(r[-2] for r in rs)} selected_top_frontier={sum(r[-1] for r in rs)} csv_sha256={d}')
if __name__=='__main__':main()
