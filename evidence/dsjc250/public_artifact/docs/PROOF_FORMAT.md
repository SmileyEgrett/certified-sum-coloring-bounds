# Proof-format summary

The integrated descriptors use schema `exact_mscp_conditional_campaign_v1` and bind each S1--S11 entry to a descriptor, model, canonical column table, proof payload, and optional sharpness witness. The second checker consumes its own rational and gzip-JSON formats. Exact field-level schemas are enforced in the two checker sources; unknown or missing keys are rejected.

For a residual top packing `F`, the complete column family consists of every stable set of each scored size that is disjoint from every vertex in `F`, ordered first by decreasing scored size and then by increasing vertex tuple. A column has unit vertex-capacity consumption, its cardinality type, and an integer score. Type quotas are upper bounds. Radix 251 encodes `(n4,n3)` by `251*n4+n3`; radix squared encodes `(n4,n3,n2)` by `63001*n4+251*n3+n2`, with `63001>250*251+250`.

A branch record has one active column and exactly two children. The zero child removes that column. The one child selects it, removes every intersecting column, decrements the applicable quota, and removes the remaining columns of a type when its quota reaches zero. Thus each feasible packing follows one and only one child.

At an integer-dual leaf, a positive denominator `D`, nonnegative scaled vertex weights, and nonnegative scaled quota weights satisfy every active column inequality. The resulting numerator bounds the remaining score. The leaf closes only when the selected score plus that bound is **strictly below** the descriptor target. The actual trees use only this leaf form.

See [S1_S11.tsv](S1_S11.tsv) and [S1_S11.md](S1_S11.md) for concrete obligations, and the two verifier source files for the normative executable grammar.

The ancillary witness JSON is a distinct format: consumed classes, named roles
and integer attainment counts are validated, while descriptive solver fields
and duplicate coloring metadata are not proof premises. The separate coloring
file and exact certificate conclusions remain authoritative. The independent
checker rejects all matching terminals; the integrated checker's separately
guarded matching rule is not exercised by any released tree.
