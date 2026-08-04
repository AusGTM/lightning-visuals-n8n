# Operator UAT — v0.6

**For the operator, in Claude Desktop.** No terminal, no n8n, no HubSpot admin. Every step is
something you say; the pass criteria are things you can see.

**Cost:** sessions 1–4, 6, 7 and 8 cost **nothing** — the plugin is disarmed by default and every
dispatch stops at a preview you can abort (DISPATCH-03, PREVIEW-04). Only session 5 spends
money, and it says so before it does. (In session 7, only ask to "run now" a workflow the
steps name as safe — running the enrichment workflow spends provider credits.)

**If any step fails, stop and report it.** A step that "sort of worked" is a fail — write down
what you saw instead. The point of UAT is to find the gap between what was promised and what
arrived, not to get a clean sheet.

**The Result column** records one of three values:

- **PASS** — pre-filled only where an admin-run live canary observed that exact behaviour
  (the RB-# references are sections of the admin `OPERATOR-RUNBOOK.md`; plan numbers like
  23-02 are the phase evidence on disk). Pre-filled 2026-08-04 at the v0.6 seal.
- **UNTESTED** — nothing has walked this step end-to-end in a live conversation yet. Unit
  tests may cover the machinery underneath, but that is not this document's standard: UAT
  passes on what an operator saw, not on what the suite asserts.
- **FAIL** — record it with what you saw instead of the pass criterion. None outstanding at
  pre-fill: every defect found by the canaries (BUGS 26–30 families) was fixed and re-proven.

- **FUNCTIONAL PASS (self-assessed)** — verified 2026-08-04 by driving the library or CLI
  directly, or by a named test that pins exactly this criterion. It proves the machinery behaves
  as the criterion requires; it does **not** prove an operator saw it in conversation. Treated as
  weaker evidence than PASS deliberately — a fair number of this milestone's defects lived
  precisely in the gap between "the function is right" and "the operator's path reaches it".
- **PENDING OPERATOR WALK** — the criterion governs in-conversation model behaviour (extraction,
  phrasing), which no CLI probe can settle. The enforceable half is pinned by tests; the rest
  needs a person.

An operator walk of the UNTESTED rows is still the point of this document — the pre-filled
PASSes save re-walking what a canary already proved, nothing more.

---

## Session 0 — install and set up

| # | Do | Pass when | Result |
|---|---|---|---|
| 0.1 | `/plugin marketplace add AusGTM/lightning-visuals-n8n` then `/plugin install operator-claude-plugin@lightning-visuals-operator` | It installs without you editing any file or knowing any path | **PASS** — installed live 2026-08-03 (RB-7 step 0) |
| 0.2 | `/operator-claude-plugin:initialize` | It tells you the **full path** to your settings file and names which values you still need | **FUNCTIONAL PASS** (self-assessed 2026-08-04, CLI) — `init_check.py` prints the absolute config path and per-capability readiness; operator walk not required to see it |
| 0.3 | Let it put the template in place, then fill in `n8n_url` and `webhook_secret` from your n8n admin | It never asks you to type a secret **into the chat** | **FUNCTIONAL PASS** (self-assessed) — `initialize/SKILL.md:63` instructs "they type these into the file, **not to you**"; `test_no_rendered_output_or_report_ever_contains_a_secret_value` pins that no output echoes a secret |
| 0.4 | `/operator-claude-plugin:initialize` again | Says setup is complete and changes nothing. Running it twice is safe | **FUNCTIONAL PASS** (self-assessed, CLI) — two consecutive runs returned byte-identical output; nothing written |

**Fail if:** it says you are set up while a value is still the template placeholder, or it asks
you to paste a secret into the conversation.

*Covers PLUGIN-01, PLUGIN-02, PLUGIN-03.*

---

## Session 1 — the plugin refuses safely when it cannot work

Do this **before** the happy path. A tool that fails badly is worse than one that fails loudly.

