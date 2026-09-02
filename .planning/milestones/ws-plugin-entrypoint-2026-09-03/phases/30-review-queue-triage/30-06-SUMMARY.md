---
phase: 30-review-queue-triage
plan: 06
subsystem: operator-plugin
tags: [plugin, review-writeback, env-kill-switch, session-arm, read-back-verification, skill, docs]

requires:
  - phase: 30
    plan: 05
    provides: "review_queue.fetch_queue / policy_class / render_queue, the `review` config_gate capability, and D-35's two-failure-mode split"
  - phase: 30
    plan: 03
    provides: "the six-outcome vocabulary (applied|rejected|stale|no_candidate|not_flagged|refused) and the multi-key approval patch"
  - phase: 30
    plan: 02
    provides: "the five-key response contract {outcome, message, would_write, verified_properties, verified} and the post-PATCH refetch behind it"
  - phase: 28
    plan: 01
    provides: "stub_module_transport_factory / _StubModuleTransport, with calls / verbs / mutating_calls"
provides:
  - "operator-claude-plugin/scripts/review_decision.py — preview_decision, submit_decision, verify_decision, submit_enabled, is_undoing"
  - "ALLOW_REVIEW_SUBMIT — the plugin-side env kill switch, exact-string `true`, checked before any transport exists, gating SUBMITTING only"
  - "operator-claude-plugin/skills/review-triage/SKILL.md — the conversational surface and its own arming phrase"
  - "the plugin's operator documentation for the three gates and the deferred resolved-source limitation"
affects:
  - "30-07 (the operator runbook drives exactly these three functions through this skill, and must open all three gates)"

tech-stack:
  added: []
  patterns:
    - "one ALLOW_* per dangerous capability, exact-string `true`, checked before any transport is constructed, with an un-doing carve-out (28 D-34, 30 D-16)"
    - "a refusal that shows what it would have done takes the showing as an ARGUMENT — it does not fetch it, or the refusal becomes a request (D-37)"
    - "a verdict is re-derived from an independent refetch; the response's own `verified` field is a convenience, never the authority (D-19, 28 D-14)"

key-files:
  created:
    - operator-claude-plugin/scripts/review_decision.py
    - operator-claude-plugin/tests/test_review_decision.py
    - operator-claude-plugin/skills/review-triage/SKILL.md
  modified:
    - operator-claude-plugin/README.md
    - operator-claude-plugin/CHANGELOG.md
    - .planning/workstreams/plugin-entrypoint/phases/30-review-queue-triage/30-CONTEXT.md

key-decisions:
  - "ALLOW_REVIEW_SUBMIT's un-doing carve-out is a predicate on the DECISION WORD, not a separate function: `reject` bypasses the switch, everything else — including an unrecognised word — is gated. The switch fails closed on input it does not recognise. Folded in as D-38."
  - "The env carve-out is NOT a carve-out from the session arm. A rejection writes to HubSpot, so D-03 still applies to it and an unarmed rejection refuses."
  - "submit_decision gained one optional keyword argument, `preview=None`. The plan's 'refuse before any network call' and 'return the preview's would_write' are jointly satisfiable only if the preview is handed in — a dry-run POST is still a `post` and would land in `mutating_calls`. Folded in as D-37."
  - "_EXPECTED_SEND_SHAPED was not touched. The transport is the bare requests module, so the guard never fired and there was nothing to allowlist."

metrics:
  duration: ~55 min
  completed: 2026-07-31
status: complete
---

# Phase 30 Plan 06: The Decision Half of the Loop Summary

An operator can now adjudicate a flagged record in conversation, see the backend's own
computed patch before anything is sent, and — only with three independent gates open — send
it and be told verified or failed from a re-read of the record rather than from a status
code.

## What was built

**Task 1 — `review_decision.py` and its tests** (`86a10a9`)

