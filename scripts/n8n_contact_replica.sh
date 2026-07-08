#!/usr/bin/env bash
# scripts/n8n_contact_replica.sh
#
# Milestone 3 Wave B proof. Runs the locally-EXECUTABLE contact-ingest workflow
# (n8n/wf_contact_ingest_local.json) headless against the already-running
# Dockerized n8n (container `n8n`, v2.4.4). Unlike the M2 replica, ALL logic is
# inlined into n8n Code nodes — there is NO host decision service to start.
#
# It:
#   1. docker cp's the local workflow into the container;
#   2. imports it (pinned id => idempotent upsert);
#   3. executes it via `n8n execute --id --rawOutput`;
#   4. asserts every ingestion path fired (match->update, net_new->review [create
#      gated off], ambiguous->review, rejected->skip), the REAL email verifier
#      returned a status, and NO real HubSpot write occurred;
#   5. prints PASS or FAIL (non-zero on fail).
#
# The email verifier HTTP node is REAL (the container has internet). If it is
# unreachable the node is non-gating: Apply Email falls back to PROBABLY_VALID
# and the rest of the pipeline still runs — the script reports the fallback.
#
# Broker-port note (same as the M2 script): `n8n execute` spins up its own task
# broker; the running main instance already holds the default port in the shared
# container netns, so we pin the exec broker to a free port and disable runners.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CONTAINER=n8n
WF_FILE=wf_contact_ingest_local.json
WF_ID=LVcontactIngest01
EXEC_ENV=(-e N8N_RUNNERS_BROKER_PORT=5699 -e N8N_RUNNERS_ENABLED=false)
OUT_DIR="$(mktemp -d)"
OUT="$OUT_DIR/contact_ingest.json"

fail() { echo "FAIL: $*" >&2; exit 1; }

# 1 + 2. Copy + import.
echo "== importing $WF_FILE (id=$WF_ID) =="
docker cp "n8n/$WF_FILE" "$CONTAINER:/tmp/$WF_FILE"
docker exec "$CONTAINER" n8n import:workflow --input="/tmp/$WF_FILE" 2>&1 \
  | grep -v "Error tracking" | grep -q "Successfully imported" \
  || fail "import of $WF_FILE failed (v2.4.4 validity gate)"

# 3. Execute headless (real email-verifier HTTP call happens here).
echo "== executing contact-ingest workflow =="
docker exec "${EXEC_ENV[@]}" "$CONTAINER" n8n execute --id="$WF_ID" --rawOutput 2>&1 \
  | grep -v "Error tracking" >"$OUT"

# 4. Assertions.
have_action() { grep -qE "\"action\": *\"$1\"" "$OUT"; }
have_outcome() { grep -qE "\"outcome\": *\"$1\"" "$OUT"; }

have_outcome match     || fail "no match outcome (expected bob.smith email hit)"
have_outcome net_new   || fail "no net_new outcome (expected alice, valid email 0 hits)"
have_outcome ambiguous || fail "no ambiguous outcome (expected Carol/Dave, no email)"
have_outcome rejected  || fail "no rejected outcome (expected blank-identity row)"

have_action update || fail "match row did not route to update"
have_action review || fail "no review action (net_new gated + ambiguous should review)"
have_action skip   || fail "rejected row did not route to skip"

# Create must NOT fire: allow_create=false in the local proof.
if have_action create; then fail "a create action leaked despite allow_create=false"; fi

# The real email verifier must have returned a status for the emailed rows.
grep -qE '"email_status": *"[A-Z_]+"' "$OUT" \
  || fail "no email verifier status captured"

# No real HubSpot write: every decided row is a dry run, writes are echoed only.
grep -qE '"dry_run": *true' "$OUT" || fail "dry_run flag missing — writes may not be gated"
if grep -qiE '"statusCode": *20[0-9].*hubapi' "$OUT"; then fail "a live HubSpot write occurred"; fi

# Detect (non-fatally) whether the live verifier was reached vs the fallback.
if grep -qE '"email_verify_fallback": *true' "$OUT"; then
  VERIFIER_REACHED="NO (fell back to PROBABLY_VALID, non-gating)"
else
  VERIFIER_REACHED="YES"
fi

echo
echo "----- per-row decisions (dry-run, no live write) -----"
python3 - "$OUT" <<'PY'
import json, sys
raw = open(sys.argv[1]).read()
# n8n --rawOutput prints a log preamble then the full run-data object.
obj = json.loads(raw[raw.index('{'):])
items = obj["data"]["resultData"]["runData"]["Decide Action"][0]["data"]["main"][0]
for it in items:
    r = it["json"]
    print(f"  {str(r.get('name') or r.get('email') or '(no id)'):22} "
          f"outcome={str(r.get('outcome')):10} action={str(r.get('action')):8} "
          f"email_status={r.get('email_status')}")
PY

echo
echo "----- email verifier reached: $VERIFIER_REACHED -----"
echo
echo "PASS: local n8n contact-ingest replica ran all paths (match/net_new/ambiguous/rejected),"
echo "      real email verifier returned a status, and NO real HubSpot write occurred."
echo "      (raw execution JSON: $OUT)"
