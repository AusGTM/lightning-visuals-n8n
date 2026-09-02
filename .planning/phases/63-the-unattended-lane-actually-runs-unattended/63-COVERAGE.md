# Phase 63 — External API Coverage Matrix

Produced 2026-09-02 at plan time to satisfy the `api-coverage.verify-pre` gate. The detector ran
over the five written PLAN.md bodies and returned `detected: true` (signal: the Anthropic Messages
API trust boundary in 63-03's threat model).

Phase 63 opens **no vendor account and adds no new integration surface**. Every API below was
already in use by this project. Two consumers are new — `scripts/replay_judge_models.py` (offline
model comparison) and `scripts/verify_sweep_shim_scheduler.sh` (host scheduler, not an external
API) — and both are read-only against the services they touch.

## Matrix

| capability | decision | reason |
|---|---|---|
| anthropic.messages | INTEGRATE | 63-03 replays stored judge payloads through two models to decide D-63-05's adequacy. Same endpoint and key the deployed Judge Call already uses. |
| anthropic.web_search | OPT-OUT | The research node's server-side tool is untouched. 63-05 only READS its effective max_uses as a lever-3 fact; lever 3 is deferred by CONTEXT.md. |
| anthropic.batch | OPT-OUT | A bounded offline corpus replayed once does not justify batch submission, and the production judge path is per-record and synchronous. |
| anthropic.models.list | OPT-OUT | Model ids come from CONFIG_FLAG_DEFAULTS, the single source both the builder and the harness read. Discovering them at runtime would create a second source. |
| n8n.executions.read | INTEGRATE | 63-03 extracts the judge-input corpus via GET /executions?includeData=true; 63-05 reads the disarmed proof execution back the same way. |
| n8n.executions.delete | OPT-OUT | No execution history is pruned. Retention is the corpus constraint this phase measures, not one it manipulates. |
| n8n.workflows.read | INTEGRATE | 63-05 reads deployed workflows back to assert stored jsCode and node counts after the PUT and after the bounce. |
| n8n.workflows.create-update | INTEGRATE | 63-05's deploy PUTs the committed JSON, closing the Phase 62 divergence (D-63-08), via the existing scripts/deploy_n8n_workflows.py write gate. |
| n8n.workflows.activate-deactivate | INTEGRATE | Required: a bare PUT never reloads a running workflow, so every deploy is followed by a deactivate/activate bounce. |
| n8n.webhook.enrichment | INTEGRATE | One disarmed recompute POST is 63-05's running-instance proof. Zero provider credits, zero Anthropic calls, expected write-blocked response. |
| n8n.credentials | OPT-OUT | No credential is created, rotated or read. Binding uses the existing gitignored id map; provisioning stays scripts/provision_n8n_credentials.py's job. |
| n8n.variables-tags-users-projects | OPT-OUT | Untouched. Cloud flags are baked at build time (AR-4), so no runtime variable surface is consumed by this phase. |
| hubspot.contacts | OPT-OUT | No contact is read or written. The judge replay is offline against stored payloads and the deploy proof is write-blocked by design (D-63-09). |
| hubspot.companies | OPT-OUT | No company property is written. The recompute proof derives a veto and refuses to write because no allowlist is armed. |
| hubspot.search | OPT-OUT | Phase 62's num_associated_contacts search change is DEPLOYED here, not authored here; this phase issues no search of its own. |
| hubspot.associations | OPT-OUT | Untouched. Association has exactly one implementation, in wf_contact_ingest_cloud (CLAUDE.md 13.0.1), and this phase does not go near it. |
| hubspot.webhooks | OPT-OUT | No subscription is added or changed. The only inbound event this phase sends is an operator-initiated recompute POST. |
| lusha | OPT-OUT | Zero credits by design. D-63-06 chose offline replay precisely because a single bulk run already halves the Lusha balance. |
| zoominfo | OPT-OUT | Untouched. The provider waterfall is not the bottleneck (~4s of a 34.2s wall) and this phase changes nothing on it. |
| apollo | OPT-OUT | Untouched. Same reason as ZoomInfo; no provider lane is edited, armed or exercised. |

## Notes

**A — the only new outbound consumer.** `scripts/replay_judge_models.py` is the first Python-side
Anthropic judge caller in this repo. It sends the SAME payloads the deployed `Judge Call` node
already sends, to the same vendor, under the same key, so it adds no new data class and no new
recipient. Its verdict artifact stores an input id and a content hash, never a request body.

**B — host scheduler is not an external API.** `scripts/verify_sweep_shim_scheduler.sh` drives
`launchctl` on the operator's own machine. It is a local OS facility rather than a network service,
so it carries no matrix row; its risks are registered in 63-02's `<threat_model>` (T-63-06,
T-63-07) instead.

**C — no package-manager installs.** No plan in this phase installs an npm, pip or cargo package,
so the package-legitimacy gate does not fire. Every `T-63-*-SC` supply-chain row across the five
threat models is dispositioned `accept` for that reason.

**D — nothing armed.** No INTEGRATE row above is exercised against a live write. The first live
unattended credit-spending batch remains un-run (D-63-09), unchanged by this phase.
