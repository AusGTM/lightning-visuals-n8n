// scoreEnrichment.js — pure-JS field-level best-of-breed scorer for n8n Code nodes.
//
// scoreCandidates(candidates, opts) groups common-shape candidates (from
// normalizeProviders.toCandidates) by canonical `field`, scores EACH candidate
//   value_score = wA·A + wR·R + wG·G + wT·T          (ENRICHMENT-WORKFLOW-PLAN.md §2)
// and returns the argmax per field with full provenance, plus a flat merge-ready
// winners map ({field: value}) that slots straight into mergeContacts.
//
//   A — accuracy   : candidate.accuracy (already provider-derived).
//   R — recency    : 1 - min(ageDays/staleCeiling, 1) from recencyDate.
//                    NO recencyDate -> neutral 0.5 (freshness unknown, not penalised).
//   G — agreement  : fraction of OTHER sources whose normalizedValue equals this one
//                    (cross-check / consensus). Single source -> 0.
//   T — source trust: base rank /100 (zoominfo .85, lusha .80, apollo .75). Tiebreaker.
//
// PURE + DETERMINISTIC: inject `opts.now` (ISO) — no Date.now in the scoring math.
// `opts.mode`: 'scored_all' (default) scores everything given; 'scored_cost_aware'
// scores only sources in `opts.calledSources` (caller owns the early-exit decision).

const DEFAULT_WEIGHTS = { wA: 0.45, wR: 0.2, wG: 0.25, wT: 0.1 };
const DEFAULT_TRUST = { zoominfo: 0.85, lusha: 0.8, apollo: 0.75 };
const DEFAULT_STALE_CEILING = 365;

function _ageDays(recencyDate, nowIso) {
  if (!recencyDate) return null;
  const then = Date.parse(recencyDate);
  const now = Date.parse(nowIso);
  if (Number.isNaN(then) || Number.isNaN(now)) return null;
  return (now - then) / 86400000;
}

function _recency(recencyDate, nowIso, staleCeiling) {
  const age = _ageDays(recencyDate, nowIso);
  if (age === null) return 0.5; // unknown freshness -> neutral
  const ceil = staleCeiling > 0 ? staleCeiling : DEFAULT_STALE_CEILING;
  return 1 - Math.min(age / ceil, 1);
}

function _eq(a, b) {
  if (a === null || a === undefined || b === null || b === undefined) return false;
  return String(a) === String(b);
}

function scoreCandidates(candidates, opts) {
  opts = opts || {};
  const w = Object.assign({}, DEFAULT_WEIGHTS, opts.weights || {});
  const trust = Object.assign({}, DEFAULT_TRUST, opts.trust || {});
  const staleCeilings = opts.staleCeilings || {};
  const nowIso = opts.now || new Date().toISOString();
  const mode = opts.mode || "scored_all";

  let pool = candidates || [];
  if (mode === "scored_cost_aware" && Array.isArray(opts.calledSources)) {
    const called = new Set(opts.calledSources.map((s) => String(s).toLowerCase()));
    pool = pool.filter((c) => called.has(String(c.source).toLowerCase()));
  }

  // Group by canonical field.
  const groups = {};
  for (const c of pool) {
    (groups[c.field] || (groups[c.field] = [])).push(c);
  }

  const best = {};
  const winners = {};

  for (const field of Object.keys(groups)) {
    const group = groups[field];
    const ceil = staleCeilings[field] || DEFAULT_STALE_CEILING;
    let top = null;

    for (const c of group) {
      // Agreement: OTHER candidates (distinct sources) whose normalizedValue matches.
      const agreedBy = [];
      for (const o of group) {
        if (o === c) continue;
        if (o.source === c.source) continue;
        if (_eq(o.normalizedValue, c.normalizedValue)) agreedBy.push(o.source);
      }
      const otherSources = new Set(group.filter((o) => o.source !== c.source).map((o) => o.source));
      const A = c.accuracy;
      const R = _recency(c.recencyDate, nowIso, ceil);
      const G = otherSources.size ? new Set(agreedBy).size / otherSources.size : 0;
      const T = trust[String(c.source).toLowerCase()] != null ? trust[String(c.source).toLowerCase()] : 0.6;
      const score = w.wA * A + w.wR * R + w.wG * G + w.wT * T;

      const cand = {
        field,
        value: c.value,
        normalizedValue: c.normalizedValue,
        source: c.source,
        score,
        components: { A, R, G, T },
        agreedBy: [...new Set(agreedBy)],
      };

      if (top === null || _beats(cand, top, trust)) top = cand;
    }

    best[field] = top;
    winners[field] = top.value;
  }

  return { best, winners };
}

// Deterministic tie-break: higher score, then higher trust, then source name.
function _beats(a, b, trust) {
  if (a.score !== b.score) return a.score > b.score;
  const ta = trust[String(a.source).toLowerCase()] || 0;
  const tb = trust[String(b.source).toLowerCase()] || 0;
  if (ta !== tb) return ta > tb;
  return String(a.source) < String(b.source);
}

module.exports = { scoreCandidates, DEFAULT_WEIGHTS, DEFAULT_TRUST };
