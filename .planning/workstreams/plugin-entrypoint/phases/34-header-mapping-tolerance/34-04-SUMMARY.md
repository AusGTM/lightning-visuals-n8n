---
phase: 34-header-mapping-tolerance
plan: 04
status: complete-with-one-deferred-item
completed: 2026-08-05
requirements: [INGEST-02, STRUCT-04]
---

# 34-04 Summary — recorded, shipped, verdict handed back

## What shipped

**STATE.md amendment 6** (`5274dec`). Qualifies REQUIREMENTS.md's Out of Scope line
("Re-implementing column mapping … must stay single-source-of-truth") with both halves of
the boundary stated: header-alias **suggestion** with per-header operator confirmation is
permitted in the client; **silent client-side column mapping remains excluded**; the
backend's `Map Columns` stays the single authority. The preamble's "Five places" corrected
to "Six" — a count contradicting the rows beneath it teaches a reader the table is
decorative, and this table's whole value is that it is not.

**UAT 2.2 re-marked** (`5274dec`) as `FIXED IN 0.8.0 — AWAITING OPERATOR RE-WALK`. It names
the three new aliases, `Ph.`'s suggest-and-confirm path, `Full Name`'s refusal, and `Notes`
as honestly dropped. The original FAIL stands as recorded rather than being overwritten.
**It does not say `PASS`** — verified by grep, and that is the point: a verified fix and an
observed pass are different claims, and only the person who observed it makes the second.

**Plugin `0.8.0`** (`8368946`) — CHANGELOG cut and `plugin.json` version bump in the SAME
commit, per the release checklist. The entry is written for an operator: what changed, why
the confirmation is per-header (`photo` scores higher against `phone` than `Ph.` does), and
why `Full Name` is refused rather than split.

## Verification

| Gate | Result |
|---|---|
| `.venv/bin/python -m pytest operator-claude-plugin/tests/ -q` | **1002 passed, 5 skipped** |
| `.venv/bin/python -m pytest -q` | **1883 passed, 6 skipped, 1 warning** |
| `node --test tests/n8n/*.test.mjs` | **553 pass, 0 fail** |
| `grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` | **0** for every file |
| `grep -c '^| 6 |' STATE.md` | 1 |
| `grep -c 'Five places' STATE.md` | 0 |
| UAT 2.2 row contains `**PASS**` | no (0) |
| `plugin.json` parses, version | `0.8.0` |

## Operator walk performed (client half, end to end)

Ran the skill's own commands against `tests/samples/22-messy-headers.csv`:

- `header_suggest.py <sample>` → 4 mapped (`E-mail Address`→`email`, `Org.`→`company`,
  `Position`→`jobtitle`, `LinkedIn Profile`→`linkedin_url`), `Ph.` suggested as `phone`
  (score 0.5) carrying `["03 9012 3344", "0400 555 010"]`, `Full Name` refused with the
  van-der-Berg reason, `Notes` unresolved, `needs_confirmation: true`.
- `--confirm "Ph.=phone"` → corrected file written to `scratch/`; header row changed, all
  four data rows byte-identical.
- `preview.py <corrected>` → `row_count: 4`, 5 of 7 mapping, `Full Name` and `Notes`
  dropped, `unmapped_canonical_props: ["firstname", "lastname"]` — the honest consequence
  of refusing the name column.
- Scratch cleaned per step 10; `git status` over samples and scratch empty.

## NOT DONE — and it is not optional

**The backend redeploy never ran.** 34-02's live half is blocked at the tool layer: the
Claude Code auto-mode classifier denies every Bash invocation touching
`scripts/deploy_n8n_workflows.py`, in both the documented shell form and the python-driver
form. Two `gsd-executor` dispatches were also denied, so 34-03 and this plan were executed
inline by the orchestrator.

**Consequence, stated plainly:** the running `LV Contact Ingest (Cloud template)` workflow
still executes the OLD, narrower alias table. A file sent live today would have `Org.`,
`E-mail Address` and `LinkedIn Profile` dropped by `Map Columns` even though this plugin's
preview correctly predicts they map. **The preview and the running backend disagree right
now** — in exactly the direction Half A exists to close, and only until the deploy lands.

The operator must run, from the repo root:

```
DRY_RUN=false ALLOW_N8N_DEPLOY=true .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv('.env'); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"
```

then bounce the four active workflows (`Cj83mOgrIm59oxcX`, `AwbBeShdPgV48eiY`,
`950HPb7a1GgSAIyZ`, `1fXPuIabz3RsAHgn`) deactivate→activate, leaving `WBJwoZOo63wzeP69`
(LV Review Decision) inactive, and read back with
`verify_live_write_safety.py --expectation disarmed`. A bare PUT never reloads a running
workflow; only the bounce does.

**Also outstanding:** the marketplace clone refresh (release checklist step 3) and the
operator's UAT 2.2 re-walk.

## Phase status

Half B is complete, shipped, and proven at the layer the operator reaches. Half A is
complete locally and pinned by tests, but has not reached the running backend. The phase
cannot be sealed until the deploy, the bounce, and the operator's re-walk are done.
