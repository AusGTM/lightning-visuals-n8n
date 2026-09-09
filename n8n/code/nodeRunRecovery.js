// nodeRunRecovery.js — recovers a converged node's per-item context when the SAME node
// name can execute more than once within one n8n workflow execution.
//
// Bug (confirmed live, execution 12163, 2026-09-09 — see
// .planning/debug/uat-batch-review-row-reads-failed.md F5): a node with more than one
// INBOUND connection (e.g. "Enrichment Gate", fed separately by the email/linkedin/
// name/fetch-by-id/unmatchable lanes; "Company Gate", fed separately by the fetch-by-id
// and domain/name-search lanes) runs ONCE PER FIRING INBOUND EDGE, not once on a merged
// item array. n8n's own docs confirm `$('Node').all()` with no run index "returns the
// items of the node's most recent run" — so every later run of a node reading it BY
// NAME (required here because HTTP nodes replace $json — the reason these by-name reads
// exist at all) silently collapsed onto the SAME final run, losing every row from every
// earlier lane. A 4-row mixed batch (2 email, 2 no-email) lost both email rows this way.
//
// n8n's documented fix for "same run as the current node" is
// `$('Node').all(0, $runIndex)`. That alone is NOT sufficient here: a wave can be
// dropped ENTIRELY between the converged node and the reader (e.g. every row in one
// lane resolves `action === "skip"` and never reaches the provider chain at all — the
// "IF Name Searchable" false lane, or "IF Company Skip"'s true lane). A dropped wave
// still consumes one of the upstream node's run indices without ever producing a run of
// the reader, so a LATER wave's `$runIndex` would then point at the wrong (dropped)
// upstream run. This scans the upstream node's own runs in order, keeping only the ones
// that survive `keep`, and returns the surviving run at position `runIndex` — i.e. the
// reader's own `$runIndex`-th run always pairs with the reader's own `$runIndex`-th
// SURVIVING predecessor, regardless of how many runs were dropped in between.
//
// `all(nodeName, branchIndex, runIndex)` is injected (never n8n's ambient `$` read
// directly) so this stays a pure, Node-testable function — the n8n wrapper passes
// `(name, b, r) => $(name).all(b, r)`.
//
// Caveat (undocumented, so defended rather than assumed): n8n's docs do not say whether
// `.all(0, r)` throws or returns `[]` once `r` exceeds the node's real run count. Both
// are treated as "no more runs" here. That is safe for every node this helper reads
// (Enrichment Gate, Company Gate, ZoomInfo Token Gate/Company Token Gate) because each
// is a Code node that maps its OWN $input 1:1 — a REAL run is therefore never itself
// empty, so an empty batch can only mean "past the last run", not "a genuine empty run".
function recoverConvergedRun(all, nodeName, runIndex, keep, maxRuns) {
  const limit = maxRuns || 500;
  let matched = -1;
  for (let r = 0; r < limit; r += 1) {
    let batch;
    try {
      batch = all(nodeName, 0, r);
    } catch (e) {
      batch = null;
    }
    if (!batch || batch.length === 0) break; // past the last real run (throw or [])
    const surviving = batch.filter(keep);
    if (surviving.length === 0) continue; // this whole run was dropped upstream
    matched += 1;
    if (matched === runIndex) return surviving;
  }
  return [];
}

module.exports = { recoverConvergedRun };
