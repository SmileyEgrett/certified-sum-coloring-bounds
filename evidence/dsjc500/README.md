# DSJC500.9 evidence

The certified interval is `29791 <= Sigma(DSJC500.9) <= 29848`.
The census has 1,165 unresolved cells through 29847: three at 29791 and
1,162 above it. Excluding the three lowest alone would raise the lower
endpoint to 29792.

- [Integral certificate package](dsjc500_integrated/README.md): initial
  profile reduction, conditional exclusions, census, splitting paths and
  checked upper coloring.
- [Exact continuous endpoint points](fractional_profile_points/README.md):
  three rational feasible points for the paper's conditioned continuous
  models, with a bounded C++20 cross-check.
- [Repository replay guide](../../REPRODUCE.md) and
  [graph provenance](../../docs/GRAPH_PROVENANCE.md).

Graph-free profiles at 29789 and 29790 exist. Their exclusion uses the
certified packing-specific bound `h4 <= 101`; the
[integrated report](dsjc500_integrated/REPORT.md) gives the profiles and the
full reduction. Continuous feasibility of the three endpoint cells neither
supplies integer colorings nor establishes LP optimality. The endpoint check
and the integral certificate replay have separate scopes.
