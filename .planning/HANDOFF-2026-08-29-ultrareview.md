# Handoff for deep review — lv-n8n-poc

**Written:** 2026-08-29
**For:** `/ultrareview` (or any reviewer arriving with no prior context)
**Recommended invocation:** `/ultrareview 347ed32` — see § 9 for why.

---

## 1. What this system is, in one paragraph

A HubSpot CRM enrichment and ICP-scoring pipeline for **Lightning Visuals**, an AU sports-media
company. It takes contacts and companies, runs them through a paid provider waterfall
(ZoomInfo → Apollo → Lusha, plus Claude web research), merges the answers into HubSpot without
clobbering human-maintained values, and scores each company A/B/C/D against an ICP rubric so
sales knows who to call. Orchestration lives in **n8n Cloud**; HubSpot is the system of record;
a **Claude Code plugin** is the operator's entire control surface.

## 2. The jobs to be done

1. **Load contacts into HubSpot** from whatever the operator actually has — a spreadsheet, a
   pasted signature block, a screenshot, a bare company name, a LinkedIn URL.
2. **Enrich** those records from the provider waterfall before or after they land.
3. **Score** companies against the ICP rubric, with hard vetoes (non-ANZ, no broadcast content,
   hardware vendor) and graduated deductions.
4. **Never silently corrupt HubSpot.** ~700 live company records; HubSpot has no rollback.
5. **Do all of the above unattended**, from one approval at the start of a session.

## 3. THE CONSTRAINT THAT SHOULD DRIVE YOUR REVIEW

**This system is operated by one non-technical operator. The admin is not readily available.**

- The operator works from **Claude Desktop / Claude Code**. They have **no terminal**, and cannot
  set a shell environment variable, run a deploy, or edit a config file by hand.
- The admin can do those things but is **rarely reachable**. Every path that requires an admin is
  a path that stalls for hours or days.
- Therefore: **anything that can only be unblocked by an admin is a design defect unless the
  escalation is genuinely severe** (destroying data, spending beyond a hard ceiling, changing who
  is authorized).
- The operator's stated priorities, in order: **speed, autonomy, unattended runs.**

**This constraint has been repeatedly violated in practice, and that is the core thing to look
for.** Documented instances:

| Incident | What happened |
|---|---|
| Client UAT 2026-08-25 (G-2) | The interactive write path required `ALLOW_N8N_ARM` as a **shell environment variable**. An operator in Claude Desktop cannot set one. Every write to date was landed by an admin from a terminal. |
| 2026-08-27 | Approving **one** flagged contact needed a plugin-side kill switch **plus** an admin-run arm-deploy — two human round trips for a six-property update on one record. |
| Still open | The review lane (Phase 60) is the one lane write grants deliberately do not reach, so it still has G-2's shape. |

Phase 53 built an operator-openable **write grant** to fix this. Phases 54–59 built on it. **The
end-to-end flow it exists to serve has never once completed** — see § 5.

## 4. Architecture map

```
Operator (Claude Desktop, no terminal)
  └─ operator-claude-plugin/          ← THE operator's entire surface
       skills/    backend-control, backend-status, backend-sweep, contact-upload,
                  enrich-before-ingest, enrich-records, initialize,
                  loss-reason-report, review-triage
       scripts/   ~45 modules. Load-bearing ones:
                    write_grant.py     (59KB) — the session grant: authority, envelope,
                                       per-send narrowing, close-reason vocabulary
                    n8n_arming.py      — armed_window: arms a record-scoped write window,
                                       disarms on exit, reports a failed disarm loudly
                    chunking.py        — dispatch_plan: the shared chunk loop EVERY lane uses
                    extraction.py      (44KB) — Claude-as-extractor contract + validation
                    preingest.py       (41KB) — match, classify, merge_enriched
                    written_records.py — the post-run "what actually got written" artifact
                    enrichment.py      — envelope building, provider resolution
                    scheduled_arm.py   — the UNATTENDED cron path
  └─ n8n Cloud (8 workflow JSONs, generated — see the parity rule below)
  └─ HubSpot (system of record, ~700 companies, no rollback)

src/            The Python oracle — icp_scoring.py, merge_policy.py, normalizer.py, taxonomy.py.
                Mirrors logic that also lives in generated n8n nodes.
tests/          112 files (repo) + tests/n8n/ 65 .mjs files
operator-claude-plugin/tests/   84 files
```

**Run the suites with these exact commands** (system python lacks the deps):

```
.venv/bin/python -m pytest -q                              # 3285 passed / 154 skipped
.venv/bin/python -m pytest operator-claude-plugin/tests -q  # 1701 passed / 5 skipped
node --test tests/n8n/*.test.mjs                            # 776 pass / 0 fail
```

