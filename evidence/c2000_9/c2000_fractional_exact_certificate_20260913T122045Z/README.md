# Exact C2000.9 fractional colouring and sum-master certificates

**Certified: chi_f(C2000.9) = 1948/5 = 389.6.**

The package contains a rational fractional colouring, its matching dual, the separately fetched graph and independent standard-library verifiers. Verification reconstructs the required stable-set facts directly from graph bytes. No numerical solver status, commercial license, precomputed stable-set census, NumPy or FLINT is needed to check the result.

## Verify

Use the [shared replay prerequisites](../../../REPRODUCE.md). First fetch the authenticated graph with the paper repository root script scripts/fetch_graphs.sh. Then enter this directory:

```sh
sha256sum -c SHA256SUMS
python3 source_snapshot/verify_fractional_coloring.py .
python3 source_snapshot/verify_sum_master.py .
```

The first checker proves the exact fractional chromatic value. The second proves that the floor-capped complete minimum-sum-colouring master has exact optimum **381,823 both without and with an explicit k>=390 restriction**. These are fractional certificates; integer 390-colourability remains open.

## Replay harness process controls

The harness regression suite uses Python 3.10 or later and additionally requires Linux `/proc`, Bash, a C++20 compiler, GNU `taskset`, `timeout` and `sha256sum`. Give it a new disposable directory and one allowed logical CPU; it copies this package before every injected failure and signals only children whose command line contains that unique copied root.

```sh
tests/test_harness_process_outcomes.sh /new/disposable/harness-tests 16
```

The default `all` suite runs both maintained harness baselines and the targeted process-outcome controls. Pass `baselines`, `controls`, `controls-v1` or `controls-v2` as an optional third argument to replay only that group. The script applies 2 GiB address-space limits and explicit wall deadlines. A child timeout, signal, crash, wrong exit status or missing semantic-rejection diagnostic is expected to make its harness fail; it is never recorded as a successful semantic rejection.

## Fractional primal and dual

`EXACT_FRACTIONAL_COLORING.json` lists 1,829 positive stable-set terms: 1,757 five-sets and 72 six-sets. Numerators and the common denominator are decimal strings to preserve arbitrary precision. The denominator has 242 digits.

The exact total weight on five-sets is 1688/5, and on six-sets it is 52. Every vertex has coverage exactly 1 and total weight is exactly 1948/5.

The dual assigns weight 0 to a listed 52-vertex set H and 1/5 to every other vertex. The checker exhaustively enumerates independent sets of R=V\H through size 6, finding counts

    (1948, 188767, 1212650, 579560, 21708, 0).

Thus alpha(G[R])=5 and every stable set has dual weight at most 1. The exact primal and dual objectives agree, proving chi_f=1948/5, and hence chi>=390.

## Exact sum-master consequence

For the original fractional partition the Ferrers coordinates are

    q=(1948/5,1948/5,1948/5,1948/5,1948/5,52).

The master uses the piecewise-linear interpolation of T(q)=q(q+1)/2 at integer q, equivalently segment variables y_tj in [0,1] with costs j and sum_j y_tj=q_t. It has the original caps q_t<=floor(2000/t). The exact objective of this primal is 381,823.

`SUM_MASTER_K390_PRIMAL.json` is obtained by splitting a total weight 2/5 of five-sets into pairs and triples, preserving exact vertex coverage. Its coordinates are

    q=(390,390,1948/5,1946/5,1946/5,52),

and its exact objective is also 381,823. The split history is included. All new classes are subsets of original stable sets.

The independent master checker reconstructs all stable sets through size 7 directly from the graph, obtaining

    (2000,199468,1322912,656504,26224,90,0).

It checks the dual with vertex weights 390 outside H and 52 inside H, slopes (390,390,390,390,390,52) and intercepts (75855,75855,75855,75855,75855,1326). All stable-set inequalities and Ferrers support inequalities pass in integer arithmetic; the exact dual value is 381,823. The two matching exact primals establish both claimed LP optima. This does not prove the graph's integer chromatic sum equals its LP bound.

## Transversal intersections

Among the complete family of 90 six-sets, 89 meet H once and one meets H
twice. In particular, H meets every six-set, as required by the dual bound.

## Package identity

`manifest/frozen.json` identifies the checker sources and the two exact
primal JSON files. `SHA256SUMS` binds the supplied package and authenticated
external graph. The exact arithmetic replay verifies the fractional-coloring
and floor-capped sum-master claims without running an optimizer. Neither
primal certificate is an integer coloring.
