// scripts/dryrun_batch.mjs — batch live dry-run harness for contact enrichment.
//
// For each candidate: build identity_keys -> call LIVE Lusha/Apollo/ZoomInfo with the
// SAME request shapes the production n8n builders use -> run the production scoring modules
// (n8n/code) -> read-only HubSpot search for idempotency -> gate decision. Prints a
// per-candidate matrix and writes a markdown report.
//
// SAFETY: read-only. Provider calls + HubSpot SEARCH only. No create/update/patch is ever
// issued — there is no code path here that writes to HubSpot. Mirrors the Gillon dry-run.
//
// Run (sources .env into the process env without printing secrets):
//   set -a; . ./.env; set +a; node scripts/dryrun_batch.mjs
//
// Env used: LUSHA_API_KEY, APOLLO_API_KEY, ZOOMINFO_CLIENT_ID, ZOOMINFO_CLIENT_SECRET,
//           HUBSPOT_PRIVATE_APP_TOKEN.

import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";

const require = createRequire(import.meta.url);
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { toCandidates } = require(path.join(ROOT, "n8n/code/normalizeProviders.js"));
const { scoreCandidates } = require(path.join(ROOT, "n8n/code/scoreEnrichment.js"));
const { decideAction } = require(path.join(ROOT, "n8n/code/enrichmentGate.js"));

const NOW = new Date().toISOString();

// Domains are best-guess (providers match on name+company; domain is a bonus key).
const CANDIDATES = [
  { firstName: "Gerry",  lastName: "Harvey",     company: "Harvey Norman",        domain: "harveynorman.com.au",       tag: "1&2 rich AU exec (ZoomInfo 200 + Apollo reveal)" },
  { firstName: "Kyle",   lastName: "Bettler",    company: "Racing NSW",           domain: "racingnsw.com.au",          tag: "3&5 enrich + provider disagreement" },
  { firstName: "Kieran", lastName: "Granger",    company: "Melbourne Racing Club", domain: "mrc.net.au",               tag: "4 skip (existing, fresh)" },
  { firstName: "Mick",   lastName: "James",      company: "Australian Turf Club",  domain: "australianturfclub.com.au", tag: "4 skip (existing, fresh)" },
  { firstName: "David",  lastName: "Preschlack", company: "FanDuel",              domain: "fanduel.com",               tag: "6 non-AU (US) — phone normalizer -> review" },
];

// --- identity (mirrors ENRICH_BUILD_IDENTITY.identity_keys) -------------------
function identityKeys(c) {
  return {
    email: c.email || null,
    domain: c.domain || (c.email ? c.email.split("@")[1] : null),
    linkedin_url: c.linkedin_url || null,
    firstName: c.firstName || null,
    lastName: c.lastName || null,
    companyName: c.company || null,
  };
}

// --- resilient fetch: never throws; returns {status, body, err} --------------
async function call(url, opts) {
  try {
    const r = await fetch(url, opts);
    const text = await r.text();
    let body;
    try { body = JSON.parse(text); } catch { body = text; }
    return { status: r.status, body, err: null };
  } catch (e) {
    return { status: 0, body: null, err: String((e && e.message) || e) };
  }
}

// --- Lusha v2 person: GET, header api_key ------------------------------------
async function lusha(id) {
  const key = process.env.LUSHA_API_KEY;
  if (!key) return { status: 0, body: null, err: "no LUSHA_API_KEY" };
  const q = new URLSearchParams();
  if (id.email) q.set("email", id.email);
  if (id.linkedin_url) q.set("linkedinUrl", id.linkedin_url);
  if (id.firstName) q.set("firstName", id.firstName);
  if (id.lastName) q.set("lastName", id.lastName);
  if (id.companyName) q.set("companyName", id.companyName);
  if (id.domain) q.set("companyDomain", id.domain);
  return call(`https://api.lusha.com/v2/person?${q}`, { method: "GET", headers: { api_key: key } });
}

