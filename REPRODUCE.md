# Replaying the certified evidence

Run these commands from a fresh extraction at the repository root. Basic
requirements are Bash, Python 3.10 or later with its standard library, a C++20
compiler, GNU core utilities, GNU time at `/usr/bin/time`, curl, unzip and gzip.
The DSJC500 endpoint checker also requires OpenSSL headers and libcrypto.
The supplied replay paths were tested with Python 3.10.12 and GNU time;
this is not a compatibility claim for every later interpreter or platform.
Set one-thread limits before replay:

```sh
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
```

On Linux, use `taskset -c CPU` to select one available logical CPU. Individual
package instructions describe work directories and bounded regression controls.
First verify the exact graph-free distribution:

```sh
./scripts/check_public_manifest.sh .
```

This checks distribution files and hashes, not Git history or publication rights.

First fetch the four original benchmark graphs and verify their byte hashes:

```sh
./scripts/fetch_graphs.sh
```

The script places the files in ignored local paths. See
`docs/GRAPH_PROVENANCE.md` for URLs and hashes. A wrong cached or downloaded
file stops the script.

Replay the DSJC250.9 integrated and independent checkers, and regenerate its
profile enumeration:

```sh
./evidence/dsjc250/public_artifact/scripts/replay_all.sh \
  graphs/DSJC250.9.col build/replay-dsjc250
```

The last line must be `ALL REPLAYS AND PROFILE REGENERATIONS PASSED`.

Verify the separately reproduced complete integer-master cross-check for
DSJC250.9:

```sh
./evidence/dsjc250/direct_integer_master/verify.sh graphs/DSJC250.9.col
```

The last line must be
`DSJC250.9 DIRECT INTEGER MASTER STATIC VERIFICATION PASSED`. This check
reconstructs the graph-free package, verifies its runtime manifest and exact
model, and independently checks both returned integer colorings. It does not
rerun HiGHS branch-and-bound; the optional full rerun is documented in that
directory.

Replay the DSJC500.9 initial and conditional certificate stages:

```sh
(cd evidence/dsjc500/dsjc500_integrated && ./scripts/replay.sh)
```

The last line must be `DSJC500.9 INTEGRATED DELTA CHECK PASSED`. The replayed
interval is [29,791, 29,848]; 1,165 lower-cost cells remain unresolved.
Graph-free profiles at 29,789 and 29,790 exist; the certified
packing-specific restrictions exclude them, as explained in the
[proof report](evidence/dsjc500/dsjc500_integrated/REPORT.md).

Check the three exact continuous points for the lowest remaining cells with
the separate bounded entry point. Set `CHECK_WORK` to a fresh directory
outside this checkout:

```sh
bash evidence/dsjc500/fractional_profile_points/verify.sh "$CHECK_WORK"
```

The final line must be `DSJC500_ENDPOINT_REPLAY_PASS` and the process must
exit zero. The [package instructions](evidence/dsjc500/fractional_profile_points/README.md)
give dependencies, fixed input identities and regression controls. This
checks rational feasibility for the displayed conditioned continuous model
and correspondence with the three 29,791 cells; it supplies no integer
coloring and does not replay the integral exclusions. The other
1,162 unresolved cells lie above 29,791, so excluding only the three lowest
would improve the lower endpoint by one.

Replay the DSJC1000.9 certificates and malformed-input controls:

```sh
(cd evidence/dsjc1000/DSJC1000.9_EXACT_CONDITIONAL_RELEASE_20260728 \
  && sha256sum --check --strict MANIFEST.sha256 \
  && ./scripts/verify_all.sh .)
```

The checked interval is [102,344, 103,256]. The malformed-certificate tests
must reject all thirteen mutations.

First bind the C2000.9 top-envelope certificate's stable-set input to the
authenticated graph. This enumeration must find exactly 90 six-sets and no
seven-set, and its six-set list must match the retained payload:

```sh
mkdir -p build/c2000-census
g++ -std=c++20 -O2 evidence/c2000_9/audit_tools/census_stable_sets.cpp \
  -o build/c2000-census/census
build/c2000-census/census evidence/c2000_9/C2000.9.col 7 \
  build/c2000-census/sets6.tsv > build/c2000-census/census.txt
grep -Fx 'stable_sets_size_6=90' build/c2000-census/census.txt
grep -Fx 'stable_sets_size_7=0' build/c2000-census/census.txt
gzip -dc evidence/c2000_9/top_lower_certificate/stable_sets_size_6.tsv.gz \
  > build/c2000-census/retained6.tsv
cmp build/c2000-census/sets6.tsv build/c2000-census/retained6.tsv
```

With that prerequisite checked, replay the top-envelope lower certificate and
the upper coloring:

```sh
python3 evidence/c2000_9/top_lower_certificate/verify_c2000_9_top_envelope.py \
  --sets evidence/c2000_9/top_lower_certificate/stable_sets_size_6.tsv.gz \
  --certificate evidence/c2000_9/top_lower_certificate/top_layer_certificate.json
python3 evidence/c2000_9/audit_tools/verify_c2000_graph_witness.py \
  --graph evidence/c2000_9/C2000.9.col \
  --coloring evidence/c2000_9/upper_witness/best.coloring
```

These checks give lower bound 381,823 and a proper 402-class coloring of sum
382,379. The exact fractional-coloring and sum-master certificates have
separate checkers:

```sh
(cd evidence/c2000_9/c2000_fractional_exact_certificate_20260913T122045Z \
  && python3 source_snapshot/verify_fractional_coloring.py . \
  && python3 source_snapshot/verify_sum_master.py .)
```

Their outputs include exact fractional chromatic value 1948/5 and exact
floor-capped piecewise-linear sum-master optimum 381,823. Those LP equalities do not claim that
the minimum-sum coloring itself is known exactly for C2000.9.

The package instructions describe the models, proof formats and regression
controls in more detail. A passing manifest checks identity; each mathematical
claim requires the corresponding certificate and witness replay.
