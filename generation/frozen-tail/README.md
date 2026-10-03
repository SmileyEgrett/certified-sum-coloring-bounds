# Frozen-tail optimization

This program improves a proper coloring while keeping its classes of size at
least five fixed. It enumerates the stable sets of the remaining induced graph
and solves an integer set-partitioning model with HiGHS. The returned complete
assignment is checked against every edge and its sum is recomputed as an integer.

The supplied C2000.9 starting assignment has sum 382,384. Its 362 fixed classes
leave 138 vertices. The residual graph has independence number four and 2,051
nonempty stable sets. Optimizing this tail gives a proper coloring of sum 382,379.

## Running

Use Python 3.10 or later with `highspy`, `networkx`, `numpy` and `scipy`
installed. `requirements.txt` pins the dependency versions used in validation.
Run from the companion root after fetching its graph inputs:

```sh
python3 -m venv build/tail-env
build/tail-env/bin/pip install -r generation/frozen-tail/requirements.txt
build/tail-env/bin/python generation/frozen-tail/solve_frozen_tail.py \
  --graph graphs/C2000.9.col \
  --coloring generation/frozen-tail/source-382384.coloring \
  --output-dir build/c2000-tail --threads 1
```

The output directory must not already exist. The program writes the LP model,
stable-set list, metadata, solver log, result summary and complete coloring.
`--build-only` writes the model without starting the solver. One solver thread
is the default; there is no imposed time or node limit. Enumeration may be
expensive for other graphs, so run within an appropriate memory allocation.

## Formulation and verification

A binary variable selects each nonempty residual stable set. Vertex equations
require these sets to form a partition. For every size threshold s, the number
q_s of selected sets of size at least s equals a sum of binary segment variables
y_(s,j). These variables have costs j = 1, ..., floor(n_tail/s). Minimization
therefore assigns the cheapest q_s segments and gives q_s(q_s+1)/2. Summing over
s is exactly the canonical coloring sum of the tail.

If k classes are fixed, the full objective is the fixed-prefix sum plus
k*n_tail plus the tail's canonical sum. This decomposition requires every tail
class to be no larger than the smallest fixed class. The program checks that
condition through complete stable-set enumeration and rejects inputs that
violate it. With no fixed classes, the model covers the whole graph. An empty
tail needs no optimization.

The formulation is exact, but HiGHS performs floating-point optimization.
Its reported optimality does not supply a replayable exact lower-bound proof.
For the paper's upper bound, the relevant evidence is the proper complete
coloring and its independently checked sum. The paper's lower-bound certificates
are separate.

The source coloring contains the starting assignment used for the recorded
finishing step. The search software in the adjacent directory supports modern
heuristic searches; reproducing this finishing step does not reproduce the
earlier stochastic trajectory that found the starting assignment.

Original code is licensed under MIT; see `LICENSE-MIT`.
