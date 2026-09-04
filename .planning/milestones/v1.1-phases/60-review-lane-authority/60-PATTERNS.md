# Phase 60: Review-lane authority - Pattern Map

**Mapped:** 2026-09-01
**Files analyzed:** 5 (all modified, none new)
**Analogs found:** 5 / 5 (all self-analogous — this phase extends existing generic
mechanisms rather than introducing a new file/role)

This phase adds zero new files. Every file to change already contains the pattern it must be
extended with (a second lane/flag-set alongside an existing one), so each file's "analog" is
itself — the existing sibling constant/branch inside the same file, verified by direct read
this session (not RESEARCH.md's paraphrase).

## File Classification

| File to modify | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `operator-claude-plugin/scripts/write_grant.py` | service (authorization/scope) | CRUD (grant lifecycle) | itself — `LANES` dict, `WRITE_ENABLING_FLAGS` tuple, `read_live_write_state`'s per-lane loop | exact (extend existing dict/tuple, same file) |
| `operator-claude-plugin/scripts/n8n_arming.py` | service (remote config mutation) | request-response (PUT/verify against n8n API) | itself — `DISPATCH_FLAGS` + `arm_for_dispatch`/`disarm`/`armed_window` | exact (parameterize or sibling function, same file) |
| `operator-claude-plugin/scripts/review_decision.py` | service (client-side gate + HTTP POST) | request-response | itself — `submit_decision`'s existing 2-gate sequence (`is_undoing`/`submit_enabled`, then `review_armed`) | exact (swap gate 1's predicate, same file) |
| `operator-claude-plugin/scripts/written_records.py` | utility (durable per-run artifact writer) | event-driven / file-I/O | itself — `classify_item` + `append_chunk`, called from `chunking.dispatch_plan`'s per-chunk loop | partial — shape mismatch, see below |
| `operator-claude-plugin/skills/review-triage/SKILL.md` | doc/skill (operator-facing flow) | request-response (skill orchestration) | `operator-claude-plugin/skills/enrich-records/SKILL.md` step 8 (dispatch's authorize→arm→act→disarm block) and step 10 (end-of-run report) | role-match (cross-file, correct per phase brief) |

Note: `n8n/wf_review_decision_cloud.json` and `scripts/build_cloud_workflows.py` are
explicitly OUT of scope for logic changes (RESEARCH.md Anti-Patterns) — only Pitfall 5's
message-text edit touches the generator, and that is a string literal, not a pattern to map.

---

## Pattern Assignments

### `operator-claude-plugin/scripts/write_grant.py` — add `"review"` to `LANES`

**Analog:** the file's own existing 2-entry dict and its exclusion comment, lines 64-86.

**Current state (verbatim, lines 64-86):**
```python
LANES = {
    "enrichment": scheduled_arm.ENRICHMENT_WORKFLOW_NAME,
    "contacts": executions_client.CONTACT_INGEST_WORKFLOW_NAME,
}
```
This sits below a comment block (lines 64-72) that says *"THE REVIEW LANE IS DELIBERATELY
NOT GRANTABLE"* citing 30-01's D-02/D-08e — this is the comment D-60-05 requires AMENDING
(not deleting), mirroring the style of the D-59-07 amendment already present a few lines
below it (lines 74-82, headed `# D-59-07 AMENDMENT (operator, 2026-08-28):`). Copy that
amendment's shape (dated header, names the phase, explains what changed and what still
holds) for the new addendum.

**Pattern to copy — add a `REVIEW_WORKFLOW_NAME` constant beside `LANES`,** per
CONTEXT.md's own instruction (no existing constant names the review workflow; place it here
per RESEARCH.md Open Question 3's recommendation — smallest diff, only actual consumer):
```python
REVIEW_WORKFLOW_NAME = "LV Review Decision (Cloud)"

LANES = {
    "enrichment": scheduled_arm.ENRICHMENT_WORKFLOW_NAME,
    "contacts": executions_client.CONTACT_INGEST_WORKFLOW_NAME,
    "review": REVIEW_WORKFLOW_NAME,
}
```

**Guardrail widening (Pitfall 1) — two separate spots, verified live:**
- `write_grant.py:1556`: a LOCAL `WRITE_ENABLING_FLAGS = ("ALLOW_HUBSPOT_RECORD_WRITES",
  "ALLOW_HUBSPOT_CREATE")` — 2-item tuple, must gain `"ALLOW_HUBSPOT_REVIEW_WRITES"`.
