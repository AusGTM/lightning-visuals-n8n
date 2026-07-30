# Milestones

## v0.4 Reachability & Verification Debt (Shipped: 2026-07-29)

**Phases completed:** 3 phases, 6 plans, 17 tasks

**Key accomplishments:**

- BUG 23 fixed: enrichment `contact:create` made structurally reachable — contacts-lane `HubSpot Search`/`HubSpot Fetch By Id` swapped to the credential-bound httpRequest envelope, byte-identical pins retired with rationale, dual live canary proved match-path regression AND create-path reachability (write-gated), deployment restored disarmed.
- Added `_industryText` to `normalizeProviders.js` so ZoomInfo's and Lusha's company mappers emit the NAICS entry's human-readable name (or nothing) instead of a bare numeric code, closing the gap where a code could win the industry waterfall purely on source trust.
- Wired `lv_sponsorship_reliant` (companies research fold) and `lv_persona_group` (contacts winners loop) into their merge calls via one array entry and one dot-access if-block, closing both Phase-15-carried-forward copy-loop gaps at the wiring level; both fields still have no producer.
- Both Phase-18 verification gaps closed end-to-end: the research prompt now actually asks for `lv_sponsorship_reliant` and a new provider-mapper producer actually emits `lv_persona_group` — both proven live-reachable through compiled node bodies fed by recorded fixtures, not hand-constructed test rows.
- Reconstructed and re-executed all six v0.3 `/gsd-verify-work` re-runs against current code — surfacing BUG 26 (live n8n Cloud deployment had drifted behind git) along the way. Same-day operator runbook closed everything: Step-0 redeploy (BUG 26 resolved), armed `company:update` canary (execution 108, write proven on the allowlisted record only, disarm read back). Final ledger: **6/6 passed, zero residual operator debt**.

**Closeout:** verified — all 3 phases `verification_status: passed`; pre-close artifact audit all-clear; v4 requirements 8/8 complete. No `v0.4-MILESTONE-AUDIT.md` was run (accepted: the phase-level verifier chain + 6/6 ledger covered the same ground). No git tag created — repo tag namespace uses semver release tags (`v0.4.0`/`v0.5.0`); a `v0.4` milestone tag would collide confusingly (same precedent as the untagged v0.3 close). Legacy v1/v2 requirement sections in the archived REQUIREMENTS.md carry historical unchecked rows from already-archived milestones, not v0.4 gaps.

---
