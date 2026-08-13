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
