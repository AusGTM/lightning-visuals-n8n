---
phase: "59"
slug: "frictionless-write-path"
status: verified
# threats_open = count of OPEN threats at or above workflow.security_block_on severity (high).
# T-59-06 is OPEN but `low`, so it is below the blocking threshold and is NOT counted here.
# It is deliberately NOT recorded as closed — see "The Open Threat" below.
threats_open: 0
threats_open_below_threshold: 1
asvs_level: 1
created: "2026-09-03"
---

# Phase 59 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
>
> **Run retroactively on 2026-09-03.** All nine plans carry plan-time `<threat_model>` blocks —
> a verification pass, not retroactive-STRIDE. 52 threats, the largest register in the repo.
>
> Phase 59 is the **frictionless write path**: the whole point was reducing friction on writes, so
> its register is where an over-eager convenience would show. Write-authorization threats were
> given L2-equivalent boundary-placement scrutiny rather than L1 depth.
>
> Mitigations were verified against the code **at current HEAD**, not at the phase's own close —
> the plugin has since moved to 0.37.0 and phases 60–62 built on 59's surfaces. **Phase 60
> cross-reference:** no phase-59 threat cites an artifact that actually landed in 60; the adjacency
> runs the other way, with 60 building `REVIEW_LANE`/`classify_review_item` on top of 59's
> `written_records.py` and `write_grant._consequence` without altering any 59 mitigation.

---

## The Open Threat — T-59-06, and why it is not being closed

**A phase-internal contradiction: an accepted risk whose stated rationale was invalidated by a
later plan in the same phase, three days later, and never revisited.**

59-01 accepted T-59-06 (unbounded artifact growth, `low`) on this rationale:

> *"The file is single-run scoped: a document carrying a different `run_id` is **replaced rather
> than appended to**, so the file holds at most one run's entries. No rotation policy is needed at
> this size."*

59-08 (**D-59-09**) then deliberately changed the design to **one artifact file per `run_id`** —
`written_records_path(run_id)`, whose own docstring says *"keyed by `run_id`, so two runs never
resolve to the same path."* Its plan text is explicit that this was intentional and bounded:
*"Do NOT add a merged index, a 'latest run' pointer, a lock, or any retention or pruning of old
per-run files… retention is not in this phase's scope."*

So the premise the acceptance rested on — one file, replaced per run — **is false as shipped**.
Files accumulate, one per dispatch run, with no retention mechanism anywhere in the codebase
(independently confirmed: no `retention`/`prune`/`max_age` logic in `written_records.py` or
`durable_paths.py`). Neither `59-VERIFICATION.md`, `59-REVIEW.md` nor the CHANGELOG revisits the
acceptance against the new risk shape.

**Why it stays open rather than being re-accepted here.** Re-writing the rationale would be this
audit self-authoring an acceptance on the operator's behalf — the acceptance is the operator's to
give, and an accepted risk whose justification an auditor quietly repaired is worth less than an
open one that is honestly labelled. The auditor declined to do it and so does this record.

**Why it does not block.** Severity is genuinely `low`: `0600`-permissioned, non-PII JSON files
accumulating on the operator's own local machine, one per run, with no attacker-reachable path.
`block_on` is `high`, so `threats_open` (the blocking count) is **0** and the phase is not gated.

**Two ways to close it, either of which is a real fix:**

1. Record a **fresh, honest acceptance** reflecting the true current shape — N files, one per run,
   unbounded, small, local, non-PII — replacing 59-01's now-false sentence.
2. Add **retention or pruning** to `written_records.py`, which 59-08 explicitly deferred rather
   than rejected.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| n8n webhook/dispatch response → plugin process | Untrusted-shaped JSON; `classify_item`/`classify_review_item` are the parsers | HubSpot ids, action words, free-text reasons |
