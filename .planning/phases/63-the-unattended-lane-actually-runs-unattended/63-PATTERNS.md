# Phase 63: The unattended lane actually runs unattended - Pattern Map

**Mapped:** 2026-09-02
**Files analyzed:** 6 (2 new, 4 modified/regenerated)
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| NEW shim (`/bin/sh`, durable home) | utility (launcher) | file-I/O (path resolution + exec) | `operator-claude-plugin/skills/backend-sweep/lv-sweep-run.sh` | role-match (same shell dialect, sibling script) |
| MODIFY `lv-sweep-run.sh` (staleness self-check) | utility (trigger wrapper) | request-response (loud banner/log) | itself, prior version (in-place extension) | exact |
| MODIFY `SWEEP-CRON-TEMPLATE.md` | config (docs/crontab line) | n/a | itself, prior version | exact |
| REUSE `durable_paths.py` version helpers | utility (path/version resolution) | file-I/O | itself — `_version_key`/`_newest_sibling_holding`/`durable_dir` already exist, call don't re-implement | exact |
| MODIFY `scripts/build_cloud_workflows.py` (judge model routing) | config/codegen (workflow builder) | transform (JS string generation) | itself — `_enrich_build_judge_request_js` / `_flag_const` (existing conditional-routing precedent: `applyCostCap`, Pass-3 branching in `_enrich_judge_gate_js`) | exact |
| NEW offline replay harness (model A/B verdict comparison) | test/script (oracle comparison) | batch (offline replay over stored fixtures) | `scripts/run_scoring_parity.py` (report-dict + verdict + exit-code shape) | role-match (closest existing "compare two answers over a sample, write JSON report" harness in repo) |

## Pattern Assignments

### NEW: durable-home launcher shim

**Analog:** `operator-claude-plugin/skills/backend-sweep/lv-sweep-run.sh` (76 lines, full file already read) + `operator-claude-plugin/scripts/durable_paths.py`

**Shebang/strictness convention** (`lv-sweep-run.sh` lines 1-2):
```sh
#!/bin/sh
set -u
```
Copy this exactly — `set -u` only (no `-e`; the script deliberately checks `$?` per-command so it can bannerand log instead of dying silently).

