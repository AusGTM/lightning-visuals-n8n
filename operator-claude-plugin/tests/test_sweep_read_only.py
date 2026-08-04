"""29-03 Task 2 — NOTICE-05's enforcement: the sweep has NO code path to a mutation.

Three independent assertions, allowlist-first (fails closed on anything new):

1. The transitive first-party import closure of `sweep_entry` is a subset of an explicit
   module allowlist. A new import fails until a human deliberately adds it — which is
   the moment someone has to think about whether the new module can write.
2. The only non-GET HTTP verb reachable anywhere in that closure is the single named
   exception: `backend_status.fetch_backend_status`'s POST to
   `webhook/hubspot/backend-status` (D-13). Every other write verb, module- or
   session-level, fails — so an allowlisted module that later grows a write is still
   caught.
3. (33-02) The only FILESYSTEM write call sites reachable anywhere in that closure are
   the two named functions inside `durable_paths.py` that implement the durable-home
   migration (`_atomic_write_0600`, `_migrate_once`) — never anywhere else. This catches
   what assertion 2 structurally cannot: `open(...,"w")`, `os.replace`, `Path.unlink`,
   `os.chmod` are not HTTP verbs, so `WRITE_VERBS` was always blind to them. The sweep's
   own default config loader (`sweep_entry._load_config_no_migration`) resolves with
   `allow_migration=False`, so even though these two write-capable functions exist in
   the closure's source text (durable_paths.py is shared with the interactive
   resolvers, which DO migrate), a behavioral test below proves the sweep's actual run
   never reaches them.

WHY A POST IS A READ HERE (D-13, so the next reader does not re-derive it): the endpoint
is an n8n webhook and n8n webhooks answer on POST; the request carries no records and no
instruction — `json={}`, the empty literal — and its chain contains no write node, which
is a tested fact (test_backend_status_wiring.py::test_endpoint_chain_contains_no_write_node).
The exception is kept honest the same way test_retry_reuses_dispatch.py keeps its
send-shaped allowlist honest: the POST must carry no `files=`, no `data=`, and its
`json=` body must remain the empty dict literal, checked by AST so a reformat cannot
fool it. The moment it can carry records it is a send, and it loses the exemption.

Mirrors test_no_backend_imports.py's AST idiom — parse, never grep.

29-06 Task 1 extends this file two ways:

1. The same ALLOWED_MODULES allowlist is reused (never re-declared — a second copy is
   the copy that drifts wider, per D-13's own warning) to bound the *shipped skill body*,
   not just the module import graph. A clean module graph invoked by a skill whose prose
   also names a dispatch/write capability would pass the import-only guard above and
   still violate NOTICE-05 — T-29-20 names this exact hole.
2. `SWEEP-CRON-TEMPLATE.md` is checked as text (no pytest harness can run cron) for the
   trigger invocation and the §A5 delivery mechanics, plus the D-19 cadence-cost note.
   32-01 rewrote the invocation this file pins from the LLM-based §A1 trigger (proven
   by RB-8 to fail silently under real cron) to the LLM-free `lv-sweep-run.sh` wrapper.
"""
import ast
import re
from pathlib import Path

import config_gate
import pytest
import sweep_entry

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = PLUGIN_ROOT / "scripts"
SWEEP_SKILL_DIR = PLUGIN_ROOT / "skills" / "backend-sweep"
SWEEP_SKILL_PATH = SWEEP_SKILL_DIR / "SKILL.md"
SWEEP_CRON_TEMPLATE_PATH = SWEEP_SKILL_DIR / "SWEEP-CRON-TEMPLATE.md"

SWEEP_ENTRYPOINT = "sweep_entry"

# THE allowlist. Widening it is a deliberate act with a human attached.
#
# 29-05 Task 2 adds `execution_errors` (sweep_read's new gated get_execution +
# harvest_errors read for D-08b's swallowed-maintenance-failure detection, D-17).
# `error_table` was ALREADY present (imported by sweep_notify since 29-03); execution_errors
# imports it too, and it stays pure over already-fetched data either way — no write
# reaches this closure through it. Read both modules before adding them: neither performs
# I/O (execution_errors.harvest_errors walks an already-fetched execution payload;
# error_table.translate is a standard-library regex lookup), so this widening is the
# guard working as designed (D-10), not a regression.
#
# 33-01 added `durable_paths` on the (now superseded) grounds that it performed no I/O
# beyond `Path.exists()`. 33-02 gave it real filesystem writes (the sibling-scan
# migration): copying a sibling install's config into the durable home at 0600 and then
# DELETING the sibling's copy. That is no longer true, and the `FS_WRITE_VERBS` /
# `DURABLE_PATHS_WRITE_FUNCTIONS` assertions below are what makes this widened comment
# honest instead of stale — the write calls exist in this module's source (shared with
# the interactive resolvers, which must be able to migrate), but the sweep's own default
# loader (`sweep_entry._load_config_no_migration`) resolves with `allow_migration=False`,
# so its actual run never reaches them. See the behavioral test at the bottom of this
# file for the proof that isn't just "the source text says so."
ALLOWED_MODULES = {
    "sweep_entry", "sweep_read", "sweep_conditions", "sweep_notify",
    "config_gate", "n8n_read", "backend_status", "error_table", "execution_errors",
    "durable_paths",
}

