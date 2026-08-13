---
created: 2026-08-13T00:00:00.000Z
title: production n8n research prompt still enumerates lv_org_type with no definitions
area: n8n
severity: major
files:
  - scripts/build_cloud_workflows.py
  - n8n/wf_enrichment_cloud.json
  - n8n/wf_enrichment_local_live.json
discovered_in: phase-48-enrichment-coverage
---

## What happens

Phase 48 Plan 07 fixed the ROOT CAUSE of Racing NSW `15008671672`'s misclassification: both
Python research prompts (`RESEARCH_SYSTEM` and `RACING_NSW_ORG_TYPE_SYSTEM` in
`src/web_research.py`) enumerated the 9 `lv_org_type` enum VALUES and defined none of them, so
the model keyed on whatever the source text emphasised (statutory origin) instead of the
correct discriminator (commercial control of the sport). The fix added a `definition:` key to
every `org_types` entry in `config/taxonomy.yaml` and had both Python prompts render
`src.taxonomy.org_type_definitions_block()` from it.

**The production n8n research prompt was not fixed.** `COMPANIES_TARGET.research_system_prompt_fn_js`
in `scripts/build_cloud_workflows.py` (function `researchSystemPrompt()`, ~line 2039) builds its
`allowed_org_types` line as `"allowed_org_types: " + JSON.stringify(ORG_TYPES) + "."` —
`ORG_TYPES` there is the generated array of bare keys (`gen_taxonomy_js.render()`'s
`ORG_TYPES` constant, `n8n/code/taxonomy.generated.js`), which carries no definitions and
never will unless `gen_taxonomy_js.render()` is taught to emit them too. The live n8n
enrichment lane (and its local-live twin) is therefore still definition-free and can still
reproduce the same statutory-origin misclassification for any future org whose statutory
history reads like QRIC's or Racing NSW's.

## Why it was not fixed here

Three independent blockers, any one of which alone rules out fixing it in Plan 48-07:

1. **The frozen jsCode fixture.** `tests/test_companies_factory_frozen.py` pins the exact
   emitted `jsCode` of `Research Trigger Gate`/`Build Research Request`/etc. against
   `tests/fixtures/companies_jscode_frozen.json`, byte-for-byte, and is re-baselined "ONLY by
   an explicit, reviewed act — never as a routine 'make the test pass' step" (its own header
   comment). Changing `research_system_prompt_fn_js`'s emitted string requires re-baselining
   that fixture.
2. **Deploys are operator-only.** Any change to `COMPANIES_TARGET` requires
   `scripts/build_cloud_workflows.py` to be re-run, `n8n/wf_enrichment_cloud.json` (and
   `wf_enrichment_local_live.json`) regenerated, then `scripts/deploy_n8n_workflows.py` run
   with `DRY_RUN=false` **and** `ALLOW_N8N_DEPLOY=true`, plus a bounce. The Phase 47.5 deploy
   waiver expired with that phase.
3. **D-06 declares exactly one deploy this phase**, and it belongs to plan 48-04, not this one.

## Suggested fix

- Teach `scripts/gen_taxonomy_js.py::render()` to also emit an `ORG_TYPE_DEFINITIONS` object
  (mirroring `src.taxonomy.ORG_TYPE_DEFINITIONS`), so `n8n/code/taxonomy.generated.js` carries
  the same semantic content the Python prompts now render.
- Change `COMPANIES_TARGET.research_system_prompt_fn_js` (and its contacts-target twin, if
  applicable) to build its `allowed_org_types` line from `ORG_TYPE_DEFINITIONS` instead of a
  bare `JSON.stringify(ORG_TYPES)` — the same definitions-not-values pattern the Python side
  now uses.
- Re-baseline `tests/fixtures/companies_jscode_frozen.json` as the explicit, reviewed act its
  own test insists on.
- Rebuild, deploy (operator-armed), bounce, and prove the running instance changed with a live
  execution's own node list (not a stored read-back) per the repo's established proof standard.

## Known divergence until this lands