- `write_grant.py:1599`: `read_live_write_state`'s loop, `for flag in
  n8n_arming.DISPATCH_FLAGS:` — RESEARCH.md's recommended fix is to swap this for
  `n8n_arming.OVERLAYABLE_FLAGS` (all 5) unconditionally per lane, since every deployed
  workflow using the shared gate already declares all 5 regardless of lane.

---

### `operator-claude-plugin/scripts/n8n_arming.py` — add review's flag set + arm/disarm

**Analog:** the file's own `DISPATCH_FLAGS` constant and `arm_for_dispatch`/`disarm`
functions, read in full this session (lines 184, 299-449).

**Existing flag table (verbatim, lines ~46-57 per RESEARCH.md, confirmed shape matches
live read):**
```python
OVERLAY_DISABLED_LITERALS = {
    "ALLOW_HUBSPOT_RECORD_WRITES": '"false"',
    "ALLOW_HUBSPOT_CREATE": '"false"',
    "ALLOW_HUBSPOT_REVIEW_WRITES": '"false"',
    "TEST_RECORD_IDS": '""',
    "TEST_RECORD_DOMAINS": '""',
}
OVERLAYABLE_FLAGS = frozenset(OVERLAY_DISABLED_LITERALS)
WRITE_ENABLING_FLAGS = frozenset({
    "ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE", "ALLOW_HUBSPOT_REVIEW_WRITES",
})
ALLOWLIST_FLAGS = frozenset({"TEST_RECORD_IDS", "TEST_RECORD_DOMAINS"})

DISPATCH_FLAGS = ("ALLOW_HUBSPOT_RECORD_WRITES", "ALLOW_HUBSPOT_CREATE",
                  "TEST_RECORD_IDS", "TEST_RECORD_DOMAINS")
```
`ALLOW_HUBSPOT_REVIEW_WRITES` is already `OVERLAYABLE` and already in `WRITE_ENABLING_FLAGS`
— add only:
```python
REVIEW_FLAGS = ("ALLOW_HUBSPOT_REVIEW_WRITES", "TEST_RECORD_IDS", "TEST_RECORD_DOMAINS")
```
Never touch `DISPATCH_FLAGS` itself (Anti-Pattern, load-bearing note).

**`arm_for_dispatch` (verbatim, lines 299-420) — the exact body to parameterize or mirror:**
```python
def arm_for_dispatch(workflow_id, record_ids, record_domains, allow_create, config,
                     transport=None, grant=None):
    ...
    refusal = _arm_gate(config, grant)
    if refusal:
        return refusal

    ids = [str(v).strip() for v in (record_ids or []) if str(v).strip()]
    domains = [str(v).strip() for v in (record_domains or []) if str(v).strip()]

    if grant is not None:
        import write_grant
        out_of_scope = write_grant.covers(
            grant, workflow_id=workflow_id, record_ids=ids, record_domains=domains)
        if out_of_scope:
            return {"outcome": REFUSED,
                    "detail": f"refusing to arm: {out_of_scope['detail']}"}

    transport = transport if transport is not None else _requests

    if not ids and not domains:
        return {"outcome": REFUSED, "detail": (
            "refusing to arm: the record allowlist is empty. The deployed "
            "_writeSafetyAllows() returns false when both allowlists are empty, "
            "so arming the flag alone would report a successful arming that "
            "grants nothing at all — worse than refusing, because it reads as success.")}

    targets = {
        "ALLOW_HUBSPOT_RECORD_WRITES": True,
        "TEST_RECORD_IDS": ",".join(ids),
        "TEST_RECORD_DOMAINS": ",".join(domains),
    }
    if allow_create:
        targets["ALLOW_HUBSPOT_CREATE"] = True
    ...
    prior = {}

    def _mutate(workflow):
        prior.update({flag: n8n_read.read_write_safety(workflow, flag).get("value")
                      for flag in DISPATCH_FLAGS})
        node_names = _declaring_nodes(workflow)
        rewritten, _counts = set_write_safety(workflow, targets)
        _assert_only_declaration_lines_changed(workflow, rewritten, node_names)
        workflow["nodes"] = rewritten["nodes"]

    def _verify(workflow):
        return {flag: n8n_read.read_write_safety(workflow, flag).get("value")
                for flag in targets}

    original = n8n_read.get_workflow(config, workflow_id, transport=transport.get)
    ...
    result = n8n_control.apply_mutation(
        workflow_id, _mutate, _declaring_nodes(original), config,
        verify_fn=_verify, transport=transport,
        action=f"arm live writes on {workflow_id} for {len(ids)} id(s) and "
               f"{len(domains)} domain(s)")
    ...
    return {"outcome": ARMED, "workflow_id": workflow_id, "prior": dict(prior),
            "observed": result.observed, "record_ids": ids, "record_domains": domains,
            "reversal": result.reversal, "consequence": (...)}