WRITE_VERBS = {"post", "put", "patch", "delete"}

# (module, verb) pairs permitted in the closure — exactly one (D-13).
ALLOWED_VERB_SITES = {("backend_status", "post")}

# 33-02: filesystem write verbs. HTTP verbs (above) cannot see `open(...,"w")`,
# `os.replace`, `Path.unlink`, or `os.chmod` — a plain attribute-access scan for these
# names is the same technique WRITE_VERBS already uses, applied to a different
# vocabulary. `fdopen` is included because `_atomic_write_0600` opens its temp file via
# `os.fdopen(fd, "w")`, not the `open()` builtin.
FS_WRITE_VERBS = {"replace", "unlink", "chmod", "fdopen"}

# The narrow, named exception: filesystem writes are permitted ONLY inside these two
# functions of `durable_paths.py` — the migration write and the verify-then-delete —
# never anywhere else in the closure. `durable_paths_write_call_confinement()` below
# checks this at function granularity, not just module granularity, so a write call
# added anywhere ELSE in durable_paths.py (or in any other allowlisted module) still
# fails closed.
DURABLE_PATHS_WRITE_FUNCTIONS = {"_atomic_write_0600", "_migrate_once"}


def _first_party_imports(path: Path, scripts_dir: Path):
    """Module names imported by `path` that resolve to files in scripts_dir."""
    tree = ast.parse(path.read_text())
    found = set()
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names = [node.module]
        for name in names:
            top = name.split(".")[0]
            if (scripts_dir / f"{top}.py").exists():
                found.add(top)
    return found


def transitive_closure(entry: str, scripts_dir: Path):
    """Every first-party module reachable from `entry`, entry included."""
    seen, frontier = set(), {entry}
    while frontier:
        module = frontier.pop()
        if module in seen:
            continue
        seen.add(module)
        frontier |= _first_party_imports(scripts_dir / f"{module}.py", scripts_dir)
    return seen


