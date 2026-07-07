# src/service.py
#
# Phase 10: a THIN HTTP decision service that lets an n8n HTTP Request node drive the
# existing Python pipeline without duplicating any scoring/merge/dedupe logic in JS.
# It wraps run_contact_ingest (src.ingest) and dedupe_sweep (src.sweep) verbatim.
#
# Safety (P10-SC3): this module is a LOCAL REPLICA and can NEVER live-write:
#   - dry_run is HARD True on the ingest call (never taken from the request body).
#   - allow_create defaults False (the ALLOW_CONTACT_CREATE gate).
#   - HubSpot search/get are in-service SAFE STUBS copied from tests/test_e2e_ingest.py,
#     so no live HubSpot call ever leaves the process.
#   - load_dotenv is NOT called at import (mirrors main.py DEVIATION 1) so importing the
#     module fires no live Haiku and never leaks the HubSpot token.
#
# Serve with:  uvicorn src.service:app --host 0.0.0.0 --port 8088
# Bind 0.0.0.0 (not 127.0.0.1) so host.docker.internal reaches it from the n8n container.
from typing import Any, List

from fastapi import FastAPI
from pydantic import BaseModel

from .ingest import run_contact_ingest
from .sweep import dedupe_sweep

app = FastAPI(title="LV enrichment decision service (local replica)")

# --- SAFE HubSpot stubs (copied from tests/test_e2e_ingest.py) --------------------
# Value-routed lookup keyed on the NORMALIZED (propertyName, value) resolve_identity
# emits. Resolves every path of the bundled contacts_e2e.csv with ZERO live HubSpot:
#   Row A bob.smith@ -> match(123); Row B alice@ -> net_new; Row C +61400222333 ->
#   ambiguous(777); Row D/E -> review/reject. Everything else defaults to [].
_LOOKUP = {
    ("email", "bob.smith@example.com"): [{"id": "123"}],
    ("email", "alice@example.com"): [],
    ("phone", "+61400222333"): [{"id": "777"}],
}


def stub_search(object_type, filters, properties=None, limit=100):
    f0 = filters[0]
    return {"results": _LOOKUP.get((f0["propertyName"], f0["value"]), [])}


def stub_get(object_type, record_id, properties):
    # Row-A existing contact: present+different jobtitle, blank phone, present linkedin.
    return {"id": "123", "properties": {
        "email": "bob.smith@example.com",
        "firstname": "Bob",
        "lastname": "Smith",
        "jobtitle": "Sales Manager",
        "phone": "",
        "linkedin_url": "https://linkedin.com/in/bob-existing",
    }}


class IngestBody(BaseModel):
    path: str
    allow_create: bool = False


class SweepBody(BaseModel):
    records: List[dict]


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/ingest")
def ingest(body: IngestBody) -> List[dict]:
    # dry_run HARD True; allow_create from body (default False). Stubbed HubSpot => no
    # live write, ever. Returns the per-row report list run_contact_ingest produces.
    return run_contact_ingest(
        body.path,
        hs_search=stub_search,
        hs_get=stub_get,
        allow_create=body.allow_create,
        dry_run=True,
    )


@app.post("/sweep")
def sweep(body: SweepBody) -> dict[str, Any]:
    return dedupe_sweep(body.records).model_dump()
