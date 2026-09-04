# Phases 65-69 Discussion Log (one sitting)

**Date:** 2026-09-05
**Mode:** default (interactive)

Human reference only. Downstream agents read each phase's own CONTEXT.md.

## Why one sitting, and why this order

The operator asked whether discussion could be batched for all subsequent phases so planning
and execution could run as parallel streams. Answer given: no batch discuss exists
(`<phase>` is a single required argument; `--batch` groups questions INSIDE one phase), so the
workflow was run five times. On parallelism, a file-overlap map was produced first:

| File | Phases |
| --- | --- |
| `skills/suggest-contacts/SKILL.md` | 64, 65, 67, 68, 69 |
| `scripts/suggest_contacts.py` | 64, 65, 69 |
| `scripts/write_grant.py` | 67, 68 |
| `n8n/code/*.js`, `build_cloud_workflows.py`, `config/field_policy.yaml` | **66 only** |

So 66 is the only clean parallel stream. Recorded in each CONTEXT.

Discussion order was **69 → 65 → 66 → 68 → 67**, not numeric, because the operator's first
clarifying question ("if a dead-end is reached, does a batch report let me batch manual
interventions?") turned out to be answerable only by deciding 69's durability question, and
65's dead-end handling depends on that answer.

## 69 — Held rows survive the round

**Operator's question:** does a batch report at end of run allow batch manual interventions?

**Finding presented:** no, today. `round_artifact` writes nothing ("No file is ever
written"); the two durable stores are run-scoped; and `held_queue.save` raises
`HeldQueueError` on exactly the codes a decline produces. The blocker is 69's, not 65's.
`run_manifest.rows_to_resume(..., held_entries=...)` already exists as the hook.

**Decisions:** client-side durable store of its own (not a widened `held_queue`, not
report-only); accumulates across runs with `run_id` per entry; keyed `company_id` +
normalised name key (not `row_id`, which is re-minted per batch); four drain actions —
send / defer / delete / export; delete is removal only, no tombstone; drained inline at end
of round AND via a standalone skill.

**Concern raised and resolved:** `held_queue` is single-run scoped and treats another run's
document as a rejection, so "defer" cannot copy that part — run scope moves from the document
to the entry.

## 65 — Round-empty re-entry, keyed on the cause

**Decisions:** one pure classifier (`round_outcome`) rather than stage-by-stage inference in
prose; one primary cause plus a full breakdown, so routing stays unambiguous while the report
carries the whole truth; unreadable cause fails closed WITHOUT raising, copying D-5sd-06
exactly; the four causes route as no_people_found→search, people_thin→classify only (64
already acted), none_classified→report, all_held_on_email→report + 69's store; at most ONE
cause-selected second pass.

## 66 — Rich enrichment, not minimum enrichment

**Operator's question:** what is meant by "new normalize work"?

**Finding presented:** `apolloCandidates`'s contacts branch already emits 11 of the 12
promotable fields. Only `lv_linkedin_url` has no producer anywhere. So "new normalize work"
is one `_push` per provider plus a small URL normalizer — which collapsed the third option
offered, and it was withdrawn.

**Operator's question:** reasonable phone TTL for a company or senior leader?

**Finding presented:** `stale_after_days` is read only by the `stale_refreshable` branch;
`phone` is `fill_blank_only`, so a TTL there is inert, and activating it means a class change
SAFE-01..05 forbids. Substantively the switchboard number is org-scoped while the field that
actually goes stale for an AU club committee member (annual AGM turnover) is `jobtitle`,
already 180 days.

**Decisions:** flag phone-less rows as partial, do not hold; widen `REQUIRED` to all 12 and
write the `lv_linkedin_url` mapper; no TTL on `phone`, with the reason recorded; both lanes
(contacts and companies) this phase.

## 68 — State the price and keep moving

**Decisions:** the BROAD reading — approval implicit on the no-grant branch too, with consent
and the cap default both treated as statements per the operator's ruling; grant opening
offered inline AND invocable directly; disclosure precedes first spend by a fixed 5–10s pause;
"same behaviour everywhere" (no interactive/headless split in the posture).

**Finding presented before the ceiling question:** `agreed_cap` raises `CapRefused` when no
grant priced an allowance — "never clamps, never defaults" — so a grant-less branch has no
`priced_cap` for a stated cap default to be a default OF. Resolved by having proceeding
implicitly OPEN a grant, which mints the envelope and keeps `CapRefused` meaningful.

**Concern raised:** "same behaviour everywhere" reverses D-61-08, which the v1.2 roadmap binds
to an explicit ask, and in an unattended run the pause protects nothing because nobody is
there to interrupt. Operator reaffirmed. Resolved by scope: 68 states the intent, 67 opens
the gate formally with the tiers and fail-closed conditions; until 67 ships, unattended keeps
today's path.

## 67 — An autonomy flag with sensible defaults

**Operator's question:** what are the risks of a third gate — wouldn't it be easier and more
frictionless?

**Finding presented (four risks, with evidence):** (1) `write_grant.py`'s header records the
three-way split as deliberate and keeps the headless arm gate environment-gated; a settings
key is a file the assistant can write, so unattended write authority would become
session-editable. (2) An env var dies with the shell; a settings key survives reboots, machine
copies, backups and plugin installs. (3) It collapses two blast radii — operator-present and
nobody-present — into one. (4) It cuts against the pinned `DISPATCH_FLAGS`/`REVIEW_FLAGS`
separation. And on the friction itself: the recurring cost was per-round asking, already
removed by 68; the gates are one-time setup, so a third gate buys one shell line, once.

**Operator changed the earlier answer** from "third gate" to **default-setter for all three
tiers** after seeing this.

**Decisions:** three tiers, all autonomous by default; flag is a default-setter, both existing
gates unchanged; tier defaults applied on update (operator chose this over defaulting to
current behaviour, having been shown it is a silent write-posture change for other operators —
so the plan must surface the change in release notes and first-run output); this phase opens
D-61-08 formally, presented as a deliberate reversal; fails closed on `CEILING_UNKNOWN`, an
unread provider balance, and a missing allowance key; end-of-run report mandatory under
autonomy; per-run ceiling accepted as containment for revocation (no chunk-granular revoke).

## Recommended execution order

**66** — independent, parallel stream, any time.
**64 → 65 → 68 → 67** — serial on `SKILL.md`; 68 before 67 so the disclosure prose is not
rewritten twice.
**69** — after 65 (its store carries 65's cause) and before or alongside 68's report rule.
