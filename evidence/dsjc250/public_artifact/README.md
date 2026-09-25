# DSJC250.9 exact threshold/conditional evidence

This package contains the checked coloring, S1–S11 descriptors and exact proof
payloads, model/column data, two checker source trees, profile enumerators and
replay/mutation scripts. The manuscript and matching PDF are in the paper repository's `paper/`
directory.

Fetch the authenticated graph through the repository's `scripts/fetch_graphs.sh`
and follow [the replay instructions](docs/REPLAY.md). The exact result is
Sigma(DSJC250.9)=8277.

The two implementations share proof data; [their relationship](docs/SHARED_COMPONENTS.md)
does not imply unaffiliated research-group replication. Every released tree
uses integer-dual leaves. The independent checker rejects every `matching_leaf`;
the integrated checker has a separate guarded matching rule. See the
[independent proof language](independent_checker/PROOF_FORMAT.md).

Ancillary envelope records are checked for every 5/4/3-set cardinality, strict
integer vertex domain, disjointness, stability and named tops. Pair witnesses
must be complete partitions with their specified tops and profiles. Recorded
solver status/dual summaries and the duplicate `optimal_colouring` JSON field
are not mathematical premises. A separate coloring file is checked directly;
exact envelope sharpness additionally uses the applicable certified bound.
