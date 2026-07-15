---
phase: phase-10
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - requirements.txt
  - src/service.py
  - tests/test_service.py
  - n8n/wf_upload_ingest.json
  - n8n/wf_weekly_sweep.json
  - scripts/n8n_replica_test.sh
autonomous: true
requirements: [P10-SC1, P10-SC2, P10-SC3]
user_setup: []

must_haves:
  truths:
    - "A local HTTP decision service exposes GET /health, POST /ingest, POST /sweep and REUSES run_contact_ingest + dedupe_sweep (no scoring/merge/dedupe logic reimplemented in JS or the service) — P10-SC1."
    - "The service performs NO live HubSpot write and NO live LLM call in the replica: HubSpot search/get are stubbed, dry_run is hard-True, allow_create defaults False, and the module never loads .env — P10-SC1/P10-SC3."
    - "Two importable n8n v2.4.4 workflow JSON templates exist (upload-ingest manual trigger; weekly scheduled sweep) whose HTTP nodes call the service at http://host.docker.internal:8088/ingest and /sweep — P10-SC2."
    - "The running Dockerized n8n imports both templates and executes them; the ingest execution output contains a dry-run PATCH/create marker and the sweep execution output contains duplicate/mangled findings — P10-SC2/P10-SC3."
    - "The full offline pytest suite (78 baseline + service tests) stays green with zero network — gating proof."
  artifacts:
    - requirements.txt
    - src/service.py
    - tests/test_service.py
    - n8n/wf_upload_ingest.json
    - n8n/wf_weekly_sweep.json
    - scripts/n8n_replica_test.sh
  key_links:
    - "Service binds 0.0.0.0:8088 (NOT 127.0.0.1) so host.docker.internal reaches it from the n8n container."
    - "Workflow httpRequest node URLs/port/paths (host.docker.internal:8088 /ingest, /sweep) must exactly match the service endpoints."
    - "run_contact_ingest's hs_search/hs_get MUST be stubbed by the service (default args hit real HubSpot) — the no-live-write guarantee."
    - "Workflow JSON must be valid n8n v2.4.4 (correct node types, typeVersion, connections map) or `n8n import:workflow` fails."
---

