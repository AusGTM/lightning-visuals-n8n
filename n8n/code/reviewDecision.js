// reviewDecision.js — pure-JS decision-to-property-patch for the SYNCHRONOUS
// `hubspot/review/decision` endpoint (Phase 30 Plan 02, D-08e).
//
// Sibling of reviewApply.js, not a replacement for it. reviewApply is the compare-and-set
// APPLY engine (approve -> promote the held candidate -> clear the flags) that the
// 15-minute backstop loop runs; this module serves the operator-driven endpoint and, on
// approve, CALLS that same engine rather than re-implementing it (D-05/D-08d/D-15). The
// backstop loop is untouched and still runs — this is a second path, not a replacement.
//
// CONSUMER CONTRACT: `Build Review Decision` (scripts/build_cloud_workflows.py) calls
//
//   buildReviewDecision({ objectType, decision, reason, reviewedBy, row, nowIso, writeAllowed })
//     -> { properties, outcome, message }
//
// where `row` is the freshly-refetched HubSpot record already flattened by
// `Review Extract Record` ({ ...record.properties, hs_object_id, record_found }), and
// `properties` is put straight onto the row for the shared credential-bound PATCH node.
// `outcome` is one of:
//   rejected | applied | stale | no_candidate | not_flagged | refused | not_allowlisted.
//
// `writeAllowed` (Phase 31 Plan 02, BUG 30): the wrapper's own `_writeSafetyAllows("review",
// ...)` verdict, computed from the SAME baked constants the committed write gate reads,
// passed in so this module can answer an explicit refusal BEFORE the gate silently drops
// the row. Only the literal `false` refuses — omitted (every existing caller, every
// existing test) behaves exactly as before this phase.
//
// D-10 / REVIEW-05 — THE LOAD-BEARING RULE: a rejection RECORDS THE REASON AND NOTHING
// ELSE. It never clears lv_enrichment_needs_review or lv_icp_needs_review, never blanks
// lv_enrichment_review_candidate_json, and never stamps a reviewed-at. The record stays in
// the queue WITH a recorded decision. "Clear the flag for consistency" is precisely the
// silent de-queueing REVIEW-05 forbids, so the rejection branch is kept literally minimal:
// build the one-key patch and return.
//
// FAIL-CLOSED: never throws, never does I/O, requires nothing outside n8n/code/. Anything
// unrecognised is `refused` with EMPTY properties.
//
// ENUM GUARD (Phase 31, BUG 28/29, REVIEW-05): on approve, reviewApply also refuses any
// held field whose value HubSpot's enum will not accept (n8n/code/hubspotEnums.js). That
// refusal reuses the SAME `refused` outcome word and EMPTY properties, so the wrapper's
// dry_run resolution treats it exactly like every other non-writing outcome — the preview
// and the real submit return the identical refusal, naming the property and the value.
//

// CONTACTS (rewritten 2026-08-27, Phase 54 Plan 03, OP-54-03/OP-54-04 — operator decision
// `engine-only`, recorded in 54-03-SUMMARY.md): approve now resolves to a real HubSpot write
// for a contact exactly as it does for a company — `approve` never means two different
// things across object types. reviewApply took a third parameter this same date (a field
// policy) so ONE engine runs the SAME compare-and-set, staleness and enum guards keyed on
// either DEFAULT_COMPANY_POLICY or DEFAULT_CONTACT_POLICY, rather than a second engine.
//
// The finding that makes the contacts write a clear-only write in practice, not a fork in
// the code: `lv_enrichment_review_candidate_json` has exactly one producer in this repo —
// the COMPANIES enrichment lane's `Decide Company Action` (ENRICH_DECIDE_CO_CLOUD). The
// contacts lane (scripts/build_cloud_workflows.py:1569-1593) flags a contact only when a
// decision is BOTH a promote AND carries the human-review status, and it writes that value
// in the SAME PATCH as the flag — deliberately never staging a candidate, precisely so the
// apply lane will not re-apply an already-live value. So every contact that reaches the
// review queue today holds NO candidate: this module's held-candidate branch below reuses
// the SAME engine and policy selection a contacts candidate would need, and is proven by
// node tests driving a synthetic candidate (no live producer exists to prove it against a
// real record — see 54-03-SUMMARY.md's stated residual). The no-candidate branch is what
// every live contact hits: it clears the queue, stamps who decided and when, and says so —
// an explicit operator decision (D-10 / REVIEW-05: reject still clears nothing), not a
// silent de-queue.

const { reviewApply } = require("./reviewApply");
const { DEFAULT_COMPANY_POLICY, stableStringify } = require("./mergeCompanies");
const { DEFAULT_CONTACT_POLICY } = require("./mergeContacts");

