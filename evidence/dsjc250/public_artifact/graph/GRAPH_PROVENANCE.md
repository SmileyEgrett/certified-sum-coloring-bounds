# DSJC250.9 graph provenance and byte grammar

The DIMACS graph is fetched separately; no permission to redistribute its bytes is asserted by this package. The proof is bound to the graph by both its raw bytes and a canonical edge-set serialization. Obtain the file from the authoritative COLOR03 instance endpoint:

`https://mat.tepper.cmu.edu/COLOR03/INSTANCES/DSJC250.9.col`

From the `evidence/dsjc250/public_artifact` directory, use
`python3 -B scripts/fetch_graph.py ../../../graphs/DSJC250.9.col`.
The `-B` flag prevents local module caches from adding files to the exact
artifact manifest. Alternatively, retrieve the same URL by another method
and run `python3 -B scripts/check_graph.py FILE` from that directory.
See the [replay prerequisites](../../../../REPRODUCE.md) for the required tools.

Expected identity:

- 255,403 bytes; 27,910 physical lines;
- 250 vertices; 27,897 distinct undirected edges;
- raw SHA-256 `1b90f811e4d44f8937075865790b845e986b08b9da53caea57b2adf1c57383e7`;
- canonical SHA-256 `52be422c0065411e126008bf4ee8ee2ba21320bde0a0e94d5ab308c2e34f53a8`.

## Canonical byte grammar

After a strict DIMACS parse, normalize every edge to `(min(u,v),max(u,v))`, reject loops and duplicate undirected edges, and sort edges lexicographically. The canonical byte sequence is ASCII with LF line endings and a terminal LF:

```text
exact_mscp_graph_v1\n
vertices 250\n
u_1 v_1\n
...
u_27897 v_27897\n
```

Here each integer is base-10 without a sign or leading zero, every edge has `u_i<v_i`, and the edge sequence is strictly increasing. `scripts/check_graph.py` reproduces both hashes and fails closed on any lexical, dimensional, or identity mismatch.

This distribution uses authenticated retrieval only. Adding graph bytes in a later release would require a documented redistribution basis.
