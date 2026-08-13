---
phase: 49-re-score-strategy-reporting
plan: 04
subsystem: n8n
tags: [deploy, n8n-cloud, taxonomy, lv_org_type, research-prompt, live-proof]

# Dependency graph
requires:
  - phase: 49-re-score-strategy-reporting
    provides: "plan 49-03's committed, byte-reproducible n8n/wf_enrichment_cloud.json carrying the org-type-definitions research prompt fix"
provides:
  - "The org-type-definitions research prompt fix is live on LV Enrichment (Cloud template) (950HPb7a1GgSAIyZ), proven from the RUNNING instance's own execution data"
  - ".planning/phases/49-re-score-strategy-reporting/49-DEPLOY-PROOF.md — the deploy record, bounce, running-content proof, and post-deploy disarmed verification"
  - "The folded todo (2026-08-13-n8n-research-prompt-lacks-org-type-definitions) closed with deploy evidence"
affects: ["49-05-re-score-window"]

# Actuals (#2632)
actuals:
  tokens: 6988   # chars/4 over `git diff e26d0ce..4cec530` (49-DEPLOY-PROOF.md + todo closure + WEB-RESEARCH-SPEC.md amendment)
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Live-code-execution proof over structural-substring proof: rather than grepping a deployed node's jsCode for a constant name (which can sit inert in an inlined-but-unused shared module), extract the node's jsCode from a live execution's own workflowData.nodes and run it via new Function — the same harness the offline regression test uses — then assert on the function's ACTUAL RETURNED value. Proves the running behavior changed, not just that inert text is present."

key-files:
  created:
    - .planning/phases/49-re-score-strategy-reporting/49-DEPLOY-PROOF.md
  modified:
    - .planning/todos/completed/2026-08-13-n8n-research-prompt-lacks-org-type-definitions.md
    - docs/WEB-RESEARCH-SPEC.md

key-decisions:
  - "Used the same disarmed recompute-lane POST (scripts.remediate_veto_companies.post_webhook_event with recompute=True) that Phase 48 used for its own D-04 gate proof, against the same known-safe test company (17317850381, Jam TV). This lane bypasses providers/research/judge by design and costs 0 Anthropic calls, 0 provider credits, 0 HubSpot writes, 1 n8n execution — the cheapest available way to obtain a fresh execution whose embedded workflowData.nodes carries the running instance's actual node definitions, regardless of which branch the recompute lane itself traverses."
  - "Went beyond the plan's minimum bar (structural jsCode substring presence) and additionally executed the live-extracted jsCode via new Function, asserting on the node's actual RETURNED research_request_body.system string — mirroring tests/n8n/orgTypeDefinitionsPrompt.test.mjs's own stricter idiom and directly addressing 49-03-SUMMARY.md's caution that the shared taxonomy module is inlined into this node's jsCode regardless of whether researchSystemPrompt() consumes it."
  - "Added a small, in-scope docs/WEB-RESEARCH-SPEC.md amendment (not in the plan's declared files_modified) recording that the fix is now deployed, correcting the prior 49-03 dated entry's now-stale 'not yet deployed' claim. Treated as Rule 2 (correctness of an existing doc this plan's own action falsified), not scope creep — no new file created, no test changed."

patterns-established: []

requirements-completed: [RESCORE-01]

# Coverage metadata
coverage:
  - id: D1
    description: "Exactly one n8n deploy and one bounce spent this phase, matching D-05's declaration, with a full audit trail (invocation, response, exit code) recorded"
    requirement: "RESCORE-01"
    verification:
      - kind: other
        ref: ".planning/phases/49-re-score-strategy-reporting/49-DEPLOY-PROOF.md §3 (deploy: DRY_RUN=false ALLOW_N8N_DEPLOY=true, one invocation, 5x 200) and §4 (bounce: off->verified, on->verified)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The RUNNING n8n instance (not the stored workflow body) is proven to carry the org-type definitions — via a live execution's own embedded node list AND the node's actual returned prompt string"
    requirement: "RESCORE-01"
    verification:
      - kind: other
        ref: "execution 11871's workflowData.nodes (structural: jsCode 6928->9392 chars, const ORG_TYPE_DEFINITIONS present) plus the same jsCode executed via new Function, returning a research_request_body.system string containing all nine org-type keys+definitions, QRIC, Racing NSW, and the unweakened enum — 49-DEPLOY-PROOF.md §5"
        status: pass
    human_judgment: false
  - id: D3
    description: "After the deploy, no arming surface is left open: the record-write allowlist is re-read independently and observed empty, and no arming variable survives into a fresh shell"
    requirement: "RESCORE-01"
    verification:
      - kind: other
        ref: "scripts/verify_live_write_safety.py disarmed PASS (14 declaring nodes, TEST_RECORD_IDS/TEST_RECORD_DOMAINS empty everywhere) plus a fresh-shell dry-run invocation showing DRY_RUN/ALLOW_N8N_DEPLOY at their .env-declared disarmed defaults — 49-DEPLOY-PROOF.md §8"
        status: pass
    human_judgment: false
  - id: D4
    description: "The folded todo is closed with deploy evidence, not an assertion"
    requirement: "RESCORE-01"
    verification:
      - kind: other
        ref: ".planning/todos/completed/2026-08-13-n8n-research-prompt-lacks-org-type-definitions.md's dated RESOLVED block naming plan 49-03, plan 49-04, execution 11871, and tests/n8n/orgTypeDefinitionsPrompt.test.mjs"
        status: pass
    human_judgment: false

