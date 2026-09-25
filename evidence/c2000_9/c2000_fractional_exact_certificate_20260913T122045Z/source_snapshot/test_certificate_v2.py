"""Normal/optimized positive replays and fail-closed C2000.9 mutation tests."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Callable

from verification_common import VerificationError, load_json, pin_one_cpu, require


def check_frozen(root: Path) -> None:
    manifest = load_json(root / "manifest/frozen.json")
    require(type(manifest) is dict, "frozen manifest is not an object")
    for relative, expected in manifest.items():
        require(type(relative) is str and type(expected) is str, "invalid frozen manifest entry")
        actual = hashlib.sha256((root / relative).read_bytes()).hexdigest()
        require(actual == expected, f"frozen hash mismatch: {relative}")


def run_child(checker: Path, root: Path, optimized: bool) -> subprocess.CompletedProcess[str]:
    command = [sys.executable]
    if optimized:
        command.append("-O")
    command.extend([str(checker), str(root)])
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONOPTIMIZE"] = "1" if optimized else "0"
    try:
        return subprocess.run(command, text=True, capture_output=True, timeout=90, env=environment, check=False)
    except subprocess.TimeoutExpired as exc:
        raise VerificationError(f"child did not complete before timeout: optimized={optimized}, checker={checker.name}") from exc


def is_semantic_rejection(process: subprocess.CompletedProcess[str]) -> bool:
    return process.returncode == 1 and process.stderr.startswith("REJECT: VerificationError:")


def copy_inputs(source: Path, destination: Path) -> None:
    (destination / "input").mkdir()
    shutil.copyfile(source / "input/C2000.9.col", destination / "input/C2000.9.col")
    shutil.copyfile(source / "EXACT_FRACTIONAL_COLORING.json", destination / "EXACT_FRACTIONAL_COLORING.json")
    shutil.copyfile(source / "SUM_MASTER_K390_PRIMAL.json", destination / "SUM_MASTER_K390_PRIMAL.json")


def mutate_fractional_numerator(root: Path) -> dict[str, object]:
    certificate = load_json(root / "EXACT_FRACTIONAL_COLORING.json")
    certificate["terms"][0]["numerator"] = str(int(certificate["terms"][0]["numerator"]) + 1)
    (root / "EXACT_FRACTIONAL_COLORING.json").write_text(json.dumps(certificate), encoding="utf-8")
    return {}


def mutate_empty_support(root: Path) -> dict[str, object]:
    certificate = load_json(root / "EXACT_FRACTIONAL_COLORING.json")
    certificate["terms"] = []
    (root / "EXACT_FRACTIONAL_COLORING.json").write_text(json.dumps(certificate), encoding="utf-8")
    return {}


def mutate_invalid_transversal(root: Path) -> dict[str, object]:
    certificate = load_json(root / "EXACT_FRACTIONAL_COLORING.json")
    hit = set(certificate["zero_weight_vertices_one_based"])
    six = set(next(term["vertices_one_based"] for term in certificate["terms"] if len(term["vertices_one_based"]) == 6))
    intersection = hit & six
    require(len(intersection) == 1, "mutation seed six-set does not meet H exactly once")
    anchor = next(iter(intersection))
    replacement = next(vertex for vertex in range(1, 2001) if vertex not in hit and vertex not in six)
    hit.remove(anchor)
    hit.add(replacement)
    certificate["zero_weight_vertices_one_based"] = sorted(hit)
    (root / "EXACT_FRACTIONAL_COLORING.json").write_text(json.dumps(certificate), encoding="utf-8")
    return {"removed_anchor": anchor, "replacement": replacement, "independent_six_now_outside_H": sorted(six)}


def mutate_graph_bytes(root: Path) -> dict[str, object]:
    with (root / "input/C2000.9.col").open("a", encoding="ascii") as handle:
        handle.write("c deliberate graph-identity mutation\n")
    return {}


def mutate_duplicate_denominator(root: Path) -> dict[str, object]:
    path = root / "EXACT_FRACTIONAL_COLORING.json"
    text = path.read_text(encoding="utf-8")
    marker = '"denominator":'
    position = text.index(marker)
    path.write_text(text[:position] + '"denominator":"1",' + text[position:], encoding="utf-8")
    return {}


def mutate_boolean_vertex(root: Path) -> dict[str, object]:
    certificate = load_json(root / "EXACT_FRACTIONAL_COLORING.json")
    certificate["terms"][0]["vertices_one_based"][0] = True
    (root / "EXACT_FRACTIONAL_COLORING.json").write_text(json.dumps(certificate), encoding="utf-8")
    return {}


def mutate_sum_numerator(root: Path) -> dict[str, object]:
    certificate = load_json(root / "SUM_MASTER_K390_PRIMAL.json")
    certificate["terms"][0]["numerator"] = str(int(certificate["terms"][0]["numerator"]) + 1)
    (root / "SUM_MASTER_K390_PRIMAL.json").write_text(json.dumps(certificate), encoding="utf-8")
    return {}


def mutate_sum_negative_denominator(root: Path) -> dict[str, object]:
    certificate = load_json(root / "SUM_MASTER_K390_PRIMAL.json")
    certificate["denominator"] = "-1"
    (root / "SUM_MASTER_K390_PRIMAL.json").write_text(json.dumps(certificate), encoding="utf-8")
    return {}


def main(argv: list[str]) -> int:
    try:
        require(len(argv) == 2, "usage: test_certificate_v2.py ROOT")
        pin_one_cpu()
        root = Path(argv[1]).resolve()
        check_frozen(root)
        fractional_checker = root / "source_snapshot/verify_fractional_coloring.py"
        sum_checker = root / "source_snapshot/verify_sum_master.py"
        start = time.monotonic()
        positive_results: list[dict[str, object]] = []
        for optimized in (False, True):
            for checker in (fractional_checker, sum_checker):
                process = run_child(checker, root, optimized)
                require(process.returncode == 0, f"positive control failed: optimized={optimized}, checker={checker.name}: {process.stderr}")
                positive_results.append({"optimized": optimized, "checker": checker.name, "exit_code": process.returncode})

        mutations: list[tuple[str, Path, Callable[[Path], dict[str, object]]]] = [
            ("fractional_numerator_plus_one", fractional_checker, mutate_fractional_numerator),
            ("fractional_empty_support", fractional_checker, mutate_empty_support),
            ("fractional_invalid_transversal", fractional_checker, mutate_invalid_transversal),
            ("fractional_changed_graph_bytes", fractional_checker, mutate_graph_bytes),
            ("fractional_duplicate_denominator", fractional_checker, mutate_duplicate_denominator),
            ("fractional_boolean_vertex", fractional_checker, mutate_boolean_vertex),
            ("sum_master_numerator_plus_one", sum_checker, mutate_sum_numerator),
            ("sum_master_negative_denominator", sum_checker, mutate_sum_negative_denominator),
        ]
        results: list[dict[str, object]] = []
        for name, checker, mutate in mutations:
            for optimized in (False, True):
                with tempfile.TemporaryDirectory(prefix="c2000_mutation_") as directory:
                    scratch = Path(directory)
                    copy_inputs(root, scratch)
                    details = mutate(scratch)
                    process = run_child(checker, scratch, optimized)
                    rejected = is_semantic_rejection(process)
                    result = {
                        "mutation": name,
                        "optimized": optimized,
                        "rejected": rejected,
                        "exit_code": process.returncode,
                        "details": details,
                        "stdout": process.stdout,
                        "stderr": process.stderr,
                    }
                    results.append(result)
                    require(
                        rejected,
                        f"{name}: child did not complete a semantic rejection under optimized={optimized}: "
                        f"exit={process.returncode}, stdout={process.stdout!r}, stderr={process.stderr!r}",
                    )

        check_frozen(root)
        report = {
            "positive_accepted": all(item["exit_code"] == 0 for item in positive_results),
            "positive_controls": positive_results,
            "tests": results,
            "seconds": time.monotonic() - start,
        }
        destination = root / "verification/v2/mutation_tests.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"positive_accepted": True, "rejected_mutation_runs": len(results), "seconds": report["seconds"]}))
        return 0
    except Exception as exc:
        print(f"HARNESS FAILURE: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