<objective>
Replicate the production n8n Cloud path on the already-running local Docker n8n
(container `n8n`, v2.4.4, http://localhost:5678): a thin HTTP decision service wraps
the existing ingest + sweep Python so an n8n HTTP Request node drives the pipeline
without duplicating logic in JS, and two importable workflow templates (upload-ingest +
weekly dedupe sweep) run end-to-end producing dry-run PATCH/create output under all
safety gates.

Purpose: Prove the production-shaped `trigger → parse → decision service → dry-run
writeback` path works on a local n8n replica before touching n8n Cloud, with zero live
HubSpot writes and ALLOW_CONTACT_CREATE off by default.
Output: src/service.py (FastAPI /ingest /sweep /health), tests/test_service.py (offline
gate), two n8n v2.4.4 workflow JSON templates, and scripts/n8n_replica_test.sh (the
scripted import+execute proof), plus fastapi+uvicorn pinned in requirements.txt.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/ROADMAP.md
@.planning/STATE.md

# Reuse targets — the service is a THIN wrapper over these; do not reimplement their logic.
@src/ingest.py
@src/sweep.py
@src/hubspot_client.py
@src/schemas.py

# The offline stub pattern to copy verbatim for the service's SAFE HubSpot stubs.
@tests/test_e2e_ingest.py

# main.py DEVIATION 1: never load_dotenv at import (keeps `import` side-effect-free / no live Haiku).
@main.py

# n8n workflow + node shapes this phase encodes.
# CLAUDE.md §13.1 (webhook receiver), §13.2 (scheduled poller), §13.4 (Workflow D weekly
# dedupe sweep), §18 (n8n node-level implementation).
</context>

<tasks>

<task type="auto">
  <name>Task 1: Decision service (FastAPI /health /ingest /sweep) + deps + offline gate — P10-SC1</name>
  <files>requirements.txt, src/service.py, tests/test_service.py</files>
  <action>
    Add `fastapi>=0.115.0` and `uvicorn>=0.30.0` to requirements.txt (pinned floors), then
    install with `.venv/bin/pip install -r requirements.txt`. Supply-chain (T-10-SC): fastapi
    and uvicorn are the ubiquitous standard ASGI stack, verified on pypi.org/project/fastapi and
    pypi.org/project/uvicorn, and were pre-approved by the developer in the phase brief — no new
    logic dependency, only the transport.

    Create src/service.py exposing a FastAPI app named `app`. Do NOT call load_dotenv at import
    (mirror main.py DEVIATION 1) so importing the module never fires live Haiku or leaks the
    HubSpot token. Reuse the SAME python modules — import run_contact_ingest from src.ingest and
    dedupe_sweep from src.sweep; reimplement NO scoring/merge/dedupe logic (this is the
    no-JS-duplication guarantee, P10-SC1). Endpoints:
      - GET /health returns {"status": "ok"}.
      - POST /ingest, body {path: str, allow_create: bool = False}. Build a deterministic SAFE
        STUB hs_search and hs_get by copying the value-routed _LOOKUP + canned hs_get shape from
        tests/test_e2e_ingest.py, so the bundled tests/fixtures/uploads/contacts_e2e.csv resolves
        every path (match+enrich, net_new, ambiguous, no-email, reject) with NO live HubSpot.
        Call run_contact_ingest(path, hs_search=stub_search, hs_get=stub_get,
        allow_create=body.allow_create, dry_run=True) and return the report list as JSON. dry_run
        is HARD True (never parameterized from the body) so the service can never live-write;
        allow_create defaults False (the SC3 gate).
      - POST /sweep, body {records: list[dict]}. Call dedupe_sweep(records) and return its
        SweepReport via model_dump().
    Document in the module docstring that the app is served with `uvicorn src.service:app
    --host 0.0.0.0 --port 8088`; binding 0.0.0.0 (not 127.0.0.1) is required so host.docker.internal
    reaches it from the n8n container.

    Create tests/test_service.py using FastAPI's TestClient, fully offline and hermetic (copy the
    conventions from tests/test_e2e_ingest.py): delenv HUBSPOT_PRIVATE_APP_TOKEN and
    ANTHROPIC_API_KEY, monkeypatch src.merge_policy.classify_field_with_haiku to a promote/stage
    fake, and arm src.hubspot_client.requests.get/post/patch sentinels that raise if any live call
    leaks. Tests: GET /health equals {"status": "ok"}; POST /ingest with the bundled e2e CSV and
    allow_create False returns a list containing a match entry whose action is patch and whose
    payload carries a dry_run PATCH, and contains NO create action (gate honored); POST /sweep with
    two records sharing one email plus one record with an unparseable phone returns
    duplicate_count >= 1 and at least one mangled finding. Assert reaching the end proves zero
    network.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/test_service.py -q</automated>
    <automated>.venv/bin/python -c "import src.service"</automated>
    <automated>.venv/bin/python -m pytest tests/ -q</automated>
  </verify>
  <done>src/service.py exposes /health, /ingest, /sweep; /ingest reuses run_contact_ingest with stubbed HubSpot and dry_run hard-True and allow_create default False; /sweep reuses dedupe_sweep; test_service.py is green offline with zero network; the full suite (78 baseline + new service tests) is still green.</done>
</task>

