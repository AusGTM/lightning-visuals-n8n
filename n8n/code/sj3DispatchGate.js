// n8n/code/sj3DispatchGate.js
//
// Phase 44 Plan 01 (GATE-01/D-01) — SJ-3 dispatch gate: annotates every polled row with
// a dispatch-or-drain routing decision. This module NEVER decides *whether* a write is
// permitted — it only routes rows the injected predicate has already judged. The
// permission predicate is injected (`opts.allows`) so the module is unit-testable in
// plain node without the baked write-safety constants — the same purity reviewApply.js
// and dedupeSweep.js already have.
//
// Contract (tests/n8n/sj3DispatchGate.test.mjs):
//   - every row comes back annotated, in input order, payload otherwise untouched;
//   - `sj3_dispatch` and `sj3_drain` are mutually exclusive on every row, always;
//   - a permitted row carries sj3_dispatch=true; a declined row carries sj3_drain=true;
//   - empty input returns an empty array, throws nothing.
function sj3Gate(rows, opts) {
  const allows = (opts && typeof opts.allows === "function") ? opts.allows : () => false;
  return (rows || []).map((row) => {
    const permitted = allows(row) === true;
    return { ...row, sj3_dispatch: permitted, sj3_drain: !permitted };
  });
}

module.exports = { sj3Gate };