**Argument contract the shim must preserve** (`lv-sweep-run.sh` lines 6-11):
```
# Three positional arguments, in order: $1 the plugin root (the directory containing
# both scripts/ and skills/), $2 the python interpreter with this plugin's
# requirements.txt installed, $3 the log path.
```
The shim receives the SAME three args from cron (the crontab line is unchanged in shape — only the pinned path changes from `[plugin-root]/skills/backend-sweep/lv-sweep-run.sh` to the shim's own durable path). The shim's job is: resolve the newest install root, then `exec "$NEWEST_ROOT/skills/backend-sweep/lv-sweep-run.sh" "$NEWEST_ROOT" "$2" "$3"` — replacing `$1` with the resolved root, `exec`ing (not forking) so the shim adds zero process overhead and cron's PID tracking still points at the real work.

**Banner pattern to reuse verbatim** (`lv-sweep-run.sh` lines 13-15):
```sh
banner() {
    /usr/bin/osascript -e "display notification \"$1\" with title \"LV Backend Sweep\""
}
```

**Version resolution — do NOT reimplement, shell out to durable_paths.py's Python, or port `_version_key`/`_newest_sibling_holding` into shell.** `durable_paths.py` (`operator-claude-plugin/scripts/durable_paths.py`) already:
- `_VERSION_DIR_RE = re.compile(r"^\d+(\.\d+)*$")` (line 41) — the version-directory name filter
- `_version_key(name)` (lines 44-54) — correct dotted-version sort (`0.10.0` > `0.9.0`)
- `_newest_sibling_holding(relative)` (lines 84-119) — newest sibling excluding current install by **resolved-path equality**
- `durable_dir()` (lines 167-178) — resolves `${CLAUDE_PLUGIN_DATA}` or `~/.claude/plugins/data/<id>/`

D-63-04 mandates reuse. The shim (a `/bin/sh` script, per "the sweep path is deliberately LLM-free... a `/bin/sh` concern, not a Python-with-Anthropic one") should invoke the SAME python interpreter it's handed (`$2`) to run a tiny inline `-c` snippet that imports `durable_paths` and prints the newest install root — mirroring how `lv-sweep-run.sh` already shells out to python for JSON parsing (lines 37-44, `COUNT=$("$2" -c '...')`):
```sh
NEWEST_ROOT=$("$2" -c '
import sys
sys.path.insert(0, "'"$SHIM_INSTALLED_AT_PARENT_DIR"'")
from durable_paths import PLUGIN_ROOT, _newest_sibling_holding, _VERSION_DIR_RE, _version_key
import re
from pathlib import Path
cache_root = PLUGIN_ROOT.parent
candidates = [d for d in cache_root.iterdir() if d.is_dir() and _VERSION_DIR_RE.match(d.name)]
candidates.sort(key=lambda d: _version_key(d.name), reverse=True)
print(candidates[0] if candidates else PLUGIN_ROOT)
')
```
(Exact plumbing is Claude's discretion per CONTEXT.md — `_newest_sibling_holding` takes a `relative` file-existence arg because it's answering "which sibling holds a copy of X", not "what is the newest version"; the shim needs the latter, which is the un-filtered candidate scan already inlined inside `_newest_sibling_holding` lines 102-113 — reuse that scan logic via import, don't duplicate the regex/sort constants.)

---

### MODIFY: `lv-sweep-run.sh` — staleness self-check

**Analog:** itself (in-place extension) — reuse `stamp()` (lines 24-26) and `banner()` (lines 13-15) already in file.

**Insertion point:** after the arg-count check (line 20), before the sweep runs (line 28) — compare `$1` (the root this invocation is actually running from, now supplied by the shim) against the newest-installed root (same resolution as the shim above). D-63-02: **loud, non-refusing** — this is a third state alongside "healthy" (line 52-54) and "found notices" (line 57+), so it needs its own `stamp()` + `banner()` call that does NOT `exit` — control falls through to the existing sweep invocation at line 28 unchanged:
```sh
if [ "$RUNNING_ROOT" != "$NEWEST_ROOT" ]; then
    stamp "sweep running from $RUNNING_ROOT, newest installed is $NEWEST_ROOT"
    banner "LV backend sweep is running an old version — ask the admin to check the log"
fi
```
Naming both versions in one stamp line matches the Specific Idea in CONTEXT.md ("name **both versions**").

---

### MODIFY: `SWEEP-CRON-TEMPLATE.md`

**Analog:** itself — the crontab line at line 56 (full file already read above).

Current line to change:
```cron
0 */4 * * * /bin/sh "[plugin-root]/skills/backend-sweep/lv-sweep-run.sh" "[plugin-root]" "[venv-python]" "$HOME/Library/Logs/lv-backend-sweep.log"
```
New line pins the shim's fixed durable path instead of `[plugin-root]`:
```cron
0 */4 * * * /bin/sh "$HOME/.claude/plugins/data/<plugin-id>/<shim-filename>" "[plugin-root]" "[venv-python]" "$HOME/Library/Logs/lv-backend-sweep.log"
```
Preserve the surrounding prose exactly (the `/bin/sh` explicit-invocation rationale at lines 59-63, the "Invoking through `/bin/sh` explicitly is deliberate" warning) — only the pinned path token changes. Also update the launchd `ProgramArguments` block (lines 79-84) the same way, and the "Uninstalling" section (line 140-146) if it references the old path shape.

---

### MODIFY: `scripts/build_cloud_workflows.py` — judge model routing

**Analog:** itself — `_enrich_build_judge_request_js` (lines 2887-2900, already read) and the conditional-branching precedent in `_enrich_judge_gate_js`'s Pass 3 (lines 2874-2879).

**Current code (lines 2892-2897):**
```python
def _enrich_build_judge_request_js(cloud=False, target=None):
    t = target or COMPANIES_TARGET
    return inline(*t.judge_build_inline_modules) + r"""

// --- n8n wrapper (""" + t.label + r"""): Build Judge Request ---
""" + _flag_const("ANTHROPIC_JUDGE_MODEL", cloud) + r"""
return $input.all().map((it) => {
  const row = it.json;
  if (!row.needs_judge) return { json: { ...row, judge_request_body: null } };
  const model = ANTHROPIC_JUDGE_MODEL;
  const judge_request_body = """ + t.build_judge_fn + r"""(row, model, """ + str(t.judge_max_tokens) + r""");
  return { json: { ...row, judge_request_body } };
});
"""
```

**`_flag_const`'s bake pattern to follow for a second constant** (lines 1116-1136, already read): `CONFIG_FLAG_DEFAULTS` dict entries get baked as literal JS at cloud=True build time; `ANTHROPIC_JUDGE_MODEL` currently baked from `CONFIG_FLAG_DEFAULTS["ANTHROPIC_JUDGE_MODEL"] = "claude-sonnet-5"` (line ~1100, `CONFIG_FLAG_DEFAULTS` dict starting ~line 1090).

**D-63-05 implementation shape:** add a second model constant (e.g. `ANTHROPIC_JUDGE_MODEL_CHEAP` in `CONFIG_FLAG_DEFAULTS`, baked the same way via `_flag_const`), then branch inside the returned JS on `row.judge_reasons` — exactly the existing `(row.judge_reasons || []).length > 0` idiom already used one function up in `_enrich_judge_gate_js` (line 2875):
```javascript
const model = (row.judge_reasons.length === 1 && row.judge_reasons[0] === "confidence_band")
  ? ANTHROPIC_JUDGE_MODEL_CHEAP
  : ANTHROPIC_JUDGE_MODEL;
```
This is a build-time string template edit (Python f-string / raw-string concatenation), not a runtime Python decision — the branch text itself is baked into the generated `n8n/wf_enrichment_cloud.json` Code node's `jsCode`, matching how every other conditional in this file (`_enrich_judge_gate_js`, `Pass 3`) is expressed: plain JS `if`/ternary inside the returned raw string, never a Python-side condition that would produce two different builder code paths.

**Read-only reference for the trigger this branches on:** `n8n/code/judge.js` lines 145-151 (already read) — `reasons.push("confidence_band")` is the ONLY reason pushed when `_carriesClassification` + band check passes; other pushes (`org_type_conflict`, `region_conflict`, `produces_content_false`, `hardware_vendor_detected`, `gambling_operator_detected`) all happen earlier in the same function and are NOT mutually exclusive with `confidence_band` — hence checking `judge_reasons.length === 1 && judge_reasons[0] === "confidence_band"`, not `.includes("confidence_band")` alone.

**Do not touch** `n8n/code/judge.js`'s `computeEscalation`/`applyUnadjudicated` (D-63-05 is model routing only, `reasons[]` computation is unchanged) or `config/escalation_policy.yaml`'s band (lever 1, out of scope).

---

### NEW: offline replay harness (D-63-06)

**Analog:** `scripts/run_scoring_parity.py` (full file read above, 466 lines) — closest existing "replay stored/sampled data through a comparison and report pass/fail with a hard zero-assertions guard" shape in this repo.

**Structural pattern to copy:**
- `build_report(sample_ids, fetch_fn=..., ...)` — pure, offline-testable core taking an injectable fetch function (lines 267-282); the replay harness's core should equally take an injectable "call model X" function so it stays unit-testable without live Anthropic calls.
- The **false-green guard** (D-13 precedent, lines 19-23, 365-372): `assertions_executed == 0` must be a hard FAIL, never a silent pass — apply the identical rule to the replay harness: zero stored judge inputs in the corpus, or every model call raising, must not read as "models agree."
- `_write_report()` (lines 413-420) — JSON report written to a phase-relative `.planning/phases/.../` directory, date-stamped filename. Reuse this shape (or the phase-63 directory equivalent) for the replay verdict output.
- `main(argv=None) -> int` returning an exit code, guarded credential/precondition checks before any network call (lines 438-452, `_has_credentials()`, `_portal_ok()`) — the replay harness's equivalent precondition is `ANTHROPIC_API_KEY` presence; no HubSpot check needed since D-63-06 mandates zero HubSpot calls.

**Model-call pattern to copy** — `src/validator_sonnet.py` (already located, not fully re-read here — same file style as `src/classifier_haiku.py`, both import `from anthropic import Anthropic` and call `client.messages.create(model=..., ...)`) is the existing "call an Anthropic model with a judge-shaped payload" reference; `src/judge.py` (already read) confirms there is NO existing Python-side Anthropic call for the judge specifically — the harness will be the first one, modeled on `validator_sonnet.py`'s `Anthropic(api_key=...)` + `client.messages.create(model=model, ...)` call shape, called twice per stored input (once per model under comparison) instead of once.

**Corpus source:** stored judge inputs "from past executions" per D-63-06 — no existing fixture directory holds judge HTTP request bodies verbatim; closest existing artifact shape is `.planning/phases/51-backfill-pipeline-credit-sizing-dry-run/51-DRYRUN-PREDICTIONS-run3-judge-escalation.json` (partially read) which stores per-row prediction/evidence JSON from a dry-run batch — same "row objects in a JSON array, each carrying the fields a scoring/judge call needs" shape, but that file is scoring output, not judge request bodies; the harness's corpus-selection mechanism is explicitly Claude's discretion (CONTEXT.md) and will likely need pulling real `judge_request_body` values via `n8n`'s executions API or a HubSpot property read, not a pre-existing fixture file — flag this as a gap, no direct analog exists for "stored judge inputs," only for "stored scoring outputs."

## Shared Patterns

### `/bin/sh` strictness + loud-on-every-non-healthy-path
**Source:** `operator-claude-plugin/skills/backend-sweep/lv-sweep-run.sh` (whole file)
**Apply to:** the new shim and the modified self-check block.
```sh
#!/bin/sh
set -u
banner() { /usr/bin/osascript -e "display notification \"$1\" with title \"LV Backend Sweep\""; }
stamp() { printf '[%s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*" >> "$LOG"; }
```

### Reuse, don't reimplement, version ordering
**Source:** `operator-claude-plugin/scripts/durable_paths.py` lines 41-119
**Apply to:** the shim's version resolution. Import/invoke, never re-derive `_VERSION_DIR_RE`, `_version_key`, or the resolved-path-equality exclusion.

### Build-time constant baking for cloud workflows
**Source:** `scripts/build_cloud_workflows.py` `_flag_const` (lines 1116-1136) + `CONFIG_FLAG_DEFAULTS` dict (~line 1090)
**Apply to:** the second judge-model constant (D-63-05). New flags always go through `CONFIG_FLAG_DEFAULTS` + `_flag_const`, never a bare Python f-string literal inlined ad hoc — this is what keeps `tests/test_builder_flag_parity.py`'s parity guarantee intact per the file's own header comment (lines 1088-1093).

### Report-dict / verdict / exit-code harness shape
**Source:** `scripts/run_scoring_parity.py` `build_report` + `main` (lines 267-465)
**Apply to:** the offline replay harness — same zero-assertions-is-a-failure discipline (D-13), same injectable-function-for-testability shape, same JSON report artifact under `.planning/phases/.../`.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| Stored judge-input corpus for the replay harness | fixture data | batch | No existing file stores raw `judge_request_body` payloads from past executions; nearest neighbor (`51-DRYRUN-PREDICTIONS-run3-judge-escalation.json`) holds scoring predictions, not judge requests. Corpus-sourcing mechanism is Claude's discretion per CONTEXT.md and needs its own extraction step (likely n8n executions API or a stored HubSpot property), not a copy-paste pattern. |

## Metadata

**Analog search scope:** `operator-claude-plugin/skills/backend-sweep/`, `operator-claude-plugin/scripts/`, `scripts/`, `src/`, `n8n/code/`, `.planning/phases/51-*`
**Files scanned:** ~15 (targeted reads + greps, no full-repo scan)
**Pattern extraction date:** 2026-09-02
