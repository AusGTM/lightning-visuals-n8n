# Phase 29: Notices & Unattended Sweep - Research

**Researched:** 2026-07-30
**Domain:** Claude Desktop scheduled-routine hosting ("Cowork" scheduled tasks), Anthropic Managed
Agents deployments (documented alternative), n8n executions-API duration/condition detection,
read-only-by-construction enforcement
**Confidence:** MEDIUM — the read-side detection logic (which reuses Phase 27's surface verbatim)
is HIGH confidence. The phase's two riskiest bets — whether a scheduled Claude routine is truly
available on this account, and whether an in-session watch can report back unprompted without
degrading to the scheduled mechanism — are graded MEDIUM/LOW and are exactly what D-04 and the
phase's own framing flagged as needing verification before building, not assuming.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Sweep host**
- **D-01:** The unattended sweep is a **Claude scheduled routine that reuses the plugin's existing
  read paths** — Phase 27's status surface on a cadence, pushing a notification when something
  needs a human.
- **D-02:** This makes **NOTICE-05 structural rather than promised**: the sweep calls only read
  endpoints, so it *cannot* burn credits, enable writes, or dispatch. The plan must keep it that
  way — the sweep must have no code path to a mutation or a dispatch, not merely avoid calling one.
- **D-03:** The notice lands **where the operator already is**, rather than in a separate channel
  they would have to watch. — **Reversibility:** costly — moving to an n8n-side or cron-hosted
  sweep later means rebuilding both the scheduling and the delivery path.
- **D-04:** **Dependency the plan must verify early:** this assumes scheduled Claude agents are
  available on the operator's account. If they are not, the sweep has no host and the phase needs
  a different mechanism — verify before building, do not discover mid-implementation.

**In-session watch bound**
- **D-05:** The watch bound is an **admin-config value with a sane default**. The default is tuned
  to observed run times; an admin can raise it for a slow backend.
- **D-06:** The bound must be **empirical, not guessed**. Enrichment runs the full provider + Haiku
  + Sonnet chain per record, and 25-RESEARCH.md established that **no batch-timing data exists in
  this repo yet**. Deriving the default therefore needs a measurement task, shared with Phase 25's
  chunk-size measurement (25-CONTEXT D-11a) rather than duplicated.
- **D-07:** At the bound the run is reported as **still running, with how to re-check** — reusing
  Phase 26's run handle (26-CONTEXT D-06). The watch **never simply goes quiet** (NOTICE-02).

**What the sweep reports**
- **D-08:** The sweep is **silent when the backend is healthy** (NOTICE-04). Only these conditions
  produce a notice: a failed scheduled run, a credential or auth failure, an exhausted quota, a
  stuck lock, or a review backlog past its configured threshold.
- **D-09:** Every notice states **whether the operator or an admin can act on it** (NOTICE-04),
  using the same attribution discipline as Phase 27 D-04/D-05 — including its guardrail that an
  unrecognized cause defaults to admin attribution rather than telling the operator they can fix
  something the table does not recognize.
- **D-10:** A **stuck-armed backend** is one of the conditions the sweep watches for. Phase 28 D-03
  names this sweep as the backstop for the crash window between arm and disarm.

### Claude's Discretion
- Sweep cadence default and whether it is admin-configurable.
- Notification wording and grouping when several conditions fire at once.
- Review-backlog threshold default.
- Backoff schedule within the in-session watch.
- Whether the watch reports incrementally as chunks settle or only once at the end.

### Deferred Ideas (OUT OF SCOPE)
- **Unattended ingestion** — permanently deferred by REQUIREMENTS.md §"Future Requirements". The
  sweep never dispatches.
- **Acting on findings automatically** — out of scope. Notices point at Phase 28's controls; a
  human decides.
- **Alternative sweep hosts (n8n-side, OS cron)** — considered and rejected (D-01). Revisit only if
  D-04's availability check fails.
- **Per-condition notification channels** — all notices use one delivery path in this phase.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| NOTICE-01 | After a dispatch, keep watching until the run settles and report back unprompted with per-record outcomes and cost | §"In-session watch mechanics" — the single highest-risk finding in this document: genuinely unprompted mid-conversation follow-up requires a background-task-then-notify primitive that is *demonstrated to exist in this research session's own runtime* but is *unverified in Claude Desktop*, the phase's actual target surface |
| NOTICE-02 | The watch is bounded; an unsettled run reports "still running" with how to re-check, never goes quiet | §"D-07's bounded fallback" — mechanically simple, reuses Phase 26's run handle verbatim; this is the safety net if NOTICE-01's stronger claim doesn't hold |
| NOTICE-03 | A scheduled sweep with no session open pushes a notification for 5 named conditions | §"Claude Desktop Scheduled tasks (Cowork)" for the host; §"Sweep condition detectability" for which of the 5 conditions are actually buildable today |
| NOTICE-04 | Silent when healthy; every notice states operator-vs-admin actionability | Reuses Phase 27 D-04/D-05 verbatim — no new research needed, already answered there |
| NOTICE-05 | Read-only by construction — no code path to a mutation or dispatch | §"Read-only by construction" — a concrete, testable mechanism (dedicated module + import-graph test) is recommended below |

</phase_requirements>

## Summary

This phase's hardest questions are not about n8n or HubSpot — Phase 27 already solved the read
surface this sweep runs on, and that work ports over almost unchanged. The hard questions are about
a platform capability outside this repo entirely: whether "a Claude scheduled routine" is a real,
available, reliable host, and whether an in-session watch can genuinely speak up unprompted mid-
conversation or whether that claim quietly collapses into the same scheduled mechanism as the
sweep.

On the host question, this research found concrete, machine-local evidence that a scheduled-
routine feature exists and is enabled on this operator's own account today: `claude_desktop_config.json`
carries `"coworkScheduledTasksEnabled": true` and `"ccdScheduledTasksEnabled": true`
[VERIFIED: local file read], and a real, working scheduled routine already exists on this machine
at `~/Documents/Claude/Scheduled/weekday-morning-brief/SKILL.md` [VERIFIED: local file read] — a
plain skill (YAML frontmatter `name`/`description` + a markdown instruction body) that, on its own
cadence, drives live Slack/Gmail/Google-Calendar/HubSpot/Otter/tl;dv tool calls. That last point
matters: it demonstrates a scheduled routine gets *real, live tool access* at fire time, not a
static replay — which is the precondition D-04 needs satisfied for the sweep to actually read
Phase 27's live endpoints on a timer. Separately, Anthropic also documents a lower-level,
API-native scheduled mechanism — Managed Agents `deployments` (cron `schedule`, `deployment_run`
audit trail, webhook-delivered outcomes) [CITED: `claude-api` skill's
`shared/managed-agents-scheduled-deployments.md`] — but that mechanism delivers via a
Console-registered HTTPS webhook the *admin* would have to receive and re-route, which is exactly
the "operator never runs a command / never handles infrastructure" boundary this milestone holds.
The Desktop Cowork routine is the better fit for D-01's literal wording and D-03's "lands where the
operator already is." **What is not verified is whether the Cowork routine can invoke this specific
plugin's skill by name** — the existing example only calls MCP-connected SaaS tools, not a sibling
plugin — so this is the first thing a plan must test empirically, exactly as D-04 already demands.

On the watch question, this session directly observed its own runtime's behavior: a
`Bash(run_in_background: true)` call kept running after this agent's turn continued, and its
completion later arrived as an unprompted `<task-notification>` system-reminder injected into the
same ongoing conversation — a live demonstration of "background task, then unprompted follow-up in
the same session." That is the literal shape NOTICE-01 asks for. **The unresolved question is
whether Claude Desktop's chat runtime — the phase's actual target, not this CLI environment —
exposes an equivalent primitive.** Local machine evidence (`claude-code`, `claude-code-vm`,
`local-agent-mode-sessions` directories under Claude Desktop's own Application Support folder)
suggests Desktop *may* embed an agentic/background execution mode, but this research could not
independently fire and observe one. Given that uncertainty, the honest position — and the one this
phase's own D-07 already designed for — is: build the bounded degrade-to-"still running, here's how
to re-check" path (D-07) as the thing that is definitely buildable, and treat true continuous
unprompted mid-conversation follow-up as a capability to verify early and use if present, not a
foundation to architect the whole phase on.

On the empirical watch-bound (D-06): `scripts/enrichment_cost_ledger.py::_list_executions()`
already fetches `/api/v1/executions`, and n8n's execution objects already carry both `startedAt`
and `stoppedAt` [CITED: n8n Execution API docs, same source Phase 27 cited] — but this repo's own
ledger code only ever reads `startedAt` and never computes a duration from the pair. No new n8n
capability or schema change is needed to get real duration data; what's missing is a small
computation this repo has never bothered to do. This is the same underlying gap Phase 25's D-11a
names (no batch-timing data exists) — one measurement task, reusing the existing executions-list
call, produces both phases' defaults.

On sweep conditions (NOTICE-03's five): reusing Phase 27's exact findings, 3 of 5 are directly
buildable today with zero new reads — failed-scheduled-run (execution status, with the same
"onError swallows provider failures" caveat Phase 27 found, and this research additionally found the
**same swallowing pattern in `wf_scheduled_maintenance_cloud.json`'s own HubSpot Search nodes**),
stuck-lock (Phase 27's `is_stuck()` execution-age helper, verbatim), and review-backlog-over-
threshold (Phase 27's HubSpot count query, verbatim — the sweep only adds the threshold
comparison). The other 2 (credential/auth failure, exhausted quota) are **not** execution-status
questions at all — they require the sweep to add threshold/classification logic on top of the
*same* provider credit-balance data Phase 27's status endpoint already returns, since expired
credentials and rate limits mostly don't fail an execution in this pipeline (Phase 27's own
finding, reconfirmed here for the scheduled-maintenance workflow too).

**Primary recommendation:** Build the sweep as Phase 27's read surface plus (a) a small
threshold-classification layer for credential-failure/exhausted-quota over the existing credit
probe, (b) Phase 27's `is_stuck()` reused verbatim for the stuck-lock condition, and (c) a
dedicated, import-graph-tested read-only module so NOTICE-05 is enforced mechanically. Host it on
Claude Desktop's Scheduled-tasks (Cowork) feature — verified available on this account today — but
make "can a scheduled routine invoke this plugin's own skill" and "does Desktop chat have an
unprompted background-notify primitive" the first two things the plan tests, not assumes. Build
D-07's bounded "still running, here's the handle" path as the load-bearing NOTICE-01/02 mechanism
regardless of what that test finds; treat true mid-conversation unprompted follow-up as a bonus if
the test confirms it, not a dependency.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| In-session watch loop after a dispatch | Client / conversation (plugin) | Platform background-task primitive, if Desktop exposes one | The watch is the plugin's own conversational logic; it borrows a platform primitive to survive past one turn, it doesn't move to the backend |
| Watch-bound "still running" fallback report | Client / conversation (plugin) | — | Reuses Phase 26's run-handle renderer; no new tier |
| Unattended sweep host (the timer itself) | Platform (Claude Desktop Scheduled tasks / Cowork) | — | D-01: this is explicitly *not* an n8n-side or OS-cron mechanism; it is a Claude-platform feature |
| Sweep's read logic (what it checks) | API/Backend read surface (Phase 27's endpoint + client executions read) | — | D-02: the sweep's checks are Phase 27's reads on a timer, nothing new |
| Credential-failure / exhausted-quota classification | Client / sweep module | API/Backend (source data: the credit-probe endpoint) | The raw balance already comes from Phase 27's n8n-side endpoint; "is this exhausted" is a threshold judgment the sweep adds, not a new read |
| Read-only enforcement (NOTICE-05) | Client / plugin (dedicated module + import-graph test) | — | Structural, not policy — must be checkable independent of what the sweep's logic happens to call this week |
| Notification delivery | Platform (Claude Desktop notification / in-app surface) | — | D-03: lands where the operator already is; not an n8n or email concern |

## Standard Stack

No new library or package. This phase composes platform capabilities and Phase 27's already-built
read surface; nothing here is `pip install`-able.

| Surface | What it's for | Already exercised by |
|---|---|---|
| `GET /api/v1/executions`, `GET /api/v1/workflows` | Failed-run / stuck-lock / in-flight detection | Phase 27's client read surface, `scripts/enrichment_cost_ledger.py` (this repo) |
| `hubspot/backend-status` (n8n-side, Phase 27) | Credit balances, queued/review-backlog counts | Phase 27's endpoint design |
| Claude Desktop Scheduled tasks ("Cowork") | Sweep host (D-01) | Locally verified: `coworkScheduledTasksEnabled: true` in `claude_desktop_config.json`; a live working example (`~/Documents/Claude/Scheduled/weekday-morning-brief/SKILL.md`) already fires on a cadence and drives real MCP tool calls on this machine |
| Anthropic Managed Agents `deployments` API | Documented alternative host — **not selected**, see below | `claude-api` skill, `shared/managed-agents-scheduled-deployments.md` / `shared/managed-agents-api-reference.md` [CITED — bundled reference docs, not independently hit against a live API key this session] |
| Claude Code's `Bash(run_in_background)` + task-notification injection | Concrete, *directly observed* example of "background task, unprompted follow-up in the same session" — the shape NOTICE-01 wants | Observed live in this research session (two backgrounded `find` calls each produced an unprompted `<task-notification>` system-reminder on completion) — but this is the CLI runtime, not Desktop, the phase's actual target |

**Installation:** none.

## Package Legitimacy Audit

Not applicable — this phase installs no external package. It composes an existing n8n/HubSpot read
surface (Phase 27) with a Claude-platform scheduling feature; no new dependency is added to any
ecosystem.

## Architecture Patterns

### System Architecture Diagram

```
[In-session watch — NOTICE-01/02]

Operator approves + dispatches a batch (Phase 23/25/26 machinery)
        │
        ▼
Plugin/client: dispatch returns (sync response or fallback to executions API, Phase 26 D-01)
        │
        ├─ run has settled already ──────────────► Phase 26's outcome renderer, done
        │
        └─ run still in flight
                │
                ▼
        Plugin attempts to keep watching past this turn
                │
                ├─ IF a background-task-then-notify primitive exists in this runtime
                │     (CONFIRMED in Claude Code CLI this session; UNVERIFIED in Claude Desktop)
                │     → poll GET /api/v1/executions on an interval
                │     → run settles → unprompted report: per-record outcomes + cost (NOTICE-01)
                │
                └─ IF no such primitive, or the watch-bound elapses first (D-05/D-06)
                      → report "still running" + the run handle (Phase 26 D-06) + how to
                        re-check (D-07) — THIS PATH IS THE ONE TO BUILD FIRST; it never
                        depends on an unverified platform capability (NOTICE-02)


[Unattended sweep — NOTICE-03/04/05]

Claude Desktop Scheduled task ("Cowork" routine, D-01)
  fires on its own cadence, no session open
        │
        ▼
Sweep's dedicated read-only module (NOTICE-05 — no import of any mutation/dispatch code)
        │
        ├──► GET /api/v1/executions  ─────► failed-scheduled-run? (execution status;
        │                                    same onError-swallows-errors caveat as Phase 27)
        │                              ─────► stuck lock? (Phase 27's is_stuck(): status=running
        │                                    + execution age > threshold — reused verbatim)
        │
        └──► hubspot/backend-status (Phase 27's n8n-side endpoint)
                                       ─────► credential/auth failure? (new: threshold/shape
                                              classification over the existing credit-probe result)
                                       ─────► exhausted quota? (new: balance <= configured floor)
                                       ─────► review backlog > threshold? (Phase 27's count,
                                              sweep adds the threshold compare)
        │
        ▼
Any condition fired? ── no ──► silent (D-08/NOTICE-04)
        │
       yes
        ▼
Build notice: plain-language cause + operator-vs-admin attribution (D-09, reuses Phase 27 D-04/D-05)
        │
        ▼
Push via Claude Desktop's notification surface (D-03 — lands where the operator already is)
```

### Recommended Project Structure

```
operator-claude-plugin/
├── sweep/
│   ├── conditions.py       # pure functions: is_stuck(), is_review_backlog_over(),
│   │                       #   is_credential_failed(), is_quota_exhausted() — each takes
│   │                       #   already-fetched data, returns bool + reason; no I/O here
│   ├── read_client.py      # THE ONLY module allowed to call the n8n/HubSpot-status reads
│   │                       #   used by the sweep — imports nothing from dispatch/control code
│   └── notify.py           # formats the notice text (D-09 attribution) and hands it to
│                           #   whatever Desktop-native notification call the plan's early
│                           #   verification task confirms is reachable
└── (existing Phase 23-28 structure, untouched)

# Outside the plugin's own source tree — a platform object, not a git-tracked file the
# plugin ships:
~/Documents/Claude/Scheduled/<sweep-name>/SKILL.md   # the scheduled routine itself; an
                                                       # admin-authored instruction body that
                                                       # calls into sweep/read_client.py's
                                                       # logic (however Phase 23 exposes it —
                                                       # as a plugin skill the routine invokes)
```

Note the seam this creates: the sweep's *logic* lives in `operator-claude-plugin/` per PLUGIN-04,
but the sweep's *trigger* (the Scheduled-task SKILL.md) lives in a machine-local, non-git-tracked
location outside the plugin's own packaging. Installing the sweep is therefore a two-part admin
step — install the plugin, then author/enable the Scheduled routine that calls it — not a single
`plugin install`. Plan for this as an explicit setup task, not an implicit side effect of shipping
the plugin.

### Pattern 1: Read-only by construction (NOTICE-05, D-02) — a concrete, testable mechanism

**What:** A structural guarantee needs to be checkable by a machine, not just true by discipline.
Recommended shape: `sweep/read_client.py` is the *only* module the sweep's entrypoint imports, and
it in turn imports only GET-shaped functions (no `requests.post`/`.patch`/`.put` call exists
anywhere in its transitive import graph). A repo-level test statically walks the AST of every
module reachable from the sweep's entrypoint and asserts none of them defines or calls a function
whose name/signature matches this repo's existing mutation surface (Phase 28's control actions,
Phase 23/25's dispatch POSTs). This mirrors a pattern already in production in this repo:
`scripts/enrichment_cost_ledger.py`'s own docstring guarantee ("No PATCH/POST path to n8n or a
provider match/enrich endpoint exists here") — the only change recommended here is enforcing that
guarantee with an automated import-graph test instead of a comment, since NOTICE-05 explicitly asks
for "no code path," not "a policy it promises to follow."

**When to use:** Any module whose entire safety property is "cannot write," where "we didn't call
it this time" is not a strong enough guarantee.

**Example (sketch — adapt to whatever runtime Phase 23 lands on):**
```python
# tests/test_sweep_read_only.py — sketch; ports the *pattern* of enrichment_cost_ledger.py's
# self-declared guarantee into something CI actually checks.
import ast
from pathlib import Path

FORBIDDEN_CALL_NAMES = {"post", "put", "patch", "dispatch_batch", "activate_workflow",
                         "set_write_gate", "run_control_action"}  # extend as Phase 28 lands

def _imported_modules(module_path: Path) -> set[str]:
    tree = ast.parse(module_path.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names

def test_sweep_module_graph_has_no_mutation_import():
    # walk operator_claude_plugin/sweep/*.py transitively; assert none of
    # FORBIDDEN_CALL_NAMES appears as a call target anywhere in the graph
    ...
```
[ASSUMED: exact test shape — the pattern (AST-based import-graph assertion) is sound regardless of
runtime, but this repo has no precedent for it yet; treat as a new but well-understood technique]

**One open question worth flagging, not answering here:** whether n8n Cloud API keys can be scoped
read-only at the platform level (a second, independent enforcement layer) is unverified in this
research session — n8n's Public API key model has historically been all-or-nothing per instance
rather than per-scope. If that holds, NOTICE-05's guarantee is entirely a *client-side* software
property (the import-graph test above), not something n8n itself can also enforce. Verify this
before promising a defense-in-depth story that assumes n8n-side scoping exists.

### Pattern 2: Claude Desktop Scheduled tasks ("Cowork") — the sweep's host (D-01, D-04)

**What:** Claude Desktop (this machine: `com.anthropic.claudefordesktop`, version `1.24012.9`) has
a working scheduled-routine feature, evidenced three ways on this machine:
1. `~/Library/Application Support/Claude/claude_desktop_config.json` carries
   `"preferences": {"coworkScheduledTasksEnabled": true, "ccdScheduledTasksEnabled": true, ...}`
   [VERIFIED: local file read].
2. A real, already-authored scheduled routine exists at
   `~/Documents/Claude/Scheduled/weekday-morning-brief/SKILL.md` [VERIFIED: local file read] — a
   plain skill file (YAML frontmatter `name` + `description`, then a markdown instruction body)
   that on its own cadence pulls live data via Slack, Gmail, Google Calendar, HubSpot, Otter, and
   tl;dv tool connectors and produces a formatted brief. This is direct, on-this-machine evidence
   that a scheduled routine gets **live tool/connector access at fire time**, not a canned replay —
   the precondition D-01/D-04 need.
3. The app bundle (`app.asar`) bundles the `cronstrue` npm package (a cron-to-human-language
   formatter) [VERIFIED: `strings` scan of the bundled resource], consistent with the app
   internally representing schedules as cron expressions and rendering them in plain language for
   the user — the same "plain terms, not cron syntax" convention this milestone's CONTROL-03
   already independently adopted for n8n's Schedule Trigger cadence.

**When to use:** This is the concrete answer to D-04's "verify before building" instruction: on
this operator's own account, right now, scheduled Claude routines are enabled and demonstrably
functional. Treat D-04 as **satisfied for this machine** — but re-run this same three-point check
(`claude_desktop_config.json` flags + attempt to author one trivial Scheduled skill) on whatever
machine actually runs the sweep in production, since the flag is local preferences, not a
guaranteed account-wide entitlement independently confirmed against Anthropic's plan tiers this
session.

**What is NOT verified:** whether a Scheduled routine's markdown body can invoke *this specific
plugin's* installed skill by name (as opposed to a generic MCP tool connector like Slack/Gmail).
Nothing in the `weekday-morning-brief` example does this — it only calls SaaS connectors. The
Skill-tool mechanism is, architecturally, just markdown instructions telling the model to act, so
there is no obvious reason a scheduled routine's body couldn't say "invoke the operator status
skill" the same way an interactive session's system prompt does — but this is an inference from
how skills work generally, not an observed test of a scheduled routine actually doing it.
**Recommend this as the plan's first task**: author a trivial Scheduled skill whose body invokes
the plugin's own read-only status skill and confirms real data comes back, before committing the
sweep's architecture to this path.

### Pattern 3: Managed Agents `deployments` (Anthropic API) — documented alternative, not selected

**What:** Anthropic's Managed Agents API has a fully separate, lower-level scheduled-agent
primitive: `client.beta.deployments.create(agent=..., environment_id=..., schedule={"type": "cron",
"expression": ..., "timezone": ...})` [CITED: `claude-api` skill, `shared/
managed-agents-scheduled-deployments.md`]. Cron is POSIX 5-field with IANA timezone and literal
wall-clock DST matching (documented DST double-fire/skip edge case on transition days); execution
is jittered up to 15% of the interval (floor 5s, cap 9 min) to spread load; every trigger — success
or failure — writes an auditable `deployment_run` record; outcomes are delivered as **webhooks**
(`deployment.*` / `deployment_run.*` events) to a Console-registered HTTPS endpoint, HMAC-signed,
thin (IDs only, you fetch the rest) [CITED: `shared/managed-agents-overview.md`,
`shared/managed-agents-events.md`].

**When to use:** This is the right tool if the sweep were ever re-hosted as a standalone backend
service with its own webhook receiver and its own notification fan-out (email/Slack/etc.) — i.e.
the "alternative sweep hosts" this phase's CONTEXT.md explicitly rejected (D-01, "Alternative sweep
hosts (n8n-side, OS cron) — considered and rejected... Revisit only if D-04's availability check
fails"). It is **not** a good fit for D-03 ("lands where the operator already is") as-is: a webhook
requires the admin to stand up and receive it, and the "notification" only reaches the operator if
someone builds a second delivery hop from that webhook into wherever the operator is looking — that
is real extra infrastructure this milestone's non-technical-operator constraint is built to avoid.
Keep this in reserve as D-04's fallback plan, not the default.

**Anti-pattern to avoid:** treating "the phase says 'Claude scheduled routine'" as license to reach
for whichever scheduling API is best documented (this one has excellent reference docs) rather than
the one that actually satisfies D-03's delivery constraint. The better-documented mechanism is not
automatically the right one here.

### Pattern 4: In-session watch — what "unprompted" can actually mean (NOTICE-01, highest risk)

**What was directly observed this session:** two `Bash(..., run_in_background: true)` calls kept
executing after this agent's turn moved on; each one's completion later arrived as an unprompted
`<task-notification>` system-reminder injected into this same ongoing conversation, which this
agent then read and acted on without the user saying anything. That is a working, concrete instance
of exactly the shape NOTICE-01 describes — "keep watching... report back unprompted" — in *this*
runtime (a Claude Code CLI agent session).

**What is not established:** whether Claude Desktop's chat surface — the phase's actual target,
since the whole milestone's framing is "the operator works in Claude Desktop, never opens a
terminal" — exposes an equivalent primitive for a single open conversation. Suggestive but
unconfirmed local evidence: Claude Desktop's own Application Support directory contains
`claude-code/`, `claude-code-vm/`, and `local-agent-mode-sessions/` subdirectories [VERIFIED:
directory listing], implying Desktop may embed an agentic/background execution mode of some kind —
but this research did not fire one from inside an actual Desktop conversation and observe whether a
background result can surface as an unprompted follow-up message in that same open chat.

**Recommendation:** Do not architect NOTICE-01 as if the strong claim ("truly unprompted mid-
conversation follow-up") is guaranteed. Build D-07's fallback first — bounded watch, "still
running" + run handle + re-check instructions, entirely deliverable with mechanisms already proven
in this milestone (Phase 26's renderer, a timeout/interval check) — and treat it as NOTICE-01/02's
real, load-bearing implementation. If the plan's early verification task confirms Desktop chat
*does* support an equivalent background-then-notify primitive, layer genuinely unprompted
completion on top as an enhancement; if it doesn't, D-07's bounded report is not a degraded
experience, it's the one honest thing to promise.

### Anti-Patterns to Avoid

- **Assuming "scheduled Claude routine" and "Managed Agents deployment" are the same feature.**
  They are two different products with two different delivery models (in-app/Desktop notification
  vs. developer webhook). Conflating them will produce a plan that designs a webhook receiver this
  milestone has no room for, or that assumes Desktop's Scheduled tasks have an audit-trail/cron
  object model they may not expose the same way.
- **Treating a config-flag check (`coworkScheduledTasksEnabled: true`) as proof the *specific*
  capability the sweep needs (invoking this plugin's skill from a scheduled routine) works.** The
  flag proves the feature is on; it does not prove the composition this phase needs.
- **Reviving `enrichment_lock_until`-style stuck-lock detection.** Already settled by Phase 27 —
  reuse `is_stuck()` (execution-age based), don't re-litigate it here.
- **Treating "onError: continueRegularOutput" as only an enrichment-workflow problem.** This
  research found the same pattern on `wf_scheduled_maintenance_cloud.json`'s own `SJ-*`/`Review
  Search` HubSpot-read nodes — a broken HubSpot credential during the *scheduled maintenance job
  itself* would likely still show `execution.status: success`. NOTICE-03's "failed scheduled run"
  condition inherits this same blind spot, not just the enrichment lane's.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Stuck-lock detection | A new HubSpot lock-property scheme | Phase 27's `is_stuck()` (execution `status=running` + age > threshold), reused verbatim | Phase 27 already established the literal property doesn't exist and designed the replacement; re-deriving it risks silently diverging |
| Review-backlog count | A new HubSpot Search filter | Phase 27's exact `lv_enrichment_needs_review` / `lv_icp_needs_review` OR'd filter | Same real property names Phase 27 verified live; the generic names in root `CLAUDE.md` don't exist |
| Run handle / "how to re-check" | A second run-reference format | Phase 26 D-06's run handle and outcome renderer | D-07 explicitly says reuse it — the watch is built once |
| Cron-to-plain-language cadence text | A hand-rolled cron humanizer | If any cadence needs to be shown, the same convention CONTROL-03 already committed to (plain terms, not cron), and note Desktop's own bundled `cronstrue`-based approach as prior art for the *pattern*, not something to import | Avoids inventing a second, possibly inconsistent phrasing convention in the same milestone |
| Read-only enforcement | A code-review checklist alone | An automated AST/import-graph test (Pattern 1) | NOTICE-05 explicitly wants "no code path," which a checklist cannot guarantee once the codebase grows |

**Key insight:** almost every read this phase needs already exists in a live-validated form from
Phase 27. The only genuinely new work is (a) a thin threshold/classification layer over that data
for 2 of 5 sweep conditions, and (b) an automated enforcement test for the read-only guarantee.
Everything else is composition, not invention — the risk in this phase is entirely in the platform
capabilities (scheduling, in-session background notify) that sit outside this repo's own code.

## Common Pitfalls

### Pitfall 1: "Failed scheduled run" is not fully visible from execution status
**What goes wrong:** The plan assumes reading `execution.status` for the scheduled-maintenance
workflow's runs reliably surfaces "a scheduled run failed," the same way Phase 27 assumed for the
enrichment workflow before finding the gap.
**Why it happens:** `wf_scheduled_maintenance_cloud.json`'s own HubSpot-Search-reading nodes
(`SJ-3 Search`, `SJ-1 Search`, `SJ-2 Search`, `Dedupe Search`, `Review Search`) are **all**
configured `onError: continueRegularOutput` [VERIFIED: direct node-by-node inspection this
session]. Only the plain write-back nodes (`SJ-1 Set Requested`, `SJ-2 Set Requested`, `Dedupe Set
Needs Review`, `Review Apply Update`) have no `onError` override and would actually fail the
execution.
**How to avoid:** Treat "failed scheduled run" as reliably detectable only for the subset of
failure modes that reach one of those un-overridden write nodes; anything upstream (a broken
HubSpot credential breaking the *search* itself) will show as a "successful" execution that quietly
did nothing. Don't promise NOTICE-03's "failed scheduled run" condition covers every way the
maintenance job could actually be broken.
**Warning signs:** The scheduled maintenance job's executions all show `success` for weeks while
the queued/review counts visibly stop moving — the same "quiet failure" shape Phase 27 found for
provider credentials, now recurring in a different workflow.

### Pitfall 2: Config-flag verification is not the same as capability verification
**What goes wrong:** D-04 gets marked "verified" because `coworkScheduledTasksEnabled: true` was
found in local preferences, and the plan proceeds to build the whole sweep architecture on that
assumption.
**Why it happens:** A feature flag being on proves the platform *offers* scheduled routines; it
says nothing about whether a scheduled routine's instruction body can successfully invoke this
specific plugin's skill, which is the actual dependency the sweep needs.
**How to avoid:** Treat D-04's verification as two checks, not one: (1) is the feature enabled
(cheap, done — see Pattern 2), and (2) can a trivial Scheduled skill actually call the plugin's
read-only status logic and get real data back (not yet done — make it the plan's first task).
**Warning signs:** The sweep is fully built, wired to Phase 27's endpoint, and only then does
someone discover a Scheduled routine's markdown body cannot reach an installed plugin's skill the
way an interactive session can.

### Pitfall 3: "Read-only" enforced only by not calling a mutation this week
**What goes wrong:** The sweep module happens to import a shared HTTP client that *also* exposes
`post()`/`patch()` methods (even if the sweep's own code never calls them), and a future edit adds
one call by accident with no test catching it.
**Why it happens:** "We just don't call the write methods" is a discipline, not a structural
guarantee — exactly the distinction D-02 draws ("not merely avoid calling one").
**How to avoid:** Give the sweep its own module that imports *only* GET-shaped functions (Pattern
1), and add the AST/import-graph test so a future PR that accidentally reaches a mutation fails CI
rather than fails silently in production.
**Warning signs:** A code review that says "looks read-only" without a test that would catch a
regression.

### Pitfall 4: Guessing the watch bound instead of measuring it
**What goes wrong:** D-06 requires an empirical default; a plan that picks "5 minutes" because it
sounds reasonable violates D-06 even if the number happens to be fine.
**Why it happens:** No batch-timing data exists in this repo yet (confirmed by 25-CONTEXT D-11a),
so there is no obvious number to anchor to without doing the measurement.
**How to avoid:** `/api/v1/executions` already returns both `startedAt` and `stoppedAt` per
execution [CITED: n8n Execution API docs, same source Phase 27 used] — `scripts/
enrichment_cost_ledger.py::_list_executions()` already fetches this list but only ever reads
`startedAt`. A measurement task can compute `stoppedAt - startedAt` for recent enrichment-workflow
executions with no new endpoint, no schema change, and no new n8n capability — purely a
computation this repo has never bothered to do. Pair each duration with the record count that
execution processed (recoverable the same way `extract_token_usage()` already walks `runData` for
token counters — count the items a write node like `HubSpot Update`/`Merge Company` actually
processed) to get a genuine seconds-per-record rate, not just a per-batch duration. Do this once,
share the result with Phase 25's chunk-size default (D-11a) exactly as the CONTEXT.md instructs.
**Warning signs:** Two different phases each pick their own guessed timing constant instead of one
shared measured rate.

### Pitfall 5: Treating "unknown balance" as "exhausted quota"
**What goes wrong:** Apollo's credit probe returns `credits: None` (unknown, per Phase 27/25's
unknown-vs-zero contract) and the sweep's exhausted-quota condition fires on it, telling the
operator Apollo is out of credits when in fact the account simply can't be read.
**Why it happens:** "Exhausted" and "unknown" both look like "can't rely on this provider," but
they mean opposite things operationally and require different attribution (exhausted → admin needs
to top up; unknown → admin needs to check the API key, per Phase 27's own D-08/D-06).
**How to avoid:** The sweep's quota-exhausted condition must only fire on an explicit numeric
balance at or below a configured floor — `None`/unknown must route to a different notice (or none
at all, consistent with D-08's "unknown is never zero, never healthy") rather than "exhausted."
**Warning signs:** An "Apollo exhausted" notice for an account where Apollo has never once
returned a readable balance (this repo's own canary data shows Apollo 403s by design — that is not
exhaustion).

## Code Examples

### Deriving the watch bound empirically from data this repo already fetches (D-06)

```python
# Extends scripts/enrichment_cost_ledger.py::_list_executions(), which already returns
# the raw execution dicts (startedAt/stoppedAt included) but has never computed a duration.
from datetime import datetime, timezone

def _parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

def execution_duration_seconds(execution: dict) -> float | None:
    started, stopped = execution.get("startedAt"), execution.get("stoppedAt")
    if not started or not stopped:
        return None  # still running, or the field genuinely wasn't populated — not zero
    return (_parse_iso(stopped) - _parse_iso(started)).total_seconds()

# Pair with a record count the same way extract_token_usage() already walks runData for
# usage counters — count items at a write node (e.g. "HubSpot Update"/"Merge Company") to
# get durations-per-record, not just per-batch durations. Shared verbatim with Phase 25's
# chunk-size measurement task (25-CONTEXT D-11a).
```

### Stuck-lock reuse (verbatim from Phase 27, no new logic)

```python
# Source: 27-RESEARCH.md §"Stuck-lock detection, recommended replacement definition" —
# reused unmodified by the sweep; this is intentionally not re-derived here.
from datetime import datetime, timezone

STUCK_THRESHOLD_MINUTES = 15  # same convention Phase 27 carried from .env.example's LOCK_TTL_MINUTES

def is_stuck(execution: dict, now=None) -> bool:
    if execution.get("status") != "running":
        return False
    started = execution.get("startedAt")
    if not started:
        return False
    now = now or datetime.now(timezone.utc)
    started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
    return (now - started_dt).total_seconds() > STUCK_THRESHOLD_MINUTES * 60
```

### Exhausted-quota classification — new logic, layered over Phase 27's existing probe shape

```python
# New for this phase — Phase 27's endpoint already returns {"configured": bool,
# "credits": int | None, ...} per provider (see 27-RESEARCH Pattern 2). This adds the
# threshold judgment the raw balance alone doesn't make.
def is_quota_exhausted(provider_status: dict, floor: int = 0) -> bool | None:
    if not provider_status.get("configured"):
        return None  # no credential at all — not the same condition, don't conflate
    credits = provider_status.get("credits")
    if credits is None:
        return None  # unknown (e.g. Apollo's 403-by-design) — never "exhausted", never "healthy"
    return credits <= floor
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| Assume "scheduled Claude agent" means a developer-hosted Managed Agents deployment | Verify against the operator's actual runtime (Claude Desktop's Scheduled tasks / Cowork) first, since that's what D-03's delivery constraint actually needs | This research session | Prevents designing a webhook-receiver architecture the milestone's non-technical-operator constraint can't support |
| Root `CLAUDE.md`'s `enrichment_lock_until` stuck-lock model | Execution-age-based `is_stuck()` (Phase 27) | Phase 27 research | Already settled; the sweep just inherits it |

**Deprecated/outdated:** nothing new deprecated in this phase beyond what Phase 27 already
identified (the `enrichment_lock_until` architecture, never built).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A Claude Desktop Scheduled routine's instruction body can invoke this specific plugin's own skill by name, the same way it can call an MCP-connected SaaS tool | Pattern 2 | If wrong, D-01's host has no way to actually run the sweep's logic; the phase needs a different host (n8n-side or OS-cron, explicitly the fallback D-01 already names) — this is why it's recommended as the plan's first verification task, not assumed |
| A2 | Claude Desktop's chat runtime has an equivalent to Claude Code CLI's `run_in_background` + unprompted task-notification-injection primitive, usable within a single open conversation | Pattern 4 | If wrong, NOTICE-01's literal "reports back unprompted... during a session" cannot be built stronger than D-07's bounded "still running" report — which is explicitly an acceptable, designed-for outcome, not a failure, but the plan should not promise more than that without this confirmed |
| A3 | `coworkScheduledTasksEnabled: true` reflects an account-level entitlement (not just a locally-cached preference that could be stale or device-specific) | Pattern 2 | If wrong, the flag being true on this machine doesn't guarantee it's true wherever the sweep is actually deployed/operated — re-check on the production machine |
| A4 | n8n Cloud API keys cannot be scoped read-only at the platform level (all-or-nothing per instance) | Pattern 1 | If wrong (n8n does support scoped keys), NOTICE-05 could gain a second, platform-level enforcement layer in addition to the client-side import-graph test — worth a quick doc check before ruling it out entirely |
| A5 | The exact UI location a Claude Desktop Scheduled-task's notification surfaces at (native macOS Notification Center banner vs. an in-app inbox/badge vs. both) | Summary / Pattern 2 | Notification wording/length constraints (Claude's Discretion per CONTEXT.md) can't be finalized without knowing where and how much text actually renders; verify by firing one real test schedule and observing |

**If this table is empty:** N/A — populated above; this phase carries real, load-bearing
assumptions by its own design (D-04 says verify, don't assume) and they are listed here rather than
presented as settled fact.

## Open Questions

1. **Can a Claude Desktop Scheduled routine invoke this plugin's own skill?**
   - What we know: the feature fires on a cadence and gets live tool access (§Pattern 2's
     `weekday-morning-brief` example, verified on this machine).
   - What's unclear: whether that live tool access extends to a *sibling installed plugin's* skill,
     as opposed to only MCP-connected SaaS connectors.
   - Recommendation: make this the plan's very first task — author a trivial Scheduled skill that
     calls the plugin's own read-only status logic and confirm real data returns, before designing
     anything else around this host.

2. **Does Claude Desktop's chat runtime support an unprompted background-then-notify primitive
   within one open conversation?**
   - What we know: this exact capability was directly observed in this research session's own
     runtime (Claude Code CLI, via `run_in_background` + injected `<task-notification>`).
   - What's unclear: whether Desktop chat — the phase's actual target surface — has an equivalent.
     Suggestive but unconfirmed evidence exists (`claude-code`/`claude-code-vm`/
     `local-agent-mode-sessions` directories under Desktop's Application Support folder).
   - Recommendation: build D-07's bounded fallback as the primary NOTICE-01/02 mechanism regardless
     (it needs no unverified capability); test for the stronger unprompted-mid-conversation
     capability separately and treat it as an enhancement if confirmed.

3. **Where does the Scheduled-task push notification actually surface, and what length/formatting
   does it support?**
   - What we know: the feature exists and fires; nothing in this session's evidence pins down the
     exact rendering surface (native OS notification, in-app inbox, or both) or a character limit.
   - What's unclear: this directly affects the "Claude's Discretion" item on notification wording
     and grouping when several conditions fire at once.
   - Recommendation: fire one real test Scheduled routine and observe where its output actually
     lands before finalizing notice-text length/format decisions.

4. **Can n8n Cloud API keys be scoped read-only, giving NOTICE-05 a second enforcement layer?**
   - What we know: n8n's Public API key model has historically been all-or-nothing per instance;
     this was not independently re-checked against current n8n Cloud docs this session.
   - What's unclear: whether a recent n8n Cloud release added scoped/role-based API keys.
   - Recommendation: quick doc check before planning assumes the client-side import-graph test
     (Pattern 1) is the *only* possible enforcement layer — it's the one that's definitely
     available regardless, so plan around it either way.

5. **Exact exhausted-quota and credential-failure thresholds/signatures for each provider.**
   - What we know: Phase 27 already found that most provider auth/rate-limit failures do not fail
     an n8n execution and must be read from the credit-probe endpoint instead (Pitfall 5 here
     extends that same finding with the unknown-vs-exhausted distinction).
   - What's unclear: the exact floor value per provider (0 credits? some provider-specific minimum
     headroom?) and what a credential-failure *signature* looks like distinct from a plain zero
     balance (e.g., Lusha/ZoomInfo returning a 401 body shape vs. a legitimately-zero balance).
   - Recommendation: treat as Claude's Discretion for the default floor value (per CONTEXT.md), but
     make the None-vs-exhausted distinction (Code Examples above) a hard requirement, not
     discretionary.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Claude Desktop Scheduled tasks ("Cowork") | NOTICE-01 (fallback path aside), NOTICE-03 (sweep host) | Available on this machine — `coworkScheduledTasksEnabled: true`, `ccdScheduledTasksEnabled: true`, live working example present [VERIFIED locally] | Claude Desktop `1.24012.9` | If unavailable on the production machine: Anthropic Managed Agents `deployments` (Pattern 3) as a documented but heavier alternative — requires a webhook receiver and a second delivery hop, per D-04's own named fallback |
| n8n Cloud `/api/v1/executions`, `/api/v1/workflows` | Stuck-lock, failed-run, in-flight detection | Already used successfully by Phase 27's design (this repo) | n8n Cloud Public API v1 | None needed — same credential already proven live |
| `hubspot/backend-status` (Phase 27's n8n-side endpoint) | Credential-failure/exhausted-quota/review-backlog conditions | Designed in Phase 27, not yet implemented at research time for this phase — depends on Phase 27 landing first | n/a | None — this phase has no path around Phase 27's endpoint existing |
| A background-task-then-notify primitive in Claude Desktop chat | NOTICE-01's strongest claim ("unprompted... during a session") | **Unverified** — directly demonstrated only in this session's own CLI runtime, not tested against Desktop | n/a | D-07's bounded "still running" report — fully available today, no unverified capability required |
| `operator-claude-plugin/` runtime | All client-side sweep/watch logic | Not yet decided (Phase 23 not yet built at research time, per Phase 27's own note) | — | Keep the sweep's read-only module and condition functions runtime-agnostic (pure functions over already-fetched data) so they port cleanly whichever runtime Phase 23 lands on |

**Missing dependencies with no fallback:** the background-task-then-notify primitive for a
*genuinely* unprompted in-session watch has no fallback for that specific claim — but the phase
does not actually need it, because D-07's bounded report satisfies NOTICE-01/02 on its own.

**Missing dependencies with fallback:** Claude Desktop Scheduled tasks, if ever unavailable on the
production machine, falls back to the Managed Agents `deployments` API (heavier, requires webhook
infrastructure) — this is D-04's own named contingency, not a new one invented here.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (backend/Python side, mirroring Phase 27's approach) — `.venv/bin/python -m pytest`; the plugin-side test framework is still undecided pending Phase 23, same caveat Phase 27 recorded |
| Config file | none dedicated; repo-root `pytest.ini` present |
| Quick run command | `.venv/bin/python -m pytest tests/test_sweep_conditions.py tests/test_sweep_read_only.py -q` |
| Full suite command | `.venv/bin/python -m pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| NOTICE-01 | Watch reports settled outcome via Phase 26's renderer when a run finishes within the bound | unit (mocked executions API) | `pytest tests/test_watch_settle_reporting.py -x` | ❌ Wave 0 |
| NOTICE-02 | Watch reports "still running" + run handle when the bound elapses; never silent | unit | `pytest tests/test_watch_bound_fallback.py -x` | ❌ Wave 0 |
| NOTICE-03 | Each of the 5 conditions fires correctly on mocked data; conditions not detectable today (Pitfall 1) are explicitly tested to confirm they degrade gracefully, not silently | unit | `pytest tests/test_sweep_conditions.py -x` | ❌ Wave 0 |
| NOTICE-04 | Silent when all conditions are healthy; every fired notice carries operator-vs-admin attribution (reuses Phase 27's D-04/D-05 table+guardrail test pattern) | unit | `pytest tests/test_sweep_attribution.py -x` | ❌ Wave 0 |
| NOTICE-05 | Sweep's import graph contains zero references to any mutation/dispatch function | unit (AST-based) | `pytest tests/test_sweep_read_only.py -x` | ❌ Wave 0 |
| NOTICE-01 (host) | A Scheduled routine can invoke the plugin's status skill and get real data | manual-only — no pytest harness can drive the Claude Desktop platform's Scheduled-task feature | n/a — justified: platform-level capability, same treatment as Phase 27's STATUS-05 Artifact-publish test | — |
| NOTICE-03 (delivery) | Notification actually surfaces to the operator, in the observed location/format | manual-only | n/a — platform mechanism, not repo-testable | — |

### Sampling Rate
- **Per task commit:** the quick run command above.
- **Per wave merge:** full suite command.
- **Phase gate:** full suite green, plus the two manual-only platform checks (schedule → plugin
  invocation, notification delivery) run at least once before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_sweep_conditions.py` — all 5 NOTICE-03 conditions over mocked
  executions/HubSpot/credit-probe data, including the None-vs-exhausted distinction (Pitfall 5).
- [ ] `tests/test_sweep_read_only.py` — AST/import-graph assertion (Pattern 1).
- [ ] `tests/test_watch_settle_reporting.py` / `tests/test_watch_bound_fallback.py` — the two
  NOTICE-01/02 code paths.
- [ ] `tests/test_sweep_attribution.py` — mirrors Phase 27's D-04/D-05 guardrail test, extended to
  the sweep's notice text.
- [ ] The shared duration-measurement task (D-06 / 25-CONTEXT D-11a) itself is not a unit test —
  it's a one-time data-collection script run against real recent executions; its *output* (the
  chosen default bound) is what a test then asserts against.
- [ ] Plugin-side test framework itself does not exist yet (Phase 23 not built) — same standing
  gap Phase 27 recorded.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | yes | No new credential — reuses Phase 27's n8n API key and status-endpoint header secret |
| V3 Session Management | yes | The in-session watch's state is conversation-scoped, consistent with this milestone's existing pattern (CONTROL-04); the Scheduled routine, by contrast, runs with no session at all, which is exactly why it needs its own read-only enforcement rather than relying on conversation-scoped arming state |
| V4 Access Control | yes | NOTICE-05's entire point — enforced structurally via the dedicated read-only module + import-graph test (Pattern 1), not by policy |
| V5 Input Validation | n/a | No operator-supplied input reaches the sweep; it only reads fixed endpoints on a timer |
| V6 Cryptography | n/a | No new secret material introduced |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| A future shared-utility refactor accidentally makes a mutation function reachable from the sweep's import graph | Tampering (self-inflicted, not adversarial) | The AST/import-graph test (Pattern 1) fails CI the moment this happens, rather than relying on code review catching it |
| A scheduled routine with no session open silently accumulates stale credentials/config that an interactive session would have refreshed | Repudiation / silent failure | The sweep's own failed-scheduled-run condition should watch its own executions too, not just the enrichment/maintenance workflows — treat the sweep's own health as in scope for what "silent" means |
| A notification that tells the operator they can fix an admin-only cause (credential/quota) | Operator harm (same category Phase 27's D-05 guardrail addresses) | Reuse Phase 27's exact attribution guardrail — unrecognized cause defaults to admin, never guessed as operator-fixable |

## Sources

### Primary (HIGH confidence)
- `scripts/enrichment_cost_ledger.py` — read directly; confirms `_list_executions()` already
  fetches `startedAt`/`stoppedAt` but never computes a duration.
- `n8n/wf_scheduled_maintenance_cloud.json` — read directly via `python3 -c "json.load(...)"`
  inspection this session; confirmed `onError: continueRegularOutput` on every HubSpot-Search-
  reading node (`SJ-1/2/3 Search`, `Dedupe Search`, `Review Search`), and `onError: None` (default,
  fails execution) on the plain write nodes.
- `~/Library/Application Support/Claude/claude_desktop_config.json` — read directly this session;
  `coworkScheduledTasksEnabled: true`, `ccdScheduledTasksEnabled: true`.
- `~/Documents/Claude/Scheduled/weekday-morning-brief/SKILL.md` — read directly this session; a
  live, working scheduled routine on this machine.
- `.planning/workstreams/plugin-entrypoint/phases/27-backend-status-surface/27-RESEARCH.md` — the
  entire read surface and its known gaps, reused verbatim throughout this document.
- `.planning/workstreams/plugin-entrypoint/phases/26-outcome-reporting-safe-retry/26-CONTEXT.md` —
  the run handle and outcome renderer D-07 reuses.
- `.planning/workstreams/plugin-entrypoint/phases/25-enrichment-lane-cost-guard/25-CONTEXT.md` —
  D-11a, the shared measurement-task origin.
- This research session's own directly-observed behavior — two `Bash(run_in_background: true)`
  calls each produced an unprompted `<task-notification>` injected into this same conversation.

### Secondary (MEDIUM confidence)
- `claude-api` skill, `shared/managed-agents-scheduled-deployments.md` and
  `shared/managed-agents-api-reference.md` [CITED — bundled reference documentation; cron/DST/
  jitter/webhook semantics are as documented there, not independently hit against a live API key
  this session].
- `claude-api` skill, `shared/managed-agents-overview.md` and `shared/managed-agents-events.md`
  [CITED — webhook delivery model for Managed Agents].
- Local directory evidence (`claude-code/`, `claude-code-vm/`, `local-agent-mode-sessions/` under
  Claude Desktop's Application Support folder) suggesting an embedded agentic/background mode —
  suggestive, not confirmed by an actual fired test.

### Tertiary (LOW confidence)
- `strings` scan of the bundled `app.asar` for the `cronstrue` package reference — confirms cron
  representation is likely used internally, but this is binary-archaeology evidence, not a
  documented API contract.
- Inference that a Scheduled routine's markdown body can invoke a sibling plugin's skill the same
  way an interactive session's system prompt can — architecturally plausible, not observed.

## Metadata

**Confidence breakdown:**
- Sweep read-side logic (conditions, reuse of Phase 27): HIGH — direct code inspection this
  session, plus Phase 27's own already-verified findings.
- Scheduled-routine host availability (D-04): MEDIUM — concretely verified as *enabled* on this
  machine, but the specific composition (invoking this plugin's skill from within it) is unverified.
- In-session unprompted watch (NOTICE-01's strongest claim): LOW-MEDIUM — a working example of the
  exact mechanism exists in this research session's own runtime, but not confirmed in Claude
  Desktop, the phase's actual target. The bounded fallback (D-07) that does not depend on this is
  HIGH confidence.
- Read-only enforcement mechanism: HIGH — the AST/import-graph technique is standard and the
  pattern it mirrors (`enrichment_cost_ledger.py`'s own no-write guarantee) already exists in this
  repo.

**Research date:** 2026-07-30
**Valid until:** 30 days for the n8n-side mechanics (stable, same as Phase 27's estimate); re-verify
the Claude Desktop Scheduled-tasks capability sooner (7-14 days) since it is a client feature flag
on one machine, not a documented, versioned API contract — and re-run the plan's first
verification task (can a Scheduled routine invoke this plugin's skill) before committing further
implementation to this host.
