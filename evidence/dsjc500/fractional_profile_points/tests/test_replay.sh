#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
if [[ $# -ne 1 ]]; then
    printf 'usage: %s NEW_EXTERNAL_TEST_DIRECTORY\n' "$0" >&2; exit 2
fi
package=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
repository=$(CDPATH= cd -- "$package/../../.." && pwd -P)
work=$(realpath -m -- "$1")
case "$work/" in "$repository/"*) printf 'Test directory must be external.\n' >&2; exit 2 ;; esac
[[ ! -e "$work" && ! -L "$work" ]] || { printf 'Test directory already exists.\n' >&2; exit 2; }
mkdir -p -- "$work"
repo="$work/relocated checkout with spaces"
copy="$repo/evidence/dsjc500/fractional_profile_points"
integrated="$repo/evidence/dsjc500/dsjc500_integrated"
mkdir -p "$repo/evidence/dsjc500" "$integrated/data" "$integrated/results/census"
cp -a "$package" "$copy"
cp "$package/../dsjc500_integrated/data/DSJC500.9.col" "$integrated/data/"
cp "$package/../dsjc500_integrated/results/census/unresolved_cells.csv" "$integrated/results/census/"
graph="$integrated/data/DSJC500.9.col"
census="$integrated/results/census/unresolved_cells.csv"
points="$copy/certificates/fractional_lp"

expect_status() {
    local name=$1 expected=$2 code=0; shift 2
    "$@" > "$work/$name.log" 2>&1 || code=$?
    printf '%s\n' "$code" > "$work/$name.exit"
    if [[ $code -ne $expected ]]; then
        cat "$work/$name.log" >&2
        printf 'FAIL %s: expected %s, got %s\n' "$name" "$expected" "$code" >&2
        exit 1
    fi
    printf 'CONTROL %s exit=%s PASS\n' "$name" "$code"
}
cd "$work"
expect_status authentic 0 bash "$copy/verify.sh" "$work/authentic output"
grep -Fxq 'DSJC500_ENDPOINT_REPLAY_PASS' "$work/authentic.log"
[[ $(grep -c '^NEGATIVE_CONTROL .* REJECTED ' "$work/authentic.log") -eq 9 ]]
[[ $(grep -c '^GRAPH_FREE_PROFILE ' "$work/authentic.log") -eq 4 ]]
binary="$work/authentic output/check_endpoint_points"
expect_status native 0 "$binary" "$graph" "$points/" "$census"
grep -Fxq 'DSJC500_CURRENT_ENDPOINT_POINTS_PASS' "$work/native.log"

identity_control() {
    local name=$1 file=$2
    expect_status "wrapper-$name" 1 bash "$copy/verify.sh" "$work/rejected-$name"
    [[ ! -e "$work/rejected-$name" ]]
    grep -Eq 'INPUT_IDENTITY_FAIL|FAILED' "$work/wrapper-$name.log"
    expect_status "native-$name" 1 "$binary" "$graph" "$points" "$census"
    grep -Fq 'input byte identity:' "$work/native-$name.log"
    if grep -q '^UNIVERSE ' "$work/native-$name.log"; then
        printf 'Identity check ran after reconstruction: %s\n' "$file" >&2; exit 1
    fi
}
for name in graph census reconstruction P5E P5F P7F; do
    case "$name" in
        graph) file=$graph ;;
        census) file=$census ;;
        reconstruction) file="$copy/certificates/reconstruction.json" ;;
        *) file="$points/${name}_fractional_exact.json" ;;
    esac
    cp "$file" "$work/saved-$name"
    printf '\n' >> "$file"
    identity_control "$name" "$file"
    cp "$work/saved-$name" "$file"
done
awk -F, 'NR==1 {print; next} $2>29791 {if (!saved) saved=$0; else if (!done) {print saved; done=1; next}} {print}' \
    "$census" > "$work/duplicate-census.csv"
[[ $(wc -l < "$census") -eq $(wc -l < "$work/duplicate-census.csv") ]]
cp "$work/duplicate-census.csv" "$census"
identity_control duplicate-higher-row "$census"
cp "$work/saved-census" "$census"

cat > "$work/fail-compiler" <<'COMPILER'
#!/usr/bin/env bash
exit 42
COMPILER
cat > "$work/stub-compiler" <<'COMPILER'
#!/usr/bin/env bash
set -euo pipefail
out=
while [[ $# -gt 0 ]]; do
    if [[ $1 == -o ]]; then out=$2; shift 2; else shift; fi
done
[[ -n "$out" ]]
cat > "$out" <<'CHILD'
#!/usr/bin/env bash
printf '%s\n' "$$" > "$FAKE_PID_FILE"
printf 'CHILD_MODE=%s\n' "$FAKE_CHILD_MODE"
case "$FAKE_CHILD_MODE" in
    success-nonzero) printf 'DSJC500_CURRENT_ENDPOINT_POINTS_PASS\n'; exit 7 ;;
    missing-marker) exit 0 ;;
    signal) kill -TERM "$$" ;;
    hang) exec sleep 30 ;;
esac
CHILD
chmod +x "$out"
COMPILER
chmod +x "$work/fail-compiler" "$work/stub-compiler"
expect_status compiler-failure 42 env CXX="$work/fail-compiler" bash "$copy/verify.sh" "$work/compile failure"
[[ ! -e "$work/compile failure/check_endpoint_points" ]]
for mode in success-nonzero missing-marker signal; do
    case "$mode" in success-nonzero) expected=7 ;; missing-marker) expected=1 ;; signal) expected=143 ;; esac
    expect_status "$mode" "$expected" env CXX="$work/stub-compiler" FAKE_CHILD_MODE="$mode" \
        FAKE_PID_FILE="$work/$mode.pid" bash "$copy/verify.sh" "$work/$mode output"
    [[ -s "$work/$mode.pid" ]]
    if grep -Fxq 'DSJC500_ENDPOINT_REPLAY_PASS' "$work/$mode.log"; then
        printf 'False wrapper success for %s\n' "$mode" >&2; exit 1
    fi
done
expect_status timeout 124 timeout --signal=TERM --kill-after=1s 1s \
    env CXX="$work/stub-compiler" FAKE_CHILD_MODE=hang FAKE_PID_FILE="$work/timeout.pid" \
    bash "$copy/verify.sh" "$work/timeout output"
[[ -s "$work/timeout.pid" ]]
grep -Fxq 'CHILD_MODE=hang' "$work/timeout output/replay.log"
expect_status existing-output 2 bash "$copy/verify.sh" "$work/authentic output"
expect_status extra-argument 2 bash "$copy/verify.sh" "$work/unused" extra
# Source identity is checked before a compiler can use changed helper bytes.
printf '\n' >> "$copy/checks/check_endpoint_points.cpp"
expect_status changed-helper 1 bash "$copy/verify.sh" "$work/changed helper"
[[ ! -e "$work/changed helper" ]]
printf 'DSJC500_ENDPOINT_REGRESSION_PASS\n'
