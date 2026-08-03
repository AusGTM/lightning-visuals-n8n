# v0.6 Handoff — Claude Plugin Entrypoint

**Written:** 2026-08-03 (supersedes 2026-07-31) · **Milestone:** v0.6 · **Workstream:** `plugin-entrypoint`
**Read this first on a fresh context.** Everything below was verified live; do not re-derive or
"correct" it.

---

## 1. Where things stand

**Branch `feat/v0.6-plugin-entrypoint`, fully pushed to `origin/master` (fast-forward), tree clean.**
Suites: **1686 pytest / 6 skipped · 509 node · 811+ plugin** (all via `.venv/bin/python -m pytest`
and `node --test tests/n8n/*.test.mjs` — FILE form). Every `n8n/*.json` disarmed (grep → 0), and —
new — **the LIVE tenant is verified disarmed in both stored AND running content** (disarm + bounce +
read-back, 2026-08-03).

| Phase | State |
|---|---|
| 23 | ✅ **COMPLETE incl. armed canary** — contact `342770428400` created by run 1129; found the reload gap + BUG 27 on the way |
| 24, 25, 26 | ✅ COMPLETE (25 fully: Probe A granted, **B4 measured 37.44 s → ceiling 2 CONFIRMED**, oversize refusal verified live verbatim) |
| 27 | ✅ **COMPLETE incl. RB-4 operator walk** — STATUS-05 checked; dashboard same-URL proven cross-session |
| 28 | 28-01…05 built. **RB-7 (28-06 armed canary) is THE NEXT GATE** |
| 29 | 29-01 ✅ (host probe answered), 29-02 ✅, 29-03 ✅ (tracer + read-only guard). **29-04, 29-05, 29-06 are the remaining autonomous builds** |
| 30 | 30-01…06 built; 30-07 (RB-9 armed review canary) remains |

**Remaining work, in order:** RB-7 (operator, via the 28-05 surface, `ALLOW_N8N_ARM`) → my 29-04
(bounded watch) → 29-05 (five conditions; live shapes recorded in 29-05-PLAN header) → 29-06 (sweep
skill + cron template) → RB-8 (29-06 live gate) → RB-9 (30-07; `LV Review Decision` is deployed,
inactive, waiting). Then milestone seal: flip CONTROL/NOTICE/REVIEW checkboxes on canary evidence,
reconcile STATE progress counts.

## 2. THE TWO BIG LIVE FINDINGS OF 2026-08-03 — never un-learn these

1. **Stored vs running content (the reload gap).** `deploy_n8n_workflows.py` PUTs but never
   activates (its line 25). n8n serves a RUNNING workflow's old content until a
   deactivate→activate bounce. `verify_live_write_safety.py` reads STORED content, so `armed PASS`
   ≠ the running webhook is armed — proven by runs 1122/1123 firing disarmed inside an "armed"
   window. **Every arm AND disarm now bounces all active workflows**; the pastes in
   OPERATOR-RUNBOOK RB-3 §B history show the exact form. `n8n_arming.armed_window` was already
   correct (apply_mutation brackets); the ENABLE_BAKED_FLAGS deploy path was not.
2. **BUG 27 (fixed `22a3f2a`).** The spliced create gate derived domain from
   `identity_keys.domain`/`json.domain` — fields Decide Action never emits — so with no
   `hs_object_id` a net-new create evaluated `_writeSafetyAllows('create', null, null)` and was
   denied REGARDLESS of arming. Fix: domain from `properties.email`, **create-action only** — the
   unscoped version handed review gates a domain path 30-02 deliberately withheld and
   `reviewDecisionEndpoint g3` caught it. Pinned by two-sided flow tests that RUN Decide Action and
   feed its verbatim output to the gate. **A contract held in two places needs a test that reads
   both** — this was the fourth instance in the milestone.

## 3. Other facts established live this session

- **Phase 29 host AMENDED (D-01):** the sweep host is **cron/launchd → `claude -p` headless**
  (probe: reached installed plugin, real data, osascript banner confirmed in Notification Centre).
  Cloud Routines fail twice (403 repo access; secrets are local-only). Harness CronCreate is
  session-only. Full verdicts: `29-HOST-PROBE.md` (§A1/§A2/§A5 — A2 is NO).
- **Backend-status endpoint LIVE** (created + activated 2026-08-03; first answer recorded verbatim
  in 29-05-PLAN header): real zero queues; balances lusha 3932 / zoominfo 9301 / apollo
  `unreadable (unrecognized_response_shape)`; credential probes `no_response` (a real state
  distinct from invalid — must degrade to unknown, never fire as broken).
