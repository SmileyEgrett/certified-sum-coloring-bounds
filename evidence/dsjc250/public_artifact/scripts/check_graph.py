#!/usr/bin/env python3
"""Strictly identify DSJC250.9 bytes and reproduce the canonical graph hash."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

EXPECTED_N=250
EXPECTED_M=27897
EXPECTED_RAW="1b90f811e4d44f8937075865790b845e986b08b9da53caea57b2adf1c57383e7"
EXPECTED_CANON="52be422c0065411e126008bf4ee8ee2ba21320bde0a0e94d5ab308c2e34f53a8"
EXPECTED_BYTES=255403
EXPECTED_LINES=27910

def sha(data: bytes)->str: return hashlib.sha256(data).hexdigest()

def parse(path: Path)->dict:
    raw=path.read_bytes()
    n=declared=None; header=False; records=0; edges=set()
    for line_no, raw_line in enumerate(raw.splitlines(),1):
        try: line=raw_line.decode("ascii").strip()
        except UnicodeDecodeError as exc: raise ValueError(f"line {line_no}: non-ASCII") from exc
        if not line: continue
        f=line.split()
        if f[0]=="c": continue
        if f[0]=="p":
            if header or len(f)!=4 or f[1] not in {"edge","edges","col"}: raise ValueError(f"line {line_no}: malformed/duplicate header")
            n=int(f[2]); declared=int(f[3]); header=True
            if str(n)!=f[2] or str(declared)!=f[3] or n<=0 or declared<0: raise ValueError(f"line {line_no}: noncanonical dimensions")
        elif f[0]=="e":
            if not header or len(f)!=3: raise ValueError(f"line {line_no}: malformed edge")
            u=int(f[1]); v=int(f[2])
            if str(u)!=f[1] or str(v)!=f[2] or not (1<=u<=n and 1<=v<=n) or u==v: raise ValueError(f"line {line_no}: invalid edge")
            records += 1
            e=(u,v) if u<v else (v,u)
            if e in edges: raise ValueError(f"line {line_no}: duplicate undirected edge {e}")
            edges.add(e)
        else: raise ValueError(f"line {line_no}: unknown record {f[0]!r}")
    if not header or n!=EXPECTED_N or declared!=EXPECTED_M or records!=declared or len(edges)!=declared:
        raise ValueError(f"dimension/count mismatch: n={n}, declared={declared}, records={records}, unique={len(edges)}")
    canon=("exact_mscp_graph_v1\n"+f"vertices {n}\n"+"".join(f"{u} {v}\n" for u,v in sorted(edges))).encode("ascii")
    result={"path":str(path),"bytes":len(raw),"physical_lines":len(raw.splitlines()),"vertices":n,"edges":len(edges),"raw_sha256":sha(raw),"canonical_sha256":sha(canon),"canonical_bytes":len(canon),"canonical_grammar":"ASCII; LF; exact_mscp_graph_v1\\n; vertices <n>\\n; then normalized u<v edges sorted lexicographically, one '<u> <v>\\n' record each; terminal LF"}
    expected={"bytes":EXPECTED_BYTES,"physical_lines":EXPECTED_LINES,"vertices":EXPECTED_N,"edges":EXPECTED_M,"raw_sha256":EXPECTED_RAW,"canonical_sha256":EXPECTED_CANON}
    bad={k:(result[k],v) for k,v in expected.items() if result[k]!=v}
    if bad: raise ValueError(f"DSJC250.9 identity mismatch: {bad}")
    return result

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("graph",type=Path); ap.add_argument("--json-out",type=Path)
    a=ap.parse_args(); result=parse(a.graph)
    text=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if a.json_out: a.json_out.write_text(text,encoding="utf-8")
    print(text,end="")
    return 0
if __name__=="__main__":
    try: raise SystemExit(main())
    except Exception as exc:
        import sys; print(f"GRAPH CHECK FAILED: {exc}",file=sys.stderr); raise SystemExit(2)
