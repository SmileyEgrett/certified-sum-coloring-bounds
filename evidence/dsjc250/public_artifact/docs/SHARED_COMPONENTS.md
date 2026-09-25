# Checker implementation diversity and shared components

The release contains two author-supplied checker implementations, not two fully independent research-group replications.

## Shared or substantially shared

- the externally retrieved DIMACS graph identity and the 8,277 coloring;
- both layered rational certificates;
- all six canonical column TSVs;
- all six underlying proof-tree record arrays and roots (identical after parsing); the gzip wrapper objects differ because the second format embeds model and column data;
- the underlying conditional rational weight vectors and fixed tops, although wrapper/schema syntax differs;
- the mathematical reduction, profile frontier, and S1--S11 claims.

## Separately implemented

- graph parsing code and canonical-hash construction;
- stable-set enumeration code paths;
- profile enumeration and case-routing code;
- certificate parsers and structural validation logic;
- rational arithmetic checks and proof-tree traversal code;
- result/report schemas.

The integrated checker reads campaign descriptors, model JSON, and TSV files, then reconstructs and binds every complete column sequence. The second checker hard-codes the six model specifications and reconstructs the columns directly; its embedded proof model and columns are checked against that reconstruction. Its copied JSON model/TSV files are manifest-bound release evidence but are not the semantic source used by its tree traversal.

Accordingly, agreement is evidence of implementation diversity over substantially shared proof data. It is stronger than one checker alone, but it is not a clean full-artifact replay by an unaffiliated group and not independent research-group replication.