| plugin process → local durable state directory | Per-run written-records artifacts persisted to disk | HubSpot object ids, actions, outcomes — no PII, no secrets by construction |
| shell environment → pytest process | Real credentials may be present in a developer shell or via a stray `load_dotenv()` | `ANTHROPIC_API_KEY`, `HUBSPOT_PRIVATE_APP_TOKEN` |
| test process → Anthropic / HubSpot APIs | A billable or record-mutating call is possible if a credential is reachable | provider requests |
| plugin → operator (grant consequence text) | The **last informed-consent surface** before a live-write window can open | lane names, record/domain counts, artifact location |
| Claude Code host → hook subprocess | The host invokes a shell script from the plugin's install dir at every session start | none — fixed string only |
| hook stdout → Claude context → operator | What the script prints becomes model context relayed to a human | fixed disclosure text only |
| Claude's extraction artifact → `validate()` | Untrusted **model output**; `validate()` is the input-validation control (ASVS V5) | proposed row values, `resolutions` provenance claims |
| resolved value → operator's audit trail | A value's claimed origin determines whether the operator can verify it | `{field, source, detail}` |
| operator-named records → `plan_grant` | **The authorization boundary** — determines what the backend may write | record ids/domains, lane names |
| Claude-resolved handle → the grant's record scope | A resolved value here decides which HubSpot records become writable | a proposed, operator-confirmed id/domain |
| n8n backend → `dispatch_plan` | Untrusted response text; refusal messages must not leak transport internals | `RecordSpecError` messages — spec-sourced only |
| two OS processes → one durable state directory | The concurrency race D-59-09 removed by construction | none shared post-fix |
| armed HubSpot write window → the dispatch loop | An abort mid-window would strand a batch in an unknown partial state | n/a — D-59-10 removed the abort path |

---

## Threat Register

### 59-01 — The durable written-records artifact

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-59-01 | Information Disclosure | `written_records*.json` on disk | medium | mitigate | `written_records.py:515` writes through `durable_paths._atomic_write_0600` (tempfile + `chmod 0600` + fsync + `os.replace`). `classify_item`'s entry dict (`:311-319`) carries no `email` or PII field. | closed |
| T-59-02 | Information Disclosure | a secret or grant smuggled via a response-body key | high | mitigate | `_FORBIDDEN_NAME_MARKERS` (`:205-208`) plus `_looks_forbidden` swept over **every** entry key and value in `classify_item` (`:321-327`), raising `WrittenRecordsError`. The same discipline is applied independently in `classify_review_item` (`:403-409`, added by phase 60 and verified unweakened). | closed |
| T-59-03 | Tampering | a partially-written artifact read as complete | medium | mitigate | Atomic write (above); `load()`/`_entries_from_document` (`:426-438`) degrade a malformed or half-written document to `None` → `[]` **as a whole**, never partially. | closed |
| T-59-04 | Denial of Service | an artifact write failure halting a live HubSpot run | high | mitigate | `append_chunk` catches `OSError` and returns `False` (`:516-518`); `dispatch_plan` additionally guards both a raised `WrittenRecordsError` **and** the falsey return in one `try`/`except` (hardened by 59-09/D-59-10). Bookkeeping cannot stop a live run. | closed |
| T-59-05 | Repudiation | the artifact claiming a write the backend refused | high | mitigate | `outcome_for_action`/`classify_item` map `write_blocked`→`GATED`, `review`/`needs_match_review`→`HELD`, `skip`/`proposed`→`NO_ACTION` — **never** `WRITTEN`; a `create` with no id becomes `CREATED_ID_UNKNOWN`, never a fabricated id (`:139-270`). | closed |
| **T-59-06** | **Denial of Service** | **unbounded artifact growth** | **low** | **accept (rationale invalidated)** | **See "The Open Threat" above. 59-01's acceptance rested on one-file-replaced-per-run; 59-08/D-59-09 shipped one-file-per-run with no retention. Not re-accepted by this audit.** | **open — below `high` threshold (non-blocking)** |
| T-59-SC | Tampering | npm/pip/cargo installs | high | accept | `git log` on `requirements.txt`/`package.json` shows no touch since Phase 23 (`460c048`), before phase 59. | closed (accepted) |

### 59-02 — The ambient-credential test guard

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-59-07 | Elevation of Privilege | a routine test acquiring live-write capability | high | mitigate | `tests/conftest.py`'s autouse `no_ambient_credentials` strips `ANTHROPIC_API_KEY` and `HUBSPOT_PRIVATE_APP_TOKEN` via `monkeypatch.delenv` unless `RUN_LIVE_PARITY == "true"`. `tests/test_conftest_credential_guard.py` 3/3 passed live. | closed |
| T-59-08 | Information Disclosure | a real credential in a test fixture | medium | mitigate | The test file uses only obviously-fake sentinel strings; no real key present. | closed |
| T-59-09 | Tampering | the guard silently disabled by a future edit | medium | mitigate | `grep -c get_closest_marker tests/conftest.py` = **0** — the marker-lookup escape hatch is banned, not merely unused; the docstring records the D-59-04 rationale in-file. | closed |
| T-59-10 | Denial of Service | the guard breaking the two existing live tests on opt-in | medium | mitigate | The fixture returns early on `RUN_LIVE_PARITY=true`; the opt-in branch is proven by a subprocess test (passed live). | closed |
| T-59-SC | Tampering | npm/pip/cargo installs | high | accept | No package installed; stdlib plus existing pytest only. | closed (accepted) |

