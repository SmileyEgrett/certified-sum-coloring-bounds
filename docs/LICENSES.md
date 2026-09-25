# Licenses and third-party material

Copyright (c) 2026 Olawale Titiloye for the author's original contributions.

| Material | License |
| --- | --- |
| Original source code and executable scripts, including checkers, model generators, tests and build/replay scripts | [MIT](../LICENSE-MIT), SPDX identifier `MIT`. |
| Manuscript PDF and LaTeX, original figures and tables, documentation, and original certificate/witness data and generated research records | [Creative Commons Attribution 4.0 International](../LICENSE-CC-BY-4.0), SPDX identifier `CC-BY-4.0`, to the extent copyright or similar rights apply. |

These terms apply to the components identified above; they are not alternative
licenses for every file. They also cover the author's corresponding original
files inside the bundled direct-master archive, which carries its own license
texts and scope notice. Attribute the original work to Olawale Titiloye and
retain the notices required by the applicable license.

Third-party material retains its own copyright and license notices. These
licenses grant no rights in external material beyond the author's rights.
Benchmark graph files and duplicate edge/adjacency serializations are not
distributed here. The [graph retrieval instructions](GRAPH_PROVENANCE.md)
identify their public sources and hashes; source identity is not a
redistribution permission.

The static replay uses installed Python standard-library facilities, C++20,
shell tools and OpenSSL headers/libcrypto; those dependencies are not bundled.
The optional direct-master rerun fetches pinned HiGHS 1.11.0 source with its
complete upstream MIT and bundled third-party notices. No HiGHS binary or
vendor source tree is distributed in this companion.
