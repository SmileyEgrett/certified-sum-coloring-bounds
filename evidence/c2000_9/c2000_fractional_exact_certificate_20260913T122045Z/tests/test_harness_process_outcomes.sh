#!/usr/bin/env bash
set -euo pipefail

if (( $# < 2 || $# > 3 )); then
  printf 'usage: %s NEW_WORK_DIRECTORY CPU [all|baselines|controls|controls-v1|controls-v2]\n' "$0" >&2
  exit 2
fi

SCRIPT_DIR=$(cd -P -- "$(dirname -- "$0")" && pwd -P)
PACKAGE=$(cd -P -- "$SCRIPT_DIR/.." && pwd -P)
OUT=$1
CPU=$2
SUITE=${3:-all}
if [[ -e $OUT ]]; then
  printf 'work directory already exists: %s\n' "$OUT" >&2
  exit 2
fi
if [[ ! $CPU =~ ^[0-9]+$ ]]; then
  printf 'CPU must be one logical CPU number\n' >&2
  exit 2
fi
if [[ $SUITE != all && $SUITE != baselines && $SUITE != controls && $SUITE != controls-v1 && $SUITE != controls-v2 ]]; then
  printf 'suite must be all, baselines, controls, controls-v1, or controls-v2\n' >&2
  exit 2
fi
mkdir -p -- "$OUT/bin"
OUT=$(cd -P -- "$OUT" && pwd -P)

CONTROL_SOURCE="$SCRIPT_DIR/harness_process_control.cpp"
CONTROL="$OUT/bin/harness_process_control"
printf '%q ' g++ -std=c++20 -O2 -Wall -Wextra -pedantic "$CONTROL_SOURCE" -o "$CONTROL" \
  > "$OUT/build.command"
printf '\n' >> "$OUT/build.command"
(
  ulimit -c 0
  ulimit -v 2097152
  taskset -c "$CPU" timeout --signal=TERM --kill-after=5s 120s \
    g++ -std=c++20 -O2 -Wall -Wextra -pedantic "$CONTROL_SOURCE" -o "$CONTROL"
) > "$OUT/build.stdout" 2> "$OUT/build.stderr"
sha256sum "$CONTROL_SOURCE" "$CONTROL" > "$OUT/build.sha256"

printf 'test\tharness_exit\tmonitor_exit\tcompleted\texpectation\n' > "$OUT/RESULTS.tsv"

prepare_case() {
  local name=$1
  local directory="$OUT/$name"
  mkdir -p "$directory"
  cp -a "$PACKAGE" "$directory/root"
  chmod -R u+w "$directory/root"
  rm -f "$directory/root/verification/mutation_tests.json" \
    "$directory/root/verification/v2/mutation_tests.json"
  mkdir -p "$directory/tmp"
  printf '%s\n' "$directory"
}

record_command() {
  local destination=$1
  shift
  {
    printf 'cwd=%q\n' "$PWD"
    printf '%q ' "$@"
    printf '\n'
  } > "$destination"
}

run_harness() {
  local directory=$1
  local harness=$2
  local seconds=$3
  local root="$directory/root"
  record_command "$directory/harness.command" env TMPDIR="$directory/tmp" PYTHONOPTIMIZE=2 \
    python3 -B -OO "$root/source_snapshot/$harness" "$root"
  if (
    ulimit -c 0
    ulimit -v 2097152
    taskset -c "$CPU" timeout --signal=TERM --kill-after=5s "${seconds}s" \
      env TMPDIR="$directory/tmp" PYTHONOPTIMIZE=2 \
      python3 -B -OO "$root/source_snapshot/$harness" "$root"
  ) > "$directory/harness.stdout" 2> "$directory/harness.stderr"; then
    local result=0
  else
    local result=$?
  fi
  printf '%s\n' "$result" > "$directory/harness.exit"
  return "$result"
}

assert_mode_line() {
  local log=$1
  local line_number=$2
  local expected_environment=$3
  local expected_flag=$4
  local line
  line=$(sed -n "${line_number}p" "$log")
  grep -q "PYTHONOPTIMIZE=${expected_environment}" <<< "$line"
  if [[ $expected_flag == present ]]; then
    grep -Eq ' cmd=.*python[^ ]* .*-O( |$)' <<< "$line"
  else
    if grep -Eq ' cmd=.*python[^ ]* .*-O(O)?( |$)' <<< "$line"; then
      printf 'unexpected optimization flag on observed line: %s\n' "$line" >&2
      return 1
    fi
  fi
}

run_baseline() {
  local version=$1
  local harness=$2
  local expected_processes=$3
  local report_relative=$4
  local directory root monitor_pid harness_exit monitor_exit report
  directory=$(prepare_case "baseline_${version}")
  root="$directory/root"
  record_command "$directory/monitor.command" taskset -c "$CPU" "$CONTROL" observe \
    "$root" "$expected_processes" "$directory/monitor.log" 540000
  taskset -c "$CPU" "$CONTROL" observe "$root" "$expected_processes" \
    "$directory/monitor.log" 540000 > "$directory/monitor.stdout" 2> "$directory/monitor.stderr" &
  monitor_pid=$!
  if run_harness "$directory" "$harness" 600; then
    harness_exit=0
  else
    harness_exit=$?
  fi
  if wait "$monitor_pid"; then
    monitor_exit=0
  else
    monitor_exit=$?
  fi
  printf '%s\n' "$monitor_exit" > "$directory/monitor.exit"
  [[ $harness_exit == 0 && $monitor_exit == 0 ]]
  report="$root/$report_relative"
  cp "$report" "$directory/report.json"
  grep -q '"positive_accepted": true' "$report"
  if grep -q '"rejected": false' "$report"; then
    printf 'baseline contains an unrejected mutation: %s\n' "$report" >&2
    return 1
  fi
  grep -q 'REJECT: VerificationError:' "$report"
  assert_mode_line "$directory/monitor.log" 1 0 absent
  if [[ $version == v2 ]]; then
    assert_mode_line "$directory/monitor.log" 2 0 absent
    assert_mode_line "$directory/monitor.log" 3 1 present
    assert_mode_line "$directory/monitor.log" 4 1 present
  else
    assert_mode_line "$directory/monitor.log" 2 1 present
  fi
  printf 'baseline_%s\t%s\t%s\tyes\tpositive accepts and explicit semantic rejections pass; child modes are 0/1 under optimized parent\n' \
    "$version" "$harness_exit" "$monitor_exit" >> "$OUT/RESULTS.tsv"
}

run_replacement_control() {
  local version=$1
  local harness=$2
  local positive_count=$3
  local behavior=$4
  local outer_seconds=$5
  local expected_text=$6
  local directory root monitor_pid harness_exit monitor_exit
  directory=$(prepare_case "${version}_${behavior}")
  root="$directory/root"
  record_command "$directory/monitor.command" taskset -c "$CPU" "$CONTROL" replace_after \
    "$root" "$positive_count" "$root/source_snapshot/verify_fractional_coloring.py" \
    "$behavior" "$directory/monitor.log" 240000
  taskset -c "$CPU" "$CONTROL" replace_after "$root" "$positive_count" \
    "$root/source_snapshot/verify_fractional_coloring.py" "$behavior" \
    "$directory/monitor.log" 240000 > "$directory/monitor.stdout" 2> "$directory/monitor.stderr" &
  monitor_pid=$!
  if run_harness "$directory" "$harness" "$outer_seconds"; then
    harness_exit=0
  else
    harness_exit=$?
  fi
  if wait "$monitor_pid"; then
    monitor_exit=0
  else
    monitor_exit=$?
  fi
  printf '%s\n' "$monitor_exit" > "$directory/monitor.exit"
  [[ $harness_exit == 1 && $monitor_exit == 0 ]]
  grep -q "$expected_text" "$directory/harness.stderr"
  printf '%s_%s\t%s\t%s\tno\tincomplete or nonsemantic child fails the harness\n' \
    "$version" "$behavior" "$harness_exit" "$monitor_exit" >> "$OUT/RESULTS.tsv"
}

run_signal_control() {
  local version=$1
  local harness=$2
  local scratch_marker=$3
  local directory root monitor_pid harness_exit monitor_exit
  directory=$(prepare_case "${version}_signal")
  root="$directory/root"
  record_command "$directory/monitor.command" taskset -c "$CPU" "$CONTROL" signal_mutation \
    "$root" "$scratch_marker" "$directory/monitor.log" 240000
  taskset -c "$CPU" "$CONTROL" signal_mutation "$root" "$scratch_marker" \
    "$directory/monitor.log" 240000 > "$directory/monitor.stdout" 2> "$directory/monitor.stderr" &
  monitor_pid=$!
  if run_harness "$directory" "$harness" 300; then
    harness_exit=0
  else
    harness_exit=$?
  fi
  if wait "$monitor_pid"; then
    monitor_exit=0
  else
    monitor_exit=$?
  fi
  printf '%s\n' "$monitor_exit" > "$directory/monitor.exit"
  [[ $harness_exit == 1 && $monitor_exit == 0 ]]
  grep -q 'did not complete a semantic rejection' "$directory/harness.stderr"
  grep -q 'exit=-15' "$directory/harness.stderr"
  printf '%s_signal\t%s\t%s\tno\tSIGTERM child fails the harness and is not a rejection\n' \
    "$version" "$harness_exit" "$monitor_exit" >> "$OUT/RESULTS.tsv"
}

if [[ $SUITE == all || $SUITE == baselines ]]; then
  run_baseline v2 test_certificate_v2.py 20 verification/v2/mutation_tests.json
  run_baseline v1 test_certificate.py 8 verification/mutation_tests.json
fi

if [[ $SUITE == all || $SUITE == controls || $SUITE == controls-v1 || $SUITE == controls-v2 ]]; then
  versions=(v2 v1)
  [[ $SUITE == controls-v1 ]] && versions=(v1)
  [[ $SUITE == controls-v2 ]] && versions=(v2)
  for version in "${versions[@]}"; do
    if [[ $version == v2 ]]; then
      harness=test_certificate_v2.py
      positive_count=4
    else
      harness=test_certificate.py
      positive_count=2
    fi
    run_replacement_control "$version" "$harness" "$positive_count" exit_zero 300 \
      'did not complete a semantic rejection'
    run_replacement_control "$version" "$harness" "$positive_count" unrelated_one 300 \
      'UNRELATED CHILD FAILURE'
    run_replacement_control "$version" "$harness" "$positive_count" exit_two 300 \
      'exit=2'
    run_replacement_control "$version" "$harness" "$positive_count" syntax_error 300 \
      'SyntaxError'
    run_replacement_control "$version" "$harness" "$positive_count" empty_one 300 \
      "stderr=''"
    run_replacement_control "$version" "$harness" "$positive_count" timeout 600 \
      'child did not complete before timeout'
  done

  if [[ $SUITE != controls-v1 ]]; then
    run_signal_control v2 test_certificate_v2.py c2000_mutation_
  fi
  if [[ $SUITE != controls-v2 ]]; then
    run_signal_control v1 test_certificate.py c2000_fractional_mutation_
  fi
fi

(
  cd "$OUT"
  find . -type f ! -path '*/root/*' ! -name ARTIFACT_SHA256SUMS -print0 \
    | sort -z | xargs -0 sha256sum
) > "$OUT/ARTIFACT_SHA256SUMS"

printf 'PASS: requested C2000.9 harness regression suite (%s) completed.\n' "$SUITE"
