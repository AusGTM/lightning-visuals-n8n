# Phase 28: Control Actions - Research

**Researched:** 2026-07-30
**Domain:** n8n Public API workflow mutation (`PUT /workflows/{id}`, `/activate`, `/deactivate`),
active-workflow reload semantics, Schedule Trigger cadence schema, manual-execution API gap
**Confidence:** MEDIUM-HIGH for the mechanics of the mutation calls themselves (verified against
this repo's own live-tested deploy code); MEDIUM-LOW for two load-bearing behavioral claims (the
active-workflow reload/caching gap, and whether n8n's Public API can manually execute a
non-webhook workflow at all) — both are answered from community/GitHub evidence, not from a live
probe against this repo's actual n8n Cloud instance, and the planner should budget a cheap live
verification for each before locking the arm/disarm task design.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Live-write arming — resolving the conversation-scope contradiction**
- **D-01:** CONTROL-04 requires live-write permission to be conversation-scoped, but n8n's
  write-safety flag is persistent backend state that outlives any conversation. Resolution: the
  plugin arms immediately before dispatch, dispatches, then disarms, with read-back verification
  in both directions.
- **D-02:** This scopes the permission tighter than the conversation — to the span of a single
  operation. "Never inherited by a later session" therefore holds by construction rather than by
  promise, which is strictly stronger than CONTROL-04 asks for.
  — Reversibility: costly — the alternative (arm-for-the-session with a TTL sweep) makes the lapse
  depend on Phase 29's sweep actually running, and unwinding to it later means rebuilding the
  arming lifecycle and its verification points.
- **D-03:** Known failure mode, must be handled explicitly: a crash or interruption between
  dispatch and disarm leaves the backend armed. Mitigations required in the plan: (a) Phase 27's
  status readout reports the true flag state read from n8n, so a stuck-armed backend is visible;
  (b) Phase 29's sweep is the backstop that catches it unattended. The plugin must not pretend
  disarm always succeeds — a failed disarm is reported loudly, not swallowed.
- **D-04:** Every status readout states plainly whether live writes are currently on, read from
  the backend (Phase 27 D-03), never asserted from local config.

**Starting a run**
- **D-05:** Runs are started by the mechanism each already has: an ingestion lane is started by
  its existing webhook POST — the same dispatch path with its preview, cost guard, and arming
  gate intact. A scheduled scan has no payload and no webhook, so it is started through the n8n
  API.
- **D-06:** Rationale worth preserving: starting an ingestion lane via the n8n API would bypass
  the preview, cost guard, and arming gate that Phases 23 and 25 built. The guards live on the
  dispatch path, so the dispatch path is the only way in for a lane.
- **D-07:** No new manual-trigger webhooks are added to workflows. Each would be another entry
  point to secure for no gain.

**Cadence**
- **D-08:** Cadence accepts free-form natural language, parsed to a schedule — but the parse is
  interpreted back to the operator in plain language for confirmation before any conversion to
  cron. The operator confirms "so: every weekday at 9am and 5pm" before anything is written.
- **D-09:** The confirmation step is what makes free-form safe. A misparse silently changing how
  often the backend burns provider credits is the failure this guards against, and the operator
  sees the interpretation, not the cron string. Cron syntax never appears to the operator in
  either direction (CONTROL-03).
- **D-10:** A parse the plugin cannot confidently interpret is refused with examples, not guessed
  at.

**Reversibility statement**
- **D-11:** Before mutating, the plugin captures the prior state and quotes it back when the
  change lands: "it was hourly; to undo, I'll set it back to hourly." Exact even when the prior
  value was unusual.
- **D-12:** This costs nothing extra — the pre-read is already required for CONTROL-06's
  read-back verification, so the prior value is in hand either way.

**Confirmation and verification (from requirements, restated as binding)**
- **D-13:** Every mutation states its consequence in plain language before it happens, shows what
  will change, and waits for explicit confirmation (CONTROL-05).
- **D-14:** After every mutation the plugin re-reads the backend and reports verified or failed.
  A `200` from n8n is never reported as success on its own (CONTROL-06).
- **D-15:** Any requested change outside the allowlist is refused, not attempted (CONTROL-05).

### Claude's Discretion
- Wording of consequence statements per action type.
- Confirmation phrasing and how the diff of "what will change" is displayed.
- How the natural-language cadence parse is performed and how its interpretation is rendered.
- Retry posture when a read-back verification is inconclusive.
- Whether arm/disarm and the dispatch are presented to the operator as one action or three.

### Deferred Ideas (OUT OF SCOPE)
- Unattended detection of a stuck-armed backend — Phase 29 / NOTICE-03.
- Arbitrary workflow deployment or node editing from the plugin — permanent exclusion, not
  deferred.
- Review-queue writeback gating — Phase 30 / REVIEW-03.
- Widening the mutation allowlist — out of scope; any addition is a new requirement.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CONTROL-01 | Start a run now (ingestion lane or off-cycle scheduled scan) | §"Starting a run" — ingestion lane path fully answered (reuse Phase 23/25 dispatch verbatim); scheduled-scan-off-cycle path hits a **real Public API gap** — see Open Questions #1 |
| CONTROL-02 | Turn a workflow on or off | §"Activate/deactivate" — fully answered, no JSON body, response includes `active` |
| CONTROL-03 | Enable/disable a schedule and change cadence in plain terms, never cron | §"Schedule Trigger cadence schema" — fully answered, exact node/parameter shapes from this repo's own deployed workflow |
| CONTROL-04 | Live writes armed for the current conversation only | §"The arm/disarm mechanism" — fully answered mechanically; **the reload-timing question underneath it is the phase's central open risk** (Open Questions #2) |
| CONTROL-05 | Consequence-first confirmation; allowlist-only mutation, refuse the rest | §"Enforcing the allowlist structurally" — a concrete diff-based mechanism recommended |
| CONTROL-06 | Re-read and report verified/failed, `200` alone is never success | §"Verified-written vs. verified-effective" — this is where the research found the sharpest gap: a GET re-read proves *persisted*, not *live-effective* |
| CONTROL-07 | Every mutation reversible in one step, stated at the moment it lands | §"Reversibility bookkeeping" — mechanically trivial (capture-before-write), already required by D-11/D-12 |

</phase_requirements>

## Summary

