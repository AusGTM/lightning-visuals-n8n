// pairCreateOutcome.js — pure identity join for the ingest lane's HubSpot Create outcome.
//
// "Create Carry Merge" (scripts/build_cloud_workflows.py) concatenates (append mode)
// two or three streams onto one array: the carried pre-write rows (Decide Action's own
// output for every create-routed row), the HubSpot Create HTTP node's SUCCESS response
// items, and (D-73-01) its ERROR response items when a create is rejected. Before this
// module the merge was `combineByPosition` — item i of the response array paired with
// item i of the carried-row array — which held only because the two arrays always had
// the SAME length and order. `onError: "continueErrorOutput"` breaks that: once ANY
// create in a batch fails, the success array shrinks and every response after the first
// gap pairs with the WRONG carried row (73-RESEARCH.md's Pitfall 0). Append mode plus
// this module's identity join replaces positional pairing with a join on each row's OWN
// identity, so a shrinking response set can never mis-associate a contact.
//
// Classification is by SHAPE, not an added marker — the three sources this merge ever
// sees are already structurally disjoint by construction:
//   - a carried row (Decide Action's own output) always carries a non-empty `action`;
//     no HubSpot HTTP response, success or error, ever has an `action` field (it is not
//     a valid HubSpot property and this code never sends one).
//   - a SUCCESS response is HubSpot's own `{id, properties, ...}` echo — `id` is never
//     present on a carried row (no top-level `id` field is ever stamped on one) and
//     HubSpot's own error bodies report a conflict in `message`, never a fresh `id`.
//   - anything left over (no `action`, no usable `id`) is an ERROR item.
//
// The join key is the SAME identity ladder columnMap.js's `requiredIdentity` encodes
// for CSV completeness (config/column_mapping.yaml's `required_identity.any_of`):
// email first, then firstname+lastname+company, then linkedin_url — casefolded and
// trimmed, computed identically on the carried row and the response side.

function _norm(v) {
  return String(v == null ? "" : v).trim().toLowerCase();
}

function _emailOf(row) {
  row = row || {};
  const props = row.properties || {};
  return _norm(row.email || props.email);
}

function _nameKeyOf(row) {
  row = row || {};
  const props = row.properties || {};
  const first = _norm(row.firstname || props.firstname);
  const last = _norm(row.lastname || props.lastname);
  const company = _norm(row.company || props.company);
  if (first && last && company) return `${first}|${last}|${company}`;
  return "";
}

function _linkedinOf(row) {
  row = row || {};
  const props = row.properties || {};
  const raw = row.linkedin_url || props.linkedin_url || props.lv_linkedin_url || props.hs_linkedin_url;
  return _norm(raw);
}

// identityKey(row) -> string | null. Never a guess: returns null when no rung of the
// ladder resolves, so the caller can refuse the pairing instead of matching on nothing.
function identityKey(row) {
  const email = _emailOf(row);
  if (email) return `email:${email}`;
  const nameKey = _nameKeyOf(row);
  if (nameKey) return `name:${nameKey}`;
  const li = _linkedinOf(row);
  if (li) return `linkedin:${li}`;
  return null;
}

function _isCarriedRow(row) {
  return typeof (row && row.action) === "string" && row.action.length > 0;
}

function _isSuccessResponse(row) {
  return Boolean(row) && row.id !== undefined && row.id !== null && row.id !== "";
}

// pairCreateOutcome(items) — `items` already unwrapped to plain json objects (no
// `{json: ...}` envelopes). Returns one item per carried row, in the carried rows' own
// order, each stamped `create_outcome`:
//   "success" — paired with the response sharing its identity key. The response's own
//               fields are re-attached with the carried row's fields winning any clash
//               (`{...match, ...row}`) — the SAME carried-row-wins semantics the retired
//               combineByPosition carry-merge used (merge_node's own `resolveClash:
//               "preferLast"`, carried row wired last) — so `id` survives (the response
//               is the only side that has one) while the row's own email/company_id/
//               write_request/properties (the request that was actually sent) win.
//   "error"   — paired with a create ERROR item the same way, plus `create_error`
//               carrying the raw error item for a caller (Build Create Failure Row) to
//               classify into a refusal reason.
//   "none"    — no response of either kind ever arrived for this row's identity key.
//   "refused" — the row's own identity key is uncomputable, or it collides with
//               another carried row's key, or more than one response shares the key.
//               Never guessed — `create_outcome_reason` names which.
function pairCreateOutcome(items) {
  const carried = [];
  const responses = [];
  for (const row of items || []) {
    if (!row) continue;
    if (_isCarriedRow(row)) carried.push(row);
    else if (_isSuccessResponse(row)) responses.push({ row, outcome: "success" });
    else responses.push({ row, outcome: "error" });
  }

  const carriedKeys = carried.map((row) => identityKey(row));
  const keyCounts = new Map();
  for (const key of carriedKeys) {
    if (key === null) continue;
    keyCounts.set(key, (keyCounts.get(key) || 0) + 1);
  }

  const responsesByKey = new Map();
  for (const resp of responses) {
    const key = identityKey(resp.row);
    if (key === null) continue; // an uncomputable response key can never be joined
    if (!responsesByKey.has(key)) responsesByKey.set(key, []);
    responsesByKey.get(key).push(resp);
  }

  return carried.map((row, i) => {
    const key = carriedKeys[i];
    if (key === null) {
      return { ...row, create_outcome: "refused",
               create_outcome_reason: "no computable identity key" };
    }
    if (keyCounts.get(key) > 1) {
      return { ...row, create_outcome: "refused",
               create_outcome_reason: "identity key matches more than one carried row" };
    }
    const matches = responsesByKey.get(key) || [];
    if (matches.length === 0) {
      return { ...row, create_outcome: "none" };
    }
    if (matches.length > 1) {
      return { ...row, create_outcome: "refused",
               create_outcome_reason: "identity key matches more than one create response" };
    }
    const [match] = matches;
    if (match.outcome === "success") {
      return { ...match.row, ...row, create_outcome: "success" };
    }
    return { ...row, create_outcome: "error", create_error: match.row };
  });
}

module.exports = { pairCreateOutcome, identityKey };
