# Phase 33: Durable Operator State - Research

**Researched:** 2026-08-04
**Domain:** Claude Code plugin persistent-data contract; Python atomic/secure file writes; version-directory discovery without a `packaging` dependency
**Confidence:** HIGH — the single highest-value unknown (research priority 1) resolved from primary-source official documentation plus a live install-manifest read on this machine, not inference.

## Summary

Phase 33 moves two files (`operator.local.json`, `dashboard_artifact.json`) out of the
versioned plugin-cache directory into a durable, version-independent home, with a one-time
migration and no operator-visible terminal step. CONTEXT.md flagged the durable-home path as
"NOT verified as a documented, stable contract" and kept an env override plus legacy fallback
as load-bearing insurance. That uncertainty is resolved by this research: **`${CLAUDE_PLUGIN_DATA}`
is a documented Claude Code contract** (official plugins reference, "Persistent data
directory" section), it resolves to exactly the path CONTEXT.md inferred
(`~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/`), and the
plugin's own install manifest on this machine confirms the exact id string the formula
consumes (`operator-claude-plugin@lightning-visuals-operator`). CONTEXT.md's decision to keep
the env override and legacy fallback stands regardless — it is a locked decision, not
relitigated here — but the plan can now write the durable-home constant with a citation
instead of a guess, and should upgrade the accompanying code comment from "inferred, not
verified" to "verified against the documented contract, kept alongside a fallback per
CONTEXT.md D-1."

One real, unresolved operational risk surfaced during this research and is not fully
answerable without a live check: a closed (not-planned) Claude Code GitHub issue
(#41156) reports that writes into `~/.claude/plugins/data/<id>/` trigger a "sensitive
location" permission-confirmation prompt from the Bash-tool permission layer, even under
`bypassPermissions`, when a script performs the write as a subprocess Claude Code launched
interactively. This does not affect the unattended cron sweep (Phase 32's `lv-sweep-run.sh`
runs as a bare subprocess outside Claude Code's tool layer entirely — the confirmation
layer cannot fire there), but it may affect the FIRST interactive resolution that performs
the migration write. This is flagged as an Open Question with a recommended runbook-style
live check, consistent with how this project has resolved every other Claude-Code-host
uncertainty in this milestone (RB-1 through RB-9).

**Primary recommendation:** Build one shared module (`durable_paths.py`, per CONTEXT.md's own
"Specific Ideas") that (1) prefers `os.environ.get("CLAUDE_PLUGIN_DATA")` when present since
it is the harness-authoritative source, (2) falls back to computing
`Path.home() / ".claude" / "plugins" / "data" / "operator-claude-plugin-lightning-visuals-operator"`
directly (matching the documented substitution formula) when the env var is absent — which it
will be for every `python3 scripts/....py` invocation launched from SKILL.md instructions,
since those are plain Bash-tool subprocesses, not hooks/MCP/LSP subprocesses, the only three
process kinds the harness is documented to export the variable into. Write the migrated file
via temp-file-then-`os.replace` (not bare `os.open(..., O_CREAT)`) so a mode-0600 file is never
observable in a partially-written state. Parse sibling version directories with a tuple-of-ints
key, no `packaging` dependency. Extend `tests/test_config_gate.py::_run_cli`'s existing
subprocess harness — do not reinvent it — by pointing the subprocess's `HOME` env var at a
fake home directory, which redirects `Path.home()`-based resolution into `tmp_path` without
touching `durable_paths.py`'s production code path at all.

## User Constraints (from CONTEXT.md)

### Locked Decisions

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
   **NOT verified as a documented, stable contract** [as written in CONTEXT.md — this research
   now verifies it; see Summary]. That uncertainty is why an env override and the legacy
   fallback both stay: if the convention shifts, the plugin degrades to today's behaviour
   instead of losing config.

### Contracts to Honor

- **Resolution order, first hit wins, identical shape for both files:**
  1. explicit path argument (tests only — every existing test passes one, and must keep working)
  2. `LV_OPERATOR_CONFIG` env var (admin escape hatch)
  3. durable home
  4. `PLUGIN_ROOT/config/operator.local.json` (legacy, same install)
  5. newest sibling install → **migrate to (3)**, once
- **`load_config()` still enforces only `n8n_url`** (0.6.1, `f57b964`). Do not re-add a
  capability-specific key check to it. Capability keys are gated by `require_capability()` at
  the layer that needs them.
- **`config_gate.py`'s `__main__` still emits `can_send` + `send_blocked_reason`** (0.6.2,
  `f5ba08f`) and `SKILL.md` still consumes them. A two-sided test already pins this; keep it
  green.
- **No secret in any message, log line, or refusal** — the existing
  `test_no_configerror_message_ever_contains_the_secret_value` guard generalizes to the
  migration path.
- Migration is **idempotent and silent when there is nothing to do**. A no-op run must not
  print, log, or touch mtimes.

### Claude's Discretion

- Whether the migration lives in `config_gate` directly or in a small shared helper that
  `artifact_store` also imports (the two need the same durable-home resolution).
- Whether the dead install's config is deleted immediately after a verified copy or on the next
  successful resolution. Deleting a credential file is irreversible — favour verify-then-delete,
  and never delete the CURRENT install's copy.
- Failure posture when the durable home is unwritable (read-only HOME, permissions): the plugin
  must still WORK from wherever it read the config. Degrade to using the legacy path and say so;
  never refuse to operate because migration failed.

### Deferred Ideas (OUT OF SCOPE)

- Cleaning up entire stale install DIRECTORIES (not just their configs) — that is the plugin
  manager's business, not this plugin's.
- Any migration of the cost-rate table or other shipped config; those are package data, not
  operator state, and belong with the version.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PLUGIN-02 | Config setup is a one-time operator step | The durable-home contract (verified below) plus a version-independent write path means "once" now genuinely means once across updates, not once per version. |
| PLUGIN-03 | Refuse in plain language, name what's broken and who fixes it, degrade rather than total-fail | The recommended write pattern (temp-file + `os.replace`) and resolution-order fallback chain mean an unwritable durable home degrades to the legacy path per CONTEXT.md's discretion clause, never a hard refusal. |
| STATUS-05 | Dashboard Artifact republishes to the same URL across a new conversation | Currently silently false — verified 2026-08-04, no install directory on this machine holds a `state/` folder. The identical durable-home + migration treatment for `artifact_store.DEFAULT_STATE_PATH` is what makes this requirement true again. |
| Out-of-Scope: "Operator-run commands, scripts, or config files … Terminal instructions to the operator are a requirement failure" | The migration must be silent and automatic; `initialize` only reports, never instructs a manual copy. | The resolution-time migration (not `initialize`-time) is what satisfies this — see Locked Decision 1. |

</phase_requirements>

## Architectural Responsibility Map

This phase touches exactly one tier: the plugin's own local filesystem resolution logic,
running as a Python subprocess launched by the Bash tool from within a Claude Code / Claude
Desktop session (or, for the unattended sweep, from cron). There is no browser, no
server-rendered page, no API tier, and no database — the "storage" here is two small JSON
files on the operator's own machine.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Config path resolution (env var → durable home → legacy → sibling scan) | Client / Local Filesystem (`durable_paths.py`) | — | Pure path logic, no I/O side effects beyond reads; must be identical for both consumers (D-1 discretion). |
| One-time credential migration | Client / Local Filesystem | — | A local file copy + chmod + verify + delete-old, triggered from `config_gate.load_config()` and `artifact_store.state_path()`. No network call is involved at any point. |
| `initialize` path reporting | Client / Local Filesystem (`init_check.py`) | — | Read-only consumer of the same resolver; adds one line of output, no new resolution logic. |
| Dashboard-pointer durability (STATUS-05) | Client / Local Filesystem (`artifact_store.py`) | — | Same resolver, second file. The dashboard Artifact itself is a Claude-hosted resource reached over the network elsewhere in the codebase (Phase 27); this phase only moves the local pointer file that tracks its id. |

**Why this matters for planning:** every task in this phase's plan is a filesystem/path-logic
task. There is no wave that needs a "backend" or "frontend" designation — the plan-checker's
tier-correctness check should find nothing to flag here, and a task proposing a network call
or a backend/n8n edit is out of scope by the phase boundary in CONTEXT.md.

## Research Findings

### 1. Is the durable-home path a documented contract? — VERIFIED, not merely observed

`${CLAUDE_PLUGIN_DATA}` is a first-class, documented Claude Code environment variable,
distinct from `${CLAUDE_PLUGIN_ROOT}`. From the official Claude Code plugins reference
(`code.claude.com/docs/en/plugins-reference`, section "Persistent data directory"),
fetched and quoted verbatim 2026-08-04:

> "The `${CLAUDE_PLUGIN_DATA}` directory resolves to `~/.claude/plugins/data/{id}/`, where
> `{id}` is the plugin identifier with characters outside `a-z`, `A-Z`, `0-9`, `_`, and `-`
> replaced by `-`. For a plugin installed as `formatter@my-marketplace`, the directory is
> `~/.claude/plugins/data/formatter-my-marketplace/`."

> "`${CLAUDE_PLUGIN_DATA}` [is a] Persistent directory that survives plugin updates, created
> on first reference" — [used for] "Installed dependencies such as `node_modules` or Python
> virtual environments, generated code, and caches."

> "The data directory is deleted automatically when you uninstall the plugin from the last
> scope where it is installed. ... The CLI deletes by default; pass `--keep-data` to preserve
> it."

`[VERIFIED: code.claude.com/docs/en/plugins-reference]`

This plugin's own id, read directly from the harness's install manifest on this machine
(`~/.claude/plugins/.install-manifests/operator-claude-plugin@lightning-visuals-operator.json`,
`pluginId` field, read 2026-08-04):

```
"pluginId": "operator-claude-plugin@lightning-visuals-operator"
```

Applying the documented substitution rule (`@` → `-`) gives exactly
`operator-claude-plugin-lightning-visuals-operator` — the identical string CONTEXT.md inferred
from sibling directory names. `[VERIFIED: ~/.claude/plugins/.install-manifests/operator-claude-plugin@lightning-visuals-operator.json]`

This machine's own `~/.claude/plugins/data/` directory was also inspected directly (2026-08-04):
14 sibling directories exist for other installed plugins (`caveman-caveman`,
`claude-mem-thedotmack`, `security-guidance-claude-plugins-official`, `ponytail-ponytail`,
`vercel-claude-plugins-official`, and nine `*-inline`/marketplace-named others), every one of
them **empty** (zero files). No directory exists yet for
`operator-claude-plugin-lightning-visuals-operator` — consistent with "created on first
reference": nothing in this plugin's `plugin.json` currently references
`${CLAUDE_PLUGIN_DATA}` in a hook, MCP server, or monitor config, so the harness has never had
occasion to create it. `[VERIFIED: local filesystem inspection, 2026-08-04]`

**Implication for the plan — do not blindly rely on the OS environment variable being
present.** The docs state the three path variables are "exported as environment variables to
hook processes and to MCP and LSP server subprocesses" and separately substituted inline in
"Skill and agent content ... anywhere the placeholder appears." Neither category covers a
plain `python3 scripts/config_gate.py` command that appears in SKILL.md body text and is
executed by the Bash tool as an ordinary subprocess (not a hook, not an MCP/LSP server, and
the substitution table's "Skill and agent content" row governs literal `${...}` text
*rendered into the skill's markdown before the model reads it* — it does not establish that
the variable exists in the environment of a subprocess the model later launches via Bash).
There is no first-hand evidence in the fetched docs that `CLAUDE_PLUGIN_DATA` is present in
`os.environ` for a script invoked this way. `[ASSUMED: absence, not directly tested this
session — see Open Questions]`

Given that, `durable_paths.py` should read `os.environ.get("CLAUDE_PLUGIN_DATA")` first (free,
harness-authoritative when present, and forward-compatible if the harness starts exporting it
more broadly) and fall back to computing the path directly via the documented formula when
absent — which will be the common case for this plugin's script-invocation pattern. This is
not a contradiction of CONTEXT.md's decision to keep an env override and legacy fallback —
`CLAUDE_PLUGIN_DATA` is a *third*, harness-level input, layered underneath the durable-home
constant in the existing 5-step resolution order, not a replacement for the admin-facing
`LV_OPERATOR_CONFIG` escape hatch.

### 2. Does the harness create the directory, or must the plugin?

**The plugin must create it.** "Created on first reference" describes the harness's own
lazy-creation behavior when `${CLAUDE_PLUGIN_DATA}` is *resolved by the harness* (i.e.,
substituted into a hook/MCP/LSP config field or into rendered skill text). It says nothing
about a script the harness merely launches independently later constructing the same path
itself and expecting it to already exist. The empirical evidence above (14 other plugins'
data directories are empty, and this plugin currently has none at all despite months of use)
is consistent with the interpretation that nothing has triggered harness-side creation for
this plugin, and is not proof either way for what happens on first reference in a component
type this plugin doesn't use.

**Recommendation, HIGH confidence regardless of which is true:** the migration/save code path
must call `target.parent.mkdir(parents=True, exist_ok=True)` defensively before writing,
exactly as `artifact_store.save()` already does today for its own (pre-Phase-33) path
(`artifact_store.py:111`, `[VERIFIED: operator-claude-plugin/scripts/artifact_store.py:111]`,
quoted: `target.parent.mkdir(parents=True, exist_ok=True)`). This is a one-line, already-proven
pattern in this codebase; no new risk.

### 3. Safe-write pattern for a 0600 credential file

Two candidate stdlib patterns, both avoiding a window at default (world/group-readable)
permissions:

**A. `os.open` with `O_CREAT | O_EXCL`, mode `0o600`, then write.**
```python
fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as f:
    f.write(content)
```
Mode is atomic from creation (no window at default perms) — but content is NOT atomic: a
process killed between `os.open` and the write leaves a zero-byte, correctly-permissioned
file sitting at the durable path. Because CONTEXT.md's resolution order treats "durable home
resolves" (a file existing there) as terminating the search *before* any content is read, a
truncated file from a crashed prior migration would be picked up, fail the caller's
`n8n_url` presence check, and the operator would see a confusing "not configured" error at a
path that looks migrated — worse than not migrating at all. `O_EXCL` alone is not
recommended for this reason, despite it also conveniently doubling as an idempotence check
(`FileExistsError` on a second run).

**B. Write to a temp file in the same directory (mode 0600, guaranteed by `tempfile.mkstemp`
on POSIX per the Python stdlib docs), then `os.replace()` to the final path.**
```python
def _atomic_write_0600(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        os.chmod(tmp_name, 0o600)  # defensive — mkstemp already defaults to 0600 on POSIX
        with os.fdopen(fd, "w") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)  # atomic within one filesystem
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise
```
`[CITED: docs.python.org/3/library/tempfile.html — mkstemp is documented to create the file
"readable and writable only by the creating user ID" on POSIX]`

**Recommendation: pattern B.** It closes both the mode window AND the content window — the
final path is either absent, or present complete and `0600`; nothing in between is ever
observable. `os.replace()`'s atomicity guarantee holds because the temp file is created with
`dir=str(path.parent)`, i.e. on the same filesystem as the destination — this is the one
constraint that must not be violated (do not create the temp file under a different mount, a
system temp dir, or a different `Path.home()` resolution than the target). State this
constraint explicitly as a code comment at the call site; it is the one thing that silently
breaks the guarantee if refactored carelessly later.

Idempotence itself does **not** need to be enforced inside this write helper — it falls out
of the resolution order for free. Once the durable home holds a file, resolution stops at
step 3 and never re-enters the sibling-scan/migration branch; the write helper only ever runs
from the migration branch, which by construction only executes when step 3 found nothing.

### 4. Sibling-scan version ordering without `packaging`

Confirmed live on this machine (`~/.claude/plugins/cache/lightning-visuals-operator/operator-claude-plugin/`, `[VERIFIED: local filesystem, 2026-08-04]`): three sibling directories,
`0.1.0`, `0.6.1`, `0.6.2` (plus the current install's own directory, presently `0.6.2` — the
target release is `0.7.0` per CONTEXT.md's header, so by the time this phase ships there will
be a fourth). All three-segment dotted-integer strings; no prerelease suffixes, no build
metadata, no leading zeros beyond the literal `0.1.0`.

`requirements.txt` confirms no version-parsing dependency is available: `openpyxl`,
`requests`, `PyYAML` only. `[VERIFIED: operator-claude-plugin/requirements.txt]`

**Recommended parse — tuple-of-ints with a documented non-numeric fallback:**
```python
_VERSION_DIR_RE = re.compile(r"^\d+(\.\d+)*$")

def _version_key(dirname: str) -> tuple:
    """Sorts numeric dotted-version strings correctly; a directory that fails the format
    check is filtered out before this is ever called, so this function's fallback branch
    exists only to make comparisons total (never raise), not to rank non-versions sensibly."""
    return tuple(int(p) for p in dirname.split("."))

def newest_sibling_version(cache_root: Path, exclude: Path) -> Path | None:
    candidates = [
        d for d in cache_root.iterdir()
        if d.is_dir() and d.resolve() != exclude.resolve() and _VERSION_DIR_RE.match(d.name)
    ]
    return max(candidates, key=lambda d: _version_key(d.name), default=None)
```

Edge cases to handle explicitly (and to cover in tests):

- **Filter before sorting, don't try to make the sort tolerant.** A directory name that
  doesn't match `^\d+(\.\d+)*$` (a stray `.DS_Store`, a future non-version scratch directory,
  or a prerelease suffix like `0.7.0-rc1` if that convention is ever adopted) must be excluded
  from the candidate set entirely, not passed through a tuple key that mixes `int` and `str` —
  Python 3 raises `TypeError` comparing `int` to `str`, which would crash the scan on the
  first non-conforming sibling rather than skipping it gracefully.
