#!/usr/bin/env python3
"""Recover exact positive lower-hull facet normals for frontier points."""
from __future__ import annotations
import argparse,csv,json,itertools,math
from pathlib import Path
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def facets(points):
 out={}
 for i,j,k in itertools.combinations(range(len(points)),3):
  raw=cross(sub(points[j],points[i]),sub(points[k],points[i]))
  if raw==(0,0,0):continue
  for sign in (1,-1):
   w=tuple(sign*x for x in raw)
   if not all(x>0 for x in w):continue
   g=math.gcd(math.gcd(w[0],w[1]),w[2]);w=tuple(x//g for x in w);target=dot(w,points[i]);vals=[dot(w,p) for p in points]
   if min(vals)==target:
    face=tuple(n for n,v in enumerate(vals) if v==target);out[(w,target)]=face
 return out
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--frontier-csv',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
 rows=[{k:int(v) for k,v in r.items()} for r in csv.DictReader(a.frontier_csv.open())]
 groups={101:sorted({(r['h4'],r['h3'],r['h2']) for r in rows if r['packing'] not in (2,4)}),100:sorted({(r['h4'],r['h3'],r['h2']) for r in rows if r['packing'] in (2,4)})}
 out={'schema':'dsjc5009_frontier_supporting_normals_v1','coordinate_order':['h4','h3','h2'],'groups':{}}
 expected={101:7,100:8}
 for bound,pts in groups.items():
  fs=facets(pts)
  if len(pts)!=(23 if bound==101 else 20) or len(fs)!=expected[bound]:raise RuntimeError('facet census mismatch')
  data=[]
  for (w,t),face in sorted(fs.items()):
   if math.gcd(math.gcd(w[0],w[1]),w[2])!=1 or min(dot(w,p) for p in pts)!=t:raise RuntimeError('normal replay failed')
   data.append({'normal':list(w),'target':t,'equality_face':[list(pts[i]) for i in face],'minimum_over_frontier':t})
  out['groups'][str(bound)]={'h4_bound':bound,'frontier_points':[list(p) for p in pts],'facet_count':len(data),'facets':data}
 a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps({'groups':{k:{'points':len(v['frontier_points']),'facets':v['facet_count']} for k,v in out['groups'].items()}},indent=2))
if __name__=='__main__':main()
