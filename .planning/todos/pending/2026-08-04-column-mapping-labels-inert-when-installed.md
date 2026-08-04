---
created: 2026-08-04T04:55:00.000Z
title: Preview column labels are permanently unavailable in a standalone plugin install
area: operator-claude-plugin
severity: minor
files:
  - operator-claude-plugin/scripts/preview.py:22
  - operator-claude-plugin/config/operator.local.example.json:7
---

## Problem

Observed in UAT 1.3, 2026-08-04, on the installed 0.6.0 plugin. The upload preview rendered:

> Column labels **unavailable** (`mapping_available: false`) — can't show `header → canonical
> prop` mapping.

Cause: `preview.py:22` resolves `DEFAULT_MAPPING_PATH = REPO_ROOT / "config" /
"column_mapping.yaml"` — the **repo's** config directory, not the plugin's. `column_mapping.yaml`
is not part of the plugin package (`operator-claude-plugin/config/` ships only `cost_rates.json`
and the two operator config files), so on a machine with the plugin installed and no repo
checkout the file is never found and header labelling is inert **every time**.

This is not a behaviour defect — the resolution order is documented ("an explicit path argument,
then the repo's config/column_mapping.yaml, then unavailable — labels flagged, not guessed") and
it degrades honestly rather than guessing. It is a **packaging** gap: a documented preview
feature that the target operator (non-technical, Claude Desktop, no repo, per README) can never
see. The escape hatch `column_mapping_path` exists in `operator.local.example.json` (defaulting
to `null`) but is not mentioned in the README's setup section, so nobody would know to set it.

Not a UAT failure: no step asserts label display, and 2.2 (reads messy headers without renaming)
passed — the backend's `Map Columns` does the real mapping regardless. The labels are a display
nicety.

## Solution

TBD. Options, cheapest first:

1. **Ship a copy** of `config/column_mapping.yaml` inside `operator-claude-plugin/config/` and add
   it to the resolution order ahead of the repo path. Costs a second copy of a file that must not
   drift from the backend's — would need a test pinning the two byte-identical, which this repo
   already does for other two-sided contracts.
2. **Document `column_mapping_path`** in the README setup section and leave the behaviour alone —
   accepts that labels stay off for anyone who does not set it.
3. **Drop the feature** from the preview and the docs if the labels are not worth the coupling.

Whichever lands, the claim in `operator-claude-plugin/README.md` about reading
`config/column_mapping.yaml` should say which config directory it means.
