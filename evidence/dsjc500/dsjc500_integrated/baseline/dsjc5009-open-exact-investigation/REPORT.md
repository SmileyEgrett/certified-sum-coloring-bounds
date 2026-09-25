# DSJC500.9 initial profile reduction

## 1. Role in the complete proof

This certificate stage proves `29785 <= Sigma(DSJC500.9) <= 29848` and leaves 1,269 packing/profile cells through 29,847. It is an intermediate result: the [integrated proof](../../REPORT.md) uses the P2/P4 bound `h4 <= 100` and conditional trees to reduce that census to 1,165 and raise the lower endpoint to 29,791. The integrated verifier checks the intermediate values 29,785 and 1,269 before consuming the further exclusions.

The supplied coloring is checked as a proper 128-class coloring of canonical sum 29,848. This stage reconstructs the graph, all stable sets through size six and the eight maximum five-set packings. Eight rational covering duals and six branch-and-dual trees establish `h4 <= 101` under every top packing. Eight Farkas certificates exclude the sole surviving 123-class profile, and three more exclude specified 124-class cells. Every remaining threshold candidate has 124 through 132 classes. The certificates do not assert the feasibility of a surviving cell or optimality of the coloring.

Only finite certificates checked by `scripts/verify.py` are proof premises. Floating-point solver output used in certificate construction is not accepted as proof.

## 2. Exact instance identity

The verifier binds the work to both the raw graph bytes and a canonical undirected-edge representation.

| Item | Exact value |
|---|---:|
| vertices | 500 |
| unique unordered edge records | 112,437 |
| DIMACS header edge count | 224,874 |
| graph raw SHA-256 | `95276841dffcde7c04de2fc1ae8e43b6c7b84173b4a9646b1cc6b392a3bd7b39` |
| graph canonical SHA-256 | `69e7453e2a389197f67fe0e02cf661bc71132b4ea457a434b4726a4b7489b618` |
| incumbent coloring SHA-256 | `3f948845ad75ea1ed742916229e6060cab99d6839b7a109af59825e496804760` |

The DIMACS header is unusual: it reports exactly twice the number of undirected `e` records. The verifier does not silently repair this. It requires the exact raw hash, exact canonical hash, 112,437 unique unordered records, and header value 224,874.

## 3. Independently reconstructed graph facts

All stable sets through size 6 are enumerated directly from the graph.

| stable-set size | count | family SHA-256 |
|---:|---:|---|
| 2 | 12,313 | `e7810701a2d9477ff96b584ef766501d4163a922abe13a677da46de606b3f19a` |
| 3 | 19,901 | `978a5d78137f3552350375a4ea44ce1fdb7b7ed8cc838a26c9fc6158bf312501` |
| 4 | 2,428 | `b37042490f13c8fd13b783063a0e7a9f310c675358c34adcb4d815626aa34683` |
| 5 | 23 | `df73ea745b075ec6f949e8be027e687b10afdb1e45f06425e9081565e348d215` |
| 6 | 0 | SHA-256 of the empty family |

Hence the independence number is exactly 5.

The 23 stable 5-sets have maximum packing number 15. Exhaustive packing enumeration finds exactly eight maximum packings. Twelve 5-sets occur in every maximum packing. Sixty-six vertices are covered by every maximum packing, and 84 vertices are covered by at least one maximum packing.

The incumbent's 15 size-5 classes are reconstructed as maximum packing 5 in the verifier's deterministic ordering.

## 4. Incumbent verification

The supplied coloring assigns every vertex exactly once, uses contiguous labels 1 through 128, and contains no graph edge within a color class. Its class-size multiplicity profile is

$$
(h_1,h_2,h_3,h_4,h_5)=(3,4,10,96,15).
$$

The class sizes are already nonincreasing by label. Both the literal label sum and the canonical reordered sum are 29,848. Thus

$$
\Sigma(DSJC500.9)\le 29,848.
$$

## 5. Complete threshold-profile reconstruction

Let `h_s` be the number of classes of size `s`, and let

$$
g_i=\sum_{s=i}^{5}h_s
$$

be the Ferrers/GE column heights. For a canonical coloring,

$$
\Phi(h)=\sum_{i=1}^{5}\binom{g_i+1}{2}.
$$

