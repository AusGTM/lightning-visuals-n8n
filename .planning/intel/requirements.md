# Requirements (PRD intel)

Source PRD: `/Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc/icp-scoring.md`
Title: Lightning Visuals — ICP / Anti-ICP Validation
Status: For sign-off before rubric build (JTBD 2). Basis: 92 closed HubSpot deals (79 new-business after renewals removed, 34% baseline win).

---

## REQ-icp-scoring-model
Source: icp-scoring.md §5
Description: Compute a numeric ICP fit score from firmographic + enrichment signals available at lead/account-scoring time. Deal value is deliberately excluded (does not exist until a deal opens).
Acceptance criteria:
- Org type: governing-body/league +40, content producer +20, individual club +5, other 0.
- Produces broadcast/streaming content: +20 (none = hard veto).
- Geography ANZ: +10 (non-ANZ = hard veto).
- Revenue $5–500M: +10 (>$500M handled by graduated decay, see REQ-graduated-deductions).

## REQ-anti-icp-vetoes
Source: icp-scoring.md §4, §5
Description: Hard vetoes disqualify a prospect and set the anti-ICP flag.
Acceptance criteria:
- Hard veto fires for: non-ANZ geography, no broadcast/streaming content, AV/LED hardware vendor.
- On veto: `lv_anti_icp_flag = true`, tier forced to D.
- Gambling operators and >$500M revenue are NOT vetoes — they are graduated deductions and must never set the anti-ICP flag.

## REQ-graduated-deductions
Source: icp-scoring.md §5
Description: Negative-decay deductions applied after base points; targetable prospects, never auto-disqualified.
Acceptance criteria:
- Revenue $500M–750M −5; $750M–1B −15; $1B–1.2B −30; $1.2B+ −50 (near-veto, never auto-disqualify).
- Gambling operator −20 (surface-able when other fit signals strong).
- None of these set `lv_anti_icp_flag`.

## REQ-tiering
Source: icp-scoring.md §5
Description: Map score + veto rules to an A/B/C/D tier reps act on.
Acceptance criteria:
- A: score ≥ 70 → priority direct outreach.
- B: 40–69 → work directly if account context strong.
- C: 15–39 → nurture via league/governing body, not worked directly.
- D: any hard veto fired → disqualify.

## REQ-org-type-targeting
Source: icp-scoring.md §1, §4
Description: Shift the unit of targeting from individual clubs to governing bodies/leagues.
Acceptance criteria:
- Best-fit = AU governing-body/league (or content producer) producing live/near-live content, mid-market revenue ($5–500M).
- Individual clubs/teams are anti-ICP as a direct target (19% win over 36 deals) — reach them via their governing body.
- Secondary fit = AU sports content producers / OB houses (~40% win).

## REQ-enrichment-plan
Source: icp-scoring.md §6
Description: Enrich the ICP-decisive signals HubSpot does not natively hold, from the existing stack.
Acceptance criteria:
- Org type → Claude/Orchestrator classifier on name+website+industry.
- Content output → Claude/Orchestrator + Apollo/ZoomInfo.
- Seniority/persona → ZoomInfo → Lusha → Apollo → SignalHire waterfall.
- Revenue/employees refine → Apollo/ZoomInfo.
- Intent (forward-looking) → ZoomInfo/HubSpot pixel.
- Qualitative fit → Fathom + Claude on call transcripts.

## REQ-hubspot-icp-properties
Source: icp-scoring.md §5, §6
Description: Custom HubSpot properties backing the rubric, in three roles (input / output / hygiene).
Acceptance criteria:
- Inputs (enrichment writes): lv_org_type, lv_produces_content; plus existing country, annualrevenue.
- Outputs (rubric writes): lv_icp_fit_score, lv_icp_tier, lv_anti_icp_flag.
- Hygiene: lv_closed_lost_reason (picklist), deal_source.

## REQ-closed-lost-capture
Source: icp-scoring.md §4, §6
Description: Capture real loss reasons; closed_lost_reason is 0% filled today and is the single biggest blocker to evidence-based anti-ICP.
Acceptance criteria:
- Introduce lv_closed_lost_reason picklist and begin capturing it now.
- Known top loss reasons from discovery calls: price/affordability (#1), fear of cloud (#2, esp. horse racing); plus incumbent-satisfied, no streaming/broadcast, sub-professional kit.

## REQ-finite-list-motion
Source: icp-scoring.md §8
Description: Given a finite best-fit TAM, prefer enrich+score of a named list over high-volume programmatic prospecting.
Acceptance criteria:
- Validated best-fit ≈ 100–150 ANZ orgs (racing core ~25–28; fewer than 10 at $100K+ ACV).
- Racing core: enrich + score, ~zero net-new discovery (already in CRM).
- Non-racing best-fit: one-time hand-built list of ~30–50 orgs to validate.
- Org type verified for only 66 of 712 CRM companies → enrich first, then score.

## REQ-intent-scoring
Source: icp-scoring.md §5
Description: Forward-looking HubSpot-pixel-driven intent scoring (no historical data yet).
Acceptance criteria:
- Any tracked website visit (known company) +3; pricing/product/demo page +7; return visit within 14 days +5; ≥3 sessions or multi-contact from same company +10; no activity 0.
- NOTE: not present in the SPEC's icp_scoring.yaml — see INGEST-CONFLICTS.md INFO.

## REQ-signoff-gate
Source: icp-scoring.md §9
Description: Sign-off gate before weighted rubric build.
Acceptance criteria:
- Alex sign-off on best-fit (governing-bodies-first) and anti-ICP (clubs-direct, non-AU, no-content) before JTBD 2 rubric build.
- Point weights in §5 are illustrative and are themselves the JTBD 2 sign-off item.
- HubSpot currently on Starter ($35); scoring/workflows require a Pro tier (confirmed); orchestration options still open.
