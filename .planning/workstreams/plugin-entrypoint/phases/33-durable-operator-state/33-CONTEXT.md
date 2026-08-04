# Phase 33: Durable Operator State - Context

**Written:** 2026-08-04 · **Workstream:** `plugin-entrypoint` · **Target release:** plugin `0.7.0`

Raised by the operator after hand-copying `operator.local.json` three times in one afternoon
across `0.6.0 → 0.6.1 → 0.6.2`. Their words: *"I don't want the operator to need to do a
self-migration."* The plugin's own REQUIREMENTS.md lists **"Operator-run commands, scripts, or
config files … Terminal instructions to the operator are a requirement failure"** under Out of
Scope — so the current state is a standing violation of the plugin's stated design, not a
convenience gap.

## Phase Boundary

**In:** where per-operator state lives and how it moves. Two files, one resolution rule, one
one-time migration, the `initialize` report, and entrypoint-level tests.

**Out:** anything about what the config CONTAINS (no new keys, no schema change), the backend, the
n8n workflows, and the plugin's capability matrix. This phase moves files; it does not change what
any capability means.

## The problem, measured

Two pieces of per-operator state live INSIDE the versioned install directory
(`~/.claude/plugins/cache/lightning-visuals-operator/operator-claude-plugin/<version>/`), so a
plugin update — which lands in a NEW directory — leaves both behind:

| State | Current path | Survives update |
|---|---|---|
| `operator.local.json` (n8n URL, webhook secret, API key) | `PLUGIN_ROOT/config/` (`config_gate.py:10`) | No — hand-copied 3× on 2026-08-04 |
| `dashboard_artifact.json` (the Artifact pointer) | `PLUGIN_ROOT/state/` (`artifact_store.py:28`) | No — **and nobody noticed** |

**The pointer one silently breaks a sealed requirement.** STATUS-05 / UAT 4.5 is "a brand-new
conversation lands on the SAME dashboard URL, not a second one", proven by RB-4 and marked
Complete. That guarantee is carried entirely by the pointer file. Verified 2026-08-04: **no
install directory on this machine holds one** (`0.1.0`, `0.6.0`, `0.6.1`, `0.6.2` all lack
`state/`). So the next dashboard request will mint a fresh URL and read as a regression. The code
is not defective; the storage location is.

**Stale credential copies.** Verified 2026-08-04 — `0.1.0`, `0.6.1` and `0.6.2` each hold a full
copy of `webhook_secret` and `n8n_api_key`. Every future update adds another unless migration
cleans up behind itself.

## Implementation Decisions

### Settled by the operator — do not relitigate

1. **Migration runs at config RESOLUTION, not only in `initialize`.** The operator's first
   instinct was to put it in `initialize`; the flaw is that an operator who never types
   `/initialize` — most of them, since nothing prompts it — loses config on their NEXT update.
   Resolution is the hook that cannot be skipped. `initialize` still REPORTS the resolved path.
2. **A one-time sibling scan is required, and it is the whole point.** Without it, the release
   that introduces durability is itself the one that loses the config: `0.7.0`'s new install
   directory is empty, the durable home is empty (0.6.2's code never wrote it), and the legacy
   fallback resolves to the new empty directory. The scan looks across sibling install
   directories under this plugin's own cache root, newest version first, and migrates the newest
   config it finds.
3. **Durable home:** `~/.claude/plugins/data/<plugin>-<marketplace>/`, i.e.
   `operator-claude-plugin-lightning-visuals-operator`. Inferred from other installed plugins
   (`caveman-caveman`, `claude-mem-thedotmack`, `security-guidance-claude-plugins-official`) —
   **NOT verified as a documented, stable contract.** That uncertainty is why an env override and
   the legacy fallback both stay: if the convention shifts, the plugin degrades to today's
   behaviour instead of losing config.

### Contracts to honor

- **Resolution order, first hit wins, identical shape for both files:**
  1. explicit path argument (tests only — every existing test passes one, and must keep working)
  2. `LV_OPERATOR_CONFIG` env var (admin escape hatch)
  3. durable home
  4. `PLUGIN_ROOT/config/operator.local.json` (legacy, same install)
  5. newest sibling install → **migrate to (3)**, once
- **`load_config()` still enforces only `n8n_url`** (0.6.1, `f57b964`). Do not re-add a
  capability-specific key check to it. Capability keys are gated by `require_capability()` at the
  layer that needs them.
- **`config_gate.py`'s `__main__` still emits `can_send` + `send_blocked_reason`** (0.6.2,
  `f5ba08f`) and `SKILL.md` still consumes them. A two-sided test already pins this; keep it green.