- **KNOWN OPEN BUG:** the plugin's `backend_status` reader reports `unrecognized_response_shape`
  against the live endpoint — the webhook wraps its answer in an ARRAY (`[{...}]`) and the reader
  expects the bare object. Client-side unwrap fix + test, unassigned. Until fixed, queue counts and
  balances read `unknown` through the plugin (curl shows the real data).
- **KNOWN OPEN BUG (Phase 26):** the thin-response dispatch report labels unconfirmable sends
  `not_confirmed` and *guesses* the reason from the session's possibly-stale gate belief — it
  narrated the canary's gated sends as "write gated" from stale evidence. Reason field must be
  marked belief, not observation.
- **Installed-plugin realities:** config resolves into the VERSIONED cache path
  (`~/.claude/plugins/cache/lightning-visuals-operator/operator-claude-plugin/0.1.0/config/operator.local.json`)
  — a version bump orphans it (remediation queued), and — found live 2026-08-03 — a **same-version
  reinstall DELETES it outright**, leaving only the example. Back it up before every reinstall.
  Worse, **reinstalling the plugin does not refresh the marketplace clone** it copies from
  (`~/.claude/plugins/marketplaces/lightning-visuals-operator`), which sat at `a60e3da` for five
  commits while repeated uninstall/reinstall cycles re-copied the same stale snapshot. `plugin.json`
  pins `"version": "0.1.0"` by hand and has never been bumped, so **the version number proves
  nothing about freshness — verify by content.** Both traps and the shallow-clone fetch command are
  written up in OPERATOR-RUNBOOK RB-7 step 0. Slash commands are not recognized in Claude
  Code Desktop but conversational/skill dispatch works. The installed 0.1.0 predates 28-05 —
  version-skew: its sessions still claim on/off control "does not exist". Marketplace install from
  `AusGTM/lightning-visuals-n8n` works (manifest at repo root; validate BOTH from the COMMIT, not
  the working tree — the author-object fix was once live-broken on master while the tree passed).
- **All six skills carry a "Where commands run" note** (plugin root, not skill dir) and
  backend-status carries "a file attachment is not a dashboard" — both from live misses.
- **Chunk ceiling 2 is MEASURED** (B4 37.44 s full waterfall, +25% headroom, floor(100/46.8));
  the pinning tests now FORBID the word PROVISIONAL and require the figure+date.

## 4. RB-7 (28-06) — the next gate, how it runs

Drives the 28-05 surface end to end under `ALLOW_N8N_ARM=true`: `plan_action` → operator "yes" →
`execute_action` with a real `dispatch_fn` inside `n8n_arming.armed_window` (which brackets
correctly). Closing gate: re-run `test_control_disarmed_artifacts.py` + live disarmed read-back.
Read 28-06-PLAN.md first and expect §7b-class staleness (it was written before 28-05 existed as
built, before the bounce lesson, and before BUG 27). The operator pastes `!`-prefixed one-liners in
Claude Code Desktop; each `!` line is its own shell (re-source `.env` inside every line; `.env` is
permission-blocked to the agent — credentials only enter via the operator's `!` lines).

## 5. Safety invariants — unchanged, plus one

- Committed artifacts disarmed (`grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json` → 0).
- No automated arm/deploy/activate/live-write. Disarmed deploys and activation have passed via the
  python driver when operator-directed; ARMING remains the blocked line.
- **A window is not closed until the disarm read-back passes AND the bounce has run** — stored and
  running both.
- The `ALLOW_*` gates all demand the literal `true`; disarm paths are never gated.
- Step 8 outstanding: operator deletes/marks canary contact `342770428400`.

## 6. Sections retained from the 2026-07-31 handoff — still true, read there if needed

The previous handoff's §2 verified-facts table (lock property absent, provenance blob convention,
`lv_`-prefixed review props, Decide Action emits no email, multipart field `data`, canonical 7
props, ~100 s Cloudflare ceiling, `enable_baked_flags` cannot disarm, providers
`onError: continueRegularOutput`, tenant pin `N8N_EXPECTED_URL=https://alexherman.app.n8n.cloud`),
its §3 seven amendments (plus #5/#6 now closed in artifacts by 28-05), §6 tooling gotchas (dotenv
wrapper, `--ws plugin-entrypoint`, hand-edit STATE.md, unreliable decision-coverage gate), and §8
conventions (tell executors about siblings; SKILL.md/README are shared surfaces; verify agent
claims independently) — all stand. Git history `22a3f2a^..HEAD` carries today's evidence trail.