- **Always exclude the current install** (`exclude=` the resolved `PLUGIN_ROOT`, i.e. the
  directory `config_gate.py` itself lives under) from the candidate set, regardless of what
  its version-number comparison would say. This is a correctness invariant independent of
  ordering: the current install's own legacy config is already checked at resolution-order
  step 4, before the sibling scan (step 5) ever runs; the scan finding and "migrating from"
  itself would be a no-op at best and a confusing self-referential code path at worst.
- **Unequal segment counts** (`"0.7"` vs `"0.7.0"`) sort inconsistently with tuple comparison
  — `(0, 7) < (0, 7, 0)` is `True` in Python even though the versions are semantically equal.
  Not observed in this project's actual directory names (all three current siblings are
  three-segment), so this is a documented limitation rather than a fix, unless the plan wants
  to zero-pad to a fixed width defensively — cheap to add, not required by any observed data.
- **Pick the newest sibling whose config file actually exists and is readable**, not merely
  the newest-named directory — `newest_sibling_version()` above only ranks directories; the
  caller must still check `candidate / "config" / "operator.local.json"` exists before treating
  it as the migration source, and move to the next-newest candidate if not (an install
  directory can exist without ever having held a config, e.g. `0.1.0` if the operator set up
  config only after upgrading past it).