The checker enumerates the full graph-free range, not merely a preselected strength interval. Since `g1=q` and `T(q)=q(q+1)/2`, only `100 <= q <= 243` can possibly have value at most 29,847; `q >= 100` also follows from 500 vertices and independence number 5.

The maximum 5-set packing gives `h5 <= 15`. Exhaustive integer Ferrers-profile enumeration over the full range `100..243` produces exactly 230 profiles with value at most 29,847. Every one has `h5=15`, and their strengths are exactly 122 through 132. This derives the strength window from the complete enumeration.

Because `h5=15`, every threshold counterexample fixes one of the eight maximum 5-set packings and leaves 425 vertices for classes of sizes 1 through 4.

## 6. Exact residual 4-set bounds

### 6.1 Rational covering duals

For each maximum 5-set packing `P`, the bundle contains nonnegative integer vertex weights `w_v` with denominator

$$
D=10^{12}
$$

such that every residual stable 4-set `C` satisfies

$$
\sum_{v\in C}w_v\ge D.
$$

For any disjoint family of residual 4-sets, summing these inequalities gives an upper bound equal to

$$
\left\lfloor\frac{\sum_v w_v}{D}\right\rfloor.
$$

The verifier reconstructs the complete residual 4-set family and checks every column inequality exactly.

| packing | residual 4-sets | dual bound | exact slack `sum(w)-D*bound` |
|---:|---:|---:|---:|
| 1 | 1,178 | 102 | 75,906,219,994 |
| 2 | 1,170 | 101 | 735,831,681,356 |
| 3 | 1,156 | 102 | 21,461,535,279 |
| 4 | 1,148 | 101 | 658,005,568,971 |
| 5 | 1,180 | 102 | 443,918,708,503 |
| 6 | 1,171 | 102 | 114,416,084,937 |
| 7 | 1,158 | 102 | 367,318,689,347 |
| 8 | 1,149 | 102 | 15,463,732,915 |

### 6.2 Exact branch-and-dual certificates

Proof trees reduce the six rational bounds of 102 to 101. Packings 2 and 4 have rational bound 101, so the resulting universal conclusion is

$$
h_4\le101.
$$

For a packing whose rational bound is 102, define the exact excess of a residual quad `C` by

$$
e(C)=\sum_{v\in C}w_v-D\ge0,
$$

and let `S` be the exact rational-dual slack. If 102 disjoint quads existed, their total excess would be at most `S`. The proof tree branches on candidate quads. An include branch removes all intersecting columns and subtracts `e(C)` from the remaining excess budget; an exclude branch deletes only that column.

Every leaf is closed by integer data. If `t` more quads are required and `R` excess remains, a leaf supplies nonnegative integer vertex weights `W_v`, a nonnegative integer budget multiplier `M`, and denominator `Q=10^9` satisfying, for every active quad `C`,

$$
D\sum_{v\in C}W_v+e(C)M\ge DQ,
$$

while

$$
D\sum_v W_v+RM<tDQ.
$$

Weak duality then makes a completion of size `t` impossible. The verifier reconstructs the exact active column set at every node and checks all inequalities with arbitrary-precision integers.

| packing | proof records | leaves | maximum depth | certified bound |
|---:|---:|---:|---:|---:|
| 1 | 5 | 3 | 2 | 101 |
| 3 | 3 | 2 | 1 | 101 |
| 5 | 87 | 44 | 9 | 101 |
| 6 | 7 | 4 | 3 | 101 |
| 7 | 41 | 21 | 6 | 101 |
| 8 | 3 | 2 | 1 | 101 |

The trees are stored in `certificates/k4_lpbb/`. No optimizer status is a leaf rule.

## 7. Elimination of strengths 122 and 123

Applying `h4 <= 101` to the 230 threshold profiles leaves exactly 160 profiles per maximum 5-set packing.

- all strength-122 profiles require at least 102 size-4 classes and disappear;
- exactly one strength-123 profile survives:

$$
(h_1,h_2,h_3,h_4,h_5)=(0,0,7,101,15),
$$

with value 29,784.

After fixing any maximum 5-set packing, this profile would partition all 425 residual vertices into exactly 101 stable quads and seven stable triples.

For each of the eight packings, the package contains an integer Farkas certificate. It supplies residual vertex multipliers `y_v`, a quad-quota multiplier `a_4`, and a triple-quota multiplier `a_3` such that

