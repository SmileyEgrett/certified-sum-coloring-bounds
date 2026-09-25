# Exact certificate formats

## 1. Original residual 4-set duals

For a fixed maximum 5-set packing, `k4dual_P*.txt` contains one nonnegative integer weight for each residual vertex. The denominator is `D = 10^12`.

Validity conditions:

- the vertex rows are exactly the 425 residual vertices;
- every reconstructed residual stable 4-set `C` satisfies `sum(w[v] for v in C) >= D`;
- the certified packing bound is `floor(sum(w)/D)`.

The files are bound to the exact graph and top packing by reconstruction and by hashes stored in the derived certificates.

## 2. Residual-quad LPBB proof

Schema: `dsjc5009_residual_k4_lpbb_v1`.

The certificate stores:

- graph hashes;
- maximum 5-set packing indices and vertex sets;
- hashes of the complete global, residual, and saturation-eligible 4-set families;
- the exact old rational dual total, denominator, bound, and slack;
- a strict-postorder list of branch and leaf records.

A path state consists of:

- active eligible quads;
- number already selected;
- exact excess already spent.

A branch selects or excludes one active quad. Selection removes every intersecting quad.

A dual leaf with remaining target `t`, remaining excess `R`, leaf denominator `Q`, vertex integers `W_v`, and multiplier `M` is valid when every active quad satisfies

```text
D * sum(W_v on C) + excess(C) * M >= D * Q
```

and

```text
D * sum(W_v) + R * M < t * D * Q.
```

All operations are integer operations. Count and over-budget leaves have their direct combinatorial meanings.

## 3. Exact-cover Farkas certificate

Schema: `dsjc5009_exact_cover_farkas_v1`.

For the profile with 101 quads and seven triples, the certificate contains residual vertex multipliers `y_v`, quad multiplier `a4`, and triple multiplier `a3`.

The verifier checks:

```text
sum(y_v on C) + a4 >= 0   for every residual quad C
sum(y_v on T) + a3 >= 0   for every residual triple T
sum(y_v) + 101*a4 + 7*a3 < 0
```

These inequalities are a finite integer Farkas contradiction for the complete exact-cover column family.

## 4. Fixed-profile Farkas certificate

Schema: `dsjc5009_profile_farkas_v1`.

For quotas `h1..h4`, it stores residual vertex multipliers and one multiplier `a_s` per class size. The verifier reconstructs every residual stable set of each size and checks

```text
sum(y_v on C) + a_s >= 0
```

for every size-`s` column, while checking

```text
sum(y_v) + sum(h_s * a_s) < 0.
```

The graph hashes, top packing, residual vertex list, all four family hashes, and exact quotas are certificate fields. The checker consumes the conclusion only for the identically reconstructed packing/profile cell.

## 5. Manifest

`MANIFEST.sha256` lists every release file except itself in strict lexicographic order. Verification rejects extra files as well as missing or altered files. This prevents a certificate from being silently replaced while an unrelated hardcoded conclusion remains accepted.
