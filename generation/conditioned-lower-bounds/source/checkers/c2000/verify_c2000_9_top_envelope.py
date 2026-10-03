#!/usr/bin/env python3
"""Solver-free, fail-closed verifier for the C2000.9 size-6 packing envelope."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


class VerificationError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def reject_float(value: str) -> None:
    raise VerificationError(f"JSON floating-point value is forbidden: {value}")


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    require(path.stat().st_size <= 1024 * 1024, "certificate JSON exceeds 1 MiB")
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=strict_object,
        parse_float=reject_float,
        parse_constant=reject_float,
    )


def require_keys(value: Any, name: str, keys: set[str]) -> dict[str, Any]:
    require(type(value) is dict, f"{name} is not an object")
    actual = set(value)
    require(actual == keys, f"{name} keys differ: missing={sorted(keys-actual)}, extra={sorted(actual-keys)}")
    return value


def integer(value: Any, name: str, *, minimum: int = 0) -> int:
    require(type(value) is int and value >= minimum, f"{name} is not an integer at least {minimum}")
    return value


def integer_array(value: Any, name: str, *, maximum: int) -> list[int]:
    require(type(value) is list and len(value) <= maximum, f"{name} is not a bounded array")
    return [integer(item, f"{name}[{index}]") for index, item in enumerate(value)]


def semantic_hash(sets: list[tuple[int, ...]]) -> str:
    digest = hashlib.sha256()
    for stable_set in sets:
        digest.update((" ".join(map(str, stable_set)) + "\n").encode())
    return digest.hexdigest()


def verify(sets_path: Path, certificate_path: Path) -> None:
    stable_sets: list[tuple[int, ...]] = []
    with gzip.open(sets_path, "rt", encoding="utf-8") as handle:
        header = next(handle, None)
        require(header is not None and header.rstrip("\n") == "id\tsize\tvertices", "unexpected stable-set file header")
        for expected_id, line in enumerate(handle, 1):
            require(expected_id <= 90, "stable-set census exceeds the 90-row contract")
            require(len(line) <= 128, f"stable-set row {expected_id} exceeds 128 characters")
            fields = line.rstrip("\n").split("\t")
            require(len(fields) == 3, f"malformed stable-set row {expected_id}")
            set_id, size, vertices = fields
            try:
                parsed_id, parsed_size = int(set_id), int(size)
                stable_set = tuple(map(int, vertices.split()))
            except ValueError as exc:
                raise VerificationError(f"noninteger stable-set row {expected_id}") from exc
            require(parsed_id == expected_id, f"nonsequential stable-set id {parsed_id}")
            require(parsed_size == 6 and len(stable_set) == 6, f"wrong size at stable-set row {expected_id}")
            require(stable_set == tuple(sorted(stable_set)), f"noncanonical stable set {expected_id}")
            require(len(set(stable_set)) == 6 and all(1 <= vertex <= 2000 for vertex in stable_set), f"invalid vertices in stable set {expected_id}")
            stable_sets.append(stable_set)
    require(len(stable_sets) == 90, "stable-set census does not contain 90 rows")
    require(len(set(stable_sets)) == 90, "stable-set census contains a duplicate set")

    certificate = require_keys(
        load_json(certificate_path),
        "certificate",
        {"schema", "stable_set_census_sha256", "maximum_packing_size", "disjoint_packing_ids", "conflict_clique_cover", "arithmetic_profile"},
    )
    require(certificate["schema"] == "c2000_9_size6_packing_certificate_v1", "wrong certificate schema")
    require(type(certificate["stable_set_census_sha256"]) is str, "stable_set_census_sha256 is not a string")
    require(semantic_hash(stable_sets) == certificate["stable_set_census_sha256"], "stable-set semantic hash mismatch")
    require(integer(certificate["maximum_packing_size"], "maximum_packing_size") == 52, "maximum_packing_size is not 52")

    packing_ids = integer_array(certificate["disjoint_packing_ids"], "disjoint_packing_ids", maximum=52)
    require(len(packing_ids) == 52 and len(set(packing_ids)) == 52, "packing must contain 52 distinct ids")
    require(all(1 <= index <= 90 for index in packing_ids), "packing id out of range")
    packing = [stable_sets[index - 1] for index in packing_ids]
    covered_vertices = {vertex for stable_set in packing for vertex in stable_set}
    require(len(covered_vertices) == 6 * len(packing) == 312, "packing sets are not pairwise disjoint")

    raw_cover = certificate["conflict_clique_cover"]
    require(type(raw_cover) is list and len(raw_cover) == 52, "conflict cover must contain 52 cliques")
    cover: list[list[int]] = []
    for index, raw_clique in enumerate(raw_cover):
        clique = integer_array(raw_clique, f"conflict_clique_cover[{index}]", maximum=90)
        require(clique, f"conflict clique {index} is empty")
        require(len(clique) == len(set(clique)) and all(1 <= set_id <= 90 for set_id in clique), f"invalid ids in conflict clique {index}")
        cover.append(clique)
    flattened = [index for clique in cover for index in clique]
    require(sorted(flattened) == list(range(1, 91)), "conflict cliques do not partition all 90 sets")
    for clique_index, clique in enumerate(cover):
        for position, left in enumerate(clique):
            for right in clique[position + 1 :]:
                require(bool(set(stable_sets[left - 1]) & set(stable_sets[right - 1])), f"clique {clique_index} contains disjoint sets")

    profile = require_keys(certificate["arithmetic_profile"], "arithmetic_profile", {"q", "h", "vertices", "lower_bound"})
    q = integer_array(profile["q"], "q", maximum=6)
    h = integer_array(profile["h"], "h", maximum=6)
    require(len(q) == len(h) == 6, "arithmetic profile has wrong dimension")
    require(all(q[i] >= q[i + 1] for i in range(5)), "q is not nonincreasing")
    require(q[-1] == 52, "q_6 is not the certified cap 52")
    require(h == [q[i] - (q[i + 1] if i < 5 else 0) for i in range(6)], "h is not the inverse Ferrers profile")
    require(sum(q) == integer(profile["vertices"], "vertices") == 2000, "profile has wrong vertex mass")
    require(sum((i + 1) * h[i] for i in range(6)) == 2000, "h has wrong vertex mass")
    lower_bound = integer(profile["lower_bound"], "lower_bound")
    require(lower_bound == 381823, "claimed lower bound is not 381823")
    require(sum(value * (value + 1) // 2 for value in q) == lower_bound, "profile objective mismatch")

    arithmetic_candidates: list[tuple[int, list[int]]] = []
    for q6 in range(53):
        quotient, remainder = divmod(2000 - q6, 5)
        balanced = [quotient + 1] * remainder + [quotient] * (5 - remainder)
        require(balanced[-1] >= q6, "balanced arithmetic candidate violates monotonicity")
        candidate_q = balanced + [q6]
        candidate_value = sum(value * (value + 1) // 2 for value in candidate_q)
        arithmetic_candidates.append((candidate_value, candidate_q))
    best_value, best_q = min(arithmetic_candidates)
    require(best_q == q and best_value == lower_bound == 381823, "certificate is not the exact arithmetic minimum")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sets", type=Path, required=True)
    parser.add_argument("--certificate", type=Path, required=True)
    try:
        args = parser.parse_args(argv[1:])
        verify(args.sets, args.certificate)
    except Exception as exc:
        print(f"REJECT: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print("C2000.9 TOP ENVELOPE VERIFICATION: SUCCESS")
    print("maximum disjoint size-6 classes: 52")
    print("certified arithmetic lower bound: 381823")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
