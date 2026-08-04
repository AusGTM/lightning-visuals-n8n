---
created: 2026-08-04T04:55:00.000Z
title: Preview column labels are permanently unavailable in a standalone plugin install
area: operator-claude-plugin
severity: MAJOR (corrected 2026-08-04 — filed as minor, was a blocker)
resolved: 2026-08-04
resolved_by: "plugin 0.7.3 — ship the file inside the package, byte-identical pin"
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


---

## Resolution (2026-08-04, plugin 0.7.3) — and a correction to this file's own severity

**Filed as `minor`, was a blocker.** This todo concluded "Not a UAT failure: no step asserts label
display" from `preview.py`'s graceful degradation. `extraction.py` — the OTHER consumer of the same
resolver — **refuses** when the file is missing (`mapping_unavailable`), because the canonical-prop
allowlist cannot be built without it and it correctly declines to validate against an empty
allowlist. Net effect on every installed copy: prose, JSON, URL and screenshot ingestion all dead.

Found by the operator walking UAT session 2 against the 0.7.2 install, days after this was filed.
The severity error came from reading one caller and generalising — the same mistake shape as the
0.6.1 and 0.7.2 defects. `grep -rn column_mapping operator-claude-plugin/scripts/` would have shown
both consumers in one command.

**Fix (option 1, as proposed):** the file ships inside the plugin and is preferred over the repo
copy; the repo copy stays for dev checkouts and as the drift oracle.
`test_column_mapping_shipped.py` pins the two byte-identical — the backend's `Map Columns` reads the
repo copy, so drift would mean the plugin describes a contract the backend does not implement — and
drives `extraction.canonical_props()` so the behaviour that was lost is what gets tested, not merely
the file's presence. Red-checked: removing the shipped copy fails 3 of the 4.