- **Old install directories are not permanent.** The official docs state (plugin-root section,
  not the persistent-data section, but the same pruning behavior applies to plugin cache
  directories generally per this project's own CHANGELOG evidence of directory-per-version
  layout): *"The previous version's directory remains on disk for about two weeks after an
  update before cleanup, but treat it as ephemeral."* `[CITED: code.claude.com/docs/en/plugins-reference]`
  This is supporting evidence — not new information CONTEXT.md needs, since D-1 already
  chose resolution-time migration over `initialize`-time for the same underlying reason — but
  it quantifies the window: a fresh 0.7.0 install that goes unused for over two weeks risks
  its sibling scan finding nothing, which is a legitimate "nothing to migrate" case the plan
  should treat as a normal (not exceptional) sibling-scan outcome.

### 5. Testing an update without performing one

`tests/test_config_gate.py::_run_cli` (`[VERIFIED: operator-claude-plugin/tests/test_config_gate.py:108-130]`,
quoted key lines below) already runs `config_gate.py` as a real subprocess against an isolated,
throwaway plugin root:

```python
def _run_cli(config_json, tmp_path):
    real = Path(__file__).resolve().parent.parent / "scripts" / "config_gate.py"
    root = tmp_path / "plugin"
    (root / "scripts").mkdir(parents=True)
    (root / "config").mkdir()
    shutil.copyfile(real, root / "scripts" / "config_gate.py")
    if config_json is not None:
        (root / "config" / "operator.local.json").write_text(json.dumps(config_json))
    return subprocess.run([sys.executable, "config_gate.py"], capture_output=True,
                          text=True, cwd=str(root / "scripts"))
```

