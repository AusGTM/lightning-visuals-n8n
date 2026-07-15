# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Repository structure: README, CHANGELOG, proprietary LICENSE; docs reorganised into `docs/{business,architecture,reviews}`.

### Pending
- Live-provider **dry run** (Lusha/Apollo/ZoomInfo → scored winners → HubSpot read → printed payload, no write).
- `lv_*` HubSpot custom-property creation script (idempotent) — hard prerequisite for live writeback.

## [0.4.0] - 2026-07-15

### Added
- **Enrichment workflow** (n8n Cloud): idempotency gate — check HubSpot first, then **create / enrich (stale) / skip (current)**.
- **Quality-scored waterfall** replacing FIFO stop-on-first-match: field-level best-of-breed scoring across all three providers `value_score = wA·accuracy + wR·recency + wG·agreement + wT·trust`, with cross-source consensus and provenance.
- **ZoomInfo autonomous OAuth2** (Okta client-credentials): token minted from `client_id`/`client_secret`, cached in workflow static data, re-minted on near-expiry and **refresh-on-401**. No static token stored.
- Provider response normalizer + accuracy/recency signal mapping for Lusha, Apollo, ZoomInfo; tested JS modules (`n8n/code/{scoreEnrichment,enrichmentGate,normalizeProviders,zoominfoToken}.js`).

### Verified
- Live authentication for **Lusha, Apollo, ZoomInfo**; ZoomInfo client-credentials mint confirmed against `gtm/oauth/v1/token` (no `scope`).

### Fixed
- ZoomInfo auth corrected from single-key/PKI assumptions to Okta client-credentials (DevPortal `client_id` + `client_secret`).

## [0.3.0] - 2026-07-08

### Added
- **n8n Cloud-native port**: contact-ingestion pipeline runs entirely in n8n Code nodes (no npm) + HTTP/HubSpot nodes; AU-phone normalization in inline JS; email validation via the external verifier API.
- Cloud + locally-executable workflow templates; scripted local-n8n replica proof.

### Removed
- FastAPI decision service (superseded by inline Code nodes).

## [0.2.0] - 2026-07-08

### Added
- **Contact ingestion**: file loader (CSV/XLSX/JSON), column mapper, contact normalizer (phone→E.164, email validate).
- **Identity/dedupe resolver** (email→linkedin→phone+name→name+company; no-email never auto-creates).
- Gated net-new create with pre-create re-check; dedupe/mangled sweep.
- n8n local-server replica (FastAPI decision service) for contact ingestion + weekly sweep.

## [0.1.0] - 2026-07-07

### Added
- **Local-first ICP scoring MVP** (Milestone 1): config-driven scoring engine (score / tier / anti-ICP vetoes / graduated deductions), non-clobber merge with field-ownership classes, per-field source attribution, dry-run HubSpot PATCH output under env-flag safety gates.
- Mock provider waterfall + Claude web research; Haiku→Sonnet LLM cascade.
- Bootstrapped from ingested specification and ICP validation docs.

[Unreleased]: https://github.com/AusGTM/lightning-visuals-n8n/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/AusGTM/lightning-visuals-n8n/releases/tag/v0.4.0
[0.3.0]: https://github.com/AusGTM/lightning-visuals-n8n/releases/tag/v0.3.0
[0.2.0]: https://github.com/AusGTM/lightning-visuals-n8n/releases/tag/v0.2.0
[0.1.0]: https://github.com/AusGTM/lightning-visuals-n8n/releases/tag/v0.1.0