| function | contract |
|---|---|
| `submit_enabled()` | `True` only when `ALLOW_REVIEW_SUBMIT` reads exactly `"true"` |
| `is_undoing(decision)` | `True` only for `reject`; fails closed on anything unrecognised |
| `preview_decision(config, object_type, record_id, decision, reason, transport=requests)` | one POST with `dry_run: true`; returns the five-key contract plus `{available, reason}` |
| `submit_decision(config, object_type, record_id, decision, reason, reviewed_by, review_armed, preview=None, transport=requests)` | env gate → session arm → one POST with `dry_run: false` |
| `verify_decision(intended, response)` | `{status, outcome, message, mismatched}`; status ∈ `verified` / `failed` / `not_written` |

**`ALLOW_REVIEW_SUBMIT`, exactly as shipped:**

- **Exact string `"true"` only.** `""`, `"1"`, `"yes"`, `"TRUE"`, `"True"`, `"true "` and
  `" true"` all refuse — the near-miss table is a parametrised test, matching
  `ALLOW_N8N_ARM`'s semantics value for value.
- **Checked before any transport is constructed**, so an unset variable leaves
  `transport.calls == []` — no unsent request, none at all. Asserted directly.
- **Refuses in plain language naming the variable and saying an administrator sets it**, and
  a test asserts the message contains no `export ` — the refusal must not read as a
  workaround.
- **Gates submitting only.** `reject` — which records the operator's reason and leaves the
  record in the queue — proceeds with the variable unset, mirroring how `ALLOW_N8N_ARM`
  gates arming but never disarming. `preview_decision` is likewise ungated: a dry run writes
  nothing, and without it the operator cannot see what they are approving.
- **Not `ALLOW_HUBSPOT_REVIEW_WRITES`,** and the module docstring says so at length: the
  latter is a literal compiled into the workflow JSON and read by `_writeSafetyAllows()`
  inside n8n, in another process on another machine. Both are required; setting one has not
  done the work of the other.
- **Defence in depth, not a replacement.** The session arm and the per-decision exact-write
  display both stay, and both are exercised in tests independently of the env gate.

**The rest of the module's load-bearing behaviour:**

- The request carries only the six keys `Parse Review Decision` reads — no field name, no
  value, no patch. A test pins the key set exactly, so this client cannot tell the endpoint
  *what* to write, only which record and which decision word.
