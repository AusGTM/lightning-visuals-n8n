# Phase 24: Non-Tabular Input Adapters - Context

**Gathered:** 2026-07-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 24 adds the input adapters that Phase 23 deliberately left out: pasted prose, foreign-shaped
JSON, a public URL, and operator-supplied screenshots. Each adapter's only job is to produce
canonical contact rows plus the guarantees that make an extracted row trustworthy — provenance,
no-invention, identity-rule separation, and named errors.

Every adapter feeds **the same choke point Phase 23 built**: preview → approve → arm → dispatch.
This phase adds no new dispatch path, no new endpoint, and no second preview.

Still not in scope: column mapping, phone normalization, email verification, identity resolution,
and dedupe against HubSpot — all server-side in n8n. Phase 24's identity-rule check is a *local
pre-flight* that separates rows too thin to be useful; it is not a dedupe against the CRM.

</domain>

<decisions>
## Implementation Decisions

### Extraction engine
- **D-01:** Extraction is performed by **Claude in-session, with no Anthropic API call**. The
  `SKILL.md` instructs Claude to read the prose, JSON, fetched page, or image and emit canonical
  rows directly into the conversation. Python's role is narrow: validate row shape, apply the
  identity rule, dedupe, and assemble the payload. — **Reversibility:** costly — moving to an API
  extractor later means adding a key-handling path, a pinned model, and a prompt artifact that do
  not exist in this design, and re-testing every adapter's no-invention behavior.
