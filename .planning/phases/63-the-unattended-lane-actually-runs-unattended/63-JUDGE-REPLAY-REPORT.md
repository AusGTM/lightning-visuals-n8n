# 63-B Judge Model Replay — Verdict Report

**Date:** 2026-09-02
**Verdict: DROP.** Two reasons fired together: `material_disagreement` (one of three compared
inputs produced a materially different verdict between the two models) and `insufficient_corpus`
(the confidence_band-only corpus — 3 inputs — is below the fixed minimum of 10). Per D-63-06 this
is a legitimate, planned outcome: **the lever (D-63-05, routing `confidence_band`-only records to
the cheaper model) does not ship.** The phase lands **63-A alone**; `scripts/build_cloud_workflows.py`
and every `n8n/wf_*.json` file are untouched by this plan and stay untouched — 63-04's checkpoint
reads this verdict and does not write the constant change.

## Models compared

Read from `scripts/build_cloud_workflows.py`'s `CONFIG_FLAG_DEFAULTS` (the single source the
deployed workflow itself reads):

| | Model id |
|---|---|
| Model A (production, `ANTHROPIC_JUDGE_MODEL`) | `claude-sonnet-5` |
| Model B (candidate, `ANTHROPIC_JUDGE_MODEL_CHEAP`, fallback since the key does not exist pre-63-04) | `claude-haiku-4-5` |

## Corpus provenance

- **Execution id range scanned:** `11973`–`12069` (91 executions listed via `--limit 250`; the n8n
  Cloud executions API returned only 91 executions total for this window — `[observed live]`. No
  source in this repo documents how long n8n Cloud Starter retains execution DATA, so whether more
  history existed and aged out, or whether 91 is simply everything run, is **unknown** — stated as
  unknown rather than assumed either way.)
- **Executions carrying a judge input:** 5 of 91 scanned (executions `11975`, `11979`, `11980`,
  `11987`, `12062`) — `[observed live]`.
- **Total judge inputs found:** 5.
- **Per-lane split:** companies 5, contacts **0** — `[observed live]`. The contacts lane is the
  branch deployed disarmed on 2026-08-30 (CLAUDE.md §13.0.2) and has never run live; this zero is
  the expected, recorded observation, not evidence of a bug in this harness.
- **confidence_band-only subset (the class this replay is evidence about):** **3**, well below the
  fixed `min_corpus` of 10.

## reasons[] distribution (D-63-07 by-product)

Computed over all 5 judge inputs found, as a side effect of extraction — no standalone measurement
task exists for this, per D-63-07.

**By individual reason:**

| Reason | Count |
|---|---|
| `confidence_band` | 5 |
| `org_type_conflict` | 1 |
| `provider_conflict:country_region` | 1 |

**By reason set (what actually triggered each of the 5 judge calls):**

| Reason set | Count |
|---|---|
| `[confidence_band]` | 3 |
| `[confidence_band, org_type_conflict]` | 1 |
| `[confidence_band, provider_conflict:country_region]` | 1 |

All 5 judge inputs carried `confidence_band` as at least one reason — consistent with the todo's
claim that the inclusive `[75, 85]` band fires on essentially every record with a classification
signal. Only the 3 with `[confidence_band]` alone are in scope for D-63-05's lever.

## Comparison result

3 confidence_band-only inputs compared, both models called for each (2 Anthropic calls × 3 inputs
= 6 calls total):

| Classification | Count |
|---|---|
| `agree` | 0 |
| `immaterial` | 2 |
| `material` | 1 |
| `both_unparseable` | 0 |

### The material disagreement

One input (`11975:0`, companies lane) produced a materially different verdict:

| | `decision` | `chosen_value` |
|---|---|---|
| Model A (`claude-sonnet-5`) | `accept_research` | `governing_body_league` |
| Model B (`claude-haiku-4-5`) | `accept` | `governing_body_league` |

The `chosen_value` agrees; the `decision` field does not (`accept_research` vs `accept`). Per the
materiality rule fixed in `scripts/replay_judge_models.py` before this data was seen, a differing
`decision` is material regardless of whether `chosen_value` also differs — this is exactly the case
the rule anticipated: a model can converge on the same output value while disagreeing about *why*
or *how* it got there, and that distinction is exactly the audit-trail information the escalation
path exists to preserve (CLAUDE.md §6.1's `validation_status` vocabulary distinguishes
`sonnet_validated` from other paths for this reason). Body content is not reproduced here — the
committed verdict artifact and this report both carry only `input_id` / `body_sha256`, never the
request body, company name, or evidence URL (T-63-11).

The other two inputs (`11979:0`, `11987:0`) were classified `immaterial`: both models returned
`decision: needs_review` with `chosen_value: null` (identical core outcome), differing only on
`confidence`/`reason` prose — exactly the class of difference D-63-06's materiality definition
excludes from counting against the lever.

## Cost line

- **Anthropic Messages calls made:** 6 (2 models × 3 confidence_band-only inputs).
- **n8n API calls made:** GET only — one execution list, plus one `GET .../executions/{id}` per
  scanned execution (91) during `--extract`. Zero POST/PUT/PATCH/DELETE.
- **Provider credits spent (ZoomInfo/Apollo/Lusha):** 0.
- **HubSpot writes:** 0.
- **New n8n executions produced:** 0 — every n8n call this harness makes is a read of an execution
  that already happened.
- **Per-call latency:** not captured. `scripts/replay_judge_models.py`'s `_live_call_model` records
  no timing; the plan treats this as optional ("if the harness captured it"), and adding it now
  would mean re-running the (already-committed, tested) live calls for no verdict-relevant benefit.
  No latency datum is claimed in this report.

## Why the phase does not re-run with a relaxed threshold

Per the plan's own prohibition and D-63-06: a DROP is never re-run with a different corpus, a
different `min_corpus`, or a relaxed materiality definition to obtain a SHIP. Both the 10-minimum
threshold and the four-way materiality classification (`agree` / `immaterial` / `material` /
`both_unparseable`) were fixed in `scripts/replay_judge_models.py` before this corpus was extracted
or compared. This report records the DROP as-is.

## What this means for 63-04

63-04's checkpoint reads `63-JUDGE-REPLAY-VERDICT.json` and finds `"verdict": "DROP"`. D-63-06
explicitly permits landing 63-A (the sweep launcher) alone. `scripts/build_cloud_workflows.py`'s
`ANTHROPIC_JUDGE_MODEL` constant is not touched by this plan, and no `n8n/wf_*.json` file is
regenerated or deployed as a result of this plan's work.