```

**Review's variant targets dict (never both booleans together — the load-bearing
separation):**
```python
targets = {
    "ALLOW_HUBSPOT_REVIEW_WRITES": True,
    "TEST_RECORD_IDS": ",".join(ids),
    "TEST_RECORD_DOMAINS": ",".join(domains),
}
# never "ALLOW_HUBSPOT_RECORD_WRITES", never "ALLOW_HUBSPOT_CREATE" in this dict
```

**`disarm` (verbatim, lines 423-438+) — the pattern for a review-side disarm:**
```python
def disarm(workflow_id, config, transport=None):
    """... Deliberately NOT gated on ALLOW_N8N_ARM ..."""
    import requests as _requests
    transport = transport if transport is not None else _requests

    targets = disarmed_targets(*DISPATCH_FLAGS)

    def _mutate(workflow):
        rewritten, _counts = set_write_safety(workflow, targets)
        workflow["nodes"] = rewritten["nodes"]

    def _verify(workflow):
        ...
```
Review's disarm: `targets = disarmed_targets(*REVIEW_FLAGS)` — `disarmed_targets` already
works with any flag tuple per RESEARCH.md (`OVERLAY_DISABLED_LITERALS` already has the
`"false"` literal for `ALLOW_HUBSPOT_REVIEW_WRITES`), zero change needed to
`disarmed_targets` itself.

**`armed_window`** (context manager wrapping arm→yield→disarm, guaranteed disarm on
exception) is the pattern D-60-06's batch arm should reuse as-is per CONTEXT.md's discretion
note — its `__exit__` guarantee ("never swallow the body's exception, still disarm") carries
over unchanged; only the flags/targets passed at construction differ.

**Note the two viable mechanisms Claude's Discretion allows (RESEARCH.md Pattern 1):** (a)
give `arm_for_dispatch`/`disarm` a `flags=DISPATCH_FLAGS` keyword the review call site
overrides, reusing one function body, or (b) add `arm_for_review`/`disarm_review` composing
the same primitives (`set_write_safety`, `n8n_control.apply_mutation`,
`n8n_read.read_write_safety`) with `REVIEW_FLAGS`. Either is consistent with this codebase's
existing generic-primitive architecture — planner picks whichever is the smaller diff.

---

### `operator-claude-plugin/scripts/review_decision.py` — swap gate 1

**Analog:** the file's own current 2-gate sequence inside `submit_decision`, read in full
(lines 84-103, 228-252).

**Current state (verbatim, lines 228-252):**
```python
UNDOING_DECISIONS = ("reject",)

def submit_enabled() -> bool:
    return os.environ.get(SUBMIT_ENV_VAR) == SUBMIT_ENV_VALUE

def is_undoing(decision) -> bool:
    word = decision.strip().lower() if isinstance(decision, str) else ""
    return word in UNDOING_DECISIONS

def submit_decision(config, object_type, record_id, decision, reason, reviewed_by,
                    review_armed, preview=None, transport=requests):
    if not is_undoing(decision) and not submit_enabled():
        return _unavailable("submit_not_enabled", message=_ENV_REFUSAL,
                            would_write=(preview or {}).get("would_write"))

    if not review_armed:
        return _unavailable("not_armed", message=_NOT_ARMED_REFUSAL,
                            would_write=(preview or {}).get("would_write"))

    body = _request_body(object_type, record_id, decision, reason, reviewed_by, False)
    return _post_decision(config, body, transport)
```

**Pattern to copy for the new gate 1 — `write_grant.authorize_send` /
`authorize_ungranted_send`'s return shape (per RESEARCH.md Reusable Assets, `{armed,
workflow_id, grant, refusal, detail}`), composed BEFORE `review_armed` (Pitfall 4 — do not
replace gate 2, only gate 1):**
```python
def submit_decision(config, object_type, record_id, decision, reason, reviewed_by,
                    review_armed, grant=None, preview=None, transport=requests):
    if not is_undoing(decision):
        auth = write_grant.authorize_send(  # or authorize_ungranted_send per D-60-07
            grant, lane="review", record_id=record_id, ...)
        if not auth.get("armed"):
            return _unavailable("grant_not_authorized", message=auth.get("refusal"),
                                would_write=(preview or {}).get("would_write"))

    if not review_armed:
        return _unavailable("not_armed", message=_NOT_ARMED_REFUSAL,
                            would_write=(preview or {}).get("would_write"))
    ...
