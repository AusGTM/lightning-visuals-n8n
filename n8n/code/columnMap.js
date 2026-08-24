// columnMap.js — pure-JS header remap for n8n Code nodes.
//
// Mirrors src/column_mapper.py + config/column_mapping.yaml: arbitrary source
// headers -> canonical HubSpot contact props via case-insensitive / whitespace-
// collapsed aliases; unmapped columns are dropped. requiredIdentity mirrors the
// column_mapping required_identity reject rule (email OR firstname+lastname+company).

// Embedded alias table (source of truth: config/column_mapping.yaml). Keys are
// already lowercased/whitespace-collapsed, matching _normHeader.
const ALIASES = {
  // email
  "email": "email",
  "email address": "email",
  "e-mail": "email",
  "e-mail address": "email",
  // firstname
  "firstname": "firstname",
  "first name": "firstname",
  "fname": "firstname",
  "given name": "firstname",
  // lastname
  "lastname": "lastname",
  "last name": "lastname",
  "surname": "lastname",
  // jobtitle
  "jobtitle": "jobtitle",
  "job title": "jobtitle",
  "title": "jobtitle",
  "position": "jobtitle",
  // linkedin_url
  "linkedin_url": "linkedin_url",
  "linkedin": "linkedin_url",
  "linkedin url": "linkedin_url",
  "li": "linkedin_url",
  "linkedin profile": "linkedin_url",
  // phone
  "phone": "phone",
  "mobile": "phone",
  "tel": "phone",
  // company
  "company": "company",
  "organization": "company",
  "organisation": "company",
  "account": "company",
  "org.": "company",
  // company_id — manual contact->company association override (2026-08-25). Rides the
  // row for Build Company Link; never written as a HubSpot contact property.
  "company_id": "company_id",
  "company id": "company_id",
  "hubspot company id": "company_id",
  "associated company id": "company_id",
  "associatedcompanyid": "company_id",
};

function _normHeader(header) {
  // Trim, collapse internal whitespace, lowercase — matches column_mapper._norm_header.
  return String(header).split(/\s+/).filter(Boolean).join(" ").toLowerCase();
}

// mapRow(rawRow, mapping?) — mapping optional; defaults to embedded ALIASES.
// Accepts either a full column_mapping object ({aliases:{...}}) or a bare alias map.
function mapRow(rawRow, mapping) {
  let aliases = ALIASES;
  if (mapping) aliases = mapping.aliases || mapping;
  const out = {};
  for (const key of Object.keys(rawRow || {})) {
    if (typeof key !== "string") continue; // malformed header -> skip, never throw
    const canonical = aliases[_normHeader(key)];
    if (canonical) out[canonical] = rawRow[key];
  }
  return out;
}

function _present(v) {
  return v !== null && v !== undefined && String(v).trim() !== "";
}

// requiredIdentity(row) — email OR (firstname AND lastname AND company).
function requiredIdentity(row) {
  if (!row) return false;
  if (_present(row.email)) return true;
  return _present(row.firstname) && _present(row.lastname) && _present(row.company);
}

module.exports = { mapRow, requiredIdentity, ALIASES };