<task type="auto">
  <name>Task 2: n8n v2.4.4 workflow templates (upload-ingest + weekly sweep) — P10-SC2</name>
  <files>n8n/wf_upload_ingest.json, n8n/wf_weekly_sweep.json</files>
  <action>
    Author two minimal, import-clean n8n v2.4.4 workflow JSON files (each with nodes carrying
    typeVersion and a connections map wiring them in order). The httpRequest node URLs, port, and
    paths MUST exactly match the Task 1 service: http://host.docker.internal:8088/ingest and
    http://host.docker.internal:8088/sweep, POST, JSON body.

    n8n/wf_upload_ingest.json: n8n-nodes-base.manualTrigger → n8n-nodes-base.set (assigns
    path = "tests/fixtures/uploads/contacts_e2e.csv" and allow_create = false) →
    n8n-nodes-base.httpRequest (POST .../ingest, sendBody true, JSON body carrying {path,
    allow_create} from the Set node). Represents the production upload-ingest path (a webhook in
    n8n Cloud; a manual trigger locally so `n8n execute --id` can run it headless).

    n8n/wf_weekly_sweep.json: n8n-nodes-base.scheduleTrigger (weekly cron) → n8n-nodes-base.set
    (assigns records = a small array: two contacts sharing one email plus one contact with an
    unparseable phone, each shaped {id, properties:{...}}) → n8n-nodes-base.httpRequest (POST
    .../sweep, JSON body {records}). Represents CLAUDE.md §13.4 Workflow D weekly dedupe sweep;
    the schedule trigger is present for production shape, and `n8n execute --id` runs the whole
    workflow from its trigger.

    Keep both minimal — no credentials, no extra nodes. `n8n import:workflow` is the v2.4.4
    validity gate, so an invalid node type/typeVersion will fail import.
  </action>
  <verify>
    <automated>.venv/bin/python -c "import json; json.load(open('n8n/wf_upload_ingest.json')); json.load(open('n8n/wf_weekly_sweep.json')); print('json ok')"</automated>
    <automated>docker cp n8n/wf_upload_ingest.json n8n:/tmp/ && docker exec n8n n8n import:workflow --input=/tmp/wf_upload_ingest.json</automated>
    <automated>docker cp n8n/wf_weekly_sweep.json n8n:/tmp/ && docker exec n8n n8n import:workflow --input=/tmp/wf_weekly_sweep.json</automated>
  </verify>
  <done>Both workflow JSONs parse and import cleanly into the running n8n container; each httpRequest node targets http://host.docker.internal:8088 with the correct /ingest and /sweep path and POSTs the expected JSON body.</done>
</task>

<task type="auto">
  <name>Task 3: Scripted local-n8n replica proof (import + execute + assert) — P10-SC2/P10-SC3</name>
  <files>scripts/n8n_replica_test.sh</files>
  <action>
    Write scripts/n8n_replica_test.sh (bash, set -euo pipefail, EXIT trap that always kills the
    background uvicorn pid) that runs the end-to-end replica against the already-running `n8n`
    container:
      1. Start the service on the host with `env -u ANTHROPIC_API_KEY .venv/bin/uvicorn
         src.service:app --host 0.0.0.0 --port 8088` in the background — unsetting the key so the
         classifier's built-in no-key fallback applies (no live LLM, no token spend). Poll GET
         http://localhost:8088/health with bounded retries until it returns ok.
      2. For each workflow: `docker cp n8n/<file> n8n:/tmp/` then `docker exec n8n n8n
         import:workflow --input=/tmp/<file>`, capturing the imported workflow id from the import
         output.
      3. `docker exec n8n n8n execute --id=<id> --rawOutput` for each; capture stdout.
      4. Assert the ingest execution JSON contains a dry-run PATCH/create marker (grep for
         "dry_run" or an "action" of patch/create) and the sweep execution JSON contains
         duplicate/mangled findings (grep for "duplicate_count" / "mangled" / "to_review_ids").
      5. Tear down uvicorn via the trap. Print PASS on success or FAIL and exit non-zero on any
         failed assertion.
    Document (comment) that `n8n execute --id` runs the whole workflow from its trigger for both
    manual- and schedule-trigger workflows, so no ACTIVE state is required; note any adjustment
    needed for the running v2.4.4 CLI. Run the script and capture the actual n8n execution JSON
    into the SUMMARY.
  </action>
  <verify>
    <automated>bash scripts/n8n_replica_test.sh</automated>
  </verify>
  <done>Running the script imports both workflows into the local n8n, executes them, shows the dry-run PATCH/create output (ingest) and the duplicate/mangled findings (sweep), tears down uvicorn, and prints PASS with exit 0 — with no live HubSpot write and ALLOW_CONTACT_CREATE off. The captured execution JSON is pasted into the SUMMARY.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| n8n container → host decision service | HTTP Request node crosses from the container to the host at host.docker.internal:8088 (untrusted transport, local only). |
