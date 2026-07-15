# Review Guide — lv-n8n-poc

How to review what was built (Milestone 1: company ICP scoring MVP; Milestone 2: contact ingestion + n8n replica). Every command below was run and verified. Nothing here writes to HubSpot.

---

## 0. One-time setup

```bash
cd lv-n8n-poc
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
```

Real keys live in a gitignored `.env` (HubSpot + Anthropic set; provider keys empty — mocks cover them). You do NOT need keys to review: the whole suite runs offline.

---

## 1. Fastest signal — run the whole test suite (offline, ~1s)

```bash
.venv/bin/python -m pytest tests/ -q
```

Expect: **83 passed**, no network. This is the gate. If it's green, the logic is proven at unit + functional + E2E level.

Per-area breakdown if you want to run pieces:

```bash
.venv/bin/python -m pytest tests/test_icp_scoring.py -q        # 16 scoring cases
.venv/bin/python -m pytest tests/test_merge_policy.py -q       # non-clobber merge
.venv/bin/python -m pytest tests/test_identity.py -q           # dedupe resolver (the M2 core)
.venv/bin/python -m pytest tests/test_e2e_ingest.py -q         # full ingestion matrix
.venv/bin/python -m pytest tests/test_sweep.py -q              # dedupe/mangled sweep
.venv/bin/python -m pytest tests/test_service.py -q            # FastAPI decision service
```

---

## 2. See it run — company scoring (M1)

```bash
set -a; . ./.env; set +a
.venv/bin/python main.py
```

What to check in the output:

- Prints provider results, field decisions, ICP score, and the exact HubSpot PATCH.
- `lv_icp_tier: A`, `lv_icp_fit_score: 70`, `lv_recommended_motion: work_direct` (fixture is an AU racing league; live Haiku promotes org_type/produces_content).
- `"dry_run": true` at the bottom → **no HubSpot write**.
- Conflicting firmographics (revenue, employees) → `needs_review`, not silently promoted.

Offline variant (no key needed) — scoring degrades to `Unscored` because nothing gets promoted without the classifier; that's the documented conservative fallback, not a bug.

---

## 3. See it run — contact ingestion (M2)

```bash
.venv/bin/python main.py --ingest tests/fixtures/uploads/contacts_e2e.csv
```

The 5-row fixture exercises every path. Expected per-row outcomes:

| Row                    | Outcome → Action                                                           |
| ---------------------- | --------------------------------------------------------------------------- |
| has email, HubSpot hit | `match` → `patch` (dry-run)                                            |
| valid email, 0 hits    | `net_new` → `create` if `ALLOW_CONTACT_CREATE=true`, else `review` |
| no email, weak-key hit | `ambiguous` → `review`                                                 |
| no email, no hits      | `ambiguous` → `review` (**hard rule: never auto-create**)        |
| missing identity key   | `rejected` → `skip` (never reaches resolution)                         |

Note: with real HubSpot fns this hits the live CRM search; the tests inject mocked search/get so review stays offline and write-free.

---

## 4. The n8n replica (M2 final proof) — runs on the local n8n server

Requires the running `n8n` Docker container (already up on :5678) and a free host port 8088.

```bash
bash scripts/n8n_replica_test.sh
```

Expect: **PASS**. It starts the FastAPI decision service, imports both workflow templates into the container, executes them headless (`n8n execute --rawOutput`), and asserts:

- ingest workflow → dry-run `patch`/`review` actions, **no `create` leaked** (create gated off);
- sweep workflow → `duplicate_count: 1`, `mangled_count: 1`.

This replicates the production n8n Cloud shape: **trigger → parse → HTTP call to decision service → dry-run writeback**. The container reaches the host service via `host.docker.internal:8088`.

---

## 5. What to actually scrutinize

### Decisions to challenge (not code — judgment calls)

- **Auto-create net-new on valid email** (gated, dry-run). Reasonable? The guard: create only fires when `ALLOW_CONTACT_CREATE=true` AND a pre-create email re-check still returns 0 hits. Everything ambiguous → review. See `src/ingest.py` `precreate_email_recheck` + `run_contact_ingest`.
- **Match keys**: auto-confident only on `email`/`linkedin_url`; `phone+lastname` and `name+company` are always `ambiguous`. Too conservative? Too loose? `src/identity.py`.
- **Email asymmetry**: `manual_protected` on enrich (never overwrites an existing contact's email) but written on create (new record identity). Correct? `config/field_policy.yaml` contacts block + `src/ingest.py`.
- **CSV trust = confidence 80** for an internal upload (vs the spec's example 60, which would clear no contact threshold). `src/ingest.py` `row_to_provider_result`. Adjust per how much you trust uploads.
- **ICP weights are illustrative** pending JTBD-2 sign-off — config-driven in `config/icp_scoring.yaml`, changeable without code.

### 4 SPEC defects found + fixed (worth a look — the spec's own code shipped these)

1. `produces_content` bool-key lookup → flagship Tier A scored as B. `src/icp_scoring.py`.
2. `choose_best` returned a list, callers deref'd one element → crash. `src/merge_policy.py`.
3. `evidence_url` list assigned to `Optional[str]` schema field → crash. `src/merge_policy.py`.
4. `msg.content.text` vs SDK's `content[0].text` → live crash. `src/classifier_haiku.py`, `src/validator_sonnet.py`.

### Safety guarantees to verify yourself

- Nothing writes to HubSpot: grep for `requests.post`/`requests.patch` — they're only reached when `dry_run=False`, and `DRY_RUN`/`ALLOW_CANONICAL_WRITES`/`ALLOW_CONTACT_CREATE` all default safe. The decision service hard-codes `dry_run=True`.
- `.env` is gitignored (`git check-ignore .env`). No tokens in the repo.

---

## 6. Where the planning trail lives

- `.planning/ROADMAP.md` — both milestones, phase-by-phase goals + success criteria.
- `.planning/phases/phase-*/PLAN.md` + `*-SUMMARY.md` — per-phase plan, what shipped, deviations.
- `.planning/PROJECT.md` — decisions + risks. `.planning/INGEST-CONFLICTS.md` — source-doc reconciliation.
- Source spec: `CLAUDE.md` (technical) + `icp-scoring.md` (business rationale).

## 7. Known caveats (already documented)

- n8n schedule-trigger workflow got a `manualTrigger` added so it runs headless (schedule triggers can't be CLI-started in v2.4.4); the schedule node is retained for production shape.
- Decision service uses safe HubSpot stubs — the replica never touches real HubSpot by design. Live writeback path exists in `main.py`/`hubspot_client.py`, behind the same gates, for a future milestone (needs HubSpot Pro).
- Staged-but-not-promoted signals don't feed the scorer (only promoted ones do) — defensible, noted in the M1 integration report.
