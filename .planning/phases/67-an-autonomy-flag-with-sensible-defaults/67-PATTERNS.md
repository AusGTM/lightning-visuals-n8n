# Phase 67: An autonomy flag with sensible defaults - Pattern Map

**Mapped:** 2026-09-07
**Files analyzed:** 12 (2 new, 10 modified)
**Analogs found:** 12 / 12 — every mechanism this phase needs already exists in the repo and
is reused, per 67-RESEARCH.md's own "Don't Hand-Roll" table. All analog paths verified
git-tracked (`git ls-files`) under `operator-claude-plugin/`, a normal tracked directory, not
a `.gsd/capabilities/` mirror.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `operator-claude-plugin/scripts/config_gate.py` | config | request-response (pure read) | itself — `CAPABILITY_KEYS` + `write_grants_enabled` (same file) | exact (extend, don't replace) |
| `operator-claude-plugin/config/operator.local.example.json` | config | — | itself — `allow_write_grants` + `_allow_write_grants_note` sibling-key idiom | exact |
| `operator-claude-plugin/scripts/autonomy_gate.py` (**new**) | utility (pure refusal predicate) | request-response | `write_grant.ceiling_verdict` (`write_grant.py:319-364`) | role-match (same "pure, no I/O, returns a verdict dict" shape) |
| `operator-claude-plugin/skills/contact-upload/SKILL.md` | route (skill/orchestration prose) | CRUD (write) | `enrich-before-ingest/SKILL.md` (`build_run_report` call ~line 1038) | exact (report wiring) |
| `operator-claude-plugin/skills/suggest-contacts/SKILL.md` | route | request-response (spend-no-write) | `enrich-records/SKILL.md` (`build_run_report` call ~line 597) | exact (report wiring) |
| `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` | route | CRUD (write) | Phase 68's own implicit-open sequence in the same file (`plan_grant` → `watch.pre_spend_pause()` → `open_grant`) | exact (insert refusal before pause) |
| `operator-claude-plugin/skills/enrich-records/SKILL.md` | route | CRUD (write) | same Phase 68 implicit-open sequence, this file | exact |
| `operator-claude-plugin/skills/backend-status/SKILL.md` | route (read-only) | request-response | itself — no changed-posture prose today; closest sibling is `backend-control/SKILL.md:113-116`'s existing hook paragraph | role-match |
| `operator-claude-plugin/skills/backend-control/SKILL.md` | route | event-driven (arm/deploy) | itself, lines 95-120 — the paragraph Phase 68 already wrote naming Phase 67 as the opener | exact (edit in place, do not touch mutation logic) |
| `operator-claude-plugin/CHANGELOG.md` + `.claude-plugin/plugin.json` | config (release) | — | itself — existing release-checklist pattern, version currently `0.40.0` | exact |
| `operator-claude-plugin/tests/test_autonomy_levels.py` (**new**) | test | request-response | `tests/test_write_grant.py` (verdict-table style tests) | role-match |
| `operator-claude-plugin/tests/test_headless_grant_boundary.py` | test | event-driven (AST scan) | itself — extend only if a new absence-pin is needed; do not modify existing 3 tests | exact |
| `operator-claude-plugin/tests/test_implicit_approval_contract.py` | test | request-response | itself — `TARGETS`-style table | exact (extend table) |
| `operator-claude-plugin/tests/test_disclosure_audit.py` | test | request-response | itself — `AUDIT` dict + `PRESERVED_LITERALS` | exact (add D-61-08 pin) |
| `operator-claude-plugin/tests/test_report_enrichment.py` | test | request-response | itself — `_FORBIDDEN_SUBSTRINGS` scan | exact (no change needed, re-run only — governs new prose) |
| `operator-claude-plugin/tests/test_skill_sequence_coverage.py` | test | request-response | itself — `MAX_GRANDFATHERED = 0` ratchet | exact (register any new multi-call fence) |

## Pattern Assignments

### `operator-claude-plugin/scripts/config_gate.py` (config, extend)

**Analog:** itself, `CAPABILITY_KEYS` (lines ~57-76) and `write_grants_enabled` (lines ~104-121)

**Do NOT reuse `write_grants_enabled`'s identity-on-absence shape for the new keys** — that
pattern means "absent → OFF" and is reserved for AUTHORITY gates. The new autonomy keys are a
DEFAULT-SETTER (D-67-02) and must default to `True` when absent (D-67-03/D-67-10).

**Existing authority-gate pattern** (`config_gate.py:104-121`, for contrast — do not copy):
```python
WRITE_GRANT_SETTINGS_KEY = "allow_write_grants"

def write_grants_enabled(config: dict) -> bool:
    """True only when the admin set the key to the JSON boolean `true`. ...
    Identity (`is True`), not truthiness ...
    """
    return (config or {}).get(WRITE_GRANT_SETTINGS_KEY) is True
```

**New pattern to add** (default-setter, explicit `True` default, distinct in kind — comment
this distinction at the read site so a future reader does not "fix" it into the wrong shape):
```python
AUTONOMY_SETTINGS_KEY = "autonomy"
AUTONOMY_LEVELS = ("read_only", "spend_no_write", "write")  # D-67-01 — three, independent

def autonomy_enabled(config: dict, level: str) -> bool:
    """True unless the admin explicitly set this level's key to false.

    NOT `write_grants_enabled`'s identity-on-absence shape. This key is a DEFAULT-SETTER
    (D-67-02) layered on top of authority already granted elsewhere (allow_write_grants /
    ALLOW_N8N_ARM) — it never authorises anything by itself. D-67-03/D-67-10: an existing
    install with no `autonomy` key present must read every level as ON, so the Python-level
    default here is `True`, not `False`. Do not copy write_grants_enabled's `is True`
    identity check onto this function — that would make an absent key read as OFF and
    silently violate D-67-03.
    """
    assert level in AUTONOMY_LEVELS
    return (config or {}).get(AUTONOMY_SETTINGS_KEY, {}).get(level, True) is not False
```
(`is not False` rather than plain truthy-check keeps `"false"`/`0`/`1` from parsing as an
override — mirrors the exact-value-only spirit of the authority gates, applied to the
opposite default.)

**`CAPABILITY_KEYS`'s row-per-capability table shape** (lines ~57-76) is the precedent for
"three independently named settings, not one flat boolean" — cited as the reason three keys
nested under `autonomy` beat a single boolean (research's own recommendation, D-67-01's
requirement that the tiers be independently defaultable).

---

### `operator-claude-plugin/config/operator.local.example.json` (config)

**Analog:** itself — the `allow_write_grants` / `_allow_write_grants_note` sibling-key idiom
(lines 17-18), and `n8n_monthly_execution_allowance` / `_n8n_monthly_execution_allowance_note`
(lines 6-7) as a second example of the same idiom for a non-boolean key.

**Existing note excerpt** (line 18, the idiom to copy verbatim in structure):
```json
"allow_write_grants": false,
"_allow_write_grants_note": "Lets an operator open a WRITE GRANT in conversation: ... Absent, false, the string \"true\", 1 or \"yes\" all mean OFF: only the JSON boolean true authorizes ... It does NOT replace ALLOW_N8N_ARM ...",
```

**New keys to add**, same idiom, opposite default and opposite absence semantics — the note
text must say so explicitly since it directly contradicts the neighboring `allow_write_grants`
note's "absent means OFF" framing:
```json
"autonomy": {
  "read_only": true,
  "spend_no_write": true,
  "write": true
},
"_autonomy_note": "Per-function default: whether a batch proceeds without asking, once already authorised by allow_write_grants (interactive) or ALLOW_N8N_ARM (headless) — this key is a DEFAULT-SETTER, never a third authority gate (D-67-02). Unlike allow_write_grants above, an ABSENT key or level here reads as ON, not off (D-67-03: an existing install moves to the new defaults on update). Setting a level to false reverts that level's rounds to asking first. Levels: read_only (status/queue reads), spend_no_write (match/propose), write (ingest/enrich-write/review-apply). backend-control's own arm/deploy/structural mutations are not covered by any of these three and always confirm-and-wait (D-67-12)."
```

---

### `operator-claude-plugin/scripts/autonomy_gate.py` (**new file** — utility, pure predicate)

**Analog:** `write_grant.ceiling_verdict` (`write_grant.py:319-364`) — same shape: pure, no I/O,
takes verdict dicts already computed elsewhere, returns a small result dict with a `verdict`
key and a `reason` string.

**Core pattern to copy** (structure, not logic — `ceiling_verdict` excerpt):
```python
def ceiling_verdict(figures, headroom) -> dict:
    """Pure, no I/O: compare a batch's projected execution count against a sampled
    monthly remainder (Phase 57, D-57-01). ...
    """
    headroom = headroom or {}
    projected = (figures or {}).get("projected_executions")
    sampled = bool(headroom.get("sampled"))
    ...
    return {
        "verdict": verdict,
        "projected_executions": projected,
        ...
        "reason": reason,
    }
```

**IMPORTANT — D-67-09 reverses D-67-05.** Per the operator's 2026-09-07 planning-time ruling
(CONTEXT.md, binding), do NOT build a refusal on `CEILING_UNKNOWN` / unread balance / missing
allowance key. Autonomy ON **discloses the unknown state and proceeds**, identical to Phase
68's existing `plan_grant` behavior (`write_grant.py:1111-1120`, excerpted below) — the earlier
67-RESEARCH.md "Design for the new refusal" section and D-67-05 are superseded by D-67-09 and
must NOT be implemented as a refusal. The only bound that still refuses is `CEILING_OVER`
(already built, unchanged) and `CapRefused`. If `autonomy_gate.py` is still useful as a named
seam (e.g. to state the disclosure line distinctly for an autonomous vs. interactive round),
keep it a pure pass-through/labeling function, never a refusal path.

**`plan_grant`'s existing CEILING_OVER-only refusal** (`write_grant.py:1111-1150`, unchanged,
reused as-is — this is the ONE refusal surface this phase's D-67-13 relies on for RUN-05):
```python
    # DELIBERATE DIVERGENCE FROM `n8n_cadence.check_budget_floor`'s own analog ...
    # A `CEILING_UNKNOWN` verdict proceeds with the blind spot disclosed, per D-57-02 ...
    # Only `CEILING_OVER` refuses.
    ceiling = figures["ceiling"]
    if ceiling["verdict"] == CEILING_OVER and not override:
        # D-57-04, option-a: the refusal carries a concrete offer alongside the arithmetic.
        ...
```
Under autonomy this refusal must land loudly in the mandatory report (D-67-13), never be
silently swallowed — no new split-execution logic (RUN-05 stays a documented limitation).

---

### `operator-claude-plugin/skills/contact-upload/SKILL.md` and `suggest-contacts/SKILL.md` (route, wire in report)

**Analog:** `enrich-before-ingest/SKILL.md` (~line 1038) and `enrich-records/SKILL.md` (~line
597), which already call the report builder at end-of-run.

**Pattern to copy** (call shape — locate the exact call in the analog file at plan time and
copy the surrounding `python` fence structure, not just the bare call):
```python
run_report.record_audit(...)   # already present in enrich-before-ingest / enrich-records
...
run_report.build_run_report(...)   # end-of-run, joins 5 durable stores + audit record
```
`run_report.record_audit` (`run_report.py:169-227`) and `run_report.build_run_report`
(`run_report.py:668-690`) are fully built, "never raises," degrade any missing input to a
named `gaps` entry — reuse unmodified, do not rebuild.

**Constraint:** `test_skill_sequence_coverage.py`'s `MAX_GRANDFATHERED = 0` ratchet means any
new/changed multi-call `python` fence added to these two SKILL.md files must be registered in
that test's coverage table in the SAME commit.

---

### `operator-claude-plugin/skills/enrich-before-ingest/SKILL.md` and `enrich-records/SKILL.md` (route, disclosure line only)

**Analog:** the implicit-open sequence Phase 68 already built in these same two files:
`plan_grant` (figures + ceiling/balance verdicts) → state the arithmetic including any
`CEILING_UNKNOWN` sentence → `watch.pre_spend_pause()` (`watch.py`, `PRE_SPEND_PAUSE_SECONDS =
7`) → `open_grant("yes")` → proceed.

Per D-67-09, Phase 67's edit here is **not a new refusal branch** — it is confirming/labeling
that an autonomous round's disclosure line matches Phase 68's existing wording (D-68-10: "An
implicit open on `CEILING_UNKNOWN` PROCEEDS, with the blind spot disclosed"). Locate the exact
pre-spend disclosure sentence in each file (search for `CEILING_UNKNOWN` and `unknown` near the
`plan_grant`/`pre_spend_pause` call) and confirm/adjust wording only — do not add a branch that
stops execution.

Genuine decision points in these files (held-row vocabulary in `enrich-before-ingest`,
undecided company-domain row in `enrich-records`) are OUT OF SCOPE — Pitfall 1 in
67-RESEARCH.md. Do not touch them.

---

### `operator-claude-plugin/skills/backend-status/SKILL.md` (route, read-only)

**Analog:** `backend-control/SKILL.md:113-116`'s existing changed-posture paragraph — the
research recommends editing that hook site as the primary surface (D-67-03's release-notice
requirement) rather than inventing a new banner mechanism here. `backend-status` is read-only
tier and needs no autonomy-gating logic change; if a first-round changed-posture notice is
added here too (Claude's discretion per CONTEXT.md), keep it a single stated line, no new
persisted "last-seen version" state (Pitfall/recommendation 3 in research, "Where the first-run
notice belongs").

---

### `operator-claude-plugin/skills/backend-control/SKILL.md` (route, edit existing paragraph only)

**Analog:** itself, lines 95-120 (added by 68-01) — the exact hook site.

**Existing text to edit in place** (paraphrased from research, verify exact wording at
lines 113-116 before editing):
> "Implicit approval (D-68-01) is a posture of this conversation only. The scheduled and cron
> paths are unchanged by this phase and stay gated by `ALLOW_N8N_ARM` exactly as before; the
> unattended gate itself — the autonomy levels and their fail-closed conditions — is Phase 67's
> to open (D-68-04)."

**Do not touch anything else in this file.** Per D-67-12, `backend-control`'s own arm/deploy/
structural mutations stay confirm-and-wait regardless of any autonomy key — they are genuine
decision points (D-68-09), not covered by any of the three tiers. This is also where the
D-61-08 reversal (D-67-04, D-61-08's unattended-gate opening) should be recorded in prose,
since this is the file that already names Phase 67 as the place it happens.

**Vocabulary constraint (D-10b, binding, case-insensitive substring scan of this and every
other SKILL.md body):** never write "tier" — use "autonomy levels" (Phase 68's own fix,
already used once; reuse verbatim). `loss-reason-report/SKILL.md` is the one named exemption
and is not touched by this phase.

---

### `CHANGELOG.md` + `.claude-plugin/plugin.json` (release surface)

**Analog:** itself — existing release checklist; current version confirmed `"0.40.0"`
(unbumped since before Phase 68 shipped). Per `plugin-release-requires-version-bump` memory
note, a CHANGELOG entry without a version bump leaves the Update button greyed out and the
change invisible. Bump version and add the entry in the same commit; state the changed write
posture plainly (D-67-03's consequence — the release notes are the thing that actually informs
another operator, since the settings file itself will not).

---

## Shared Patterns

### Absence handling — the ONE thing every new-key read site must get right
**Source:** `config_gate.py` — contrast `write_grants_enabled` (`is True`, absent → False)
against the new `autonomy_enabled` (absent → True).
**Apply to:** `config_gate.py`, `autonomy_gate.py` (if built), any SKILL.md prose describing
the default, `tests/test_autonomy_levels.py`.
```python
# AUTHORITY gate (existing, do not copy for autonomy keys):
return (config or {}).get(WRITE_GRANT_SETTINGS_KEY) is True   # absent -> False

# DEFAULT-SETTER (new, autonomy keys):
return (config or {}).get(AUTONOMY_SETTINGS_KEY, {}).get(level, True) is not False  # absent -> True
```

### Vocabulary ban — "tier" is forbidden in operator-facing prose
**Source:** `tests/test_report_enrichment.py:635` (`_FORBIDDEN_SUBSTRINGS = ("icp", "tier")`),
case-insensitive substring scan of every `skills/*/SKILL.md` body except `loss-reason-report`.
**Apply to:** every SKILL.md edit in this phase (`contact-upload`, `suggest-contacts`,
`enrich-before-ingest`, `enrich-records`, `backend-status`, `backend-control`), and any
CHANGELOG text that ships inside the plugin package.
**Safe wording:** "autonomy levels" (not "autonomy tiers"); key names `read_only` /
`spend_no_write` / `write` carry no banned substring.

### D-67-09 supersedes D-67-05 — do not implement a refusal on unknown state
**Source:** CONTEXT.md D-67-09 (operator, 2026-09-07, binding), reversing 67-RESEARCH.md's own
"Design for the new refusal" recommendation which was written before this ruling.
**Apply to:** any code that reads `ceiling_verdict`'s `CEILING_UNKNOWN`, `cost_guard.compare`'s
`unknown` balance verdict, or a missing `n8n_monthly_execution_allowance` key. All three
disclose-and-proceed under autonomy, exactly as `plan_grant` already does unconditionally
today — no new gating.

### Unmodified gates — never touch, never widen
**Source:** `n8n_arming.py:178-263` (`ARM_ENV_VAR`, `_arm_gate`'s exactly-two branches),
`scheduled_arm.py` (pinned grant-free by `test_headless_grant_boundary.py`).
**Apply to:** every file in this phase. `git diff --name-only <pre-phase-commit> --
operator-claude-plugin/scripts/` must never include `n8n_arming.py` or `scheduled_arm.py`;
`n8n/wf_*.json` must never appear in any diff for this phase.

### Report builder — reuse, never rebuild
**Source:** `run_report.record_audit` (`run_report.py:169-227`), `run_report.build_run_report`
(`run_report.py:668-690`).
**Apply to:** `contact-upload/SKILL.md`, `suggest-contacts/SKILL.md` (new call sites);
`enrich-before-ingest`, `enrich-records` already call it — no change needed there beyond the
disclosure-line confirmation above.

## No Analog Found

None — every file in scope has a strong same-repo analog; 67-RESEARCH.md's own "Don't
Hand-Roll" table already performed this search exhaustively and found no gap requiring
external research or a new mechanism.

## Metadata

**Analog search scope:** `operator-claude-plugin/scripts/`, `operator-claude-plugin/skills/`,
`operator-claude-plugin/tests/`, `operator-claude-plugin/config/` — all read directly this
session or cited with exact line numbers in 67-RESEARCH.md (verified HIGH confidence there).
**Files scanned:** 12 in scope; ~8 additional read for context (`write_grant.py`, `n8n_arming.py`,
`cost_guard.py`, `durable_paths.py`)
**Pattern extraction date:** 2026-09-07
