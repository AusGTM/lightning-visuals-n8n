### Phase 60: Review-lane authority

**Status: PLANNED 2026-09-01** — 4 plans, 3 waves (`60-01`..`60-04`). Context, research, pattern
map and validation strategy all gathered 2026-09-01 (`60-CONTEXT.md`, `60-DISCUSSION-LOG.md`,
`60-RESEARCH.md`, `60-PATTERNS.md`, `60-VALIDATION.md`). Split out of Phase 59 by operator
decision 2026-08-28 (`59-CONTEXT.md` D-59-03).

**Goal**: Approving or rejecting one flagged HubSpot record costs the operator zero manual admin
round trips. Today it costs two: an admin setting `ALLOW_REVIEW_SUBMIT=true` as a shell env var,
and a separate admin-run deploy that bakes `ALLOW_HUBSPOT_REVIEW_WRITES` plus the record's id
into the deployed `LV Review Decision (Cloud)` workflow — G-2's shape, still live on this one
lane (`54-LIVE-PROOF.md`).

**The decisions this phase implements** (locked in `60-CONTEXT.md`, do not re-litigate):
D-60-01 review becomes grantable, deliberately reversing 30-01's D-02/D-08e separation (option
(b) of the three the roadmap offered) · D-60-02 one grant covers all three lanes (enrichment,
contacts, review) together · D-60-03 the grant's own record-scoping bounds which flagged records
review may approve — the same "narrower than the grant, never wider" rule dispatch follows, and
what keeps D-60-02 from being a blank check · D-60-04 `ALLOW_REVIEW_SUBMIT` is retired, with
grant-authorization taking its place as the gate · D-60-05 `ALLOW_HUBSPOT_REVIEW_WRITES` is wired
into `n8n_arming`'s existing overlay mechanism (already one of its five overlayable flags, never
wired for review), removing the deploy round trip · D-60-06 one arm window covers a batch of
review decisions per session rather than one per decision.

**Not an option** (carried from the checklist entry): deleting `ALLOW_REVIEW_SUBMIT` with no
replacement — that leaves the lane's only authority behind a deploy an operator cannot run.
D-60-04 retires it only because D-60-01 puts grant-authorization behind it first.

**Recorded-edit discipline required**: `write_grant.py:64-82`'s comment block documents why the
review lane is currently excluded from `LANES`. This phase reverses that decision — the comment
is AMENDED with a dated addendum (mirroring the D-59-07 amendment below it in the same file),
never silently deleted.

**Depends on**: Phase 53 (the grant machinery this folds review into), Phase 30 (the review lane
and the separation being reversed)

**Requirements**: none mapped — `milestones/v1.1-REQUIREMENTS.md` carries no review-lane id; this
phase is driven by D-59-03 and `60-CONTEXT.md`'s D-60-01..08. The decision ids are the coverage
contract in place of REQ ids, and each plan's `requirements` frontmatter carries the D-60-NN ids
it implements. The spec-less probe fallback records a SKIP for this phase: no `SPEC.md` and no
requirement ids, so no probe predicates were generated.

**Two additions research made that CONTEXT.md did not name**, both in scope by consequence:
Guardrail A was structurally blind to a stuck-open `ALLOW_HUBSPOT_REVIEW_WRITES` the moment
review became grantable (plan 02), and `n8n/code/reviewDecision.js`'s `not_allowlisted` message
becomes false once a grant can set the allowlist dynamically (plan 04, changed at its source and
regenerated — never a hand-edit of the JSON).

**Plans**: 4 plans

- [ ] 60-01-PLAN.md — TRACER: `"review"` becomes a grantable lane end-to-end (LANES, `REVIEW_FLAGS`,
      `arm_for_review`, `submit_decision`'s grant gate), with the two reversed-design tests rewritten
      under recorded-edit discipline. D-60-01/02/03/04/05/07. Wave 1.
- [ ] 60-02-PLAN.md — Guardrail A learns to see a stuck-open review authorization; `authorize_review_batch`
      and the one-window-per-sitting lifecycle (normal, out-of-scope, crashed, revoked). D-60-06. Wave 2.
- [ ] 60-03-PLAN.md — review writes land in the per-run `written_records-<run_id>.json` artifact, in its
      existing vocabulary, with the bookkeeping structurally unable to stop a write. D-60-08. Wave 2.
- [ ] 60-04-PLAN.md — operator surfaces and release: the corrected backend message (regenerated), the
      review-triage skill on the grant, three-lane grants in the dispatch skills, truthful gate tables,
      CHANGELOG and version `0.35.0`. Wave 3.

**Nothing in these plans arms, deploys, writes to HubSpot or calls a provider.** This phase's own
live proof is a supervised operator walk (`60-VALIDATION.md` § Manual-Only Verifications), not an
executor task — the arming gates are what would be under test.