// --- Apollo people/match: POST, header X-Api-Key, reveal email ---------------
async function apollo(id) {
  const key = process.env.APOLLO_API_KEY;
  if (!key) return { status: 0, body: null, err: "no APOLLO_API_KEY" };
  const body = {
    email: id.email || undefined,
    domain: id.domain || undefined,
    first_name: id.firstName || undefined,
    last_name: id.lastName || undefined,
    organization_name: id.companyName || undefined,
    reveal_personal_emails: true, // phone is async (webhook) — not requested here
  };
  return call("https://api.apollo.io/v1/people/match", {
    method: "POST",
    headers: { "Content-Type": "application/json", "Cache-Control": "no-cache", "X-Api-Key": key },
    body: JSON.stringify(body),
  });
}

// --- ZoomInfo GTM: mint token (Basic client creds) then enrich (Bearer) ------
// LIVE-verified valid outputFields (matchStatus is in meta, not an outputField).
const ZOOM_OUTPUT_FIELDS = ["id", "firstName", "lastName", "email", "phone", "mobilePhone",
  "jobTitle", "managementLevel", "contactAccuracyScore", "validDate", "lastUpdatedDate"];
let _zoomToken = null;
async function zoomMint() {
  const cid = process.env.ZOOMINFO_CLIENT_ID, csec = process.env.ZOOMINFO_CLIENT_SECRET;
  if (!cid || !csec) return null;
  const basic = Buffer.from(`${cid}:${csec}`).toString("base64");
  const r = await call("https://api.zoominfo.com/gtm/oauth/v1/token", {
    method: "POST",
    headers: { Authorization: `Basic ${basic}`, "Content-Type": "application/x-www-form-urlencoded" },
    body: "grant_type=client_credentials",
  });
  const b = r.body || {};
  return b.access_token || b.jwt || b.token || null;
}
async function zoominfo(id) {
  if (!process.env.ZOOMINFO_CLIENT_ID) return { status: 0, body: null, err: "no ZOOMINFO creds" };
  if (!_zoomToken) _zoomToken = await zoomMint();
  if (!_zoomToken) return { status: 0, body: null, err: "token mint failed" };
  const person = {};
  if (id.email) person.emailAddress = id.email;
  if (id.firstName) person.firstName = id.firstName;
  if (id.lastName) person.lastName = id.lastName;
  if (id.companyName) person.companyName = id.companyName;
  const hasKey = person.emailAddress || (person.firstName && person.lastName && person.companyName);
  if (!hasKey) return { status: 0, body: { skipped: "no zoominfo match key" }, err: null };
  return call("https://api.zoominfo.com/gtm/data/v1/contacts/enrich", {
    method: "POST",
    headers: { Authorization: `Bearer ${_zoomToken}`,
      "Content-Type": "application/vnd.api+json", Accept: "application/vnd.api+json" },
    body: JSON.stringify({ data: { type: "ContactEnrich",
      attributes: { matchPersonInput: [person], outputFields: ZOOM_OUTPUT_FIELDS } } }),
  });
}

// --- HubSpot read-only search (idempotency). Search by email then by name ----
async function hsSearch(id, discoveredEmail) {
  const tok = process.env.HUBSPOT_PRIVATE_APP_TOKEN;
  if (!tok) return { status: 0, body: null, err: "no HUBSPOT token", results: [] };
  const props = ["email", "firstname", "lastname", "jobtitle", "phone", "mobilephone",
    "jobtitle_verified_at", "mobilephone_verified_at"];
  const email = id.email || discoveredEmail;
  const filters = email
    ? [{ propertyName: "email", operator: "EQ", value: email }]
    : [{ propertyName: "firstname", operator: "EQ", value: id.firstName },
       { propertyName: "lastname", operator: "EQ", value: id.lastName }];
  const r = await call("https://api.hubapi.com/crm/v3/objects/contacts/search", {
    method: "POST",
    headers: { Authorization: `Bearer ${tok}`, "Content-Type": "application/json" },
    body: JSON.stringify({ filterGroups: [{ filters }], properties: props, limit: 5 }),
  });
  const results = (r.body && Array.isArray(r.body.results)) ? r.body.results : [];
  return { ...r, results };
}

