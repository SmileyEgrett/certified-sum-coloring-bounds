# DSJC500.9 exact certificate report

## Certified result

The integrated standard-library replay certifies

```text
29,791 <= Sigma(DSJC500.9) <= 29,848.
```

The upper bound is the supplied explicit proper coloring, checked by the baseline verifier against every edge and recomputed canonically. The release does not claim that 29,848 is optimal.

## Proof stages

The initial stage in `baseline/dsjc5009-open-exact-investigation/` enumerates 230 graph-free threshold profiles. The certified bound `h4 <= 101` leaves 160 profiles for each of eight top packings. Eleven Farkas exclusions reduce the resulting 1,280 cells to 1,269 and prove the intermediate lower bound 29,785. The integrated verifier checks this stage before applying the further exclusions below. See the [initial-stage report](baseline/dsjc5009-open-exact-investigation/REPORT.md) for its certificates and model definitions.

### One-unit residual four-set bounds

Exact branch-and-dual trees establish

```text
P2: h4 <= 100
P4: h4 <= 100
```

The retained trees contain 761 and 589 records, respectively, with maximum depths 14 and 13. Every terminal is checked by arbitrary-precision integer covering inequalities against the reconstructed residual stable-four-set family. These two bounds remove exactly 74 of the baseline's 1,269 unresolved packing/profile cells.

### Conditional envelope portfolio

Seventeen exact weighted conditional trees are retained. Their score systems are radix encodings with radix 501:

- `H36`: score `501*h4 + h3`, caps `h4 <= 101`, `h3 <= 6`, strict target `50,607`. Six trees rule out 101 quads together with six triples under P1, P3, P5, P6, P7, and P8.
- `A`: score `251001*h4 + 501*h3 + h2`, caps `h4 <= 101`, `h3 <= 4`, strict target `25,353,109`. Trees are retained for P1, P3, P6, P7, and P8.
- `B`: the same score, caps `h4 <= 101`, `h3 <= 5`, strict target `25,353,607`. Trees are retained for P1, P3, P6, and P8. These conclusions also exclude the mapped profiles with larger pair counts and the same quad and triple counts.
- `C`: the same score and caps as B, strict target `25,353,608`. Trees for P5 and P7 close the 29,787 and 29,788 pair-demand cells without asserting the still-open B targets.

The registry maps the exact conclusions to 30 distinct cells not already eliminated by the initial stage or the P2/P4 bounds. Each mapping is checked against the verified top packing, caps, score and strict target.

### Cell census

The verifier reconstructs the census from profile arithmetic rather than trusting stored totals:

```text
baseline certified unresolved cells        1,269
removed by P2/P4 h4 <= 100                   74
removed by exact conditional mappings         30
final certified unresolved cells          1,165
```

The lowest remaining objective is 29,791. Exactly three cells remain at that value:

```text
P5  (h1,h2,h3,h4,h5) = (1,4,4,101,15)
P5  (h1,h2,h3,h4,h5) = (4,1,5,101,15)
P7  (h1,h2,h3,h4,h5) = (4,1,5,101,15)
```

Graph-free profiles at both 29,789 and 29,790 exist:

| `(h1,h2,h3,h4,h5)` | `Phi(h)` |
| --- | ---: |
| `(3,5,0,103,15)` | 29789 |
| `(7,0,2,103,15)` | 29789 |
| `(3,4,2,102,15)` | 29790 |
| `(6,2,1,103,15)` | 29790 |

All four violate the graph-dependent certified bound `h4 <= 101` under each maximum five-set packing. Their exclusion is therefore not a graph-free objective gap. The [endpoint checker](../fractional_profile_points/README.md) retains regression checks of all four counterprofiles. Together with the other certified exclusions, this proves that every cell below 29,791 is infeasible. The remaining 1,165 cells comprise these three at 29,791 and 1,162 above them through 29,847; feasibility of those cells remains unresolved.

## Explicit splitting frontier