```
`SUBMIT_ENV_VAR`/`submit_enabled()`/`_ENV_REFUSAL` are retired per D-60-04; `is_undoing` and
`UNDOING_DECISIONS` survive unchanged (D-60-07 explicitly re-points the carve-out at the
grant check rather than deleting it — resolves RESEARCH.md's Open Question 1 and Pitfall
4/A3: yes, reject bypasses gate 1 with no grant open, symmetrically with the old env-var
carve-out). `review_armed` (gate 2) is untouched — CONTEXT.md's canonical refs are explicit
this constraint (never persisted to disk, session-scoped) is unaffected by folding review
into a grant.

---

### `operator-claude-plugin/scripts/written_records.py` — D-60-08's new writer, shape mismatch

**Analog:** `classify_item` (lines 248-304) + `append_chunk` (lines 353+), the existing
per-chunk writer called from `chunking.dispatch_plan`'s loop immediately after
`responses.append(body)`.

**Existing shape `classify_item` expects (verbatim, lines 280-294):**
```python
action = item.get("action")
hs_object_id = item.get("hs_object_id") or None
object_type = item.get("object_type") or "contacts"
reason = item.get("reason")
outcome = outcome_for_action(action, hs_object_id)

entry = {
    "object_type": object_type,
    "action": action,
    "hs_object_id": hs_object_id,
    "outcome": outcome,
    "reason": reason,
    "row_id": item.get("row_id"),
    "association": item.get("association"),
}
```
This is a dispatch-response item shape (`{action, hs_object_id, object_type, reason,
row_id, association}`), fed from `chunking.dispatch_plan`'s per-chunk `responses` list.

**Shape mismatch, reported precisely per phase-mapper instructions:** the review endpoint
(`review_decision.submit_decision` → `_post_decision`) returns the FIVE-KEY contract
`{outcome, message, would_write, verified_properties, verified}` plus `{available, reason}`
(`_unavailable`'s dict, lines 148-150, and `_post_decision`'s success path). There is
**no `action`, no `hs_object_id`, no `row_id`, no `association` key anywhere in that
response** — `classify_item` cannot be called on it as-is; `outcome_for_action(action,
hs_object_id)` would receive `action=None` (since `.get("action")` on the review response is
always absent) and resolve through the `FAILED` fallback branch for every single review
decision, which is wrong (an `applied`/`rejected` review outcome is not a failure).

**No existing adapter bridges these two shapes.** The closest thing in the codebase is
`outcome_for_action`'s own docstring statement that it is "the one, pure, total,
never-raising action-to-outcome vocabulary" — but its vocabulary
(`WRITE_ACTIONS`/`ACTION_TO_OUTCOME`) is keyed on dispatch-style `action` strings
(`create`/`update`/`enrich`), not on review's `outcome` strings (`applied`/`rejected`/
`stale`/`no_candidate`/`not_flagged`/`refused`/`not_allowlisted` — see
`review_decision.WRITING_OUTCOMES`/`NON_WRITING_OUTCOMES`, lines 96-98). D-60-08's writer
needs either (a) a new small item-builder in `review_decision.py` or a call site that maps
`{outcome, record_id, object_type, reason}` into `written_records`'s entry dict directly
(bypassing `classify_item`, constructing the same 7-key entry shape by hand using
`review_decision.WRITING_OUTCOMES` to decide written-vs-not instead of `outcome_for_action`),
or (b) a new `classify_review_item`-style function beside `classify_item` in
`written_records.py` performing the equivalent mapping. Either way this is NEW plumbing per
D-60-08's own reversibility note ("review decisions... never `chunking.dispatch_plan`... new
plumbing rather than a reused call site") — do not attempt to force review responses through
`classify_item` unmodified.

**Constraints to carry over, both verified live:**
- `written_records_path(run_id)` (lines 206-216) — keyed by `run_id`, resolved fresh every
  call, never a module constant. The review call site needs its own `run_id` the same way a
  dispatch run has one (D-59-09).
- `append_chunk` (lines 353-373) — "MUST NOT raise on an I/O failure... a bookkeeping
  failure that halted a live HubSpot run would convert a missing log line into a mid-run
  stop" — this is D-59-10's constraint CONTEXT.md explicitly carries into D-60-08 ("a
  written-records failure must never stop or abort a review write"). Call this (or its
  review-side equivalent) AFTER the HubSpot write already happened, same as dispatch's call
  site sits "INSIDE the loop immediately after `responses.append(body)`," never before.

---

### `operator-claude-plugin/skills/review-triage/SKILL.md` — dispatch shape to mirror

**Analog:** `operator-claude-plugin/skills/enrich-records/SKILL.md` step 8 (authorize → arm
→ act → disarm) and step 10 (end-of-run report call) — named directly in the phase-mapper
prompt as the canonical shape; RESEARCH.md's own Reusable Assets section points at the same
step 8 code block for the `{armed, workflow_id, grant, refusal, detail}` pattern
`write_grant.authorize_send`/`authorize_ungranted_send` both return identically regardless
of lane. The review-triage skill's own Step 6 ("A yes here authorizes this record's write
and nothing else") is the per-decision confirmation UX that Pitfall 4 says must survive
unchanged underneath whichever authority gates it.

---

## Shared Patterns

### The single write-safety gate function (n8n side, UNCHANGED by this phase)
**Source:** `scripts/build_cloud_workflows.py:1177-1194` (`WRITE_SAFETY_GATE_JS`, baked into
every gate node in `n8n/wf_review_decision_cloud.json`)
```javascript
function _writeSafetyAllows(action, hsObjectId, domain) {
  if (action === "review") {
    if (String(ALLOW_HUBSPOT_REVIEW_WRITES).toLowerCase() !== "true") return false;
  } else {
    if (String(ALLOW_HUBSPOT_RECORD_WRITES).toLowerCase() !== "true") return false;
    if (action === "create" && String(ALLOW_HUBSPOT_CREATE).toLowerCase() !== "true") return false;
  }
  const allowedDomains = String(TEST_RECORD_DOMAINS).split(",").map((s) => s.trim().toLowerCase()).filter(Boolean);
  const allowedIds = String(TEST_RECORD_IDS).split(",").map((s) => s.trim()).filter(Boolean);
  if (!allowedDomains.length && !allowedIds.length) return false;
  if (hsObjectId && allowedIds.indexOf(String(hsObjectId)) !== -1) return true;
  if (domain && allowedDomains.indexOf(String(domain).toLowerCase()) !== -1) return true;
  return false;
}
```
**Apply to:** proof that arming `ALLOW_HUBSPOT_REVIEW_WRITES` alone (never
`ALLOW_HUBSPOT_RECORD_WRITES`) is sufficient and correctly isolated for the `action ===
"review"` branch — this function itself needs no code change, only its input constants get
a new writer (the Python arm function above).

### Scope check: "narrower than the grant, never wider"
**Source:** `write_grant.covers` (called from inside `arm_for_dispatch`, quoted above) —
"the ONE implementation of the scope question" per its own docstring.
**Apply to:** every lane, review included (D-60-03) — do not write a second scope-check
function for review.

### Recorded-edit discipline for amending a reversed-design comment
**Source:** `write_grant.py` lines 74-82, the existing `# D-59-07 AMENDMENT (operator,
2026-08-28):` block, sitting directly below the comment D-60-05 requires amending (lines
64-72).
**Apply to:** the new addendum documenting D-60-01/D-60-05's reversal of 30-01's D-02/D-08e
— same file, same style, dated, names the phase, explains what changed and what still holds.

## No Analog Found

None — every file in scope already contains the sibling pattern it needs extended (this is
"add a third value/branch to an existing generic mechanism," per RESEARCH.md's own framing,
not "build a new mechanism").

## Metadata

**Analog search scope:** `operator-claude-plugin/scripts/{write_grant,n8n_arming,
review_decision,written_records,chunking}.py`, `operator-claude-plugin/skills/{enrich-records,
review-triage}/SKILL.md`, `n8n/wf_review_decision_cloud.json` (read-only confirmation, no
change needed), `scripts/build_cloud_workflows.py` (targeted read, `WRITE_SAFETY_GATE_JS`).
**Files scanned:** 8 (all named in RESEARCH.md's canonical refs; each re-verified directly
this session against line numbers rather than trusted from RESEARCH.md's paraphrase).
**Pattern extraction date:** 2026-09-01