| # | Do | Pass when | Result |
|---|---|---|---|
| 1.1 | Temporarily blank `webhook_secret` in the settings file, then ask to upload contacts | It refuses in **plain language**, names the missing setting, and does **not** show a stack trace | **PASS on 0.6.0 · BEHAVIOUR CHANGED on 0.6.1 — re-walk needed.** The 0.6.1 re-walk previewed the file and invited arming instead of refusing: the skill's step-1 preflight (`config_gate.py` `__main__`) lost its guard when `load_config()` was loosened. Refusal now arrives only at dispatch. See todo `2026-08-04-upload-preflight-lost-its-guard` |
| 1.2 | Same state — ask for backend status | Status still works. A missing upload secret must not break the status answer | **PASS** — re-walked 2026-08-04 on 0.6.1 after fix `f57b964`: workflow/execution half answered (5 workflows, gates read off), backend half reported `webhook_secret_not_configured`, queue counts stated as *unknown, not zero* |
| 1.3 | Restore the secret | Both work again | **PASS** — UAT 2026-08-04: upload previewed 3 rows, status returned the full picture |

**Fail if:** it says the plugin is "broken" or refuses everything when only one setting is
missing. Over-refusing is a defect (PLUGIN-03).

---

## Session 2 — getting contacts in, five ways

Each is a fresh message. Use your own data or anything realistic.

| # | Do | Pass when | Result |
|---|---|---|---|
| 2.1 | Paste an email signature or a few lines of prose with names and companies | Rows come back, and it says **where each value came from** | PENDING OPERATOR WALK — extraction happens in-conversation, so no CLI probe can settle it. `test_extraction_contract.py` pins that the documented examples validate and carry their ambiguity |
| 2.2 | Give it a CSV or XLSX with messy headers (`E-mail Address`, `Ph.`) | Reads them without you renaming anything first | **PASS** — 23-02 file-handoff + RB-3 live dispatch |
| 2.3 | Give it JSON in some other shape | Translated into contact rows | PENDING OPERATOR WALK — same as 2.1 (contract pinned, extraction itself is in-conversation) |
| 2.4 | Give it a public URL | Contact/company data extracted from the page | PENDING OPERATOR WALK — same as 2.1; `test_extraction_md_states_the_fetch_failed_and_nothing_usable_outcomes_separately` pins that a failed fetch and an empty result are distinct outcomes |
| 2.5 | Paste one or more screenshots of a page | Rows extracted from the image, same provenance rules | PENDING OPERATOR WALK — same as 2.1; `test_screenshot_example_artifact_collapses_to_one_row_with_one_carried_ambiguity` pins the overlapping-screenshot rule |
| 2.6 | Give it something unreadable — an empty file, a PDF of a photo | A **clear, actionable** error. Never a silent drop, never zero rows with no explanation | **SPLIT — unsupported type PASSES, empty file FAILS** (self-assessed, live probe). A `.pdf` refuses cleanly (`UnsupportedFileError: Unsupported file extension: .pdf`). An **empty `.csv` returns `row_count: 0` with no error and no explanation**, and `SKILL.md` has no zero-row branch — so "file unreadable" and "nothing to send" are indistinguishable. Todo `2026-08-04-empty-input-previews-zero-rows-silently` |
| 2.7 | Look at any row where a field was absent in your source | It is **empty** — not guessed, not filled from the company name | PENDING OPERATOR WALK — the no-invention rule governs model output, not library output. `extraction.py` is the enforceable half and its contract tests pass |

**Fail if:** any value appears that was not in your input. Invention is the most serious defect
in this list (STRUCT-04).

*Covers INGEST-01/02/03/05/06/07, STRUCT-03/04.*

---

## Session 3 — the preview, and aborting from it

| # | Do | Pass when | Result |
|---|---|---|---|
| 3.1 | Take any batch to the point of sending | You see the **exact payload** and the **row count** before anything is sent | **PASS** — RB-3 (exact payload shown, nothing sent unarmed) |
| 3.2 | Read the cost line | An estimated **provider-credit and token cost**, with the date its rates were measured | **PASS** — UAT 2026-08-04: per-provider credit estimate + $0.21 Anthropic, rates dated 2026-07-30 with age stated; Apollo headroom explicitly *not confirmed* |
| 3.3 | Try a batch bigger than the chunk size | It shows you the **chunking plan** before sending | **PASS** — UAT 2026-08-04: 3 records → 2 chunks (2 then 1), ceiling stated as a measured bound |
| 3.4 | Say no / abort | **Nothing is sent and nothing is spent.** Ask for backend status afterwards to confirm no run started | **PASS** — UAT 2026-08-04: batch left unarmed (disarmed default *is* the abort); status confirmed no run started, nothing spent |
| 3.5 | Check what it says about credits | If a balance is unknown it says **unknown** — never `0`, never "healthy" | **PASS** — UAT 2026-08-04: Apollo read `unknown` with "not zero, provider didn't answer"; Lusha 3930 / ZoomInfo 9301 real |

