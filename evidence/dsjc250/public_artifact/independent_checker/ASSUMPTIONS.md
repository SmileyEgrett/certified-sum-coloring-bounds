# Trust boundary and assumptions

The checker recomputes graph identity, stable-set census, maximum stable sets, compatible maximum-class packings, the coloring sum, certificate inequalities, branch-tree semantics, all 6,668 sub-incumbent profiles, and universal profile/packing exclusion with exact integer arithmetic. It does not infer correctness from an optimizer status, floating-point value, payload hash alone, expected profile count, or certificate name alone.

The accepted proof language is release-specific: two conditioned layered rational bounds, three exact-top residual size-four rational bounds, and six named LPBB score models. A checked conclusion applies only under its returned conditions, top sets, caps, coefficients, and target. See `PROOF_FORMAT.md`.

Conventional trust remains in the Python interpreter/standard library, SHA-256, gzip/JSON implementation, hardware/OS, and the audited mathematical reduction. The proof data are substantially shared with the integrated archive; see `../docs/SHARED_COMPONENTS.md`.
