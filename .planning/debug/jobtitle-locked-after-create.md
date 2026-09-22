---
slug: jobtitle-locked-after-create
status: fixing
trigger: "provider_sourced_fields fix and regression test; then jobtitle lock; Apollo not master key is known - no need to investigate"
created: 2026-09-22
updated: 2026-09-22
---

# Debug session — a jobtitle the pipeline just wrote cannot be corrected through the lane

Found live 2026-09-22 (American Football Australia board, operator UAT). Root cause is
established from code reading; awaiting the operator's ruling on which of two truthful fixes
to take (CLAUDE.md §31 rule 3: ruling BEFORE planning). Second session of the same trigger;
the first (`mobile-dropped-partial-batch`) is independent.

## Current Focus

hypothesis: The contact merge engine's provider vocabulary is `{apollo, lusha, zoominfo, claude_web}` (`n8n/code/mergeContacts.js::_isProviderSource`, `src/merge_policy.py::PROVIDER_SOURCES`, `system_correctable_sources` in `config/field_policy.yaml`), but BOTH production contact callers label their candidates `"waterfall"` — the ingest lane via the plugin's `source_by_field` map, the enrichment lane via `ENRICH_MERGE`'s `{ source: "waterfall", confidence: 85, rankedByField }` with no `sourceByField`. Provenance therefore records `source: "waterfall"` for every field the pipeline writes, and on a later correction: (a) the D-72-08 system-correctable arm never fires (conjunct 2: `"waterfall"` is not on the list), and (b) the D-72-06/07 recency arm can never promote even a stale value (`candidateObservedAt` is `undefined` for a non-provider source, so no candidate is "newer"). Net: a `stale_refreshable` value the pipeline wrote is locked for the field's TTL AND beyond, unless a caller hand-labels a real provider — which is exactly what the operator's Claude did (`claude_web`) to land Renée Quirk's title.
test: offline — `mergeContacts({jobtitle:"Program Director", lv_contact_enrichment_provenance: <entry source "waterfall", value "Program Director">}, {jobtitle:"Deputy Chairperson"}, undefined, {source:"waterfall", confidence:85, historyByField:{jobtitle: <12 min ago>}, now, rowConflicted:false})` → expect `needs_review` "Refresh candidate requires review in MVP." Then the same with `sourceByField:{jobtitle:"claude_web"}` → `promote` via the system-correctable arm ONLY if the stored entry's source is also a listed provider — it is not, so still `needs_review`; with a 2-year-old history it promotes via recency (Renée's case).
expecting: reproduces the 1-of-4 outcome exactly: fresh + "waterfall" → refused; 2-years-stale + hand-labelled `claude_web` candidate → promoted.
next_action: RULING RECEIVED 2026-09-22 — operator chose Option A. Write the RED tests first (tests/n8n/mergeRecencyGate.test.mjs with source "waterfall"; Python oracle parity in tests/test_merge_policy*.py), confirm RED, then implement Option A in ONE commit across n8n/code/mergeContacts.js, n8n/code/mergeCompanies.js, src/merge_policy.py, config/field_policy.yaml (+ DEFAULT_*_POLICY mirrors), regenerate n8n bodies with scripts/build_cloud_workflows.py, run both full suites.
bug_class: bohrbug
reasoning_checkpoint: null
tdd_checkpoint: null

## Symptoms

expected: A wrong `jobtitle` the ingest lane wrote 12 minutes earlier (provider day-job value) is corrected by a higher-confidence, conflict-free candidate from the company's own board page — §17.2.1's "previously written by the enrichment system" PROMOTE clause, extended to `jobtitle` by D-72-08.
actual: 4 corrections sent under a grant with `source_by_field = {"jobtitle": "claude_web"}`; 1 landed (Renée Quirk, existing value ~2 years old, no pipeline provenance), 3 refused silently (Joan Norton `354794813936`, John Wreghitt `354684361160`, Matt Croasdaile `354776419827` — values written by the same lane 12 minutes earlier). Operator's Claude then wrote the three directly through the HubSpot connector, outside the grant/arming chain and the written_records audit trail.
errors: none surfaced — field-level `needs_review` inside `Merge Contacts`; dispatch reported no failures. The operator's Claude could not read runData (executions API unreachable at the time) and reasoned from config.
reproduction: deterministic offline (see test above). Live: any contact the pipeline created, corrected through the ingest lane within 180 days.
started: Phase 72 Plan 04 (2026-09-12) built the recency + system-correctable arms with tests that label sources `zoominfo`/`claude_web` (`tests/n8n/mergeRecencyGate.test.mjs:38-145`); no test exercises the production `"waterfall"` label, so the arms were green offline and dead live from day one.

## Eliminated

