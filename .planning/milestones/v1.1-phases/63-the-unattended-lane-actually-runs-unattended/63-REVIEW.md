---
phase: 63-the-unattended-lane-actually-runs-unattended
reviewed: 2026-09-02T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - .gitignore
  - operator-claude-plugin/scripts/sweep_shim.py
  - operator-claude-plugin/skills/backend-sweep/SWEEP-CRON-TEMPLATE.md
  - operator-claude-plugin/skills/backend-sweep/lv-sweep-run.sh
  - operator-claude-plugin/tests/test_sweep_shim.py
  - operator-claude-plugin/tests/test_sweep_trigger_contract.py
  - scripts/replay_judge_models.py
  - scripts/verify_sweep_shim_scheduler.sh
  - tests/test_replay_judge_models.py
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: issues_found
---

# Phase 63: Code Review Report

**Reviewed:** 2026-09-02
**Depth:** standard
**Files Reviewed:** 9
**Status:** issues_found

## Summary

Reviewed the durable-home sweep launcher shim (63-A: `sweep_shim.py`, the staleness
self-check added to `lv-sweep-run.sh`, the real-launchd proof harness
`verify_sweep_shim_scheduler.sh`) and the offline two-model judge replay harness (63-B:
`replay_judge_models.py`). Ran the full test suite for the files in scope
(`tests/test_replay_judge_models.py`: 18 passed; `operator-claude-plugin/tests/test_sweep_shim.py`
+ `test_sweep_trigger_contract.py`: 27 passed) and `sh -n` against every shell artifact,
including the shim template extracted at runtime from `shim_text()` — all syntactically
clean, no bashisms found.

The hard invariants this phase names — the wrapper never invokes `sweep_shim.py --install`,
no LLM/Anthropic credential anywhere in the sweep trigger path, no `crontab` mutation
anywhere in the verification harness, the judge-replay module contains no write verb or
HubSpot URL, the committed verdict artifact carries no company name/evidence/request body —
all hold, both by source-text inspection and by the tests that pin them. No Critical findings.

Four Warnings: two are gaps in the "a failure is always loud" design goal this phase is
explicitly building toward (a class of shim failure that banners but never logs; a
pre-existing gap in the wrapper's headline-printing that can silently under-report notices
and then log a "posted N" line that doesn't match what was actually posted); one is a claim
in `sweep_shim.py`'s own docstring (a symlink cannot redirect the shim's exec target outside
the plugin tree) that the implementation does not fully deliver on — the check only covers
the top-level version directory, not the wrapper path one level inside it; one is in the new
verification harness itself, where the failure branch's own remediation instructions name a
file (`$PLIST_PATH`) that the very next line deletes. Four Info items are lower-severity
correctness/robustness notes.

## Warnings

### WR-01: Shim-level failures banner but never write a log line

**File:** `operator-claude-plugin/scripts/sweep_shim.py:68-79` (inside `_SHIM_TEMPLATE`,
the shell code written to the durable shim path)

**Issue:** `lv-sweep-run.sh`'s own failure paths both banner *and* `stamp()` a line to the
log (`$3`), which SWEEP-CRON-TEMPLATE.md states as the deliberate design: "the banner budget
is one short line and the log is where the rest survives." The shim's own failure paths —
"could not resolve an install" when the bootstrap loop finds nothing (lines 68-71) and
"could not resolve an install" when `--newest` fails or returns something unusable (lines
76-79) — only call `banner()`. Neither writes anything to `$3`, even though `$3` (the log
path) is already validated as present by that point (the `$#` check at line 51 has already
passed). A macOS notification can be dismissed or missed; if it is, there is no durable trace
in `~/Library/Logs/lv-backend-sweep.log` that a shim-level failure ever happened — the one
failure class in this whole design that is genuinely silent-after-the-fact.