- **D-02:** Consequences of D-01 that the planner must honor: **no Anthropic API key ever enters
  the plugin** (keeps PLUGIN-02's spirit intact even after the Phase 23 amendment), extraction
  costs nothing per batch, and images are read natively rather than base64-shipped. The trade-off
  accepted: extraction quality tracks whatever model runs the session rather than being pinned to
  a version.
- **D-03:** The no-invention guarantee (STRUCT-04) is therefore a **prompt-and-validation
  contract**, not a model property. The skill must state the rule explicitly, and the Python
  validator must reject any row carrying a field the operator's source demonstrably could not
  have supplied where that is checkable. Absent stays absent.

### Provenance
- **D-04:** Provenance is a **preview-only sidecar, stripped before dispatch**. Each extracted row
  carries a parallel provenance record (which input, which span of text / which image and where on
  it) that renders as extra columns in the preview and is **removed from the POST body**. This
  keeps STRUCT-01 exactly true — n8n receives canonical props only.
- **D-05:** Provenance does **not** persist beyond the session and is **not** written to HubSpot.
  Its audience is the operator deciding whether to approve, at the moment they decide.

### Ambiguity handling
- **D-06:** Ambiguous values are **collected into a single list presented with the preview** — one
  "needs your eyes" block covering every ambiguous cell in the batch. The operator confirms or
  corrects them in one reply before approving. One interruption per batch, never one per row.
- **D-07:** An unconfirmed ambiguity is **not** silently resolved. If the operator approves without
  addressing it, the affected value stays absent rather than being filled with the model's best
  guess. (Direct consequence of STRUCT-04.)

### Screenshot overlap
- **D-08:** Duplicate detection across a scrolled screenshot sequence uses **the existing identity
  rule**: same `email`, or same `firstname` + `lastname` + `company`. One dedupe concept across
  the whole system — the same rule n8n applies server-side.
- **D-09:** Near-duplicates that differ only in a truncated or unreadable field surface as
  **ambiguities** (D-06), not as silent collapses. The operator decides whether two partial
  captures are one person.

### Claude's Discretion
- Foreign-JSON key-translation approach, and how unmappable keys are reported (criterion 2
  requires only that they are reported, not silently dropped).
- Wording and shape of the per-row rejection reasons for identity-rule failures (STRUCT-02).
- How provenance columns are laid out in the preview table.
- Error taxonomy for unreadable / empty / unsupported input (INGEST-06) — the requirement is a
  named error, not a specific naming scheme.
- Whether the URL adapter summarizes the fetched page before extraction or extracts directly.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 23 output — the shell this phase plugs into
- `.planning/workstreams/plugin-entrypoint/phases/23-walking-skeleton-plugin-shell-tabular-dispatch/23-CONTEXT.md`
  — locked decisions for the shell. D-07 (pass-through + read-only mapping preview), D-08 (adaptive
  preview scope), D-09 (chat-first rendering), and D-11 (conversation-only arming) all constrain
  this phase. Adapters feed that preview; they do not replace it.
- `operator-claude-plugin/README.md` — the plugin's stated design posture: deliberately thin, no
  backend logic.

### Milestone scope and requirements
- `.planning/workstreams/plugin-entrypoint/REQUIREMENTS.md` — INGEST-01/03/05/06/07 and
  STRUCT-02/03/04 are this phase. §"Out of Scope" is binding and unusually load-bearing here: no
  user-agent obfuscation, no viewport emulation, no anti-bot technique, no authenticated or
  paywalled scraping, and **no automated screenshot capture** — the operator hands over images
  they already have. A screenshot is explicitly not a route around the scraping exclusions;
  LinkedIn profile fields still come from the licensed provider waterfall.
- `.planning/workstreams/plugin-entrypoint/ROADMAP.md` §"Phase 24" — goal and six success criteria.

### Backend contract (read-only)
- `config/column_mapping.yaml` — the canonical prop set adapters must emit over. Read-only.
- `n8n/wf_contact_ingest_cloud.json` — `Map Columns` defines what canonical means. **Corrected by
  24-RESEARCH.md:** the identity rule (`email` OR `firstname`+`lastname`+`company`) that D-08 and
  STRUCT-02 mirror lives in `Map Columns`' `requiredIdentity()` (trim-then-presence-check), **not**
  in `Resolve Identity` / `Merge Contacts` — those are CRM-dedupe matching and are out of scope.
  Note also that `src/file_loader.py::_has_identity` does **not** trim whitespace, unlike the live
  n8n JS; the client-side validator must trim and must not be copied from that function.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- The Phase 23 preview, approval, arming, and dispatch path — reused wholesale. Phase 24 adds
  producers in front of it, nothing behind it.
- The identity rule, already implemented server-side and now mirrored locally as a pre-flight
  separator (STRUCT-02) and an overlap-dedupe key (D-08).
- Native `web_fetch` for the URL adapter — mandated by criterion 3, so no HTTP-scraping client is
  built here.

### Established Patterns
- **The backend owns transformation.** Local identity checking is a pre-flight filter, not a
  reimplementation of `Resolve Identity`.
- **No-invention over completeness.** The repo's enrichment side already prefers `unknown` to a
  guess (see the research adapter's "prefer unknown over guessing" rule in CLAUDE.md §14.2).
  D-03 is the same principle applied to extraction.

### Integration Points
- Adapters emit into the Phase 23 preview structure — this is the single integration seam and the
  place STRUCT-01 is enforced.
- Provenance attaches alongside rows and is stripped at payload assembly (D-04). That strip point
  is the enforcement site for "canonical props only".
- No new network call except native `web_fetch`.

</code_context>

<specifics>
## Specific Ideas

- The four adapters are not equally risky: screenshots carry both the ambiguity problem and the
  overlap problem, and are the only input where the source can be genuinely unreadable. Prose is
  the volume case. Foreign JSON is the mechanical case. The URL adapter is mostly a `web_fetch`
  call feeding the prose path.
- "Reported rather than silently dropped" recurs across criteria 2, 5, and 6. Silence is the
  failure mode this whole phase is defending against.

</specifics>

<deferred>
## Deferred Ideas

- **Persistent provenance / audit archive** — D-05 keeps provenance session-scoped. A durable
  per-batch audit file was considered and deferred; it raises a retention question this milestone
  has not scoped.
- **Pinned-model extraction** — D-01 accepts session-model variance. Revisit if extraction quality
  proves unstable across model versions.
- **Company-object ingestion** — out of milestone (v0.6 is contacts + enrichment triggers only).
- **Automated screenshot capture** — permanently out of scope, not deferred. Explicit exclusion.
- **Cost estimation for extraction** — Phase 25 / PREVIEW-02. D-01 makes extraction free of
  provider and API cost, so the cost guard covers dispatch, not extraction.

</deferred>

---

*Phase: 24-non-tabular-input-adapters*
*Context gathered: 2026-07-30*