The **glob form** of the node command is required — the directory form is broken on node 24.

## 5. THE RECURRING FAILURE MODE — read this before reviewing anything

**Every component passes its tests. The compositions break.** Four instances in one week, all of
which survived three fully green suites:

| # | Defect | Why the tests missed it |
|---|---|---|
| 1 | `merge_enriched` silently filed every enriched row as `unanswered` — paid-for provider data discarded and reported as absent. Present in **every version ever shipped** (0.11.1–0.19.0). | Tests passed flat response dicts; the backend returns per-chunk **lists**. |
| 2 | `RecordSpecError.resolvable` (the whole point of four converted gates) was discarded by `chunking.py`'s exception handler — the only call site real usage goes through. | Every `.resolvable` test called `build_envelope` **directly**. |
| 3 | `written_records.json` had no concurrency protection; two shipped processes could silently drop each other's history. | No test ran two dispatches against one directory. |
| 4 | **Still open.** `write_dispatch_csv` refuses the rows `merge_enriched` produces — the documented ingest sequence cannot execute. | **No test chains `merge_enriched` → `hold_emailless` → `write_dispatch_csv`.** |

**The pattern: unit boundaries are well tested; the documented sequences joining them are not.**
Defect #1 was found only by the first end-to-end operator walk ever performed. #2 and #3 were
found by code review and goal verification, not by tests. #4 was found by the second walk,
yesterday.

**This is the single highest-value thing to sweep for.** Wherever a `SKILL.md` documents a call
sequence, check that a test drives *that sequence*, not just its parts.

## 6. Known-open defects (found 2026-08-29, not yet fixed)

Full evidence: `.planning/phases/53-operator-openable-write-grant/53-WALK-RECORD-2.md`.

**FINDING B — the ingest composition is broken.** `enrich-before-ingest/SKILL.md` step 7:

```python
sendable_rows, held = extraction.hold_emailless(merge_report.rows)
extraction.write_dispatch_csv(sendable_rows, out_path)
```

raises `ExtractionError: Row 0 carries key(s) outside the canonical set: ['row_id']`.
`preingest.build_rows_spec` mints `row_id` **into** every row (by design, required by step 2);
`write_dispatch_csv` correctly refuses non-canonical keys (deliberately unit-tested). **No strip
helper exists anywhere** and no skill names one. Both behaviours are individually correct.
**Consequence: an enrich-before-ingest batch still cannot reach a HubSpot write.**

**FINDING A — the test suite writes into the operator's real state directory.** 413
`written_records-*.json` files appeared in
`~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/` during one session's
test runs. `chunking.dispatch_plan`'s inline flush resolves the **real** durable path, and older
`dispatch_plan` callers don't monkeypatch it. `written_records.load()` globs and unions all of
them, so the operator-facing "what did my run write?" read returns mostly test debris. Per-run
reads by `run_id` are unaffected.

**Minor:** an opened grant reports `expires_at: None` though the design language is "bounded,
**expiring** and revocable". `close_grant` returns `state: closed` but `close_reason: None`.

## 7. What is deliberately load-bearing — do NOT propose simplifying these away

Each of these looks like ceremony and is not. All operator-confirmed.

- **The n8n write-safety gate nodes.** HubSpot has no rollback; a bad merge hits ~700 live
  records. The empty-allowlist-denies-everything rule is the last line.
- **`plan_grant`'s refusal of an empty record set.** A grant over nothing would *report* as a
  grant while granting nothing — worse than refusing, because it reads as success.
- **The material-conflict judge gate.** It caught a real false veto (execution `11983`).
- **The non-clobber merge policy.** Manual CRM values outrank provider values by design.
- **The no-invention rule in `extraction.md`.** A fabricated value that lands *undetectably* is
  the failure it exists to prevent. Note the 2026-08-28 amendment (D-59-08): the rule became
  `refuse` → **propose**, never `refuse` → **guess**. Legitimate resolution sources are a closed
  vocabulary (HubSpot read-only, operator statement, provider result, same-row derivation);
  Claude's own recall and plausible email patterns remain forbidden.
- **Per-send armed windows narrower than the grant.** "This send's records, never the grant's
  whole record set" is the only structural protection left after D-53-05 collapsed two asks
  into one.
- **The Phase 46 parity rule.** A shared predicate lands in BOTH `src/icp_scoring.py` and the node
  built by `scripts/build_cloud_workflows.py`, in ONE commit. **Never hand-edit
  `n8n/wf_enrichment_cloud.json`** — it is generated (809KB).

## 8. Where a refactor is genuinely invited

