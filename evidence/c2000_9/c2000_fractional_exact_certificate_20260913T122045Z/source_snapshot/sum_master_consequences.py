"""Exact Ferrers-master consequences of the independently checked partition."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from verification_common import decimal_uint, load_json, pin_one_cpu, require, require_list, require_object, vertex_list


def inspect(terms: dict[tuple[int, ...], int], denominator: int) -> dict[str, object]:
    coverage = [0] * 2000
    q = [0] * 6
    for vertices, weight in terms.items():
        require(weight > 0 and 1 <= len(vertices) <= 6, "term has invalid weight or size")
        for vertex in vertices:
            require(1 <= vertex <= 2000, "term contains an out-of-range vertex")
            coverage[vertex - 1] += weight
        for layer in range(len(vertices)):
            q[layer] += weight
    require(coverage == [denominator] * 2000, "terms do not cover every vertex exactly once")
    require(all(q[layer] <= 2000 // (layer + 1) * denominator for layer in range(6)), "a q coordinate violates its floor cap")
    value = 0
    for numerator in q:
        integer, remainder = divmod(numerator, denominator)
        value += integer * (integer + 1) // 2 * denominator + remainder * (integer + 1)
    require(value == 381823 * denominator, "sum-master objective is not 381823")
    return {
        "q_numerators": list(map(str, q)),
        "denominator": str(denominator),
        "exact_sum_master_objective": "381823",
        "exact_vertex_partition": True,
        "class_count_numerator": str(q[0]),
    }


def run(root: Path) -> None:
    certificate = require_object(
        load_json(root / "EXACT_FRACTIONAL_COLORING.json"),
        "fractional certificate",
        {"schema", "vertices", "graph_sha256", "objective", "denominator", "total_numerator", "terms", "zero_weight_vertices_one_based"},
    )
    denominator = decimal_uint(certificate["denominator"], "denominator", positive=True)
    raw_terms = require_list(certificate["terms"], "terms", maximum=1829)
    require(len(raw_terms) == 1829, "fractional certificate must contain 1829 terms")
    terms: dict[tuple[int, ...], int] = {}
    for index, raw_term in enumerate(raw_terms):
        term = require_object(raw_term, f"terms[{index}]", {"column", "vertices_one_based", "numerator"})
        vertices = tuple(vertex_list(term["vertices_one_based"], f"terms[{index}].vertices_one_based", minimum_size=1, maximum_size=6))
        require(vertices not in terms, "duplicate stable-set term")
        terms[vertices] = decimal_uint(term["numerator"], f"terms[{index}].numerator", positive=True)

    original = inspect(terms, denominator)
    require(int(original["class_count_numerator"]) * 5 == 1948 * denominator, "fractional class count is not 1948/5")
    require(denominator % 5 == 0, "denominator is not divisible by five")
    remaining = 2 * denominator // 5
    splits: list[dict[str, object]] = []
    for vertices, weight in list(terms.items()):
        if len(vertices) != 5 or remaining == 0:
            continue
        amount = min(weight, remaining)
        terms[vertices] -= amount
        parts = [vertices[:2], vertices[2:]]
        require(set(parts[0]).isdisjoint(parts[1]) and sorted(parts[0] + parts[1]) == sorted(vertices), "split does not partition its original set")
        for part in parts:
            terms[part] = terms.get(part, 0) + amount
        remaining -= amount
        splits.append({"original_set": vertices, "parts": parts, "numerator": str(amount)})
    terms = {vertices: weight for vertices, weight in terms.items() if weight}
    require(remaining == 0, "insufficient five-set weight for the exact 2/5 split")
    modified = inspect(terms, denominator)
    require(int(modified["class_count_numerator"]) == 390 * denominator, "modified class count is not 390")
    require(
        list(map(int, modified["q_numerators"]))
        == [390 * denominator, 390 * denominator, 1948 * denominator // 5, 1946 * denominator // 5, 1946 * denominator // 5, 52 * denominator],
        "modified q coordinates are wrong",
    )
    (root / "SUM_MASTER_K390_PRIMAL.json").write_text(
        json.dumps(
            {
                "denominator": str(denominator),
                "exact_class_count": 390,
                "exact_sum_master_objective": 381823,
                "terms": [{"vertices_one_based": vertices, "numerator": str(weight)} for vertices, weight in terms.items()],
                "splits": splits,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "verification/sum_master_consequences.json").write_text(
        json.dumps(
            {
                "original": original,
                "with_k_ge_390": modified,
                "total_split_weight": "2/5",
                "all_new_sets_are_subsets_of_original_verified_stable_sets": True,
                "scope": "exact matching primals for the six-layer floor-capped Ferrers master; combine with the checked 381823 dual for exact optimality",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def main(argv: list[str]) -> int:
    try:
        require(len(argv) == 2, "usage: sum_master_consequences.py ROOT")
        pin_one_cpu()
        run(Path(argv[1]))
    except Exception as exc:
        print(f"REJECT: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print("Exact master primal values: original=381823, with k>=390=381823; modified class count=390")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
