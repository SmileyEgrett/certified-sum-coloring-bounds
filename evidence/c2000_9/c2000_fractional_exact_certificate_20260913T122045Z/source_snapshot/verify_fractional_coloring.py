"""Independent standard-library exact primal/dual checker on original graph bytes."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from verification_common import (
    GRAPH_SHA256,
    decimal_uint,
    json_uint,
    load_json,
    parse_graph,
    pin_one_cpu,
    require,
    require_list,
    require_object,
    sha256_bytes,
    stable,
    vertex_list,
)


def verify(root: Path) -> dict[str, object]:
    start = time.monotonic()
    raw, adjacency = parse_graph(root / "input/C2000.9.col")
    certificate = require_object(
        load_json(root / "EXACT_FRACTIONAL_COLORING.json"),
        "fractional certificate",
        {"schema", "vertices", "graph_sha256", "objective", "denominator", "total_numerator", "terms", "zero_weight_vertices_one_based"},
    )
    require(certificate["schema"] == "c2000_fractional_coloring_exact_v1", "wrong fractional certificate schema")
    require(json_uint(certificate["vertices"], "vertices") == 2000, "wrong certificate vertex count")
    require(certificate["graph_sha256"] == sha256_bytes(raw) == GRAPH_SHA256, "certificate graph binding mismatch")
    require(certificate["objective"] == "1948/5", "wrong declared fractional objective")
    denominator = decimal_uint(certificate["denominator"], "denominator", positive=True)
    declared_total = decimal_uint(certificate["total_numerator"], "total_numerator", positive=True)
    terms = require_list(certificate["terms"], "terms", maximum=1829)
    require(len(terms) == 1829, "fractional certificate must contain exactly 1829 terms")

    coverage = [0] * 2000
    total = 0
    columns: set[int] = set()
    stable_sets: set[tuple[int, ...]] = set()
    size_counts = [0] * 7
    size_weights = [0] * 7
    for term_index, raw_term in enumerate(terms):
        name = f"terms[{term_index}]"
        term = require_object(raw_term, name, {"column", "vertices_one_based", "numerator"})
        column = json_uint(term["column"], f"{name}.column", positive=True)
        require(column not in columns, f"duplicate column id {column}")
        columns.add(column)
        vertices = vertex_list(term["vertices_one_based"], f"{name}.vertices_one_based", minimum_size=1, maximum_size=6)
        key = tuple(vertices)
        require(key not in stable_sets, f"duplicate stable-set term at {name}")
        stable_sets.add(key)
        weight = decimal_uint(term["numerator"], f"{name}.numerator", positive=True)
        stable(vertices, adjacency, name)
        for vertex in vertices:
            coverage[vertex - 1] += weight
        total += weight
        size_counts[len(vertices)] += 1
        size_weights[len(vertices)] += weight

    require(coverage == [denominator] * 2000, "fractional primal does not cover every vertex exactly once")
    require(total == declared_total, "total_numerator does not equal the term sum")
    require(5 * total == 1948 * denominator, "fractional primal objective is not exactly 1948/5")
    require(size_counts[5] == 1757 and size_counts[6] == 72 and sum(size_counts) == 1829, "unexpected term-size profile")
    require(5 * size_weights[5] == 1688 * denominator, "size-five weight is not 1688/5")
    require(size_weights[6] == 52 * denominator, "size-six weight is not 52")

    hit_vertices = vertex_list(
        certificate["zero_weight_vertices_one_based"],
        "zero_weight_vertices_one_based",
        minimum_size=52,
        maximum_size=52,
    )
    hit = {v - 1 for v in hit_vertices}
    universe = (1 << 2000) - 1
    outside = universe
    for vertex in hit:
        outside ^= 1 << vertex
    nonadjacent = [outside & ~(adjacency[v] | (1 << v)) for v in range(2000)]
    counts = [0] * 6

    def visit(candidates: int, depth: int) -> None:
        while candidates:
            bit = candidates & -candidates
            candidates -= bit
            vertex = bit.bit_length() - 1
            counts[depth] += 1
            require(depth < 5, "independent six-set outside H invalidates the dual")
            next_candidates = candidates & nonadjacent[vertex]
            if next_candidates:
                visit(next_candidates, depth + 1)

    visit(outside, 0)
    require(counts == [1948, 188767, 1212650, 579560, 21708, 0], "outside-H stable-set census mismatch")
    return {
        "status": "ACCEPT",
        "claim": "chi_f(C2000.9) = 1948/5",
        "primal_exact_vertex_coverage": True,
        "primal_exact_total": "1948/5",
        "dual_exact_total": "1948/5",
        "outside_independent_counts_sizes_1_to_6": counts,
        "outside_alpha": 5,
        "terms": len(terms),
        "denominator_digits": len(str(denominator)),
        "seconds": time.monotonic() - start,
    }


def main(argv: list[str]) -> int:
    try:
        require(len(argv) == 2, "usage: verify_fractional_coloring.py ROOT")
        pin_one_cpu()
        result = verify(Path(argv[1]))
    except Exception as exc:
        print(f"REJECT: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