**Fail if:** aborting still costs something, or an unknown balance renders as zero.

*Covers PREVIEW-01/02/03/04, STATUS-06.*

---

## Session 4 — asking what the backend is doing

| # | Do | Pass when | Result |
|---|---|---|---|
| 4.1 | "What's the backend doing?" | **One plain-language answer.** No JSON, no node names, no n8n jargon | **PASS** — RB-4 |
| 4.2 | Ask about a run that failed | The real cause **translated** — not a raw error string | **PASS** — RB-4 |
| 4.3 | Ask for the dashboard | It publishes, and shows the **same** workflows and counts as the text answer | **PASS** — RB-4 |
| 4.4 | Ask for a refresh in the same conversation | **Same URL**, timestamp moves forward | **PASS** — RB-4 |
| 4.5 | **Brand-new conversation** — ask for the dashboard again | Lands on the **same URL**, not a second one | **PASS** — RB-4 (same URL cross-session) |
| 4.6 | Anything the backend could not read | Shows as **unknown**, never zero | **PASS** — RB-4; balances re-proven real after the 29-05 unwrap fix |

**Fail if:** step 4.5 mints a new URL. That is the one step that proves the dashboard survives
a session, and it is why the state file exists.

*Covers STATUS-01/02/05/06 — this is RB-4.*

---

## Session 5 — the one that spends money

**Read the preview before approving. This is the only session with a real cost.**

| # | Do | Pass when | Result |
|---|---|---|---|
| 5.1 | Take a **small** batch (2–3 rows) to preview and approve it | It required an explicit approval — a live send is never the default (DISPATCH-03) | **PASS** — RB-3 (execution 1129) |
| 5.2 | Watch what comes back | **Per-record outcome**: accepted, matched, created, failed — row by row | **PASS** — RB-3 (verified per-record report) |
| 5.3 | If any row failed | The **failing rows are identified**, and you are told what to do about them | **FUNCTIONAL PASS** (self-assessed) — `test_build_enrichment_report_failing_rows_include_blocked_skipped_and_needs_review` itemises each failing row; `test_report_sufficiency.py` pins that a create/update row is NOT reported confirmed when HubSpot produced zero items (the failure-as-success guard) |
| 5.4 | If the run is still going | It says so and shows partial results — it does not hang or pretend to be done | **FUNCTIONAL PASS** (self-assessed) — `test_unsettled_at_the_bound_returns_still_running_with_handle_and_recheck` plus `test_settles_before_the_bound_returns_a_settled_report`: two terminal shapes, never a third |
| 5.5 | Check the records in HubSpot | They match what the report said | **PASS** — RB-3 (created contact confirmed in HubSpot) |

**Fail if:** the report is a summary count with no per-row detail, or a failure is reported as
a success.

*Covers DISPATCH-01/03/04, REPORT-01/03.*

---

## Session 6 — the review queue

| # | Do | Pass when | Result |
|---|---|---|---|
| 6.1 | Ask to see records waiting on a human | Each one's conflict is in **plain language** — what disagrees, and what each source said | **PASS** — RB-9 step 5 |
| 6.2 | Look for a HubSpot link | Present if the portal id is configured; if not, it says the link is missing rather than guessing a URL | **FUNCTIONAL PASS** (self-assessed, live) — `record_link()` returns the real URL with the portal id configured (`22617666`) and **`None` rather than a guessed URL** when portal id or record id is missing. The "says the link is missing" half is unexercised here because the portal id IS configured |
| 6.3 | Resolve one conversationally | It asks for a **separate confirmation** before writing back — approving a review is not covered by any earlier approval | **PASS** — RB-9 step 6 |
| 6.4 | Reject one | The rejection **reason is recorded** and the record **stays in the queue** | **PASS** — RB-9 step 7 |
| 6.5 | After an approve lands | It stamps that a **human** made it, with timestamp and your reason — and the record's history still shows what the machine had said before you overrode it | **PASS** — RB-9 close 2026-08-04 (human provenance stamped, machine source readable) |
| 6.6 | If a held value includes a **protected** field (e.g. `domain`) | It is **labelled protected and withheld** — the approve applies the other fields and says which one it withheld. The protected field never changes | **PASS** — RB-9 close (`domain` withheld on preview AND submit) |
| 6.7 | If the backend refuses | The refusal **names the gate** — "not on the allowlist", "not a value HubSpot accepts" — never a bare failure or an empty answer | **PASS** — Phase 31 canary (explicit enum refusal, live) |