# Metrics
duration: 8min
completed: 2026-08-13
status: complete
---

# Phase 49 Plan 04: Deploy, bounce, and prove — org-type definitions live Summary

**Spent Phase 49's one declared n8n deploy and bounce to put plan 49-03's research-prompt org-type-definitions fix on the running `LV Enrichment (Cloud template)` instance, then proved it live by executing the deployed node's own code (not just grepping it) and reading its actual returned prompt string — closing the folded Racing-NSW-misclassification todo with evidence.**

## Performance

- **Duration:** 8 min
- **Tasks:** 3/3 completed (checkpoint authorised by the operator mid-session as `deploy-now`, then executed to completion)
- **Files modified:** 1 created (`49-DEPLOY-PROOF.md`), 2 modified

## Accomplishments

- **Deploy.** `DRY_RUN=false ALLOW_N8N_DEPLOY=true` set together in one invocation of `scripts/deploy_n8n_workflows.py`; all 5 Cloud-target workflows updated 200 (`LV Backend Status`, `LV Contact Ingest`, `LV Enrichment`, `LV Review Decision`, `LV Scheduled Maintenance` — all sharing the `ENRICH_CO_GATE` node, the known diff-noise shape). Exactly one PUT-issuing attempt was made; no credential-skip occurred.
- **Bounce.** Deactivated then reactivated `LV Enrichment (Cloud template)` (`950HPb7a1GgSAIyZ`); both legs independently re-read and verified (`off -> verified | observed: False`, `on -> verified | observed: True`).
- **Proof.** One disarmed recompute-lane POST (`remediate_veto_companies.post_webhook_event`, 0 Anthropic, 0 provider credits, 0 HubSpot writes) located execution `11871`. Its own embedded `workflowData.nodes` — the running instance's own graph snapshot, never a `GET /workflows/{id}` read — showed `Build Research Request`'s `jsCode` grown from 6928 to 9392 chars, carrying `const ORG_TYPE_DEFINITIONS` and all nine org-type keys. Node count unchanged at 111 (a `jsCode` content change, not a topology change).
- **Stronger-than-required proof.** Executed the live-extracted jsCode via `new Function` (the exact harness `tests/n8n/orgTypeDefinitionsPrompt.test.mjs` uses) and inspected the node's actual RETURNED `research_request_body.system` string — it carries every org type's key and definition, including the QRIC (`regulator`) and Racing NSW (`governing_body_league`) anchor examples from Phase 48-07, with the strict nine-key `allowed_org_types` enum unweakened. This directly answers 49-03-SUMMARY.md's own caution that a raw-jsCode substring check would pass even on an inert, unused inlined module.
- **Post-deploy verification.** `scripts/verify_live_write_safety.py`'s disarmed pass returned PASS (5 workflows, 14 declaring nodes, every `ALLOW_HUBSPOT_*_WRITES` flag `'false'`, `TEST_RECORD_IDS`/`TEST_RECORD_DOMAINS` empty everywhere) from a fresh GET, independent of the deploy's own PUT response. A fresh-shell invocation of the deploy script's dry path confirmed `DRY_RUN`/`ALLOW_N8N_DEPLOY` read their `.env`-declared disarmed defaults — no arming variable survived the window.
- **Todo closed.** `.planning/todos/pending/2026-08-13-n8n-research-prompt-lacks-org-type-definitions.md` moved to `completed/` with a dated `RESOLVED — Phase 49, plans 03-04` block naming both plans, execution `11871`, and the regression test. `docs/WEB-RESEARCH-SPEC.md`'s TX-10 dated amendment updated to record the deploy (superseding 49-03's "not yet deployed" note).
- Full regression: `node --test tests/n8n/*.test.mjs` -> 676/676 green (before and after the deploy — deploying never rewrites the committed build artifact). `.venv/bin/python -m pytest -q` -> 2705 passed, 128 skipped, 0 failed.

## Task Commits

1. **Task 49-04-01: Authorise the one declared deploy and bounce** — checkpoint (`checkpoint:decision`); operator selected `deploy-now`, recorded above and in `49-DEPLOY-PROOF.md`'s header. No commit of its own — an authorisation act, not a file change.
2. **Task 49-04-02: Deploy, bounce, and prove the running instance carries the definitions** — `a26d5ca` — `feat(49-04): deploy org-type-definitions prompt fix, bounce, and prove it live`
3. **Task 49-04-03: Verify nothing is left armed, and close the folded todo** — `16879da` (rename only, content unstaged — see Deviations) + `4cec530` — `docs(49-04): land the RESOLVED closure block and WEB-RESEARCH-SPEC deploy note` (the actual content of both changes)

