# Phase 63 — Discussion Log

**Date:** 2026-09-02
**Mode:** discuss (default), no flags
**Areas selected by operator:** all four offered

> Human reference only — audits and retrospectives. Downstream agents read
> `63-CONTEXT.md`, not this file.

---

## Grounding done before any question was asked

Both todos were re-read in full (each had been re-verified against the tree and the machine on
2026-09-02), and the code they name was read directly rather than trusted from the todo text:

- `escalation.generated.js:9` → `ESCALATION_CONFIDENCE_BAND = [75, 85]`, and `judge.js:147` →
  `conf >= lo && conf <= hi` — **inclusive at both ends, confirmed by reading, not inferred.**
- `build_cloud_workflows.py:1100` → `"ANTHROPIC_JUDGE_MODEL": "claude-sonnet-5"` — establishing
  that lever 2 is a one-constant change, which materially shaped how the options were framed.
- `durable_paths.py` → `_version_key` (44), `_newest_sibling_holding` (84), `_migrate_once` (122).
  The migration semantics here are what surfaced the un-migrated-credential hazard behind D-63-03;
  that hazard was raised to the operator *before* the deletion question, not after.
- `lv-sweep-run.sh` → takes plugin root as `$1` by design; already has `banner()`/`stamp()`.

Decisions carried forward and deliberately **not** re-asked: no terminal instructions to the
operator (v1.0 REQUIREMENTS.md Out of Scope); real-scheduler proof mandatory (memory
`sweep-trigger-llm-free`); reuse `durable_paths` rather than reimplement; 58-06's widening and RO-2
must hold; never hand-edit workflow JSON; nothing armed.

---

## Area 1 — Sweep fix shape

**Q1. What shape should the 63-A sweep fix take?**

| Option | Chosen |
|---|---|
| Both — shim + self-check *(recommended)* | ✅ |
| Shim only | |
| Self-check only | |
| Shim + self-check + auto-repoint | |

Framing given: the todo calls the shim "clearly right," but the self-check is the only mechanism
that reaches the twelve crontabs already installed. Auto-repoint was offered and declined — it
would mean the plugin editing the user's crontab, and a bad rewrite kills the sweep outright.

→ **D-63-01**

**Q2. When the self-check detects staleness, what should it do?**

| Option | Chosen |
|---|---|
| Run, but notify loudly *(recommended)* | ✅ |
| Refuse and exit non-zero | |
| Run; notify only past a drift threshold | |

The real tension surfaced here: Phase 32 established that a trigger which cannot run must be loud,
and "refuse" is the option consistent with that. It was declined because stale ≠ cannot-run, and
refusing converts a degraded-but-working unattended lane into a dead one — the worse failure for
this milestone. The threshold variant was declined as having no evidence to set N.

→ **D-63-02**

---

## Area 2 — The twelve stale directories

**Q3. What to do about the directories and any crontab already pinned to one?**

| Option | Chosen |
|---|---|
| Leave them; signal only *(recommended)* | ✅ |
| Prune, but only provably-migrated dirs | |
| Leave dirs; add a one-time re-point notice | |

The hazard was put on the table before the question: `_newest_sibling_holding()` deletes a
sibling's state copy only after a verified read-back, so an install directory that looks like dead
weight may hold the only copy of an un-migrated credential. The re-point-notice option was flagged
as partially re-opening what Q1 had just decided, and as a terminal instruction to the operator.

→ **D-63-03**

---

## Area 3 — How far to touch the judge

**Q4. Which judge levers are in scope?**

| Option | Chosen |
|---|---|
| Lever 2 only — cheaper model *(recommended)* | ✅ |
| Levers 2 + 3 — model and search cap | |
| All three — including the band | |
| Measure first, decide nothing yet | |

The distinction the options were built around: **lever 2 changes who adjudicates; lever 1 changes
what gets adjudicated.** Only lever 1 is an authorization change, and 58-06 widened this gate on
purpose after an unadjudicated conflict false-vetoed a real AU company (execution `11983`). The
"measure first" option was offered honestly — the todo does recommend it — but noted as landing no
throughput improvement.

Observed and reported after the choice: routing on "`confidence_band` is the only reason" requires
branching on `reasons[]` anyway, so the measurement the todo asks for falls out as a by-product
rather than needing its own spike.

→ **D-63-05**, **D-63-07**

---

## Area 4 — Proof standard

**Q5. How should 63-A be proven, given a real cron tick is mandatory?**

| Option | Chosen |
|---|---|
| Temporary fast schedule, then restore *(recommended)* | ✅ |
| Wait out the real 4-hourly tick | |
| Run under `env -i` as a cron proxy | |

The `env -i` option was included and explicitly marked as the approximation the
`sweep-trigger-llm-free` memory warns about — the original probe passed that way and still failed
under real cron.

→ **D-63-05 (proof method)**

**Q6. What evidence establishes Haiku 4.5 is adequate for `confidence_band`-only adjudication?**

| Option | Chosen |
|---|---|
| Offline replay, both models *(recommended)* | ✅ |
| Ship it; guard with a disagreement trip | |
| Small live sample (5–10 records) | |
| Offline replay, then a small live sample | |

Constraint stated up front: a bulk run already consumes half the Lusha balance, so live sampling
must be small or zero. Offline replay spends Anthropic calls only — zero Lusha credits, zero
HubSpot writes, zero n8n executions. The disagreement-trip option was named as establishing
adequacy by assertion — the same shape as CR-01, which had just cost Phase 62 a full gap-closure
plan.

→ **D-63-06**

---

## Deployment (raised by Claude, not on the original list)

**Q7. Does Phase 63 deploy, given a deploy also carries Phase 62's undeployed changes?**

| Option | Chosen |
|---|---|
| Deploy disarmed, both phases' changes *(recommended)* | ✅ |
| Commit only, deploy never | |
| Deploy 63's judge change only | |

Raised because Phase 63 necessarily regenerates the workflow JSON, and the committed JSON is
already ahead of the live instance by Phase 62's `num_associated_contacts` and `sourceByField`.
The third option was included to be shown as unworkable: `build_cloud_workflows.py` generates the
whole workflow from current source, so isolating 63's change means deploying JSON matching no
commit.

→ **D-63-08**, **D-63-09**

---

## Scope creep

None occurred. The operator selected all four offered areas and answered within each.

## Deferred

Levers 1 and 3, crontab auto-repoint, directory pruning, and re-examining fan-out cost — all
recorded with rationale in `63-CONTEXT.md` `<deferred>`.

## Claude's discretion

Shim filename and install location; the staleness comparison's mechanics; the replay harness shape
and agreement threshold (bounded by D-63-06's drop-the-lever rule).
