// companyLink.js — contact -> company resolution for the ingest lane.
//
// A contact must never land in HubSpot unassociated (operator ruling, 2026-08-25). This
// module answers ONE question per row: which company record does this contact belong to?
// It resolves, it never creates — an unresolved row is HELD for review, because a junk
// company shell is worse than a held row, and an existing company must never be
// duplicated (the company lane already dedupes on `domain`; this keeps ingest honest to
// the same anchor).
//
// Resolution order, strongest first:
//   1. manual  — the operator named the company id on the row itself (`company_id`).
//   2. domain  — the contact's email domain matched a company's `domain` EXACTLY.
//   3. name    — the row's company name matched a company's `name` EXACTLY.
//
// ponytail: name matching is exact-EQ only. CONTAINS_TOKEN would raise the hit rate and
// mis-associate "Racing Victoria" onto "Racing Victoria Foundation" — a wrong association
// is silent and worse than the hold lane it would bypass. Upgrade path if hit rate hurts:
// a candidate-list return the operator confirms, the way preingest confirms matches.
//
// NO npm, dependency-free — this module is inline()'d verbatim into n8n Code nodes.

// Free/consumer mail domains: an @gmail.com address says nothing about the employer, and
// searching companies for domain="gmail.com" would associate every such contact onto one
// arbitrary record. AU ISP domains included — they are the local shape of the same trap.
const FREEMAIL_DOMAINS = new Set([
  "gmail.com", "googlemail.com", "outlook.com", "outlook.com.au", "hotmail.com",
  "hotmail.com.au", "live.com", "live.com.au", "msn.com", "yahoo.com", "yahoo.com.au",
  "ymail.com", "icloud.com", "me.com", "mac.com", "aol.com", "protonmail.com", "proton.me",
  "gmx.com", "mail.com", "zoho.com",
  // AU consumer ISPs
  "bigpond.com", "bigpond.net.au", "bigpond.com.au", "optusnet.com.au", "iinet.net.au",
  "tpg.com.au", "internode.on.net", "westnet.com.au", "dodo.com.au", "iprimus.com.au",
  "exemail.com.au", "ozemail.com.au",
]);

// Hosts that are somebody's PROFILE PAGE, never a company's own domain. Found live
// 2026-08-25 during the Phase 53 operator walk: an operator with only a LinkedIn URL is the
// normal case, and the naive host extraction turned
// `linkedin.com/company/futsal-australia` into the domain `linkedin.com`. That would search
// HubSpot for domain=linkedin.com, find nothing, create a company whose domain IS
// linkedin.com — and then every later LinkedIn-sourced company would MATCH that one poisoned
// record. One bad row swallowing every future company, silently.
//
// These are not the same thing as FREEMAIL_DOMAINS (a personal mailbox); they are hosts where
// a URL identifies a page ABOUT a company rather than the company's own site. Both are
// unusable as a company domain, for different reasons, so both are refused here.
const NOT_A_COMPANY_DOMAIN = new Set([
  "linkedin.com", "lnkd.in", "facebook.com", "fb.com", "instagram.com", "twitter.com",
  "x.com", "youtube.com", "youtu.be", "tiktok.com", "threads.net", "medium.com",
  "crunchbase.com", "wikipedia.org", "en.wikipedia.org", "bloomberg.com", "zoominfo.com",
  "apollo.io", "abn.business.gov.au", "linktr.ee", "about.me", "sites.google.com",
  "wixsite.com", "squarespace.com", "godaddysites.com",
]);

