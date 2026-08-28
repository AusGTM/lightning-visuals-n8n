# Phase 59: Frictionless write path - Pattern Map

**Mapped:** 2026-08-28
**Files analyzed:** 6 (new) + 5 (modified)
**Analogs found:** 10 / 11

**Scope pins honored:** FINDING 2 / `merge_enriched` NOT re-mapped for a fix (already shipped,
commit `9e603d6`, `preingest.py:528-537`) — mapped below only as a raise-instead-of-swallow
analog. Phase 53 walk tooling excluded. D-59-08 mapped as the full gate surface named in the
task brief, not just `extraction.py`.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `tests/conftest.py` (NEW, repo root) | test infrastructure | request-response (fixture) | `operator-claude-plugin/tests/conftest.py`'s `no_network` fixture | role-match (same idiom, different resource being stripped) |
| `operator-claude-plugin/hooks/hooks.json` (NEW) | config | event-driven (SessionStart) | `~/.claude/plugins/marketplaces/stz-marketplace/hooks/hooks.json` | exact (external precedent, no in-repo analog exists) |
| `operator-claude-plugin/hooks/session-start.sh` (NEW) | utility (hook script) | event-driven | none in-repo; script itself has no analog, only its JSON wiring does | no analog — see below |
| `operator-claude-plugin/scripts/chunking.py` (MODIFIED — `dispatch_plan` loop) | orchestration/service | batch, event-driven | itself (existing loop) + `durable_paths.py`'s atomic-write primitive | exact (extend existing function with existing primitive) |
| `operator-claude-plugin/scripts/durable_paths.py` (REUSED, likely unmodified) | utility | file-I/O | n/a — this IS the analog for D-59-07's persistence | exact |
| written-records artifact writer (fold into `chunking.py` or a thin new module) | utility | file-I/O, append-only | `operator-claude-plugin/scripts/artifact_store.py` | role-match |
| `operator-claude-plugin/skills/contact-upload/extraction.md` (MODIFIED, 2 passages) | operator-facing skill contract (prose) | request-response | itself — verbatim text already quoted in RESEARCH.md | exact (in-place edit) |
| `operator-claude-plugin/scripts/extraction.py` (MODIFIED — identity gate wiring) | validation/gate | request-response | `operator-claude-plugin/scripts/company_domain.py` (resolve/propose lane) | exact (same resolve-then-propose shape, different field) |
| `tests/test_conftest_credential_guard.py` (NEW) | test | unit | `operator-claude-plugin/tests/conftest.py`'s own test-of-fixture style + `tests/test_scoring_parity.py`'s `RUN_LIVE_PARITY` skipif idiom | role-match |
| `operator-claude-plugin/tests/test_write_grant.py` (MODIFIED — extend revocation test) | test | integration | `test_a_revocation_midway_does_not_stop_a_running_dispatch` at line 1153, same file | exact (extend, don't duplicate) |
| D-59-07 crash-survival test (NEW, likely in `operator-claude-plugin/tests/`) | test | unit | `stub_module_transport_factory` fixture used by the revocation test (same file) | role-match |

## Pattern Assignments

### `tests/conftest.py` (NEW — repo root)

**Analog:** `operator-claude-plugin/tests/conftest.py` lines 1-13, 573-592 (the `no_network` fixture)

**The exact precedent to copy the shape of** (VERIFIED, read this session):
```python
@pytest.fixture(autouse=True)
def no_network(monkeypatch, request):
    """Any requests.post/request/Session.request call inside a test raises immediately.

    Autouse so a later plan's test cannot opt out by forgetting to request a fixture — the
    guard applies to every test in this suite by construction, not by discipline.
    """
    test_name = request.node.name

    def _blocked(*args, **kwargs):
        raise RuntimeError(
            f"Network access blocked in test '{test_name}': plugin tests must use "
            "stub_transport instead of a real requests call."
        )

    monkeypatch.setattr(requests, "post", _blocked)
    monkeypatch.setattr(requests, "request", _blocked)
    monkeypatch.setattr(requests.Session, "request", _blocked)
```

**Critical divergence from the analog (do not copy this part):** the plugin's `no_network` is
UNCONDITIONAL — that suite has no live tests. The new root fixture MUST be conditional, gated on
the identical env var the two existing live tests already use (`RUN_LIVE_PARITY`), never on a
pytest marker named `live` (no such marker is registered anywhere in this repo — confirmed by
`grep -rln '\[pytest\]' .` returning zero hits). Shape to follow instead, from RESEARCH.md
Pitfall 1 / Code Examples:

```python
# tests/test_scoring_parity.py:48-54 — VERIFIED, the existing opt-in idiom to mirror
live = pytest.mark.skipif(
    os.getenv("RUN_LIVE_PARITY") != "true",
    reason="Set RUN_LIVE_PARITY=true to run live-service parity tests",
)
```

The new fixture's gate must read `os.getenv("RUN_LIVE_PARITY") != "true"` directly (not a
marker lookup) and skip stripping when that is `"true"`, because autouse fixtures run for a
test whose `skipif` evaluates to "don't skip" — proven live in this session's research pass.

