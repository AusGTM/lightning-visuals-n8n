# API Coverage — Phase 59 (frictionless-write-path)

> Full coverage by default. Opt-outs are explicit, reasoned decisions.

**Detector result:** `api-coverage.cjs --json` returned `detected: true` on a single signal —
the noun `sdk` in the phase-scope sentence describing what the plugin suite's existing
`no_network` fixture patches (`requests`) versus what the Anthropic SDK uses (`httpx`). That
sentence is a note about an EXISTING test fixture's reach, not a statement that this phase
integrates an SDK.

**No external API integration:** every one of this phase's four decision areas
(D-59-04 / D-59-06 / D-59-07 / D-59-08) is internal — a pytest `conftest.py` fixture that
*removes* ambient credentials, a Claude Code `SessionStart` plugin hook, a local durable JSON
artifact written through `durable_paths._atomic_write_0600`, and operator-facing gate/skill
text. No new endpoint, verb, method, client, SDK, credential, or scope is added anywhere.

The HubSpot, n8n, Anthropic and provider (Apollo / Lusha / ZoomInfo) calls the plugin already
makes are pre-existing surfaces this phase neither widens nor narrows:

- D-59-07 **reads** the response body `chunking.dispatch_plan` already receives from the n8n
  webhook it already calls. Zero new requests, zero new endpoints, zero new n8n nodes
  (see 59-01's explicit scope-out of a companies-lane create-confirmation node).
- D-59-08 routes an already-refused row into an already-existing propose lane. The read-only
  HubSpot lookups it permits are the SAME searches `preingest`/`enrichment` already perform.
- D-59-04 strips credentials; it never uses them.
- D-59-06 emits text to stdout from a shell script.

An opt-out matrix would therefore be fabricated rows. This declaration stands in its place, per
the gate's own "reasoned declaration" branch.

**Re-run trigger:** if any plan's `files_modified` grows to include `scripts/build_cloud_workflows.py`,
a new `requests`/`httpx` call site, or a new provider adapter, this declaration is void and the
full-coverage matrix must be produced before seal.
