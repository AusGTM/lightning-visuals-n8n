# Gap Analysis — n8n Use vs Phase-2 Proposal

> **⚠ SUPERSEDED (2026-07-23).** Point-in-time snapshot from proposal week 3. The gaps it flags as *Not built* — the Lusha→Apollo→ZoomInfo enrichment waterfall (D2), ICP scoring as an n8n node (D5), and live `lv_*` properties (D6) — were all **delivered** by Phases 11–16 (enrichment + companies branch, `n8n/code/scoreEnrichment.js` + judge wiring, and the live Phase-15 property migration). Retained for historical audit; read against current `README.md` / `n8n/README.md`.

**Scope:** POC's n8n implementation vs the n8n-related deliverables in *Detailed Lightning_Visuals_GTM_Engineering_Proposal.md* (Phase 2, Weeks 4–11).
**Date:** 2026-07-14 (proposal week 3).
**Verdict:** The POC delivers the **Orchestration & Tier Cutover workflow POC** (proposal item 4, *IN PROGRESS*) and de-risks the n8n plumbing + safe HubSpot write-back. It does **not** yet deliver the core Phase-2 n8n deliverable — the **Lusha→Apollo→ZoomInfo enrichment waterfall** — which the proposal itself marks *NOT STARTED*. The POC's n8n effort went into an **adjacent** contact-ingestion/hygiene pipeline, not the enrichment waterfall.

---

## 1. What the proposal asks of n8n (Phase 2)

| # | n8n deliverable | Source |
|---|---|---|
| D1 | Orchestration layer (n8n) provisioned; API access confirmed for Lusha/Apollo/ZoomInfo | Deliverables Wk4; Status item 4 |
| D2 | Lusha→Apollo→ZoomInfo waterfall **live in n8n**, **stop on first confident match**, per-source confidence thresholds, field-level write-back mapping | Deliverables Wk6; JTBD 1.2 |
| D3 | Gap-flagging + **data-quality labels** for partial/failed enrichment (all sources fail → work manually) | JTBD 1.3; Status item 1 |
| D4 | ZoomInfo **intent-pixel** trigger routed via a managed Claude agent (PAYG) | JTBD 1.4 |
| D5 | **Scoring triggered automatically on enrichment completion** (orchestration) | JTBD 2.2 |
| D6 | Write-back to HubSpot; **custom HubSpot properties created**; validate write-back **permissions + API limits across all 4 sources** | Status item 4; JTBD 1.2 |
| D7 | Test waterfall against a sample lead set; reconcile vs Phase-1 minimum-data definition | JTBD 1.5 |

*(Non-n8n Phase-2 items — native HubSpot scoring properties, per-rep stack-ranked views, lead-magnet landing pages — are out of this n8n-focused scope but noted where they intersect.)*

---

## 2. What the POC actually built in n8n

- **n8n provisioned** — local Docker n8n v2.4.4 (`localhost:5678`), owner account set up.
- **Cloud-compatible workflow pattern** — `n8n/wf_contact_ingest_cloud.json` (19 nodes): Webhook → Extract-from-File → Code(map) → Code(normalize phone) → HTTP(email verify) → Code(apply) → HubSpot(search) → Code(identity resolve) → Code(non-clobber merge) → IF → HubSpot(update/create) / Set(review). All logic in **inline Code nodes (no npm)**, ported from tested Python, cross-checked `JS === Python`.
- **Safe HubSpot write-back pattern** — gated update/create, dry-run default, non-clobber merge (`mergeContacts.js`), per-field source metadata + `validation_status`.
- **Data hygiene** — AU phone normalization (inline JS), email validation via `rapid-email-verifier` (out-of-box API), identity/dedupe resolver, weekly dedupe sweep.
- **Proven on the local server** — `scripts/n8n_contact_replica.sh` imports + executes headless; live email verifier reached; no HubSpot write.

**Evidence of absence** (grep of `n8n/`): no enrichment, waterfall, intent, or scoring nodes. Node types: `code`×8, `hubspot`×3, `httpRequest`×1 (email verifier only), `extractFromFile`, `if`×2, `set`, `webhook`. Provider keys (`LUSHA/APOLLO/ZOOMINFO_API_KEY`) all **empty**.

---

## 3. Gap table (n8n deliverables)

| # | Deliverable | Status | Evidence / Gap |
|---|---|---|---|
| D1 | n8n provisioned + API access confirmed (3 sources) | 🟡 **Partial** | n8n provisioned (local; not the paid Cloud instance yet). Provider API access **not** confirmed — Lusha/Apollo/ZoomInfo keys empty, no live call. |
| D2 | Enrichment waterfall **live in n8n**, stop-on-first-match, thresholds, write-back mapping | 🔴 **Not built** | No waterfall in any n8n workflow. A *Python mock* company waterfall exists (M1, `src/providers.py`) but: not n8n, mocked, **no stop-on-first-match** (merge takes all candidates), order ZoomInfo-first (proposal is Lusha-first). |
| D3 | Gap-flagging + data-quality labels | 🟡 **Mechanism only** | No enrichment → no enrichment gap-flagging. But the plumbing exists: `validation_status`, `needs_review`, per-field source metadata, and the dedupe sweep's mangled/duplicate flags. Directly reusable to carry the labels once the waterfall exists. |
| D4 | ZoomInfo intent-pixel via managed Claude agent | 🔴 **Not built** | Absent entirely. |
| D5 | Scoring triggered on enrichment completion (n8n) | 🔴 **Not orchestrated** | ICP scoring is standalone **Python** (M1, dry-run), not an n8n node, not triggered by enrichment. No enrichment event to trigger on. |
| D6 | Write-back live + custom properties created + permissions/API-limit validation | 🟡 **Pattern only** | HubSpot update/create **nodes** exist but need credentials; all writes are **dry-run**. Custom `lv_*` properties are **defined** (`config/field_policy.yaml`, CLAUDE.md) but **not created** in the live portal ("workflow POC to transpose upstream dependency custom HubSpot properties to be created" — still to do). No live permission/API-limit validation. |
| D7 | Test vs sample lead set + minimum-data reconciliation | 🔴 **Not done** | No live provider data; tests run on fixtures, not a HubSpot sample lead set; no reconciliation vs the Phase-1 minimum-data definition. |

