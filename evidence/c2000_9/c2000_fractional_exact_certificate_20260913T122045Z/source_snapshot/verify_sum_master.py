"""Exact graph-to-certificate check for both floor-capped sum-master optima."""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
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


FRACTIONAL_KEYS = {"schema", "vertices", "graph_sha256", "objective", "denominator", "total_numerator", "terms", "zero_weight_vertices_one_based"}


def parse_primal(path: Path, adjacency: list[int], *, fractional: bool) -> tuple[dict[str, object], int, list[int], dict[tuple[int, ...], int], Counter[int]]:
    raw = require_object(
        load_json(path),
        path.name,
        FRACTIONAL_KEYS if fractional else {"denominator", "exact_class_count", "exact_sum_master_objective", "terms", "splits"},
    )
    denominator = decimal_uint(raw["denominator"], f"{path.name}.denominator", positive=True)
    if fractional:
        require(raw["schema"] == "c2000_fractional_coloring_exact_v1", "wrong fractional schema")
        require(json_uint(raw["vertices"], "vertices") == 2000, "wrong fractional vertex count")
        require(raw["graph_sha256"] == GRAPH_SHA256, "fractional graph binding mismatch")
        require(raw["objective"] == "1948/5", "wrong fractional objective field")
        decimal_uint(raw["total_numerator"], "total_numerator", positive=True)
        expected_terms = 1829
    else:
        require(json_uint(raw["exact_class_count"], "exact_class_count") == 390, "wrong exact_class_count")
        require(json_uint(raw["exact_sum_master_objective"], "exact_sum_master_objective") == 381823, "wrong exact_sum_master_objective")
        expected_terms = 1831
    terms = require_list(raw["terms"], f"{path.name}.terms", maximum=expected_terms)
    require(len(terms) == expected_terms, f"{path.name} has the wrong number of terms")
    coverage = [0] * 2000
    q = [0] * 6
    term_map: dict[tuple[int, ...], int] = {}
    size_counts: Counter[int] = Counter()
    columns: set[int] = set()
    for index, raw_term in enumerate(terms):
        name = f"{path.name}.terms[{index}]"
        keys = {"vertices_one_based", "numerator", "column"} if fractional else {"vertices_one_based", "numerator"}
        term = require_object(raw_term, name, keys)
        if fractional:
            column = json_uint(term["column"], f"{name}.column", positive=True)
            require(column not in columns, f"duplicate column id {column}")
            columns.add(column)
        vertices = vertex_list(term["vertices_one_based"], f"{name}.vertices_one_based", minimum_size=1, maximum_size=6)
        key = tuple(vertices)
        require(key not in term_map, f"duplicate stable-set term in {path.name}")
        numerator = decimal_uint(term["numerator"], f"{name}.numerator", positive=True)
        stable(vertices, adjacency, name)
        term_map[key] = numerator
        size_counts[len(vertices)] += 1
        for vertex in vertices:
            coverage[vertex - 1] += numerator
        for layer in range(len(vertices)):
            q[layer] += numerator
    require(coverage == [denominator] * 2000, f"{path.name} does not cover every vertex exactly once")
    return raw, denominator, q, term_map, size_counts


def verify_split(raw_k390: dict[str, object], denominator: int, original: dict[tuple[int, ...], int], transformed_expected: dict[tuple[int, ...], int], adjacency: list[int]) -> None:
    splits = require_list(raw_k390["splits"], "splits", maximum=1)
    require(len(splits) == 1, "split history must contain exactly one split")
    transformed = dict(original)
    total_split = 0
    for index, raw_split in enumerate(splits):
        split = require_object(raw_split, f"splits[{index}]", {"original_set", "parts", "numerator"})
        original_set = tuple(vertex_list(split["original_set"], "split.original_set", minimum_size=5, maximum_size=5))
        raw_parts = require_list(split["parts"], "split.parts", maximum=2)
        require(len(raw_parts) == 2, "split must contain exactly two parts")
        parts = [tuple(vertex_list(part, f"split.parts[{i}]", minimum_size=1, maximum_size=4)) for i, part in enumerate(raw_parts)]
        require(set(parts[0]).isdisjoint(parts[1]), "split parts overlap")
        require(sorted(parts[0] + parts[1]) == list(original_set), "split parts do not partition the original set")
        for i, part in enumerate(parts):
            stable(list(part), adjacency, f"split.parts[{i}]")
        amount = decimal_uint(split["numerator"], "split.numerator", positive=True)
        require(original_set in transformed and transformed[original_set] >= amount, "split removes unavailable weight")
        transformed[original_set] -= amount
        for part in parts:
            transformed[part] = transformed.get(part, 0) + amount
        total_split += amount
    transformed = {vertices: weight for vertices, weight in transformed.items() if weight}
    require(5 * total_split == 2 * denominator, "total split weight is not exactly 2/5")
    require(transformed == transformed_expected, "K390 terms do not equal the declared split transformation")