**Fail if:** a review writes back without its own confirmation step (REVIEW-03).

**Note:** an approve that actually lands needs the backend opened by an admin first (a
deploy-time write flag plus a record allowlist, and an environment variable on your machine).
Without that, steps 6.1–6.3 and 6.7 still work — the preview shows the exact write and the
submit refuses naming what is closed. That refusal is a **pass**, not a fail.

*Covers REVIEW-01/02/03/04/05 — proven live 2026-08-04 (RB-9 close).*

---

## Session 7 — controlling the backend

| # | Do | Pass when | Result |
|---|---|---|---|
| 7.1 | Ask to turn a scheduled workflow **off**, then **on** again | Each change asks for its own confirmation first, then reports the new state **read back from the backend**, not assumed | **PASS** — RB-5 (on/off roundtrip) |
| 7.2 | Ask to change a schedule's cadence | You see current cadence and proposed cadence **before** confirming; afterwards the new cadence is read back | **PASS** — RB-5 (cadence change, execution spacing measured) |
| 7.3 | Ask for something outside the allowlist (e.g. "edit the workflow's nodes", "change a credential") | It refuses and says that is an **admin task**, not a plugin action | **FUNCTIONAL PASS** (self-assessed, live) — refusal names the boundary ("does not change workflow structure, nodes, or credentials") and points at the admin |
| 7.4 | Ask to arm live writes without the admin having opened the backend | It refuses **naming the closed gate** and who opens it — it never pretends to be armed | **PASS** — RB-9 step 6b (refusal names the closed gate, zero requests) |
| 7.5 | After any mutation | Backend status reflects it — the two answers agree | **PASS** — RB-5 (before/after read-back comparison) |

**Fail if:** a mutation happens without its own confirmation, or a state change is reported
from memory rather than read back.

*Covers CONTROL-01…07 — the armed dispatch path itself was proven in RB-7 (admin-audited).*

---

## Session 8 — notices

| # | Do | Pass when | Result |
|---|---|---|---|
| 8.1 | After approving a send (session 5), stay in the conversation | When the run settles it **reports itself** — you did not have to ask | **FUNCTIONAL PASS** (self-assessed) — `test_watch_settle_reporting.py` pins that a settled run renders the same counts as the report directly and never re-renders a second outcome shape |
| 8.2 | Run the sweep on demand (`/operator-claude-plugin:backend-sweep`) | It reports **only what needs a human** — or says the backend is healthy and reports nothing else | **PASS** — RB-8 (notice path + healthy silence, real cron) |
| 8.3 | Ask what the unattended schedule would have said | Same answer as 8.2 — the on-demand run is exactly what the next unattended fire would report | **PASS** — RB-8 (wrapper emits byte-identical JSON to the on-demand run) |

**Unattended firing is an admin install** (a `cron`/`launchd` entry per
`skills/backend-sweep/SWEEP-CRON-TEMPLATE.md` — terminal commands, so not part of *operator*
UAT). If notices are expected but never arrive, the first thing to check is whether that
schedule was ever installed — an uninstalled trigger is silent; an installed-but-broken one
now announces itself.

*Covers NOTICE-01…05 — the unattended path was proven under real cron 2026-08-03 (RB-8).*

---

## Reporting your results

For each session, one line: **pass**, or **what you saw instead**. Include the step number.

The three that matter most, in order:

1. **Any invented value** (2.7) — a field that was not in your input.
2. **A failure reported as success** (5.2–5.3, 6.3).
3. **The dashboard minting a second URL** (4.5).

A "small" thing you noticed and dismissed is worth reporting. Three real defects in this
milestone were found exactly that way — by someone walking the steps and saying "that looked
odd" rather than assuming it was meant to be like that.