// --- per-candidate run -------------------------------------------------------
async function runOne(c) {
  const id = identityKeys(c);
  const [lu, ap, zi] = await Promise.all([lusha(id), apollo(id), zoominfo(id)]);

  const cands = [
    ...(lu.status === 200 ? toCandidates("lusha", lu.body, "contacts") : []),
    ...(ap.status === 200 ? toCandidates("apollo", ap.body, "contacts") : []),
    ...(zi.status === 200 ? toCandidates("zoominfo", zi.body, "contacts") : []),
  ];
  const gap_flag = cands.length === 0;
  const { best, winners } = scoreCandidates(cands, { now: NOW });
  const discoveredEmail = best.email && best.email.value;

  const hs = await hsSearch(id, discoveredEmail);
  const existing = hs.results[0] ? hs.results[0].properties : {};
  const gate = decideAction(existing, ["email", "jobtitle", "mobilephone"],
    { jobtitle: { stale_after_days: 180 }, mobilephone: { stale_after_days: 180 } }, NOW);

  return { c, id, lu, ap, zi, cands, best, winners, gap_flag, hs, existing, gate };
}

// --- report ------------------------------------------------------------------
function bestVal(best, f) { return best[f] ? `${best[f].value} (${best[f].source})` : "—"; }

function report(rows) {
  const d = NOW.slice(0, 10);
  let md = `# Batch Dry-Run Report — ${d}\n\n`;
  md += `**Mode:** DRY RUN (no HubSpot write) · read-only provider calls + HubSpot search only.\n\n`;
  md += `## Provider + gate matrix\n\n`;
  md += `| Candidate | Company | Lusha | Apollo | ZoomInfo | #cand | best email | best phone | best title | HS match | gate |\n`;
  md += `|---|---|---|---|---|---|---|---|---|---|---|\n`;
  for (const r of rows) {
    const st = (x) => x.err ? `err` : x.status;
    md += `| ${r.c.firstName} ${r.c.lastName} | ${r.c.company} | ${st(r.lu)} | ${st(r.ap)} | ${st(r.zi)} | ${r.cands.length} | ${bestVal(r.best, "email")} | ${bestVal(r.best, "mobilephone") !== "—" ? bestVal(r.best, "mobilephone") : bestVal(r.best, "phone")} | ${bestVal(r.best, "jobtitle")} | ${r.hs.results.length} | ${r.gate.action} |\n`;
  }
  md += `\n_Gate acts on read-only search only; no create/update/patch issued this run._\n\n`;
  md += `## Raw provider responses\n\n`;
  for (const r of rows) {
    md += `### ${r.c.firstName} ${r.c.lastName} — ${r.c.company}  ·  _${r.c.tag}_\n\n`;
    for (const [name, x] of [["lusha", r.lu], ["apollo", r.ap], ["zoominfo", r.zi]]) {
      md += `**${name}** — HTTP ${x.err ? `ERR (${x.err})` : x.status}\n\n`;
      md += "```json\n" + JSON.stringify(x.body, null, 2).slice(0, 4000) + "\n```\n\n";
    }
    md += `**HubSpot search** — HTTP ${r.hs.status}, ${r.hs.results.length} match(es). **Gate:** ${r.gate.action} (${r.gate.reason || ""}).\n\n---\n\n`;
  }
  return md;
}

async function main() {
  console.log(`Batch dry-run — ${CANDIDATES.length} candidates — ${NOW}\n`);
  const rows = [];
  for (const c of CANDIDATES) {
    process.stdout.write(`  ${c.firstName} ${c.lastName} … `);
    const r = await runOne(c);
    rows.push(r);
    console.log(`lusha=${r.lu.err ? "err" : r.lu.status} apollo=${r.ap.err ? "err" : r.ap.status} zoominfo=${r.zi.err ? "err" : r.zi.status} cands=${r.cands.length} HS=${r.hs.results.length} gate=${r.gate.action}`);
  }
  const md = report(rows);
  const out = path.join(ROOT, "docs/reports", `${NOW.slice(0, 10)}-dryrun-batch.md`);
  fs.writeFileSync(out, md);
  console.log(`\nReport: ${path.relative(ROOT, out)}`);
}

main();
