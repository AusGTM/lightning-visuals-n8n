#!/usr/bin/env bash
# scripts/n8n_replica_test.sh
#
# Phase 10 (P10-SC2/P10-SC3): end-to-end replica proof against the already-running
# Dockerized n8n (container `n8n`, v2.4.4). It:
#   1. starts the FastAPI decision service on the host (0.0.0.0:8088) with ANTHROPIC_API_KEY
#      unset, so the classifier's no-key fallback runs — no live LLM, no token spend;
#   2. imports both workflow templates into n8n (pinned ids => idempotent upsert);
#   3. executes each via `n8n execute --id --rawOutput`;
#   4. asserts the ingest output shows a dry-run PATCH action and the sweep output shows
#      duplicate/mangled findings;
#   5. always tears down uvicorn via the EXIT trap; prints PASS or FAIL (non-zero on fail).
#
# Trigger notes (v2.4.4 CLI, verified on this host):
#   - `n8n execute --id` runs the whole graph starting from a MANUAL trigger. It REJECTS a
#     schedule-only workflow ("Missing node to start execution"), so wf_weekly_sweep.json
#     carries BOTH a scheduleTrigger (production shape) and a manualTrigger (headless start).
#   - The CLI execute spins up its own task broker; the running main instance already holds
#     the default broker port 5679 in the shared container netns, so we point the exec's
#     broker at a free in-container port (5699) and disable runners for the exec.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PORT=8088
CONTAINER=n8n
INGEST_ID=LVuploadIngest01
SWEEP_ID=LVweeklySweep001
EXEC_ENV=(-e N8N_RUNNERS_BROKER_PORT=5699 -e N8N_RUNNERS_ENABLED=false)
OUT_DIR="$(mktemp -d)"

UVICORN_PID=""
cleanup() { [ -n "$UVICORN_PID" ] && kill "$UVICORN_PID" 2>/dev/null || true; }
trap cleanup EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }

# 1. Start the decision service (no ANTHROPIC key => classifier no-key fallback, no live LLM).
env -u ANTHROPIC_API_KEY .venv/bin/uvicorn src.service:app \
  --host 0.0.0.0 --port "$PORT" >"$OUT_DIR/uvicorn.log" 2>&1 &
UVICORN_PID=$!

echo "== waiting for service on :$PORT =="
for _ in $(seq 1 40); do
  curl -sf "http://localhost:$PORT/health" >/dev/null 2>&1 && break
  sleep 0.25
done
curl -sf "http://localhost:$PORT/health" >/dev/null 2>&1 || fail "service /health never came up"
echo "service healthy: $(curl -s http://localhost:$PORT/health)"

# 2 + 3. Import then execute each workflow.
run_wf() {
  local file="$1" id="$2" out="$3"
  docker cp "n8n/$file" "$CONTAINER:/tmp/$file"
  docker exec "$CONTAINER" n8n import:workflow --input="/tmp/$file" 2>&1 \
    | grep -v "Error tracking" | grep -q "Successfully imported" \
    || fail "import of $file failed"
  docker exec "${EXEC_ENV[@]}" "$CONTAINER" n8n execute --id="$id" --rawOutput 2>&1 \
    | grep -v "Error tracking" >"$out"
}

echo "== upload-ingest workflow =="
run_wf wf_upload_ingest.json "$INGEST_ID" "$OUT_DIR/ingest.json"
echo "== weekly-sweep workflow =="
run_wf wf_weekly_sweep.json "$SWEEP_ID" "$OUT_DIR/sweep.json"

# 4. Assertions.
# Ingest: a dry-run PATCH action must be present (the match row's writeback), and the
# ALLOW_CONTACT_CREATE gate must hold (no create action with allow_create=false).
grep -qE '"action": *"patch"' "$OUT_DIR/ingest.json" \
  || fail "ingest: no dry-run PATCH action found"
if grep -qE '"action": *"create"' "$OUT_DIR/ingest.json"; then
  fail "ingest: a create action leaked despite allow_create=false"
fi

# Sweep: duplicate and mangled findings must be present.
grep -qE '"duplicate_count": *[1-9]' "$OUT_DIR/sweep.json" \
  || fail "sweep: no duplicate findings"
grep -qE '"mangled_count": *[1-9]' "$OUT_DIR/sweep.json" \
  || fail "sweep: no mangled findings"
grep -q '"to_review_ids"' "$OUT_DIR/sweep.json" \
  || fail "sweep: no to_review_ids"

echo
echo "----- ingest actions (dry-run, no live write) -----"
grep -oE '"(outcome|action)": *"[^"]*"' "$OUT_DIR/ingest.json" | paste - -
echo "----- sweep findings -----"
grep -oE '"(duplicate_count|mangled_count)": *[0-9]+' "$OUT_DIR/sweep.json"

echo
echo "PASS: local n8n replica ran trigger -> set -> decision service -> dry-run output"
echo "      (raw execution JSON: $OUT_DIR/ingest.json, $OUT_DIR/sweep.json)"