Its own docstring names the exact historical failure this phase must not repeat: *"the first
attempt silently read the operator's REAL config because `runpy` discarded the path
override."* `[VERIFIED: operator-claude-plugin/tests/test_config_gate.py:108-118]` The lesson
generalizes directly to the durable-home path: a test that monkeypatches `Path.home` at the
Python-object level, or that imports `durable_paths` in-process and patches an attribute on
it, is vulnerable to the same class of bug if `config_gate.py`'s `__main__` block ever runs via
`runpy` or a fresh subprocess that re-imports the module — the isolation must hold at the
**process boundary**, not the Python-object boundary, for the entrypoint-level test to mean
anything (this is also this phase's Roadmap success criterion 5, verbatim: *"Every path is
pinned at the ENTRYPOINT layer against an isolated plugin root ... Asserting on the resolver
function alone is what shipped the 0.6.1 and 0.6.2 defects in opposite directions"*).

**Recommended extension, reusing `_run_cli` rather than reinventing it:**

1. **Extend `_run_cli` to accept an explicit `env` override**, defaulting to a minimal dict
   rather than inheriting the real process environment wholesale — pass `env={"PATH": ...,
   "HOME": str(fake_home), **overrides}` explicitly to `subprocess.run`, never
   `{**os.environ, ...}`. This is the one change to the existing harness; every other call
   site keeps working unchanged since `env=None` can default to today's behavior.
2. **Point `HOME` at a `tmp_path` directory.** `Path.home()` on POSIX resolves via
   `os.path.expanduser("~")`, which honors `$HOME` when set — no code change to
   `durable_paths.py` is needed to make it testable; only the subprocess's environment needs
   redirecting. This mirrors the project's own established pattern (process-boundary
   isolation) rather than introducing a new one.
3. **Build the cache layout the sibling scan expects**, mirroring the real structure evidenced
   on this machine: `tmp_path/cache/<marketplace>/<plugin>/<version>/scripts/config_gate.py`
   (and the same for `durable_paths.py`, which `config_gate.py` will import — copy both files,
   not just one, since `_run_cli`'s current single-file copy assumption
   ("it imports nothing from its siblings") will no longer hold once a shared helper exists).
   Create at least two version directories — an older one holding a legacy
   `config/operator.local.json`, and the "current" one the CLI is actually invoked from (no
   local config) — to exercise the sibling scan.
4. **Assert, across (at minimum) three test cases:**
   - *Migration happens*: durable home is empty beforehand; after one CLI run, the durable
     home holds the migrated file, its mode is `0o600` (`stat.S_IMODE(path.stat().st_mode)
     == 0o600`), and it contains the same `n8n_url`/`webhook_secret` values the sibling held.
   - *Idempotence*: run the CLI a second time with the same fake `HOME`; assert the durable
     file's `st_mtime` is byte-for-byte unchanged (capture it before the second run, compare
     after) and that nothing in `stdout`/`stderr` mentions migration — CONTEXT.md's silent-
     no-op requirement is directly testable this way.
   - *Simulated version bump*: after the first run has migrated into the durable home, copy
     the CLI files into a THIRD version directory (representing the next update) with no local
     config of its own, and run from there. Assert it resolves via the durable home (step 3)
     directly — no sibling scan, no second migration, no touch to the now-two-versions-old
     sibling's dead config beyond whatever the verify-then-delete discretion decided in step 1.
