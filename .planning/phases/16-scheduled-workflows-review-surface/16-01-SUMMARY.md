---
phase: 16-scheduled-workflows-review-surface
plan: 01
subsystem: infra
tags: [n8n, hubspot, zoominfo, oauth2, credentials, webhook, python, javascript]

# Dependency graph
requires:
  - phase: 15
    provides: "lv_enrichment_provenance blob model, Approach C (HubSpot derives ICP outputs), companies branch in build_enrichment_local_live()"
  - phase: 15.5
    provides: "tiered candidate adjudication (judge chain) already wired for the companies branch in local-live"
provides:
  - "scripts/deploy_n8n_workflows.py + scripts/provision_n8n_credentials.py — two-key-gated, dry-run-by-default n8n Cloud deploy/credential scripts"
  - "build_enrichment_cloud() companies ICP branch (full port from local-live, Cloud-converted)"
  - "ZoomInfo split-code-node credential architecture (credential-bound Mint HTTP node + secret-free cache/gate/enrich Code nodes)"
  - "CONFIG_FLAG_DEFAULTS / SECRET_ENV_NAMES single-source parity infra for the 6 research/judge flags and 6 provider secrets"
  - "WRITE_SAFETY_DEFAULTS Cloud-only write gate (ALLOW_HUBSPOT_RECORD_WRITES default false)"
  - "Cloud webhook auth (native Header Auth) + HubSpot event parser + object-type router"
  - "lv_enrichment_requested / lv_enrichment_status HubSpot control properties (SJ-3 prerequisite)"
