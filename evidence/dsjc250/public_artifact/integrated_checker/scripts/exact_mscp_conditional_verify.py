#!/usr/bin/env python3
"""Exact verifier for certified conditional MSCP envelope campaigns.

The verifier reconstructs the graph, stable-set families, maximum-class
packings, arithmetic profile frontier, certificate models, proof trees,
matching barriers, and colorings.  Optimizer statuses and floating-point
metadata are never proof inputs.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from itertools import combinations
from typing import Any, Callable, Iterable, Iterator, Mapping, Sequence

CAMPAIGN_SCHEMA = "exact_mscp_conditional_campaign_v1"
VERIFY_SCHEMA = "exact_mscp_conditional_verification_v1"
MODEL_SCHEMA = "exact_mscp_conditional_model_v1"
TREE_CERT_SCHEMA = "exact_mscp_conditional_tree_certificate_v1"
TREE_PROOF_SCHEMA = "exact_mscp_conditional_tree_proof_v1"
DUAL_SCHEMA = "exact_mscp_conditional_dual_v1"
WITNESS_SCHEMA = "exact_mscp_conditional_witness_bundle_v1"
_HEX = frozenset("0123456789abcdef")


class VerificationError(RuntimeError):
    """A fail-closed verification error."""


def fail(message: str) -> None:
    raise VerificationError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def is_sha256(text: str) -> bool:
    return len(text) == 64 and all(ch in _HEX for ch in text)


def safe_identifier(text: str) -> bool:
    return bool(text) and len(text) <= 128 and all(
        ch.isalnum() or ch in "._-" for ch in text
    )


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        fail(f"cannot safely open artifact {path}: {error}")
    digest = hashlib.sha256()
    with os.fdopen(descriptor, "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_regular_nonsymlink(path: Path, context: str) -> Path:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        try:
            status = current.lstat()
        except FileNotFoundError as error:
            fail(f"missing {context}: {current}")
        if stat.S_ISLNK(status.st_mode):
            fail(f"symbolic-link component rejected for {context}: {current}")
    try:
        status = absolute.stat()
    except OSError as error:
        fail(f"cannot stat {context} {absolute}: {error}")
    if not stat.S_ISREG(status.st_mode):
        fail(f"{context} is not a regular file: {absolute}")
    return absolute


def resolve_relative(owner: Path, text: str, context: str) -> Path:
    relative = Path(text)
    if not text or relative.is_absolute() or ".." in relative.parts or text.startswith("./"):
        fail(f"unsafe {context} path in {owner}: {text!r}")
    return require_regular_nonsymlink(owner.parent / relative, context)


def parse_canonical_int(text: str, context: str, *, nonnegative: bool = False) -> int:
    if not text or text in {"+", "-"}:
        fail(f"invalid integer for {context}: {text!r}")
    if text.startswith("+"):
        digits = text[1:]
    elif text.startswith("-"):
        digits = text[1:]
    else:
        digits = text
    if not digits.isdigit():
        fail(f"invalid integer for {context}: {text!r}")
    value = int(text)
    if str(value) != text and not (text.startswith("+") and str(value) == text[1:]):
        fail(f"noncanonical integer for {context}: {text!r}")
    if nonnegative and value < 0:
        fail(f"negative integer for {context}: {text!r}")
    return value


def parse_properties_rows(path: Path, row_names: set[str]) -> tuple[dict[str, str], dict[str, list[tuple[int, list[str]]]]]:
    path = require_regular_nonsymlink(path, "properties artifact")
    properties: dict[str, str] = {}
    rows = {name: [] for name in row_names}
    row_section = False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        fail(f"cannot read properties artifact {path}: {error}")
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        tag = line.split("\t", 1)[0]
        if tag in rows:
            row_section = True
            rows[tag].append((number, line.split("\t")))
            continue
        if row_section:
            fail(f"{path}:{number}: property after row section")
        if "=" not in line:
            fail(f"{path}:{number}: expected key=value or known row")
        key, value = (part.strip() for part in line.split("=", 1))
        if not key or key in properties:
            fail(f"{path}:{number}: duplicate or empty property")
        properties[key] = value
    return properties, rows


def require_exact_keys(actual: Mapping[str, Any], expected: set[str], context: str) -> None:
    missing = sorted(expected - set(actual))
    extra = sorted(set(actual) - expected)
    if missing or extra:
        fail(f"{context}: key mismatch: missing={missing}, extra={extra}")


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            fail(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_float(text: str) -> Any:
    fail(f"floating-point JSON value is not proof data: {text}")


def load_json_bytes(data: bytes, context: str) -> Any:
    try:
        text = data.decode("utf-8")
    except UnicodeError as error:
        fail(f"{context}: invalid UTF-8: {error}")
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_float=_reject_float,
            parse_constant=_reject_float,
        )
    except VerificationError:
        raise
    except json.JSONDecodeError as error:
        fail(f"{context}: malformed JSON: {error}")


def load_json(path: Path, context: str, maximum_bytes: int) -> Any:
    path = require_regular_nonsymlink(path, context)
    size = path.stat().st_size
    if size <= 0 or size > maximum_bytes:
        fail(f"{context} size outside configured limit: {size}")
    return load_json_bytes(path.read_bytes(), context)


def load_gzip_json(path: Path, context: str, maximum_bytes: int) -> Any:
    path = require_regular_nonsymlink(path, context)
    output = bytearray()
    try:
        with gzip.open(path, "rb") as stream:
            while True:
                block = stream.read(1024 * 1024)
                if not block:
                    break
                output.extend(block)
                if len(output) > maximum_bytes:
                    fail(f"{context} decompressed beyond configured limit")
    except (OSError, EOFError) as error:
        fail(f"{context}: malformed gzip stream: {error}")
    return load_json_bytes(bytes(output), context)


@dataclass(frozen=True)
class Graph:
    vertices: int
    edges: frozenset[tuple[int, int]]
    adjacency: tuple[int, ...]
    complement: tuple[int, ...]
    raw_sha256: str
    canonical_sha256: str


def parse_graph(path: Path) -> Graph:
    path = require_regular_nonsymlink(path, "DIMACS graph")
    raw = path.read_bytes()
    raw_hash = sha256_bytes(raw)
    vertices: int | None = None
    declared: int | None = None
    edge_records = 0
    edges: set[tuple[int, int]] = set()
    header_seen = False
    for number, raw_line in enumerate(raw.splitlines(), 1):
        try:
            line = raw_line.decode("ascii").strip()
        except UnicodeDecodeError:
            fail(f"{path}:{number}: non-ASCII DIMACS input")
        if not line:
            continue
        fields = line.split()
        if fields[0] == "c":
            continue
        if fields[0] == "p":
            if header_seen or len(fields) != 4 or fields[1] not in {"edge", "edges", "col"}:
                fail(f"{path}:{number}: malformed or duplicate DIMACS header")
            vertices = parse_canonical_int(fields[2], "DIMACS vertex count", nonnegative=True)
            declared = parse_canonical_int(fields[3], "DIMACS edge count", nonnegative=True)
            if vertices <= 0:
                fail(f"{path}:{number}: vertex count must be positive")
            header_seen = True
            continue
        if fields[0] == "e":
            if not header_seen or len(fields) != 3 or vertices is None:
                fail(f"{path}:{number}: malformed edge record")
            left = parse_canonical_int(fields[1], "edge endpoint")
            right = parse_canonical_int(fields[2], "edge endpoint")
            if not (1 <= left <= vertices and 1 <= right <= vertices) or left == right:
                fail(f"{path}:{number}: invalid edge")
            edge = (left, right) if left < right else (right, left)
            if edge in edges:
                fail(f"{path}:{number}: duplicate edge")
            edges.add(edge)
            edge_records += 1
            continue
        fail(f"{path}:{number}: unknown DIMACS record {fields[0]!r}")
    if not header_seen or vertices is None or declared is None:
        fail(f"{path}: missing DIMACS header")
    if edge_records != declared or len(edges) != declared:
        fail(f"{path}: declared/record/unique edge count mismatch")
    adjacency = [0] * (vertices + 1)
    full = sum(1 << vertex for vertex in range(1, vertices + 1))
    for left, right in edges:
        adjacency[left] |= 1 << right
        adjacency[right] |= 1 << left
    complement = [0] * (vertices + 1)
    for vertex in range(1, vertices + 1):
        complement[vertex] = full & ~adjacency[vertex] & ~(1 << vertex)
    canonical = (
        f"exact_mscp_graph_v1\nvertices {vertices}\n"
        + "".join(f"{left} {right}\n" for left, right in sorted(edges))
    ).encode("ascii")
    return Graph(
        vertices=vertices,
        edges=frozenset(edges),
        adjacency=tuple(adjacency),
        complement=tuple(complement),
        raw_sha256=raw_hash,
        canonical_sha256=sha256_bytes(canonical),
    )


def iter_bits(mask: int) -> Iterator[int]:
    while mask:
        bit = mask & -mask
        yield bit.bit_length() - 1
        mask ^= bit


@dataclass(frozen=True)
class StableEnumeration:
    by_size: dict[int, tuple[tuple[int, ...], ...]]
    nodes: int


def enumerate_stable_sets(graph: Graph, maximum_size: int, node_limit: int) -> StableEnumeration:
    if maximum_size < 1:
        fail("stable-set enumeration maximum size must be positive")
    families: dict[int, list[tuple[int, ...]]] = {
        size: [] for size in range(1, maximum_size + 1)
    }
    full = sum(1 << vertex for vertex in range(1, graph.vertices + 1))
    nodes = 1

    def extend(prefix: tuple[int, ...], candidates: int) -> None:
        nonlocal nodes
        remaining = candidates
        while remaining:
            bit = remaining & -remaining
            vertex = bit.bit_length() - 1
            remaining ^= bit
            child = prefix + (vertex,)
            nodes += 1
            if nodes > node_limit:
                fail("stable-set enumeration hit configured node limit")
            families[len(child)].append(child)
            if len(child) < maximum_size:
                extend(child, remaining & graph.complement[vertex])

    extend((), full)
    return StableEnumeration(
        {size: tuple(values) for size, values in families.items()}, nodes
    )


def is_stable(vertices: Sequence[int], graph: Graph) -> bool:
    if len(vertices) != len(set(vertices)):
        return False
    return all(not ((graph.adjacency[left] >> right) & 1) for left, right in combinations(vertices, 2))


def stable_family_text(family: Sequence[Sequence[int]]) -> str:
    return "".join(" ".join(str(vertex) for vertex in stable) + "\n" for stable in family)


def parse_simple_properties(path: Path) -> dict[str, str]:
    path = require_regular_nonsymlink(path, "properties file")
    result: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            fail(f"{path}:{number}: malformed property")
        key, value = line.split("=", 1)
        if not key or key in result:
            fail(f"{path}:{number}: duplicate or empty property")
        result[key] = value
    return result


def read_disk_stable_families(root: Path, independent: Mapping[int, Sequence[tuple[int, ...]]], maximum_size: int) -> dict[int, tuple[tuple[int, ...], ...]]:
    manifest_path = require_regular_nonsymlink(root / "manifest.properties", "stable-family manifest")
    manifest = parse_simple_properties(manifest_path)
    if manifest.get("schema") != "exact_mscp_stable_set_manifest_v1":
        fail("unexpected stable-family manifest schema")
    result: dict[int, tuple[tuple[int, ...], ...]] = {}
    for size in range(1, maximum_size + 1):
        count_key = f"size.{size}.count"
        hash_key = f"size.{size}.sha256"
        if count_key not in manifest or hash_key not in manifest:
            fail(f"stable-family manifest omits size {size}")
        expected_count = parse_canonical_int(manifest[count_key], f"stable count {size}", nonnegative=True)
        expected_hash = manifest[hash_key]
        if not is_sha256(expected_hash):
            fail(f"stable-family manifest has malformed hash for size {size}")
        csv_path = require_regular_nonsymlink(root / f"size_{size}.csv", f"stable size-{size} CSV")
        rows: list[tuple[int, ...]] = []
        with csv_path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.reader(stream)
            try:
                header = next(reader)
            except StopIteration:
                fail(f"empty stable-family CSV {csv_path}")
            if header != ["id", "size", "vertices"]:
                fail(f"unexpected stable-family CSV header in {csv_path}")
            previous: tuple[int, ...] | None = None
            for line_number, fields in enumerate(reader, 2):
                if len(fields) != 3:
                    fail(f"{csv_path}:{line_number}: malformed row")
                identifier = parse_canonical_int(fields[0], "stable-set ID", nonnegative=True)
                row_size = parse_canonical_int(fields[1], "stable-set size", nonnegative=True)
                if identifier != len(rows) + 1 or row_size != size:
                    fail(f"{csv_path}:{line_number}: noncanonical ID or size")
                vertices = tuple(parse_canonical_int(field, "stable-set vertex") for field in fields[2].split())
                if len(vertices) != size or tuple(sorted(vertices)) != vertices or len(set(vertices)) != size:
                    fail(f"{csv_path}:{line_number}: malformed stable set")
                if previous is not None and previous >= vertices:
                    fail(f"{csv_path}:{line_number}: duplicate or reordered stable set")
                previous = vertices
                rows.append(vertices)
        actual_hash = sha256_bytes(stable_family_text(rows).encode("ascii"))
        if len(rows) != expected_count or actual_hash != expected_hash:
            fail(f"stable-family count/hash mismatch for size {size}")
        if tuple(rows) != tuple(independent[size]):
            fail(f"disk stable-family semantics differ from graph reconstruction at size {size}")
        result[size] = tuple(rows)
    return result


def enumerate_top_packings(maximum_sets: Sequence[tuple[int, ...]], vertex_count: int, limit: int) -> tuple[int, dict[int, tuple[tuple[tuple[int, ...], ...], ...]]]:
    if not maximum_sets:
        fail("maximum stable-set family is empty")
    if len(maximum_sets[0]) == 1:
        packing = tuple(maximum_sets)
        return len(packing), {len(packing): (packing,)}
    masks = [sum(1 << vertex for vertex in stable) for stable in maximum_sets]
    by_count: dict[int, list[tuple[tuple[int, ...], ...]]] = {0: [()]}
    produced = 1

    def search(start: int, chosen: tuple[int, ...], used: int) -> None:
        nonlocal produced
        for index in range(start, len(maximum_sets)):
            if used & masks[index]:
                continue
            next_chosen = chosen + (index,)
            packing = tuple(maximum_sets[item] for item in next_chosen)
            by_count.setdefault(len(packing), []).append(packing)
            produced += 1
            if produced > limit:
                fail("maximum-class packing enumeration hit configured limit")
            search(index + 1, next_chosen, used | masks[index])

    search(0, (), 0)
    packing_number = max(by_count)
    normalized = {
        count: tuple(sorted(values)) for count, values in by_count.items()
    }
    return packing_number, normalized


@dataclass(frozen=True)
class Profile:
    h: tuple[int, ...]
    ge: tuple[int, ...]
    strength: int
    objective: int


def profile_from_h(h: Sequence[int]) -> Profile:
    alpha = len(h) - 1
    running = 0
    ge_reversed: list[int] = []
    for size in range(alpha, 0, -1):
        running += h[size]
        ge_reversed.append(running)
    ge = tuple(reversed(ge_reversed))
    objective = sum(value * (value + 1) // 2 for value in ge)
    return Profile(tuple(h), ge, ge[0] if ge else 0, objective)


def enumerate_profiles(vertices: int, alpha: int, top_packing_number: int, threshold: int, node_limit: int) -> tuple[tuple[Profile, ...], int]:
    if alpha <= 0:
        fail("maximum class size must be positive")
    if alpha == 1:
        profile = profile_from_h((0, vertices))
        return ((profile,) if profile.objective <= threshold else ()), 1
    h = [0] * (alpha + 1)
    profiles: list[Profile] = []
    nodes = 0

    def search(size: int, remaining: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > node_limit:
            fail("profile enumeration hit configured node limit")
        if size == 1:
            h[1] = remaining
            profile = profile_from_h(h)
            if profile.objective <= threshold:
                profiles.append(profile)
            return
        maximum = remaining // size
        if size == alpha:
            maximum = min(maximum, top_packing_number)
        for count in range(maximum + 1):
            h[size] = count
            search(size - 1, remaining - size * count)
        h[size] = 0

    search(alpha, vertices)
    profiles.sort(key=lambda profile: (profile.objective, profile.h[1:]))
    unique = {profile.h: profile for profile in profiles}
    if len(unique) != len(profiles):
        fail("profile enumeration produced a duplicate")
    return tuple(profiles), nodes


def profile_key(profile: Profile) -> tuple[int, ...]:
    return profile.h[1:]


def profile_csv_rows(path: Path, alpha: int) -> tuple[Profile, ...]:
    path = require_regular_nonsymlink(path, "generator profile CSV")
    result: list[Profile] = []
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        expected = ["id", "strength", "objective"] + [f"h{s}" for s in range(1, alpha + 1)] + [f"ge{s}" for s in range(1, alpha + 1)]
        if reader.fieldnames != expected:
            fail(f"unexpected profile CSV header in {path}")
        for number, row in enumerate(reader, 2):
            if any(value is None for value in row.values()):
                fail(f"{path}:{number}: malformed profile CSV row")
            h = [0] + [parse_canonical_int(row[f"h{s}"], f"{path}:{number} h{s}", nonnegative=True) for s in range(1, alpha + 1)]
            profile = profile_from_h(h)
            expected_identifier = f"q{profile.strength}_" + "_".join(
                f"h{size}_{profile.h[size]}" for size in range(1, alpha + 1)
            )
            if row["id"] != expected_identifier:
                fail(f"{path}:{number}: forged profile identifier")
            if profile.strength != parse_canonical_int(row["strength"], f"{path}:{number} strength", nonnegative=True) or profile.objective != parse_canonical_int(row["objective"], f"{path}:{number} objective", nonnegative=True):
                fail(f"{path}:{number}: forged strength/objective")
            for size in range(1, alpha + 1):
                if parse_canonical_int(row[f"ge{size}"], f"{path}:{number} ge{size}", nonnegative=True) != profile.ge[size - 1]:
                    fail(f"{path}:{number}: forged GE coordinate")
            result.append(profile)
    if len({profile.h for profile in result}) != len(result):
        fail(f"duplicate profile in {path}")
    return tuple(result)


@dataclass(frozen=True)
class LayeredConclusion:
    certificate_id: str
    minimum_size: int
    bound: int
    conditions: tuple[tuple[int, int], ...]
    kind: str

    def rejects(self, profile: Profile) -> bool:
        return all(profile.h[size] == count for size, count in self.conditions) and profile.ge[self.minimum_size - 1] > self.bound


@dataclass(frozen=True)
class ConditionalConclusion:
    certificate_id: str
    fixed_top_classes: tuple[tuple[int, ...], ...]
    score_by_size: tuple[tuple[int, int], ...]
    type_caps: tuple[tuple[int, int], ...]
    strict_target: int
    kind: str
    proof_stats: tuple[tuple[str, int], ...] = ()

    @property
    def minimum_scored_size(self) -> int:
        return min(size for size, _ in self.score_by_size)

    def rejects(self, profile: Profile, packing: tuple[tuple[int, ...], ...]) -> bool:
        if packing != self.fixed_top_classes:
            return False
        alpha = len(profile.h) - 1
        if profile.h[alpha] != len(packing):
            return False
        if any(profile.h[size] > cap for size, cap in self.type_caps):
            return False
        score = sum(profile.h[size] * coefficient for size, coefficient in self.score_by_size)
        return score >= self.strict_target


def verify_graph_binding(properties: Mapping[str, str], graph: Graph, alpha: int, context: str) -> None:
    if properties.get("graph_raw_sha256") != graph.raw_sha256 or properties.get("graph_canonical_sha256") != graph.canonical_sha256:
        fail(f"{context}: graph hash mismatch")
    if parse_canonical_int(properties.get("vertices", ""), f"{context} vertices", nonnegative=True) != graph.vertices:
        fail(f"{context}: vertex count mismatch")
    if parse_canonical_int(properties.get("maximum_class_size", ""), f"{context} maximum class size", nonnegative=True) != alpha:
        fail(f"{context}: maximum class size mismatch")


def verify_layered_rational(path: Path, expected_id: str, graph: Graph, stable_sets: Mapping[int, Sequence[tuple[int, ...]]], alpha: int) -> LayeredConclusion:
    properties, rows = parse_properties_rows(path, {"condition", "weight"})
    require_exact_keys(properties, {
        "schema", "certificate_id", "graph_raw_sha256", "graph_canonical_sha256",
        "vertices", "maximum_class_size", "minimum_class_size", "claimed_bound",
        "denominator", "rhs_numerator", "condition_count",
    }, str(path))
    if properties["schema"] != "exact_mscp_layered_rational_v1" or properties["certificate_id"] != expected_id:
        fail(f"{path}: schema/certificate identity mismatch")
    verify_graph_binding(properties, graph, alpha, str(path))
    minimum_size = parse_canonical_int(properties["minimum_class_size"], "minimum class size", nonnegative=True)
    bound = parse_canonical_int(properties["claimed_bound"], "claimed bound", nonnegative=True)
    denominator = parse_canonical_int(properties["denominator"], "denominator", nonnegative=True)
    rhs = parse_canonical_int(properties["rhs_numerator"], "RHS numerator")
    if not (1 <= minimum_size <= alpha and denominator > 0 and rhs >= 0):
        fail(f"{path}: invalid conclusion arithmetic")
    condition_count = parse_canonical_int(properties["condition_count"], "condition count", nonnegative=True)
    if condition_count != len(rows["condition"]):
        fail(f"{path}: condition count mismatch")
    conditions: list[tuple[int, int]] = []
    multipliers: dict[int, int] = {}
    previous = 0
    for number, fields in rows["condition"]:
        if len(fields) != 4:
            fail(f"{path}:{number}: malformed condition row")
        size = parse_canonical_int(fields[1], "condition size", nonnegative=True)
        count = parse_canonical_int(fields[2], "condition count", nonnegative=True)
        multiplier = parse_canonical_int(fields[3], "condition multiplier")
        if not (minimum_size <= size <= alpha) or size <= previous:
            fail(f"{path}:{number}: condition order/range mismatch")
        previous = size
        conditions.append((size, count))
        multipliers[size] = multiplier
    if len(rows["weight"]) != graph.vertices:
        fail(f"{path}: wrong number of vertex weights")
    weights = [0] * (graph.vertices + 1)
    for expected_vertex, (number, fields) in enumerate(rows["weight"], 1):
        if len(fields) != 3 or parse_canonical_int(fields[1], "weight vertex", nonnegative=True) != expected_vertex:
            fail(f"{path}:{number}: noncanonical weight row")
        weights[expected_vertex] = parse_canonical_int(fields[2], "vertex weight", nonnegative=True)
    if sum(weights) + sum(multipliers[size] * count for size, count in conditions) != rhs:
        fail(f"{path}: RHS arithmetic mismatch")
    for size in range(minimum_size, alpha + 1):
        multiplier = multipliers.get(size, 0)
        for stable in stable_sets[size]:
            if sum(weights[vertex] for vertex in stable) + multiplier < denominator:
                fail(f"{path}: violated stable-column inequality for {stable}")
    if rhs // denominator != bound:
        fail(f"{path}: floor bound mismatch")
    return LayeredConclusion(expected_id, minimum_size, bound, tuple(conditions), "layered_rational")


def parse_opb_constraints(data: bytes, context: str) -> tuple[int, int, list[tuple[tuple[tuple[int, int], ...], str, int]]]:
    try:
        text = data.decode("ascii")
    except UnicodeError:
        fail(f"{context}: OPB is not ASCII")
    variable_count: int | None = None
    declared_constraints: int | None = None
    constraints: list[tuple[tuple[tuple[int, int], ...], str, int]] = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("*"):
            if line.startswith("* #variable="):
                fields = line.replace("=", " ").split()
                try:
                    variable_count = int(fields[2])
                    declared_constraints = int(fields[4])
                except (IndexError, ValueError):
                    fail(f"{context}:{number}: malformed OPB header")
            continue
        if not line.endswith(";"):
            fail(f"{context}:{number}: unterminated constraint")
        tokens = line[:-1].split()
        sense_index = next((i for i, token in enumerate(tokens) if token in {"<=", ">=", "="}), -1)
        if sense_index <= 0 or sense_index + 2 != len(tokens):
            fail(f"{context}:{number}: malformed constraint")
        terms: list[tuple[int, int]] = []
        if sense_index % 2:
            fail(f"{context}:{number}: malformed coefficient-variable pairs")
        for index in range(0, sense_index, 2):
            coefficient = parse_canonical_int(tokens[index], "OPB coefficient")
            variable = tokens[index + 1]
            if not variable.startswith("x"):
                fail(f"{context}:{number}: malformed OPB variable")
            variable_id = parse_canonical_int(variable[1:], "OPB variable", nonnegative=True)
            if variable_id <= 0:
                fail(f"{context}:{number}: OPB variables are one-based")
            terms.append((variable_id, coefficient))
        rhs = parse_canonical_int(tokens[-1], "OPB RHS")
        constraints.append((tuple(terms), tokens[sense_index], rhs))
    if variable_count is None or declared_constraints is None:
        fail(f"{context}: missing OPB header")
    if declared_constraints != len(constraints):
        fail(f"{context}: OPB constraint count mismatch")
    return variable_count, declared_constraints, constraints


def expected_layered_opb(graph: Graph, stable_sets: Mapping[int, Sequence[tuple[int, ...]]], alpha: int, minimum_size: int, conditions: Sequence[tuple[int, int]], claimed_bound: int) -> tuple[int, list[tuple[tuple[tuple[int, int], ...], str, int]]]:
    columns: list[tuple[int, ...]] = []
    sizes: list[int] = []
    for size in range(alpha, minimum_size - 1, -1):
        for stable in stable_sets[size]:
            columns.append(stable)
            sizes.append(size)
    expected: list[tuple[tuple[tuple[int, int], ...], str, int]] = []
    for vertex in range(1, graph.vertices + 1):
        terms = tuple((index + 1, 1) for index, stable in enumerate(columns) if vertex in stable)
        if terms:
            expected.append((terms, "<=", 1))
    for size, count in conditions:
        terms = tuple((index + 1, 1) for index, column_size in enumerate(sizes) if column_size == size)
        expected.append((terms, "=", count))
    expected.append((tuple((index + 1, 1) for index in range(len(columns))), ">=", claimed_bound + 1))
    return len(columns), expected


def run_veripb_snapshot(veripb: Path, opb_bytes: bytes, proof_bytes: bytes, expected_opb_hash: str, expected_proof_hash: str, success_exit: int, success_marker: str, timeout_seconds: int) -> dict[str, Any]:
    veripb = require_regular_nonsymlink(veripb, "VeriPB executable")
    if not os.access(veripb, os.X_OK):
        fail(f"VeriPB is not executable: {veripb}")
    tool_hash = sha256_file(veripb)
    with tempfile.TemporaryDirectory(prefix="exact_mscp_conditional_veripb_") as raw:
        directory = Path(raw)
        opb = directory / "statement.opb"
        proof = directory / "certificate.pbp"
        for path, data in ((opb, opb_bytes), (proof, proof_bytes)):
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o400)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        if sha256_file(opb) != expected_opb_hash or sha256_file(proof) != expected_proof_hash:
            fail("private VeriPB snapshot hash mismatch")
        try:
            completed = subprocess.run(
                [str(veripb), str(opb), str(proof)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                encoding="utf-8",
                errors="replace",
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            fail("VeriPB verification timed out")
        if sha256_file(veripb) != tool_hash:
            fail("VeriPB executable changed during verification")
        if completed.returncode != success_exit or success_marker not in completed.stdout:
            fail("VeriPB did not produce the configured verified result")
        return {
            "tool_sha256": tool_hash,
            "exit": completed.returncode,
            "marker_sha256": sha256_bytes(success_marker.encode("utf-8")),
        }


def verify_layered_veripb(path: Path, expected_id: str, graph: Graph, stable_sets: Mapping[int, Sequence[tuple[int, ...]]], alpha: int, veripb: Path | None, timeout_seconds: int) -> tuple[LayeredConclusion, dict[str, Any]]:
    properties, rows = parse_properties_rows(path, {"condition"})
    require_exact_keys(properties, {
        "schema", "certificate_id", "graph_raw_sha256", "graph_canonical_sha256",
        "vertices", "maximum_class_size", "minimum_class_size", "claimed_bound",
        "condition_count", "opb_file", "opb_sha256", "proof_file", "proof_sha256",
        "veripb_success_exit", "veripb_success_marker",
    }, str(path))
    if properties["schema"] != "exact_mscp_layered_veripb_v1" or properties["certificate_id"] != expected_id:
        fail(f"{path}: schema/certificate identity mismatch")
    verify_graph_binding(properties, graph, alpha, str(path))
    minimum_size = parse_canonical_int(properties["minimum_class_size"], "minimum class size", nonnegative=True)
    bound = parse_canonical_int(properties["claimed_bound"], "claimed bound", nonnegative=True)
    condition_count = parse_canonical_int(properties["condition_count"], "condition count", nonnegative=True)
    if condition_count != len(rows["condition"]):
        fail(f"{path}: condition count mismatch")
    conditions: list[tuple[int, int]] = []
    previous = 0
    for number, fields in rows["condition"]:
        if len(fields) != 3:
            fail(f"{path}:{number}: malformed condition row")
        size = parse_canonical_int(fields[1], "condition size", nonnegative=True)
        count = parse_canonical_int(fields[2], "condition count", nonnegative=True)
        if size <= previous or not (minimum_size <= size <= alpha):
            fail(f"{path}:{number}: invalid condition order/range")
        previous = size
        conditions.append((size, count))
    opb = resolve_relative(path, properties["opb_file"], "layered OPB")
    proof = resolve_relative(path, properties["proof_file"], "layered proof")
    opb_hash = properties["opb_sha256"]
    proof_hash = properties["proof_sha256"]
    if not is_sha256(opb_hash) or not is_sha256(proof_hash) or sha256_file(opb) != opb_hash or sha256_file(proof) != proof_hash:
        fail(f"{path}: OPB/proof hash mismatch")
    variable_count, _, constraints = parse_opb_constraints(opb.read_bytes(), str(opb))
    expected_variables, expected_constraints = expected_layered_opb(graph, stable_sets, alpha, minimum_size, conditions, bound)
    if variable_count != expected_variables or constraints != expected_constraints:
        fail(f"{path}: OPB does not exactly reconstruct the graph statement")
    if veripb is None:
        fail(f"{path}: VeriPB certificate configured but no verifier supplied")
    success_exit = parse_canonical_int(properties["veripb_success_exit"], "VeriPB success exit")
    marker = properties["veripb_success_marker"]
    if not marker:
        fail(f"{path}: empty VeriPB success marker")
    tool = run_veripb_snapshot(veripb, opb.read_bytes(), proof.read_bytes(), opb_hash, proof_hash, success_exit, marker, timeout_seconds)
    return LayeredConclusion(expected_id, minimum_size, bound, tuple(conditions), "layered_veripb"), tool


def canonical_top(classes: Sequence[Sequence[int]]) -> tuple[tuple[int, ...], ...]:
    normalized = tuple(tuple(item) for item in classes)
    if tuple(sorted(normalized)) != normalized:
        fail("fixed top classes are not in canonical order")
    return normalized


def verify_conditional_dual(path: Path, expected_id: str, graph: Graph, stable_sets: Mapping[int, Sequence[tuple[int, ...]]], alpha: int) -> ConditionalConclusion:
    properties, rows = parse_properties_rows(path, {"fixed_top_set", "score", "type_cap", "weight"})
    require_exact_keys(properties, {
        "schema", "certificate_id", "graph_raw_sha256", "graph_canonical_sha256",
        "vertices", "maximum_class_size", "fixed_top_count", "score_size_count",
        "type_cap_count", "denominator", "strict_target", "rhs_numerator",
    }, str(path))
    if properties["schema"] != DUAL_SCHEMA or properties["certificate_id"] != expected_id:
        fail(f"{path}: schema/certificate identity mismatch")
    verify_graph_binding(properties, graph, alpha, str(path))
    top_count = parse_canonical_int(properties["fixed_top_count"], "fixed top count", nonnegative=True)
    score_count = parse_canonical_int(properties["score_size_count"], "score size count", nonnegative=True)
    cap_count = parse_canonical_int(properties["type_cap_count"], "type cap count", nonnegative=True)
    if top_count != len(rows["fixed_top_set"]) or score_count != len(rows["score"]) or cap_count != len(rows["type_cap"]):
        fail(f"{path}: row count mismatch")
    tops: list[tuple[int, ...]] = []
    for expected_ordinal, (number, fields) in enumerate(rows["fixed_top_set"], 1):
        if len(fields) != 3 or parse_canonical_int(fields[1], "top ordinal", nonnegative=True) != expected_ordinal:
            fail(f"{path}:{number}: malformed fixed-top row")
        stable = tuple(parse_canonical_int(value, "top vertex") for value in fields[2].split())
        if len(stable) != alpha or stable not in stable_sets[alpha]:
            fail(f"{path}:{number}: fixed top is not a reconstructed maximum stable set")
        tops.append(stable)
    fixed_top = canonical_top(tops)
    flat_top = [vertex for stable in fixed_top for vertex in stable]
    if len(flat_top) != len(set(flat_top)):
        fail(f"{path}: fixed top classes overlap")
    scores: list[tuple[int, int]] = []
    previous = alpha
    for number, fields in rows["score"]:
        if len(fields) != 3:
            fail(f"{path}:{number}: malformed score row")
        size = parse_canonical_int(fields[1], "score size", nonnegative=True)
        coefficient = parse_canonical_int(fields[2], "score coefficient", nonnegative=True)
        if not (2 <= size < alpha) or size >= previous or coefficient <= 0:
            fail(f"{path}:{number}: score order/range mismatch")
        previous = size
        scores.append((size, coefficient))
    if not scores:
        fail(f"{path}: conditional dual has no scored sizes")
    caps: list[tuple[int, int]] = []
    multipliers: dict[int, int] = {}
    previous = alpha
    for number, fields in rows["type_cap"]:
        if len(fields) != 4:
            fail(f"{path}:{number}: malformed type-cap row")
        size = parse_canonical_int(fields[1], "cap size", nonnegative=True)
        cap = parse_canonical_int(fields[2], "cap", nonnegative=True)
        multiplier = parse_canonical_int(fields[3], "cap multiplier", nonnegative=True)
        if size >= previous or size not in dict(scores):
            fail(f"{path}:{number}: cap order/range mismatch")
        previous = size
        caps.append((size, cap))
        multipliers[size] = multiplier
    if len(rows["weight"]) != graph.vertices:
        fail(f"{path}: wrong number of vertex weights")
    weights = [0] * (graph.vertices + 1)
    for expected_vertex, (number, fields) in enumerate(rows["weight"], 1):
        if len(fields) != 3 or parse_canonical_int(fields[1], "weight vertex", nonnegative=True) != expected_vertex:
            fail(f"{path}:{number}: noncanonical vertex-weight row")
        weights[expected_vertex] = parse_canonical_int(fields[2], "vertex weight", nonnegative=True)
    denominator = parse_canonical_int(properties["denominator"], "denominator", nonnegative=True)
    target = parse_canonical_int(properties["strict_target"], "strict target", nonnegative=True)
    rhs = parse_canonical_int(properties["rhs_numerator"], "RHS numerator", nonnegative=True)
    if denominator <= 0 or target <= 0:
        fail(f"{path}: invalid denominator/target")
    expected_rhs = sum(weights) + sum(cap * multipliers.get(size, 0) for size, cap in caps)
    if rhs != expected_rhs or rhs >= target * denominator:
        fail(f"{path}: dual objective does not close strict target")
    used = set(flat_top)
    for size, coefficient in scores:
        for stable in stable_sets[size]:
            if used.intersection(stable):
                continue
            if sum(weights[vertex] for vertex in stable) + multipliers.get(size, 0) < coefficient * denominator:
                fail(f"{path}: violated residual column inequality for {stable}")
    return ConditionalConclusion(expected_id, fixed_top, tuple(scores), tuple(caps), target, "conditional_dual")


def parse_model(path: Path, expected_id: str, graph: Graph, stable_sets: Mapping[int, Sequence[tuple[int, ...]]], alpha: int, maximum_json_bytes: int) -> tuple[dict[str, Any], tuple[tuple[tuple[int, ...], int, int, int], ...], Path]:
    model = load_json(path, "conditional model", maximum_json_bytes)
    if not isinstance(model, dict):
        fail(f"{path}: model is not an object")
    require_exact_keys(model, {
        "schema", "model_id", "graph_raw_sha256", "graph_canonical_sha256", "vertices",
        "maximum_class_size", "fixed_top_classes", "score_by_size", "type_caps",
        "strict_target", "radix", "columns_file", "columns_sha256", "column_count",
    }, str(path))
    if model["schema"] != MODEL_SCHEMA or model["model_id"] != expected_id:
        fail(f"{path}: model schema/identity mismatch")
    if model["graph_raw_sha256"] != graph.raw_sha256 or model["graph_canonical_sha256"] != graph.canonical_sha256 or type(model["vertices"]) is not int or model["vertices"] != graph.vertices or type(model["maximum_class_size"]) is not int or model["maximum_class_size"] != alpha:
        fail(f"{path}: model graph/dimension mismatch")
    if not isinstance(model["fixed_top_classes"], list):
        fail(f"{path}: fixed top classes must be a list")
    tops: list[tuple[int, ...]] = []
    for item in model["fixed_top_classes"]:
        if not isinstance(item, list) or any(type(vertex) is not int for vertex in item):
            fail(f"{path}: malformed fixed top class")
        stable = tuple(item)
        if len(stable) != alpha or stable not in stable_sets[alpha]:
            fail(f"{path}: fixed top is not a reconstructed maximum stable set")
        tops.append(stable)
    fixed_top = canonical_top(tops)
    flat = [vertex for stable in fixed_top for vertex in stable]
    if len(flat) != len(set(flat)):
        fail(f"{path}: fixed top classes overlap")
    for key in ("score_by_size", "type_caps"):
        if not isinstance(model[key], dict) or any(type(name) is not str or type(value) is not int for name, value in model[key].items()):
            fail(f"{path}: {key} must map canonical integer strings to integers")
    scores = {parse_canonical_int(size, "score size", nonnegative=True): value for size, value in model["score_by_size"].items()}
    caps = {parse_canonical_int(size, "cap size", nonnegative=True): value for size, value in model["type_caps"].items()}
    if not scores:
        fail(f"{path}: score_by_size must not be empty")
    # JSON key order is not trusted.  Canonical semantics are descending size.
    score_items = tuple(sorted(scores.items(), reverse=True))
    cap_items = tuple(sorted(caps.items(), reverse=True))
    if any(not (2 <= size < alpha) or coefficient <= 0 for size, coefficient in score_items):
        fail(f"{path}: invalid scored size")
    if any(size not in scores or cap < 0 for size, cap in cap_items):
        fail(f"{path}: invalid type cap")
    target = model["strict_target"]
    radix = model["radix"]
    column_count = model["column_count"]
    if type(target) is not int or target <= 0 or type(radix) is not int or radix <= graph.vertices or type(column_count) is not int or column_count < 0:
        fail(f"{path}: invalid target/radix/count")
    columns_hash = model["columns_sha256"]
    if not isinstance(columns_hash, str) or not is_sha256(columns_hash):
        fail(f"{path}: malformed columns hash")
    columns_path = resolve_relative(path, model["columns_file"], "conditional columns")
    if sha256_file(columns_path) != columns_hash:
        fail(f"{path}: columns hash mismatch")
    used = set(flat)
    reconstructed: list[tuple[tuple[int, ...], int, int, int]] = []
    for size, coefficient in score_items:
        for stable in stable_sets[size]:
            if not used.intersection(stable):
                reconstructed.append((stable, size, coefficient, sum(1 << vertex for vertex in stable)))
    parsed: list[tuple[tuple[int, ...], int, int, int]] = []
    with columns_path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream, delimiter="\t")
        try:
            header = next(reader)
        except StopIteration:
            fail(f"{columns_path}: empty column file")
        if header != ["column_id", "size", "score", "vertices"]:
            fail(f"{columns_path}: unexpected column header")
        for number, fields in enumerate(reader, 2):
            if len(fields) != 4:
                fail(f"{columns_path}:{number}: malformed column")
            identifier = parse_canonical_int(fields[0], "column ID", nonnegative=True)
            size = parse_canonical_int(fields[1], "column size", nonnegative=True)
            score = parse_canonical_int(fields[2], "column score", nonnegative=True)
            vertices = tuple(parse_canonical_int(value, "column vertex") for value in fields[3].split())
            if identifier != len(parsed) or len(vertices) != size or tuple(sorted(vertices)) != vertices or len(set(vertices)) != size:
                fail(f"{columns_path}:{number}: noncanonical column")
            parsed.append((vertices, size, score, sum(1 << vertex for vertex in vertices)))
    if tuple(parsed) != tuple(reconstructed) or len(parsed) != column_count:
        fail(f"{path}: supplied columns differ from graph reconstruction")
    normalized = dict(model)
    normalized["fixed_top_classes"] = fixed_top
    normalized["score_items"] = score_items
    normalized["cap_items"] = cap_items
    return normalized, tuple(reconstructed), columns_path


def odd_components(residual: Sequence[int], barrier: Sequence[int], pair_set: set[tuple[int, int]]) -> list[list[int]]:
    remaining = set(residual) - set(barrier)
    odd: list[list[int]] = []
    while remaining:
        start = min(remaining)
        remaining.remove(start)
        queue = [start]
        component: list[int] = []
        while queue:
            vertex = queue.pop()
            component.append(vertex)
            for other in list(remaining):
                edge = (vertex, other) if vertex < other else (other, vertex)
                if edge in pair_set:
                    remaining.remove(other)
                    queue.append(other)
        if len(component) % 2:
            odd.append(sorted(component))
    odd.sort()
    return odd


def verify_matching_witness(matching: Any, residual: Sequence[int], pair_set: set[tuple[int, int]], expected_size: int, context: str) -> None:
    if not isinstance(matching, list):
        fail(f"{context}: matching must be a list")
    used: set[int] = set()
    normalized: list[tuple[int, int]] = []
    for item in matching:
        if not isinstance(item, list) or len(item) != 2 or any(type(vertex) is not int for vertex in item):
            fail(f"{context}: malformed matching edge")
        left, right = sorted(item)
        edge = (left, right)
        if left == right or edge not in pair_set or left not in residual or right not in residual or left in used or right in used:
            fail(f"{context}: invalid matching edge")
        used.update(edge)
        normalized.append(edge)
    if normalized != sorted(normalized) or len(normalized) != expected_size:
        fail(f"{context}: matching order/size mismatch")


def verify_tree_proof(proof_path: Path, model_path: Path, expected_id: str, graph: Graph, stable_sets: Mapping[int, Sequence[tuple[int, ...]]], alpha: int, maximum_json_bytes: int, maximum_proof_bytes: int, maximum_records: int) -> ConditionalConclusion:
    model, columns, columns_path = parse_model(model_path, expected_id, graph, stable_sets, alpha, maximum_json_bytes)
    proof = load_gzip_json(proof_path, "conditional proof", maximum_proof_bytes)
    if not isinstance(proof, dict):
        fail(f"{proof_path}: proof is not an object")
    require_exact_keys(proof, {"schema", "status", "model_sha256", "columns_sha256", "root", "proof", "statistics"}, str(proof_path))
    if proof["schema"] != TREE_PROOF_SCHEMA or proof["status"] != "PROVED":
        fail(f"{proof_path}: proof schema/status mismatch")
    if proof["model_sha256"] != sha256_file(model_path) or proof["columns_sha256"] != sha256_file(columns_path):
        fail(f"{proof_path}: proof-to-model binding mismatch")
    records = proof["proof"]
    root = proof["root"]
    statistics = proof["statistics"]
    if not isinstance(records, list) or len(records) > maximum_records or type(root) is not int or not (0 <= root < len(records)) or not isinstance(statistics, dict):
        fail(f"{proof_path}: malformed proof root/records/statistics")
    require_exact_keys(statistics, {"nodes", "branches", "leaves", "matching_leaves"}, f"{proof_path} statistics")
    if any(type(statistics[key]) is not int or statistics[key] < 0 for key in statistics):
        fail(f"{proof_path}: noninteger proof statistics")
    fixed_top = model["fixed_top_classes"]
    top_vertices = {vertex for stable in fixed_top for vertex in stable}
    residual_vertices = [vertex for vertex in range(1, graph.vertices + 1) if vertex not in top_vertices]
    scores = dict(model["score_items"])
    initial_caps = dict(model["cap_items"])
    target = model["strict_target"]
    count = len(columns)
    all_active = (1 << count) - 1
    incident = {vertex: 0 for vertex in residual_vertices}
    size_masks = {size: 0 for size in scores}
    for index, (stable, size, _, _) in enumerate(columns):
        bit = 1 << index
        size_masks[size] |= bit
        for vertex in stable:
            incident[vertex] |= bit
    conflicts: list[int] = []
    for stable, _, _, _ in columns:
        mask = 0
        for vertex in stable:
            mask |= incident[vertex]
        conflicts.append(mask)
    seen: set[int] = set()
    branch_count = 0
    leaf_count = 0
    matching_leaf_count = 0
    pair_set = set(stable_sets.get(2, ()))

    def visit(index: int, active: int, caps: dict[int, int], selected_score: int, used_mask: int) -> None:
        nonlocal branch_count, leaf_count, matching_leaf_count
        if not (0 <= index < len(records)) or index in seen:
            fail(f"{proof_path}: child out of range, shared, or cyclic at record {index}")
        seen.add(index)
        record = records[index]
        if not isinstance(record, dict) or "kind" not in record:
            fail(f"{proof_path}: malformed record {index}")
        kind = record["kind"]
        if kind == "branch":
            branch_count += 1
            require_exact_keys(record, {"kind", "var", "zero", "one"}, f"{proof_path} branch {index}")
            variable = record["var"]
            zero = record["zero"]
            one = record["one"]
            if type(variable) is not int or not (0 <= variable < count) or not ((active >> variable) & 1) or type(zero) is not int or type(one) is not int or zero >= index or one >= index:
                fail(f"{proof_path}: invalid branch record {index}")
            visit(zero, active & ~(1 << variable), dict(caps), selected_score, used_mask)
            stable, size, score, mask = columns[variable]
            if used_mask & mask:
                fail(f"{proof_path}: selected branch overlaps its path")
            next_caps = dict(caps)
            if size in next_caps:
                if next_caps[size] <= 0:
                    fail(f"{proof_path}: selected branch exceeds type cap")
                next_caps[size] -= 1
            next_active = active & ~conflicts[variable]
            if size in next_caps and next_caps[size] == 0:
                next_active &= ~size_masks[size]
            visit(one, next_active, next_caps, selected_score + score, used_mask | mask)
            return
        if kind == "leaf":
            leaf_count += 1
            require_exact_keys(record, {"kind", "denominator", "vertex_weights", "cap_weights", "numerator", "selected_score", "repairs"}, f"{proof_path} leaf {index}")
            denominator = record["denominator"]
            if type(denominator) is not int or denominator <= 0 or record["selected_score"] != selected_score or type(record["repairs"]) is not int or record["repairs"] < 0:
                fail(f"{proof_path}: invalid leaf metadata")
            weights: dict[int, int] = {}
            previous_vertex = 0
            if not isinstance(record["vertex_weights"], list):
                fail(f"{proof_path}: vertex weights are not a list")
            for item in record["vertex_weights"]:
                if not isinstance(item, list) or len(item) != 2 or type(item[0]) is not int or type(item[1]) is not int:
                    fail(f"{proof_path}: malformed vertex weight")
                vertex, weight = item
                if vertex <= previous_vertex or vertex not in incident or weight <= 0:
                    fail(f"{proof_path}: invalid vertex weight")
                previous_vertex = vertex
                weights[vertex] = weight
            multipliers: dict[int, int] = {}
            previous_size = alpha
            if not isinstance(record["cap_weights"], list):
                fail(f"{proof_path}: cap weights are not a list")
            for item in record["cap_weights"]:
                if not isinstance(item, list) or len(item) != 2 or type(item[0]) is not int or type(item[1]) is not int:
                    fail(f"{proof_path}: malformed cap weight")
                size, weight = item
                if size >= previous_size or size not in caps or weight <= 0:
                    fail(f"{proof_path}: invalid cap weight")
                previous_size = size
                multipliers[size] = weight
            numerator = sum(weights.values()) + sum(caps[size] * multipliers.get(size, 0) for size in caps)
            if record["numerator"] != numerator:
                fail(f"{proof_path}: leaf numerator mismatch")
            remaining = active
            while remaining:
                bit = remaining & -remaining
                variable = bit.bit_length() - 1
                remaining ^= bit
                stable, size, score, _ = columns[variable]
                if sum(weights.get(vertex, 0) for vertex in stable) + multipliers.get(size, 0) < score * denominator:
                    fail(f"{proof_path}: invalid exact dual at leaf {index}, column {variable}")
            if selected_score * denominator + numerator >= target * denominator:
                fail(f"{proof_path}: leaf does not close strict target")
            return
        if kind == "matching_leaf":
            leaf_count += 1
            matching_leaf_count += 1
            require_exact_keys(record, {"kind", "selected_score", "residual", "matching_upper", "barrier", "odd_components", "matching"}, f"{proof_path} matching leaf {index}")
            if record["selected_score"] != selected_score or type(record["matching_upper"]) is not int or record["matching_upper"] < 0:
                fail(f"{proof_path}: malformed matching-leaf metadata")
            remaining_active_sizes = {columns[var][1] for var in range(count) if (active >> var) & 1}
            if remaining_active_sizes - {2} or scores.get(2) != 1:
                fail(f"{proof_path}: matching terminal reached before all larger scored columns were fixed")
            residual = [vertex for vertex in residual_vertices if not ((used_mask >> vertex) & 1)]
            if record["residual"] != residual:
                fail(f"{proof_path}: matching residual mismatch")
            barrier = record["barrier"]
            if not isinstance(barrier, list) or barrier != sorted(set(barrier)) or any(type(vertex) is not int or vertex not in residual for vertex in barrier):
                fail(f"{proof_path}: invalid Tutte--Berge barrier")
            odd = odd_components(residual, barrier, pair_set)
            if record["odd_components"] != odd:
                fail(f"{proof_path}: odd-component reconstruction mismatch")
            numerator = len(residual) + len(barrier) - len(odd)
            if numerator < 0 or numerator % 2:
                fail(f"{proof_path}: malformed Tutte--Berge parity")
            upper = numerator // 2
            if record["matching_upper"] != upper:
                fail(f"{proof_path}: Tutte--Berge upper bound mismatch")
            verify_matching_witness(record["matching"], residual, pair_set, upper, f"{proof_path} matching leaf {index}")
            if selected_score + upper >= target:
                fail(f"{proof_path}: matching leaf does not close strict target")
            return
        fail(f"{proof_path}: unknown proof record kind {kind!r}")

    visit(root, all_active, dict(initial_caps), 0, 0)
    if len(seen) != len(records):
        fail(f"{proof_path}: unreachable proof records")
    actual_stats = {
        "nodes": len(records),
        "branches": branch_count,
        "leaves": leaf_count,
        "matching_leaves": matching_leaf_count,
    }
    if statistics != actual_stats:
        fail(f"{proof_path}: proof statistics mismatch: {statistics} != {actual_stats}")
    return ConditionalConclusion(
        expected_id,
        tuple(fixed_top),
        tuple(model["score_items"]),
        tuple(model["cap_items"]),
        target,
        "conditional_tree",
        tuple(sorted(actual_stats.items())),
    )


def verify_tree_certificate(path: Path, expected_id: str, graph: Graph, stable_sets: Mapping[int, Sequence[tuple[int, ...]]], alpha: int, maximum_json_bytes: int, maximum_proof_bytes: int, maximum_records: int) -> ConditionalConclusion:
    properties, rows = parse_properties_rows(path, set())
    if any(rows.values()):
        fail(f"{path}: unexpected rows")
    require_exact_keys(properties, {
        "schema", "certificate_id", "graph_raw_sha256", "graph_canonical_sha256",
        "vertices", "maximum_class_size", "model_file", "model_sha256",
        "proof_file", "proof_sha256",
    }, str(path))
    if properties["schema"] != TREE_CERT_SCHEMA or properties["certificate_id"] != expected_id:
        fail(f"{path}: tree certificate schema/identity mismatch")
    verify_graph_binding(properties, graph, alpha, str(path))
    model_path = resolve_relative(path, properties["model_file"], "conditional model")
    proof_path = resolve_relative(path, properties["proof_file"], "conditional proof")
    if not is_sha256(properties["model_sha256"]) or not is_sha256(properties["proof_sha256"]) or sha256_file(model_path) != properties["model_sha256"] or sha256_file(proof_path) != properties["proof_sha256"]:
        fail(f"{path}: model/proof artifact hash mismatch")
    return verify_tree_proof(proof_path, model_path, expected_id, graph, stable_sets, alpha, maximum_json_bytes, maximum_proof_bytes, maximum_records)


def parse_coloring(path: Path, graph: Graph) -> dict[str, Any]:
    path = require_regular_nonsymlink(path, "coloring witness")
    colors: dict[int, int] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("c"):
            continue
        fields = line.split()
        if len(fields) != 2:
            fail(f"{path}:{number}: malformed coloring row")
        vertex = parse_canonical_int(fields[0], "coloring vertex", nonnegative=True)
        color = parse_canonical_int(fields[1], "color", nonnegative=True)
        if not (1 <= vertex <= graph.vertices) or color <= 0 or vertex in colors:
            fail(f"{path}:{number}: invalid or duplicate coloring assignment")
        colors[vertex] = color
    if set(colors) != set(range(1, graph.vertices + 1)):
        fail(f"{path}: coloring does not assign every vertex exactly once")
    classes: dict[int, list[int]] = {}
    for vertex, color in colors.items():
        classes.setdefault(color, []).append(vertex)
    if set(classes) != set(range(1, max(classes) + 1)):
        fail(f"{path}: color labels are not contiguous")
    for color, stable in classes.items():
        if not is_stable(stable, graph):
            fail(f"{path}: color class {color} is not stable")
    sizes = sorted((len(stable) for stable in classes.values()), reverse=True)
    canonical_sum = sum((index + 1) * size for index, size in enumerate(sizes))
    actual_sum = sum(colors.values())
    alpha = max(sizes)
    h = [0] * (alpha + 1)
    for size in sizes:
        h[size] += 1
    profile = profile_from_h(h)
    return {
        "actual_sum": actual_sum,
        "canonical_sum": canonical_sum,
        "strength": len(sizes),
        "maximum_class_size": alpha,
        "exact_size_profile": list(profile.h[1:]),
        "ge_profile": list(profile.ge),
        "classes": [sorted(classes[color]) for color in sorted(classes)],
    }


def verify_witness_bundle(path: Path, expected_hash: str, graph: Graph, stable_sets: Mapping[int, Sequence[tuple[int, ...]]], alpha: int, maximum_json_bytes: int) -> list[dict[str, Any]]:
    if sha256_file(path) != expected_hash:
        fail("primal witness bundle hash mismatch")
    data = load_json(path, "primal witness bundle", maximum_json_bytes)
    if not isinstance(data, dict):
        fail("primal witness bundle is not an object")
    require_exact_keys(data, {"schema", "graph_raw_sha256", "graph_canonical_sha256", "witnesses"}, str(path))
    if data["schema"] != WITNESS_SCHEMA or data["graph_raw_sha256"] != graph.raw_sha256 or data["graph_canonical_sha256"] != graph.canonical_sha256 or not isinstance(data["witnesses"], list):
        fail("primal witness bundle schema/graph mismatch")
    result: list[dict[str, Any]] = []
    previous_id = ""
    for witness in data["witnesses"]:
        if not isinstance(witness, dict):
            fail("malformed primal witness")
        if not isinstance(witness.get("classes"), list):
            fail("primal witness classes must be a list")
        kind = witness.get("kind")
        if kind == "packing":
            require_exact_keys(witness, {"id", "kind", "fixed_top_classes", "classes"}, "packing witness")
            top_data = witness["fixed_top_classes"]
        elif kind == "complete_partition":
            require_exact_keys(witness, {"id", "kind", "classes"}, "partition witness")
            top_data = [stable for stable in witness["classes"] if isinstance(stable, list) and len(stable) == alpha]
        else:
            fail(f"unknown primal witness kind: {kind!r}")
        identifier = witness["id"]
        if not isinstance(identifier, str) or not safe_identifier(identifier) or identifier <= previous_id:
            fail("primal witness IDs are duplicated, unsafe, or reordered")
        previous_id = identifier
        if not isinstance(top_data, list) or not isinstance(witness["classes"], list):
            fail(f"witness {identifier}: classes must be lists")
        # Validate the raw JSON domain before set membership or adjacency access.
        # In particular, Python bool/int equality must not admit boolean vertices.
        for stable in top_data + witness["classes"]:
            if not isinstance(stable, list) or not 1 <= len(stable) <= alpha:
                fail(f"witness {identifier}: invalid class size or shape")
            if any(type(vertex) is not int or not 1 <= vertex <= graph.vertices for vertex in stable):
                fail(f"witness {identifier}: vertex must be an integer in 1..{graph.vertices}")
        tops = tuple(tuple(item) for item in top_data)
        if tuple(sorted(tops)) != tops or any(stable not in stable_sets[alpha] for stable in tops):
            fail(f"witness {identifier}: invalid fixed top classes")
        classes = [tuple(item) for item in witness["classes"]]
        all_classes = list(tops) + classes if kind == "packing" else classes
        flat = [vertex for stable in all_classes for vertex in stable]
        if len(flat) != len(set(flat)) or any(not is_stable(stable, graph) for stable in all_classes):
            fail(f"witness {identifier}: classes are unstable or overlapping")
        if kind == "complete_partition" and sorted(flat) != list(range(1, graph.vertices + 1)):
            fail(f"witness {identifier}: partition does not cover every vertex")
        result.append({
            "id": identifier,
            "kind": kind,
            "fixed_top_classes": tops,
            "classes": tuple(classes if kind == "packing" else [stable for stable in classes if len(stable) < alpha]),
            "all_classes": tuple(all_classes),
        })
    return result


@dataclass(frozen=True)
class CampaignEntry:
    certificate_id: str
    kind: str
    path: Path
    sha256: str


@dataclass(frozen=True)
class Campaign:
    path: Path
    graph_raw_sha256: str
    graph_canonical_sha256: str
    vertices: int
    maximum_class_size: int
    objective_threshold: int
    incumbent_path: Path
    incumbent_sha256: str
    incumbent_canonical_sum: int
    witness_path: Path
    witness_sha256: str
    stable_enumeration_node_limit: int
    profile_enumeration_node_limit: int
    maximum_top_packings: int
    maximum_json_bytes: int
    maximum_proof_bytes: int
    maximum_proof_records: int
    veripb_timeout_seconds: int
    entries: tuple[CampaignEntry, ...]


def parse_campaign(path: Path) -> Campaign:
    path = require_regular_nonsymlink(path, "conditional campaign manifest")
    properties, rows = parse_properties_rows(path, {"certificate"})
    require_exact_keys(properties, {
        "schema", "graph_raw_sha256", "graph_canonical_sha256", "vertices",
        "maximum_class_size", "objective_threshold", "incumbent_file", "incumbent_sha256",
        "incumbent_canonical_sum", "witness_bundle_file", "witness_bundle_sha256",
        "stable_enumeration_node_limit", "profile_enumeration_node_limit",
        "maximum_top_packings", "maximum_json_bytes", "maximum_proof_bytes",
        "maximum_proof_records", "veripb_timeout_seconds", "certificate_count",
    }, str(path))
    if properties["schema"] != CAMPAIGN_SCHEMA:
        fail(f"{path}: unexpected campaign schema")
    for key in ("graph_raw_sha256", "graph_canonical_sha256", "incumbent_sha256", "witness_bundle_sha256"):
        if not is_sha256(properties[key]):
            fail(f"{path}: malformed SHA-256 for {key}")
    certificate_count = parse_canonical_int(properties["certificate_count"], "certificate count", nonnegative=True)
    if certificate_count != len(rows["certificate"]):
        fail(f"{path}: certificate count mismatch")
    entries: list[CampaignEntry] = []
    previous_id = ""
    for number, fields in rows["certificate"]:
        if len(fields) != 5:
            fail(f"{path}:{number}: malformed certificate row")
        _, identifier, kind, relative, digest = fields
        if not safe_identifier(identifier) or identifier <= previous_id:
            fail(f"{path}:{number}: certificate IDs are unsafe, duplicate, or reordered")
        previous_id = identifier
        if kind not in {"layered_rational", "layered_veripb", "conditional_dual", "conditional_tree"}:
            fail(f"{path}:{number}: unknown certificate kind {kind!r}")
        if not is_sha256(digest):
            fail(f"{path}:{number}: malformed certificate hash")
        artifact = resolve_relative(path, relative, "campaign certificate")
        if sha256_file(artifact) != digest:
            fail(f"{path}:{number}: certificate hash mismatch")
        entries.append(CampaignEntry(identifier, kind, artifact, digest))
    return Campaign(
        path=path,
        graph_raw_sha256=properties["graph_raw_sha256"],
        graph_canonical_sha256=properties["graph_canonical_sha256"],
        vertices=parse_canonical_int(properties["vertices"], "campaign vertices", nonnegative=True),
        maximum_class_size=parse_canonical_int(properties["maximum_class_size"], "campaign maximum class size", nonnegative=True),
        objective_threshold=parse_canonical_int(properties["objective_threshold"], "campaign objective threshold", nonnegative=True),
        incumbent_path=resolve_relative(path, properties["incumbent_file"], "campaign incumbent"),
        incumbent_sha256=properties["incumbent_sha256"],
        incumbent_canonical_sum=parse_canonical_int(properties["incumbent_canonical_sum"], "incumbent canonical sum", nonnegative=True),
        witness_path=resolve_relative(path, properties["witness_bundle_file"], "primal witness bundle"),
        witness_sha256=properties["witness_bundle_sha256"],
        stable_enumeration_node_limit=parse_canonical_int(properties["stable_enumeration_node_limit"], "stable enumeration limit", nonnegative=True),
        profile_enumeration_node_limit=parse_canonical_int(properties["profile_enumeration_node_limit"], "profile enumeration limit", nonnegative=True),
        maximum_top_packings=parse_canonical_int(properties["maximum_top_packings"], "top packing limit", nonnegative=True),
        maximum_json_bytes=parse_canonical_int(properties["maximum_json_bytes"], "JSON byte limit", nonnegative=True),
        maximum_proof_bytes=parse_canonical_int(properties["maximum_proof_bytes"], "proof byte limit", nonnegative=True),
        maximum_proof_records=parse_canonical_int(properties["maximum_proof_records"], "proof record limit", nonnegative=True),
        veripb_timeout_seconds=parse_canonical_int(properties["veripb_timeout_seconds"], "VeriPB timeout", nonnegative=True),
        entries=tuple(entries),
    )


def verify_generator_profiles(generator_root: Path, threshold_profiles: Sequence[Profile], parent_profiles: Sequence[Profile], alpha: int) -> dict[str, Any]:
    profiles_root = generator_root / "preprocess" / "profiles"
    threshold_path = profiles_root / "threshold_profiles.csv"
    universal_path = profiles_root / "universal_profiles.csv"
    generated_threshold = profile_csv_rows(threshold_path, alpha)
    generated_parent = profile_csv_rows(universal_path, alpha)
    if {profile.h for profile in generated_threshold} != {profile.h for profile in threshold_profiles} or len(generated_threshold) != len(threshold_profiles):
        fail("generator threshold profile family differs from independent reconstruction")
    if {profile.h for profile in generated_parent} != {profile.h for profile in parent_profiles} or len(generated_parent) != len(parent_profiles):
        fail("generator parent profile family differs from independent reconstruction")
    manifest = parse_simple_properties(profiles_root / "manifest.properties")
    threshold_sha256 = sha256_file(threshold_path)
    universal_sha256 = sha256_file(universal_path)
    if parse_canonical_int(manifest.get("global_threshold_profiles", ""), "generator threshold count", nonnegative=True) != len(threshold_profiles) or parse_canonical_int(manifest.get("global_universal_profiles", ""), "generator parent count", nonnegative=True) != len(parent_profiles):
        fail("generator profile manifest count is forged or stale")
    if manifest.get("threshold_profiles_sha256") != threshold_sha256 or manifest.get("universal_profiles_sha256") != universal_sha256:
        fail("generator profile manifest hash is forged or stale")
    return {
        "threshold_profiles_sha256": threshold_sha256,
        "parent_profiles_sha256": universal_sha256,
    }


def certificate_score(conclusion: ConditionalConclusion, witness: Mapping[str, Any]) -> int | None:
    if witness["fixed_top_classes"] != conclusion.fixed_top_classes:
        return None
    counts: dict[int, int] = {}
    for stable in witness["classes"]:
        counts[len(stable)] = counts.get(len(stable), 0) + 1
    if any(counts.get(size, 0) > cap for size, cap in conclusion.type_caps):
        return None
    return sum(counts.get(size, 0) * coefficient for size, coefficient in conclusion.score_by_size)


def verify_campaign(graph_path: Path, campaign_path: Path, *, generator_root: Path | None, stable_mode: str, veripb: Path | None) -> dict[str, Any]:
    started = time.monotonic()
    campaign = parse_campaign(campaign_path)
    graph = parse_graph(graph_path)
    if graph.raw_sha256 != campaign.graph_raw_sha256 or graph.canonical_sha256 != campaign.graph_canonical_sha256 or graph.vertices != campaign.vertices:
        fail("campaign graph identity mismatch")
    alpha = campaign.maximum_class_size
    enumeration = enumerate_stable_sets(graph, alpha + 1, campaign.stable_enumeration_node_limit)
    stable_sets = enumeration.by_size
    if not stable_sets[alpha] or stable_sets[alpha + 1]:
        fail("campaign maximum class size is not exactly reconstructed")
    packing_number, packings = enumerate_top_packings(stable_sets[alpha], graph.vertices, campaign.maximum_top_packings)
    threshold_profiles, profile_nodes = enumerate_profiles(graph.vertices, alpha, packing_number, campaign.objective_threshold, campaign.profile_enumeration_node_limit)
    disk_result: dict[str, Any] | None = None
    if stable_mode not in {"materialized", "disk", "both"}:
        fail(f"unknown stable-family mode: {stable_mode}")
    if stable_mode in {"disk", "both"}:
        if generator_root is None:
            fail("disk stable-family mode requires --generator-root")
        disk = read_disk_stable_families(generator_root / "preprocess" / "stable_sets", stable_sets, alpha + 1)
        disk_result = {str(size): len(family) for size, family in disk.items()}
    layered: list[LayeredConclusion] = []
    conditional: list[ConditionalConclusion] = []
    veripb_tools: list[dict[str, Any]] = []
    certificate_results: list[dict[str, Any]] = []
    for entry in campaign.entries:
        if sha256_file(entry.path) != entry.sha256:
            fail(f"certificate changed during verification: {entry.certificate_id}")
        if entry.kind == "layered_rational":
            conclusion = verify_layered_rational(entry.path, entry.certificate_id, graph, stable_sets, alpha)
            layered.append(conclusion)
            certificate_results.append({"id": entry.certificate_id, "kind": entry.kind, "bound": conclusion.bound})
        elif entry.kind == "layered_veripb":
            conclusion, tool = verify_layered_veripb(entry.path, entry.certificate_id, graph, stable_sets, alpha, veripb, campaign.veripb_timeout_seconds)
            layered.append(conclusion)
            veripb_tools.append(tool)
            certificate_results.append({"id": entry.certificate_id, "kind": entry.kind, "bound": conclusion.bound})
        elif entry.kind == "conditional_dual":
            conclusion = verify_conditional_dual(entry.path, entry.certificate_id, graph, stable_sets, alpha)
            conditional.append(conclusion)
            certificate_results.append({"id": entry.certificate_id, "kind": entry.kind, "strict_target": conclusion.strict_target})
        else:
            conclusion = verify_tree_certificate(entry.path, entry.certificate_id, graph, stable_sets, alpha, campaign.maximum_json_bytes, campaign.maximum_proof_bytes, campaign.maximum_proof_records)
            conditional.append(conclusion)
            certificate_results.append({"id": entry.certificate_id, "kind": entry.kind, "strict_target": conclusion.strict_target, "proof_stats": dict(conclusion.proof_stats)})
        if sha256_file(entry.path) != entry.sha256:
            fail(f"certificate changed after verification: {entry.certificate_id}")
    layered_profiles = tuple(
        profile for profile in threshold_profiles if not any(rule.rejects(profile) for rule in layered)
    )

    def surviving_branches(profile: Profile, conclusions: Sequence[ConditionalConclusion]) -> tuple[tuple[tuple[int, ...], ...], ...]:
        top_count = profile.h[alpha]
        branches = packings.get(top_count, ())
        return tuple(
            packing for packing in branches
            if not any(conclusion.rejects(profile, packing) for conclusion in conclusions)
        )

    parent_conclusions = [conclusion for conclusion in conditional if conclusion.minimum_scored_size >= max(2, alpha - 1)]
    parent_profiles = tuple(
        profile for profile in layered_profiles if surviving_branches(profile, parent_conclusions)
    )
    unresolved: list[dict[str, Any]] = []
    eliminated: list[dict[str, Any]] = []
    for profile in parent_profiles:
        branches = surviving_branches(profile, conditional)
        if branches:
            unresolved.append({
                "h": list(profile.h[1:]),
                "objective": profile.objective,
                "surviving_top_packings": [[list(stable) for stable in packing] for packing in branches],
            })
        else:
            eliminated.append({"h": list(profile.h[1:]), "objective": profile.objective})
    if sha256_file(campaign.incumbent_path) != campaign.incumbent_sha256:
        fail("incumbent coloring changed or hash mismatched")
    incumbent = parse_coloring(campaign.incumbent_path, graph)
    if incumbent["canonical_sum"] != campaign.incumbent_canonical_sum or incumbent["maximum_class_size"] != alpha:
        fail("incumbent coloring does not match campaign conclusion")
    witnesses = verify_witness_bundle(campaign.witness_path, campaign.witness_sha256, graph, stable_sets, alpha, campaign.maximum_json_bytes)
    exact_envelopes: list[dict[str, Any]] = []
    for conclusion in conditional:
        best: tuple[int, str] | None = None
        for witness in witnesses:
            score = certificate_score(conclusion, witness)
            if score is not None and (best is None or score > best[0]):
                best = (score, witness["id"])
        item = {
            "certificate_id": conclusion.certificate_id,
            "strict_target": conclusion.strict_target,
            "certified_upper_score": conclusion.strict_target - 1,
            "score_by_size": {str(size): coefficient for size, coefficient in conclusion.score_by_size},
            "type_caps": {str(size): cap for size, cap in conclusion.type_caps},
            "fixed_top_classes": [list(stable) for stable in conclusion.fixed_top_classes],
        }
        if best is not None:
            item["best_checked_witness_score"] = best[0]
            item["best_checked_witness_id"] = best[1]
            item["exact"] = best[0] == conclusion.strict_target - 1
        else:
            item["exact"] = False
        exact_envelopes.append(item)
    generator_result = None
    if generator_root is not None:
        generator_root = generator_root.absolute()
        generator_result = verify_generator_profiles(generator_root, threshold_profiles, parent_profiles, alpha)
    better_witnesses = []
    for witness in witnesses:
        if witness["kind"] != "complete_partition":
            continue
        sizes = sorted((len(stable) for stable in witness["all_classes"]), reverse=True)
        value = sum((index + 1) * size for index, size in enumerate(sizes))
        if value <= campaign.objective_threshold:
            better_witnesses.append({"id": witness["id"], "canonical_sum": value})
    if better_witnesses:
        status = "BETTER_COLORING_FOUND"
        optimum: int | None = min(item["canonical_sum"] for item in better_witnesses)
    elif not unresolved and incumbent["canonical_sum"] == campaign.objective_threshold + 1:
        status = "OPTIMALITY_CERTIFIED"
        optimum = incumbent["canonical_sum"]
    else:
        status = "INCOMPLETE"
        optimum = None
    return {
        "schema": VERIFY_SCHEMA,
        "status": status,
        "optimum": optimum,
        "objective_threshold": campaign.objective_threshold,
        "graph": {
            "vertices": graph.vertices,
            "edges": len(graph.edges),
            "raw_sha256": graph.raw_sha256,
            "canonical_sha256": graph.canonical_sha256,
        },
        "stable_sets": {str(size): len(stable_sets[size]) for size in range(1, alpha + 2)},
        "stable_enumeration_nodes": enumeration.nodes,
        "stable_mode": stable_mode,
        "disk_stable_sets": disk_result,
        "maximum_class_size": alpha,
        "maximum_class_packing_number": packing_number,
        "maximum_class_packing_counts": {str(count): len(values) for count, values in sorted(packings.items())},
        "profile_enumeration_nodes": profile_nodes,
        "threshold_profile_count": len(threshold_profiles),
        "layered_profile_count": len(layered_profiles),
        "parent_profile_count": len(parent_profiles),
        "eliminated_parent_profiles": len(eliminated),
        "unresolved_threshold_profiles": len(unresolved),
        "unresolved_profiles": unresolved,
        "certificate_count": len(campaign.entries),
        "certificates": certificate_results,
        "derived_envelopes": exact_envelopes,
        "incumbent": {key: value for key, value in incumbent.items() if key != "classes"},
        "better_witnesses": better_witnesses,
        "generator": generator_result,
        "veripb_tools": veripb_tools,
        "elapsed_seconds": round(time.monotonic() - started, 6),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, required=True)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--generator-root", type=Path)
    parser.add_argument("--stable-mode", choices=("materialized", "disk", "both"), default="materialized")
    parser.add_argument("--veripb", type=Path)
    parser.add_argument("--json-out", type=Path)
    arguments = parser.parse_args(argv)
    try:
        result = verify_campaign(
            arguments.graph,
            arguments.campaign,
            generator_root=arguments.generator_root,
            stable_mode=arguments.stable_mode,
            veripb=arguments.veripb,
        )
        text = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if arguments.json_out is not None:
            arguments.json_out.parent.mkdir(parents=True, exist_ok=True)
            arguments.json_out.write_text(text, encoding="utf-8")
        sys.stdout.write(text)
        return 0 if result["status"] in {"OPTIMALITY_CERTIFIED", "BETTER_COLORING_FOUND"} else 3
    except VerificationError as error:
        print(f"CONDITIONAL VERIFICATION FAILED: {error}", file=sys.stderr)
        return 2
    except Exception as error:  # fail closed on unexpected parser/runtime errors
        print(f"CONDITIONAL VERIFICATION FAILED: {type(error).__name__}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
