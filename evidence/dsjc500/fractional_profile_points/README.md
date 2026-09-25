# DSJC500.9 continuous endpoint points

These three exact rational points satisfy the conditioned continuous master
in the paper's equation `eq:dsjc500-continuous-profile`. They correspond to
exactly the three lowest rows of the retained 1,165-cell census:

| Point | Top packing | Profile `(h1,h2,h3,h4,h5)` | Positive support | Objective |
| --- | --- | --- | ---: | ---: |
| P5E | P5 | `(1,4,4,101,15)` | 424 | 29791 |
| P5F | P5 | `(4,1,5,101,15)` | 410 | 29791 |
| P7F | P7 | `(4,1,5,101,15)` | 411 | 29791 |

They are continuous feasible points, not integer colorings. They establish
feasibility only for the displayed model and do not rule out stronger
relaxations. The separate integral certificate package establishes
`29791 <= Sigma(DSJC500.9) <= 29848`. Excluding these three cells alone would
raise the lower endpoint to 29792; another 1,162 cells remain above them.
See the [DSJC500 evidence overview](../README.md) and
[integral proof report](../dsjc500_integrated/REPORT.md).

## Replay

Dependencies: Bash, GNU core utilities (including `realpath` and `sha256sum`),
a C++20 compiler, and installed OpenSSL headers/libcrypto. No optimizer,
Python package, Boost library or network access is used by this command.
First obtain the graph using the repository's
[graph instructions](../../../docs/GRAPH_PROVENANCE.md) and
`scripts/fetch_graphs.sh`. The replay does not download missing inputs.

From the repository root, set `CHECK_WORK` to a new directory outside the
checkout, then run:

```sh
bash evidence/dsjc500/fractional_profile_points/verify.sh "$CHECK_WORK"
```

The work directory must not exist. The script resolves its resources from
its own location, so it can also be invoked by an absolute path from another
working directory. It checks the package manifest and all six input hashes
before compiling a fresh executable. It records `compile.log`, `compile.exit`,
`replay.log` and `replay.exit` in `CHECK_WORK`. A successful command exits zero
and ends with `DSJC500_ENDPOINT_REPLAY_PASS`; a completion message with a
nonzero process status is a failure. `CXX` may name a compiler executable.
The command uses one thread and inherits the caller's CPU affinity. On Linux,
`taskset -c CPU bash .../verify.sh "$CHECK_WORK"` selects an available CPU.

The native interface is
`check_endpoint_points GRAPH POINT_DIRECTORY UNRESOLVED_CSV`.
It enforces the same fixed identities, reads each input once, verifies its
hash before parsing, and reads `reconstruction.json` from the parent of
`POINT_DIRECTORY`. There is no identity-bypass option.

## Inputs and exact scope

The graph and census stay in the existing repository package:

| Input, relative to the repository root | SHA-256 |
| --- | --- |
| `evidence/dsjc500/dsjc500_integrated/data/DSJC500.9.col` | `95276841dffcde7c04de2fc1ae8e43b6c7b84173b4a9646b1cc6b392a3bd7b39` |
| `evidence/dsjc500/dsjc500_integrated/results/census/unresolved_cells.csv` | `60f50a2de470d7fe6925d9b327cecc017def5a346723fc011b2817f9ada3e27f` |

The four certificate JSON identities are in [SHA256SUMS](SHA256SUMS) and
[PROVENANCE.md](PROVENANCE.md). The graph's header reports twice its 112,437
undirected edge records; its original bytes are preserved.

The C++ check reconstructs all stable sets through size six, obtaining
`500/12313/19901/2428/23/0`, and all eight maximum packings of 15 five-sets.
Ascending vertex-set enumeration, one-based five-set indices and sorted
packing order fix the P5/P7 names. It compares the reconstruction record's
schema, graph/stable-family/packing hashes, counts and packing order with
these computed objects. Packet identity, platform and discovery fields record provenance; they
are not replay dependencies or mathematical premises.

For every supported residual size-2–4 column, the check verifies stability,
residual membership, nonnegative exact weight, unit vertex capacity and exact
size totals. Unlisted columns have zero weight. Nonnegative singleton deficits
complete the partition equations and the prescribed profile. The integer
Ferrers coordinates have unit-cell objective 29791. Arithmetic uses
arbitrary-length nonnegative integers. The check also verifies the identified
census's endpoint correspondence and the finite 230/160 profile counts.

Nine in-memory semantic controls change a numerator, set a zero denominator,
or change top-packing order, for each point. They must fail with the specified
capacity, denominator or top-binding diagnostic. File-mutation controls
exercise the separate byte-identity boundary; hash rejection alone is not a
semantic test. Regression instructions are in [tests/README.md](tests/README.md).

This is a bounded cross-check of authentic, fixed data. It does not replay
every integral exclusion, certify a general JSON/CSV proof
language, establish arbitrary-input resource safety, or replace the existing
integral replay. Hashes identify data; the mathematical interpretation also
depends on the reconstructed model and the paper's correspondence argument.