// The `lv_`-prefixed review family (config/hubspot_properties.yaml). The generic
// unprefixed names in the root CLAUDE.md do not exist in this deployment (30 D-08c).
const P_NEEDS_REVIEW = "lv_enrichment_needs_review";
const P_ICP_NEEDS_REVIEW = "lv_icp_needs_review";
const P_REVIEW_REASON = "lv_enrichment_review_reason";
const P_CANDIDATE_JSON = "lv_enrichment_review_candidate_json";
// Named for the same reason the two flags above are: so the D-10 guarantee reads as an
// explicit non-write of a known property rather than an accidental omission. Only the
// approve branch writes reviewed-by; reviewed-at is written by reviewApply's OWN clear
// patch, so this module never stamps it (stamping it twice is how the two timestamps
// start disagreeing).
const P_REVIEWED_BY = "lv_enrichment_reviewed_by";
// The companies provenance blob (30 D-08a): ONE JSON object per record keyed by field,
// NOT a flat `<field>_source` family — that convention does not exist in this deployment.
const P_PROVENANCE = "lv_enrichment_provenance";
// The contacts provenance blob (Phase 15) — a DIFFERENT property from the companies one
// (D-08a); a contact's approve overlay must never write into the companies blob.
const P_CONTACT_PROVENANCE = "lv_contact_enrichment_provenance";

// HubSpot's own textarea ceiling — the same [:60000] cap merge_policy.py and the
// enrichment wrapper apply to every JSON blob they stage.
const MAX_TEXT = 60000;
// HubSpot single-line-text ceiling, for the operator label.
const MAX_SHORT_TEXT = 255;

// config/source_registry.yaml: `human` is a registered source, type reviewer,
// trust_rank 100, can_promote_directly true. `human_approved` is the registered
// validation status. Neither is invented here.
const HUMAN_SOURCE = "human";
const HUMAN_STATUS = "human_approved";
const HUMAN_CONFIDENCE = 100;

// Ownership classes that a review decision may never write, whatever a candidate says.
const PROTECTED_CLASSES = ["manual_protected", "review_required"];

// HubSpot returns booleancheckbox values as the STRINGS "true"/"false", so a bare
// truthiness test would read "false" as flagged.
function _truthy(v) {
  if (v === true) return true;
  if (typeof v === "string") return v.trim().toLowerCase() === "true";
  return false;
}

// Parse the existing provenance blob. A blob that cannot be read degrades to EMPTY and
// says so — never throws, and never silently pretends the history was empty: the caller
// puts that fact in the operator's message, because this write replaces the whole blob.
function _parseProvenance(raw) {
  if (raw === undefined || raw === null || String(raw).trim() === "") {
    return { entries: {}, unreadable: false };
  }
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (e) {
    return { entries: {}, unreadable: true };
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    return { entries: {}, unreadable: true };
  }
  return { entries: parsed, unreadable: false };
}

// buildHumanProvenance({ existingJson, applied, reason, verifiedAt })
//   -> { json, entries, unreadable }
//
// An ADDITIVE, field-keyed overlay onto the existing blob (D-08b): every entry for a field
// this decision did not touch is carried through byte-identically, and only the approved
// fields get a new entry. Re-serialized with mergeCompanies' own stableStringify so the
// blob stays byte-comparable with the Python oracle (src/merge_policy.py's
// serialize_provenance) and with every other writer of this property.
//
// The entry extends the deployed shape with exactly two additive flat keys — `reason` (the
// operator's text, REVIEW-04) and `superseded_source` (what the machine had said, so a
// human decision does not erase the attribution it replaced). It carries NO
// model-attribution key: the deployed shape has never had one and inventing it here would
// fork the shape from the oracle.
//
// Deliberately NOT truncated at MAX_TEXT, unlike the enrichment producer's blob write: a
// JSON blob cut mid-token is unparseable, so truncating would silently destroy the audit
// history on the NEXT approval. An over-long blob is rejected loudly by HubSpot instead.
function buildHumanProvenance(input) {
  const inp = (input && typeof input === "object") ? input : {};
  const applied = (inp.applied && typeof inp.applied === "object" && !Array.isArray(inp.applied))
    ? inp.applied : {};
  const reason = typeof inp.reason === "string" ? inp.reason : "";
  const verifiedAt = (typeof inp.verifiedAt === "string" && inp.verifiedAt)
    ? inp.verifiedAt : new Date().toISOString();

  const parsed = _parseProvenance(inp.existingJson);
  const merged = {};
  for (const field of Object.keys(parsed.entries)) merged[field] = parsed.entries[field];

  for (const field of Object.keys(applied)) {
    const prior = parsed.entries[field];
    merged[field] = {
      source: HUMAN_SOURCE,
      confidence: HUMAN_CONFIDENCE,
      verified_at: verifiedAt,
      validation_status: HUMAN_STATUS,
      value: applied[field],
      reason,
      superseded_source: (prior && typeof prior === "object" && typeof prior.source === "string")
        ? prior.source : "",
    };
  }

  return { json: stableStringify(merged), entries: merged, unreadable: parsed.unreadable };
}

