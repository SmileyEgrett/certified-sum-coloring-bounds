"""Fail-closed helpers shared by the C2000.9 standard-library checkers."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


GRAPH_SHA256 = "aa4b1d7df7f9c1afbf8c9f35fcf5bdfc6370fd27db5c9f3fd5409dfd0d164f16"
DECIMAL = re.compile(r"0|[1-9][0-9]*\Z")


class VerificationError(RuntimeError):
    """An input failed a proof obligation."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def pin_one_cpu() -> None:
    """Keep verification within one CPU when the platform supports affinity."""
    if hasattr(os, "sched_getaffinity") and hasattr(os, "sched_setaffinity"):
        available = os.sched_getaffinity(0)
        require(bool(available), "process has no available CPU")
        os.sched_setaffinity(0, {min(available)})


def _reject_float(value: str) -> None:
    raise VerificationError(f"JSON floating-point value is forbidden: {value}")


def _reject_constant(value: str) -> None:
    raise VerificationError(f"non-finite JSON value is forbidden: {value}")


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise VerificationError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path, *, maximum_bytes: int = 8 * 1024 * 1024) -> Any:
    try:
        require(path.stat().st_size <= maximum_bytes, f"JSON input exceeds {maximum_bytes} bytes: {path}")
        return json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError(f"cannot parse {path}: {exc}") from exc


def require_object(value: Any, name: str, keys: set[str]) -> dict[str, Any]:
    require(type(value) is dict, f"{name} is not a JSON object")
    actual = set(value)
    require(actual == keys, f"{name} keys differ: missing={sorted(keys-actual)}, extra={sorted(actual-keys)}")
    return value


def require_list(value: Any, name: str, *, maximum: int) -> list[Any]:
    require(type(value) is list, f"{name} is not a JSON array")
    require(len(value) <= maximum, f"{name} exceeds the size limit {maximum}")
    return value


def json_uint(value: Any, name: str, *, positive: bool = False) -> int:
    require(type(value) is int, f"{name} is not a JSON integer")
    require(value > 0 if positive else value >= 0, f"{name} has invalid sign")
    return value


def decimal_uint(value: Any, name: str, *, positive: bool = False) -> int:
    require(type(value) is str and DECIMAL.fullmatch(value) is not None, f"{name} is not a canonical decimal string")
    result = int(value)
    require(result > 0 if positive else result >= 0, f"{name} has invalid sign")
    return result


def vertex_list(value: Any, name: str, *, minimum_size: int, maximum_size: int) -> list[int]:
    raw = require_list(value, name, maximum=maximum_size)
    require(minimum_size <= len(raw) <= maximum_size, f"{name} has invalid length")
    vertices = [json_uint(v, f"{name}[{i}]", positive=True) for i, v in enumerate(raw)]
    require(all(v <= 2000 for v in vertices), f"{name} contains an out-of-range vertex")
    require(vertices == sorted(vertices), f"{name} is not in canonical increasing order")
    require(len(vertices) == len(set(vertices)), f"{name} contains a duplicate vertex")
    return vertices


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_graph(path: Path) -> tuple[bytes, list[int]]:
    try:
        require(path.stat().st_size <= 24 * 1024 * 1024, "graph input exceeds 24 MiB")
        raw = path.read_bytes()
        lines = raw.decode("ascii").splitlines()
    except (OSError, UnicodeError) as exc:
        raise VerificationError(f"cannot read graph {path}: {exc}") from exc
    require(sha256_bytes(raw) == GRAPH_SHA256, "graph hash mismatch")

    adjacency: list[int] | None = None
    declared_edges: int | None = None
    edge_count = 0
    for line_number, raw_line in enumerate(lines, 1):
        tokens = raw_line.split()
        if not tokens or tokens[0] == "c":
            continue
        if tokens[0] == "p":
            require(adjacency is None, f"duplicate or late graph header at line {line_number}")
            require(len(tokens) == 4 and tokens[1] in {"edge", "edges", "col"}, f"bad graph header at line {line_number}")
            try:
                vertices, declared_edges = int(tokens[2]), int(tokens[3])
            except ValueError as exc:
                raise VerificationError(f"noninteger graph header at line {line_number}") from exc
            require(vertices == 2000 and declared_edges == 1799532, "wrong graph dimensions")
            adjacency = [0] * vertices
        elif tokens[0] == "e":
            require(adjacency is not None, f"edge before graph header at line {line_number}")
            require(len(tokens) == 3, f"bad edge record at line {line_number}")
            try:
                left, right = int(tokens[1]) - 1, int(tokens[2]) - 1
            except ValueError as exc:
                raise VerificationError(f"noninteger edge at line {line_number}") from exc
            require(0 <= left < 2000 and 0 <= right < 2000 and left != right, f"invalid edge at line {line_number}")
            require(not (adjacency[left] >> right) & 1, f"duplicate edge at line {line_number}")
            adjacency[left] |= 1 << right
            adjacency[right] |= 1 << left
            edge_count += 1
        else:
            raise VerificationError(f"unexpected graph record {tokens[0]!r} at line {line_number}")
    require(adjacency is not None and declared_edges is not None, "missing graph header")
    require(edge_count == declared_edges == 1799532, "graph edge count mismatch")
    return raw, adjacency


def stable(vertices_one_based: list[int], adjacency: list[int], name: str) -> None:
    zero_based = [v - 1 for v in vertices_one_based]
    for position, left in enumerate(zero_based):
        require(
            all(not ((adjacency[left] >> right) & 1) for right in zero_based[position + 1 :]),
            f"{name} is not stable",
        )
