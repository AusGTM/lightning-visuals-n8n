// Probe: does THIS account's ZoomInfo GTM contacts/enrich expose location outputFields?
//
// Question (operator, 2026-08-26): Lusha never supplies contact state; Apollo does but
// rarely matches; does ZoomInfo? The account-verified valid list (memory:
// zoominfo-gtm-enrich-400-blocker, probed 2026-07) has NO location field — but that list
// is only what we asked for. GTM rejects unknown outputFields with a hard 400 that names
// the invalid field, so a live request is the one authority on what this tier exposes.
//
// Method: binary split. One request with the verified list + ALL candidate location
// names. 200 → every candidate is valid; read which came back non-null. 400 → drop the
// fields the error names and retry with the survivors (up to a handful of rounds, since
// the 400 may name only one offender at a time). Uses the SAME match key as production
// (firstName+lastName+companyName), on a real known-match contact, so a 200 also shows
// real values, not just schema acceptance. Cost: ZoomInfo bills per MATCH — at most a
// few match credits total (memory: ~1.08 credits/match), zero on 400s.
//
// Run (needs .env — unreadable from Claude sessions, so the operator runs this):
//   set -a; . ./.env; set +a; node scripts/probe_zoominfo_location_fields.mjs
//
// Read-only against everything except the ZoomInfo match-credit meter. No HubSpot, no
// n8n, no writes anywhere.

const VERIFIED = ["id", "firstName", "lastName", "email", "phone", "mobilePhone",
  "jobTitle", "managementLevel", "contactAccuracyScore", "validDate", "lastUpdatedDate"];

// Candidate names, ordered by likelihood: classic-API contact fields first, then GTM-ish
// and JSON:API-ish variants of the same concepts.
const CANDIDATES = ["city", "state", "country", "zipCode", "metroArea", "region",
  "personCity", "personState", "personCountry", "location"];

// A known FULL_MATCH contact on this account (execution 11956/11960 matched via Lusha;
// ZoomInfo match not guaranteed — a NO_MATCH still proves schema acceptance on a 200).
const PERSON = { firstName: "John", lastName: "Tsatsimas", companyName: "Football NSW" };

async function call(url, opts) {
  const r = await fetch(url, opts);
  const text = await r.text();
  let body;
  try { body = JSON.parse(text); } catch { body = text; }
  return { status: r.status, body };
}

async function mint() {
  const cid = process.env.ZOOMINFO_CLIENT_ID, csec = process.env.ZOOMINFO_CLIENT_SECRET;
  if (!cid || !csec) {
    console.error("FATAL: ZOOMINFO_CLIENT_ID / ZOOMINFO_CLIENT_SECRET not in env. Run:\n" +
      "  set -a; . ./.env; set +a; node scripts/probe_zoominfo_location_fields.mjs");
    process.exit(1);
  }
  const basic = Buffer.from(`${cid}:${csec}`).toString("base64");
  const r = await call("https://api.zoominfo.com/gtm/oauth/v1/token", {
    method: "POST",
    headers: { Authorization: `Basic ${basic}`, "Content-Type": "application/x-www-form-urlencoded" },
    body: "grant_type=client_credentials",
  });
  const t = r.body && (r.body.access_token || r.body.jwt || r.body.token);
  if (!t) { console.error("FATAL: token mint failed", r.status, JSON.stringify(r.body).slice(0, 300)); process.exit(1); }
  return t;
}

async function enrich(token, outputFields) {
  return call("https://api.zoominfo.com/gtm/data/v1/contacts/enrich", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`,
      "Content-Type": "application/vnd.api+json", Accept: "application/vnd.api+json" },
    body: JSON.stringify({ data: { type: "ContactEnrich",
      attributes: { matchPersonInput: [PERSON], outputFields } } }),
  });
}

// Pull every candidate name the 400 body mentions, however the error is phrased.
function offendersIn(body, candidates) {
  const text = JSON.stringify(body || "");
  return candidates.filter((c) => new RegExp(`\\b${c}\\b`).test(text));
}

const token = await mint();
let pool = [...CANDIDATES];
const rejected = [];

for (let round = 1; round <= 6 && pool.length; round++) {
  const fields = [...VERIFIED, ...pool];
  const r = await enrich(token, fields);
  console.log(`round ${round}: HTTP ${r.status} with candidates [${pool.join(", ")}]`);

  if (r.status === 200) {
    const rec = Array.isArray(r.body?.data) ? r.body.data[0] : null;
    const attrs = rec?.attributes || {};
    const matchStatus = rec?.meta?.matchStatus || "(no record)";
    console.log(`\nVERDICT: schema ACCEPTS [${pool.join(", ")}]  (rejected: ${rejected.join(", ") || "none"})`);
    console.log(`matchStatus: ${matchStatus}`);
    console.log("values returned for accepted candidates:");
    for (const c of pool) console.log(`  ${c}: ${JSON.stringify(attrs[c] ?? null)}`);
    console.log("\nNote: accepted-but-null on one contact is not proof the field is never " +
      "populated — but accepted + populated here is proof it IS available. Paste this " +
      "whole output back to Claude.");
    process.exit(0);
  }

  if (r.status === 400) {
    const named = offendersIn(r.body, pool);
    console.log(`  400 body: ${JSON.stringify(r.body).slice(0, 400)}`);
    if (named.length) {
      rejected.push(...named);
      pool = pool.filter((c) => !named.includes(c));
      console.log(`  dropping named offender(s): ${named.join(", ")}`);
      continue;
    }
    // 400 that names no candidate: halve the pool to isolate (defensive; GTM normally names the field).
    if (pool.length === 1) { rejected.push(pool.pop()); continue; }
    const half = pool.splice(Math.ceil(pool.length / 2));
    console.log(`  400 named nothing — setting aside [${half.join(", ")}] and retrying front half`);
    rejected.push(...half.map((c) => `${c}?`)); // "?" = eliminated by split, not named — re-probe individually if it matters
    continue;
  }

  console.error(`FATAL: unexpected HTTP ${r.status}: ${JSON.stringify(r.body).slice(0, 400)}`);
  process.exit(1);
}

console.log(`\nVERDICT: no location outputField accepted. Rejected: ${rejected.join(", ")}`);
console.log("This tier exposes no contact location fields — the normalizeProviders.js " +
  "comment (no ZoomInfo location candidates) stands as-is.");