- **No secret in any message, log line, or refusal** — the existing
  `test_no_configerror_message_ever_contains_the_secret_value` guard generalizes to the migration
  path.
- Migration is **idempotent and silent when there is nothing to do**. A no-op run must not print,
  log, or touch mtimes.

### Claude's Discretion

- Whether the migration lives in `config_gate` directly or in a small shared helper that
  `artifact_store` also imports (the two need the same durable-home resolution).
- Whether the dead install's config is deleted immediately after a verified copy or on the next
  successful resolution. Deleting a credential file is irreversible — favour verify-then-delete,
  and never delete the CURRENT install's copy.
- Failure posture when the durable home is unwritable (read-only HOME, permissions): the plugin
  must still WORK from wherever it read the config. Degrade to using the legacy path and say so;
  never refuse to operate because migration failed.

## Canonical References

- `operator-claude-plugin/scripts/config_gate.py` — resolution point, `DEFAULT_CONFIG_PATH:10`
- `operator-claude-plugin/scripts/artifact_store.py` — `DEFAULT_STATE_PATH:28`, `_state_path():40`
- `operator-claude-plugin/scripts/init_check.py` — reports the path to the operator
- `operator-claude-plugin/skills/initialize/SKILL.md` — the operator-facing setup contract
- `operator-claude-plugin/CHANGELOG.md` — the release checklist at the bottom: bump
  `plugin.json` in the SAME commit as the CHANGELOG cut, then refresh the marketplace clone

### Evidence trail

- `.planning/todos/completed/2026-08-04-load-config-over-refuses-status.md` — the 0.6.1 fix
- `.planning/todos/completed/2026-08-04-upload-preflight-lost-its-guard.md` — the 0.6.2 fix
- `.planning/debug/load-config-over-refusal.md` — why entrypoint-level tests are mandatory here

## Patterns

**The rule this phase exists under, learned six times in this milestone and twice this week:**
pin behaviour at the layer the operator actually reaches. `config_gate` has now shipped a defect
in each direction — refusing where it should degrade (0.6.1), then not refusing where the skill
needed a verdict (0.6.2) — and both were invisible to tests that called the resolver directly.
Every success criterion here is testable by driving the CLI as a subprocess against an isolated
plugin root; the harness for that already exists in `tests/test_config_gate.py::_run_cli` and
should be reused rather than reinvented. Note its own history: the first attempt silently read
the operator's REAL config because `runpy` discarded the path override.

**Simulating an update in a test** is the key move for criteria 1, 2 and 5: build a fake cache
root with two version directories, put a config in the older one, resolve from the newer one, and
assert the migration happened, the mode is `0600`, and the second resolution is a no-op.

## Specific Ideas

- A tiny `durable_paths.py` (or equivalent) exporting `durable_dir()`, `resolve_config_path()` and
  `resolve_state_path()` keeps the rule in ONE place for both consumers — the second-source-of-truth
  pattern this milestone avoids everywhere else.
- `initialize` gains one line: where the config actually is. It should read as reassurance, not as
  a terminal instruction.

## Deferred Ideas

- Cleaning up entire stale install DIRECTORIES (not just their configs) — that is the plugin
  manager's business, not this plugin's.
- Any migration of the cost-rate table or other shipped config; those are package data, not
  operator state, and belong with the version.