5. **Old-config removal, if implemented, needs its own explicit assertion**: verify-then-delete
   means the test should assert the sibling's original file is gone (or deliberately still
   present, depending on which discretion choice the plan makes) only *after* confirming the
   durable copy is byte-identical and readable — sequence the assertions to mirror the
   production sequence, so a test bug can't accidentally pass by asserting deletion before
   confirming the copy succeeded.

## Standard Stack

No new dependency of any kind. Everything needed — `os`, `pathlib`, `tempfile`, `re`, `stat`,
`contextlib` — is Python stdlib, already available under the existing
`operator-claude-plugin/requirements.txt` (`openpyxl`, `requests`, `PyYAML`) plus stdlib. This
matches the phase's explicit constraint ("No new runtime dependencies") and this codebase's
existing `Don't Hand-Roll` posture toward avoiding unrequested libraries for local file I/O.

## Package Legitimacy Audit

Not applicable — no external package is added, upgraded, or removed by this phase.

## Architecture Patterns

### System Architecture Diagram

```
                         (interactive session)                (cron, no session)
                                  |                                    |
                    SKILL.md tells Claude to run          lv-sweep-run.sh invokes
                    `python3 scripts/config_gate.py`       sweep_entry.py directly
                    via the Bash tool                       (bare subprocess, no
                                  |                           Claude Code tool layer)
                                  v                                    v
                    +----------------------------------------------------------+
                    |             config_gate.load_config(path=None)           |
                    |          artifact_store.state_path() / load()            |
                    +----------------------------------------------------------+
                                  |
                                  v
                    +----------------------------------------------------------+
                    |                    durable_paths.py                     |
                    |  resolve_config_path() / resolve_state_path()           |
                    |                                                          |
                    |  1. explicit path arg (tests)          <-- highest       |
                    |  2. LV_OPERATOR_CONFIG env var                          |
                    |  3. durable home (CLAUDE_PLUGIN_DATA or computed)       |
                    |  4. PLUGIN_ROOT/config/... (legacy, same install)       |
                    |  5. newest sibling install's config --> MIGRATE to (3)  |
                    +----------------------------------------------------------+
                        |find at 1/2/3/4|          |nothing found until 5|
                        v                                     v
                  return path, no I/O              read sibling file
                  beyond existence check                    |
                                                              v
                                                  _atomic_write_0600() into (3)
                                                  (tempfile in same dir + os.replace)
                                                              |
                                                              v
                                                  verify durable copy readable
                                                              |
                                                              v
                                                  remove sibling's copy
                                                  (never the current install's own)
                                                              |
                                                              v
                                                  return durable path

                    +----------------------------------------------------------+
                    |              init_check.py / initialize skill            |
                    |  reads the SAME resolver (read-only), reports the        |
                    |  REAL resolved path; never itself triggers migration     |
                    +----------------------------------------------------------+
```

### Recommended Project Structure

```
operator-claude-plugin/
├── scripts/
│   ├── durable_paths.py      # NEW — shared resolver + migration, both files import it
│   ├── config_gate.py        # imports durable_paths; DEFAULT_CONFIG_PATH becomes a call
│   ├── artifact_store.py     # imports durable_paths; DEFAULT_STATE_PATH becomes a call
│   └── init_check.py         # reads durable_paths' resolved path for reporting only
└── tests/
    ├── test_config_gate.py   # _run_cli extended with an env= override
    └── test_durable_paths.py # NEW — the version-key parser, atomic-write helper, unit-level
```

### Pattern 1: Shared resolver, both consumers import it

**What:** One module (`durable_paths.py`) owns `durable_dir()`, `resolve_config_path()`, and
`resolve_state_path()`. `config_gate.py` and `artifact_store.py` each call the matching
resolver instead of hardcoding `DEFAULT_CONFIG_PATH`/`DEFAULT_STATE_PATH` as module-level
constants.
**When to use:** Any time two files need identical resolution-order logic — CONTEXT.md's own
"Specific Ideas" section names this explicitly as the way to avoid a second source of truth.
**Example:**
```python
# durable_paths.py
import os
from pathlib import Path

PLUGIN_ID = "operator-claude-plugin-lightning-visuals-operator"  # [VERIFIED, see Finding 1]

def durable_dir() -> Path:
    env = os.environ.get("CLAUDE_PLUGIN_DATA")
    if env:
        return Path(env)
    return Path.home() / ".claude" / "plugins" / "data" / PLUGIN_ID
```
`[VERIFIED: code.claude.com/docs/en/plugins-reference — formula]` for the fallback branch;
the env-var-first check is a defensive addition this research recommends, not something the
docs require.

### Anti-Patterns to Avoid

- **Hardcoding the durable-home path independently in both `config_gate.py` and
  `artifact_store.py`.** CONTEXT.md's own discretion note calls this out; it is exactly the
  "second-source-of-truth pattern this milestone avoids everywhere else."
- **Relying on `O_CREAT` alone for the migrated file's atomicity.** See Finding 3 — it leaves a
  content-partial-write window even though the mode bits are correct from creation.
- **Testing the resolver function in-process instead of the CLI subprocess.** This phase's own
  Roadmap success criterion 5 states this explicitly as the failure mode to avoid, citing the
  0.6.1/0.6.2 defect history.

## Common Pitfalls

### Pitfall 1: A Bash-tool "sensitive location" permission prompt on the first migration write