// Same normalisation the companies lane's Build Company Identity applies, so a domain
// resolved here and a domain the company lane stored are the same string. Returns null for
// anything that cannot BE a company domain — the caller then falls through to the exact-name
// match rather than resolving against a host that identifies no company.
function cleanCompanyDomain(raw) {
  if (!raw) return null;
  let d = String(raw).trim().toLowerCase();
  d = d.replace(/^https?:\/\//, "").replace(/^www\./, "").split("/")[0].split("?")[0];
  if (!d) return null;
  if (NOT_A_COMPANY_DOMAIN.has(d)) return null;
  if (FREEMAIL_DOMAINS.has(d)) return null;
  return d;
}

function emailDomain(email) {
  const e = String(email || "").trim().toLowerCase();
  if (!e || e.indexOf("@") === -1) return null;
  const d = e.split("@").pop();
  return d || null;
}

// The domain to search companies by, or null when the row gives no usable one.
// An explicit column wins; otherwise the email domain, unless it is freemail.
function companyDomainForRow(row) {
  const explicit = cleanCompanyDomain((row || {}).company_domain || (row || {}).website);
  if (explicit) return explicit;
  const d = emailDomain((row || {}).email_normalized || (row || {}).email);
  if (!d || FREEMAIL_DOMAINS.has(d)) return null;
  return d;
}

function companyNameForRow(row) {
  const n = String(((row || {}).company) || "").trim();
  return n || null;
}

// HubSpot CRM v3 search envelope -> [{id, properties}]. Tolerates an error item (the
// search nodes run with onError: continueRegularOutput) by returning [].
function searchResults(response) {
  const res = (response && response.json) || response || {};
  if (res.error || (res.json && res.json.error)) return [];
  const results = res.results;
  if (!Array.isArray(results)) return [];
  return results.filter((r) => r && r.id);
}

function domainMatchId(response, domain) {
  if (!domain) return null;
  const wanted = String(domain).toLowerCase();
  for (const r of searchResults(response)) {
    const got = cleanCompanyDomain((r.properties || {}).domain);
    if (got && got === wanted) return String(r.id);
  }
  return null;
}

function nameMatchId(response, name) {
  if (!name) return null;
  const wanted = String(name).trim().toLowerCase();
  const hits = searchResults(response).filter(
    (r) => String((r.properties || {}).name || "").trim().toLowerCase() === wanted
  );
  // Two companies with the identical name is an ambiguity, not a match — hold it.
  if (hits.length !== 1) return null;
  return String(hits[0].id);
}

// The one entry point the n8n node calls. `row` is the ingest row; the two responses are
// the domain-search and name-search HTTP node outputs for THAT row.
function resolveCompanyLink(row, domainResponse, nameResponse) {
  const company_domain = companyDomainForRow(row);
  const company_name = companyNameForRow(row);
  const manual = String(((row || {}).company_id) || "").trim();
  if (manual) {
    return {
      company_id: manual,
      company_match: "manual",
      company_domain,
      company_name,
      company_hold_reason: null,
    };
  }
  const byDomain = domainMatchId(domainResponse, company_domain);
  if (byDomain) {
    return { company_id: byDomain, company_match: "domain", company_domain, company_name,
             company_hold_reason: null };
  }
  const byName = nameMatchId(nameResponse, company_name);
  if (byName) {
    return { company_id: byName, company_match: "name", company_domain, company_name,
             company_hold_reason: null };
  }
  let reason;
  if (!company_domain && !company_name) {
    reason = "no company domain or name on the row — nothing to match a company on";
  } else {
    const tried = [];
    if (company_domain) tried.push("domain " + company_domain);
    if (company_name) tried.push("name \"" + company_name + "\"");
    reason = "no company in HubSpot matched " + tried.join(" or ") +
             " — create or enrich the company first, or name its record id on the row";
  }
  return { company_id: null, company_match: null, company_domain, company_name,
           company_hold_reason: reason };
}

// v4 default association: HubSpot-defined contact->company, idempotent, no body.
function associationUrl(contactId, companyId) {
  if (!contactId || !companyId) return null;
  return "https://api.hubapi.com/crm/v4/objects/contacts/" + String(contactId) +
         "/associations/default/companies/" + String(companyId);
}

module.exports = {
  FREEMAIL_DOMAINS, NOT_A_COMPANY_DOMAIN, cleanCompanyDomain, emailDomain, companyDomainForRow,
  companyNameForRow, searchResults, domainMatchId, nameMatchId, resolveCompanyLink,
  associationUrl,
};