### 59-03 — Retiring D-53-05's pre-emptive disclosure

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-59-11 | Repudiation | disclosure quietly weakened | high | mitigate | The retired sentence *"authorized before the enriched preview exists"* is found **only** inside the deliberately-preserved historical `LANES` comment (`write_grant.py:92-101`), never in operator-facing rendered text. Both named pin-tests confirmed present at HEAD. | closed |
| T-59-12 | Spoofing | replacement text promising a nonexistent artifact | high | mitigate | `written_records.py` exists and is imported by `write_grant.py:55`; `_consequence` (`:752-756`) names the real `WRITTEN_RECORDS_GLOB` object rather than a hardcoded string — the promise cannot drift from the artifact. | closed |
| T-59-13 | Tampering | the arm-dispatch register altered while editing prose | high | mitigate | `test_the_consequence_carries_the_arm_dispatch_register_in_full` present at HEAD; the base sentence (record/domain bound, disarm-failure escalation) verified unchanged at `:693-702`. | closed |
| T-59-14 | Information Disclosure | the consequence string echoing config or credentials | low | accept | `_consequence(lane_names, ids, domains, allow_create)` takes only lane names and counts and reads no config value. See AR-59-02. | closed (accepted) |
| T-59-SC | Tampering | npm/pip/cargo installs | high | accept | Prose and test edits only. | closed (accepted) |

### 59-04 — The SessionStart disclosure hook

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-59-15 | Information Disclosure | hook stdout carrying a credential or path every session | high | mitigate | Live-run under a minimal environment (`env -i PATH=… bash operator-claude-plugin/hooks/session-start.sh`): exits 0, no config, network or filesystem access, fixed-string output only. | closed |
| T-59-16 | Denial of Service | a failing hook blocking every session start | high | mitigate | Same minimal-env run — zero dependencies, unconditional `exit 0`. | closed |
| T-59-17 | Elevation of Privilege | a plugin hook executing arbitrary code | medium | accept | Inherent to the Claude Code hook mechanism; the script body is a fixed-string echo with no external-input interpolation. See AR-59-03. | closed (accepted) |
| T-59-18 | Repudiation | the note contradicting real revocation behaviour | high | mitigate | Captured hook output states revoke *"refuses the NEXT send"* and that a running dispatch *"finishes its remaining chunks"* — which matches `dispatch_plan`'s actual behaviour, pinned by `test_a_revocation_midway_does_not_stop_a_running_dispatch`. The disclosure and the code agree. | closed |
| T-59-19 | Tampering | `${CLAUDE_PLUGIN_ROOT}` replaced by a hardcoded path | medium | mitigate | `hooks.json` references `${CLAUDE_PLUGIN_ROOT}` literally. | closed |
| T-59-SC | Tampering | npm/pip/cargo installs | high | accept | One JSON file, one bash script, one stdlib-only test. | closed (accepted) |

### 59-05 — The identity gate: resolve-and-propose

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-59-20 | Repudiation | provenance laundering | high | mitigate | `extraction.py:611-667` — `resolutions` are validated **before** the identity check; an unrecognised `source`, or a `field` the row does not carry, rejects the whole record (`:651-664`). | closed |
| T-59-21 | Spoofing | a fabricated value reaching HubSpot | high | mitigate | `test_no_invention_structural.py`'s forbidden-substring list is extended with `fill_identity`, `apply_resolution`, `confirm_resolution`, `resolve_identity` alongside the original four. No function in `extraction.py` writes a value into a row — `resolvable` only **classifies**, never fills. | closed |
| T-59-22 | Elevation of Privilege | a row silently starting to dispatch | high | mitigate | `extraction.py:672-676` — the identity gate's `rejected.append(...)` is retained exactly as before, with a comment saying so; `resolvable` is purely additive. | closed |
| T-59-23 | Tampering | the D-07 contradiction check bypassed for a resolved field | high | mitigate | Module docstring states it explicitly: *"a resolved field named by an ambiguity still rejects the record; being resolved is never an exemption."* The D-07 enforcement path was located unmodified. | closed |
| T-59-24 | Information Disclosure | a resolution `detail` string carrying a credential or path | medium | mitigate | `resolutions` is a **record**-level key, never a row key (`:611-617`), and `write_dispatch_csv`'s STRUCT-01 guard raises `ExtractionError("non_canonical_key_in_row", …)` on any row key outside the canonical set **before the output file is opened**. The claimed backstop was read directly and does exist. | closed |
| T-59-25 | Denial of Service | the inventory closed by reclassifying an inconvenient gate | medium | mitigate | `59-GATE-INVENTORY.md` scanned for "too hard / too difficult / too complex / not worth / low value" → **0** hits. | closed |
| T-59-SC | Tampering | npm/pip/cargo installs | high | accept | No package installed. | closed (accepted) |

