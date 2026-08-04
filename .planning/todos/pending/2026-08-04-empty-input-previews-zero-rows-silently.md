---
created: 2026-08-04T07:10:00.000Z
title: An empty spreadsheet previews as 0 rows with no explanation and nothing stops the send
area: operator-claude-plugin
severity: minor
scheduled: "plugin 0.7.1 — tack-on release AFTER Phase 33 ships as 0.7.0 (operator decision 2026-08-04)"
files:
  - operator-claude-plugin/scripts/preview.py
  - operator-claude-plugin/skills/contact-upload/SKILL.md:79
---

## Problem

Found by the autonomous UAT self-assessment of step 2.6, 2026-08-04. UAT 2.6's criterion is
*"A **clear, actionable** error. Never a silent drop, never zero rows with no explanation."*

Two unreadable-input cases behave differently:

| Input | Result |
|---|---|
| a `.pdf` (photo saved as PDF) | **Clean refusal** — `UnsupportedFileError: Unsupported file extension: .pdf`. Correct. |
| an **empty `.csv`** | `build_preview()` returns `row_count: 0`, `headers: []`, `outgoing_bytes: 0` — **no error, no explanation** |

Nothing above the library fills the gap: `skills/contact-upload/SKILL.md` instructs the model to
state `row_count` (line 79) but has **no zero-row branch** — no instruction to explain, to refuse,
or to skip the approval question. So the documented flow proceeds to "ask for approval" and then
offers the arming phrase for a batch containing nothing.

Observed payload for the empty file:

```json
{"headers": [], "row_count": 0, "outgoing_bytes": 0,
 "cost_block": "… No provider credits: 0 … a real, explainable zero …"}
```

The cost block cheerfully explains that zero cost is "real and explainable", which reads as
reassurance about a file that could not be read.

**Not a data-loss risk** — sending zero rows costs nothing and writes nothing. The defect is that
"your file is empty / has no data rows" and "everything is fine, 0 rows to send" are presented
identically, which is the same silence-means-healthy failure shape as NOTICE-04 and the sweep.

A capable model reading `row_count: 0` would probably say something sensible unprompted — but
nothing *guarantees* it, and UAT records what is guaranteed. That is why this is filed rather
than waved through.

## Solution

**SCHEDULED: plugin 0.7.1, as a tack-on immediately after Phase 33 ships as 0.7.0.** Do NOT apply
this before 0.7.0 is cut and pushed — a fix sitting in the tree when the 0.7.0 version bump lands
ships inside 0.7.0 and makes the 0.7.1 cut meaningless. Order is: Phase 33 executes -> 0.7.0
bump + CHANGELOG cut + push + clone refresh -> THEN this fix -> 0.7.1 bump + cut + push.

Option 1 (skill-only) is the chosen shape unless execution surfaces a reason against it.

Cheapest first:

1. **Skill-only:** add a zero-row branch to `SKILL.md` step 3 — when `row_count` is 0, say the file
   parsed but carried no data rows, name the likely causes (empty file, header row only, wrong
   sheet), and do NOT ask for approval or offer the arming phrase. Mirrors the `can_send: false`
   handling added in 0.6.2. No code change; pin with a two-sided test that the skill body contains
   the branch.
2. **Library too:** have `build_preview()` carry an explicit `empty_reason` (`"no rows"` vs
   `"headers only"`), so the distinction is data rather than inference. Slightly more code, but
   the two cases genuinely differ for the operator: a header-only file is a wrong-export mistake,
   a zero-byte file is a wrong-file mistake.

Option 1 is enough for the UAT criterion. Option 2 is better if header-only files turn out to be
the common real-world case.

Whichever lands, pin it at the layer the operator reaches — the skill body and/or the CLI — not
only at `build_preview()`. Same rule as the 0.6.1/0.6.2 defect family.
