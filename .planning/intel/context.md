# Context (DOC intel)

No DOC-classified documents in this ingest set. Running notes below capture
cross-references and background carried by the two classified docs.

## Cross-references (external, not in ingest set)
Source: classifications
- CLAUDE.md → RTK.md (referenced tooling doc; not provided to this ingest run).
- icp-scoring.md → Market-Research (companion market-size + competition analysis; not provided). Referenced for full saturation breakdown (§8) and competitor sourcing (§7). No cycle: neither external ref points back into the ingest set.

## Market / competition background
Source: icp-scoring.md §7, §8
- #1 threat: LIGR.live — Australian cloud pay-per-use competitor already running the governing-body "buy-once-deploy-league-wide" play; holds Football Australia gatekeeper deal; lists Cricket Australia / QRL / AFL NAB League. LV positioned between Vizrt (premium) and LIGR (budget).
- Differentiate on automation, data, price, outbound — NOT "cloud" (Vizrt/Ross now ship cloud too).
- Virtual-advertising bet faces AU incumbents (Broadcast Virtual, Girraphic).
- Validated best-fit TAM is finite (~100–150 ANZ orgs), which motivates enrich-and-score over high-volume prospecting.

## Data-quality caveats (affect confidence in PRD figures)
Source: icp-scoring.md §1, §2
- Findings measure which engaged deals convert, not the whole addressable market; small cells (n ≥ 3 shown) — treat as hypotheses, not statistical certainty.
- Pre-HubSpot deals (prior founder's video work) missing → CRM likely undercounts wins; true win rate probably higher than 34% baseline.
- closed_lost_reason 0% filled → anti-ICP inferred from firmographics (discovery calls now supply real reasons: price + cloud-fear).
- HubSpot native industry tag unreliable (e.g. Australian Turf Club tagged "Gambling/Casinos") → lead with enriched signals, not native tags.
- org type verified for only 66 of 712 CRM companies.