- hypothesis: contacts carry no provenance at all (operator's Claude: "`lv_enrichment_provenance` isn't populated on contacts")
  evidence: contacts use a DIFFERENT property, `lv_contact_enrichment_provenance` — live on the portal (`portal-schema-contacts-phase75.json`), fetched by the ingest lane (`build_cloud_workflows.py:3539`) and written on every contact patch (`:665, :1145, :3001, :3082`)
  timestamp: 2026-09-22
- hypothesis: the 180-day TTL alone explains it
  evidence: the TTL branch is reached only because the system-correctable arm failed on the source label; and even past the TTL a `"waterfall"` candidate cannot win (`candidateObservedAt` undefined) — Renée's landed only because the candidate was hand-labelled `claude_web`
  timestamp: 2026-09-22

## Evidence

- timestamp: 2026-09-22
  checked: n8n/code/mergeContacts.js:97-99 `_isProviderSource`, :181-195 `_isSystemCorrectable`, :245-270 `_gate` stale_refreshable branch, :407 `resolvedSource`, :414 `candidateObservedAt`
  found: provider vocabulary is the four names; `resolvedSource = sourceByField[field] ?? source`; observation time exists only for a provider-vocabulary source
  implication: any candidate whose resolved source is `"waterfall"` is clockless and non-correctable
- timestamp: 2026-09-22
  checked: scripts/build_cloud_workflows.py:2804-2842 (ENRICH_MERGE) and :4932 (local-live companies)
  found: `mergeContacts(row.existingRecord, candidate, undefined, { source: "waterfall", confidence: 85, rankedByField })` — `candidate` built from `row.scored.winners` (values only), `rankedByField` restricted to phone/mobilephone/email, no `sourceByField`; `n8n/code/scoreEnrichment.js:65-111` shows `ranked[field][0].source` DOES carry the winning provider per field
  implication: the enrichment lane throws away per-field provider names it already has and stamps `"waterfall"` into provenance
- timestamp: 2026-09-22
  checked: scripts/build_cloud_workflows.py:607-640 (MERGE_CONTACTS, ingest lane) and operator-claude-plugin/skills/enrich-before-ingest/SKILL.md:1167
  found: ingest candidates carry `sourceByField[f] = "waterfall"` from the plugin's round-level map; the plugin has no per-field provider name (STRUCT-01 forbids per-row provenance in the CSV)
  implication: the ingest lane can only ever say "waterfall"; a fix that requires real provider names on this lane is not available
- timestamp: 2026-09-22
  checked: config/field_policy.yaml:30-34, :277-281; n8n/code/mergeContacts.js:61-62; n8n/code/mergeCompanies.js:132-134; src/merge_policy.py:38, :401
  found: `system_correctable_sources` for `companies.industry` and `contacts.jobtitle` list the four providers; Python oracle mirrors the vocabulary in `PROVIDER_SOURCES`
  implication: Phase 46 parity rule applies — any vocabulary change lands in JS engines, the Python oracle and the yaml in ONE commit
- timestamp: 2026-09-22
  checked: tests/n8n/mergeRecencyGate.test.mjs:38-145
  found: every recency/system-correctable case uses `source: "zoominfo"` or `sourceByField: {jobtitle: "zoominfo"|"claude_web"|"csv"}`; none uses `"waterfall"`
  implication: the production label is untested; the regression test must use it
- timestamp: 2026-09-22
  checked: CLAUDE.md §17.2.2 amendment 1 and §13.0.2 Phase 72 gate (contact `1251`, execution `12406`: "lands lv_linkedin_url correctly (waterfall/85)")
  found: live provenance on Phase 72's own gate record already reads source `waterfall`
  implication: this is the standing live state, not a one-off of the AFA batch

## Resolution

root_cause: Vocabulary mismatch between the label the pipeline stamps (`"waterfall"`, both contact lanes) and the provider vocabulary the merge engine's recency and system-correctable arms require (`apollo|lusha|zoominfo|claude_web`). Every `stale_refreshable` value the pipeline itself wrote is un-correctable through the lane: the system-correctable arm never matches the stored source, and a `"waterfall"` candidate has no observation time so it cannot beat even a stale value. Phase 72's tests never used the production label.
fix: RULING 2026-09-22: Option A (operator). Options as evaluated —
  Option A (engine vocabulary, both lanes, smallest diff): treat `"waterfall"` as a provider-class source. `_isProviderSource` (mergeContacts.js AND mergeCompanies.js — byte-identical function text, both inline into one Code node), `PROVIDER_SOURCES` (src/merge_policy.py), and the `system_correctable_sources` lists for `contacts.jobtitle` / `companies.industry` (field_policy.yaml + DEFAULT_*_POLICY mirrors) gain `waterfall`. Truthfulness: the label is assigned only to fields the plugin's `provider_sourced_fields` proved came from the waterfall (post mobile-dropped-partial-batch fix: never a CSV-supplied value), and the observation time is the run time — same as `claude_web`. T-72-02 (backdated CSV column) stays closed by construction because a CSV value never receives the label.
  Option B (enrichment lane stamps real names + Option A for the ingest lane): ENRICH_MERGE derives `sourceByField[f] = ranked[f][0].source` from `row.scored.ranked` for every winner so enrichment-lane provenance names the actual provider; the ingest lane still needs Option A's `waterfall` admission because the plugin cannot know per-field providers. More honest provenance on one lane; larger diff; touches `n8n/wf_*.json` regeneration.
  Either way: RED tests first in `tests/n8n/mergeRecencyGate.test.mjs` (source `"waterfall"`, fresh value + stored `"waterfall"` entry → promote via correction; 2-year-stale + `"waterfall"` candidate → promote via recency) and the Python oracle parity test; regenerate bodies via `scripts/build_cloud_workflows.py`; do NOT deploy (operator step); plugin skill text: `enrich-before-ingest/SKILL.md` — no hand-built maps needed, and never hand-label a source the round did not use.
verification: (planned) RED→GREEN on both engines; `node --test tests/n8n/*.test.mjs`; full pytest; `git diff --stat n8n/` shows only regenerated jsCode strings, node counts unchanged.
oracle_type: specified
files_changed: []