Under a fixed maximum size-five packing, a residual class can be split as follows:

```text
2 -> 1+1
3 -> 2+1 or 1+1+1
4 -> 3+1, 2+2, 2+1+1, or 1+1+1+1
```

Feasibility propagates only in this splitting direction. The release constructs the complete post-P2/P4, pre-conditional family of 1,195 admissible cells and an explicit shortest splitting path from every cell to a splitting-maximal target. Every path is replayed step by step and kept inside the admissible family.

The maximal antichain has 178 cells:

- 23 each for P1, P3, P5, P6, P7, and P8;
- 20 each for P2 and P4.

This reduction is safe because a coloring of a source profile directly yields a coloring of every profile on its recorded splitting path while preserving the fixed size-five packing. No converse refinement claim is used.

## Supporting-normal reconstruction

The exact positive lower hull of the frontier in coordinates `(h4,h3,h2)` is reconstructed by primitive integer cross products.

For the 23-point `h4 <= 101` frontier, the seven primitive normals and targets are:

```text
(2,1,1)    204
(5,2,1)    504
(5,3,1)    511
(7,3,1)    707
(7,4,2)    717
(11,5,1)  1109
(13,7,3)  1327
```

For the 20-point `h4 <= 100` frontier, the additional facet is:

```text
(3,2,1)    309
```

The release stores every equality face and independently checks that each target is the exact minimum over the associated frontier.

## Fixed-incumbent structural certificate

Fixing all 15 size-five and all 96 size-four classes of the incumbent leaves 41 vertices. Exact reconstruction certifies:

- no residual stable four-set;
- 21 residual stable triples and 97 residual stable pairs;
- maximum disjoint triple packing 10;
- exactly 12 maximum triple packings;
- maximum residual matching after a maximum triple packing 4.

For every maximum triple packing, the certificate stores an explicit matching and a Tutte--Berge barrier whose odd-component count proves optimality. The nine improving arithmetic completions retaining all fixed top classes are then excluded: eight require at least 11 triples, and the remaining profile requires five pairs after ten triples.

Therefore every coloring of canonical sum at most 29,847 changes at least one incumbent size-four or size-five class.

## Interpretation of the remaining obstruction

The remaining obstruction is a joint near-exact-cover problem, not a scalar quad-packing problem. With 15 size-five classes fixed, let `q`, `t`, and `nu` be the counts of residual quads, triples, and pairs. Then

```text
g1 = 440 - 3q - 2t - nu
g2 = q + t + nu + 15
g3 = q + t + 15
g4 = q + 15
g5 = 15
```

and the true canonical objective is the sum of the five triangular numbers `T(gi)`. For fixed `q,t`, the best terminal layer uses the maximum residual matching. The three lowest unresolved cells all require the exact balance `q=101` with either `(t,nu)=(4,4)` or `(5,1)`.

## Standalone replay

Use the [shared replay prerequisites](../../../REPRODUCE.md), including
Python 3.10 or later. From the paper repository root, first run
`./scripts/fetch_graphs.sh` to install and authenticate both required graph
copies. Then enter `evidence/dsjc500/dsjc500_integrated` and run:

```bash
./scripts/replay.sh
```

The wrapper disables Python bytecode caches so that the exact runtime file
set remains unchanged.

The verifier checks the top-level manifest, replays the initial certificate stage, reconstructs graph and stable-set data, verifies the two P2/P4 trees, verifies all 17 conditional trees and all 30 explicit conclusion mappings, rebuilds the census/frontier/normals byte-for-byte, and verifies the fixed-incumbent certificate. It uses only the Python standard library.

`RESULTS.json` records generation seconds and available peak-memory measurements for the 17 conditional trees, together with their model, column and proof hashes. A null memory field means no measurement is supplied. These records describe certificate construction; no generation script is required for replay. All lower-proof premises are the checked integer inequalities, exhaustive branch trees and deterministic graph/profile reconstructions described above.
