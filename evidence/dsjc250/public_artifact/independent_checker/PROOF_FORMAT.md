# Exact branch-and-bound proof format

## Model

A model has a finite list of stable-set columns. Column `j` has a vertex set `C_j`, a type (its cardinality), and a nonnegative integer score `w_j`. Vertex capacity is one. Some column types also have integer upper quotas.

The five conditional maxima are encoded lexicographically with base `B=251`, larger than any possible number of lower-type columns:

- envelope: score `251 n4 + n3`;
- pair endgame: score `251^2 n4 + 251 n3 + n2`.

A sixth tree proves that the `x2` top permits at most 37 residual 4-sets.

The independent checker accepts only these six named release models.  Model
names select their fixed top sets, type caps, score coefficients, and strict
targets, all of which are checked against the proof payload.  Verification
returns those checked fields as the tree conclusion; the profile analysis
uses the returned fields rather than a second table of envelope maxima.

## Rational conclusions

The two layered rational certificates prove an upper bound on the number of
classes at or above `minimum_class_size`.  A conclusion applies to a profile
only when every `condition size count multiplier` row has the stated class
count.  The checker then rejects the profile only when its actual cumulative
count exceeds the verified bound.

The three residual rational certificates prove an upper bound on the number
of residual size-four classes for one exact packing of size-five top classes.
They cannot be applied to another top packing.  Besides checking every
residual stable 4-set inequality, the checker requires

`slack_budget = rhs_numerator - required_residual_sets * denominator`.

Thus the descriptive residual count and slack cannot drift away from the
dual objective.  The `purpose` field is explanatory text and grants no proof
authority.

## Branch records

An internal record branches on one active column `j`:

- the zero child excludes `j`;
- the one child selects `j`, removes every intersecting column, decrements the applicable type quota, and removes all columns of a type when its quota reaches zero.

Thus every feasible integer packing follows exactly one child at every branch.

## Rational-dual leaf records

At a leaf, integer numerators encode nonnegative rational vertex weights `y_v` and type-quota weights `lambda_s`, with common positive denominator `D`. The verifier checks, for every active column,

`sum(v in C_j) y_v + lambda_type(j) >= D * w_j`.

For any remaining feasible packing, summing these inequalities and using vertex capacity and type quotas gives the exact upper bound

`remaining score <= (sum_v y_v + sum_s quota_s lambda_s) / D`.

The leaf closes only when

`selected_score * D + sum_v y_v + sum_s quota_s lambda_s < target * D`.

All quantities are checked as arbitrary-precision integers. The certificate generator used floating-point LP solutions only as suggestions; it rounded and repaired them, and the verifier accepts a leaf only if the resulting exact inequalities hold.

## Matching terminals

A cardinality matching terminal would be sound only after every eligible
active scored column is a size-2 stable set with score one, with the residual
stable-pair graph, path state, quotas, Tutte--Berge barrier, odd components,
and strict closure all checked.  The independent schema does not include the
explicit matching witness used by the integrated checker.  The independent
checker therefore rejects every `matching_leaf`.  All six released trees use
only rational-dual leaves, so this restriction does not change a genuine
certificate.

## Fail-closed checks

The verifier independently rebuilds the stable-set columns from the graph and requires byte-independent structural equality with the proof's column list. It rejects duplicate JSON keys, non-finite JSON constants, unknown/missing fields, noninteger child references, inactive branch variables, overlapping selected columns, quota violations, cycles, reused or unreachable records, non-postorder children, malformed weights, incorrect statistics, stale graph/census data, unsupported matching terminals, and any rational-dual leaf that fails a single exact column inequality.

## Final contradiction

The checker first enumerates all 6,668 class-count profiles on 250 vertices
with maximum class size five and canonical sum at most 8,276.  The maximum
number and complete family of compatible size-five top packings are derived
from the graph's independently enumerated stable 5-sets.  No certificate
bound limits this initial enumeration.

Layered conclusions filter profiles only under their checked conditions.
For every survivor, residual and LPBB conclusions are tried only on an exact
matching top packing and only when their checked caps hold.  Acceptance
requires every profile/top-packing branch to be rejected.  The result also
requires every one of the five rational and six LPBB conclusions to have an
applicable, rejecting use.  A valid but weaker certificate therefore causes
`mathematical proof incomplete` rather than inheriting a historical cap.
