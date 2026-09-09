// tests/n8n/nodeRunRecovery.test.mjs
//
// Phase 70 Plan 04 Task 3 (D-70-01) — `n8n/code/nodeRunRecovery.js` is DELETED, not kept
// as a fallback. D-70-04's carry merges retire the by-name-recovery idiom this module
// existed to patch (F5, execution 12163 — .planning/debug/resolved/
// uat-batch-review-row-reads-failed.md): a converged node's per-item context no longer
// needs recovering by name at all, because every consumer downstream of an HTTP hop now
// reads its own row off a real Merge instead of `$('Node').all()`.
//
// This file used to test `recoverConvergedRun` in isolation (the F5 repro + the
// all-skip-run drift case + the ZoomInfo cache-token predicate variant). Those scenarios
// are retired along with the module — there is no longer a `recoverConvergedRun` to
// call. What this file asserts NOW is the deletion itself, on both sides: the module is
// gone from disk, and its own function-signature marker (the "run_recovery_inlined"
// violation form `detect_by_name_reads` still knows how to recognise, per
// `_run_recovery_marker()`'s own docstring) appears in none of the eight workflow JSON
// files `scripts/build_cloud_workflows.py::main()` writes — so a future regression that
// reinlines the retired idiom fails this test, not just the builder's own generation-time
// assertion (tests/test_no_by_name_reads.py covers that half).
import { test } from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const MODULE_PATH = path.join(ROOT, "n8n", "code", "nodeRunRecovery.js");

// The exact marker `_run_recovery_marker()` hardcodes post-deletion (scripts/
// build_cloud_workflows.py) — duplicated here deliberately: this file exists to prove
// the marker is absent from every committed artifact, so it must hold its OWN copy
// rather than importing the value it is checking for.
const MARKER = "function recoverConvergedRun(all, nodeName, runIndex, keep, maxRuns) {";

const WORKFLOW_FILES = [
  "wf_contact_ingest_local.json", "wf_contact_ingest_cloud.json",
  "wf_enrichment_local.json", "wf_enrichment_cloud.json", "wf_enrichment_local_live.json",
  "wf_scheduled_maintenance_cloud.json", "wf_backend_status_cloud.json",
  "wf_review_decision_cloud.json",
];

test("n8n/code/nodeRunRecovery.js does not exist on disk", () => {
  assert.equal(fs.existsSync(MODULE_PATH), false,
    "the module must be deleted, never kept as a fallback (D-70-01)");
});

test("recoverConvergedRun's signature marker appears in no committed workflow JSON", () => {
  for (const file of WORKFLOW_FILES) {
    const wfPath = path.join(ROOT, "n8n", file);
    assert.ok(fs.existsSync(wfPath), `committed workflow present: ${file}`);
    const text = fs.readFileSync(wfPath, "utf8");
    assert.equal(text.includes(MARKER), false,
      `${file} still carries the retired run-recovery marker verbatim`);
  }
});
