#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, os, shutil, stat, subprocess, sys, tempfile
from pathlib import Path


def make_view(root: Path, temp: Path) -> Path:
    view = temp / "release"
    view.mkdir()
    os.symlink(root / "instance", view / "instance", target_is_directory=True)
    os.symlink(root / "witness", view / "witness", target_is_directory=True)
    shutil.copytree(root / "certificates", view / "certificates")
    (view / "results").mkdir()
    shutil.copy2(root / "results" / "final_bound.json", view / "results" / "final_bound.json")
    for path in (view / "certificates").iterdir():
        path.chmod(path.stat().st_mode | stat.S_IWUSR)
    final = view / "results" / "final_bound.json"
    final.chmod(final.stat().st_mode | stat.S_IWUSR)
    return view


def run_verify(root: Path, view: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(root / "scripts" / "verify_release.py"), "--release-root", str(view)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180,
    )


def mutate_json(path: Path, mutator) -> None:
    obj = json.loads(path.read_text())
    mutator(obj)
    path.write_text(json.dumps(obj, indent=2) + "\n")


def wrong_threshold(d: dict) -> None:
    fixed = {v for stable_set in d["fixed_size6_classes"] for v in stable_set}
    increment = 1_000_000
    residual_count = 0
    for i, value in enumerate(d["residual_vertex_cover_weights_num"], 1):
        if i not in fixed:
            d["residual_vertex_cover_weights_num"][i - 1] = value + increment
            residual_count += 1
    if residual_count != 982:
        raise RuntimeError("unexpected residual vertex count in threshold mutation")
    d["dual_objective_num"] += residual_count * increment
    d["minimum_column_surplus_num"] += 5 * increment
    d["strict_upper_threshold"] = 136
    total = d["dual_objective_num"]
    denominator = d["denominator"]
    if not (135 * denominator <= total < 136 * denominator):
        raise RuntimeError("threshold mutation did not enter [135D,136D)")


