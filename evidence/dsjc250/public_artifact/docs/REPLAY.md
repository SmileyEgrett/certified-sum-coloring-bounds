# Replay

Use the [shared replay prerequisites](../../../../REPRODUCE.md), including
Python 3.10 or later and GNU time at `/usr/bin/time`. From the paper repository
root, fetch exact graph bytes and run:

```sh
./scripts/fetch_graphs.sh
./evidence/dsjc250/public_artifact/scripts/replay_all.sh \
  graphs/DSJC250.9.col build/replay-dsjc250
./evidence/dsjc250/public_artifact/scripts/run_mutations.sh graphs/DSJC250.9.col
```

The replay must exit zero and end with `ALL REPLAYS AND PROFILE REGENERATIONS PASSED`.
The mutation suite must exit zero and end with `ALL MUTATION TESTS PASSED`;
its malformed children must complete with the intended verifier rejection,
not merely any nonzero process status. Both graph and manifest identity checks
precede proof replay. Staging creates a separate runtime manifest after adding
the authenticated external graph.

The maintained manuscript and build instructions are at `paper/` and
`docs/PAPER_BUILD.md` in the repository root.