function buildReviewDecision(input) {
  const inp = (input && typeof input === "object") ? input : {};
  const refused = (message) => ({ properties: {}, outcome: "refused", message });

  const row = inp.row;
  if (!row || typeof row !== "object" || Array.isArray(row)) {
    return refused("no record to decide on");
  }
  if (row.record_found === false || row.hs_object_id === undefined
      || row.hs_object_id === null || row.hs_object_id === "") {
    return refused("record not found");
  }

  // D-09: a decision without a reason is still a decision, so absent reads as empty. A
  // reason of the WRONG TYPE is a malformed request, not an empty one.
  let reason = inp.reason;
  if (reason === undefined || reason === null) reason = "";
  if (typeof reason !== "string") return refused("reason must be text");
  if (reason.length > MAX_TEXT) reason = reason.slice(0, MAX_TEXT);

  if (inp.decision !== "approve" && inp.decision !== "reject") {
    return refused("unknown decision " + JSON.stringify(inp.decision)
                   + ' — expected "approve" or "reject"');
  }

  // Flagged the way the queue itself defines flagged: either review flag set, or a held
  // candidate. "[]" is reviewApply's own empty default, so it is not a candidate.
  const rawCandidate = row[P_CANDIDATE_JSON];
  const candidate = (rawCandidate === undefined || rawCandidate === null)
    ? "" : String(rawCandidate).trim();
  const held = (candidate !== "" && candidate !== "[]") ? candidate : "";
  const flagged = _truthy(row[P_NEEDS_REVIEW]) || _truthy(row[P_ICP_NEEDS_REVIEW]) || held !== "";
  if (!flagged) {
    return {
      properties: {}, outcome: "not_flagged",
      message: "record is not in the review queue — nothing to decide",
    };
  }

  // ALLOWLIST GUARD (Phase 31 Plan 02, BUG 30): checked here, BEFORE the reject branch, so
  // a reject and an approve refuse IDENTICALLY when the record is not permitted — the
  // committed write gate drops both the same way, and an endpoint that answered `rejected`
  // for a write the gate would silently drop would be the same lie BUG 29 closed for
  // approve. `not_allowlisted` is a distinct outcome from `refused`: never collapse them.
  if (inp.writeAllowed === false) {
    return {
      properties: {}, outcome: "not_allowlisted",
      message: "this record is not on the backend's TEST_RECORD_* allowlist, so nothing was "
        + "sent to HubSpot and the record is unchanged — an administrator adds records to "
        + "that allowlist at deploy time",
    };
  }

  if (inp.decision === "reject") {
    return {
      properties: { [P_REVIEW_REASON]: reason },
      outcome: "rejected",
      message: "rejection reason recorded; the record stays in the review queue",
    };
  }

  // ---- approve --------------------------------------------------------------------
  const nothingToApply = (message) => ({ properties: {}, outcome: "no_candidate", message });

  const isContact = inp.objectType === "contacts";
  const policy = isContact ? DEFAULT_CONTACT_POLICY : DEFAULT_COMPANY_POLICY;
  const provenanceProp = isContact ? P_CONTACT_PROVENANCE : P_PROVENANCE;

  // verifiedAt and reviewedBy are computed ONCE, above every branch that might stamp them,
  // so one response can never carry two clocks or duplicate the trim/slice logic (54-03).
  const verifiedAt = (typeof inp.nowIso === "string" && inp.nowIso)
    ? inp.nowIso : new Date().toISOString();
  const reviewedByLabel = typeof inp.reviewedBy === "string" ? inp.reviewedBy.trim() : "";

  if (held === "") {
    if (isContact) {
      // Every contact reaching the queue today hits this branch (see the module header):
      // its enriched value is already live, written by the permissive contact lane in the
      // same PATCH as the flag. Approve is still a real HubSpot write — it clears the
      // queue and stamps who decided and when — it just has nothing to promote, because
      // nothing was withheld. All seven properties below are confirmed present on the live
      // contacts object (54-CONTACTS-PROPERTY-CHECK.md, Task 1), so none is narrowed here.
      const properties = {
        lv_enrichment_needs_review: "false",
        lv_enrichment_review_approved: "false",
        lv_enrichment_review_reason: "",
        lv_enrichment_review_candidate_json: "",
        lv_enrichment_reviewed_at: verifiedAt,
      };
      if (reviewedByLabel !== "") properties[P_REVIEWED_BY] = reviewedByLabel.slice(0, MAX_SHORT_TEXT);
      return {
        properties, outcome: "applied",
        message: "acknowledged — this contact's value was already written by the permissive "
          + "contact enrichment lane at the moment it was flagged, so no field was promoted "
          + "because none was withheld; the review flag is cleared and the decision is "
          + "recorded",
      };
    }
    return nothingToApply(
      "this record is in the review queue but holds no candidate values to approve — "
      + "nothing was written and it stays queued");
  }

  // THE non-clobber authority. Its compare-and-set is all-or-nothing: if any held field's
  // frozen baseline disagrees with the live record, it applies nothing and reports stale.
  // `policy` selects DEFAULT_CONTACT_POLICY for a contact and DEFAULT_COMPANY_POLICY for a
  // company (Phase 54 Plan 03) — one engine, two policies, never a second compare-and-set.
  const applied = reviewApply(held, row, policy);
  if (applied.stale) {
    return {
      properties: {}, outcome: "stale",
      message: "the record changed since this candidate was created, so nothing was "
             + "written and it stays queued — " + applied.reason,
    };
  }
  // ENUM GUARD (Phase 31, BUG 28/29, REVIEW-05): reviewApply refused one or more held
  // fields because their value is not one HubSpot's enum accepts. Reuse the EXISTING
  // `refused` outcome word (the client already treats it as non-writing) rather than
  // inventing a second one. `properties` stays EMPTY here, so the wrapper's `hasWrite`
  // below is false and `dry_run` resolves true regardless of the caller's request — the
  // row routes straight to `Build Review Response` on BOTH the preview and the real
  // submit, which is what makes them return the identical refusal (BUG 29's fix).
  if (applied.invalid && applied.invalid.length > 0) {
    const message = "one or more fields hold a value HubSpot would refuse, so nothing was "
      + "written and the record stays queued — "
      + applied.invalid.map((i) => i.reason).join(" ");
    return { properties: {}, outcome: "refused", message };
  }
  // reviewApply's fail-closed path: an unreadable candidate yields empty patches with a
  // reason. Its clear patch is never empty on a real apply, so an empty one here means the
  // candidate could not be read — and clearing the queue on that basis would de-queue a
  // record with nothing written (REVIEW-05).
  if (Object.keys(applied.clearPatch).length === 0) {
    return nothingToApply(
      "the held candidate could not be read (" + applied.reason + ") — nothing was written "
      + "and the record stays queued");
  }

  // D-12: reviewApply's allowlist is the set of policy KEYS, and `domain` is one of them
  // with class manual_protected — so membership alone does not exclude it, and a stale or
  // hand-edited candidate naming it would otherwise reach the patch. Consult the class on
  // the SAME policy object the engine was given (T-54-11) — for a contact that is
  // DEFAULT_CONTACT_POLICY, never DEFAULT_COMPANY_POLICY — the existing authority, not a
  // second policy table (D-05/D-07).
  const canonical = {};
  const withheld = [];
  for (const field of Object.keys(applied.canonicalPatch)) {
    const fieldPolicy = policy[field];
    if (fieldPolicy && PROTECTED_CLASSES.indexOf(fieldPolicy.class) !== -1) {
      withheld.push(field);
      continue;
    }
    canonical[field] = applied.canonicalPatch[field];
  }

  const provenance = buildHumanProvenance({
    existingJson: row[provenanceProp], applied: canonical, reason, verifiedAt,
  });

  const properties = { ...canonical, ...applied.clearPatch, [provenanceProp]: provenance.json };

  // Only ever WRITTEN, never blanked: an empty or wrong-typed label is omitted, because
  // writing "" would erase a reviewer HubSpot already holds.
  if (reviewedByLabel !== "") properties[P_REVIEWED_BY] = reviewedByLabel.slice(0, MAX_SHORT_TEXT);

  const applies = Object.keys(canonical);
  let message = applies.length
    ? "applied " + applies.length + " field(s) as a human decision: " + applies.join(", ")
    : "no field was eligible to apply, but the record has left the queue with a recorded "
      + "decision";
  if (withheld.length) {
    message += "; withheld as protected by field policy: " + withheld.join(", ");
  }
  if (provenance.unreadable) {
    message += "; the record's previous provenance blob could not be read and was replaced "
             + "with this decision's entries only";
  }

  return { properties, outcome: "applied", message };
}

module.exports = { buildReviewDecision, buildHumanProvenance };