**What goes wrong:** A closed (labeled "not planned") Claude Code GitHub issue
(anthropics/claude-code#41156) reports that writes into `~/.claude/plugins/data/<plugin-id>/`
trigger a confirmation prompt from the permission system — *"This file is in a sensitive
location"* — even with `bypassPermissions: true` or `--dangerously-skip-permissions`, and even
though the harness itself designates that exact directory as the pre-authorized plugin-state
location via `CLAUDE_PLUGIN_DATA`. The reporter's attempted workaround (a `PreToolUse` hook
allowlisting the path) did not suppress it, because the check reportedly runs at a layer
`PreToolUse` hooks don't intercept.
**Why it happens:** A framework-level inconsistency between where the plugin-data contract
says state should live and where the permission layer treats writes as needing confirmation —
per the issue, still unresolved upstream as of its "closed, not planned" status.
**How to avoid:** This is not fully avoidable from plugin code — it is host-permission-layer
behavior, not something `durable_paths.py` can suppress. What the plan CAN do: (1) confirm the
degrade-never-refuse posture already required by CONTEXT.md's discretion clause covers this
case too — if the migration write stalls on a permission prompt rather than raising a catchable
Python exception, the plugin cannot detect or recover from that programmatically, so the
resolution-order fallback (keep using the legacy path) needs to be what an operator
experiences if they decline or ignore the prompt, not a hang; (2) treat this as a live-check
item for a runbook-style verification pass during or after execution, consistent with how
every other Claude-Code-host uncertainty in this milestone (the RB-1 through RB-9 runbooks) was
resolved by observation rather than by more research. `[CITED: github.com/anthropics/claude-code/issues/41156]`
**Warning signs:** An interactive session where the migration appears to hang with no error
and no progress after the operator's first post-update contact-upload or status check —
distinguishable from a genuine slow filesystem by checking whether a confirmation dialog is
pending in the transcript/UI.

### Pitfall 2: Comparing an `int` and a `str` in the version sort

**What goes wrong:** A naive `sorted(dirs, key=lambda d: tuple(int(p) for p in d.split(".")))`
raises `ValueError` (from the failed `int()` call) or, if guarded loosely, ends up comparing an
`int` to a `str` inside a tuple comparison, which raises `TypeError` in Python 3 — either way,
one malformed sibling directory name crashes the entire scan instead of being skipped.
**Why it happens:** Directory listings under a plugin's cache root are not guaranteed to
contain only version-looking names — see Finding 4.
**How to avoid:** Filter candidates with a regex (`^\d+(\.\d+)*$`) BEFORE sorting, so the sort
key function is only ever called on strings already known to parse cleanly.
**Warning signs:** A `ValueError`/`TypeError` traceback surfacing through `config_gate.py`'s
`__main__`, which the existing `ConfigError`-wrapping discipline in that file does not catch
because it's a different exception class entirely — this would be a genuine regression against
the "refuse in plain language, never a raw traceback" contract (D-06, PLUGIN-03).

### Pitfall 3: Migrating from — or deleting — the wrong install's config

**What goes wrong:** The sibling scan finds and migrates from an old version's config, then
(per the verify-then-delete discretion) deletes it — but if the exclusion of the CURRENT
install (`PLUGIN_ROOT`) from the candidate set is implemented by name/version-string
comparison rather than by resolved-path identity, a coincidental version-string collision (not
possible today given the cache's own directory-per-version uniqueness, but worth guarding
against defensively) or a refactor that changes how `PLUGIN_ROOT` is computed could cause the
current install's own legacy config to be deleted by the "sibling" code path instead of being
left alone by the step-4 same-install path.
**Why it happens:** Two separate code paths (step 4's same-install check, step 5's sibling
scan) both touch config files; if they don't share one unambiguous exclusion check, they can
disagree about which directory is "current."
**How to avoid:** Exclude `PLUGIN_ROOT` from the sibling candidate set by resolved-path
equality (`d.resolve() != PLUGIN_ROOT.resolve()`), computed once, and never delete anything at
a path equal to the current install's own config path — assert this invariant directly in a
test rather than relying on it holding by construction alone.
**Warning signs:** A test that only exercises a single sibling directory would never catch
this — the test suite needs at least one case with the current install ALSO holding a (valid,
untouched) legacy config alongside an older sibling's config, to prove the current install's
copy is left alone even when the sibling scan runs.

## Code Examples

### Resolution order, mirroring the shape CONTEXT.md specifies for both files

```python
# durable_paths.py
def resolve_config_path(explicit=None) -> Path:
    if explicit is not None:
        return Path(explicit)
    env_override = os.environ.get("LV_OPERATOR_CONFIG")
    if env_override:
        return Path(env_override)

    durable = durable_dir() / "operator.local.json"
    if durable.exists():
        return durable

    legacy = PLUGIN_ROOT / "config" / "operator.local.json"
    if legacy.exists():
        return legacy

    migrated = _migrate_from_newest_sibling("operator.local.json", durable)
    if migrated is not None:
        return migrated

    return legacy  # nothing found anywhere; return the legacy default so the
                    # existing "file not found" ConfigError message still names
                    # a sensible path
```
This shape is illustrative of the resolution order in CONTEXT.md's Contracts-to-Honor section
(explicit → env → durable → legacy → sibling-scan-and-migrate) — the exact function
decomposition (one function vs. several) is left to the plan/implementation, not prescribed
here.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `CLAUDE_PLUGIN_DATA` is NOT present in `os.environ` for a plain `python3 scripts/...` subprocess launched by the Bash tool from SKILL.md text (as opposed to a hook/MCP/LSP subprocess, which the docs confirm DO receive it) | Finding 1 | If wrong (the variable IS present), the code still works correctly — the env-var-first check in `durable_dir()` simply becomes the common path instead of the fallback path. No behavior change needed either way; this assumption only affects which branch is more heavily exercised, not correctness. Low risk. |
| A2 | The GitHub-issue-reported "sensitive location" permission prompt (Pitfall 1) still reproduces on the current Claude Code version relevant to this operator's install, given the issue is closed as "not planned" and dated from an unknown Claude Code version | Common Pitfalls, Pitfall 1 | If the behavior has since changed (fixed or worsened), the plan's mitigation (degrade gracefully, verify live) still applies without modification — a live check during execution/verification resolves this regardless of which way it goes. Medium risk to plan sequencing (a live-check task should exist), low risk to design correctness. |
| A3 | Old plugin-cache version directories (siblings) are pruned roughly two weeks after an update, per the docs' statement about `${CLAUDE_PLUGIN_ROOT}`'s prior-version retention — assumed to apply the same way to the cache directories the sibling scan reads | Finding 4 | If pruning happens sooner or is disabled/different for this project's marketplace-clone-based install flow (evidenced by this project's own CHANGELOG describing manual `git fetch --reset --hard` refresh steps, which may interact with pruning differently than a marketplace-registry-managed install), the sibling scan could either find nothing (safe — normal "nothing to migrate" case) or find a stale directory later than expected (safe — resolution order still picks the newest valid one). No correctness risk either way, only a note that the exact retention window on THIS project's install mechanism (manual clone refresh, not registry auto-update) may differ from the documented registry-plugin retention period. |

