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
| 2.1 | Paste an email signature or a few lines of prose with names and companies | Rows come back, and it says **where each value came from** | **PASS** — operator walk 2026-08-04 on 0.7.3 |
| 2.2 | Give it a CSV or XLSX with messy headers (`E-mail Address`, `Ph.`) | Reads them without you renaming anything first | **PASS** — operator re-walk 2026-08-05 on `0.9.0`. Four headers mapped with nothing typed (`E-mail Address`, `Org.`, `Position`, `LinkedIn Profile`); `Ph.` proposed as `phone` with its own sample values shown (`03 9012 3344`, `0400 555 010`, `03 9555 0142`) for a per-header yes; `Notes` reported dropped, not silently lost; `Full Name` offered to the reviewed per-row splitter — 4 clean, 3 flagged first with their reasons (empty cell, `Maria Jane Santos` middle-name-vs-surname, `Cher` single word), and `Jan van der Berg` kept whole as one surname rather than cut on whitespace. Nothing mapped or split before the operator answered. **History below kept deliberately — this row failed twice before it passed, and how it failed is the record.** ~~FIXED IN 0.8.0 — AWAITING OPERATOR RE-WALK.~~ Phase 34 added `e-mail address`, `org.` and `linkedin profile` to the alias table (all three tables moved together, pinned equal by `columnMapAliasParity.test.mjs`), so 4 of the 7 headers now map with nothing typed. ~~`Full Name` is refused with its reason named; this system deliberately has no name-splitter.~~ **Superseded in `0.9.0`** — the flat refusal was stricter than the suggest-and-confirm pattern beside it, so a full-name column is now split per row for the operator to review (amendment 6a). The original FAIL (operator walk 2026-08-04, 0.7.3 — the first build that could show header mapping at all) stands as recorded: 6 of 7 dropped, the plugin predicted it correctly, and the requirement and the mapping disagreed, not the code. Todo `2026-08-04-uat-22-names-aliases-the-mapping-lacks` |
| 2.3 | Give it JSON in some other shape | Translated into contact rows | **PASS** — operator walk 2026-08-04: 2 accepted, Wen correctly REJECTED (`family: null` + no email fails identity), unmapped `web` key surfaced not silently dropped, absent fields shown as `—` |
| 2.4 | Give it a public URL | Contact/company data extracted from the page | **PASS** — operator walk 2026-08-05 on `0.10.0`, against `https://gctc.com.au/board-of-directors/`. The ordinary fetch returned **0 people**; the escalation ladder's rung 1 returned **all 9 directors** and the ladder stopped there (1 of 5 permitted fetches used). Provenance names the rung-1 URL actually fetched, not the pasted page. No email, phone or `linkedin_url` on any row — none present on the source, left blank rather than guessed. **The judgement that earned the pass:** each director's day-job employer (BOQ, Norco, Cordner Advisory) appears in the source bios and was deliberately NOT used — the role this page asserts is the GCTC board seat, so jobtitle is the board role and company is the club. Filing them under their day-job employers would have been the page's context masquerading as the page's claim. The walk also stated up front that all 9 lack an email and will therefore land in `needs_review` — expected for a board page, not a failure. Nothing sent; dispatch stayed disarmed. **History: this row was held unmarked after the 2026-08-05 walk on `0.9.0`**, where the same page dead-ended — the adapter reported "likely a client-rendered page" (a conclusion its own instructions handed it, and wrong: the content was server-side available the whole time) and stopped. Phase 35 closed that gap. |
| 2.5 | Paste one or more screenshots of a page | Rows extracted from the image, same provenance rules | **PASS** — operator walk 2026-08-05 on `0.9.0`, against a LinkedIn people-search screenshot the operator captured and supplied. 6 cards read, **2 accepted / 4 rejected / 1 ambiguity**, each rejection naming its own reason. The rejections are the evidence: the "Melbourne Racing Club" chip is a SEARCH FILTER, and four cards that stated no employer were rejected rather than having the filter's company written into them — the invention this criterion exists to catch. No email, phone or `linkedin_url` was lifted off the image; those are provider-waterfall fields and a screenshot is not a route around that. `Hayden James Lowe` surfaced as an ambiguity, not a guess (middle name vs two-word surname — 0.9.0's splitter behaving the same way in the screenshot adapter as in a spreadsheet), and his card states a café, not MRC. The walk also stated up front that both accepted rows carry no email and would therefore land in `needs_review` on arrival — seeding the queue, not a finished import. Nothing sent; dispatch stayed disarmed. |
| 2.6 | Give it something unreadable — an empty file, a PDF of a photo | A **clear, actionable** error. Never a silent drop, never zero rows with no explanation | **PASS** — operator walk 2026-08-04 on 0.7.3: named the causes, stopped before approval, offered no arming phrase (the 0.7.1 branch working live) |
| 2.7 | Look at any row where a field was absent in your source | It is **empty** — not guessed, not filled from the company name | **PASS** — operator walk 2026-08-04: Tomas's absent title/phone/linkedin rendered `—`; nothing invented from company or email |
| 2.8 | Give it a row carrying **only** a LinkedIn profile URL — no email, no company | It is **accepted**, not refused, and you are **not** asked to supply a company for it | **UNTESTED** — the identity rule gained `linkedin_url` as a third group on 2026-08-30 (`config/column_mapping.yaml`, `n8n/code/columnMap.js`, pinned equal by a parity test); no operator has walked it in conversation. **Scope, so a pass is not misread:** this row tests the identity gate only. Plain contact-upload still searches HubSpot by **email alone**, so a linkedin-only row taken through *that* lane lands in `needs_review` — expected, not a failure. Matching and enriching *on* the LinkedIn URL is the **enrich-before-ingest** flow ("enrich these contacts before uploading them"); walk 2.8 there to see that half |
| 2.9 | Give it a row with a **name only** — no company, no email, no LinkedIn URL | It goes to **review**, not to a match. Being unmatched is the intended answer here | **UNTESTED** — deliberately unchanged by the 2026-08-30 identity work: a wrongly matched person is worse than an unmatched one |

**Fail if:** any value appears that was not in your input. Invention is the most serious defect
in this list (STRUCT-04). Also fail 2.9 if a name-only row is matched to somebody — turning a
weak key into a confident write is the one thing that change deliberately did not do.

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
| 5.6 | Take a batch where at least one row is uncertain (a weak match, or providers that disagree) | The run **does not stop to ask you about it mid-batch**. It finishes every row, then hands you the uncertain ones as **one review list** — each named by the person, with the reason it was held | **UNTESTED** — the hold-don't-block shape was ruled 2026-08-30; the machinery is pinned by tests, but no operator has walked a mixed batch in conversation |
| 5.7 | Interrupt a batch partway (stop it, or let a chunk fail), then run it again against the same file | It says in words which of four things happened — nothing ran before / resuming K of N / previous state unreadable, rerunning all / previous state belongs to a different run — and does not re-spend credit on rows that already settled. It asks for a **fresh** grant | **UNTESTED** — resume-or-disclose is pinned by tests; the four disclosure sentences have not been read by an operator in a live conversation |

**Fail if:** the report is a summary count with no per-row detail, or a failure is reported as
a success. On 5.6, also fail if a held row is silently dropped instead of returned by name, or
if the run stops to ask about it mid-batch. On 5.7, fail if a resume presents itself as a fresh
first run, or if unreadable previous state is trusted in part rather than rerun in full.

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
