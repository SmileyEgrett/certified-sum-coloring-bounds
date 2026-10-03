#!/usr/bin/env python3
"""Enumerate every stable set of a DIMACS graph into size-partitioned gzip files.

The algorithm enumerates cliques of the complement in increasing vertex order.
It streams each set immediately, so memory is independent of the number of sets.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import resource
import time
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_dimacs(path: Path):
    n = declared = None
    records = 0
    adjacency = None
    with path.open("rt", encoding="ascii") as handle:
        for lineno, line in enumerate(handle, 1):
            fields = line.split()
            if not fields or fields[0] == "c":
                continue
            if fields[0] == "p":
                if adjacency is not None or len(fields) != 4 or fields[1] not in {"edge", "edges", "col"}:
                    raise ValueError(f"line {lineno}: invalid or duplicate problem line")
                n = int(fields[2])
                declared = int(fields[3])
                adjacency = [0] * (n + 1)
                continue
            if fields[0] != "e" or adjacency is None or len(fields) != 3:
                raise ValueError(f"line {lineno}: invalid DIMACS record")
            u, v = map(int, fields[1:])
            if not (1 <= u <= n and 1 <= v <= n) or u == v:
                raise ValueError(f"line {lineno}: invalid edge endpoints")
            if adjacency[u] & (1 << v):
                raise ValueError(f"line {lineno}: duplicate undirected edge")
            adjacency[u] |= 1 << v
            adjacency[v] |= 1 << u
            records += 1
    if adjacency is None or records != declared:
        raise ValueError(f"edge count mismatch: declared={declared} read={records}")
    return n, records, adjacency


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--max-size", type=int, default=7)
    parser.add_argument("--progress-every", type=int, default=250_000)
    args = parser.parse_args()
    if args.max_size < 2:
        raise ValueError("--max-size must be at least 2 so truncation can be detected")

    args.out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    n, edge_count, adjacency = parse_dimacs(args.graph)
    parsed = time.perf_counter()
    full = (1 << (n + 1)) - 2
    complement = [0] * (n + 1)
    for vertex in range(1, n + 1):
        complement[vertex] = full & ~adjacency[vertex] & ~(1 << vertex)
    del adjacency

    paths = {size: args.out / f"stable_sets_size_{size}.tsv.gz" for size in range(1, args.max_size + 1)}
    handles = {size: gzip.open(path, "wt", encoding="ascii", newline="") for size, path in paths.items()}
    counts = [0] * (args.max_size + 1)
    semantic = [hashlib.sha256() for _ in range(args.max_size + 1)]
    total = 0
    for handle in handles.values():
        handle.write("id\tsize\tvertices\n")

    def visit(prefix: tuple[int, ...], candidates: int) -> None:
        nonlocal total
        remaining = candidates
        while remaining:
            bit = remaining & -remaining
            remaining ^= bit
            vertex = bit.bit_length() - 1
            child = prefix + (vertex,)
            size = len(child)
            counts[size] += 1
            total += 1
            vertices = " ".join(map(str, child))
            handles[size].write(f"{counts[size]}\t{size}\t{vertices}\n")
            semantic[size].update((vertices + "\n").encode("ascii"))
            if args.progress_every and total % args.progress_every == 0:
                print(json.dumps({"stage": "enumerating", "total": total, "counts": counts[1:]}), flush=True)
            if size < args.max_size:
                visit(child, remaining & complement[vertex])

    try:
        visit((), full)
    finally:
        for handle in handles.values():
            handle.close()
    enumerated = time.perf_counter()
    if counts[args.max_size]:
        raise RuntimeError(
            f"enumeration reached max size {args.max_size}; rerun with a larger --max-size"
        )
    alpha = max(size for size in range(1, args.max_size) if counts[size])
    families = {}
    for size in range(1, alpha + 1):
        families[str(size)] = {
            "count": counts[size],
            "file": paths[size].name,
            "file_sha256": sha256_file(paths[size]),
            "semantic_sha256": semantic[size].hexdigest(),
        }
    metadata = {
        "schema": "stable_set_stream_census_v1",
        "graph": str(args.graph.resolve()),
        "graph_raw_sha256": sha256_file(args.graph),
        "vertices": n,
        "unique_edges": edge_count,
        "alpha": alpha,
        "counts_by_size": counts[1 : alpha + 1],
        "nonempty_total": sum(counts[1 : alpha + 1]),
        "weighted_incidence_total": sum(size * counts[size] for size in range(1, alpha + 1)),
        "families": families,
        "timing_seconds": {
            "parse": parsed - started,
            "enumerate_and_write": enumerated - parsed,
            "total": enumerated - started,
        },
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    (args.out / "census.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print("FINAL_CENSUS", json.dumps(metadata, indent=2), flush=True)


if __name__ == "__main__":
    main()