Not prescriptions — the areas where the operator constraint and the current design are in
tension, and a reviewer with fresh eyes may see better.

1. **The composition-testing gap (§5).** The deepest issue. Is there a structural fix — contract
   tests generated from the `SKILL.md` sequences, a typed pipeline object that makes
   `merge_enriched → write_dispatch_csv` a compile-time error rather than a runtime one, or an
   end-to-end harness that runs each skill's documented sequence against stubs?
2. **`row_id` as an in-row key.** FINDING B exists because a plugin-internal correlation id lives
   inside the same dict as HubSpot properties. Should it be carried alongside (a wrapper, an
   index) rather than inside?
3. **Throughput.** `max_records_per_chunk: 2` against a ~100s synchronous n8n response window
   means a 40-record batch is 20 sequential chunks each holding a connection open. That is
   supervised, not unattended — directly against the operator's stated priority. (Owned by
   Phase 55, unstarted.)
4. **Three separate flows** (`contact-upload`, `enrich-records`, `enrich-before-ingest`) with
   overlapping steps and drifting duplicated prose. Phase 56 wants one unattended pipeline.
5. **The review lane.** Still admin-gated (§3). Phase 60 has three candidate options recorded.
6. **The durable-state directory.** FINDING A suggests the real path is too easy to reach from
   test code. Injected path? A guard that refuses to write outside a temp dir when pytest is
   running?
7. **Skill prose as contract.** The `SKILL.md` files are long and carry recorded-edit history
   inline. This is deliberate (it prevents silent weakening), but it also means the
   executable contract is prose that only a test can pin. Is there a better shape?

## 9. Reviewing this: scope and bases

The full unpushed range is **59 files / 10,155 lines**, over `/ultrareview`'s 8,000-line limit —
but **~72% of that is `.planning/` markdown**, not code.

| Base | Scope | Files / lines |
|---|---|---|
| `4bc152d` | everything this session | 59 / 10,155 — **over limit** |
| **`347ed32`** | **Phase 59 execution + gap closure + both walks** | **49 / 6,401 — fits** |
| `4e919a9` | gap closure only (59-07..59-09) | 23 / 2,012 |
| — | code only, any base | 30 / 2,875 |

**Recommended: `/ultrareview 347ed32`.**

**Note:** `origin/master` was moved to HEAD by a push that did not originate from this session —
flagged rather than assumed. A useful side effect: the marketplace clone can now fetch 0.28.0,
which unblocks the operator-chair walk that § 10 names.

## 10. What "done" would look like

- An operator, in Claude Desktop, with no terminal, opens **one** grant at session start and
  carries a batch through **ingest → enrich → create → associate → write** unattended.
- That has **never happened**. Two walks have been run (2026-08-28, 2026-08-29). Walk 1 halted at
  the merge; walk 2 got past it and halted at the CSV write. **Zero HubSpot writes in either.**
- The success criterion (`GRANT-01`) remains **unticked**, correctly.
- Both walks ran from Claude Code **with** a terminal, so even a pass would test the composition
  and not the operator's actual constraint set.

## 11. Reviewer's checklist

1. Sweep for **composition breaks** — every `SKILL.md` documented call sequence, checked against
   whether a test drives that sequence end to end (§5). Highest value.
2. Confirm or refute **FINDING A** and **FINDING B** (§6), and look for siblings of both.
3. Look for **any remaining admin-only path** an operator could hit in normal work (§3).
4. Check the **unattended path** (`scheduled_arm.py`, `sweep_*.py`) for anything that can hang,
   stall silently, or need a human mid-run.
5. Check **write-safety invariants** still hold: empty allowlist denies everything; per-send
   window ⊆ grant; disarm always runs and a failed disarm is loud.
6. Check the **oracle/n8n parity** rule has not been broken (§7).
7. Propose refactors against §8 — but check each against §7 first; several "obvious"
   simplifications are load-bearing safety.

## 12. Orientation reading, in order

1. `CLAUDE.md` — the spec. **Read its § 4.0, § 10.3.1, § 13.0, § 13.0.1, § 29.1 "as-built delta"
   blocks first**; the main tables are the original design and several are stale.
2. `.planning/phases/53-operator-openable-write-grant/53-WALK-RECORD.md` and
   `53-WALK-RECORD-2.md` — the only two end-to-end exercises ever performed. Best evidence of how
   this actually behaves.
3. `.planning/phases/59-frictionless-write-path/59-CONTEXT.md` — decisions D-59-01..D-59-10.
4. `.planning/phases/59-frictionless-write-path/59-VERIFICATION.md` — 18/18, and what that does
   and does not mean.
5. `.planning/ROADMAP.md` § v1.1 — phases 53–60, what shipped and what is deferred.
