// n8n/code/sj3DispatchGate.js
//
// Phase 44 Plan 01 (GATE-01/D-01) — SJ-3 dispatch gate: annotates every polled row with
// a dispatch-or-drain routing decision. This module NEVER decides *whether* a write is
// permitted — it only routes rows the injected predicate has already judged. The
// permission predicate is injected (`opts.allows`) so the module is unit-testable in
// plain node without the baked write-safety constants — the same purity reviewApply.js
// and dedupeSweep.js already have.
//
// Phase 44 Plan 02 (CAP-01/CAP-02/D-09) — `opts.cap` bounds how many permitted rows one
// tick may dispatch, and every row carries the same `sj3_tick` summary object so a
// downstream node can report what the gate decided (found vs dispatched — a capped tick
// must never read as "processed everything").
//
// Contract (tests/n8n/sj3DispatchGate.test.mjs):
//   - every row comes back annotated, in input order, payload otherwise untouched;
//   - `sj3_dispatch` and `sj3_drain` are mutually exclusive on a permitted/declined row;
//   - a permitted row within the cap carries sj3_dispatch=true; a declined row carries
//     sj3_drain=true;
//   - a permitted row BEYOND the cap is DEFERRED: sj3_dispatch=false AND sj3_drain=false;
//   - the cap counts only permitted rows, in input order (the deferred set is the tail
//     of the permitted stream, never an arbitrary subset); declined rows drain regardless
//     of position and never consume cap budget;
//   - every row carries sj3_tick = {found, permitted, dispatched, declined, deferred,
//     cap, outcome} with found === permitted + declined and
//     permitted === dispatched + deferred, outcome one of dispatched|gate_closed|
//     capped_partial;
//   - empty input returns an empty array, throws nothing.
function sj3Gate(rows, opts) {
  const allows = (opts && typeof opts.allows === "function") ? opts.allows : () => false;
  // Cap semantics: absent -> uncapped; present but not a positive integer -> 0, i.e.
  // fail CLOSED (defer everything permitted). Deferral preserves the work — flags stay
  // set, the next tick retries — and stays visible via outcome=capped_partial.
  let cap = Infinity;
  if (opts && opts.cap !== undefined) {
    cap = (Number.isInteger(opts.cap) && opts.cap > 0) ? opts.cap : 0;
  }
  let dispatched = 0, declined = 0, deferred = 0;
  const annotated = (rows || []).map((row) => {
    const permitted = allows(row) === true;
    if (!permitted) {
      declined += 1;
      return { ...row, sj3_dispatch: false, sj3_drain: true };
    }
    if (dispatched < cap) {
      dispatched += 1;
      return { ...row, sj3_dispatch: true, sj3_drain: false };
    }
    // D-09: a permitted row beyond the cap is DEFERRED work, not DECLINED work. It keeps
    // its flag (sj3_dispatch=false so this tick does not spend on it, sj3_drain=false so
    // the drain never touches it) and the next tick picks it up. Draining overflow would
    // be exactly the silent truncation CAP-02 forbids.
    deferred += 1;
    return { ...row, sj3_dispatch: false, sj3_drain: false };
  });
  const found = annotated.length;
  const permitted = dispatched + deferred;
  if (found !== permitted + declined || permitted !== dispatched + deferred) {
    throw new Error(
      "sj3Gate invariant violated: found=" + found + " permitted=" + permitted
      + " dispatched=" + dispatched + " declined=" + declined + " deferred=" + deferred);
  }
  const outcome = deferred > 0 ? "capped_partial"
    : (permitted === 0 && found > 0 ? "gate_closed" : "dispatched");
  // Echo the EFFECTIVE cap (what the gate actually enforced), not the raw opt — an
  // invalid opt reporting its own value while behaving as 0 would be a small lie.
  const sj3_tick = {
    found, permitted, dispatched, declined, deferred,
    cap: cap === Infinity ? null : cap, outcome,
  };
  return annotated.map((row) => ({ ...row, sj3_tick }));
}

module.exports = { sj3Gate };
