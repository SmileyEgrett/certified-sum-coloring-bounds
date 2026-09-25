# Bounded replay regression controls

With the graph installed, set `TEST_WORK` to a new directory outside the
checkout and run from the repository root:

```sh
bash evidence/dsjc500/fractional_profile_points/tests/test_replay.sh "$TEST_WORK"
```

The final line must be `DSJC500_ENDPOINT_REGRESSION_PASS`, with exit zero.
The driver copies the small endpoint package and its two external inputs into
a relocated checkout with spaces in its name. It writes logs, exit files and
started-child PIDs only beneath `TEST_WORK`. It leaves the original package
unchanged. Commands run sequentially and inherit the caller's CPU affinity.
GNU `timeout` is required in addition to replay dependencies.

Controls cover authentic wrapper and native replay (including a trailing
point-directory separator), each of six input identities, a duplicate higher
census row with the same row count, compiler failure, apparent success with a
nonzero child exit, missing completion output, a real child signal/timeout,
existing-output preservation, unexpected arguments and changed checker source.
Only processes started by this driver are signalled. Stub compilers exercise
process handling; they are not tests against a malicious compiler within the
trusted toolchain. The authentic replay separately requires all nine in-memory
semantic controls and four printed counterprofiles.

The controls distinguish fixed-byte identity, exact arithmetic and process
completion. They do not constitute a general certificate-parser soundness
review or replay all integral exclusion certificates.
