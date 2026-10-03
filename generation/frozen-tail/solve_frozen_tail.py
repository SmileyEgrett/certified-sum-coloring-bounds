#!/usr/bin/env python3
"""Reoptimize the small-class tail of a proper coloring.

All classes of size at least five are frozen.  Every stable set in the
remaining induced graph is enumerated for a set-partitioning MILP. HiGHS
searches in floating point; the returned complete coloring is checked directly.
Solver optimality is not an independently checkable lower-bound certificate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path

import highspy
import networkx as nx
import numpy as np
from scipy.sparse import csr_matrix, lil_matrix


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def read_coloring(path: Path, n: int) -> tuple[dict[int, int], dict[int, list[int]]]:
    assigned: dict[int, int] = {}
    for line_number, raw in enumerate(path.read_text().splitlines(), 1):
        raw = raw.strip()
        if not raw or raw.split()[0].lower() == "c":
            continue
        fields = raw.split()
        if len(fields) != 2:
            raise ValueError(f"invalid coloring line {line_number}")
        vertex, color = map(int, fields)
        if vertex in assigned or not 1 <= vertex <= n or color <= 0:
            raise ValueError(f"invalid coloring vertex at line {line_number}")
        assigned[vertex] = color
    if set(assigned) != set(range(1, n + 1)):
        raise ValueError("coloring does not assign every vertex exactly once")
    classes: dict[int, list[int]] = defaultdict(list)
    for vertex, color in assigned.items():
        classes[color].append(vertex)
    return assigned, dict(classes)


def graph_records(path: Path):
    """Validate a simple DIMACS graph while streaming its edges."""
    n = declared = None
    seen: set[int] = set()
    with path.open() as source:
        for line_number, raw in enumerate(source, 1):
            fields = raw.split()
            if not fields or fields[0].lower() == "c":
                continue
            tag = fields[0].lower()
            if tag == "p":
                if n is not None or len(fields) != 4 or fields[1] not in {"col", "edge"}:
                    raise ValueError(f"invalid problem line {line_number}")
                n, declared = map(int, fields[2:])
                if n < 1 or not 0 <= declared <= n * (n - 1) // 2:
                    raise ValueError("invalid graph size")
                yield "p", n, declared
            elif tag == "e":
                if n is None or len(fields) != 3:
                    raise ValueError(f"invalid edge line {line_number}")
                u, v = sorted(map(int, fields[1:]))
                if not 1 <= u < v <= n:
                    raise ValueError(f"invalid edge line {line_number}")
                key = (u - 1) * n + v - 1
                if key in seen:
                    raise ValueError(f"duplicate edge line {line_number}")
                seen.add(key)
                yield "e", u, v
            else:
                raise ValueError(f"unsupported graph record {line_number}")
    if n is None or len(seen) != declared:
        raise ValueError("missing problem line or edge count mismatch")


def read_tail_graph(
    path: Path, assigned: dict[int, int], tail_vertices: set[int]
) -> tuple[nx.Graph, int, int]:
    n = 0
    graph = nx.Graph()
    graph.add_nodes_from(tail_vertices)
    edge_count = 0
    conflicts = 0
    for tag, u, v in graph_records(path):
        if tag == "p":
            if u != len(assigned):
                raise ValueError("graph/coloring order mismatch")
        else:
            edge = (u, v)
            edge_count += 1
            if u in tail_vertices and v in tail_vertices:
                graph.add_edge(*edge)
            if assigned[u] == assigned[v]:
                conflicts += 1
    return graph, edge_count, conflicts


def verify_full_coloring(path: Path, color_for_vertex: dict[int, int]) -> int:
    conflicts = 0
    for tag, u, v in graph_records(path):
        if tag == "e":
            if color_for_vertex[u] == color_for_vertex[v]:
                conflicts += 1
    return conflicts


def enumerate_stable_sets(graph: nx.Graph) -> tuple[list[tuple[int, ...]], int]:
    complement = nx.complement(graph)
    maximal = list(nx.find_cliques(complement))
    alpha = max(map(len, maximal), default=0)
    stable_sets: list[tuple[int, ...]] = []
    for clique in nx.enumerate_all_cliques(complement):
        if len(clique) > alpha:
            break
        stable_sets.append(tuple(sorted(clique)))
    stable_sets.sort(key=lambda group: (len(group), group))
    return stable_sets, alpha


def linear_terms(indices, coefficients, names) -> str:
    terms: list[tuple[str, str]] = []
    for index, coefficient in zip(indices, coefficients):
        if coefficient == 0:
            continue
        sign = "+" if coefficient > 0 else "-"
        magnitude = abs(float(coefficient))
        term = names[index] if magnitude == 1 else f"{magnitude:g} {names[index]}"
        terms.append((sign, term))
    if not terms:
        return "0"
    first_sign, first_term = terms[0]
    result = ("- " if first_sign == "-" else "") + first_term
    for sign, term in terms[1:]:
        result += f" {sign} {term}"
    return result


def write_lp(
    path: Path,
    matrix: csr_matrix,
    lower: np.ndarray,
    upper: np.ndarray,
    objective: np.ndarray,
    names: list[str],
) -> None:
    with path.open("w") as out:
        out.write("\\ Frozen-prefix tail reoptimization\n")
        nz = np.flatnonzero(objective)
        out.write("Minimize\n obj: " + linear_terms(nz, objective[nz], names) + "\n")
        out.write("Subject To\n")
        for row in range(matrix.shape[0]):
            start, end = matrix.indptr[row], matrix.indptr[row + 1]
            lhs = linear_terms(matrix.indices[start:end], matrix.data[start:end], names)
            if lower[row] == upper[row]:
                out.write(f" r{row:04d}: {lhs} = {lower[row]:g}\n")
            else:
                raise AssertionError("only equality rows are expected")
        out.write("Binary\n")
        for start in range(0, len(names), 12):
            out.write(" " + " ".join(names[start : start + 12]) + "\n")
        out.write("End\n")


def canonical(classes: list[tuple[int, ...]]) -> tuple[int, list[tuple[int, ...]]]:
    ordered = sorted(classes, key=lambda group: (-len(group), group))
    return sum(index * len(group) for index, group in enumerate(ordered, 1)), ordered


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--coloring", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--build-only", action="store_true", help="write the model without solving it")
    args = parser.parse_args()
    if args.threads < 1:
        parser.error("--threads must be positive")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    started = time.perf_counter()

    # Read n first, then the coloring, then fully validate graph and coloring.
    records = graph_records(args.graph)
    try:
        tag, n, _ = next(records)
    except StopIteration:
        raise ValueError("missing graph problem line")
    finally:
        records.close()
    assigned, source_classes = read_coloring(args.coloring, n)
    frozen = [tuple(sorted(group)) for group in source_classes.values() if len(group) >= 5]
    tail_vertices = sorted(
        vertex for group in source_classes.values() if len(group) < 5 for vertex in group
    )
    frozen.sort(key=lambda group: (-len(group), group))
    offset = len(frozen)
    tail_graph, edge_count, conflicts = read_tail_graph(args.graph, assigned, set(tail_vertices))
    if conflicts:
        raise ValueError(f"source coloring has {conflicts} conflicts")
    stable_sets, alpha = enumerate_stable_sets(tail_graph)
    if frozen and alpha > min(map(len, frozen)):
        raise ValueError("a tail class could precede the frozen prefix; this model requires tail independence number no larger than the smallest frozen class")
    if not tail_vertices:
        value, classes = canonical(frozen)
        colors = {v: c for c, group in enumerate(classes, 1) for v in group}
        (args.output_dir / "best.coloring").write_text(
            "c proper coloring; empty tail\n" + "".join(f"{v} {colors[v]}\n" for v in range(1, n + 1)))
        (args.output_dir / "result.json").write_text(json.dumps({
            "model_status": "Not needed: empty tail", "verified_full_sum": value,
            "total_wall_seconds": time.perf_counter() - started,
            "graph_sha256": digest(args.graph), "source_coloring_sha256": digest(args.coloring)
        }, indent=2) + "\n")
        return
    counts = {
        str(size): sum(len(group) == size for group in stable_sets)
        for size in range(1, alpha + 1)
    }

    row_for_vertex = {vertex: row for row, vertex in enumerate(tail_vertices)}
    y_index: dict[tuple[int, int], int] = {}
    variable = len(stable_sets)
    for threshold in range(1, alpha + 1):
        for segment in range(1, len(tail_vertices) // threshold + 1):
            y_index[(threshold, segment)] = variable
            variable += 1
    matrix = lil_matrix((len(tail_vertices) + alpha, variable), dtype=np.float64)
    for column, stable_set in enumerate(stable_sets):
        for vertex in stable_set:
            matrix[row_for_vertex[vertex], column] = 1
    for threshold in range(1, alpha + 1):
        row = len(tail_vertices) + threshold - 1
        for column, stable_set in enumerate(stable_sets):
            if len(stable_set) >= threshold:
                matrix[row, column] = 1
        for segment in range(1, len(tail_vertices) // threshold + 1):
            matrix[row, y_index[(threshold, segment)]] = -1
    matrix = matrix.tocsr()
    lower = np.zeros(matrix.shape[0])
    upper = np.zeros(matrix.shape[0])
    lower[: len(tail_vertices)] = upper[: len(tail_vertices)] = 1
    objective = np.zeros(variable)
    for (threshold, segment), column in y_index.items():
        objective[column] = segment
    names = [f"x_{index:05d}" for index in range(len(stable_sets))]
    names += [
        f"y_{threshold}_{segment}"
        for threshold in range(1, alpha + 1)
        for segment in range(1, len(tail_vertices) // threshold + 1)
    ]
    model_path = args.output_dir / "frozen_tail.lp"
    write_lp(model_path, matrix, lower, upper, objective, names)
    (args.output_dir / "stable_sets.json").write_text(
        json.dumps([list(group) for group in stable_sets]) + "\n"
    )
    metadata = {
        "schema": "frozen_tail_v1",
        "graph": args.graph.name,
        "graph_sha256": digest(args.graph),
        "source_coloring": args.coloring.name,
        "source_coloring_sha256": digest(args.coloring),
        "vertices": n,
        "edges": edge_count,
        "frozen_classes": offset,
        "frozen_profile": dict(
                sorted((str(size), sum(len(group) == size for group in frozen)) for size in set(map(len, frozen)))
        ),
        "tail_vertices": len(tail_vertices),
        "tail_alpha": alpha,
        "tail_stable_sets": len(stable_sets),
        "tail_stable_sets_by_size": counts,
        "model_rows": matrix.shape[0],
        "model_columns": matrix.shape[1],
        "model_nonzeros": matrix.nnz,
        "threads": args.threads,
        "time_limit": None,
    }
    (args.output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print("MODEL", json.dumps(metadata, sort_keys=True), flush=True)
    if args.build_only:
        return

    highs = highspy.Highs()
    if highs.readModel(str(model_path)) != highspy.HighsStatus.kOk:
        raise RuntimeError("HiGHS could not read model")
    for option, value in {
        "mip_rel_gap": 0.0,
        "threads": args.threads,
        "parallel": "off" if args.threads == 1 else "on",
        "random_seed": 0,
        "log_file": str(args.output_dir / "highs.log"),
    }.items():
        if highs.setOptionValue(option, value) != highspy.HighsStatus.kOk:
            raise RuntimeError(f"HiGHS rejected {option}={value}")
        status, actual = highs.getOptionValue(option)
        if status != highspy.HighsStatus.kOk or actual != value:
            raise RuntimeError(f"HiGHS did not retain {option}={value}")
    run_status = highs.run()
    if run_status not in {highspy.HighsStatus.kOk, highspy.HighsStatus.kWarning}:
        raise RuntimeError(f"HiGHS run failed: {run_status}")
    solution = highs.getSolution()
    info = highs.getInfo()
    result = {
        "model_status": highs.modelStatusToString(highs.getModelStatus()),
        "solution_value_valid": bool(solution.value_valid),
        "objective": float(info.objective_function_value),
        "dual_bound": float(info.mip_dual_bound),
        "mip_gap": float(info.mip_gap),
        "nodes": int(info.mip_node_count),
        "simplex_iterations": int(info.simplex_iteration_count),
        "runtime_seconds": float(highs.getRunTime()),
    }
    if solution.value_valid:
        tail_classes = []
        for index, stable_set in enumerate(stable_sets):
            lookup_status, column = highs.getColByName(f"x_{index:05d}")
            if lookup_status != highspy.HighsStatus.kOk:
                raise AssertionError(f"missing model column x_{index:05d}")
            if solution.col_value[column] > 0.5:
                tail_classes.append(stable_set)
        tail_sum, tail_classes = canonical(tail_classes)
        full_sum, all_classes = canonical(frozen + tail_classes)
        frozen_sum, _ = canonical(frozen)
        flat = sorted(vertex for group in all_classes for vertex in group)
        if flat != list(range(1, n + 1)):
            raise AssertionError("solution is not a vertex partition")
        if abs(tail_sum - info.objective_function_value) > 1e-6:
            raise AssertionError("model and verified tail objectives differ")
        expected_full_sum = frozen_sum + offset * len(tail_vertices) + tail_sum
        if full_sum != expected_full_sum:
            raise AssertionError("full objective decomposition differs")
        result.update(
            {
                "verified_full_sum": full_sum,
                "tail_local_sum": tail_sum,
                "tail_classes": len(tail_classes),
                "tail_profile": dict(
                    sorted(
                        (str(size), sum(len(group) == size for group in tail_classes))
                        for size in set(map(len, tail_classes))
                    )
                ),
                "full_profile": dict(
                    sorted(
                        (str(size), sum(len(group) == size for group in all_classes))
                        for size in set(map(len, all_classes))
                    )
                ),
            }
        )
        color_for_vertex = {}
        for color, group in enumerate(all_classes, 1):
            for vertex in group:
                color_for_vertex[vertex] = color
        solution_conflicts = verify_full_coloring(args.graph, color_for_vertex)
        if solution_conflicts:
            raise AssertionError(f"solution has {solution_conflicts} conflicting edges")
        certificate = [
            "c proper coloring obtained by frozen-tail optimization",
            f"c graph {args.graph.name}",
            f"c source_coloring_sha256 {metadata['source_coloring_sha256']}",
            f"c colors_used {len(all_classes)}",
            f"c canonical_sum {full_sum}",
            "c vertices and colors are 1-based",
        ]
        certificate += [f"{vertex} {color_for_vertex[vertex]}" for vertex in range(1, n + 1)]
        (args.output_dir / "best.coloring").write_text("\n".join(certificate) + "\n")
        (args.output_dir / "classes.json").write_text(
            json.dumps([list(group) for group in all_classes], indent=2) + "\n"
        )
    result["total_wall_seconds"] = time.perf_counter() - started
    (args.output_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print("RESULT", json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