**Anthropic client construction sites the guard protects** (`src/classifier_haiku.py:47,57`,
`src/validator_sonnet.py:23,36`, `src/web_research.py:119,126` — all VERIFIED, quoted in full
in RESEARCH.md § Code Examples). Two are self-guarding once the key is absent; `web_research.py`
has no local guard and relies entirely on the strip.

---

### `operator-claude-plugin/hooks/hooks.json` + `hooks/session-start.sh` (NEW)

**Analog:** `~/.claude/plugins/marketplaces/stz-marketplace/hooks/hooks.json` (external,
installed, live in this environment — VERIFIED)

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"${CLAUDE_PLUGIN_ROOT}/hooks/session-start.sh\""
          }
        ]
      }
    ]
  }
}
```
`operator-claude-plugin/` currently has no `hooks/` directory at all (VERIFIED:
`find operator-claude-plugin -maxdepth 1 -type d` lists no `hooks`). This is new infrastructure,
not an extension.

**Relay convention to follow for the script's stdout text** (analog: `initialize/SKILL.md` step
1, "Read its output back to the operator in your own words") — the script should emit an
instruction for Claude to relay, not assume verbatim echo to the human. This is inferred (A1 in
RESEARCH.md), not directly observed for a hook in this specific plugin — flagged for the
planner, not settled.

---

### `operator-claude-plugin/scripts/chunking.py` — `dispatch_plan` loop (MODIFY)

**Analog:** itself (the exact hook point), plus `durable_paths.py`'s atomic-write primitive.

**The exact loop and hook point** (VERIFIED, `chunking.py:279-313`):
```python
for index, chunk in enumerate(plan.chunks):
    ...
    body = enrichment.dispatch_enrichment(envelope, armed, config, transport=watcher)
    ...
    responses.append(body)          # <-- durable write must happen right here, per chunk,
                                     #     not after the loop via the returned DispatchOutcome
    if reason is not None:
        failed_chunks.append(chunk)

