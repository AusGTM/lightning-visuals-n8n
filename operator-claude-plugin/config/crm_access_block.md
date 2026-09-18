<!-- CRM-ACCESS-BLOCK v1 (D-14a/D-14b/D-14d, D-15a/D-15b/D-15c/D-15d) -->
<!-- Canonical source: operator-claude-plugin/config/crm_access_block.md -->
<!-- Do not edit this block inside a SKILL.md. Edit the canonical file above and copy it -->
<!-- verbatim into every skill; test_crm_access_block.py pins that every copy matches. -->

**Before any HubSpot access this session, read this.**

**Portal rule (D-14a).** Any HubSpot tool outside this plugin's own lanes — the claude.ai
HubSpot connector, an MCP HubSpot server, the `hs` CLI — must prove IT is on portal
`22617666` before its first call this session, read or write. The proof is that tool
looking up, through itself, a record this plugin knows exists: an `hs_object_id` from
`written_records`, or the configured sentinel id. Zero results is the lookup proof
failing — it means the wrong portal: stop the step and say so, naming the portal the
plugin expects and the record that was not found. Do not retry, do not fall back to a
plugin lane silently, and do not treat a zero result as "the record does not exist." The
2026-09-18 session's connector was on a different portal and returned zero results for
contacts the plugin had just created — this rule exists to stop exactly that. This rule
is skill text the assistant follows when reading this skill; there is no runtime hook
and no code gate enforcing the portal proof.

**Connector-write rule (D-14b).** A write through such a tool, once its portal is
proven, is under the SAME session grant as every other write path: call
`write_grant.covers()` before it, append the outcome to `written_records` with
`source: connector`, and associate a created contact to its company in the same step,
exactly as the ingest lane does. One yes governs all paths.

**Session-grant rule (D-15a/b/c/d).** The first yes covers the whole session — every
lane, and the domains and ids named in that proposal. Every later send goes through
`covers()` on that one grant. A send outside its record set widens the grant with
`widen()` and STATES the widening; it never asks again and never opens a second grant.
A second `open_grant` while one is open is refused by the code, naming the open grant.
The ask itself is one sentence: this yes covers every send this session across the
named lanes for the named domains, widening as new domains appear, and the operator may
say revoke at any time (`CLOSED_REVOKED`).

<!-- END CRM-ACCESS-BLOCK -->
