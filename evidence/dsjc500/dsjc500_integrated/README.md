# DSJC500.9 integrated exact evidence

The certified interval is [29,791,29,848], with 1,165 unresolved cells through
29,847: three at 29,791 and 1,162 above it. The
[proof report](REPORT.md) describes the complete reduction.

The initial certificate stage in `baseline/` proves a lower bound of 29,785
and leaves 1,269 cells. Two residual four-set certificates remove 74 cells;
17 conditional trees map to 30 further exclusions, leaving 1,165. The
integrated verifier consumes each stage with those exact conclusions. It
also checks 1,195 splitting paths, 178 targets and the fixed-coloring
certificate.

Fetch the graph from the repository root, then follow [REPRODUCE.md](REPRODUCE.md).
The runtime manifests bind every package file and the authenticated external
graph. Replay uses only Python's standard library and runs no optimizer.
`RESULTS.json` records the final interval, stage counts, tree identities,
generation timings and memory measurements where available. These recorded
statistics are descriptive; the replay reconstructs the proof conclusions.