This phase's HTTP mechanics are simple and already proven live in this repo:
`scripts/deploy_n8n_workflows.py::_update_workflow_live()` already performs the exact `PUT
/api/v1/workflows/{id}` this phase needs, filtered to the only four fields n8n's schema accepts
(`name`, `nodes`, `connections`, `settings` — confirmed independently by n8n's own JSON-schema
error, `"request/body must NOT have additional properties"`, which several community reports hit
by naively round-tripping a raw GET response). There is no partial-patch verb — `PUT` replaces
`nodes`/`connections`/`settings` wholesale with whatever the body contains, so the only safe
pattern is GET → deep-copy → mutate the allowlisted node(s) in place → PUT the *entire* unchanged
structure back with that one surgical diff. n8n exposes no optimistic-concurrency field
(`versionId`, `ETag`, or similar) on this endpoint in any of the sources checked, so a concurrent
admin edit racing the plugin's write has no server-side protection at all — the mitigation has to
be procedural (minimize the window, verify immediately after, never leave the mutation
in-flight for longer than necessary).

**The one finding that changes the shape of the whole phase** is that n8n's active-workflow
runtime does not reliably reload a workflow's content the instant a `PUT` returns `200`.
Multiple independent community/GitHub reports — one closed by n8n maintainers as
"working as expected" — describe an *already-active* workflow continuing to execute its
previous Code-node logic or previous schedule after a save/API update, until the workflow is
deactivated and reactivated (activation is documented elsewhere in n8n's own trigger-node
family — the "Activation Trigger" node fires exactly on this event — as the point at which a
workflow's definition is (re)loaded into the in-memory active-workflow manager). This means
CONTROL-06's literal instruction ("re-read the backend and report verified") is **necessary but
provably insufficient** for the write-safety flag and the Schedule Trigger cadence: a `GET
/workflows/{id}` immediately after a `PUT` will show the new value because GET reads from the
database, not from the live in-memory instance — so a naive "PUT, then GET to confirm" sequence
will report "verified" even in the scenario where the *running* workflow has not actually picked
up the change yet. The research could not find one report that pins down decisively whether a
simple deactivate→reactivate cycle is *reliably* sufficient to force the reload (one reporter's
workaround was to duplicate the workflow entirely, which is far outside this phase's allowlist);
this is flagged plainly as a MEDIUM-LOW confidence, unverified-live claim (see Open Questions #2)
rather than asserted as a solved problem.

A second, separate gap: n8n's Public API has **no endpoint to manually execute an arbitrary
workflow by ID today**. A `POST /workflows/{id}/execute` endpoint has been proposed and
implemented in an open, unmerged pull request (n8n-io/n8n #20304, internal tracker `GHC-4791`,
requiring a new `workflow:execute` API-key scope) — but it has not landed on `master`, has no
target release, and there is no evidence it is available on n8n Cloud today. D-05's second half
("a scheduled scan... is started through the n8n API") currently has **no real endpoint to call**.
This is reported plainly per the research brief's instruction rather than papered over — see Open
Questions #1 for the two realistic alternatives.

**Primary recommendation:** (1) Build every mutation as GET-full-workflow → deep-copy → mutate
only the allowlisted node(s) → **structural diff-check that every other byte is unchanged** →
PUT the full body back — this is the only mechanism that makes an out-of-allowlist change
*structurally impossible* per D-15, not merely unattempted. (2) Treat "verified" (CONTROL-06) as
two separate claims the plan must satisfy separately: *persisted* (GET shows the new value — easy,
mechanical) and *effective* (the running instance is honoring it — requires an explicit
deactivate→activate bracket around the mutation, budgeted as a live-tested assumption, not a given).
(3) Surface the manual-execution gap to the user/planner explicitly rather than silently building
around it — recommend re-purposing the already-allowlisted Schedule Trigger cadence mutation as
the practical "start it now" mechanism (temporarily set a near-future one-shot-equivalent interval,
let it fire, restore the prior cadence) since no independent execute-by-id path exists.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Ingestion lane start (record a run "now") | Client → existing webhook (API/Backend receives) | — | D-05/D-06: reuses Phase 23/25's dispatch path verbatim; no new mutation surface |
| Scheduled-scan off-cycle start | Client → n8n Public API | — | No webhook exists for it (D-07); **the intended API surface does not exist yet** — see Open Questions #1 |
| Write-safety flag arm/disarm | Client → n8n Public API (`PUT`, `/activate`, `/deactivate`) | — | Same flag Phase 27 reads; this phase writes it, bracketed by reload-forcing lifecycle calls |
| Schedule Trigger cadence mutation | Client → n8n Public API (`PUT`) | — | Structured `rule.interval` object, never cron text, per D-09 |
| Workflow active/inactive toggle | Client → n8n Public API (`/activate`, `/deactivate`) | — | Lowest-risk mutation; no JSON body |
| Allowlist enforcement (refuse non-allowlisted changes) | Client (structural diff before PUT) | — | D-15: must be structurally impossible, not merely unattempted |
| Consequence statement + confirmation UI | Client / conversation | — | D-13, plain-language, before any network call |

## Standard Stack

No new library or package. This phase extends the same HTTP surface Phase 27 already reads and
that `scripts/deploy_n8n_workflows.py` already writes to, live, in this repo.

| Surface | Method | Auth | Already exercised by |
|---|---|---|---|
| `GET /api/v1/workflows/{id}` (single) or `/api/v1/workflows` (list, then filter) | n8n Public API | `X-N8N-API-KEY` | `scripts/deploy_n8n_workflows.py::_get_live_workflows()` (list form; single-id GET is standard REST, same auth, not separately exercised in this repo but implied by the PUT endpoint's own id-scoped path) |
| `PUT /api/v1/workflows/{id}` | n8n Public API | `X-N8N-API-KEY` | `scripts/deploy_n8n_workflows.py::_update_workflow_live()` — **exact** field filter (`name`, `nodes`, `connections`, `settings`) this phase must reuse |
| `POST /api/v1/workflows/{id}/activate`, `/deactivate` | n8n Public API | `X-N8N-API-KEY` | Not yet called by any script in this repo (deploy script's own comment: "Activation... is a separate operator-runbook step, not performed here") — new to this phase, but a well-documented, no-body endpoint |
| `POST /api/v1/workflows/{id}/execute` | n8n Public API | `X-N8N-API-KEY` + `workflow:execute` scope | **Does not exist on `master` as of this research session** — open PR #20304, unmerged, no target version [CITED, see Open Questions #1] |

**Installation:** none. Same HTTP client the plugin's chosen runtime already uses (Phase 23 not
yet built at time of writing — see Environment Availability, carried forward from Phase 27's
research unchanged).

## Package Legitimacy Audit

Not applicable — this phase installs no external package.

## Architecture Patterns

### System Architecture Diagram

```
Operator: "turn on live writes and run the enrichment scan on these 12 companies"
        │
        ▼
Client (plugin) — states consequence, shows diff, waits for explicit confirmation (D-13)
        │
        ├─(1)─► GET /api/v1/workflows/{id}         [pre-read: capture prior flag value (D-11/D-12)]
        │
        ├─(2)─► POST /api/v1/workflows/{id}/deactivate   [force-reload bracket, open question — see below]
        │
        ├─(3)─► PUT  /api/v1/workflows/{id}         [ALLOWLISTED mutation only: flip
        │             ALLOW_HUBSPOT_RECORD_WRITES literal inside "Decide Action" /
        │             "Decide Company Action" jsCode, nothing else changed — diff-checked (D-15)]
        │
        ├─(4)─► POST /api/v1/workflows/{id}/activate      [forces the active-workflow manager
        │                                                    to (re)load current DB content]
        │
        ├─(5)─► GET /api/v1/workflows/{id}          [read-back: confirm literal now reads "true"
        │             AND active:true — this proves PERSISTED, not necessarily EFFECTIVE]
        │
        ├─(6)─► POST hubspot/enrichment/event        [the existing Phase 25 dispatch path,
        │             preview/cost-guard/arming gate intact, D-05/D-06]
        │
        ├─(7)─► POST /api/v1/workflows/{id}/deactivate    [disarm bracket, same reload concern]
        ├─(8)─► PUT  /api/v1/workflows/{id}          [flip literal back to "false", diff-checked]
        ├─(9)─► POST /api/v1/workflows/{id}/activate
        └─(10)► GET /api/v1/workflows/{id}           [read-back: confirm disarmed — CONTROL-06]
        │
        ▼
Client reports: "verified: live writes were on for this dispatch and are now off again" or,
   on any GET mismatch / non-200 at any step, "disarm FAILED — backend may still be armed,
   an admin should check" (D-03 — never swallowed)

Cadence mutation (CONTROL-03) — same GET → deactivate → PUT → activate → GET bracket, but the
PUT touches the named Schedule Trigger node's `parameters.rule.interval` array instead of a
Code node's jsCode literal. Operator confirms the PARSED INTERPRETATION ("every weekday at
9am and 5pm"), never the resulting interval/cron structure (D-09).

Activate/deactivate toggle (CONTROL-02) — no PUT at all, just steps analogous to (2)/(4) or
(7)/(9) alone, since there is no content to reload — the toggle itself IS the state.
```

### Pattern 1: The exact PUT body filter (already live-tested in this repo)

**What:** n8n's `PUT /workflows/{id}` schema rejects any key outside `{name, nodes, connections,
settings}` with `"request/body must NOT have additional properties"` — confirmed independently
by this repo's own `_update_workflow_live()` (which already filters to exactly these four keys)
and by a public GitHub issue reproducing the identical error when a raw GET response (which also
carries `id`, `active`, `tags`, `createdAt`, `updatedAt`, `staticData`, etc.) is PUT back
unmodified.

**When to use:** Every mutation in this phase. Never attempt to include `active` in a PUT body —
it is rejected outright; activation state is exclusively the `/activate`/`/deactivate` endpoints'
job.

**Example:**
```python
# Source: scripts/deploy_n8n_workflows.py::_update_workflow_live — reuse this filter verbatim,
# do not re-derive it.
def _put_body(full_workflow: dict) -> dict:
    return {k: v for k, v in full_workflow.items()
            if k in ("name", "nodes", "connections", "settings")}
```
[VERIFIED: `scripts/deploy_n8n_workflows.py` — `_update_workflow_live()`, read directly, this
exact filter is already what ships live in this repo's deploy path]
[CITED: github.com/n8n-io/n8n/issues/25778 — reproduces the identical "must NOT have additional
properties" rejection when extra top-level fields are included]

### Pattern 2: Structural allowlist enforcement via full-diff, not "we only touched what we meant to"

**What:** Because `PUT` replaces `nodes`/`connections`/`settings` wholesale, the only way to make
an out-of-allowlist change **structurally impossible** (D-15's actual wording) rather than merely
"we didn't intend to change it" is to diff the outgoing body against the freshly-fetched one,
node-by-node, and refuse to PUT if anything differs outside the exact allowlisted path.

**When to use:** Every mutation, before the PUT fires.

**Example:**
```python
import json

ALLOWLISTED_NODE_NAMES = {"Decide Action", "Decide Company Action"}  # write-safety flag
# ...plus whichever single Schedule Trigger node name is the mutation's target for cadence calls.

def assert_only_allowlisted_change(original: dict, modified: dict, allowed_names: set) -> None:
    """Refuses (raises) if ANY node outside allowed_names differs, or if connections/settings
    differ at all. Mirrors enable_baked_flags()'s fail-closed re-scan discipline (Phase 27/28's
    shared repo convention), applied here as a whole-workflow guard rather than a single-literal
    one."""
    orig_by_name = {n["name"]: n for n in original.get("nodes", [])}
    mod_by_name = {n["name"]: n for n in modified.get("nodes", [])}
    if set(orig_by_name) != set(mod_by_name):
        raise ValueError("refusing PUT: node set itself changed (added/removed a node)")
    for name, orig_node in orig_by_name.items():
        if name in allowed_names:
            continue
        if json.dumps(orig_node, sort_keys=True) != json.dumps(mod_by_name[name], sort_keys=True):
            raise ValueError(f"refusing PUT: node {name!r} changed outside the allowlist")
    if original.get("connections") != modified.get("connections"):
        raise ValueError("refusing PUT: connections graph changed — never allowlisted")
    if original.get("settings") != modified.get("settings"):
        raise ValueError("refusing PUT: settings changed — never allowlisted")
```
This is the concrete mechanism Priority Question #5 asked for: a change outside the allowlist
cannot reach the network call at all, not merely "wasn't planned."

### Pattern 3: Reading the Schedule Trigger cadence (structured, never cron, per D-09)

**What:** This repo's own deployed `n8n/wf_scheduled_maintenance_cloud.json` already contains
five `n8n-nodes-base.scheduleTrigger` (typeVersion 1.2) nodes, each expressed as a structured
interval object — never a cron string:
```json
{"rule": {"interval": [{"field": "hours", "hoursInterval": 1}]}}
{"rule": {"interval": [{"field": "minutes", "minutesInterval": 15}]}}
{"rule": {"interval": [{"field": "months", "monthsInterval": 1}]}}
{"rule": {"interval": [{"field": "weeks", "weeksInterval": 1}]}}
```
[VERIFIED: `n8n/wf_scheduled_maintenance_cloud.json` — `SJ-1 Trigger (hourly)`, `SJ-3 Trigger (15
min)`, `SJ-2 Trigger (monthly)`, `Dedupe Trigger (weekly)`, `Review Trigger (15 min)`, read
directly]

The node's full parameter schema [CITED: docs.n8n.io/integrations/builtin/core-nodes/
n8n-nodes-base.scheduletrigger/] supports these `field` values, each with its own companion keys:

| `field` | Companion parameters |
|---|---|
| `seconds` | `secondsInterval` |
| `minutes` | `minutesInterval` |
| `hours` | `hoursInterval`, `triggerAtMinute` |
| `days` | `daysInterval`, `triggerAtHour`, `triggerAtMinute` |
| `weeks` | `weeksInterval`, `triggerOnWeekdays` (array), `triggerAtHour`, `triggerAtMinute` |
| `months` | `monthsInterval`, `triggerAtDayOfMonth`, `triggerAtHour`, `triggerAtMinute` |
| `cronExpression` | `expression` (standard 5- or 6-field Unix cron, seconds field optional) |

`rule.interval` is an **array** — multiple entries fire independently. "Every weekday at 9am and
5pm" (D-08's own example) is naturally two `weeks`-type entries (`triggerOnWeekdays: [1,2,3,4,5]`,
one with `triggerAtHour: 9`, one with `triggerAtHour: 17`), **not** a single cron string — this
maps cleanly onto the native schema without ever constructing a `cronExpression`. Reserve
`cronExpression` only for patterns the native fields genuinely cannot express (e.g., "the third
Tuesday of the month") — and per D-10, a parse that would require falling back to raw cron is
exactly the kind of low-confidence interpretation that should be refused with examples rather
than silently emitted as an opaque cron string the operator never sees explained.

**Example — minimal cadence PUT, diff-scoped to one node:**
```python
def set_cadence(node: dict, new_interval: list[dict]) -> None:
    """Mutates ONE Schedule Trigger node's rule.interval in place. Caller must still run
    assert_only_allowlisted_change() against the full workflow before PUT."""
    node["parameters"]["rule"]["interval"] = new_interval
```

### Pattern 4: Activate/deactivate — no JSON body, response echoes the workflow

**What:** `POST /api/v1/workflows/{id}/activate` and `.../deactivate` take no request body and
return the (now-updated) workflow object, including its `active` field.
[CITED: community/docs consensus — see Sources; not independently reproduced live in this repo,
since the deploy script deliberately never calls these endpoints ("Activation... is a separate
operator-runbook step, not performed here")]

**When to use:** CONTROL-02's toggle directly; also as the forced-reload bracket around every
`PUT` this phase makes (Pattern 5).

**Recommendation:** Do not trust the activate/deactivate response body alone as CONTROL-06's
"re-read" — it is the mutation's own echo, not an independent read. Follow it with a **separate**
`GET /workflows/{id}` call, per D-14's literal wording ("re-reads the backend").

### Pattern 5: Verified-*persisted* vs. verified-*effective* — the phase's central risk (Priority Q2)

**What was found:** Multiple independent reports (GitHub issues, n8n community threads) describe
an **already-active** workflow continuing to run its *previous* logic or *previous* schedule
after a content update lands via save/API, until the workflow goes through a
deactivate→reactivate cycle. One such issue was closed by n8n maintainers with the label
`closed:working-as-expected` — i.e., not acknowledged as a bug to be fixed, which means this is
not a transient defect likely to disappear in a future n8n release. n8n's own trigger-node family
independently confirms that *activation* is a meaningful reload event: the "Activation Trigger"
node's entire purpose is firing "when the workflow containing this node updates or gets
published" or on activation — i.e., n8n's own documented model treats activation as the load
point, which is consistent with (but does not, on its own, prove) "a bare PUT to an
already-active workflow does not retroactively reload the running instance."

**Why this matters for D-14/CONTROL-06 specifically:** A `GET /workflows/{id}` immediately after
a `PUT` reads from the persisted store and will **always** show the new value — that part of the
database write is not in question. What is genuinely unverified is whether the **currently
running active-workflow instance** — the one that will actually process the next webhook call or
schedule fire — is honoring that new value without an explicit deactivate→activate bracket. A
"re-read and confirm" step that only does `GET` cannot distinguish these two states; it will
report "verified" in both the good case and the stuck-on-stale-cache case.

**Confidence and what's still unverified:** MEDIUM-LOW. All evidence is community/GitHub-sourced,
not obtained from a live probe against this repo's actual n8n Cloud account, and one report's
resolution ("I had to duplicate the workflow") suggests deactivate→reactivate may not be
universally sufficient in every reported case — though that report gives no detail on whether the
reporter actually tried a bare deactivate→reactivate cycle before escalating to duplication, so it
cannot be read as proof that reactivation fails; it can only be read as "not proven to always
work."

**Recommendation for the plan:** (1) Always bracket every content-changing `PUT` in this phase
with `deactivate` → `PUT` → `activate`, never a bare `PUT` to an active workflow. (2) Budget one
explicit, early, live verification task: flip the write-safety flag with the bracket, dispatch a
real (test-record) enrichment event immediately after, and inspect the actual written
source-metadata to confirm the NEW flag value was honored — this is the only way to close the
MEDIUM-LOW confidence gap into a real HIGH-confidence fact for this specific n8n Cloud account and
version. (3) Treat "GET shows the new value" (persisted) and "a live-fired test observably behaved
according to the new value" (effective) as two separate claims in the plan's own test map — do not
let one satisfy CONTROL-06 for the other.

### Anti-Patterns to Avoid

- **Constructing the PUT body from scratch instead of GET → mutate → PUT.** The community thread
  on this exact endpoint shows that hand-building `settings` (rather than passing through
  whatever GET returned, unmodified except for the intended field) produces its own class of
  schema-validation failures, because the nested shape has undocumented constraints. Always
  start from a fresh GET; never author `settings`/`connections` by hand.
- **Trusting a `200` from `PUT`/`activate` as "verified."** D-14 already forbids this explicitly;
  Pattern 5 above shows it is forbidden for a second, deeper reason than the obvious one (a `200`
  can be entirely honest about persistence and still not reflect a live-effective change).
- **Assuming `POST /workflows/{id}/execute` exists.** It is an open, unmerged PR as of this
  research session — do not design CONTROL-01's off-cycle scan around an endpoint that is not
  live on n8n's Public API. See Open Questions #1.
- **Using `cronExpression` as the default cadence representation.** It works, but D-09 requires
  cron to never appear to the operator; defaulting to the native `interval`/`weeks`/`triggerAt*`
  fields keeps the *stored* representation legible without cron even incidentally, and reserves
  `cronExpression` for the rare pattern that genuinely needs it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| PUT body field filtering | A new "which keys does n8n accept" guess | `scripts/deploy_n8n_workflows.py::_update_workflow_live()`'s exact `{name, nodes, connections, settings}` filter | Already live-tested against this real instance; re-deriving risks missing a field n8n silently rejects |
| Write-safety flag literal rewrite | A bespoke regex | `enable_baked_flags()`'s exact literal-match-then-fail-closed-rescan pattern (same repo, same flag) | Phase 27 already reads with this exact regex; Phase 28 must write the identical literal shape or the two desync |
| Allowlist enforcement | Trusting "we only touched two fields" by convention | The structural full-diff in Pattern 2 | D-15 requires structurally impossible, not merely-not-attempted; a diff is the only mechanism that is actually structural |
| Natural-language cadence parsing | A hand-rolled NL date/time parser | Claude's own reasoning over the operator's phrase, confirmed back in plain language before conversion (D-08/D-09) — this is explicitly Claude's discretion, not a library decision | The confirmation step, not the parser's cleverness, is what CONTEXT identifies as the actual safety mechanism (D-09) |

**Key insight:** almost everything mechanical in this phase is already proven code elsewhere in
this repo (the PUT filter, the flag-literal regex, the fail-closed re-scan idiom) — the genuinely
new work is the allowlist-diff wrapper and the deactivate/activate reload bracket, neither of
which exists anywhere in this repo yet because nothing before this phase has ever needed to
*mutate* a live workflow surgically.

## Common Pitfalls

### Pitfall 1: A `GET`-after-`PUT` "verification" that cannot actually detect the stale-cache case
**What goes wrong:** The plan implements CONTROL-06 as "PUT, then GET, compare" and calls it done.
**Why it happens:** It is the literal, obvious reading of "re-reads the backend and reports
verified or failed," and it is *correct* for detecting a failed write (network error, 4xx, a
value that didn't stick). It is *not* sufficient evidence the running instance is honoring the
new value (Pattern 5).
**How to avoid:** Bracket every content PUT with deactivate→activate (forces a reload event by
n8n's own documented trigger-node model), and budget one live end-to-end verification early
rather than trusting the mechanism by inference.
**Warning signs:** An armed dispatch that writes with the OLD flag value despite every read-back
in the plan showing "armed: true."

### Pitfall 2: Assuming `POST /workflows/{id}/execute` is available
**What goes wrong:** A task is written assuming this endpoint exists on n8n Cloud today.
**Why it happens:** It is a completely reasonable-sounding endpoint name and multiple search
results reference "n8n adds workflow execute endpoint" without prominently flagging that the PR
is unmerged.
**How to avoid:** Confirm live with one cheap call (`POST {base}/api/v1/workflows/{any_id}/execute`
against a real workflow, expect 404/405) before designing around it. Treat the CONTEXT's D-05
"started through the n8n API" language for the scheduled-scan case as needing a concrete
alternative mechanism (see Open Questions #1), not a literal existing call.
**Warning signs:** A 404/405 on the very first live attempt to fire an off-cycle scan.

### Pitfall 3: Constructing a `PUT` body that includes `active`, `id`, `tags`, or `createdAt`/`updatedAt`
**What goes wrong:** n8n's JSON-schema validator rejects the whole request with `"request/body
must NOT have additional properties"` — a 400, not a silent strip.
**Why it happens:** A raw GET response naturally carries all of these fields; forgetting to
filter before PUT is the single most commonly reported mistake against this endpoint in n8n's own
community/issue tracker.
**How to avoid:** Always run the fetched workflow through the exact four-key filter (Pattern 1)
before every PUT, with no exceptions.
**Warning signs:** A 400 with the literal string "must NOT have additional properties."

### Pitfall 4: Interrupting the enrichment webhook's own reachability during its arm bracket
**What goes wrong:** The deactivate→PUT→activate bracket this phase's own recommendation
requires (Pattern 5) necessarily makes the target workflow briefly inactive — if the dispatch
POST (step 6 in the diagram) races the reactivation, it could 404 against a not-yet-re-registered
webhook path (a separately documented n8n behavior: webhook registration can lag activation).
**Why it happens:** Deactivate/activate and webhook-route registration are two different internal
mechanisms with their own (undocumented) timing.
**How to avoid:** Do not fire the dispatch POST immediately on receiving `200` from `activate` —
perform the `GET` read-back first (Pattern 5 already requires this) and treat its successful
response as a lightweight settle-delay; if the dispatch POST still 404s once, retry it once after
a short pause before reporting a hard failure (Claude's discretion per CONTEXT's "retry posture
when read-back is inconclusive").
**Warning signs:** A dispatch POST 404s once immediately after arming, then succeeds on a bare
retry with no other change.

## Code Examples

### Full mutation sequence, write-safety flag (arm half; disarm is the mirror)
```python
# Source: composed from scripts/deploy_n8n_workflows.py's proven primitives
# (_n8n_headers, _base_url, the PUT field filter) plus this phase's two new pieces
# (assert_only_allowlisted_change, the deactivate/activate reload bracket).
import re
import requests

FLAG_RE = re.compile(r'const\s+ALLOW_HUBSPOT_RECORD_WRITES\s*=\s*"(true|false)";')
TARGET_NODES = ("Decide Action", "Decide Company Action")

def arm_write_safety(base_url: str, headers: dict, workflow_id: str) -> dict:
    prior = requests.get(f"{base_url}/api/v1/workflows/{workflow_id}", headers=headers, timeout=30).json()
    modified = json.loads(json.dumps(prior))  # deep copy
    for node in modified["nodes"]:
        if node["name"] in TARGET_NODES:
            js = node["parameters"]["jsCode"]
            node["parameters"]["jsCode"] = FLAG_RE.sub(
                'const ALLOW_HUBSPOT_RECORD_WRITES = "true";', js)

    assert_only_allowlisted_change(prior, modified, set(TARGET_NODES))  # Pattern 2 — refuses closed

    requests.post(f"{base_url}/api/v1/workflows/{workflow_id}/deactivate", headers=headers, timeout=30).raise_for_status()
    put_resp = requests.put(f"{base_url}/api/v1/workflows/{workflow_id}",
                             headers=headers, json=_put_body(modified), timeout=30)
    put_resp.raise_for_status()
    requests.post(f"{base_url}/api/v1/workflows/{workflow_id}/activate", headers=headers, timeout=30).raise_for_status()

    verify = requests.get(f"{base_url}/api/v1/workflows/{workflow_id}", headers=headers, timeout=30).json()
    found = {FLAG_RE.search(n["parameters"].get("jsCode", "") or "").group(1)
             for n in verify["nodes"] if n["name"] in TARGET_NODES
             and FLAG_RE.search(n["parameters"].get("jsCode", "") or "")}
    if found != {"true"} or not verify.get("active"):
        raise RuntimeError("arm FAILED verification — backend may be in an inconsistent state; "
                            "an admin should check n8n directly")
    return {"prior_flag": _extract_prior(prior), "verified_armed": True}
```

### Cadence change — read the current value, state it back, then mutate (D-11/D-08)
```python
def read_current_cadence(workflow: dict, node_name: str) -> list[dict]:
    for node in workflow["nodes"]:
        if node["name"] == node_name:
            return node["parameters"]["rule"]["interval"]
    raise KeyError(f"no Schedule Trigger node named {node_name!r}")

# D-11 requires this captured BEFORE the mutation, so "it was hourly; to undo, I'll set it back
# to hourly" can be stated the moment the change lands — the same GET already required for
# CONTROL-06's read-back supplies this for free (D-12).
```

## State of the Art

| Old/assumed approach | What this research found | When it matters | Impact |
|---|---|---|---|
| "PUT a workflow, trust the 200" | n8n's schema rejects any body with extra top-level keys; the deploy script already filters to four keys | Every mutation in this phase | Confirms the existing repo convention is correct and must be reused, not re-derived |
| "GET-after-PUT proves the change is live" | GET proves persistence only; the running active-workflow instance may not reload without a deactivate/activate cycle (community-reported, not officially documented, one issue closed "working as expected") | CONTROL-06's entire verification design | The single most consequential finding in this phase — changes "verify" from a one-step GET into a two-part persisted+effective claim |
| "n8n has a way to run a workflow by ID via API" | No — `POST /workflows/{id}/execute` is an open, unmerged PR (#20304) as of this research session, not shipped | CONTROL-01's off-cycle scheduled-scan case | D-05's assumption needs a concrete alternative (Open Questions #1), not a literal implementation of "call the execute endpoint" |

**Deprecated/outdated:** none — this is all current-state n8n Public API behavior, not a
migration from an older approach.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | A deactivate→PUT→activate bracket reliably forces the active-workflow manager to reload the new node content before the next execution | Pattern 5 | If wrong (some other mechanism is needed, or the bracket is itself insufficient per the one "had to duplicate the workflow" report), the arm/disarm cycle could dispatch against a stale flag with no read-back able to catch it — this is the single highest-impact assumption in the phase and MUST be live-verified early, not assumed from research alone |
| A2 | `POST /workflows/{id}/execute` is not available on this repo's n8n Cloud instance | Summary / Open Questions #1 | If the endpoint actually is available on this specific Cloud account (feature-flagged ahead of the public PR merge, unlikely but not disprovable from outside), the recommended cadence-based workaround would be unnecessarily complex — a single cheap live probe (expect 404/405) resolves this before planning locks in the workaround |
| A3 | `GET /api/v1/workflows/{id}` (single-workflow-by-id) exists and behaves like the documented list endpoint's per-item shape | Standard Stack | Not independently exercised in this repo (only the list form is); if the single-id GET has any shape divergence from the list-item shape, the node-lookup-by-name logic in every pattern above needs a small adjustment — low risk, standard REST convention, but unverified live here |
| A4 | Activation/deactivation endpoints require no request body and return the updated workflow object including `active` | Pattern 4 | If the response shape differs (e.g., only a bare `{success: true}`), D-14's "re-read" still holds via the follow-up GET this research already recommends performing regardless — low risk since the plan is told not to trust the response body alone anyway |

**If this table is empty:** N/A — populated above; A1 is the load-bearing one and should be the
first thing verified once implementation starts.

## Open Questions

> **Status annotation added 2026-07-31 during Phase 28 plan repair.** These three were unannotated,
> which invited a re-litigation of settled scope. Question 1 is **RESOLVED** — it was answered by a
> decision, not by a probe. Questions 2 and 3 are **resolved by 28-02, pending execution** — the
> plan exists and names the observation; only the human-run checkpoint remains.

1. **[RESOLVED — 28-CONTEXT.md D-05a/D-05b/D-05c]** CONTROL-01's "start a scheduled scan off-cycle"
   has no existing n8n Public API endpoint to call.
   - **Resolution:** the research's recommendation (a) — repurposing the cadence mutation as a
     one-shot fire — was **rejected** by D-05c: it mutates a schedule to simulate a trigger, and a
     crash mid-sequence leaves the backend on the wrong schedule, silently changing how often it
     burns provider credits. Recommendation (b) was taken instead: CONTROL-01 **narrows to the
     ingestion lanes** and off-cycle scheduled scans are dropped, with enable/disable (CONTROL-02)
     and re-timing (CONTROL-03) as the operator's available controls. This is the milestone's fifth
     accepted amendment. 28-05 Task 3 records it in REQUIREMENTS.md and ROADMAP.md; 28-02's
     `execute_probe` confirms the endpoint's absence against this tenant rather than against the
     upstream PR's state. **Do not re-propose the cadence-as-fire workaround; it was considered and
     refused on the record.**
   - The original research text follows, unedited, for provenance.
   - What we know: `POST /workflows/{id}/execute` was proposed in n8n-io/n8n PR #20304 (requires
     a new `workflow:execute` API-key scope, returns `{executionId, waitingForWebhook}`) but
     remains **open and unmerged** as of this research session, with no target release named.
     [CITED: github.com/n8n-io/n8n/pull/20304] No new manual-trigger webhook may be added
     (D-07), and Schedule Trigger workflows have no other documented "run once now" verb.
   - What's unclear: Whether this specific n8n Cloud account happens to have early access to the
     unmerged endpoint (extremely unlikely, but a single live `POST .../execute` call against a
     real workflow id — expect 404 or 405 — resolves this in seconds and should be the very first
     thing the plan's implementation does, before any task assumes either outcome).
   - Recommendation: **Two realistic alternatives, in preference order.** (a) Repurpose the
     already-allowlisted Schedule Trigger cadence mutation (CONTROL-03's own mechanism) as the
     "run it now" primitive for a scheduled scan: read the current cadence (captured anyway per
     D-11), temporarily set a near-future single-fire-equivalent interval (e.g., `seconds` field
     with a short interval, or a `days`/`hours` entry timed to fire within roughly a minute),
     wait for/confirm the fire via the executions API (already read by Phase 27), then restore
     the prior cadence and state the restoration per D-11 — this stays entirely inside the
     existing allowlist and needs no new endpoint. (b) If (a) is judged too indirect or its
     timing too unreliable for "start it now" semantics, degrade CONTROL-01's scheduled-scan case
     to an explicit, honest refusal ("I can't trigger this scan directly today — ask an admin to
     run it from the n8n UI, or I can adjust its schedule to fire again shortly") — consistent
     with PLUGIN-03's "state what still works" pattern rather than building a call to an endpoint
     that doesn't exist. This is a genuine scope decision for the user/planner, not something
     this research should silently resolve.

2. **[RESOLVED BY 28-02, PENDING EXECUTION — `cadence_reload`, Task 3, a `blocking-human`
   checkpoint; the observation lands in 28-FINDINGS.md]** Does a deactivate→PUT→activate bracket
   actually and reliably force the active-workflow
   runtime to honor a changed Code-node literal or Schedule Trigger interval, on THIS n8n Cloud
   account/version — or does the reported caching behavior require something stronger (as one
   community report's "had to duplicate the workflow" workaround hints)?**
   - What we know: Multiple community/GitHub reports describe stale-execution behavior after a
     content update to an active workflow, closed by n8n maintainers as "working as expected"
     with no detailed root-cause explanation given in any source this research could reach.
     n8n's own "Activation Trigger" node documents activation as a genuine reload/publish event,
     which is suggestive but not conclusive proof the bracket is sufficient.
   - What's unclear: Whether the one report that needed a full workflow duplication tried a bare
     deactivate→reactivate cycle first and found it insufficient, or skipped straight to
     duplication without testing the simpler fix — the source available to this research does
     not say.
   - Recommendation: Treat A1 above as the phase's first implementation task, not a research
     conclusion to build on faith: flip the flag with the bracket, immediately dispatch a real
     test-record enrichment event, and inspect the written source-metadata to directly observe
     which flag value was honored. If the bracket proves insufficient live, the plan needs a
     different mechanism entirely (possibly: accept a short, bounded wait-and-recheck loop after
     reactivation before dispatching) — but that redesign should be driven by a real observed
     failure, not preemptively over-built against a risk that may not materialize on this
     account's actual n8n version.

3. **[RESOLVED BY 28-02, PENDING EXECUTION — `roundtrip`, Task 2, a `blocking-human` checkpoint;
   the observation lands in 28-FINDINGS.md]** Does `settings`/`connections` round-trip cleanly (GET
   then PUT, unmodified) on this repo's
   specific n8n Cloud version, or does the nested-shape validation issue one community report
   describes ("settings... requires attention... contains unsupported properties") apply here
   too?**
   - What we know: The one community report describing this explicitly did not enumerate which
     nested settings keys caused the failure, and this repo's own deploy script has never
     round-tripped a *live* GET response back through PUT (it always PUTs the *local template*
     body, with the live `id` substituted in — a different data path that has never exercised a
     genuine GET→PUT round-trip of `settings`).
   - What's unclear: Whether this repo's specific deployed workflows' `settings` objects (mostly
     `{}` per direct inspection of `wf_scheduled_maintenance_cloud.json`) are simple enough to
     avoid the issue entirely, or whether some workflow's settings carry a field that trips it.
   - Recommendation: The very first live PUT this phase's implementation performs should be a
     genuine no-op round-trip test (GET, then PUT the identical filtered body straight back,
     changing nothing) against a low-risk workflow, to confirm the round-trip itself is clean
     before any task relies on it for a real mutation.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| n8n Cloud instance + `X-N8N-API-KEY` with write scope | Every mutation in this phase | Assumed available (admin-provisioned, per Phase 27's same note) — not independently re-verified this session | n8n Cloud, Public API v1 | None — PLUGIN-03 requires a plain refusal naming who can fix a missing/rejected key |
| `POST /workflows/{id}/execute` | CONTROL-01 (scheduled-scan off-cycle) | **Not available** — open, unmerged PR as of this research session | n/a | See Open Questions #1 — cadence-based workaround, or explicit refusal |
| `operator-claude-plugin/` runtime (language/framework) | All client-side work in this phase | Not yet decided — same standing gap noted in Phase 27's research; Phase 23 not yet built at time of writing | — | Keep every pattern above phrased so it ports cleanly to whichever runtime Phase 23 lands on |
| Repo-internal note: agent tooling in this repo is blocked from performing arming writes (per this repo's own operating convention, `.env`/credential gating aside) | Live testing of any arm/disarm sequence during THIS phase's implementation | A human must execute and observe the live-armed test (Open Questions #2/A1) — Claude/agent tooling cannot perform it unilaterally in this repo | — | Plan implementation tasks accordingly: write the code and its tests, but flag the live-fire verification step as needing a human operator to actually run and confirm |

**Missing dependencies with no fallback:** the `/execute` endpoint has no fallback that calls the
same verb — see Open Questions #1 for the two alternative mechanisms.

**Missing dependencies with fallback:** none beyond what's noted above.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing repo convention) — `.venv/bin/python -m pytest`; plugin-side framework still undecided pending Phase 23, same caveat as Phase 27's research |
| Config file | none dedicated; repo-root `pytest.ini` already present |
| Quick run command | `.venv/bin/python -m pytest tests/test_deploy_n8n_workflows.py tests/test_deploy_write_safety_overlay.py -q` (nearest existing sibling tests to extend/mirror) |
| Full suite command | `.venv/bin/python -m pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONTROL-05 | `assert_only_allowlisted_change` refuses any node/connections/settings diff outside the allowlist | unit | `pytest tests/test_control_allowlist_diff.py -x` | ❌ Wave 0 |
| CONTROL-03 | Cadence PUT body touches only the named Schedule Trigger node's `rule.interval`; NL parse → structured interval mapping for representative phrases ("hourly", "every weekday at 9am and 5pm", an ambiguous phrase that must refuse) | unit | `pytest tests/test_control_cadence_parse.py -x` | ❌ Wave 0 |
| CONTROL-04/CONTROL-06 | Flag-literal regex read/write round-trip agrees with Phase 27's read regex exactly (shared literal contract) | unit | `pytest tests/test_control_flag_write_read_parity.py -x` | ❌ Wave 0 |
| CONTROL-06 | "Verified" reporting distinguishes a failed GET/mismatch from a genuine success; never reports success on `200` alone | unit (mocked HTTP) | `pytest tests/test_control_verify_reporting.py -x` | ❌ Wave 0 |
| CONTROL-07 | Prior-state capture happens before mutation and is quoted back verbatim on success | unit | `pytest tests/test_control_reversibility_statement.py -x` | ❌ Wave 0 |
| A1 (arm/disarm effective, not just persisted) | Real armed dispatch against a test record honors the newly-armed flag | **manual-only, live** — justified: this is precisely the class of behavior (n8n's own runtime reload timing) no mock or unit test can substitute for; requires a human to execute per the standing "agent tooling is blocked from arming writes" convention | n/a | — |

### Sampling Rate
- **Per task commit:** the relevant new pytest file(s) above.
- **Per wave merge:** full `pytest` suite.
- **Phase gate:** full suite green, **plus** the one live manual verification (A1) actually
  performed and its result recorded before `/gsd-verify-work` — this phase's gate cannot be
  satisfied by automated tests alone given the load-bearing MEDIUM-LOW-confidence assumption.

### Wave 0 Gaps
- [ ] `tests/test_control_allowlist_diff.py` — the structural diff refusal (Pattern 2), including
  a case that mutates an out-of-allowlist node and asserts a raised refusal.
- [ ] `tests/test_control_cadence_parse.py` — NL phrase → structured `rule.interval` mapping,
  plus at least one deliberately-ambiguous phrase that must refuse with examples (D-10).
- [ ] `tests/test_control_flag_write_read_parity.py` — write-side regex from this phase agrees
  byte-for-byte with Phase 27's read-side regex on the same literal shapes.
- [ ] `tests/test_control_verify_reporting.py` — mocked GET/PUT/activate responses covering
  success, a non-200, and a GET that reads back the OLD value (simulating the stale-cache case)
  — the reporting layer must fail closed on the last case, not report "verified."
- [ ] `tests/test_control_reversibility_statement.py` — D-11/D-12 prior-value capture and
  restatement.
- [ ] A live-fire manual test plan document for A1 (Open Questions #2) — not a pytest file, but a
  named, trackable verification step the phase gate depends on.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | yes | Same `X-N8N-API-KEY` as Phase 27, admin-provisioned, never operator-visible (PLUGIN-02); this phase adds no new credential |
| V3 Session Management | yes | The armed/disarmed state is the plugin's OWN conversation-scoped fact, distinct from n8n's persistent flag (ROADMAP's own explicit distinction) — this phase must never conflate "n8n allows writes" with "I am willing to write right now" |
| V4 Access Control | yes | The entire phase's purpose is a bounded write surface; the allowlist-diff mechanism (Pattern 2) IS the access-control enforcement point |
| V5 Input Validation | yes | Natural-language cadence input must be validated by successful mapping to a known `rule.interval` shape before any write; an unmappable phrase is refused (D-10), never guessed into a plausible-looking cron string |
| V6 Cryptography | n/a | No new secret material or crypto operation |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| A `PUT` that silently carries an unintended change through a shared "local template" or stale in-memory copy | Tampering (self-inflicted) | Always GET fresh immediately before mutating; never reuse a workflow JSON fetched earlier in the same session for a later mutation |
| A crashed arm/disarm cycle leaving the backend permanently armed with no operator awareness | Elevation of privilege (persistent, unintended) | D-03's explicit mitigations: Phase 27's status readout always reports the true flag state; Phase 29's sweep is the unattended backstop; a failed disarm must be reported loudly, never swallowed |
| A confident "verified" that is actually only "persisted," while the live instance still runs the old (disarmed) logic and silently drops writes the operator believed were happening | Repudiation (operator believes an action succeeded when it partially didn't) | Pattern 5's two-part persisted/effective distinction; the mandatory live-fire verification task (A1) before this phase's gate closes |
| A race between the plugin's own arm write and a concurrent admin deploy (`scripts/deploy_n8n_workflows.py`) clobbering each other, since no optimistic-concurrency field exists on this endpoint | Tampering (concurrent, non-adversarial) | No server-side mechanism exists to detect this; the only mitigation is minimizing the write's open window (this phase already does, by design — arm immediately before dispatch, disarm immediately after) and reporting failure loudly if a post-write GET shows an unexpected value |

## Sources

### Primary (HIGH confidence)
- `scripts/deploy_n8n_workflows.py` — read directly; `_n8n_headers()`, `_get_live_workflows()`,
  `_update_workflow_live()`, `enable_baked_flags()`, `_OVERLAY_FLAG_SPEC` — this repo's own
  live-tested PUT/flag-literal conventions.
- `n8n/wf_scheduled_maintenance_cloud.json` — read directly; the five deployed
  `scheduleTrigger` nodes' exact parameter shapes.
- `.planning/workstreams/plugin-entrypoint/phases/27-backend-status-surface/27-RESEARCH.md` —
  the write-safety flag's read-side regex and node names, which this phase's write side must
  match exactly.
- `.planning/workstreams/plugin-entrypoint/phases/25-enrichment-lane-cost-guard/25-RESEARCH.md` —
  the ~100s webhook response ceiling and the enrichment envelope this phase's dispatch step
  reuses unchanged.

### Secondary (MEDIUM confidence)
- [n8n Schedule Trigger node docs](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.scheduletrigger/) — full parameter schema [CITED].
- [n8n-io/n8n PR #20304](https://github.com/n8n-io/n8n/pull/20304) — the open, unmerged
  `POST /workflows/{id}/execute` proposal, its scope requirement, and response shape [CITED].
- [n8n-io/n8n Issue #25778](https://github.com/n8n-io/n8n/issues/25778) — PUT schema rejecting
  additional properties, reproduced independently of this repo's own code [CITED].
- [n8n-io/n8n Issue #24418](https://github.com/n8n-io/n8n/issues/24418) — "Active workflow
  executions do not reflect saved changes," closed `working-as-expected` [CITED, MEDIUM-LOW —
  no detailed maintainer root-cause explanation available in the sources this research reached].
- n8n community thread ("Best practice for PUT workflow using JSON from GET API") — the
  additional-properties rejection and nested-settings validation issue [CITED, community-sourced].
- n8n docs on the "Activation Trigger" / "Workflow Trigger" nodes — activation as a documented
  reload/publish event [CITED].

### Tertiary (LOW confidence)
- Various n8n community/GitHub reports of webhook-registration lag after API-driven
  create/activate (`#21614`, `#14646`, `#18893`, `#7258`) — used only to establish that
  activation-adjacent timing gaps are a recognized, recurring category of n8n behavior, not to
  pin an exact number; none independently reproduced against this repo's actual instance.

## Metadata

**Confidence breakdown:**
- PUT/activate/deactivate mechanics and the four-key body filter: HIGH — cross-confirmed by this
  repo's own live-tested code and independent public GitHub issues hitting the identical
  validation error.
- Schedule Trigger cadence schema: HIGH — read directly from this repo's own deployed workflow
  JSON, cross-checked against official n8n docs.
- The persisted-vs-effective reload gap (Pattern 5 / Open Questions #2): MEDIUM-LOW — real,
  multiply-reported, but not verified live against this specific account/version; flagged as the
  phase's single required early live-verification task.
- Manual-execution API gap (Open Questions #1): HIGH confidence that the endpoint does NOT exist
  today (unmerged PR, no ambiguity in the PR's own state); MEDIUM confidence in the recommended
  cadence-based workaround's practicality (untested against this account).

**Research date:** 2026-07-30
**Valid until:** 30 days for the n8n Public API mechanics (stable, low-churn surface); re-check
PR #20304's merge status specifically before finalizing CONTROL-01's scheduled-scan design, since
a merge would materially simplify that requirement.