**Plan metadata:** committed together with this SUMMARY (see final commit below).

## Files Created/Modified

- `.planning/phases/49-re-score-strategy-reporting/49-DEPLOY-PROOF.md` — new; the full deploy/bounce/proof/disarm record
- `.planning/todos/completed/2026-08-13-n8n-research-prompt-lacks-org-type-definitions.md` — moved from `pending/`, dated RESOLVED block appended
- `docs/WEB-RESEARCH-SPEC.md` — TX-10 amendment updated to record the deploy

## Decisions Made

1. **Reused Phase 48's proof company and lane.** Company `17317850381` (Jam TV) and the disarmed recompute-lane POST are the same mechanism Phase 48's own D-04 gate proof used — a known-cheap, known-safe way to obtain a fresh execution against the deployed workflow without spending Anthropic budget or touching a HubSpot write.
2. **Went beyond structural proof to behavioral proof.** Rather than stopping at "the jsCode text contains `ORG_TYPE_DEFINITIONS`" (which 49-03-SUMMARY.md flags as potentially toothless — the shared module is inlined into this node regardless of whether the function under test consumes it), the live-extracted jsCode was executed and its actual return value inspected. This is strictly stronger evidence and directly forecloses the exact false-positive class the prior plan warned about.
3. **Small doc-accuracy fix outside the plan's declared file list.** `docs/WEB-RESEARCH-SPEC.md` carried a dated 49-03 entry stating "This plan did not deploy or bounce anything ... not yet deployed" — this plan's own action made that sentence false the moment the deploy succeeded. Amended it in place under a new dated entry rather than leaving a stale claim in a project-standard spec doc.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 — staging bug, own error] Task 3's first commit (`16879da`) captured only the pending->completed rename, not either file's content**
- **Found during:** Task 49-04-03, immediately after the commit — `git status --short` still showed both target files as modified in the worktree.
- **Issue:** `git add path-A path-B path-C` was run with one already-renamed pathspec (`.planning/todos/pending/...`, since `git mv` had already moved it); git's pathspec validation aborted the ENTIRE `git add` invocation before staging any of the three paths, printing `fatal: pathspec ... did not match any files`. The rename itself stayed staged from the earlier `git mv`, but the content edits made afterward (the RESOLVED block, the WEB-RESEARCH-SPEC.md amendment) were never staged. The subsequent `git commit -F <message>` therefore committed only the zero-diff rename.
- **Fix:** Ran `git add` again against only the two genuinely-modified paths (no already-renamed pathspec in the same invocation) and committed the actual content in a follow-up commit (`4cec530`), with a commit message explaining the split.
- **Files modified:** `.planning/todos/completed/2026-08-13-n8n-research-prompt-lacks-org-type-definitions.md`, `docs/WEB-RESEARCH-SPEC.md`
- **Verification:** `git diff --stat e26d0ce..4cec530` shows both files' content changes present; `node --test tests/n8n/*.test.mjs` green after the fixup commit.
- **Committed in:** `4cec530`

---

**Total deviations:** 1 auto-fixed (Rule 1 — a `git add` staging error caught and corrected before this SUMMARY was written, not a defect in the deploy/proof work itself)
**Impact on plan:** None on the deploy, bounce, or proof — those landed correctly in `a26d5ca` on the first attempt. The staging slip affected only the todo-closure and docs-amendment commit, and is fully corrected with an honest paper trail (two commits instead of one, explained).

## Issues Encountered

The `git add` staging slip above (self-caught and corrected). No auth gates, no blocking issues, no architectural questions, no unplanned n8n executions beyond the one declared proof execution.

## Budget / Window Accounting

- **Deploys:** 1 (declared, spent) — `a26d5ca` / `49-DEPLOY-PROOF.md` §3.
- **Bounces:** 1 (declared, spent) — `49-DEPLOY-PROOF.md` §4.
- **n8n executions:** 1 (`11871`) against the 2,500/month allowance (~0.04%).
- **Anthropic calls:** 0.
- **Provider credits:** 0.
- **HubSpot record writes:** 0 (`write_blocked` — no allowlist armed).
- **No excess deploys or bounces occurred.** Nothing to disclose beyond this record.

## User Setup Required

None. The operator's only required action — authorising Task 49-04-01's checkpoint — was already given (`deploy-now`) before this continuation began.

## Next Phase Readiness

Plan 49-05 (the 66-record re-score window, per `49-CONTEXT.md` D-05/D-08) can proceed. This plan's deploy did not touch any HubSpot record and armed no HubSpot-write surface, so plan 49-05 starts from a clean, fully disarmed backend. The folded todo this phase existed to close is closed; `docs/WEB-RESEARCH-SPEC.md` and the completed-todos directory both carry the evidence trail.

---
*Phase: 49-re-score-strategy-reporting*
*Completed: 2026-08-13*

## Self-Check: PASSED

All 3 files listed under Files Created/Modified confirmed present on disk. All 3 task commit hashes (`a26d5ca`, `16879da`, `4cec530`) confirmed present in `git log --oneline --all`.