return DispatchOutcome(
    results=tuple(results),
    failed_batch=failed_batch(failed_chunks),
    responses=tuple(responses),
)
```
D-59-07 requires the artifact write to happen inline, immediately after `responses.append(body)`,
not after the loop — a crash of the calling process between chunks must not lose prior chunks'
written-record data.

**Durable-write primitive to reuse (do not hand-roll atomic writes):**
`operator-claude-plugin/scripts/durable_paths.py`'s `resolve_state_path()` and
`_atomic_write_0600` (lines 44-234, VERIFIED referenced in RESEARCH.md — read this file directly
before implementing; it is the plugin's one existing precedent for durable local state).

**Companies-lane gap flagged by RESEARCH.md (Open Question 1 / Pitfall 2):** the contacts lane's
write-confirmation source exists (`Build Ingest Response`, below); no equivalent post-write
`hs_object_id` resolution was found for companies in this research pass — `Decide Company
Action`'s output is a pre-write decision, not proof of a write (its `create` rows carry
`hs_object_id: null`). Verify this directly before assuming parity between lanes.

**Contacts-lane write-confirmation shape to read `hs_object_id` from** (VERIFIED,
`scripts/build_cloud_workflows.py:471-520`, the source the generator writes into the deployed
n8n `Build Ingest Response` node):
```javascript
return decided.map((row) => {
  return { json: {
    action: row.action,
    outcome: row.outcome || null,
    contact_id: contactId,
    hs_object_id: contactId,
    email: email || null,
    company_id: row.company_id || null,
    company_match: row.company_match || null,
    association,
    reason: row.reason || null,
    email_status: row.email_status || null,
  }};
});
```
Every decided row appears here, including held/gated rows, by design — the flattening idiom
(`chunking.py:93-96`) must be applied before reading rows out of `responses`:
```python
[item for body in outcome.responses for item in (body if isinstance(body, list) else [body])]
```

**Reuse warning (Don't Hand-Roll, from RESEARCH.md):** do not build a new indexing/merge
function for joining responses to rows — reuse `preingest.merge_enriched`'s row_id-keyed join
discipline (now fixed, raises `MergeError` on malformed shape rather than silently discarding).

---

### `operator-claude-plugin/scripts/preingest.py` — `merge_enriched` (ALREADY FIXED, reference only)

**Not phase scope to fix.** Shipped shape, useful as the raise-instead-of-swallow analog for
any new code this phase writes that touches response shapes (`preingest.py:528-537`, commit
`9e603d6`, plugin 0.20.0):
```python
# now raises MergeError on a non-dict response item, instead of silently indexing it
# as row_id: None and filing it under `unanswered`.
```
Any new D-59-07/D-59-08 code that does its own ad hoc indexing into `dispatch_plan(...).responses`
must follow this same fail-loud discipline rather than reintroducing the pre-fix silent-loss
shape (RESEARCH.md Pitfall 3).

---

### `operator-claude-plugin/skills/contact-upload/extraction.md` (MODIFY, 2 passages)

**Analog:** itself — exact text to amend, both locations VERIFIED with line numbers.

**Passage 1** (`extraction.md:27-30`):
```
3. **Never fill a gap to make a row satisfy the identity rule** (a non-blank `email`, or all
   three of `firstname`/`lastname`/`company`). A row that gets rejected with a stated reason is
   the correct outcome. A row you completed just to get it past that check is not — it is
   invention with extra steps.