**Fix:** Have the shim append a stamped line to `$3` on these two failure branches, mirroring
`lv-sweep-run.sh`'s `stamp()` helper (a one-line `printf` with a timestamp), e.g.:
```sh
if [ -z "$BOOTSTRAP" ]; then
    printf '[%s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" \
        "shim: could not resolve an install under $CACHE_ROOT" >> "$3"
    banner "LV backend sweep launcher: cannot run - wrong number of arguments"
    exit 1
fi
```
(The wrong-argument-count branch at line 51-54 cannot safely do this — `$3` may not even be
the log path in that case, since the argument order itself is what's in question.)

### WR-02: Headline-printing program has no exception guard, unlike the count program (pre-existing, not introduced by phase 63)

**File:** `operator-claude-plugin/skills/backend-sweep/lv-sweep-run.sh:55-93`

**Issue:** This code predates phase 63 (only the staleness block at lines 28-44 is new to
this phase; confirmed via `git diff` against the phase's base commit) but is in the reviewed
file, so it's included here. The `COUNT` python program (lines 55-62) wraps its work in
`try/except Exception: print(-1)`, so any malformed `$OUT` shape degrades to the "unreadable"
banner path. The `HEADLINES` program (lines 78-85) has no such guard:
```python
d = json.loads(sys.argv[1])
for n in d:
    h = n.get("headline") or ""
    if h:
        print(h)
```
If any element of the parsed list is not a dict (e.g. a bare string), `n.get(...)` raises
`AttributeError` and the program aborts mid-loop — headlines after the bad element are never
printed, and no banner or log line records that the print was incomplete. Worse, the final
`stamp "posted $COUNT notification(s)"` (line 93) reports `$COUNT` (the total notice count),
not the number of banners actually posted, so on this exact failure path the log itself
misrepresents what happened — it claims full delivery for a run that silently dropped some.
`sweep_entry.py`'s current notice-construction paths always emit well-formed dicts, so this
is latent rather than currently triggered, but the `COUNT` program's own defensiveness
(`isinstance(d, list)` only — it does not check item shape either) shows the wrapper does not
trust that shape to be guaranteed.

**Fix:** Wrap the `HEADLINES` program in the same `try/except` pattern as `COUNT`, and count
what was actually printed rather than trusting `$COUNT`:
```python
import json, sys
try:
    d = json.loads(sys.argv[1])
    for n in d:
        h = (n.get("headline") if isinstance(n, dict) else None) or ""
        if h:
            print(h)
except Exception:
    pass
```

### WR-03: Symlink-escape guard covers the version directory, not the wrapper path one level inside it

**File:** `operator-claude-plugin/scripts/sweep_shim.py:100-123` (`newest_install_root`) and
the `exec` line inside `_SHIM_TEMPLATE` at line 81

**Issue:** The docstring for `newest_install_root` (lines 90-94) states the symlink check
exists so "any entry whose resolved path escapes the resolved `cache_root` is skipped
(T-63-01 — a symlink inside a user-writable cache root must not redirect the shim's `exec`
target outside the plugin tree)." The implemented check (lines 108-114) resolves and validates
containment only for the **top-level candidate directory** (`entry`, e.g. `1.1.0`). The
existence check for the wrapper itself, `(entry / "skills" / "backend-sweep" /
"lv-sweep-run.sh").is_file()` (line 115), follows symlinks with no equivalent containment
check — a real (non-symlink) version directory that itself contains a symlinked
`lv-sweep-run.sh` pointing anywhere on the filesystem would pass every check here, and the
shim would then `exec /bin/sh "$NEWEST/skills/backend-sweep/lv-sweep-run.sh" ...` against
that redirected target. This is a gap between the stated guarantee and what's implemented,
not a demonstrated exploit — an attacker who can already write inside the cache root can
plant a fully malicious (non-symlinked) version directory just as easily, so the practical
blast radius is unchanged. But the docstring's claim ("must not redirect the shim's exec
target outside the plugin tree") is broader than the code delivers, and the existing test
(`test_symlink_escaping_cache_root_is_skipped`) only exercises the top-level-directory case.

**Fix:** Either narrow the docstring's claim to "the version directory itself," or extend the
check to resolve `(entry / "skills" / "backend-sweep" / "lv-sweep-run.sh")` and verify it
also stays within `resolved_cache_root` before treating the candidate as valid.

### WR-04: The harness's own failure-path remediation instructions name a file the harness then deletes

**File:** `scripts/verify_sweep_shim_scheduler.sh:64-87` (`cleanup()`)

**Issue:** When `launchctl unload` cannot be confirmed, the failure message tells the operator:
```
Remove it by hand: launchctl unload '$PLIST_PATH' (or launchctl list | grep $LABEL_PREFIX ...)
```
`$PLIST_PATH` is `"$WORK/${LABEL}.plist"` — it lives inside the harness's own temp work
directory. The very next block in the same `cleanup()` function, unconditional on
`$TEARDOWN_OK`, runs:
```sh
if [ -n "$WORK" ] && [ -d "$WORK" ]; then
    rm -rf "$WORK"
fi
```
So by the time an operator reads the printed remediation and tries
`launchctl unload '$PLIST_PATH'`, the plist file named in that exact command no longer
exists — `launchctl unload` on a missing file will fail, leaving only the second,
label-lookup-based remediation path (`launchctl list | grep ... | launchctl bootout ...`)
actually usable. This directly touches the phase's stated constraint that the harness "must
always remove a temporary launchd agent, including on failure paths" — the agent registration
itself is left in place correctly (that part is right), but the harness destroys its own
best remediation artifact on exactly the path where the operator needs it.

**Fix:** Skip (or copy elsewhere) the `rm -rf "$WORK"` when `$TEARDOWN_OK` is `0`:
```sh
if [ -n "$WORK" ] && [ -d "$WORK" ]; then
    if [ "$TEARDOWN_OK" -eq 1 ]; then
        rm -rf "$WORK"
    else
        log_err "leaving work dir in place for manual cleanup: $WORK"
    fi
fi
```

## Info

### IN-01: `_resolve_model_ids` reads a config key that is never present in `CONFIG_FLAG_DEFAULTS`

**File:** `scripts/replay_judge_models.py:447-458`

**Issue:** `defaults.get("ANTHROPIC_JUDGE_MODEL_CHEAP", "claude-haiku-4-5")` reads a key that
does not exist anywhere in `scripts/build_cloud_workflows.py`'s `CONFIG_FLAG_DEFAULTS` dict
(confirmed — only `ANTHROPIC_RESEARCH_MODEL` and `ANTHROPIC_JUDGE_MODEL` are defined there).
The `.get(..., "claude-haiku-4-5")` call therefore *always* falls through to the hardcoded
default, which happens to be exactly the model this harness is meant to evaluate — so the
behavior is correct today, but the code reads as if it dynamically sources a "cheap judge
model" config value that in fact never exists and is silently and permanently a hardcoded
literal.

**Fix:** Either add `ANTHROPIC_JUDGE_MODEL_CHEAP` to `CONFIG_FLAG_DEFAULTS` (if it's meant to
become a real, tunable config flag) or replace the `.get(...)` call with a plain module-level
constant to stop implying a config lookup that will never resolve.

### IN-02: Corpus extraction only reads the first run of a node per execution

**File:** `scripts/replay_judge_models.py:168-174`

**Issue:** `runs = run_data.get(node_name); ... for item in _node_output_items(runs[0]):`
only inspects `runs[0]` — the first NodeRun for that node name within an execution. If
"Build Judge Request" / "Build Contact Judge Request" ever executes more than once within a
single n8n execution (e.g. inside a loop construct), later runs' output items are silently
dropped from the corpus. This mirrors an existing pattern already used elsewhere in
`scripts/enrichment_cost_ledger.py` for the same node family, so it's likely consistent with
how these nodes actually execute in the current workflow topology (batched items in one run,
not looped re-invocations) — but it is worth flagging because the failure direction, if the
assumption is ever wrong, is silent undercounting, not a crash. The error direction is safe
either way: undercounting only pushes the verdict toward `DROP`/`insufficient_corpus`, never
toward a false `SHIP`.

**Fix:** If node re-invocation within a single execution is ever possible for this workflow
shape, iterate all of `runs`, not just `runs[0]`.

### IN-03: The shim's bootstrap install-pick is unordered by design

**File:** `operator-claude-plugin/scripts/sweep_shim.py:56-66` (inside `_SHIM_TEMPLATE`)

**Issue:** The bootstrap loop that locates a python-importable copy of `sweep_shim.py` to
compute "newest" picks the **first** matching version directory under the cache root, not the
newest. This is explicitly documented as deliberate ("This pick is deliberately unordered").
Noting for completeness: this means the *resolution logic itself* (including any future
safety fix inside `newest_install_root`, e.g. the symlink check in WR-03) is only as
up-to-date as whichever install happens to bootstrap first — not necessarily the newest
installed version. Given cache roots are typically pruned of stale installs on update, the
practical exposure window is small, but it's worth knowing this is the shape of the design
rather than an oversight.

**Fix:** None required — documented tradeoff. Flagging only so it isn't mistaken for an
unnoticed gap during a future audit.

### IN-04: Staleness comparison is a raw string equality, sensitive to a trailing slash

**File:** `operator-claude-plugin/skills/backend-sweep/lv-sweep-run.sh:38`

**Issue:** `if [ "$1" != "$NEWEST_ROOT" ]; then` compares the running root against the
resolved newest root as plain strings. `$NEWEST_ROOT` is always produced by
`sweep_shim.py --newest`, which never has a trailing slash (Python `Path` construction
strips it). But SWEEP-CRON-TEMPLATE.md's own "Already have a schedule installed under the old
shape?" section instructs an admin to hand-edit an existing cron/launchd entry's
`[plugin-root]` argument. If that hand-edited value ever carries a trailing slash (e.g.
`.../1.1.0/`), `dirname` still correctly strips it down to the right cache root for
resolution purposes, but the direct string comparison at line 38 would then permanently
disagree even while running the genuinely-newest install — every fire would log a false
"sweep running from an old version" line and post a spurious banner, with no way to clear it
short of re-editing the schedule entry.

**Fix:** Normalize `$1` before comparing, e.g. `RUNNING_ROOT="${1%/}"` and compare against
that instead of `$1` directly.

---

_Reviewed: 2026-09-02_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