def write_verb_sites(modules, scripts_dir: Path):
    """(module, verb) for every attribute access to an HTTP write verb in the given
    modules — `requests.post`, `session.put`, anything `.delete`-shaped."""
    sites = set()
    for module in modules:
        tree = ast.parse((scripts_dir / f"{module}.py").read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in WRITE_VERBS:
                sites.add((module, node.attr))
    return sites


def fs_write_verb_sites(modules, scripts_dir: Path):
    """(module, verb) for every attribute access to a filesystem write verb in the
    given modules — the same technique as `write_verb_sites`, applied to
    `FS_WRITE_VERBS` instead of HTTP verbs.

    `.replace` is narrowed to `os.replace(...)` specifically (the qualifier must be the
    bare name `os`): unqualified `.replace` is also the ordinary `str`/`datetime` method
    (e.g. `n8n_read.py`'s `started.replace(tzinfo=...)`), and treating every occurrence
    as a filesystem write would make this guard too noisy to mean anything. `unlink`,
    `chmod` and `fdopen` are not narrowed the same way — they are rare enough in this
    codebase (verified: `unlink` appears nowhere else in scripts/ reachable from the
    sweep) that a false positive there is a real signal worth reading, not noise.
    """
    sites = set()
    for module in modules:
        tree = ast.parse((scripts_dir / f"{module}.py").read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Attribute) or node.attr not in FS_WRITE_VERBS:
                continue
            if node.attr == "replace" and not (
                isinstance(node.value, ast.Name) and node.value.id == "os"
            ):
                continue
            sites.add((module, node.attr))
    return sites


def durable_paths_write_call_confinement(scripts_dir: Path):
    """Which top-level functions in durable_paths.py contain a filesystem write verb.
    Must equal exactly `DURABLE_PATHS_WRITE_FUNCTIONS` — not a subset, not a superset —
    so a write call added to any OTHER function (including a resolver itself, which
    would mean the migration gate had been bypassed) is caught by name, not merely by
    module."""
    tree = ast.parse((scripts_dir / "durable_paths.py").read_text())
    housing = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for inner in ast.walk(node):
                if isinstance(inner, ast.Attribute) and inner.attr in FS_WRITE_VERBS:
                    housing.add(node.name)
                    break
    return housing


def status_post_payload_violations(path: Path):
    """AST check that fetch_backend_status's transport call stays bodyless: `json=`
    must be the empty dict literal, and no `files=` / `data=` may appear anywhere in
    the function. Returns human-readable violations; empty means honest."""
    tree = ast.parse(path.read_text())
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "fetch_backend_status":
            for call in ast.walk(node):
                if not isinstance(call, ast.Call):
                    continue
                for kw in call.keywords:
                    if kw.arg in ("files", "data"):
                        violations.append(f"carries {kw.arg}= — a payload channel")
                    if kw.arg == "json":
                        if not (isinstance(kw.value, ast.Dict) and not kw.value.keys):
                            violations.append("json= is not the empty dict literal")
            break
    else:
        violations.append("fetch_backend_status not found")
    return violations


# --- the two live assertions ------------------------------------------------------------

def test_the_sweep_import_closure_is_exactly_the_allowlist():
    closure = transitive_closure(SWEEP_ENTRYPOINT, SCRIPTS)
    assert closure <= ALLOWED_MODULES, (
        f"new module(s) in the sweep graph: {sorted(closure - ALLOWED_MODULES)} — "
        f"before widening ALLOWED_MODULES, decide whether they can write"
    )
    # And no stale allowlist fat: every allowed module is genuinely reachable, so the
    # list stays a description of the graph rather than a wish.
    assert closure == ALLOWED_MODULES, (
        f"allowlisted but unreachable: {sorted(ALLOWED_MODULES - closure)}"
    )


def test_the_only_reachable_write_verb_is_the_named_status_post():
    closure = transitive_closure(SWEEP_ENTRYPOINT, SCRIPTS)
    sites = write_verb_sites(closure, SCRIPTS)
    assert sites == ALLOWED_VERB_SITES, (
        f"write verbs beyond the D-13 exception: {sorted(sites - ALLOWED_VERB_SITES)}"
    )


def test_the_allowlisted_post_is_still_bodyless():
    assert status_post_payload_violations(SCRIPTS / "backend_status.py") == []


def test_the_only_reachable_filesystem_writes_are_the_named_migration_functions():
    """33-02: the compensating assertion the blocking constraint requires — WRITE_VERBS
    is HTTP-shaped and structurally cannot see `open`/`replace`/`unlink`/`chmod`. This
    is the same allowlist-first discipline as the HTTP-verb guard, applied to a
    filesystem vocabulary, with the narrow named exception being function-scoped
    (`DURABLE_PATHS_WRITE_FUNCTIONS`) rather than module-scoped — a write call added
    anywhere else in durable_paths.py, or in any other module in the closure, fails."""
    closure = transitive_closure(SWEEP_ENTRYPOINT, SCRIPTS)
    sites = fs_write_verb_sites(closure, SCRIPTS)
    modules_with_writes = {module for module, _verb in sites}
    assert modules_with_writes <= {"durable_paths"}, (
        f"filesystem write verb(s) outside durable_paths.py: "
        f"{sorted(sites - fs_write_verb_sites({'durable_paths'}, SCRIPTS))}"
    )

    housing = durable_paths_write_call_confinement(SCRIPTS)
    assert housing == DURABLE_PATHS_WRITE_FUNCTIONS, (
        f"filesystem writes are housed in {sorted(housing)}, expected exactly "
        f"{sorted(DURABLE_PATHS_WRITE_FUNCTIONS)} — a write call outside the named "
        f"migration functions (or the migration gaining a new one) must be reviewed"
    )


def test_the_guard_flags_a_filesystem_write_outside_the_named_functions(tmp_path):
    scripts = _mini_graph(
        tmp_path,
        "import helper\n",
        helper="import os\n\ndef go(path):\n    os.unlink(path)\n")
    sites = fs_write_verb_sites({"entry", "helper"}, scripts)
    assert sites == {("helper", "unlink")}, "the guard failed to see a filesystem write"


def test_the_sweep_does_not_migrate_even_when_a_sibling_holds_a_config(tmp_path, monkeypatch):
    """The behavioral proof the static guards above cannot provide on their own: the
    write-capable code exists in durable_paths.py's source (shared with the interactive
    resolvers), so a purely syntactic scan can only confine WHERE it lives, not prove
    the sweep's actual run never gets there. This drives `sweep_entry._cli_main()` with
    its REAL default loader (no injected `load_config=`) against a fake HOME where a
    migration is genuinely available, and proves it does not happen — then, as a
    control, proves the identical layout DOES migrate when `allow_migration=True`, so
    the abstention above is meaningful and not just "nothing was there anyway"."""
    import config_gate
    import durable_paths

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    monkeypatch.delenv("LV_OPERATOR_CONFIG", raising=False)

    cache_root = tmp_path / "cache"
    sibling = cache_root / "0.6.1" / "config"
    sibling.mkdir(parents=True)
    sibling_config = sibling / "operator.local.json"
    sibling_config.write_text(
        '{"n8n_url": "https://sibling.example", "n8n_api_key": "k", '
        '"webhook_secret": "s"}'
    )
    current = cache_root / "0.6.2"
    (current / "config").mkdir(parents=True)  # current install's own config/, empty

    monkeypatch.setattr(durable_paths, "PLUGIN_ROOT", current)

    durable_target = (fake_home / ".claude" / "plugins" / "data"
                      / durable_paths.PLUGIN_ID / "operator.local.json")

    notices = sweep_entry._cli_main()

    assert not durable_target.exists(), (
        "the sweep must never write the durable home — it resolved read-only"
    )
    assert sibling_config.exists(), (
        "the sweep must never delete a sibling's config — it never reached the "
        "migration step at all"
    )
    assert notices and notices[0]["condition"] == "sweep_not_configured", (
        "with migration disabled and nothing else configured, the sweep must report "
        "sweep_not_configured — loud, not a silent all-clear"
    )

    # Control: the identical layout DOES migrate when migration is allowed — proving
    # the scenario above was genuinely capable of migrating, not vacuous.
    migrated_path = durable_paths.resolve_config_path(allow_migration=True)
    assert migrated_path == durable_target
    assert durable_target.exists()
    assert not sibling_config.exists()


# --- proof the guard bites (synthetic modules, never edited production code) ------------

def _mini_graph(tmp_path, entry_source, **modules):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "entry.py").write_text(entry_source)
    for name, source in modules.items():
        (scripts / f"{name}.py").write_text(source)
    return scripts


