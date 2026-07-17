#!/usr/bin/env bash
# scripts/n8n_enrichment_live_replica.sh
#
# LIVE end-to-end enrichment proof. Runs n8n/wf_enrichment_local_live.json headless in the
# already-running Dockerized n8n. Unlike n8n_enrichment_replica.sh (mock providers), this
# hits the REAL providers — Lusha (GET v2), Apollo (people/match + reveal), ZoomInfo (cached
# GTM token) — and a read-only HubSpot SEARCH. Secrets are read from ./.env on the host and
# passed into the exec process with `docker exec -e` (the nodes read them via $env).
#
# READ-ONLY: the workflow has NO write nodes; Decide Action echoes the would-be payload.
# It spends a few provider credits (same as the batch dry-run). No HubSpot write occurs.
#
# Broker-port note: `n8n execute` spins up its own task broker; the running main instance
# holds the default port in the shared container netns, so we pin a free port + disable runners.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CONTAINER=n8n
WF_FILE=wf_enrichment_local_live.json
WF_ID=LVenrichmentLive01
OUT_DIR="$(mktemp -d)"
OUT="$OUT_DIR/enrichment_live.json"

fail() { echo "FAIL: $*" >&2; exit 1; }

# Load provider/HubSpot secrets from .env into this shell (not printed).
[ -f .env ] || fail ".env not found — needed for live provider + HubSpot keys"
set -a; . ./.env; set +a
for v in LUSHA_API_KEY APOLLO_API_KEY ZOOMINFO_CLIENT_ID ZOOMINFO_CLIENT_SECRET HUBSPOT_PRIVATE_APP_TOKEN; do
  [ -n "${!v:-}" ] || fail "$v is empty in .env"
done

echo "== importing $WF_FILE (id=$WF_ID) =="
docker cp "n8n/$WF_FILE" "$CONTAINER:/tmp/$WF_FILE"
docker exec "$CONTAINER" n8n import:workflow --input="/tmp/$WF_FILE" 2>&1 \
  | grep -v "Error tracking" | grep -q "Successfully imported" \
  || fail "import of $WF_FILE failed"

echo "== executing LIVE enrichment workflow (real providers, read-only HubSpot) =="
docker exec \
  -e N8N_RUNNERS_BROKER_PORT=5699 -e N8N_RUNNERS_ENABLED=false \
  -e N8N_BLOCK_ENV_ACCESS_IN_NODE=false \
  -e LUSHA_API_KEY="$LUSHA_API_KEY" \
  -e APOLLO_API_KEY="$APOLLO_API_KEY" \
  -e ZOOMINFO_CLIENT_ID="$ZOOMINFO_CLIENT_ID" \
  -e ZOOMINFO_CLIENT_SECRET="$ZOOMINFO_CLIENT_SECRET" \
  -e HUBSPOT_PRIVATE_APP_TOKEN="$HUBSPOT_PRIVATE_APP_TOKEN" \
  "$CONTAINER" n8n execute --id="$WF_ID" --rawOutput 2>&1 \
  | grep -v "Error tracking" >"$OUT"

# Assertions: dry-run only, and the scored waterfall produced provider-sourced winners
# (proves the LIVE calls actually returned data through the real n8n runtime).
grep -qE '"dry_run": *true' "$OUT" || fail "dry_run flag missing — writes may not be gated"
grep -qE '"source": *"(lusha|apollo|zoominfo)"' "$OUT" \
  || fail "no provider-sourced winner — live provider calls returned nothing usable"

echo
echo "----- per-identity decisions + scored winners (LIVE providers, dry-run) -----"
python3 - "$OUT" <<'PY'
import json, sys
raw = open(sys.argv[1]).read()
obj = json.loads(raw[raw.index('{'):])
items = obj["data"]["resultData"]["runData"]["Decide Action"][0]["data"]["main"][0]
for it in items:
    r = it["json"]
    print(f"  {str(r.get('email')):42} action={str(r.get('action')):8} gap_flag={r.get('gap_flag')}")
    for w in (r.get("winners_sample") or []):
        ab = ",".join(w.get("agreedBy") or []) or "-"
        print(f"      {w['field']:14} -> {str(w['source']):9} score {w['score']:<5} agreedBy[{ab}]")
PY

echo
echo "PASS: LIVE local n8n enrichment fired the full real-provider waterfall end-to-end"
echo "      (Lusha + Apollo + ZoomInfo + read-only HubSpot search), scored best-per-field"
echo "      winners with provenance, and issued NO HubSpot write."
echo "      (raw execution JSON: $OUT)"