## Open Questions

1. **Does the Bash-tool "sensitive location" permission prompt (Pitfall 1) actually fire for
   this plugin's migration write, on this operator's Claude Code version?**
   - What we know: A GitHub issue reports it does, for writes into
     `~/.claude/plugins/data/<id>/`, closed as "not planned" by the upstream project.
   - What's unclear: Whether it reproduces here, whether it blocks (hangs pending
     confirmation) or is skippable, and whether it differs between an interactive session and
     any other invocation path this plugin uses.
   - Recommendation: Add a live-check step to this phase's own execution/verification —
     consistent with this project's established pattern of resolving Claude-Code-host
     uncertainties via a runbook-style observed check (RB-1 through RB-9) rather than further
     research. Not a blocker for planning or building the code — the degrade-never-refuse
     design already required by CONTEXT.md's discretion clause is the correct response
     regardless of the answer.

2. **Is `CLAUDE_PLUGIN_DATA` actually exported into the environment of a `Bash`-tool-launched
   subprocess, contrary to what the docs' process-type table implies?**
   - What we know: The docs explicitly name three process types that receive it (hook, MCP,
     LSP subprocesses); a `python3 scripts/...` command in SKILL.md body text is none of
     those three when executed via the general-purpose Bash tool.
   - What's unclear: Whether Claude Code injects it more broadly into every tool-launched
     subprocess's environment as a convenience, undocumented.
   - Recommendation: Not worth a dedicated live check — the code path is correct either way
     (see Assumption A1). If curious during execution, one `env | grep CLAUDE_PLUGIN` inside a
     script invoked exactly the way SKILL.md invokes it would settle this in seconds; low
     priority.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python stdlib (`os`, `pathlib`, `tempfile`, `re`, `stat`) | All of this phase | ✓ | matches repo's existing Python (3.14 per `tests/__pycache__` filenames observed) | — |
| `${CLAUDE_PLUGIN_DATA}` / `CLAUDE_PLUGIN_ROOT` harness contract | Durable-home resolution | Documented, version unspecified as of when `CLAUDE_PLUGIN_DATA` was added (a web search result referenced "v2.1.78") | — | `durable_paths.py` computes the same path directly without relying on the env var being present — see Finding 1 |
| Write access to `~/.claude/plugins/data/` | Migration | Not independently verified this session beyond the empty-but-present sibling directories observed | — | Resolution order falls back to legacy `PLUGIN_ROOT/config/` path per CONTEXT.md's degrade-never-refuse discretion clause |

**Missing dependencies with no fallback:** none identified.

**Missing dependencies with fallback:** an unwritable durable home degrades to the legacy
same-install path, per CONTEXT.md's explicit discretion instruction — already covered by the
resolution order itself, not a gap this research needs to add anything for.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (no `pytest.ini`/`pyproject.toml` found under `operator-claude-plugin/`; run from the plugin directory, `tests/conftest.py` puts `scripts/` on `sys.path`) |
| Config file | none — see `tests/conftest.py` for the `sys.path` shim and the autouse `no_network` guard |
| Quick run command | `.venv/bin/python -m pytest operator-claude-plugin/tests/test_config_gate.py operator-claude-plugin/tests/test_artifact_store.py operator-claude-plugin/tests/test_durable_paths.py -x` (per `.planning` memory: use `.venv/bin/python -m pytest`, not a bare `pytest` invocation — the system Python lacks the test deps) |
| Full suite command | `.venv/bin/python -m pytest operator-claude-plugin/tests/ -x` |

### Phase Requirements → Test Map

| Req / Criterion | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| Roadmap criterion 1 (config resolution order + free sibling migration) | 5-step resolution order resolves correctly at every priority level; sibling scan migrates on a simulated update | entrypoint (subprocess) | `pytest tests/test_config_gate.py -k durable -x` | ❌ Wave 0 — extend `_run_cli`, add new test functions |
| Roadmap criterion 2 (dashboard pointer gets identical treatment) | `artifact_store` resolves/migrates via the same `durable_paths` module | entrypoint (subprocess) | `pytest tests/test_artifact_store.py -k durable -x` | ❌ Wave 0 — `test_artifact_store.py`'s existing tests use direct `path=` args (unit-level); a subprocess-level entrypoint test needs to be added, mirroring `_run_cli`'s pattern applied to `artifact_store.py`'s own `__main__` |
| Roadmap criterion 3 (0600 mode, verify-then-delete) | Migrated file mode is `0o600`; old copy removed only after verified readable; current install's own copy never removed | unit + entrypoint | `pytest tests/test_durable_paths.py -x` (unit) plus the subprocess assertions in extended `_run_cli` tests | ❌ Wave 0 — new file |
| Roadmap criterion 4 (`initialize` reports real path, silent unless migration happened) | `init_check.py` output names the durable path; a no-op run produces no migration language | unit | `pytest tests/test_init_check.py -x` (extend existing file) | Existing file, needs new test cases |
| Roadmap criterion 5 (entrypoint-layer pinning) | Every assertion above is driven through the CLI subprocess, not the bare resolver function | entrypoint (subprocess) | (covered by the above — this criterion is a testing-methodology constraint on how the other tests are written, not a separate behavior) | — |
| Roadmap criterion 6 (no regression, no secret leak) | Legacy same-install path still resolves; full suite stays green; no secret in any output | regression + unit | `pytest tests/ -x` (full suite) plus generalizing `test_no_configerror_message_ever_contains_the_secret_value`-style assertions to the migration path | Existing pattern — extend, don't replace |