**Legend:** 🔴 not built · 🟡 partial/foundation · 🟢 built.

---

## 4. Adjacent work the POC built (valuable, but not a named Phase-2 n8n deliverable)

The proposal's three Phase-2 JTBDs are **enrichment, scoring, lead magnets**. The POC's n8n build is **contact CSV/file ingestion + identity/dedupe + hygiene + non-clobber write-back** — none of which is a named Phase-2 deliverable. It maps to:
- **Foundational** to D2/D6: the non-clobber merge, source-metadata/data-quality-label mechanism, and gated HubSpot update/create nodes are exactly what the enrichment write-back needs. The hardest *write-back safety* problem is solved and reusable.
- **A new pipe entry point**: file/upload ingestion resembles the proposal's "outbound-sourced lead / lead-magnet form → same pipe" concept, but ingestion itself isn't scoped in Phase 2.
- **Data hygiene** (email/phone validation, dedupe sweep): supports the pipe; overlaps the Phase-1 `dedupe_check` mode, not a Phase-2 line item.

**Net:** real, reusable engineering — but it advanced the *rails and hygiene*, not the *enrichment waterfall* that is the heart of the Phase-2 n8n scope.

---

## 5. Architecture divergences to flag

1. **Enrichment was deliberately excluded** from the n8n build (separation of concerns). Defensible design-wise, but enrichment is Phase-2 deliverable #1 — the POC prioritized the front-half (ingest/hygiene) over the core.
2. **Lusha is "native HubSpot integration," first in the waterfall** (proposal) — a HubSpot-marketplace enrichment, *not* an n8n node. The waterfall shape is: HubSpot-native Lusha → then n8n orchestrates Apollo + ZoomInfo APIs. The POC's Python treated Lusha as a mock API adapter; the native-first nuance isn't modeled.
3. **Stop-on-first-match** (cost control) vs the POC's **take-all-candidates merge**. These are different control flows — the waterfall halts on first confident match; the merge engine consumes every source. The waterfall's early-exit is not implemented.
4. **Scoring: external-compute (POC) vs HubSpot-native properties (proposal Wk8).** Compatible in principle (compute externally → write `lv_*` properties), but the proposal wants it *triggered on enrichment completion* and surfaced as *per-rep stack-ranked HubSpot views* — neither exists.
5. **n8n Cloud vs local.** Provisioned locally and validated Cloud-compatible, but not running on the paid n8n Cloud instance with live credentials.
6. **HubSpot tier.** Live scoring needs Marketing Hub Pro; the proposal marks HubSpot "Upgraded," but the POC has never written live (Starter was noted earlier) — confirm actual tier before D5/D6 go live.

---

## 6. What to build to close the n8n gaps (priority order)

1. **Enrichment waterfall workflow (D2)** — the core miss. New n8n workflow: trigger (HubSpot property/webhook) → Lusha (native/HubSpot) → *if no confident match* → Apollo (HTTP) → *if no match* → ZoomInfo (HTTP). Per-source confidence threshold gate; **stop on first match**. Reuse `mergeContacts.js` for field-level write-back mapping. **~biggest chunk of the 28h enrichment estimate.**
2. **Create the custom HubSpot properties (D6)** — script the `lv_*` + provider-staging + source-metadata property creation in the live portal (the "properties to be created" line). Prereq for any live write-back.
3. **Live credentials + write-back validation (D1/D6)** — wire Lusha/Apollo/ZoomInfo keys + HubSpot creds; validate permissions and per-source API limits on a small sample.
4. **Data-quality labels + gap-flagging (D3)** — extend the existing `validation_status`/source-metadata mechanism to stamp enrichment-source coverage + "all sources failed → manual" flag.
5. **Scoring-on-enrichment trigger (D5)** — fire the (existing) scoring engine when enrichment completes; write score/grade to properties; build the per-rep stack-ranked HubSpot view.
6. **ZoomInfo intent path (D4)** — later; managed Claude agent on the intent-pixel trigger (pending the PAYG decision).
7. **Sample-set test + minimum-data reconciliation (D7)** — run the waterfall on a real HubSpot lead sample; reconcile vs Phase-1 minimum-data.

**Reuse leverage:** items 1–5 inherit the POC's non-clobber merge, HubSpot nodes, source-metadata/label mechanism, dedupe, and Code-node inlining pattern. The plumbing is de-risked; the waterfall control-flow + live integrations are the remaining build.

---

## 7. Honest one-paragraph summary

The POC proves the n8n **orchestration substrate**, a **Cloud-compatible workflow-authoring pattern** (tested Code-node logic, no npm), and a **safe, non-clobbering HubSpot write-back** — plus a contact-ingestion/hygiene pipeline that, while genuinely useful and reusable, is **adjacent** to the three named Phase-2 JTBDs. Measured against the proposal's n8n deliverables, the POC is **on-track for item 4 (Orchestration & Tier Cutover, IN PROGRESS)** but has **not started the enrichment waterfall (item 1), scoring automation (item 2), or intent path** — consistent with the proposal's own week-3 status. The single most important n8n gap to close is the **Lusha→Apollo→ZoomInfo stop-on-first-match waterfall with live write-back**, and the POC's merge/label/HubSpot-node work is exactly the foundation to build it on.