The Python (`src/web_research.py`) and production n8n research prompts are **knowingly
divergent**: Python renders `org_type_definitions_block()`, the live n8n lane does not. This is
recorded here and in `docs/WEB-RESEARCH-SPEC.md` §2's dated TX-10 amendment rather than
silently left implicit.

## Verification

After the fix: `node --test tests/n8n/*.test.mjs` should include a new assertion that
`Research Trigger Gate`'s (or the relevant node's) emitted `jsCode` contains each org type's
definition text, not just its bare key — mirroring
`tests/test_taxonomy_conformance.py::test_tx10_every_org_type_has_a_definition_and_both_prompts_render_them`
on the Python side.

Full context: `.planning/phases/48-enrichment-coverage/48-07-PLAN.md` Task 2.

---

## RESOLVED — Phase 49, plans 03-04 (2026-08-13)

Fixed exactly the way "Suggested fix" above described, and deployed within the same phase.

**Offline fix (plan 49-03).** `scripts/gen_taxonomy_js.py::render()` now emits an
`ORG_TYPE_DEFINITIONS` const into `n8n/code/taxonomy.generated.js`, generated from
`config/taxonomy.yaml`'s `definition:` key — the same source both Python prompts already
render via `src.taxonomy.org_type_definitions_block()`. `COMPANIES_TARGET.research_system_prompt_fn_js`
(the `Build Research Request` node) now builds its `lv_org_type option definitions:` line
from that const and appends it to the returned system prompt, verified by executing the
node's own committed jsCode (never by grepping it) — the QRIC / Racing NSW anchor examples
are present, and the strict nine-key `allowed_org_types` enum constraint is unchanged.
`tests/fixtures/companies_jscode_frozen.json` was re-baselined as the explicit, reviewed
act its own header comment requires. New regression guard:
`tests/n8n/orgTypeDefinitionsPrompt.test.mjs`, with a negative control proving the
assertion has teeth.

**Deployed and live (plan 49-04).** Phase 49's one declared deploy+bounce (D-05, authorised
under waiver D-49-01 at the plan's checkpoint, operator selected `deploy-now`) put the
built `n8n/wf_enrichment_cloud.json` on the running instance. Deploy: `DRY_RUN=false
ALLOW_N8N_DEPLOY=true`, one invocation, all 5 Cloud workflows updated 200. Bounce:
`LV Enrichment (Cloud template)` (`950HPb7a1GgSAIyZ`) deactivated then reactivated, both
legs independently verified.

**Proven from the RUNNING instance, not a stored read-back.** Execution `11871` (a
disarmed recompute POST, 0 Anthropic calls, 0 provider credits, 0 HubSpot writes) supplied
its own embedded `workflowData.nodes` — `Build Research Request`'s live jsCode grew 6928 →
9392 chars and now carries `const ORG_TYPE_DEFINITIONS` with all nine org-type keys.
Stronger than a structural check: that live jsCode was executed via `new Function` (the
same harness `orgTypeDefinitionsPrompt.test.mjs` uses) and its RETURNED
`research_request_body.system` string was inspected directly — it carries every org
type's key and definition, including the QRIC/regulator and Racing NSW/governing-body
anchor examples, with the enum constraint unweakened. Node count unchanged at 111 (a
jsCode content change, not a topology change). Full detail:
`.planning/phases/49-re-score-strategy-reporting/49-DEPLOY-PROOF.md`.

**Post-deploy verification.** `scripts/verify_live_write_safety.py`'s disarmed pass
returned PASS immediately after the bounce, and an independent fresh-shell invocation of
the deploy script's dry path confirmed no arming variable survived the window.

**Honest limitation, same shape as Phase 48's own D-04 gate closure.** The research
branch's live FIRING with a genuine Anthropic call is not proven this phase — the
recompute lane used for the proof execution bypasses providers/research/judge by design,
and there is no supported way to force a live research call on demand without spending
budget this plan declared zero of. Structural presence plus the executed-node behavioural
proof above is the proof bar this phase meets, matching the offline test's own standard.

Known-divergence note above is now closed: `docs/WEB-RESEARCH-SPEC.md` §2's TX-10
amendment records both the build-time fix (49-03) and the deploy (49-04).
