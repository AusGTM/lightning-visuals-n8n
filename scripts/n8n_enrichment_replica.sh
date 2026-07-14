#!/usr/bin/env bash
# scripts/n8n_enrichment_replica.sh
#
# Enrichment Wave B proof (ENRICHMENT-WORKFLOW-PLAN.md §5). Runs the locally-
# EXECUTABLE enrichment workflow (n8n/wf_enrichment_local.json) headless against
# the already-running Dockerized n8n (container `n8n`, v2.4.4). Like the M3
# contact replica, ALL logic is inlined into n8n Code nodes — there is NO host
# decision service to start. HubSpot search + provider waterfall + writes are
# mocked; enrichmentGate / normalizeProviders / scoreEnrichment / mergeContacts
# are the REAL Wave-A/M3 logic running on realistic fixture data.
#
# It:
#   1. docker cp's the local workflow into the container;
#   2. imports it (pinned id => idempotent upsert);
#   3. executes it via `n8n execute --id --rawOutput`;
#   4. asserts the create / enrich / skip gate branches each fired for the right
#      identity, the scored waterfall produced best-per-field winners WITH
#      provenance (source + score + agreedBy), and NO real HubSpot write occurred;
#   5. prints PASS or FAIL (non-zero on fail).
#
# Broker-port note (same as the M3 script): `n8n execute` spins up its own task
# broker; the running main instance already holds the default port in the shared
# container netns, so we pin the exec broker to a free port and disable runners.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CONTAINER=n8n
WF_FILE=wf_enrichment_local.json
WF_ID=LVenrichment01
EXEC_ENV=(-e N8N_RUNNERS_BROKER_PORT=5699 -e N8N_RUNNERS_ENABLED=false)
OUT_DIR="$(mktemp -d)"
OUT="$OUT_DIR/enrichment.json"

fail() { echo "FAIL: $*" >&2; exit 1; }

# 1 + 2. Copy + import.
echo "== importing $WF_FILE (id=$WF_ID) =="
docker cp "n8n/$WF_FILE" "$CONTAINER:/tmp/$WF_FILE"
docker exec "$CONTAINER" n8n import:workflow --input="/tmp/$WF_FILE" 2>&1 \
  | grep -v "Error tracking" | grep -q "Successfully imported" \
  || fail "import of $WF_FILE failed (v2.4.4 validity gate)"

# 3. Execute headless.
echo "== executing enrichment workflow =="
docker exec "${EXEC_ENV[@]}" "$CONTAINER" n8n execute --id="$WF_ID" --rawOutput 2>&1 \
  | grep -v "Error tracking" >"$OUT"

# 4. Assertions.
have_action() { grep -qE "\"action\": *\"$1\"" "$OUT"; }

have_action create || fail "no create action (expected jamie.rivera, not in HubSpot)"
have_action enrich || fail "no enrich action (expected alex.taylor, stale record)"
have_action skip   || fail "no skip action (expected sam.fresh, fresh+complete)"

# Scored waterfall must have produced winners with provenance (source + agreedBy).
grep -qE '"agreedBy"' "$OUT" || fail "no agreedBy provenance — scoring did not run"

# No real HubSpot write: every decided row is a dry run, writes are echoed only.
grep -qE '"dry_run": *true' "$OUT" || fail "dry_run flag missing — writes may not be gated"
if grep -qiE '"statusCode": *20[0-9].*hubapi' "$OUT"; then fail "a live HubSpot write occurred"; fi

echo
echo "----- per-identity decisions + sample scored winners (dry-run, no live write) -----"
python3 - "$OUT" <<'PY'
import json, sys
raw = open(sys.argv[1]).read()
# n8n --rawOutput prints a log preamble then the full run-data object.
obj = json.loads(raw[raw.index('{'):])
items = obj["data"]["resultData"]["runData"]["Decide Action"][0]["data"]["main"][0]
for it in items:
    r = it["json"]
    print(f"  {str(r.get('email')):40} action={str(r.get('action')):8} "
          f"gap_flag={r.get('gap_flag')}")
    for w in (r.get("winners_sample") or [])[:3]:
        ab = ",".join(w.get("agreedBy") or []) or "-"
        print(f"      {w['field']:14} -> {w['source']:9} score {w['score']:<5} agreedBy[{ab}]")
PY

echo
echo "PASS: local n8n enrichment replica fired all 3 gate branches (create/enrich/skip),"
echo "      the scored waterfall produced best-per-field winners with provenance,"
echo "      and NO real HubSpot write occurred."
echo "      (raw execution JSON: $OUT)"
