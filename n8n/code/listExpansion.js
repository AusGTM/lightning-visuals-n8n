// n8n/code/listExpansion.js — pure-JS HubSpot-list -> enrichment-events expansion.
//
// Phase 25 Plan 03 (INGEST-04, D-01/D-02/D-15). The plugin never holds a HubSpot token, so
// it hands the enrichment webhook a list identifier verbatim and n8n resolves it with the
// credential it already owns. This module is the pure half of that resolution: given the
// caller's body plus the two HubSpot responses, it returns either the SAME envelope shape
// `Parse HubSpot Event` already accepts, or a refusal carrying a plain-language reason.
// Pure, deterministic, no n8n globals — mirrors providerSelection.js, inlined into the
// Code node by the builder's inline() (Code nodes cannot require() siblings).
//
// expandListToEvents({ body, listResult, membershipsResult, maxRecords })
//   -> { events: [...], providers?: any, refused: false, reason: null }
//   -> { events: [],    refused: true,  reason: "<operator-facing sentence>" }
//
// IT REFUSES RATHER THAN TRUNCATING. Five ways a resolution can fail to produce a whole,
// enrichable record set, each with its own sentence and all of them with `events: []`:
//
//   1. A saved VIEW was named. HubSpot exposes no API for views, so a view is never
//      resolved against the LIST endpoint — a view name colliding with an unrelated list
//      name would enrich the wrong record set with NO error (25-RESEARCH.md Pitfall 2).
//      This is the recorded `refuse-and-redirect` decision (25-BLOCKERS.md, amendment #7).
//   2. The list name did not resolve (404, a 401/403 error item, or a body with no listId).
//   3. The membership body was unreadable, or the list has zero members. A zero-event
//      "success" is not a success: it would emit zero items into a `responseNode` webhook,
//      which returns NO response at all and hangs until Cloudflare 524s (D-22).
//   4. The membership page carried MORE ids than the ceiling.
//   5. The membership response carried a PAGING CURSOR — checked BEFORE the count and
//      refused even when the returned page is at or below the ceiling. This is the
//      cursor-follow requirement, discharged by refusal rather than by pagination: a
//      cursor means the read is a PAGE, not the list, and the single most repeated
//      failure in this milestone is a partial result impersonating a whole one (D-08,
//      D-20, D-22, D-23, D-33). Enumerating the remaining pages could not change the
//      outcome — the memberships endpoint pages at or below 102 members (live-probed
//      2026-07-31, 25-BLOCKERS.md) while the ceiling is derived from a ~100s response
//      window at ~36s/record, so a cursor ALWAYS implies "far more than the ceiling".
//      Following it would spend N requests to reach a refusal one request already proves.
//      ponytail: refuse-on-cursor, not paginate. Revisit only if the ceiling ever exceeds
//      a HubSpot membership page — it cannot while the response window bounds it.
//
// The provider selection is carried through UNCHANGED, including an explicitly empty
// selection: a list batch must burn exactly the providers the operator approved, no more
// (T-25-02). The key is copied only when the caller sent it, so an absent selection stays
// absent and `resolveEnabledProviders` resolves it to zero providers, fail-closed.
//
// Only record IDs cross this boundary. No HubSpot property value is read or emitted here
// (T-25-06).

// The exact operator-facing sentence recorded in 25-BLOCKERS.md as amendment #7, minus the
// document's markdown emphasis markers (this is an API refusal string, not a document).
// 25-04 uses the same words client-side.
const VIEW_REFUSAL =
  "I can't resolve a HubSpot view — HubSpot doesn't expose views through its API. " +
  "Save that view as a list in HubSpot and give me the list name, or paste the record IDs directly.";

// Accepts every spelling `Parse HubSpot Event`'s own normalizeObjectType() accepts, so a
// list envelope and a record-ID envelope agree on what an object type is.
const OBJECT_TYPE_IDS = {
  contact: "0-1", contacts: "0-1", "0-1": "0-1",
  company: "0-2", companies: "0-2", "0-2": "0-2",
};
const OBJECT_TYPE_BY_ID = { "0-1": "contacts", "0-2": "companies" };