### 59-06 — Enrichment/grant lane resolve-and-propose

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-59-26 | Elevation of Privilege | a resolution widening a grant | high | mitigate | Commit `73d6484`'s diff on `write_grant.py` is **exactly one hunk**, 12 insertions / 1 deletion, confined to the empty-record-set refusal's message text — `plan_grant`'s logic untouched. `test_write_grant_module_never_calls_a_hubspot_search_endpoint` passing; direct scan finds 0 occurrences of `hubapi.com`, `crm/v3/objects`, `/search` or `hubspot_lookup(`. The authorization boundary was not widened while the convenience was added. | closed |
| T-59-27 | Spoofing | a plausible-but-wrong domain resolving to the wrong company | high | mitigate | `enrich-records/SKILL.md` names all four closed-vocabulary sources, the illegitimate list ("own recall", "inferred domain", "plausible"), and requires operator confirmation. | closed |
| T-59-28 | Repudiation | a Claude-resolved handle presented as operator-supplied | high | mitigate | `enrichment.RecordSpecError.__init__` validates every `sources` entry against `resolution_sources.RESOLUTION_SOURCES` **at construction**, raising `ValueError`. Confirmed live that `extraction.RESOLUTION_SOURCES is resolution_sources.RESOLUTION_SOURCES` and `enrichment.RESOLUTION_SOURCES is resolution_sources.RESOLUTION_SOURCES` are **both `True`** — one shared object, not two closed sets that could drift apart. | closed |
| T-59-29 | Tampering | a pinned refusal message reworded | medium | mitigate | `write_grant.py` still contains `"refusing to plan a grant over an empty record set"` verbatim; `enrichment.py`'s verbatim-pinned profile-page refusal unchanged. | closed |
| T-59-30 | Denial of Service | the inventory closed by reclassification | medium | mitigate | `59-GATE-INVENTORY.md`'s *Unplanned items* section states plainly that GATE-02..05's delivery gap existed between 59-06 and 59-07 and was **not** hidden. The inventory tells the truth rather than closing cleanly. | closed |
| T-59-SC | Tampering | npm/pip/cargo installs | high | accept | No package installed. | closed (accepted) |

### 59-07 — Gap closure: carrying GATE-02..05's payload through dispatch

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-59-07-01 | Information Disclosure | `ChunkResult.reason` now carrying `str(e)` | medium | mitigate | The `ChunkResult` docstring confirms `resolvable`/`reason` are admitted from `RecordSpecError` **because that exception is raised by `build_envelope` before any request is built** — never transport-, response- or config-sourced. `DispatchError`'s fixed string is unchanged. | closed |
| T-59-07-02 | Tampering | `resolvable` sources laundered past the closed vocabulary | high | mitigate | Nothing in `chunking.py` constructs a `resolvable` entry — it only reads `getattr(e, "resolvable", ())` off an already-validated exception, so T-59-28's construction-time gate covers this path too. | closed |
| T-59-07-03 | Elevation of Privilege | a skill acting on a proposal without the operator | high | mitigate | Both `enrich-records/SKILL.md` and `enrich-before-ingest/SKILL.md` reference `resolvable` and require operator confirmation before acting. | closed |
| T-59-07-SC | Tampering | npm/pip/cargo installs | high | mitigate | No package installed. | closed |

### 59-08 — Gap closure: per-run artifact concurrency + universal disclosure

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-59-08-01 | Tampering | concurrent writers clobbering flushed chunk history | high | mitigate | `written_records_path(run_id)` returns `written_records-{run_id}.json` — two runs never share a path (`:231-241`). `test_written_records.py` 74/74 passed live. **This is the change that invalidated T-59-06's rationale.** | closed |
| T-59-08-02 | Information Disclosure | per-run files inheriting weaker permissions | high | mitigate | Every write still goes through `durable_paths._atomic_write_0600` (`:515`). | closed |
| T-59-08-03 | Repudiation | a legacy artifact silently dropped by a too-narrow glob | medium | mitigate | `WRITTEN_RECORDS_GLOB = "written_records*.json"` — **not** hyphen-anchored (`:130`), so the pre-change `written_records.json` still matches. | closed |
| T-59-08-04 | Elevation of Privilege | a grant persisted into the artifact | high | mitigate | `_FORBIDDEN_NAME_MARKERS`/`_looks_forbidden` unchanged and re-verified. | closed |
| T-59-08-05 | Repudiation | a single-lane grant with no disclosure of the artifact | medium | mitigate | Commit `744e2ff`'s diff shows exactly two hunks: the disclosure sentence moved **outside** the `len(lane_names) > 1` block, so a one-lane grant discloses too. Present at HEAD (`:747-756`). | closed |
| T-59-08-SC | Tampering | npm/pip/cargo installs | high | mitigate | No package installed; scan for `flock`/`filelock`/`msvcrt` in `written_records.py` → **0**, confirming the rejected locking alternative was not smuggled back in. | closed |

