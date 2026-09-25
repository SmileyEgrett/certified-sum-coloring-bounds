# DSJC1000.9 exact conditional evidence

The certified interval is **[102344,103256]**. Use the
[shared replay prerequisites](../../../REPRODUCE.md). Fetch the graph through the root
`scripts/fetch_graphs.sh`, verify the package's `MANIFEST.sha256`, then run:

```sh
./scripts/verify_all.sh .
```

The standard-library checker reconstructs every stable set, verifies the proper
coloring of sum 103256, checks the rational-dual baseline and all eight exhaustive
conditional scenarios. The companion malformed suite contains 13 controls.
The baseline 102309 is derived from a feasible rational dual; it is not asserted
to equal the complete LP optimum. Cap 134 is the certified conditional contract;
cap 133 is a hypothetical strengthening. Graph prerequisites and strict targets
are required throughout.

`MANIFEST.sha256` binds the proof objects, checker sources, coloring,
final-bound record and external graph. The result depends on exact replay
of the complete conditional disjunction and direct checking of the coloring.
