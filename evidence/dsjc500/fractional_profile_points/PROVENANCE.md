# Endpoint data and reconstruction identities

The three rational points and their reconstruction record have these identities:

| File | SHA-256 |
| --- | --- |
| `certificates/fractional_lp/P5E_fractional_exact.json` | `25e14e3725e7629f4edce87dcb60848755edf5109ad8fc7fb1574d423cdaea5b` |
| `certificates/fractional_lp/P5F_fractional_exact.json` | `9e3f7e8d3d2e70c00bbb9ac4fcce230829690f60cc2fdb12a5dd3a6087391285` |
| `certificates/fractional_lp/P7F_fractional_exact.json` | `187ea34d08ebc1d4840cf11240656f7bc836572273735ef36aece92b6967e147` |
| `certificates/reconstruction.json` | `95758a2d7144dbc84c3a032237ccef0a4cc554d9385e7d4e2cb4d98fd372c19c` |

The graph and final census identities are specified in [README.md](README.md).
The reconstruction record fixes stable-set ordering and top-packing names.
The bounded checker validates these identities before interpreting the points,
reconstructs the graph-derived objects and checks rational feasibility exactly.
It also checks the four graph-free counterprofiles at 29789 and 29790, each of
which violates the certified `h4 <= 101` restriction.

The reconstruction record's `packet_sha256`, timing and platform fields and
the point discovery metadata describe the source computation. They do not
supply mathematical premises or require another archive for replay. The
source endpoint package has SHA-256
`042e3636a265ddf0a95ef53691bfea57d8c560c7859ae191f94d93de45851fe5`.

[SHA256SUMS](SHA256SUMS) identifies the supplied data, checker, shell entry
point, controls and documentation. A manifest is an identity record; the
proof interpretation additionally depends on graph reconstruction, exact
arithmetic and the model specified in the paper. The separate integral
package establishes the lower bound; these points establish continuous
feasibility only.
