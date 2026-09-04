# Phase 64: The ladder stops at the best page, not the first - Discussion Log

**Date:** 2026-09-05
**Mode:** default (interactive)

Human reference only. Downstream agents read `64-CONTEXT.md`, not this file.

## Pre-discussion blocker

`init.phase-op 64` returned `phase_found: false`. Root `ROADMAP.md` carried Phase 64 only as a
checklist bullet; the parser requires a `### Phase 64: Name` detail block, and the v1.2
milestone switch that `milestones/v1.2-ROADMAP.md` named as "the one remaining step" after
v1.1 closed had never run. Resolved before discussion started (commit `1acc6a0`): the six v1.2
phase blocks were promoted into root `ROADMAP.md` with colon headings, `REQUIREMENTS.md` was
installed from the milestone copy, and STATE.md frontmatter moved to v1.2 / Phase 64.
`state.milestone-switch` was deliberately NOT used — it rewrites the whole Current Position
body, which would have discarded the retained 62-01/62-02 and Phase 47.5 records.

## Scouting finding that shaped the questions

The "stop at the first page that yields people" rule exists **only as prose** in
`SKILL.md:101`/`:299`. No code decides it — `next_candidates` and `company_budget` bound the
walk, nothing scores a page or merges people across pages. So the phase is necessarily about
moving a decision into a testable predicate, which is what the brief asks for.

## Area 1 — Merge rule

**Question:** a club's `/contact` page names 1 receptionist; `/board/` names 9 committee
members. What ends up in the round?

- Union across walked pages (deduped by name) — **selected**
- Best page replaces
- Best page + carry held names (report-only)

**Selected:** Union. Ten candidates reach the role filter, which decides.

## Area 2 — What "better" means

**Question:** what makes a page better? Has to be a code predicate, not model judgement.

- Most role-filter hits — **selected**
- Most people found
- Role hits, then people count (lexicographic)

**Selected:** role-filter hit count. Note: with union merging chosen in area 1, the score's
job is the stop decision rather than picking a single winning page.

## Area 3 — Stop rule

**Question:** when does the walk stop? `MAX_FOLLOWUP_FETCHES` (5) unchanged either way.

- Walk the whole ladder to cap
- Stop on a "good enough" threshold — **selected**
- Stop when no board-shaped candidate remains

**Selected:** threshold. Follow-up needed because the threshold was a new tunable.

## Area 4 — Walk-end reason

**Question:** Phase 65 routes re-entry on the cause of a round-empty. Should 64 emit why the
walk ended?

- Yes, 64 emits the reason — **selected**
- No, leave it to 65

**Selected:** yes. Boundary recorded explicitly in D-64-08: 64 emits, 65 acts.

## Follow-up 1 — What the bar measures, and what sets it

**Q1: page just fetched, or everything so far?** → cumulative across walked pages. A club
spreading officers over several thin pages reaches the bar without walking the full cap.

**Q2: what sets GOOD_ENOUGH?** → count of chosen role families. Fixed named constant and the
agreed per-company cap were the alternatives.

## Follow-up 2 — The floor (concern raised)

Concern stated: `BAR = len(chosen_families)` means a one-family round stops on its first hit,
reproducing the exact "stop at the first page" defect the phase exists to fix.

- Floor at the agreed per-company cap — **selected**
- Floor at a fixed minimum constant
- No floor, keep it exact

**Selected:** `BAR = max(len(chosen_families), agreed_cap)`.

## Claude's discretion

- Where the walk lives and its exact return shape beyond `ended`.
- How much of `SKILL.md` step 5's prose is replaced versus rewritten.
- Whether per-page scores surface in the round artifact.

## Deferred

- Round-empty re-entry keyed on cause → Phase 65.
- Board-shaped URL heuristics → not chosen as a stop rule; noted for 65's candidate ranking.
- Surfacing per-page scores to the operator → possibly Phase 68's disclosure audit.
