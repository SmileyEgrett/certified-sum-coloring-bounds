#!/usr/bin/env python3
"""Fail-closed verifier for the authentic C2000.9 graph and upper witness."""

from __future__ import annotations

import argparse
import hashlib
import sys
from collections import Counter, defaultdict
from pathlib import Path


GRAPH_RAW_SHA256 = "aa4b1d7df7f9c1afbf8c9f35fcf5bdfc6370fd27db5c9f3fd5409dfd0d164f16"
GRAPH_CANONICAL_SHA256 = "a7083cb6110feefea75ed6728fa13968a1533cdc6751717ca09e99b2eafb8bfd"
WITNESS_SHA256 = "4461990a562e2e5616d38709332f3ff1b634753009b97f39627026b6c028d0a2"


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def parse_graph(path: Path) -> tuple[bytes, int, int, set[tuple[int, int]], str]:
    require(path.stat().st_size <= 24 * 1024 * 1024, "graph input exceeds 24 MiB")
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == GRAPH_RAW_SHA256, "graph raw SHA-256 mismatch")
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise VerificationError("graph is not ASCII") from exc
    vertices = declared_edges = None
    edges: set[tuple[int, int]] = set()
    header_count = 0
    for line_number, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line or line.startswith("c"):
            continue
        fields = line.split()
        if fields[0] == "p":
            require(len(fields) == 4 and fields[1] in {"edge", "edges", "col"}, f"bad header at line {line_number}")
            require(header_count == 0 and not edges, f"duplicate or late header at line {line_number}")
            header_count += 1
            try:
                vertices, declared_edges = int(fields[2]), int(fields[3])
            except ValueError as exc:
                raise VerificationError(f"noninteger header at line {line_number}") from exc
        elif fields[0] == "e":
            require(len(fields) == 3 and vertices is not None, f"bad edge at line {line_number}")
            try:
                left, right = int(fields[1]), int(fields[2])
            except ValueError as exc:
                raise VerificationError(f"noninteger edge at line {line_number}") from exc
            require(1 <= left <= vertices and 1 <= right <= vertices and left != right, f"invalid edge at line {line_number}")
            if left > right:
                left, right = right, left
            require((left, right) not in edges, f"duplicate edge at line {line_number}")
            edges.add((left, right))
        else:
            raise VerificationError(f"unexpected record at line {line_number}")
    require(header_count == 1 and vertices is not None and declared_edges is not None, "missing graph header")
    require(vertices == 2000 and declared_edges == len(edges) == 1799532, "graph dimensions or edge count mismatch")
    digest = hashlib.sha256()
    digest.update(f"p edge {vertices} {len(edges)}\n".encode())
    for left, right in sorted(edges):
        digest.update(f"e {left} {right}\n".encode())
    canonical_hash = digest.hexdigest()
    require(canonical_hash == GRAPH_CANONICAL_SHA256, "graph canonical SHA-256 mismatch")
    return raw, vertices, declared_edges, edges, canonical_hash


def parse_coloring(path: Path, vertices: int) -> tuple[bytes, dict[int, int]]:
    require(path.stat().st_size <= 1024 * 1024, "coloring input exceeds 1 MiB")
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == WITNESS_SHA256, "witness SHA-256 mismatch")
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise VerificationError("coloring is not UTF-8") from exc
    assignment: dict[int, int] = {}
    for line_number, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line or line.startswith("c"):
            continue
        fields = line.split()
        require(len(fields) == 2, f"bad coloring line {line_number}")
        try:
            vertex, color = map(int, fields)
        except ValueError as exc:
            raise VerificationError(f"nonnumeric coloring line {line_number}") from exc
        require(1 <= vertex <= vertices and color > 0 and vertex not in assignment, f"invalid coloring line {line_number}")
        assignment[vertex] = color
    require(set(assignment) == set(range(1, vertices + 1)), "coloring is not a complete assignment")
    return raw, assignment


def verify(graph_path: Path, coloring_path: Path) -> list[str]:
    raw_graph, vertices, edges_count, edges, canonical_hash = parse_graph(graph_path)
    raw_coloring, assignment = parse_coloring(coloring_path, vertices)
    conflicts = [(left, right, assignment[left]) for left, right in edges if assignment[left] == assignment[right]]
    require(not conflicts, f"color conflicts: {conflicts[:5]}")
    classes: defaultdict[int, list[int]] = defaultdict(list)
    for vertex, color in assignment.items():
        classes[color].append(vertex)
    labels = sorted(classes)
    require(labels == list(range(1, len(labels) + 1)), "noncontiguous labels")
    sizes = [len(classes[color]) for color in labels]
    require(sizes == sorted(sizes, reverse=True), "not canonical nonincreasing class order")
    require(all(1 <= size <= 6 for size in sizes), "class size outside 1..6")
    profile = Counter(sizes)
    expected_profile = (1, 4, 11, 24, 310, 52)
    require(len(classes) == 402, "witness does not have 402 classes")
    require(tuple(profile.get(size, 0) for size in range(1, 7)) == expected_profile, "witness profile mismatch")
    direct = sum(assignment.values())
    canonical = sum((index + 1) * size for index, size in enumerate(sizes))
    require(direct == canonical == 382379, "witness objective is not 382379")
    return [
        f"graph_raw_sha256={hashlib.sha256(raw_graph).hexdigest()}",
        f"graph_canonical_sha256={canonical_hash}",
        f"vertices={vertices}",
        f"edges={edges_count}",
        f"witness_sha256={hashlib.sha256(raw_coloring).hexdigest()}",
        f"classes={len(classes)}",
        f"profile={expected_profile}",
        f"direct_sum={direct}",
        f"canonical_sum={canonical}",
        "conflicts=0",
        "C2000.9 GRAPH/WITNESS VERIFICATION: SUCCESS",
    ]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--coloring", type=Path, required=True)
    try:
        arguments = parser.parse_args(argv[1:])
        output = verify(arguments.graph, arguments.coloring)
    except Exception as exc:
        print(f"REJECT: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print("\n".join(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