affects: ["16-02", "scheduled-workflows", "review-surface"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Split-code-node credential architecture: a credential-bound HTTP node is the ONLY place a secret is read; all cache/business-logic Code nodes are secret-free and consume only the derived short-lived token."
    - "Cloud-aware JS-body generator functions (cloud: bool parameter) as the single source both the docker-replica and Cloud builders read for build-time config flags — replaces bare string constants with functions."
    - "Native n8n Webhook Header Auth for a shared-secret gate, in place of a Code node comparing a header against an inlined constant."

key-files:
  created:
    - scripts/deploy_n8n_workflows.py
    - scripts/provision_n8n_credentials.py
    - tests/test_deploy_n8n_workflows.py
    - tests/test_cloud_companies_branch.py
    - tests/test_cloud_write_path.py
    - tests/test_builder_flag_parity.py
  modified:
    - scripts/build_cloud_workflows.py
    - config/hubspot_properties.yaml
    - tests/test_hubspot_properties_config.py
    - tests/test_architecture_guard.py
    - tests/test_judge_spec.py
    - n8n/wf_enrichment_cloud.json
    - n8n/wf_enrichment_local_live.json
    - n8n/wf_enrichment_local.json

key-decisions:
  - "ZoomInfo credential architecture (Task 2 checkpoint): split-code-node — credential-bound Mint HTTP node (generic Basic Auth) + secret-free Token Gate/Cache Token/Enrich Code nodes. Known-working shape, offline-verifiable, preserves the proven cache/401-invalidate behavior in zoominfoToken.js."
  - "Webhook shared-secret gate uses n8n's NATIVE Header Auth on the Webhook Trigger node (credential-bound), not a custom 'Verify Secret' Code node — avoids a Code node ever reading the secret value and avoids a $env/$vars expression that would trip the zero-env-var guard."
  - "test_builder_flag_parity.py creation deferred from Task 4's commit to Task 5's (documented Rule 3 deviation) — the test requires both builders to actually reference the 6 flags in their built output, which only becomes true once Task 5 wires the companies branch into Cloud."
  - "WRITE_SAFETY_DEFAULTS is a separate constant from CONFIG_FLAG_DEFAULTS (never enters the parity set) since LOCAL/LOCAL-LIVE never write a HubSpot record."

patterns-established:
  - "Flag/secret single-source: CONFIG_FLAG_DEFAULTS + SECRET_ENV_NAMES are the ONE place both enrichment builders read; _flag_const(name, cloud) and _env_secret_expr(name) are the only call sites, both asserting membership in the shared constant, making a flag/secret added to one builder but not the other structurally caught by tests/test_builder_flag_parity.py."
  - "Fail-closed lookup: Adapt Search/Adapt Company Search tag lookup_failed=true on any non-200/errored/malformed HubSpot search response; the Gate wrapper (not the frozen enrichmentGate.js) overrides action create->skip whenever that flag is set."

requirements-completed:
  - "Criterion 5 (env->credentials + build-time constants + parity)"
  - "Criterion 6 (credential-provisioning script)"
  - "Criterion 7 (deploy script)"
  - "Criterion 8 (companies-branch port)"
  - "Criterion 1 enabler (SJ-3 control properties prerequisite)"

coverage:
  - id: D1
    description: "deploy_n8n_workflows.py / provision_n8n_credentials.py — two-key-gated deploy + credential provisioning, credential-id binding, wrong-instance guard (no fail-open)"
    requirement: "Criterion 6, Criterion 7"
    verification:
      - kind: unit
        ref: "tests/test_deploy_n8n_workflows.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "ZoomInfo split-code-node credential architecture (contacts + companies), CONFIG_FLAG_DEFAULTS/SECRET_ENV_NAMES parity infra, zero $env/$vars in built Cloud workflow"
    requirement: "Criterion 5"
    verification:
      - kind: unit
        ref: "tests/test_architecture_guard.py::test_no_env_or_vars_in_cloud_workflows"
        status: pass
      - kind: unit
        ref: "tests/test_builder_flag_parity.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "Companies ICP branch ported into build_enrichment_cloud() — BFS-reachable, no fixture emitter, Approach C clean, review-loop producer contract"
    requirement: "Criterion 8"
    verification:
      - kind: unit
        ref: "tests/test_cloud_companies_branch.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "Cloud webhook write-path hardening — native header auth, event parser, fail-closed lookup, write-safety gate"
    verification:
      - kind: unit
        ref: "tests/test_cloud_write_path.py"
        status: pass
    human_judgment: false
  - id: D5
    description: "lv_enrichment_requested / lv_enrichment_status HubSpot control properties on both objects (SJ-3 prerequisite)"
    requirement: "Criterion 1 enabler"
    verification:
      - kind: unit
        ref: "tests/test_hubspot_properties_config.py"
        status: pass
    human_judgment: false
  - id: D6
    description: "Live n8n Cloud deploy/provisioning and live HubSpot property creation (operator runbook)"
    verification: []
    human_judgment: true
    rationale: "Requires a live n8n Cloud instance, live credentials, and live HubSpot writes — deliberately out of this plan's automated scope (two-key gate never fires offline). Operator runbook only."

duration: ~110min
completed: 2026-07-23
status: complete
---

# Phase 16 Plan 01: Deployable Cloud Enrichment Pipeline Summary

**n8n Cloud enrichment workflow with the companies ICP branch ported, ZoomInfo converted to a credential-bound split-code-node, 6 config flags baked as build-time constants, and the webhook write path authenticated + fail-closed + write-safety-gated — all proven offline (261 pytest / 123 node, zero regressions).**

## Performance

- **Duration:** ~110 min (continuation from checkpoint; Task 1 tracer completed in a prior session)
- **Tasks:** 4 (Tasks 3, 4, 5, 6 — Task 1 tracer + Task 2 decision already resolved before this continuation)
- **Files modified:** 14 (8 scripts/config, 6 tests) + 3 built workflow JSONs regenerated

## Accomplishments

- Added the two SJ-3 control HubSpot properties (`lv_enrichment_requested`, `lv_enrichment_status`) to both companies and contacts manifests.
- Resolved the Task 2 ZoomInfo credential-architecture checkpoint (split-code-node) and implemented it for both the contacts and companies branches — a credential-bound "Mint" HTTP node is the only node that ever touches ZoomInfo client_id/client_secret; three secret-free Code nodes handle caching, gating, and the enrich call.
- Built `CONFIG_FLAG_DEFAULTS`/`SECRET_ENV_NAMES` as the single source both `build_enrichment_local_live()` and `build_enrichment_cloud()` read for the 6 research/judge config flags and 6 provider secrets, converting 4 shared JS-body constants into cloud-aware functions.
- Ported the full companies ICP branch (identity, HubSpot search, providers, web research, judge chain, merge, decide) into `build_enrichment_cloud()` as a sibling of the contacts branch, with a new `ENRICH_DECIDE_CO_CLOUD` review-loop producer node.
- Hardened the Cloud webhook write path: native Header Auth on the Webhook Trigger, a HubSpot event parser + object-type router, real HubSpot Search filters with `hs_object_id` preservation, fail-closed lookup-failure handling, and a `WRITE_SAFETY_DEFAULTS` gate that keeps an activated-but-not-enabled workflow at zero record writes.

## Task Commits

Each task was committed atomically (Task 1 and Task 2 predate this continuation agent):

1. **Task 1: End-to-end deploy + credential-provisioning slice (tracer)** — `34e6dcf` (feat, prior session)
2. **Task 2: ZoomInfo credential architecture decision** — resolved by operator, no commit (checkpoint:decision)
3. **Task 3: Add SJ-3 control properties** — `d87b8bb` (feat)
4. **Task 4: ZoomInfo split-code-node + 6-flag build-time constants** — `a444fc7` (feat)
5. **Task 5: Port companies ICP branch into build_enrichment_cloud()** — `a8c4d5a` (feat)
6. **Task 6: Harden Cloud webhook write path** — `601c787` (feat)

## Files Created/Modified

- `scripts/deploy_n8n_workflows.py` — added `NODE_CREDENTIAL_MAP` entries for the two ZoomInfo Mint nodes and the Webhook Trigger's header-auth credential
- `scripts/provision_n8n_credentials.py` — filled `ZOOMINFO_CREDENTIAL_TYPE` (`httpBasicAuth`), added a 7th credential manifest entry for the webhook shared secret
- `scripts/build_cloud_workflows.py` — the bulk of the phase's work: `CONFIG_FLAG_DEFAULTS`/`SECRET_ENV_NAMES`/`WRITE_SAFETY_DEFAULTS`, ZoomInfo split-node subgraph builders, the companies-branch port, webhook auth + event parser + router, fail-closed Adapt/Gate wrappers
- `config/hubspot_properties.yaml` — `lv_enrichment_requested` + `lv_enrichment_status` on both object groups
- `tests/test_deploy_n8n_workflows.py`, `tests/test_hubspot_properties_config.py`, `tests/test_architecture_guard.py`, `tests/test_judge_spec.py` — extended for the above
- `tests/test_cloud_companies_branch.py`, `tests/test_cloud_write_path.py`, `tests/test_builder_flag_parity.py` — new, 44 tests total
- `n8n/wf_enrichment_cloud.json`, `n8n/wf_enrichment_local_live.json`, `n8n/wf_enrichment_local.json` — regenerated build artifacts

## Decisions Made

- **ZoomInfo split-code-node** (Task 2, operator-resolved before this continuation): credential-bound Mint HTTP node + secret-free cache/gate/enrich Code nodes, applied to both branches.
- **Native webhook Header Auth instead of a Code node** for the shared-secret gate (see Deviations below) — a cleaner mechanism that achieves CLAUDE.md §18.1's property without conflicting with the zero-env-var guard.
- **WRITE_SAFETY_DEFAULTS kept separate from CONFIG_FLAG_DEFAULTS** — it's Cloud-write-only; including it in the parity set would be meaningless (LOCAL/LOCAL-LIVE never write HubSpot) and would break `test_builder_flag_parity.py`'s exact-6 assertion.
- **No early skip switch on the companies branch** (unlike contacts) — mirrors `build_enrichment_local_live()`'s actual behavior of running providers unconditionally for every company row; a "skip" action falls through the post-merge IF chain to end.

## Deviations from Plan

### Auto-fixed / Judgment-call Issues

**1. [Rule 3 - Blocking] `tests/test_builder_flag_parity.py` deferred from Task 4's commit to Task 5's**
- **Found during:** Task 4
- **Issue:** The plan assigns this test file to Task 4, whose own `<verify>` step runs it. But the test needs to inspect BOTH builders' actual output for all 6 flags — `build_enrichment_cloud()` only gains flag-consuming nodes once Task 5 ports the companies branch. Writing the file in Task 4 would fail Task 4's own verify step against a structural impossibility.
- **Fix:** Task 4 built the complete parity infrastructure (`CONFIG_FLAG_DEFAULTS`/`SECRET_ENV_NAMES`, the 4 cloud-aware helper functions) and verified it via the architecture guard test; Task 5's commit created `tests/test_builder_flag_parity.py`, once it was actually meaningful (Cloud references all 6 flags/6 secrets after the companies-branch port).
- **Files modified:** `tests/test_builder_flag_parity.py` (created in Task 5's commit `a8c4d5a`)
- **Verification:** `tests/test_builder_flag_parity.py -q` passes (6 tests); no functional behavior differs from what the plan specified — only the commit boundary moved.
- **Committed in:** `a8c4d5a` (Task 5 commit)

**2. [Rule 4-adjacent, no user ask needed — equivalent-or-better mechanism] Native webhook Header Auth instead of a "Verify Secret" Code node**
- **Found during:** Task 6
- **Issue:** The plan's literal text asks for a Code node that "checks the X-Enrichment-Secret header against a build-time constant name." Implementing that literally requires the Code node to read the secret VALUE from somewhere — the only mechanisms available to a Code node are `$env`/`$vars`, both of which the plan's own Criterion 5 guard (`test_no_env_or_vars_in_cloud_workflows`, word-boundary regex over the WHOLE built workflow) forbids anywhere in the built JSON, or a build-time baked literal (which would commit the secret VALUE to source, explicitly prohibited: "no secret value... is inlined into any committed workflow JSON").
- **Fix:** Used n8n's native Webhook Trigger authentication (`authentication: "headerAuth"`, credential-bound to a new "LV Enrichment Webhook" `httpHeaderAuth` credential). n8n rejects an unauthenticated request before any node executes — same security property CLAUDE.md §18.1 requires, achieved via the credential store (never a Code node, never $env/$vars, never inlined). Added the credential to `provision_n8n_credentials.py`'s manifest and `deploy_n8n_workflows.py`'s `NODE_CREDENTIAL_MAP`.
- **Files modified:** `scripts/build_cloud_workflows.py`, `scripts/provision_n8n_credentials.py`, `scripts/deploy_n8n_workflows.py`
- **Verification:** `tests/test_cloud_write_path.py::test_webhook_trigger_uses_native_header_auth` passes; `test_no_env_or_vars_in_cloud_workflows` still passes with zero matches.
- **Committed in:** `601c787` (Task 6 commit)

**3. [Rule 3 - Blocking] MINIMUM-scope event-consumption shim documented, not fully restructured**
- **Found during:** Task 6
- **Issue:** The plan's full-scope description for webhook hardening says Build Identity/Build Company Identity should "fetch the real record by id rather than trusting direct body fields" — a larger restructure (an additional HubSpot GET-by-id fetch node per branch) than Task 6's stated budget, which explicitly permits a documented minimum: "the Verify-Secret node exists and gates the graph, and the event parser exists and feeds the object-type router... document any remaining direct-field shim as a follow-up."
- **Fix:** Implemented exactly the permitted minimum — Webhook auth (native, see deviation 2), `Parse HubSpot Event` (normalizes the event array, spreads the raw event through for the direct-field shim's benefit), and `Route By Object Type`. Build Identity/Build Company Identity continue reading direct body fields (`row.email`, `row.domain`, etc.) — documented inline in `ENRICH_PARSE_EVENT_CLOUD`'s comment as a follow-up, not performed here.
- **Files modified:** `scripts/build_cloud_workflows.py`
- **Verification:** `tests/test_cloud_write_path.py::test_parse_hubspot_event_node_exists_upstream_of_build_identity` and `test_object_type_router_sends_companies_events_to_the_company_branch` pass.
- **Committed in:** `601c787` (Task 6 commit)

---

**Total deviations:** 3 (1 commit-boundary reordering, 1 mechanism substitution, 1 explicitly plan-permitted scope minimum)
**Impact on plan:** None of the three change the final proven state — all four verification blocks (Criterion 5 parity, companies branch, write-path hardening, SJ-3 properties) pass exactly as the plan's acceptance criteria specify. Deviation 2 is arguably a security improvement (a native n8n mechanism has fewer places for the secret to leak than a hand-written Code node comparison).

## Known Stubs / Limitations (documented, not blocking)

- **`.env.example` not updated with the Cloud-only write-safety knobs.** The environment restricted read/write access to `.env.example` in this session (a project-level file-access policy, not a code issue). `WRITE_SAFETY_DEFAULTS`'s env-var-shaped names (`ALLOW_HUBSPOT_RECORD_WRITES`, `ALLOW_HUBSPOT_CREATE`, `TEST_RECORD_DOMAINS`, `TEST_RECORD_IDS`) are documented in code comments and the workflow's sticky note but not mirrored to `.env.example`. Not a functional gap — these are Cloud-only BUILD-TIME constants (`scripts/build_cloud_workflows.py::WRITE_SAFETY_DEFAULTS`), not runtime env vars an operator sets; the values are edited directly in that dict and the workflow rebuilt. A future session with `.env.example` access should still add a documentation comment there for operator discoverability.
- **The direct-field shim** on Build Identity/Build Company Identity (deviation 3 above) means a genuine HubSpot webhook event (which carries only `objectId`/`objectType`/`subscriptionType`, never `email`/`domain`) will not yet resolve an identity end-to-end without a follow-up fetch-by-id node. This is explicitly scoped out of Task 6's budget by the plan itself and does not block this plan's own acceptance criteria (all of which are structural/offline).

## Issues Encountered

- **Self-inflicted false-positive on the zero-env-var guard:** the Cloud sticky note's own prose initially quoted the literal strings `` $env `` / `` $vars `` as documentation, which `test_no_env_or_vars_in_cloud_workflows`'s word-boundary regex correctly flagged (the regex has no way to distinguish code from prose in a JSON string). Reworded the note to describe the same fact without the literal token sequences. No code change was needed — a documentation wording fix.

## User Setup Required

None required to pass this plan's automated verification. For the LIVE operator runbook (out of this plan's automated scope):
1. Run the ZoomInfo OAuth2 spike / confirm the split-code-node path on a scratch Cloud workflow (Task 2 — already resolved as split-code-node, no spike needed for the fallback path).
2. `python scripts/provision_n8n_credentials.py` with `N8N_URL`/`N8N_API_KEY` set (creates 6 credential objects: LV HubSpot, LV Lusha, LV Apollo, LV Anthropic, LV ZoomInfo, LV Enrichment Webhook) — writes `.n8n_credential_ids.json` (gitignored).
3. `python scripts/deploy_n8n_workflows.py` with `DRY_RUN=false ALLOW_N8N_DEPLOY=true` to push workflows, binding credentials from the id map.
4. Live-create the two SJ-3 HubSpot properties via `scripts/sync_hubspot_properties.py`.
5. To enable a first live write, set `WRITE_SAFETY_DEFAULTS` in `scripts/build_cloud_workflows.py` (`ALLOW_HUBSPOT_RECORD_WRITES=true`, a `TEST_RECORD_DOMAINS`/`TEST_RECORD_IDS` allowlist) and rebuild before redeploying.

## Next Phase Readiness

- `build_enrichment_cloud()` now has full contacts + companies parity with `build_enrichment_local_live()`, credential-bound throughout, ready for 16-02's schedules and review-surface wiring.
- The review-loop producer (`ENRICH_DECIDE_CO_CLOUD` writing `lv_enrichment_needs_review`/`lv_enrichment_review_candidate_json` on `needs_review`) is the exact seam 16-02 Task 4's `reviewApply` consumes.
- No blockers for 16-02. The direct-field-shim limitation (see above) does not block 16-02's scope (scheduled workflows + review surface, not live webhook event consumption correctness).

---
*Phase: 16-scheduled-workflows-review-surface*
*Completed: 2026-07-23*

## Self-Check: PASSED

All key files verified present on disk; all 5 task commit hashes (34e6dcf, d87b8bb,
a444fc7, a8c4d5a, 601c787) verified present in `git log`. Full offline suite (261 pytest
/ 123 node) green at time of writing; builder rebuild confirmed byte-identical
(`git status --short n8n/` clean after a fresh `python scripts/build_cloud_workflows.py`).