def verify(root: Path) -> dict[str, object]:
    start = time.monotonic()
    raw_graph, adjacency = parse_graph(root / "input/C2000.9.col")
    base_raw, denominator, base_q, base_terms, base_sizes = parse_primal(root / "EXACT_FRACTIONAL_COLORING.json", adjacency, fractional=True)
    require(base_raw["graph_sha256"] == sha256_bytes(raw_graph), "fractional certificate is not bound to these graph bytes")
    hit_vertices = vertex_list(base_raw["zero_weight_vertices_one_based"], "zero_weight_vertices_one_based", minimum_size=52, maximum_size=52)
    hit = {vertex - 1 for vertex in hit_vertices}

    weights = [52 if vertex in hit else 390 for vertex in range(2000)]
    slopes = [390] * 5 + [52]
    intercepts = [75855] * 5 + [1326]
    prefix: list[int] = []
    running = 0
    for slope in slopes:
        running += slope
        prefix.append(running)
    for layer in range(6):
        for count in range(2000 // (layer + 1) + 1):
            require(count * slopes[layer] - intercepts[layer] <= count * (count + 1) // 2, "Ferrers support inequality violated")

    universe = (1 << 2000) - 1
    nonadjacent = [universe & ~(adjacency[vertex] | (1 << vertex)) for vertex in range(2000)]
    counts = [0] * 7

    def visit(candidates: int, depth: int, weight: int) -> None:
        while candidates:
            bit = candidates & -candidates
            candidates -= bit
            vertex = bit.bit_length() - 1
            new_weight = weight + weights[vertex]
            counts[depth] += 1
            require(depth < 6, "stable seven-set invalidates complete six-layer universe")
            require(new_weight <= prefix[depth], "stable-set dual constraint violated")
            next_candidates = candidates & nonadjacent[vertex]
            if next_candidates:
                visit(next_candidates, depth + 1, new_weight)

    visit(universe, 0, 0)
    require(counts == [2000, 199468, 1322912, 656504, 26224, 90, 0], "complete stable-set census mismatch")
    lower = sum(weights) - sum(intercepts)
    require(lower == 381823, "dual objective is not 381823")

    require(denominator % 5 == 0, "fractional denominator is not divisible by five")
    expected_base_q = [1948 * denominator // 5] * 5 + [52 * denominator]
    require(base_q == expected_base_q, "fractional primal has the wrong q coordinates")
    require(base_sizes == Counter({5: 1757, 6: 72}), "fractional primal has the wrong term-size profile")
    declared_total = decimal_uint(base_raw["total_numerator"], "total_numerator", positive=True)
    require(sum(base_terms.values()) == declared_total and 5 * declared_total == 1948 * denominator, "fractional total is not 1948/5")

    k390_raw, k390_denominator, k390_q, k390_terms, k390_sizes = parse_primal(root / "SUM_MASTER_K390_PRIMAL.json", adjacency, fractional=False)
    require(k390_denominator == denominator, "K390 denominator differs from the fractional denominator")
    expected_k390_q = [390 * denominator, 390 * denominator, 1948 * denominator // 5, 1946 * denominator // 5, 1946 * denominator // 5, 52 * denominator]
    require(k390_q == expected_k390_q, "K390 primal has the wrong q coordinates")
    require(k390_sizes == Counter({2: 1, 3: 1, 5: 1757, 6: 72}), "K390 primal has the wrong term-size profile")
    verify_split(k390_raw, denominator, base_terms, k390_terms, adjacency)

    output: dict[str, object] = {}
    for name, q in [("EXACT_FRACTIONAL_COLORING.json", base_q), ("SUM_MASTER_K390_PRIMAL.json", k390_q)]:
        objective = 0
        for layer, numerator in enumerate(q):
            require(0 <= numerator <= 2000 // (layer + 1) * denominator, f"{name} violates a layer cap")
            integer, remainder = divmod(numerator, denominator)
            objective += integer * (integer + 1) // 2 * denominator + (integer + 1) * remainder
        require(objective == lower * denominator, f"{name} objective is not 381823")
        output[name] = {
            "exact_objective": 381823,
            "effective_class_count": "390" if name.startswith("SUM_") else "1948/5",
            "valid_stable_set_partition": True,
        }

    return {
        "status": "ACCEPT",
        "complete_stable_counts_sizes_1_to_7": counts,
        "all_stable_dual_constraints_exact": True,
        "all_ferrers_support_constraints_exact": True,
        "exact_dual_bound": lower,
        "primal_certificates": output,
        "conclusion": "The floor-capped complete sum-colouring master has exact optimum 381823 both without and with k>=390.",
        "seconds": time.monotonic() - start,
    }


def main(argv: list[str]) -> int:
    try:
        require(len(argv) == 2, "usage: verify_sum_master.py ROOT")
        pin_one_cpu()
        result = verify(Path(argv[1]))
    except Exception as exc:
        print(f"REJECT: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