### Sampling Rate

- **Per task commit:** the targeted quick-run command above (durable-paths + config_gate +
  artifact_store test files only)
- **Per wave merge:** full plugin suite (`operator-claude-plugin/tests/`)
- **Phase gate:** full plugin suite green, plus a manual/observed check of Open Question 1
  (the permission-prompt risk), before this phase is marked complete — consistent with how
  Phases 27–32 in this same milestone gated on a runbook (RB-4, RB-7, RB-8, RB-9) rather than
  automated tests alone for host-boundary behavior.

### Wave 0 Gaps

- [ ] `operator-claude-plugin/scripts/durable_paths.py` — the shared resolver module itself;
      does not exist yet.
- [ ] `operator-claude-plugin/tests/test_durable_paths.py` — unit tests for the version-key
      parser and the atomic-write helper, independent of the subprocess-level entrypoint tests.
- [ ] Extension of `tests/test_config_gate.py::_run_cli` to accept an `env=` override and a
      multi-version-directory cache layout — the current signature only takes `config_json`
      and `tmp_path`.
- [ ] A parallel subprocess-level entrypoint test for `artifact_store.py`'s own `__main__` —
      today's `test_artifact_store.py` tests call `load()`/`save()` directly with an explicit
      `path=`, which is exactly the unit-level testing style this phase's own criterion 5
      warns is insufficient on its own for the resolver's default-path behavior.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V6 Cryptography / Secrets Storage | yes | File-level access control (`0600`) on the two secrets this file holds (`webhook_secret`, `n8n_api_key`) — no encryption at rest is introduced or required by this phase; matches the existing `.gitignore`d, plaintext-on-local-disk posture of `operator.local.json` today. This phase's job is narrowing the file-mode window during migration, not changing the storage model. |
| V5 Input Validation | yes (pre-existing, unchanged) | `config_gate.load_config()`'s existing JSON-parse + `n8n_url` scheme check is unchanged by this phase; the migrated file goes through the same validation once resolved to a path, no new parsing surface is introduced. |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Credential file left world/group-readable during a migration write | Information Disclosure | Atomic temp-file + `os.replace` write with `0600` from creation (Finding 3) — the pattern this research recommends. |
| Old install's credential copy left behind after migration | Information Disclosure | Verify-then-delete of the sibling's copy, per CONTEXT.md's discretion clause; never delete the CURRENT install's own copy (Pitfall 3). |
| Secret value leaking into a log line, refusal message, or test output during the migration path | Information Disclosure | Generalize the existing `test_no_configerror_message_ever_contains_the_secret_value` guard to cover migration-path output; the migration itself should never print the file's contents, only paths and booleans (mirrors `init_check.py`'s existing "never reads, accepts, prints or logs a secret" discipline). |

## Sources

### Primary (HIGH confidence)
- `code.claude.com/docs/en/plugins-reference` (official Claude Code documentation) —
  "Environment variables" and "Persistent data directory" sections, fetched and quoted
  verbatim 2026-08-04. Confirms `${CLAUDE_PLUGIN_DATA}` path formula and process-type export
  scope.
- `~/.claude/plugins/.install-manifests/operator-claude-plugin@lightning-visuals-operator.json`
  — this plugin's own harness-recorded `pluginId`, read directly, 2026-08-04.
- Local filesystem inspection of `~/.claude/plugins/data/`, `~/.claude/plugins/cache/`, and
  `~/.claude/plugins/marketplaces/lightning-visuals-operator/.claude-plugin/marketplace.json`
  on this machine, 2026-08-04.
- `operator-claude-plugin/scripts/config_gate.py`, `artifact_store.py`, `init_check.py`, and
  `tests/test_config_gate.py` — read in full this session.
- `docs.python.org/3/library/tempfile.html` — `mkstemp`'s documented POSIX file-mode guarantee.

### Secondary (MEDIUM confidence)
- `github.com/anthropics/claude-code/issues/41156` — "sensitive location" permission-prompt
  report for writes into `~/.claude/plugins/data/`. Closed as "not planned"; reproduction on
  this specific host/version not independently verified this session — see Open Question 1.

### Tertiary (LOW confidence)
- WebSearch result snippets (not independently fetched from a primary page) mentioning
  `CLAUDE_PLUGIN_DATA` being "added in v2.1.78" — used only as color for when the feature
  shipped, not relied on for any correctness claim in this research.

## Metadata

**Confidence breakdown:**
- Durable-home path contract (Finding 1): HIGH — verified against official docs and this
  machine's own install manifest, not inferred.
- Safe-write pattern (Finding 3): HIGH — stdlib-documented guarantees, no external dependency.
- Sibling-scan version parsing (Finding 4): HIGH — verified against this machine's actual
  directory names; edge cases are documented limitations, not unknowns.
- Testing approach (Finding 5): HIGH — directly extends an existing, read, verified harness in
  this codebase.
- Permission-prompt risk (Pitfall 1): MEDIUM — a real, cited report, but not independently
  reproduced this session; flagged as an Open Question with a recommended live-check rather
  than asserted as fact.

**Research date:** 2026-08-04
**Valid until:** ~30 days for the stdlib/local-codebase findings (stable); the
`CLAUDE_PLUGIN_DATA` contract and the GitHub issue status should be re-checked if this phase's
execution is delayed more than a few weeks, since both are Claude Code host-platform behaviors
that could change independently of this project.