def activate_wrong_scenario(cert: dict, final: dict) -> None:
    if cert["scenario"] != "101" or cert["q5_cap"] is not None or cert["q5_cap_multiplier_num"] != 0:
        raise RuntimeError("wrong-scenario mutation requires the authentic inactive scenario 101 certificate")
    cert["q5_cap"] = 134
    cert["q5_cap_multiplier_num"] = 1
    cert["lower_bound_num"] -= 134
    cert["minimum_slack_num_by_size"][4] += 1
    final["scenario_lower_bound_num"]["101"] -= 134


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--release-root", required=True, type=Path)
    args = ap.parse_args()
    root = args.release_root.resolve()
    tests = []

    with tempfile.TemporaryDirectory(prefix="dsjc1000_badcert_", dir=root.parent) as td:
        view = make_view(root, Path(td))
        mutate_json(view / "certificates" / "full_master_dual.json",
                    lambda d: d["graph"].__setitem__("raw_sha256", "0" * 64))
        tests.append(("graph_hash_mismatch", run_verify(root, view), "certificate graph hash mismatch"))

    with tempfile.TemporaryDirectory(prefix="dsjc1000_badcert_", dir=root.parent) as td:
        view = make_view(root, Path(td))
        mutate_json(view / "certificates" / "full_master_dual.json",
                    lambda d: d["vertex_weights_num"].__setitem__(0, d["vertex_weights_num"][0] + 10**15))
        tests.append(("dual_column_violation", run_verify(root, view), "master stable inequality size 1"))

    with tempfile.TemporaryDirectory(prefix="dsjc1000_badcert_", dir=root.parent) as td:
        view = make_view(root, Path(td))
        mutate_json(view / "certificates" / "size5_packing_cap_111.json",
                    lambda d: d.__setitem__("residual_vertex_cover_weights_num", [0] * 1000))
        tests.append(("packing_column_violation", run_verify(root, view), "packing dual column violation"))

    with tempfile.TemporaryDirectory(prefix="dsjc1000_badcert_", dir=root.parent) as td:
        view = make_view(root, Path(td))
        p = view / "certificates" / "full_master_dual.json"
        p.write_text(p.read_text().replace('"denominator": 100000000', '"denominator": 1.5', 1))
        tests.append(("floating_point_rejected", run_verify(root, view), "floats forbidden"))

    with tempfile.TemporaryDirectory(prefix="dsjc1000_badcert_", dir=root.parent) as td:
        view = make_view(root, Path(td))
        mutate_json(view / "certificates" / "size5_packing_cap_111.json", wrong_threshold)
        tests.append(("packing_threshold_cap_mismatch", run_verify(root, view),
                      "packing threshold/cap relation"))

    with tempfile.TemporaryDirectory(prefix="dsjc1000_badcert_", dir=root.parent) as td:
        view = make_view(root, Path(td))
        cert_path = view / "certificates" / "conditional_101.json"
        final_path = view / "results" / "final_bound.json"
        cert = json.loads(cert_path.read_text())
        final = json.loads(final_path.read_text())
        activate_wrong_scenario(cert, final)
        cert_path.write_text(json.dumps(cert, indent=2) + "\n")
        final_path.write_text(json.dumps(final, indent=2) + "\n")
        tests.append(("active_cap_wrong_scenario", run_verify(root, view),
                      "conditional q5 cap contract"))

    with tempfile.TemporaryDirectory(prefix="dsjc1000_badcert_", dir=root.parent) as td:
        view = make_view(root, Path(td))
        mutate_json(view / "certificates" / "conditional_101.json",
                    lambda d: d.__setitem__("q5_cap", 134))
        tests.append(("declared_cap_zero_multiplier", run_verify(root, view),
                      "conditional q5 cap contract"))

    with tempfile.TemporaryDirectory(prefix="dsjc1000_badcert_", dir=root.parent) as td:
        view = make_view(root, Path(td))
        mutate_json(view / "certificates" / "conditional_111_q5cap134.json",
                    lambda d: d.__setitem__("q5_cap", 133))
        tests.append(("active_cap_wrong_value", run_verify(root, view),
                      "conditional q5 cap contract"))

    with tempfile.TemporaryDirectory(prefix="dsjc1000_badcert_", dir=root.parent) as td:
        view = make_view(root, Path(td))
        mutate_json(view / "certificates" / "conditional_111_q5cap134.json",
                    lambda d: d.__setitem__("q5_cap_multiplier_num", True))
        tests.append(("active_cap_boolean_multiplier", run_verify(root, view),
                      "conditional q5 cap contract"))

    with tempfile.TemporaryDirectory(prefix="dsjc1000_badcert_", dir=root.parent) as td:
        view = make_view(root, Path(td))
        mutate_json(view / "certificates" / "conditional_111_q5cap134.json",
                    lambda d: d.__setitem__("q5_cap_multiplier_num", 0))
        tests.append(("active_cap_zero_multiplier", run_verify(root, view),
                      "conditional q5 cap contract"))

    with tempfile.TemporaryDirectory(prefix="dsjc1000_badcert_", dir=root.parent) as td:
        view = make_view(root, Path(td))
        mutate_json(view / "certificates" / "conditional_101.json",
                    lambda d: d.__setitem__("q5_cap_multiplier_num", 1))
        tests.append(("multiplier_without_cap", run_verify(root, view),
                      "conditional q5 cap contract"))

    with tempfile.TemporaryDirectory(prefix="dsjc1000_badcert_", dir=root.parent) as td:
        view = make_view(root, Path(td))
        mutate_json(view / "certificates" / "conditional_111_q5cap134.json",
                    lambda d: d.__setitem__("denominator", d["denominator"] + 1))
        tests.append(("active_cap_denominator_mismatch", run_verify(root, view),
                      "conditional q5 cap contract"))

    with tempfile.TemporaryDirectory(prefix="dsjc1000_badcert_", dir=root.parent) as td:
        view = make_view(root, Path(td))
        mutate_json(view / "certificates" / "size5_packing_cap_111.json",
                    lambda d: d["fixed_size6_classes"].reverse())
        tests.append(("packing_fixed_set_identity", run_verify(root, view),
                      "packing scenario"))

    bad = []
    for name, result, expected_error in tests:
        accepted = result.returncode == 0
        wrong_error = (result.returncode != 1 or not result.stderr.startswith("VERIFICATION_FAILED: ")
                       or expected_error not in result.stderr)
        print(f"{name}: {'FAIL (accepted)' if accepted else 'FAIL (wrong rejection)' if wrong_error else 'PASS (rejected)'}; verifier_exit={result.returncode}")
        if accepted:
            bad.append(name)
        elif wrong_error:
            bad.append(name)
            print(f"  expected error containing: {expected_error}")
            print(f"  actual stderr: {result.stderr.strip()}")
        else:
            line = result.stderr.strip().splitlines()
            if line:
                print(f"  verifier: {line[-1]}")
    if bad:
        print("Malformed-certificate regressions failed: " + ", ".join(bad), file=sys.stderr)
        return 1
    print(f"All {len(tests)} malformed-certificate tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