$$
\sum_{v\in C}y_v+a_4\ge0
$$

for every reconstructed residual stable quad,

$$
\sum_{v\in T}y_v+a_3\ge0
$$

for every reconstructed residual stable triple, but

$$
\sum_v y_v+101a_4+7a_3<0.
$$

Multiplying the proposed exact-cover equations by these integers gives a nonnegative left side and a negative right side, a contradiction. The exact negative right sides for packings 1 through 8 are respectively

$$
-57,-54,-54,-39,-59,-31,-37,-33.
$$

Thus no coloring of value at most 29,847 can have fewer than 124 classes.

## 8. Three additional exact strength-124 eliminations

Three further cells have integer Farkas certificates with quota multipliers for all residual class sizes 1 through 4.

| packing | residual profile `(h1,h2,h3,h4)` | full value | exact Farkas RHS |
|---:|---|---:|---:|
| 1 | `(1,1,6,101)` | 29,785 | -57 |
| 3 | `(1,1,6,101)` | 29,785 | -49 |
| 3 | `(0,3,5,101)` | 29,787 | -53 |

For every residual stable set of size `s`, the checker verifies

$$
\sum_{v\in C}y_v+a_s\ge0,
$$

and verifies that the weighted sum of all vertex-cover and quota right sides is negative.

These cuts do not eliminate strength 124 globally: the same profiles remain unresolved in other maximum 5-set packings.

## 9. Initial-stage profile census

After the universal `h4 <= 101` bound, there are 160 profiles per packing. Eight strength-123 cells and the three strength-124 cells above are exactly eliminated. The remaining cell count is 1,269.

| strength | unresolved packing/profile cells |
|---:|---:|
| 124 | 45 |
| 125 | 120 |
| 126 | 192 |
| 127 | 248 |
| 128 | 232 |
| 129 | 192 |
| 130 | 144 |
| 131 | 80 |
| 132 | 16 |
| **total** | **1,269** |

The smallest unresolved profile value is 29,785. Since every profile below 29,785 has been excluded, the lower bound from this stage is

$$
\Sigma(DSJC500.9)\ge29,785.
$$

Together with the incumbent:

$$
\boxed{29,785\le\Sigma(DSJC500.9)\le29,848.}
$$

## 10. Checking and failure behavior

`scripts/verify.py` uses only the Python standard library. It:

1. checks a strict SHA-256 manifest and rejects missing, extra, altered, unsafe, or symlinked files;
2. strictly parses the graph and coloring;
3. reconstructs every stable set of sizes 2 through 6;
4. reconstructs all maximum 5-set packings;
5. checks every original rational-dual column;
6. reconstructs every LPBB state and checks every leaf inequality exactly;
7. reconstructs all residual column families consumed by every Farkas certificate;
8. enumerates the complete graph-free threshold profile range through strength 243;
9. derives, rather than hardcodes independently, the conclusions used in the final profile reduction.

The exact quota, score-relevant profile, graph identity, top packing, column-family hashes and derived bound are checked before a conclusion is consumed. A certificate supports only the bound and conditions actually established by these checks.

Malformed JSON, noncanonical graph structure, altered family data, wrong quotas, unreachable proof records, invalid branches, nonnegative Farkas right sides, or any failed integer inequality cause a nonzero exit.

## 11. Replay and recorded generation timings

The release checker completed in approximately 1.4 seconds wall time with about 139 MiB peak resident memory on the recorded environment. The six retained LPBB certificates took approximately 1.1, 1.1, 6.1, 1.4, 3.3, and 1.1 seconds wall time for packings 1, 3, 5, 6, 7, and 8. The eight primary Farkas searches each took about one second of solver time; the three additional profile Farkas searches took about 3.1 to 3.5 seconds each.

Use the [shared replay prerequisites](../../../../../REPRODUCE.md), including Python 3.10 or later. After graph retrieval from the repository root, run `PYTHONDONTWRITEBYTECODE=1 bash scripts/verify.sh` from this directory to check this stage alone. The complete proof is replayed with `scripts/replay.sh` from the enclosing integrated package. See [PROOF_FORMAT.md](PROOF_FORMAT.md) for certificate semantics. Generation timings describe the recorded environment; replay uses only the supplied certificates and Python standard library.
