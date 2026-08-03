# 29-HOST-PROBE — recorded verdicts for A1, A2, A5 (plan 29-01)

**Probed:** 2026-08-03 (AEST) · **Operator:** Robert · **Plugin:** operator-claude-plugin 0.1.0,
installed via the Desktop marketplace from `AusGTM/lightning-visuals-n8n` (`.claude-plugin/
marketplace.json`), running from the versioned plugin cache — NOT a repo checkout.

**Read this before building 29-03…06.** The verdicts below are per HOST, because the phase's
original host assumption did not survive contact: D-01 named "Claude Desktop scheduled routines"
(`~/Documents/Claude/Scheduled/`), and the operator's actual surface is **Claude Code Desktop**,
where that scheduler's UI is not visible. Four candidate hosts were examined; one works.

---

## A1 — can a scheduled, unattended invocation reach this plugin's skill and return REAL data?

> **⚠ SUPERSEDED 2026-08-03 (Phase 32, RB-8) — this verdict is amended, not retracted.** The
> host below is no longer what 29-03…06's trigger runs on. It is now **cron/launchd → the
> plugin's own Python**, via `skills/backend-sweep/lv-sweep-run.sh` (32-01) — no `claude -p`,
> no Anthropic credential, no LLM in the path at all.
>
> **Why this probe misled:** it was run from an interactive shell, which inherits a live
> session's credentials and PATH. That proved `claude -p` works *headlessly*; it did not
> prove it works *unattended under cron*, which is what NOTICE-03 actually requires. RB-8
> (`29-06-FINDINGS.md`) fired this exact trigger under real cron and it failed silently — an
> expired credential with no refresh, `node` absent from cron's PATH.
>
> **This is the same class of error as the stored-vs-running reload gap:** a verification
> performed one layer away from the thing it claimed to verify. See `29-06-FINDINGS.md` for
> the verbatim failure and Phase 32 (`32-01-PLAN.md` / `32-01-SUMMARY.md`) for the
> replacement. The verdict below is preserved as the dated record of what was actually
> observed on 2026-08-03 — read it as "headless `claude -p` works interactively," not as
> "the cron trigger works."

**YES — on the host `headless claude -p`** (the thing a macOS cron/launchd job runs).

Probe: `claude -p "<probe prompt>" --allowedTools "Skill,Bash,Read,Glob,Grep"`, cwd `$HOME`
(deliberately NOT the repo — a real scheduled job starts nowhere useful). Observed, verbatim
verdict block:

```
LV-SWEEP-PROBE RESULT (host: headless claude -p, cwd $HOME)
A1 reached the skill: YES
A1 real data returned: YES-REAL-DATA (three named live workflows from n8n API — "LV Scheduled
  Maintenance (Cloud)", "LV Enrichment (Cloud template)", "LV Contact Ingest (Cloud template)" —
  with real execution IDs 1099/443/26 and timestamps; note: webhook-backed half unavailable,
  http_404, so review counts/balances read "unknown")
A5 notification posted: YES (osascript exit 0)
END OF PROBE OUTPUT
```

- **Real data, not narration:** named workflows, live execution ids, per-workflow write-safety
  state — all from the n8n API through the INSTALLED plugin's own scripts and cache config.
- The `http_404` half is a **separate, pre-existing defect** (the `hubspot/backend-status`
  webhook workflow was built by 27-02 but never deployed to the tenant), not a host failure.
  The skill rendered those values as `unknown`, never zero — exactly as designed.
- `END OF PROBE OUTPUT` survived — no truncation in the headless stdout path.

### Hosts that do NOT work — measured, not assumed

| Host | Verdict | Evidence |
|---|---|---|
| Claude Code Desktop cloud **Routines** | **NO, twice over** | `HTTP 403 — no access to a repository this routine uses` (GitHub integration not granted on the private repo); and structurally, `operator.local.json` is local-only/gitignored, so secrets can never reach a cloud sandbox. Viable only if BOTH the repo grant and cloud-environment env vars are set up — neither exists today |
| Harness **CronCreate** jobs | **NO for NOTICE-03** | Session-only by contract: fires into the creating session while idle, dies with it. NOTICE-03 requires a sweep with *no session open* |
| Claude Desktop app scheduler (`~/Documents/Claude/Scheduled/`) | **UNVERIFIED, moot** | The operator's surface (Claude Code Desktop) does not show its UI. Not disproven — but with headless working, nothing depends on it |

**Consequence for D-01: host amended** from "Claude Desktop scheduled routines" to
**cron/launchd → `claude -p` headless**. Same property the decision wanted (unattended, local,
has plugin + config + secrets, can notify); different scheduler. This is an explicit amendment,
not drift — 29-03…06 build against the headless host.

> **⚠ SUPERSEDED 2026-08-03 (Phase 32) — this host is itself amended.** RB-8 proved the
> headless-`claude -p` host fails silently under real cron (credential expiry, `node` off
> PATH). D-01's host is amended a second time, to **cron/launchd → the plugin's own Python**
> via `lv-sweep-run.sh` — no LLM, no credential. See the amendment at the head of §A1.

## A2 — does Desktop chat report back unprompted mid-conversation?

**NOT OBSERVED → treated as NO**, exactly as 29-01 Task 2 prescribes (an unverified capability
and an absent one get the same treatment; the cost of being wrong is a watch that goes silent,
which NOTICE-02 forbids). The bounded in-session watch (D-07) is the designed-for outcome.
Nothing in 29-04 may fail because this is NO — that constraint stands.

## A5 — where does unattended output surface, and how much renders?

- **macOS Notification Centre banner: CONFIRMED by the operator** ("LV Sweep Probe" banner
  appeared, visible in Notification Centre). Posted by the probe itself via `osascript` — the
  same call a sweep would make. **Banner budget is one short line** (title + ~1 sentence);
  format notices accordingly (29-05's ceiling).
- **The full report surfaces in the invoking session's stdout/transcript** — untruncated in
  this probe. A cron wrapper should redirect stdout to a log file so the detail outlives the
  banner; the banner says *that* something needs a human, the log says *what*.

## Defect found by the probe (fixed same session)

`backend-status/SKILL.md` implied `python3 scripts/...` runs relative to the skill directory;
scripts live at the **plugin root**. The probe lost a step to `[Errno 2] No such file or
directory` and recovered by trying the plugin root — an unattended sweep might not recover.
All six skills now carry an explicit "Where commands run" note. Related, still open: the
installed plugin's config resolves into the **versioned** cache path
(`…/operator-claude-plugin/0.1.0/config/operator.local.json`), so a version bump orphans the
operator's config — remediation queued, not yet designed.

## What 29-03…06 may rely on

1. ~~Headless `claude -p` reaches the installed plugin's skills with real backend data. (A1)~~
   **SUPERSEDED 2026-08-03 (Phase 32):** the trigger is now `lv-sweep-run.sh` running
   `sweep_entry.py` directly against the plugin's own Python — no `claude -p`, no LLM in the
   path. See the amendment at the head of §A1.
2. `osascript` notifications reach the operator's Notification Centre. (A5)
3. Full detail goes to a log; the banner is one line. (A5)
4. No unprompted mid-conversation reporting exists — bounded watch only. (A2 = NO)
5. The backend-status webhook half stays `unknown` until the 404 remediation (disarmed deploy
   of `wf_backend_status_cloud.json`) lands — build to degrade, exactly as the skill already does.
