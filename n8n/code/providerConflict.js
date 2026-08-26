// n8n/code/providerConflict.js
//
// Shared cross-provider conflict predicate for the companies enrichment lane
// (gap-closure 58-06, T-58-26/§21.2). PURE and parameterized: takes the scored bundle
// (row.scored from scoreEnrichment.js's scoreCandidates output) and the field list to
// watch as ARGUMENTS -- the watched list is never a hardcoded constant inside this
// module. This is load-bearing for RO-2 (Phase 14): this module gets inlined into BOTH
// ENRICH_MERGE_CO (which watches the size fields too) and, from gap-closure 58-06 Task
// 2 onward, Judge Gate (which must NEVER see the size list) -- a single call-site-owned
// parameter is what keeps the size list out of Judge Gate's built jsCode by construction
// rather than by convention. Field-name-agnostic on purpose, same discipline as
// n8n/code/judge.js's computeEscalation.
//
// detectConflicts(scored, watchFields) -> per-field conflict records, same shape the
// original inline size watch-list loop in ENRICH_MERGE_CO produced:
//   { field, chosen, chosen_source, candidates }
// A conflict fires when 2+ distinct sources answered a watched field and NONE of them
// agree (best[f].agreedBy is empty) while sourcesByField[f] has more than one entry. A
// single source, or sources that agree on the normalized value, is never a conflict --
// mirrors scoreEnrichment.js's own G (agreement) component exactly, no new comparison
// logic invented here.
function detectConflicts(scored, watchFields) {
  const best = (scored && scored.best) || {};
  const sourcesByField = (scored && scored.sourcesByField) || {};
  const conflicts = [];
  for (const f of (watchFields || [])) {
    const b = best[f];
    if (!b) continue;
    const others = (b.agreedBy || []).length;
    const sources = sourcesByField[f];
    if (sources && sources.length > 1 && others === 0) {
      conflicts.push({ field: f, chosen: b.normalizedValue, chosen_source: b.source,
                        candidates: sources });
    }
  }
  return conflicts;
}

// groupConflicts(conflicts, groups) -> one record per group with at least one
// conflicted member field: { group, fields, conflicts }, where `conflicts` is the
// subset of the input conflict records belonging to that group's `fields`. A group with
// no conflicted member is omitted entirely -- this is what lets
// lv_country_region_normalized and native `country` be modelled as ONE disputed fact
// with two HubSpot serializations (config/escalation_policy.yaml's
// material_conflict_field_groups): a conflict on EITHER member field surfaces the WHOLE
// group here, so the caller can suppress both members under a single reason.
function groupConflicts(conflicts, groups) {
  const byField = new Map((conflicts || []).map((c) => [c.field, c]));
  const result = [];
  for (const g of (groups || [])) {
    const memberConflicts = (g.fields || []).map((f) => byField.get(f)).filter(Boolean);
    if (memberConflicts.length === 0) continue;
    result.push({ group: g.name, fields: g.fields, conflicts: memberConflicts });
  }
  return result;
}

module.exports = { detectConflicts, groupConflicts };