def test_the_guard_flags_an_import_outside_the_allowlist(tmp_path):
    scripts = _mini_graph(tmp_path, "import helper\nimport dispatch\n",
                          helper="x = 1\n", dispatch="def dispatch():\n    pass\n")
    closure = transitive_closure("entry", scripts)
    assert not closure <= {"entry", "helper"}, "the guard failed to flag a new import"


def test_the_guard_flags_a_non_allowlisted_write_verb(tmp_path):
    scripts = _mini_graph(
        tmp_path,
        "import requests\n\ndef go(url):\n    return requests.put(url)\n")
    sites = write_verb_sites({"entry"}, scripts)
    assert sites == {("entry", "put")}, "the guard failed to see a write verb"
    assert not sites <= ALLOWED_VERB_SITES


def test_the_guard_flags_the_status_post_growing_a_body(tmp_path):
    mutated = (SCRIPTS / "backend_status.py").read_text().replace(
        "json={},", 'json={"records": "smuggled"},')
    assert mutated != (SCRIPTS / "backend_status.py").read_text()
    bad = tmp_path / "backend_status.py"
    bad.write_text(mutated)
    assert status_post_payload_violations(bad), (
        "the compensating assertion failed to catch a payload-carrying status POST"
    )


# --- 29-06 Task 1: the shipped skill body is bound by the SAME allowlist (T-29-20) ------

_SCRIPT_REF = re.compile(r"scripts/([A-Za-z_][A-Za-z0-9_]*)\.py")


def _skill_capabilities(text: str) -> set:
    """Every first-party script a skill body names, by module name — the skill's own
    'capability surface', read in the same terms the import-graph allowlist uses. A
    skill that never mentions a script beyond the sweep entrypoint has nowhere else to
    reach; a skill that also names, say, `scripts/control_actions.py` has widened its
    reach past what the module guard above can see, since prose is not an import."""
    return set(_SCRIPT_REF.findall(text))