- `verify_decision` re-derives the comparison from `verified_properties` — 30-02's
  independent post-PATCH refetch, not the PATCH's echo (D-19). A test asserts `verified:
  false` on a matching refetch still reads verified and `verified: true` on a mismatching
  one does not, so the response's own flag is provably not the authority. A written decision
  arriving with `verified_properties` null / `""` / `[]` / `0` reports **failed**.
- All six outcomes branch and are tested. `unsupported` is asserted absent (D-30), and an
  outcome this client does not recognise reports failed rather than falling through.
- The empty-body case (D-23) degrades to `unparseable_response` and `verify_decision`
  reports it failed — indistinguishable from a rejected write, as required.
- The response is parsed as **one dict**, never `body[0]` (D-24); an array reports
  `unrecognized_response_shape`.
- `reviewed_by` unset or whitespace becomes `"operator (unnamed)"` rather than `""`, because
  the backend writes `lv_enrichment_reviewed_by` only for a non-empty label.
- Nothing persists. An AST test asserts `review_armed` is never a module-level name, and a
  source scan asserts the module contains no `open(`, `Path(`, `json.dump(`, `write_text` or
  `read_text`.

**Task 2 — `skills/review-triage/SKILL.md`** (`bb75621`)

Frontmatter names the natural phrasings ("what needs review", "what's waiting on me", "work
the review queue", "approve this record"), so it is reachable both by intent and as
`/operator-claude-plugin:review-triage`. The flow: config check and arming position → fetch
→ render → pick one record → elicit decision and reason → show the backend's exact write →
confirm → armed submit → verified/failed.

Wording rules it carries, because they are decisions rather than style:

- Its arming phrase is **"arm review writeback"**, and it states that this arm and the
  contact-upload arm are separate switches in both directions (D-02).
- **It can arm the conversation; it cannot open the env gate, and it says so.** On a
  `submit_not_enabled` refusal it relays the message as-is and is explicitly forbidden from
  offering to export it, write it to a file, or suggest any way around it.
- Rejection is described as recording a reason and leaving the record in the queue — never
  clearing, dismissing, removing, resolving or closing (D-10, REVIEW-05).
- A reason is asked every time and a decision without one is still accepted (D-09).
- `stale`, `no_candidate` and `not_flagged` each have operator-facing wording saying what
  happened, that nothing was written, and what to do next.
- An unavailable queue is never reported as an empty one, with `hubspot_search_did_not_run`
  named specifically.

`tests/test_plugin_manifest.py` hardcodes a single `contact-upload` `SKILL_PATH` and does
not enumerate skills, so the new skill needed no change to it — **and it was not touched**
(it is uncommitted-modified by the operator).

**Task 3 — README and CHANGELOG** (`b0cec87`)

The README gains a "Working the review queue" section: what the queue shows, the
resolved-source caveat, that the backend enforces field policy while the client only labels
it (scoped to the decision endpoint), that rejection leaves the record queued, both endpoint
names, the config keys, and a **three-gate table** stating that the first and third are
different variables in different processes despite the similar names, and that
`ALLOW_REVIEW_SUBMIT` gates submitting only. The CHANGELOG entry records the
resolved-source limitation as deferred with its reason.

## Deviations from Plan

**1. [Rule 3 — blocking contradiction in the spec] `submit_decision` takes an optional `preview`**

The plan's action text asks the unarmed refusal to "refuse before any network call" *and*
to return "the preview's `would_write`". `_StubModuleTransport.mutating_calls` classifies by
verb, so a dry-run POST issued inside the refusal lands in that list and fails the plan's
own `transport.mutating_calls == []` criterion — a dry run writes nothing but is still a
`post`. Resolved with one optional keyword argument, `preview=None`, placed after
`review_armed` and before `transport` so the plan's positional order is untouched: the skill
hands back the envelope it already showed the operator, and the refusal echoes its
`would_write`. **No call of any kind is made on either refusal path.** With no preview
supplied, `would_write` is `None` rather than a guess. **Folded in as D-37.**

**2. [design choice, recorded so it is not undone] the un-doing carve-out is scoped by decision word**

Phase 28's carve-out is structural — `disarm` is a different function from `arm_for_dispatch`.
Here the un-doing path is the same `submit_decision` call with `decision: "reject"`, so the
carve-out had to be a predicate. `is_undoing` recognises **only** `reject`, matching
`reviewDecision.js:172`'s two-word vocabulary; `approve`, an unknown word and a non-string
are all gated, so the switch fails closed on input it does not recognise. Two consequences
stated in tests: an unarmed rejection still refuses (the env carve-out is not a carve-out
from the session arm — a rejection writes to HubSpot, so D-03 applies), and a future third
decision word must be classified deliberately rather than inheriting a default. **Folded in
as D-38.**

**Nothing else deviated.** No `conftest.py` edit (D-21 — `stub_module_transport_factory`
already existed), no `test_retry_reuses_dispatch.py` edit, no `reviewApply.js` edit, no
`test_plugin_manifest.py` edit, no `STATE.md` edit, and no file outside
`operator-claude-plugin/` except this phase's own planning docs.

## Verification

**No network call of any kind. Nothing armed, deployed, or activated.** Every test runs
under the autouse `no_network` guard; every request path is driven through
`stub_module_transport_factory`.

Disarmed grep, after the final code commit — 0 across all 8 `n8n/*.json`:

```
grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json   ->  0 matches
```

Empty-diff guards:

| guard | result |
|---|---|
| `operator-claude-plugin/tests/test_retry_reuses_dispatch.py` | **byte-identical to pre-plan HEAD** — sha256 `26bba4f2a7f71401e095846a81abc39119a5e87e48f254cb4f71721d2e2f97ad` on both sides, the same digest 30-05 recorded. `_EXPECTED_SEND_SHAPED` still holds exactly its two entries |
| `operator-claude-plugin/tests/conftest.py` | **empty** — D-21 |
| `n8n/code/reviewApply.js` | **empty** — D-15/D-31 intact, the backstop untouched |
| file deletions across all three commits | **none** |

| Suite | Before | After | Attribution |
|---|---|---|---|
| `.venv/bin/python -m pytest -q` (repo root) | 1242 passed, 1 skipped | **1290 passed, 1 skipped** | +48, **all mine** — the root suite collects the plugin's tests too, so this is the same 48 as the row below |
| `node --test tests/n8n/*.test.mjs` (file form) | 474 / 0 fail | **474 / 0 fail** | unchanged, correctly — this plan touches no n8n artifact |
| plugin (`python3 -m pytest` in `operator-claude-plugin/`) | 442 | **490** | +48, **all mine**, all in `test_review_decision.py` |

Baselines were measured before any edit and matched the dispatch exactly (1242/1, 474/0,
442). No sibling executor moved them.

**Flake:** none observed. The `mergeContacts.test.mjs` 1 ms timestamp shape did not fire
across the two full node runs, and this plan adds no wall-clock assertion of its own, so it
cannot join that class. Left unfixed — outside this plan's `files_modified` and outside
`operator-claude-plugin/`. No run needed a re-run to reach green.

## Known Stubs

None. Every function returns real data or a named reason. Two intentional non-implementations,
both inherited and both documented rather than hidden:

- A **contacts approve** resolves to `no_candidate` at the backend and writes nothing (D-27).
  Correct, not a stub — the candidate JSON has exactly one producer and it is the companies
  lane. The skill states it in the operator's terms.
- The queue names the **resolved source**, not the provider-by-provider disagreement (D-08f).
  Recorded as deferred in the CHANGELOG with its reason; no client can show it until the
  backend persists it.

## Documentation debt, not introduced by this plan

`README.md`'s "Layout" tree still lists only the `contact-upload` skill and four scripts —
it has been stale since Phase 24 and does not name `backend-status`, `review-triage`,
`review_queue.py` or `review_decision.py`. Deliberately not partially refreshed here:
adding only this plan's entries would make a stale tree look maintained. A one-line
refresh of the whole tree belongs to whichever plan next has cause to touch that section.

## What 30-07 needs to know

1. **Three gates, and the runbook must open all three, in this order:**
   (a) an admin exports `ALLOW_REVIEW_SUBMIT=true` in the shell the plugin runs in — the
   exact string, nothing else; (b) the operator says **"arm review writeback"** in the
   conversation — a distinct phrase from "arm the upload", and arming one does not arm the
   other; (c) a deploy arms `ALLOW_HUBSPOT_REVIEW_WRITES` with a **non-empty** allowlist.
   An empty allowlist grants nothing while reporting success.
2. **A contact can only be allowlisted by `TEST_RECORD_IDS`** (D-29) — contacts carry no
   `domain`. And per D-23 an armed-but-not-allowlisted decision returns **no response at
   all**; the client reports that as `failed`, so the runbook must tell the operator a
   silent failure here means "not on the allowlist", not "broken endpoint".
3. **The canary must not be read as proving protected-field enforcement** while D-31 is
   open — it exercises the decision-endpoint path only, and the 15-minute backstop still
   allowlists by key.
4. **Verify the write from the plugin's own verdict**, not from an HTTP status: run
   `verify_decision` and expect `verified`. A `failed` with a named mismatched key and a
   `failed` from an unreadable read-back are different findings and should be reported as
   such.
5. **Rejecting is the safest first canary** — one property, the record stays queued, and it
   needs neither `ALLOW_REVIEW_SUBMIT` nor an approval's multi-key patch. It still needs the
   session arm and the backend allowlist.

## Self-Check: PASSED

- `operator-claude-plugin/scripts/review_decision.py` — FOUND
- `operator-claude-plugin/tests/test_review_decision.py` — FOUND
- `operator-claude-plugin/skills/review-triage/SKILL.md` — FOUND
- `operator-claude-plugin/README.md` (both endpoints, three-gate table) — FOUND
- `operator-claude-plugin/CHANGELOG.md` (Phase 30 entry, deferred limitation) — FOUND
- commits `86a10a9`, `bb75621`, `b0cec87` — all FOUND in `git log`
- no file deletions in any of the three commits