```

**Passage 2** (`extraction.md:364-368`):
```
The rule at the top of this file governs company rows exactly as it governs contact rows: a
field the source does not show is left out of the row entirely, a value the source renders
unclearly goes in the ambiguity list rather than the row, and a company name is never invented
to make a nameless row pass the identity check. A company row rejected with a stated reason is
the correct outcome here too — never fill a gap just to get it past the check.
```

**Rewrite discipline (per D-59-08):** the "Never fill a gap…" sentence in BOTH passages survives
verbatim, unchanged. Only the "rejected with a stated reason is the correct outcome" clause in
each is rewritten to make rejection the last resort, after a resolve-and-propose attempt failed
or was declined. Use the same recorded-edit discipline D-53-05 used elsewhere in this codebase
(reason and date written into the file itself, nothing silently deleted).

**No pinning test found** — `grep -rln "rejected with a stated reason" tests/*.py
operator-claude-plugin/tests/*.py` returns nothing (VERIFIED in RESEARCH.md). Do not spend
planning effort hunting for one.

---

### `operator-claude-plugin/scripts/extraction.py` (MODIFY — identity gate)

**Analog:** `operator-claude-plugin/scripts/company_domain.py` — Phase 58's resolve/confirm/
decline lane, the exact resolve-then-propose shape D-59-08 asks to reuse.

```python
# operator-claude-plugin/scripts/company_domain.py — module docstring, VERIFIED
# "Phase 58's domain confirm/decline lane (INPUT-03): a company row Claude (or the
# backend's research) resolved a candidate domain for is not silently written — it is
# proposed, and the operator must confirm, correct, or decline before it becomes part of
# the envelope."
#
# apply_domain_decisions(proposals, resolved) -- never mutates input; DomainDecisionError
# raised for: no decision recorded, an unrecognized decision value, or a decision naming a
# row that was never proposed. Vocabulary: confirm / correct / DECLINE_DOMAIN sentinel.
```

Also reuse rather than reinvent: `preingest.py`'s existing `proposed` / `auto_matched` /
`unmatched` / `unchecked` grouping (`classify_matches`, `resolve_proposed`) and its
`approve`/`deny`/`pick`/`email:` vocabulary, and the enrichment backend's own
`action: "proposed"` / `mode: "propose"` response shape (confirmed live in
`53-WALK-RECORD.md` Step 7: `action: proposed / mode: propose / needs_review: true`).

**Legitimate vs illegitimate resolution sources** (the acceptance criteria the gate's rewrite
must preserve — from CONTEXT.md D-59-08, restated here because it is the input-validation
contract the analog's tests must keep enforcing):

| Legitimate | Illegitimate |
|---|---|
| HubSpot itself, read-only | Claude's own recall/training-data knowledge |
| The operator's own prior conversation statements | Inference from "companies like this usually…" |
| The enrichment waterfall's provider results | A plausible corporate email pattern |
| Another field of the same row, by stated derivation | Anything the operator has no way to check |

**Provenance requirement:** a Claude-resolved value must carry provenance saying so — never
dressed as source-derived. No existing field/vocabulary for this was found reused as-is;
planner should check whether `company_domain.py`'s decision vocabulary already carries a
provenance marker to extend, or whether a new field is needed.

---

## Shared Patterns

### Autouse pytest fixture gated on an existing env-var convention (not a marker)
**Source:** `operator-claude-plugin/tests/conftest.py` (`no_network`) + `tests/test_scoring_parity.py:48-54` (`RUN_LIVE_PARITY`)
**Apply to:** `tests/conftest.py` (D-59-04)
Structural guard ("by construction, not discipline") combined with the repo's one real live-test
gating convention. No new pytest config/marker registration — none exists anywhere in this repo.

### Resolve-then-propose, never resolve-then-silently-fill
**Source:** `operator-claude-plugin/scripts/company_domain.py`, `preingest.py`'s propose grouping
**Apply to:** `extraction.py` (D-59-08), and any other operator-facing gate a later phase widens
Never invent a mechanism — an operator-confirm-or-decline lane already exists; wire the gate to
reach it instead of terminating in refusal.

### Fail loud on shape mismatch, never silently index/drop
**Source:** `preingest.py:528-537` (`merge_enriched`, post-fix)
**Apply to:** any new code in D-59-07/D-59-08 that reads `dispatch_plan(...).responses`
Flatten with the documented idiom (`chunking.py:93-96`) before touching row-level data; raise
rather than skip on an unexpected shape.

### Durable atomic writes for local plugin state
**Source:** `operator-claude-plugin/scripts/durable_paths.py` (`resolve_state_path`, `_atomic_write_0600`)
**Apply to:** the D-59-07 written-records artifact
Reuse the plugin's one existing durable-state primitive; do not add a new file-locking helper.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `operator-claude-plugin/hooks/session-start.sh` (the script body's operator-facing note text) | utility | event-driven | No prior hook script exists in this plugin; only the JSON wiring shape has a precedent (external plugin). Text content is new prose, not a code pattern. |
| Companies-lane post-write confirmation (if D-59-07 needs one) | n8n node / response shape | request-response | RESEARCH.md Open Question 1 — no equivalent of `Build Ingest Response` was found for companies; may need a new addition via `scripts/build_cloud_workflows.py` (Phase 46 parity rule), not a copy of an existing node. |

## Metadata

**Analog search scope:** `operator-claude-plugin/scripts/`, `operator-claude-plugin/tests/`,
`operator-claude-plugin/skills/contact-upload/`, `src/` (Anthropic client sites),
`~/.claude/plugins/marketplaces/` (external hook precedent), `scripts/build_cloud_workflows.py`.
**Files scanned:** ~15, all previously read/verified in `59-RESEARCH.md` plus 3 direct
confirmation reads this pass (`conftest.py` header, revocation test location, no-invention test
function list).
**Pattern extraction date:** 2026-08-28
