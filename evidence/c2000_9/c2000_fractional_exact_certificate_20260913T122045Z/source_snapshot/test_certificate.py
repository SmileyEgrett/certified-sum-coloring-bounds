"""Compatibility mutation harness preserving the historical output path."""

from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

from test_certificate_v2 import (
    check_frozen,
    copy_inputs,
    mutate_fractional_numerator,
    mutate_graph_bytes,
    mutate_invalid_transversal,
    is_semantic_rejection,
    run_child,
)
from verification_common import pin_one_cpu, require


def main(argv: list[str]) -> int:
    try:
        require(len(argv) == 2, "usage: test_certificate.py ROOT")
        pin_one_cpu()
        root = Path(argv[1]).resolve()
        checker = root / "source_snapshot/verify_fractional_coloring.py"
        check_frozen(root)
        start = time.monotonic()
        positive_controls: list[dict[str, object]] = []
        for optimized in (False, True):
            process = run_child(checker, root, optimized)
            require(process.returncode == 0, f"positive control failed under optimized={optimized}: {process.stderr}")
            positive_controls.append({"optimized": optimized, "exit_code": process.returncode})

        mutations = [
            ("numerator_plus_one", mutate_fractional_numerator),
            ("invalid_transversal", mutate_invalid_transversal),
            ("changed_graph_bytes", mutate_graph_bytes),
        ]
        results: list[dict[str, object]] = []
        for name, mutate in mutations:
            for optimized in (False, True):
                with tempfile.TemporaryDirectory(prefix="c2000_fractional_mutation_", dir=root.parent) as directory:
                    scratch = Path(directory)
                    copy_inputs(root, scratch)
                    details = mutate(scratch)
                    process = run_child(checker, scratch, optimized)
                    rejected = is_semantic_rejection(process)
                    results.append(
                        {
                            "mutation": name,
                            "optimized": optimized,
                            "rejected": rejected,
                            "exit_code": process.returncode,
                            "details": details,
                            "stderr": process.stderr,
                        }
                    )
                    require(
                        rejected,
                        f"{name}: child did not complete a semantic rejection under optimized={optimized}: "
                        f"exit={process.returncode}, stderr={process.stderr!r}",
                    )
        check_frozen(root)
        report = {
            "positive_accepted": all(item["exit_code"] == 0 for item in positive_controls),
            "positive_controls": positive_controls,
            "tests": results,
            "seconds": time.monotonic() - start,
        }
        destination = root / "verification/mutation_tests.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"positive_accepted": report["positive_accepted"], "rejected_mutation_runs": len(results), "seconds": report["seconds"]}))
        return 0
    except Exception as exc:
        print(f"HARNESS FAILURE: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