### 59-09 — Gap closure: a bookkeeping failure never stops a dispatch

| Threat ID | Category | Component | Severity | Disposition | Mitigation | Status |
|-----------|----------|-----------|----------|-------------|------------|--------|
| T-59-09-01 | Denial of Service | `dispatch_plan` aborted mid-run by a bookkeeping refusal | high | mitigate | `chunking.py`'s guard catches both a raised `WrittenRecordsError` and `append_chunk`'s falsey return in one `try`/`except`, records into `written_records_failures`, and continues. | closed |
| T-59-09-02 | Repudiation | a short list read as a complete account | high | mitigate | `DispatchOutcome.written_records_failures` defaults to an empty tuple, **never `None`**, and is reported on four surfaces (`chunking.py`, `scheduled_arm.py`, both SKILL.md files). | closed |
| T-59-09-03 | Repudiation | an unattended crash discarding results with nothing to page on | high | mitigate | `scheduled_arm.py` carries `run_id` and `records_incomplete` into `_outcome`; the stale "only raises" comment is gone (0 occurrences). | closed |
| T-59-09-04 | Information Disclosure | the forbidden-name refusal weakened to stop it firing | high | mitigate | The markers and the sweep are unchanged and unweakened — **only the caller's reaction to the raise changed, not the check itself.** That distinction is the whole mitigation. | closed |
| T-59-09-05 | Tampering | the armed window left open by the new control flow | high | mitigate | The `dispatch_plan` call sits entirely inside `with n8n_arming.armed_window(...)`; D-59-10's guard is purely internal to `chunking.py`'s loop, with no change to the `with` block or its guaranteed disarm on exit. | closed |
| T-59-09-SC | Tampering | npm/pip/cargo installs | high | mitigate | No package installed. | closed |

*Status: closed · closed (accepted) · open — below `high` threshold (non-blocking)*
*Severity: critical > high > medium > low — only open threats at or above `security_block_on` (`high`) count toward `threats_open`*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-59-01 | T-59-SC (plans 59-01 … 59-06) | No package installed across these six plans; `requirements.txt`/`package.json` untouched since Phase 23 (`460c048`), still true at HEAD. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-59-02 | T-59-14 | `write_grant._consequence`'s signature takes only lane names, id/domain counts and a boolean; it reads no config value. | plan-time disposition, re-confirmed this audit | 2026-09-03 |
| AR-59-03 | T-59-17 | Inherent to the Claude Code `SessionStart` hook mechanism. Mitigated by the script being a fixed-string echo with no external-input interpolation and no execution of anything it reads — confirmed by a live minimal-environment subprocess run. | plan-time disposition, re-confirmed this audit | 2026-09-03 |

**No AR is recorded for T-59-06.** That is deliberate: see "The Open Threat" above. Adding one here
would be this audit granting an acceptance that is the operator's to grant.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open (blocking) | Open (below threshold) | Run By |
|------------|---------------|--------|-----------------|------------------------|--------|
| 2026-09-03 | 52 | 51 (43 mitigation-verified, 8 accepted) | 0 | 1 (T-59-06, `low`) | `gsd-security-auditor`, `asvs_level: 1` |

**Audit depth.** L1 grep-and-read throughout, with **L2-equivalent boundary-placement scrutiny on
the write-authorization threats** — this is the frictionless-write-path phase, so an over-eager
convenience would show up there first. The strongest single piece of evidence in the register is
T-59-26's: commit `73d6484`'s diff on `write_grant.py` is one hunk confined to a refusal *message*,
proving the authorization boundary was not widened while friction was being removed. No L3
end-to-end trace was performed.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed (no open threat at or above `high`)
- [ ] **One `low` threat open below threshold — T-59-06, awaiting an operator decision between a fresh acceptance and adding retention**
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-09-03, with T-59-06 outstanding and non-blocking
