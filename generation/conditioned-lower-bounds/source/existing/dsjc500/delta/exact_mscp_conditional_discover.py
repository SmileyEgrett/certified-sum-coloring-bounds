#!/usr/bin/env python3
"""Bounded discovery for certified conditional MSCP envelopes.

This module is deliberately outside the trusted proof boundary.  Floating-point
LP solutions guide branching and suggest dual weights, but generated conclusions
are useful only after independent replay by ``exact_mscp_conditional_verify.py``.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Mapping, Sequence

import exact_mscp_conditional_verify as checked

PROOF_SCHEMA = checked.TREE_PROOF_SCHEMA
MODEL_SCHEMA = checked.MODEL_SCHEMA
PLAN_SCHEMA = "exact_mscp_conditional_plan_v1"
DISCOVERY_SCHEMA = "exact_mscp_conditional_discovery_v1"
DENOMINATOR = 10**9
TOLERANCE = 1e-7


class DiscoveryLimit(RuntimeError):
    """A configured discovery resource limit was reached."""


class FeasiblePacking(RuntimeError):
    """The strict target was met by an exact integral packing."""

    def __init__(self, columns: tuple[int, ...]):
        super().__init__("strict target has an integral packing")
        self.columns = columns


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(canonical_json(value))
    os.replace(temporary, path)


def write_gzip_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0, compresslevel=9) as stream:
            stream.write(canonical_json(value))
    os.replace(temporary, path)


def model_identifier(payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return "conditional_" + digest[:20]


def h_to_profile(h_values: Sequence[int]) -> checked.Profile:
    h = [0] + list(h_values)
    return checked.profile_from_h(h)


def create_model(
    output: Path,
    graph: checked.Graph,
    stable_sets: Mapping[int, Sequence[tuple[int, ...]]],
    alpha: int,
    fixed_top: Sequence[Sequence[int]],
    scores: Mapping[int, int],
    caps: Mapping[int, int],
    target: int,
    radix: int,
) -> dict[str, Any]:
    tops = checked.canonical_top(tuple(tuple(stable) for stable in fixed_top))
    identity_payload = {
        "graph": graph.canonical_sha256,
        "fixed_top": tops,
        "scores": sorted(scores.items(), reverse=True),
        "caps": sorted(caps.items(), reverse=True),
        "target": target,
    }
    identifier = model_identifier(identity_payload)
    used = {vertex for stable in tops for vertex in stable}
    columns: list[tuple[tuple[int, ...], int, int]] = []
    for size, coefficient in sorted(scores.items(), reverse=True):
        for stable in stable_sets[size]:
            if not used.intersection(stable):
                columns.append((stable, size, coefficient))
    columns_path = output / f"{identifier}.columns.tsv"
    with columns_path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t", lineterminator="\n")
        writer.writerow(["column_id", "size", "score", "vertices"])
        for column_id, (stable, size, coefficient) in enumerate(columns):
            writer.writerow([column_id, size, coefficient, " ".join(map(str, stable))])
    model = {
        "schema": MODEL_SCHEMA,
        "model_id": identifier,
        "graph_raw_sha256": graph.raw_sha256,
        "graph_canonical_sha256": graph.canonical_sha256,
        "vertices": graph.vertices,
        "maximum_class_size": alpha,
        "fixed_top_classes": [list(stable) for stable in tops],
        "score_by_size": {str(size): scores[size] for size in sorted(scores)},
        "type_caps": {str(size): caps[size] for size in sorted(caps)},
        "strict_target": target,
        "radix": radix,
        "column_count": len(columns),
        "columns_file": columns_path.name,
        "columns_sha256": sha256_file(columns_path),
    }
    model_path = output / f"{identifier}.model.json"
    write_json_atomic(model_path, model)
    return {
        "model_id": identifier,
        "model_file": model_path.name,
        "model_sha256": sha256_file(model_path),
        "columns_file": columns_path.name,
        "columns_sha256": model["columns_sha256"],
        "column_count": len(columns),
        "fixed_top_classes": [list(stable) for stable in tops],
        "score_by_size": model["score_by_size"],
        "type_caps": model["type_caps"],
        "strict_target": target,
    }


def plan_command(arguments: argparse.Namespace) -> int:
    started = time.monotonic()
    graph = checked.parse_graph(arguments.graph)
    if arguments.campaign is not None:
        campaign = checked.parse_campaign(arguments.campaign)
        alpha = campaign.maximum_class_size
        threshold = campaign.objective_threshold
        verification = checked.verify_campaign(
            arguments.graph,
            arguments.campaign,
            generator_root=arguments.generator_root,
            stable_mode=arguments.stable_mode,
            veripb=arguments.veripb,
        )
        unresolved = verification["unresolved_profiles"]
        prior_count = verification["certificate_count"]
        stable_limit = campaign.stable_enumeration_node_limit
        top_limit = campaign.maximum_top_packings
    else:
        if arguments.maximum_class_size is None or arguments.objective_threshold is None:
            raise checked.VerificationError(
                "plan without --campaign requires --maximum-class-size and --objective-threshold"
            )
        alpha = arguments.maximum_class_size
        threshold = arguments.objective_threshold
        stable_limit = arguments.stable_node_limit
        top_limit = arguments.top_packing_limit
        enumeration = checked.enumerate_stable_sets(graph, alpha + 1, stable_limit)
        stable_sets = enumeration.by_size
        if not stable_sets[alpha] or stable_sets[alpha + 1]:
            raise checked.VerificationError("configured maximum class size is not exact")
        packing_number, packings = checked.enumerate_top_packings(
            stable_sets[alpha], graph.vertices, top_limit
        )
        profiles, _ = checked.enumerate_profiles(
            graph.vertices,
            alpha,
            packing_number,
            threshold,
            arguments.profile_node_limit,
        )
        unresolved = [
            {
                "h": list(profile.h[1:]),
                "objective": profile.objective,
                "surviving_top_packings": [
                    [list(stable) for stable in packing]
                    for packing in packings.get(profile.h[alpha], ())
                ],
            }
            for profile in profiles
        ]
        prior_count = 0
    enumeration = checked.enumerate_stable_sets(graph, alpha + 1, stable_limit)
    stable_sets = enumeration.by_size
    arguments.out.mkdir(parents=True, exist_ok=True)
    models_root = arguments.out / "models"
    models_root.mkdir(parents=True, exist_ok=True)
    if not unresolved:
        result = {
            "schema": PLAN_SCHEMA,
            "status": "COMPLETE",
            "graph_raw_sha256": graph.raw_sha256,
            "graph_canonical_sha256": graph.canonical_sha256,
            "objective_threshold": threshold,
            "prior_certificate_count": prior_count,
            "unresolved_profile_count": 0,
            "selected_objective": None,
            "model_count": 0,
            "completion_count": 0,
            "models": [],
            "elapsed_seconds": round(time.monotonic() - started, 6),
        }
        write_json_atomic(arguments.out / "plan.json", result)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0

    selected_objective = min(item["objective"] for item in unresolved)
    selected = [item for item in unresolved if item["objective"] == selected_objective]
    emitted: dict[str, dict[str, Any]] = {}
    radix = graph.vertices + 1
    for item in sorted(selected, key=lambda entry: (entry["h"], entry["surviving_top_packings"])):
        profile = h_to_profile(item["h"])
        for top in item["surviving_top_packings"]:
            for terminal_size in range(alpha - 1, 1, -1):
                score_sizes = list(range(alpha - 1, terminal_size - 1, -1))
                scores = {
                    size: radix ** (size - terminal_size)
                    for size in score_sizes
                }
                caps = {
                    size: profile.h[size]
                    for size in score_sizes
                    if size > terminal_size
                }
                target = sum(profile.h[size] * scores[size] for size in score_sizes)
                if target <= 0:
                    continue
                descriptor = create_model(
                    models_root,
                    graph,
                    stable_sets,
                    alpha,
                    top,
                    scores,
                    caps,
                    target,
                    radix,
                )
                descriptor["source_profile_h"] = list(profile.h[1:])
                descriptor["source_profile_objective"] = profile.objective
                descriptor["terminal_size"] = terminal_size
                emitted.setdefault(descriptor["model_id"], descriptor)
    models = [emitted[key] for key in sorted(emitted)]
    result = {
        "schema": PLAN_SCHEMA,
        "status": "PLANNED",
        "graph_raw_sha256": graph.raw_sha256,
        "graph_canonical_sha256": graph.canonical_sha256,
        "objective_threshold": threshold,
        "prior_certificate_count": prior_count,
        "unresolved_profile_count": len(unresolved),
        "selected_objective": selected_objective,
        "selected_profile_count": len(selected),
        "model_count": len(models),
        "completion_count": 0,
        "models": models,
        "elapsed_seconds": round(time.monotonic() - started, 6),
    }
    write_json_atomic(arguments.out / "plan.json", result)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


@dataclass
class ExactPacking:
    size: int
    edges: tuple[tuple[int, int], ...]


def exact_matching(
    residual: Sequence[int], pair_set: set[tuple[int, int]]
) -> ExactPacking:
    vertices = tuple(sorted(residual))
    local = {vertex: index for index, vertex in enumerate(vertices)}
    neighbors = [0] * len(vertices)
    for left, right in pair_set:
        if left in local and right in local:
            i, j = local[left], local[right]
            neighbors[i] |= 1 << j
            neighbors[j] |= 1 << i

    @lru_cache(maxsize=None)
    def solve(mask: int) -> tuple[int, tuple[tuple[int, int], ...]]:
        if not mask:
            return 0, ()
        bit = mask & -mask
        i = bit.bit_length() - 1
        without = mask ^ bit
        best = solve(without)
        choices = neighbors[i] & without
        while choices:
            other_bit = choices & -choices
            choices ^= other_bit
            j = other_bit.bit_length() - 1
            count, edges = solve(without ^ other_bit)
            edge = (vertices[i], vertices[j])
            candidate = (count + 1, tuple(sorted(edges + (edge,))))
            if candidate[0] > best[0] or (candidate[0] == best[0] and candidate[1] < best[1]):
                best = candidate
        return best

    count, edges = solve((1 << len(vertices)) - 1)
    return ExactPacking(count, edges)


def exact_barrier(
    residual: Sequence[int], pair_set: set[tuple[int, int]], matching_size: int
) -> tuple[tuple[int, ...], list[list[int]]]:
    vertices = tuple(sorted(residual))
    for mask in range(1 << len(vertices)):
        barrier = tuple(vertices[index] for index in range(len(vertices)) if (mask >> index) & 1)
        odd = checked.odd_components(vertices, barrier, pair_set)
        numerator = len(vertices) + len(barrier) - len(odd)
        if numerator >= 0 and numerator % 2 == 0 and numerator // 2 == matching_size:
            return barrier, odd
    raise RuntimeError("Tutte--Berge equality barrier was not found")


class Prover:
    def __init__(
        self,
        graph: checked.Graph,
        stable_sets: Mapping[int, Sequence[tuple[int, ...]]],
        model: Mapping[str, Any],
        columns: Sequence[tuple[tuple[int, ...], int, int, int]],
        *,
        node_limit: int,
        time_limit: float,
        matching_vertex_limit: int,
        denominator: int,
    ) -> None:
        self.graph = graph
        self.stable_sets = stable_sets
        self.model = model
        self.columns = tuple(columns)
        self.node_limit = node_limit
        self.time_limit = time_limit
        self.matching_vertex_limit = matching_vertex_limit
        self.denominator = denominator
        self.started = time.monotonic()
        self.nodes = 0
        self.branches = 0
        self.leaves = 0
        self.matching_leaves = 0
        self.lp_seconds = 0.0
        self.records: list[dict[str, Any]] = []
        top_vertices = {
            vertex
            for stable in model["fixed_top_classes"]
            for vertex in stable
        }
        self.residual_vertices = tuple(
            vertex for vertex in range(1, graph.vertices + 1) if vertex not in top_vertices
        )
        self.vertex_index = {vertex: index for index, vertex in enumerate(self.residual_vertices)}
        self.incident = [0] * len(self.residual_vertices)
        self.size_masks: dict[int, int] = {size: 0 for size, _ in model["score_items"]}
        for column_id, (stable, size, _, _) in enumerate(self.columns):
            bit = 1 << column_id
            self.size_masks[size] |= bit
            for vertex in stable:
                self.incident[self.vertex_index[vertex]] |= bit
        self.conflicts: list[int] = []
        for stable, _, _, _ in self.columns:
            mask = 0
            for vertex in stable:
                mask |= self.incident[self.vertex_index[vertex]]
            self.conflicts.append(mask)
        self.pair_set = set(stable_sets.get(2, ()))

    def check_limit(self) -> None:
        if self.node_limit > 0 and self.nodes >= self.node_limit:
            raise DiscoveryLimit("node limit")
        if self.time_limit > 0 and time.monotonic() - self.started >= self.time_limit:
            raise DiscoveryLimit("time limit")

    def solve_lp(self, active_ids: tuple[int, ...], caps: Mapping[int, int]) -> tuple[Any, Any, tuple[int, ...]]:
        try:
            import numpy as np
            from numerical import linprog
            from scipy.sparse import csc_matrix
        except ImportError as error:
            raise DiscoveryLimit(f"SciPy discovery dependency unavailable: {error}")
        started = time.monotonic()
        cap_sizes = tuple(sorted(caps, reverse=True))
        row_count = len(self.residual_vertices) + len(cap_sizes)
        cap_row = {
            size: len(self.residual_vertices) + index
            for index, size in enumerate(cap_sizes)
        }
        rows: list[int] = []
        cols: list[int] = []
        values: list[float] = []
        objective = np.empty(len(active_ids), dtype=float)
        for local_id, column_id in enumerate(active_ids):
            stable, size, score, _ = self.columns[column_id]
            objective[local_id] = -float(score)
            for vertex in stable:
                rows.append(self.vertex_index[vertex])
                cols.append(local_id)
                values.append(1.0)
            if size in cap_row:
                rows.append(cap_row[size])
                cols.append(local_id)
                values.append(1.0)
        matrix = csc_matrix((values, (rows, cols)), shape=(row_count, len(active_ids)))
        rhs = np.r_[
            np.ones(len(self.residual_vertices)),
            [caps[size] for size in cap_sizes],
        ]
        result = linprog(
            objective,
            A_ub=matrix,
            b_ub=rhs,
            bounds=(0, None),
            method="highs-ipm",
            options={"presolve": False},
        )
        self.lp_seconds += time.monotonic() - started
        if not result.success:
            raise DiscoveryLimit("unexpected discovery LP failure: " + result.message)
        return result.x, -result.ineqlin.marginals, cap_sizes

    def exact_dual_leaf(
        self,
        active_ids: tuple[int, ...],
        caps: Mapping[int, int],
        selected_score: int,
        dual: Any,
        cap_sizes: Sequence[int],
    ) -> dict[str, Any] | None:
        vertex_count = len(self.residual_vertices)
        weights = [
            max(0, math.ceil(float(dual[index]) * self.denominator - 1e-5))
            for index in range(vertex_count)
        ]
        multipliers = {
            size: max(
                0,
                math.ceil(
                    float(dual[vertex_count + index]) * self.denominator - 1e-5
                ),
            )
            for index, size in enumerate(cap_sizes)
        }
        repairs = 0
        for column_id in active_ids:
            stable, size, score, _ = self.columns[column_id]
            lhs = sum(weights[self.vertex_index[vertex]] for vertex in stable)
            lhs += multipliers.get(size, 0)
            required = score * self.denominator
            if lhs < required:
                deficit = required - lhs
                weights[self.vertex_index[stable[0]]] += deficit
                repairs += deficit
        numerator = sum(weights) + sum(
            caps[size] * multipliers.get(size, 0) for size in caps
        )
        if selected_score * self.denominator + numerator >= self.model["strict_target"] * self.denominator:
            return None
        return {
            "kind": "leaf",
            "denominator": self.denominator,
            "vertex_weights": [
                [self.residual_vertices[index], value]
                for index, value in enumerate(weights)
                if value
            ],
            "cap_weights": [
                [size, multipliers[size]]
                for size in cap_sizes
                if multipliers[size]
            ],
            "numerator": numerator,
            "selected_score": selected_score,
            "repairs": repairs,
        }

    def matching_terminal(
        self,
        active_ids: tuple[int, ...],
        selected_score: int,
        used_mask: int,
        selected_columns: tuple[int, ...],
    ) -> dict[str, Any] | None:
        if any(self.columns[column_id][1] != 2 for column_id in active_ids):
            return None
        if dict(self.model["score_items"]).get(2) != 1:
            return None
        residual = tuple(
            vertex
            for vertex in self.residual_vertices
            if not ((used_mask >> vertex) & 1)
        )
        if len(residual) > self.matching_vertex_limit:
            return None
        expected_pairs = {
            stable
            for stable in self.pair_set
            if stable[0] in residual and stable[1] in residual
        }
        active_pairs = {self.columns[column_id][0] for column_id in active_ids}
        if active_pairs != expected_pairs:
            return None
        maximum = exact_matching(residual, self.pair_set)
        if selected_score + maximum.size >= self.model["strict_target"]:
            edge_to_column = {
                self.columns[column_id][0]: column_id for column_id in active_ids
            }
            raise FeasiblePacking(
                tuple(sorted(selected_columns + tuple(edge_to_column[edge] for edge in maximum.edges)))
            )
        barrier, odd = exact_barrier(residual, self.pair_set, maximum.size)
        return {
            "kind": "matching_leaf",
            "selected_score": selected_score,
            "residual": list(residual),
            "matching_upper": maximum.size,
            "barrier": list(barrier),
            "odd_components": odd,
            "matching": [list(edge) for edge in maximum.edges],
        }

    def choose_branch(self, active_ids: tuple[int, ...], solution: Any) -> int | None:
        choices: list[tuple[int, float, float, int, int]] = []
        for local_id, column_id in enumerate(active_ids):
            value = float(solution[local_id])
            if TOLERANCE < value < 1.0 - TOLERANCE:
                score = self.columns[column_id][2]
                choices.append((score, -abs(value - 0.5), value, -column_id, column_id))
        return max(choices)[-1] if choices else None

    def recurse(
        self,
        active: int,
        caps: dict[int, int],
        selected_score: int,
        used_mask: int,
        selected_columns: tuple[int, ...],
    ) -> int:
        self.check_limit()
        self.nodes += 1
        active_ids = tuple(index for index in range(len(self.columns)) if (active >> index) & 1)
        matching = self.matching_terminal(
            active_ids, selected_score, used_mask, selected_columns
        )
        if matching is not None:
            self.leaves += 1
            self.matching_leaves += 1
            self.records.append(matching)
            return len(self.records) - 1
        if not active_ids:
            if selected_score >= self.model["strict_target"]:
                raise FeasiblePacking(tuple(sorted(selected_columns)))
            self.leaves += 1
            self.records.append({
                "kind": "leaf",
                "denominator": self.denominator,
                "vertex_weights": [],
                "cap_weights": [],
                "numerator": 0,
                "selected_score": selected_score,
                "repairs": 0,
            })
            return len(self.records) - 1
        solution, dual, cap_sizes = self.solve_lp(active_ids, caps)
        leaf = self.exact_dual_leaf(active_ids, caps, selected_score, dual, cap_sizes)
        if leaf is not None:
            self.leaves += 1
            self.records.append(leaf)
            return len(self.records) - 1
        branch = self.choose_branch(active_ids, solution)
        if branch is None:
            integral = tuple(
                active_ids[local_id]
                for local_id, value in enumerate(solution)
                if float(value) > 0.5
            )
            candidate = tuple(sorted(selected_columns + integral))
            score = sum(self.columns[column_id][2] for column_id in candidate)
            if score >= self.model["strict_target"]:
                raise FeasiblePacking(candidate)
            raise DiscoveryLimit("integral LP point did not close and did not meet target")
        self.branches += 1
        zero = self.recurse(
            active & ~(1 << branch),
            dict(caps),
            selected_score,
            used_mask,
            selected_columns,
        )
        stable, size, score, mask = self.columns[branch]
        if used_mask & mask:
            raise RuntimeError("discovery selected an overlapping column")
        next_caps = dict(caps)
        if size in next_caps:
            if next_caps[size] <= 0:
                raise RuntimeError("discovery selected a column after cap exhaustion")
            next_caps[size] -= 1
        one_active = active & ~self.conflicts[branch]
        if size in next_caps and next_caps[size] == 0:
            one_active &= ~self.size_masks[size]
        one = self.recurse(
            one_active,
            next_caps,
            selected_score + score,
            used_mask | mask,
            tuple(sorted(selected_columns + (branch,))),
        )
        self.records.append({"kind": "branch", "var": branch, "zero": zero, "one": one})
        return len(self.records) - 1

    def run(self) -> int:
        return self.recurse(
            (1 << len(self.columns)) - 1,
            dict(self.model["cap_items"]),
            0,
            0,
            (),
        )


def packing_witness(
    graph: checked.Graph,
    model: Mapping[str, Any],
    columns: Sequence[tuple[tuple[int, ...], int, int, int]],
    selected: Sequence[int],
) -> dict[str, Any]:
    classes = [tuple(stable) for stable in model["fixed_top_classes"]]
    classes.extend(columns[index][0] for index in selected)
    flat = [vertex for stable in classes for vertex in stable]
    if len(flat) != len(set(flat)) or any(not checked.is_stable(stable, graph) for stable in classes):
        raise RuntimeError("internal feasible packing is invalid")
    used = set(flat)
    complete = classes + [(vertex,) for vertex in range(1, graph.vertices + 1) if vertex not in used]
    complete = sorted(complete, key=lambda stable: (-len(stable), stable))
    sizes = [len(stable) for stable in complete]
    canonical_sum = sum((index + 1) * size for index, size in enumerate(sizes))
    maximum_size = max(sizes, default=0)
    exact_size_profile = [sum(1 for size in sizes if size == value) for value in range(1, maximum_size + 1)]
    ge_profile = [sum(1 for size in sizes if size >= value) for value in range(1, maximum_size + 1)]
    return {
        "schema": "exact_mscp_conditional_discovery_witness_v1",
        "status": "FEASIBLE",
        "graph_raw_sha256": graph.raw_sha256,
        "graph_canonical_sha256": graph.canonical_sha256,
        "model_id": model["model_id"],
        "fixed_top_classes": [list(stable) for stable in model["fixed_top_classes"]],
        "selected_columns": list(selected),
        "selected_classes": [list(columns[index][0]) for index in selected],
        "complete_partition": [list(stable) for stable in complete],
        "canonical_sum": canonical_sum,
        "strength": len(complete),
        "exact_size_profile": exact_size_profile,
        "ge_profile": ge_profile,
    }


def write_and_check_coloring(path: Path, graph: checked.Graph, witness: Mapping[str, Any]) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    rows: list[str] = []
    assigned: set[int] = set()
    for color, stable in enumerate(witness["complete_partition"], 1):
        for vertex in stable:
            if vertex in assigned:
                raise RuntimeError("internal coloring witness assigns a vertex twice")
            assigned.add(vertex)
            rows.append(f"{vertex} {color}")
    if assigned != set(range(1, graph.vertices + 1)):
        raise RuntimeError("internal coloring witness is incomplete")
    temporary.write_text("\n".join(rows) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    independently_checked = checked.parse_coloring(path, graph)
    if (
        independently_checked["canonical_sum"] != witness["canonical_sum"]
        or independently_checked["actual_sum"] != witness["canonical_sum"]
        or independently_checked["strength"] != witness["strength"]
        or independently_checked["exact_size_profile"] != witness["exact_size_profile"]
        or independently_checked["ge_profile"] != witness["ge_profile"]
    ):
        raise RuntimeError("independent coloring reconstruction disagrees with discovery witness")
    return independently_checked


def prove_command(arguments: argparse.Namespace) -> int:
    if arguments.workers < 1:
        raise checked.VerificationError("worker count must be positive")
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[variable] = str(arguments.workers)
    started = time.monotonic()
    graph = checked.parse_graph(arguments.graph)
    raw_model = checked.load_json(arguments.model, "conditional discovery model", arguments.maximum_json_bytes)
    if not isinstance(raw_model, dict) or not isinstance(raw_model.get("model_id"), str):
        raise checked.VerificationError("conditional model has no valid model_id")
    alpha = raw_model.get("maximum_class_size")
    if type(alpha) is not int or alpha <= 0:
        raise checked.VerificationError("conditional model maximum class size is invalid")
    enumeration = checked.enumerate_stable_sets(graph, alpha + 1, arguments.stable_node_limit)
    stable_sets = enumeration.by_size
    model, columns, _ = checked.parse_model(
        arguments.model,
        raw_model["model_id"],
        graph,
        stable_sets,
        alpha,
        arguments.maximum_json_bytes,
    )
    prover = Prover(
        graph,
        stable_sets,
        model,
        columns,
        node_limit=arguments.node_limit,
        time_limit=arguments.time_limit,
        matching_vertex_limit=arguments.matching_vertex_limit,
        denominator=arguments.denominator,
    )
    result: dict[str, Any]
    exit_code: int
    try:
        root = prover.run()
        proof = {
            "schema": PROOF_SCHEMA,
            "status": "PROVED",
            "model_sha256": sha256_file(arguments.model),
            "columns_sha256": model["columns_sha256"],
            "root": root,
            "proof": prover.records,
            "statistics": {
                "branches": prover.branches,
                "leaves": prover.leaves,
                "matching_leaves": prover.matching_leaves,
                "nodes": len(prover.records),
            },
        }
        write_gzip_json_atomic(arguments.out, proof)
        checked.verify_tree_proof(
            arguments.out,
            arguments.model,
            model["model_id"],
            graph,
            stable_sets,
            alpha,
            arguments.maximum_json_bytes,
            arguments.maximum_proof_bytes,
            arguments.maximum_proof_records,
        )
        result = {
            "schema": DISCOVERY_SCHEMA,
            "status": "PROVED",
            "model_id": model["model_id"],
            "proof_file": str(arguments.out),
            "proof_sha256": sha256_file(arguments.out),
            "proof_records": len(prover.records),
            "branches": prover.branches,
            "leaves": prover.leaves,
            "matching_leaves": prover.matching_leaves,
            "search_nodes": prover.nodes,
            "stable_enumeration_nodes": enumeration.nodes,
            "lp_seconds": round(prover.lp_seconds, 6),
        }
        exit_code = 0
    except FeasiblePacking as feasible:
        witness = packing_witness(graph, model, columns, feasible.columns)
        witness_path = arguments.witness_out or arguments.out.with_suffix(".witness.json")
        coloring_path = witness_path.with_name(witness_path.name + ".coloring")
        independently_checked = write_and_check_coloring(coloring_path, graph, witness)
        witness["coloring_file"] = coloring_path.name
        witness["coloring_sha256"] = sha256_file(coloring_path)
        witness["independent_coloring_check"] = {
            "actual_sum": independently_checked["actual_sum"],
            "canonical_sum": independently_checked["canonical_sum"],
            "strength": independently_checked["strength"],
            "exact_size_profile": independently_checked["exact_size_profile"],
            "ge_profile": independently_checked["ge_profile"],
        }
        write_json_atomic(witness_path, witness)
        result = {
            "schema": DISCOVERY_SCHEMA,
            "status": "FEASIBLE",
            "model_id": model["model_id"],
            "witness_file": str(witness_path),
            "witness_sha256": sha256_file(witness_path),
            "coloring_file": str(coloring_path),
            "coloring_sha256": sha256_file(coloring_path),
            "canonical_sum": witness["canonical_sum"],
            "strength": witness["strength"],
            "search_nodes": prover.nodes,
            "stable_enumeration_nodes": enumeration.nodes,
            "lp_seconds": round(prover.lp_seconds, 6),
        }
        exit_code = 4
    except DiscoveryLimit as limit:
        result = {
            "schema": DISCOVERY_SCHEMA,
            "status": "INCOMPLETE",
            "model_id": model["model_id"],
            "reason": str(limit),
            "search_nodes": prover.nodes,
            "proof_records": len(prover.records),
            "stable_enumeration_nodes": enumeration.nodes,
            "lp_seconds": round(prover.lp_seconds, 6),
        }
        exit_code = 3
    result["elapsed_seconds"] = round(time.monotonic() - started, 6)
    print(json.dumps(result, indent=2, sort_keys=True))
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    plan = subparsers.add_parser("plan", help="emit models for the lowest unresolved objective layer")
    plan.add_argument("--graph", type=Path, required=True)
    plan.add_argument("--out", type=Path, required=True)
    plan.add_argument("--campaign", type=Path)
    plan.add_argument("--generator-root", type=Path)
    plan.add_argument("--stable-mode", choices=("materialized", "disk", "both"), default="materialized")
    plan.add_argument("--veripb", type=Path)
    plan.add_argument("--maximum-class-size", type=int)
    plan.add_argument("--objective-threshold", type=int)
    plan.add_argument("--stable-node-limit", type=int, default=10_000_000)
    plan.add_argument("--profile-node-limit", type=int, default=10_000_000)
    plan.add_argument("--top-packing-limit", type=int, default=100_000)
    plan.set_defaults(function=plan_command)

    prove = subparsers.add_parser("prove-model", help="bounded exact proof-tree discovery")
    prove.add_argument("--graph", type=Path, required=True)
    prove.add_argument("--model", type=Path, required=True)
    prove.add_argument("--out", type=Path, required=True)
    prove.add_argument("--witness-out", type=Path)
    prove.add_argument("--node-limit", type=int, default=100_000)
    prove.add_argument("--time-limit", type=float, default=300.0)
    prove.add_argument("--stable-node-limit", type=int, default=10_000_000)
    prove.add_argument("--matching-vertex-limit", type=int, default=22)
    prove.add_argument("--workers", type=int, default=1)
    prove.add_argument("--denominator", type=int, default=DENOMINATOR)
    prove.add_argument("--maximum-json-bytes", type=int, default=100_000_000)
    prove.add_argument("--maximum-proof-bytes", type=int, default=500_000_000)
    prove.add_argument("--maximum-proof-records", type=int, default=1_000_000)
    prove.set_defaults(function=prove_command)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        return arguments.function(arguments)
    except checked.VerificationError as error:
        print(f"CONDITIONAL DISCOVERY FAILED: {error}", file=sys.stderr)
        return 2
    except Exception as error:
        print(f"CONDITIONAL DISCOVERY FAILED: {type(error).__name__}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