def test_the_sweep_skill_names_only_the_sweep_entrypoint():
    assert SWEEP_SKILL_PATH.exists(), "skills/backend-sweep/SKILL.md was not shipped"
    named = _skill_capabilities(SWEEP_SKILL_PATH.read_text())
    assert named, "the skill body names no script at all — nothing for it to invoke"
    assert named <= ALLOWED_MODULES, (
        f"the skill body names capabilities outside the read-only allowlist: "
        f"{sorted(named - ALLOWED_MODULES)} — a clean module graph invoked by a wide "
        f"skill body still violates NOTICE-05 (T-29-20)"
    )


def test_the_skill_capability_check_flags_a_synthetic_wide_skill_body():
    wide_body = (
        "Run:\n\n    python3 scripts/sweep_entry.py\n\n"
        "then dispatch anything pending with:\n\n    python3 scripts/control_actions.py\n"
    )
    named = _skill_capabilities(wide_body)
    assert not named <= ALLOWED_MODULES, (
        "the capability check failed to flag a skill body naming a write capability "
        "outside the allowlist"
    )


# --- 29-06 Task 1: SWEEP-CRON-TEMPLATE.md, checked as text (no pytest can run cron) -----

def test_sweep_cron_template_reproduces_the_wrapper_invocation_and_a5_delivery():
    """Rewritten 2026-08-03 (32-01, RB-8). The assertions this test carried before this
    date REQUIRED `claude -p` and `--allowedTools` — exactly the invocation RB-8 proved
    fails silently under real cron (an expired credential with no refresh, `node`
    absent from cron's PATH; `29-06-FINDINGS.md`). That invocation is no longer correct
    to ship, so this test is inverted: it now asserts the NEW wrapper invocation
    (`lv-sweep-run.sh`, run through `/bin/sh`, LLM-free) is present, and that the OLD
    LLM invocation is ABSENT, so the removal cannot silently regress back to the
    trigger that failed."""
    assert SWEEP_CRON_TEMPLATE_PATH.exists(), "SWEEP-CRON-TEMPLATE.md was not shipped"
    text = SWEEP_CRON_TEMPLATE_PATH.read_text()

    assert "lv-sweep-run.sh" in text, "must invoke the shipped wrapper, not an LLM"
    assert "/bin/sh" in text, "must invoke the wrapper through /bin/sh explicitly"
    assert "[plugin-root]" in text and "[venv-python]" in text, (
        "must name the wrapper's three positional arguments (plugin root, python, log)"
    )
    assert ".log" in text, (
        "must still name a log path (§A5 — the banner is one line, the log carries "
        "the untruncated detail)"
    )
    assert "osascript" in text, "must post the one-line banner via osascript (§A5)"
    assert "empty" in text.lower(), (
        "the banner must be gated on a non-empty notice list, not fired every run"
    )

    assert "claude -p" not in text, (
        "the old LLM invocation must be gone — RB-8 proved it fails silently under cron"
    )
    assert "--allowedTools" not in text, "the old tool-permission flag must be gone too"


def test_sweep_cron_template_states_the_cadence_mediated_no_credit_property():
    text = SWEEP_CRON_TEMPLATE_PATH.read_text()
    assert re.search(r"all three provider", text, re.I), (
        "cadence note must state that each fire probes all three provider balance "
        "endpoints via the backend (D-19)"
    )
    assert re.search(r"cadence is the only dial|cadence.{0,40}bound", text, re.I), (
        "cadence note must state that cadence, not structure, bounds the sweep's cost "
        "(D-19) — it must not read as free at any frequency"
    )


# --- 29-06 Task 1: the CLI entrypoint the skill invokes fails closed, never raises ------

def test_the_cli_entrypoint_returns_a_notice_never_raises_when_config_load_fails():
    """sweep_entry.py had no runnable CLI before this plan — the skill above needed one
    to invoke, so `_cli_main` was added. D-15's rule applies one layer above
    `run_sweep`'s own 'sweep' capability check: `config_gate.load_config` can raise
    `ConfigError` before `run_sweep` ever gets a config dict (e.g. no n8n_url/
    webhook_secret configured at all). That must be a notice too, never a traceback —
    a traceback prints nothing into a cron wrapper's redirected log, which reads as
    silence, and silence means healthy (D-08)."""
    def _raise():
        raise config_gate.ConfigError("boom: no config at all")

    notices = sweep_entry._cli_main(load_config=_raise)
    assert notices == [{
        "condition": "sweep_not_configured",
        "headline": "LV backend sweep: not configured — it is NOT watching",
        "detail": ("boom: no config at all\nUntil this is fixed the sweep runs but "
                   "cannot check anything, so silence from it means nothing."),
        "who_can_fix": "admin",
        "execution_id": None,
    }]
