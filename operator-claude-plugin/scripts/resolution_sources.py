"""operator-claude-plugin/scripts/resolution_sources.py

D-59-08 (operator ruling, 2026-08-28)'s CLOSED vocabulary of legitimate sources a
Claude-resolved value may claim, factored out of `extraction.py` into its own module
(59-06 Task 1) so `enrichment.py` can import it without a circular import.

The cycle is real and was verified live before this module existed: `enrichment ->
extraction -> preview -> preview_enrichment -> chunking -> enrichment`. `chunking.py`
imports `enrichment` at module level, and `extraction.py` imports `preview` (for
`resolve_mapping_path`), which imports `preview_enrichment`, which imports `chunking`.
Whichever module is imported FIRST in a given process wins the race; when it is
`extraction`, `enrichment`'s own top-level `from extraction import RESOLUTION_SOURCES`
would hit `extraction` mid-initialization and raise `ImportError: cannot import name`.
This module has no imports of its own, so it cannot be part of that cycle either way.

`extraction.RESOLUTION_SOURCES` is the SAME object, re-exported by import — nothing
that already reads `extraction.RESOLUTION_SOURCES` needs to change.

Illegitimate — and still forbidden no matter what a resolution claims — are: Claude's
own recall about the person or company from training data; inference from "companies
like this usually..."; a plausible corporate email pattern (`first@company.com`);
anything the operator would have no way to check. A resolution naming a source outside
this set is rejected rather than accepted unlabelled (T-59-20).
"""

RESOLUTION_SOURCES = frozenset({
    "hubspot_lookup",
    "operator_statement",
    "provider_result",
    "same_row_derivation",
})
