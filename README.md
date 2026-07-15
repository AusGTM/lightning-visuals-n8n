# Lightning Visuals — HubSpot Enrichment & ICP Scoring (n8n)

> **Proprietary & Confidential.** Copyright © 2026 **Australia Go To Market (AusGTM)** and **Dr. Robert Li**. Licensed for use by **Lightning Visuals**. See [LICENSE](LICENSE).

A HubSpot → n8n waterfall **enrichment + ICP-scoring** system for Lightning Visuals' RevOps/sales team. It enriches contacts and companies from multiple providers, scores them against a governing-body-first ICP rubric, and writes back to HubSpot under a strict **non-clobber** policy — with a **dry-run** path that emits the exact payload without touching the CRM.

The production orchestration runs **entirely in n8n Cloud** (out-of-box nodes + external APIs, no deployed service). A tested Python engine acts as the reference oracle for the JavaScript ported into n8n Code nodes.

## Status

| Area | State |
|---|---|
| ICP scoring engine (Python) | ✅ 83 tests |
| Contact ingestion (file → identity/dedupe → non-clobber merge) | ✅ |
| n8n Cloud-native workflows (contact ingest + enrichment) | ✅ run on local n8n replica |
| Provider auth (Lusha / Apollo / ZoomInfo) | ✅ validated live |
| ZoomInfo autonomous OAuth2 (cached, refresh-on-401) | ✅ verified |
| `lv_*` HubSpot properties | ⏳ **not yet created** (blocks live writeback) |
| Live-provider dry run | ⏳ next |

## Repository layout

```
config/        # scoring rubric, field-ownership policy, provider priority, source registry (YAML)
src/           # Python engine: schemas, scoring, normalizer, merge, ingest, HubSpot client (reference oracle)
tests/         # Python suite (pytest) + n8n JS module tests (node --test)
n8n/           # n8n workflow templates (Cloud + local) and inlined Code-node modules (n8n/code/*.js)
scripts/       # build_cloud_workflows.py (inliner) + local-n8n replica proof scripts
docs/          # project documentation (see below)
.planning/     # GSD planning trail (roadmap, phases, decisions)
main.py        # local MVP entrypoint (company scoring + `--ingest <file>` contact ingestion)
CLAUDE.md      # canonical technical specification (also Claude Code project instructions)
```

## Documentation

- **Architecture / design** — [`docs/architecture/ENRICHMENT-WORKFLOW-PLAN.md`](docs/architecture/ENRICHMENT-WORKFLOW-PLAN.md) · canonical spec: [`CLAUDE.md`](CLAUDE.md)
- **Business** — [`docs/business/icp-scoring.md`](docs/business/icp-scoring.md) (ICP / Anti-ICP validation from 92 closed deals)
- **Reviews / assessments** — [`docs/reviews/REVIEW.md`](docs/reviews/REVIEW.md) (reviewer runbook) · [`docs/reviews/GAP-ANALYSIS-n8n.md`](docs/reviews/GAP-ANALYSIS-n8n.md)
- **n8n workflows** — [`n8n/README.md`](n8n/README.md) (import, credentials, ZoomInfo OAuth2, Cloud-vs-local)
- **Changelog** — [`CHANGELOG.md`](CHANGELOG.md)

## Quick start (local)

```bash
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

.venv/bin/python -m pytest tests/ -q          # Python suite (offline)
node --test tests/n8n/                          # n8n JS module tests
.venv/bin/python main.py                        # company scoring (dry-run)
.venv/bin/python main.py --ingest tests/fixtures/uploads/contacts_e2e.csv   # contact ingestion (dry-run)
```

Secrets live in a gitignored `.env` (see `.env.example`). In production, secrets live in **n8n's credential store / Variables**, never in the repo. Nothing writes to HubSpot unless a write is explicitly enabled and gated.

## License

Proprietary. Copyright © 2026 Australia Go To Market (AusGTM) and Dr. Robert Li. Licensed for use by Lightning Visuals. See [LICENSE](LICENSE). Not for redistribution or use outside the AusGTM–Lightning Visuals engagement without written permission.