function isPlainObject(value) {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function isNumber(value) {
  return typeof value === "number" && isFinite(value);
}

function normalizeObjectType(raw) {
  const key = String(raw == null ? "" : raw).toLowerCase().trim();
  return OBJECT_TYPE_BY_ID[OBJECT_TYPE_IDS[key]] || null;
}

function objectTypeId(raw) {
  const key = String(raw == null ? "" : raw).toLowerCase().trim();
  return OBJECT_TYPE_IDS[key] || null;
}

function refuse(reason) {
  return { events: [], refused: true, reason };
}

// The list-by-name 200 body nests the list under `list`; tolerate a flat body and any
// shape mismatch (an onError item, an error body, a 404) by returning null.
function extractListId(listResult) {
  if (!isPlainObject(listResult)) return null;
  const source = isPlainObject(listResult.list) ? listResult.list : listResult;
  const listId = source.listId;
  if (listId === undefined || listId === null || listId === "") return null;
  return String(listId);
}

function hasPagingCursor(membershipsResult) {
  const paging = isPlainObject(membershipsResult) ? membershipsResult.paging : null;
  const next = isPlainObject(paging) ? paging.next : null;
  return !!(isPlainObject(next) && next.after);
}

// Fail closed: one unusable row refuses the whole read rather than emitting a null
// objectId that would enrich nothing while reporting a record count.
function memberIds(results) {
  const ids = [];
  for (const row of results) {
    const raw = isPlainObject(row)
      ? (row.recordId !== undefined ? row.recordId : row.id)
      : row;
    if (raw === undefined || raw === null || raw === "") return null;
    ids.push(String(raw));
  }
  return ids;
}

function oversizeRefusal(name, maxRecords, detail) {
  return (
    `The list "${name}" is larger than this backend can enrich in one request — the ` +
    `limit is ${maxRecords} record(s) per request, measured against the ~100s webhook ` +
    `response ceiling. ${detail} Nothing was enriched. Send record IDs instead, in ` +
    `batches of ${maxRecords} or fewer.`
  );
}

function expandListToEvents(input) {
  const opts = isPlainObject(input) ? input : {};
  const body = isPlainObject(opts.body) ? opts.body : null;
  const maxRecords = isNumber(opts.maxRecords) ? opts.maxRecords : 0;

  if (!body) {
    return refuse("The enrichment request carried no readable body, so there was nothing to resolve.");
  }

  // Checked FIRST and never resolved against the list endpoint (Pitfall 2).
  if (body.view !== undefined && body.view !== null) {
    return refuse(VIEW_REFUSAL);
  }

  const spec = isPlainObject(body.list) ? body.list : null;
  const name = spec && typeof spec.name === "string" ? spec.name.trim() : "";
  if (!name) {
    return refuse(
      "The enrichment request named no list, so there was nothing to resolve. Give me a " +
      "HubSpot list name, or paste the record IDs directly."
    );
  }

  const objectType = normalizeObjectType(spec.objectType);
  if (!objectType) {
    return refuse(
      `I can't tell whether "${name}" is a contact list or a company list. Name the object ` +
      `type as "contacts" or "companies" and I'll resolve it.`
    );
  }

  if (!extractListId(opts.listResult)) {
    return refuse(
      `HubSpot has no ${objectType} list named "${name}", or it refused to read it. Nothing ` +
      `was enriched. Check the list name in HubSpot, or paste the record IDs directly.`
    );
  }

  const memberships = opts.membershipsResult;
  const results = isPlainObject(memberships) && Array.isArray(memberships.results)
    ? memberships.results
    : null;
  if (!results) {
    return refuse(
      `HubSpot returned no readable membership list for "${name}". Nothing was enriched.`
    );
  }
  if (results.length === 0) {
    return refuse(
      `The ${objectType} list "${name}" has no members, so there is nothing to enrich.`
    );
  }

  // Cursor before count: with a cursor the returned length is a lower bound, and reporting
  // it as the size would understate the list.
  if (hasPagingCursor(memberships)) {
    return refuse(oversizeRefusal(
      name, maxRecords,
      "HubSpot returned only the first page of its members, so the full list is larger than " +
      "one response and its true size is unknown from here."
    ));
  }

  const total = isPlainObject(memberships) ? memberships.total : undefined;
  if (results.length > maxRecords || (isNumber(total) && total > maxRecords)) {
    const size = isNumber(total) && total > results.length ? total : results.length;
    return refuse(oversizeRefusal(name, maxRecords, `It has ${size} member(s).`));
  }

  const ids = memberIds(results);
  if (!ids) {
    return refuse(
      `HubSpot returned a membership row for "${name}" with no usable record id. Nothing was ` +
      `enriched.`
    );
  }

  const out = {
    events: ids.map((objectId) => ({ objectId: objectId, objectType: objectType })),
    refused: false,
    reason: null,
  };
  // Carried through unchanged, and ONLY when the caller sent it (T-25-02).
  if (Object.prototype.hasOwnProperty.call(body, "providers")) {
    out.providers = body.providers;
  }
  return out;
}

module.exports = { expandListToEvents, normalizeObjectType, objectTypeId, VIEW_REFUSAL };