| uploaded file → /ingest | A file path from the request body is read and parsed by run_contact_ingest. |
| service → HubSpot / Anthropic | The ONLY place a live write/LLM call could originate; must be fully stubbed/dry-run in the replica. |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-10-01 | Info Disclosure | decision service bound on 0.0.0.0:8088 | low | accept | Local replica only; responses carry only report/SweepReport JSON, never HUBSPOT token or hs_headers. Documented as local-dev-only, not exposed publicly. |
| T-10-02 | Tampering | POST /ingest writeback | high | mitigate | dry_run hard-coded True in the service (not body-parameterized); HubSpot hs_search/hs_get stubbed; allow_create defaults False. No live PATCH/create possible. |
| T-10-03 | Info Disclosure | accidental .env load → live Haiku / token leak | medium | mitigate | Service never calls load_dotenv at import (main.py DEVIATION 1); replica launches uvicorn with `env -u ANTHROPIC_API_KEY`, so the classifier's no-key fallback runs with no network. |
| T-10-04 | Denial of Service | arbitrary `path` read by /ingest | low | mitigate | Replica passes only repo-relative fixture paths; path is developer-controlled on a local-only port, not a public endpoint. |
| T-10-SC | Tampering | pip installs (fastapi, uvicorn) | high | mitigate | Pinned floors; verified on pypi.org/project/fastapi and pypi.org/project/uvicorn; standard ASGI stack, developer-pre-approved in the phase brief. No [ASSUMED]/[SUS] packages. |
</threat_model>

<verification>
Offline gate (authoritative, zero network):
- `.venv/bin/python -m pytest tests/ -q` → 78 baseline + new service tests all green.
- `.venv/bin/python -c "import src.service"` imports with no side effect / no network.

Integration proof (the running n8n container is available now — RUN it):
- `bash scripts/n8n_replica_test.sh` imports both workflows into the local Docker n8n,
  executes them, and asserts the ingest output shows a dry-run PATCH/create and the sweep
  output shows duplicate/mangled findings. This is the integration proof; if Docker/n8n is
  transiently flaky it is non-gating, but the offline pytest gate above is authoritative and
  must pass. Capture the actual `n8n execute --rawOutput` JSON into the SUMMARY.
</verification>

<success_criteria>
- P10-SC1: src/service.py exposes /health, /ingest, /sweep and invokes run_contact_ingest +
  dedupe_sweep directly (no logic duplicated in JS or the service); tests/test_service.py proves
  it offline.
- P10-SC2: n8n/wf_upload_ingest.json and n8n/wf_weekly_sweep.json are valid v2.4.4 JSON that the
  local Docker n8n imports and executes end-to-end, producing dry-run PATCH/create output.
- P10-SC3: the replica run demonstrates trigger → set/parse → decision service → dry-run
  writeback with every safety gate honored (dry_run True, ALLOW_CONTACT_CREATE off by default,
  no live HubSpot write, no live LLM call).
</success_criteria>

<output>
Create `.planning/phases/phase-10/PLAN-SUMMARY.md` when done, and paste the captured
`n8n execute --rawOutput` JSON (ingest dry-run PATCH/create + sweep duplicate/mangled findings)
into it as the integration evidence.
</output>
