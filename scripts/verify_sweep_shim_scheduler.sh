#!/bin/sh
set -u

# scripts/verify_sweep_shim_scheduler.sh
#
# Real-scheduler proof for the sweep launcher shim (D-63-01, phase 63 plan 02). An
# interactive `sh` invocation of the shim proves nothing about the case that matters
# -- memory `sweep-trigger-llm-free` records that this project's earlier trigger
# design passed its own interactive host probe and still failed silently under a
# real cron tick, because the interactive run inherited an environment the
# scheduler never has. This harness instead:
#
#   1. builds an isolated temporary plugin world (a `cache/` root holding real
#      copies of sweep_shim.py, durable_paths.py and lv-sweep-run.sh under version
#      directories 1.0.0 and 1.1.0, each with a stubbed sweep_entry.py carrying a
#      distinguishing marker);
#   2. installs the shim via the real CLI, pointed at that temporary world only;
#   3. registers a real, uniquely labelled, temporary launchd agent (StartInterval
#      60s, no RunAtLoad) naming the shim as its ProgramArguments[1];
#   4. waits for a genuine scheduled fire, asserts it resolved 1.1.0 (the newest
#      install at that point) by grepping the shared log for that version's marker;
#   5. simulates a plugin update by adding a 1.2.0 directory -- no edit to the
#      plist, no edit to the shim -- and waits for the NEXT fire to resolve 1.2.0;
#   6. tears down the launchd registration on every exit path and confirms its
#      absence with an INDEPENDENT `launchctl list` read, then removes the
#      temporary work directory.
#
# D-63-03 forbids rewriting any crontab. This harness contains no `crontab`
# invocation of any form, writes nothing outside its own `mktemp -d` work
# directory except the launchd registration it removes by label, and never
# touches a real install directory under the operator's plugin cache root.
#
# Evidence is read by LINE CONTENT (the version marker embedded by the wrapper's
# own `stamp()` call), never by line count or line position -- two overlapping
# fires may both append, and the harness must still attribute each line correctly
# (T-63-A concurrency backstop).
#
# Re-runnable: the launchd label embeds this run's own PID, so two runs in
# succession never collide, and each run's teardown leaves no residue for the
# next.

LABEL_PREFIX="com.lightningvisuals.sweep-shim-proof"
LABEL="${LABEL_PREFIX}.$$"

FIRST_FIRE_TIMEOUT=150
SECOND_FIRE_TIMEOUT=150
POLL_INTERVAL=2

CLEANED=0
WORK=""
PLIST_PATH=""
LOADED=0
TEARDOWN_OK=1

log_err() {
    echo "$1" >&2
}

# --- teardown --------------------------------------------------------------------
# Runs from the EXIT trap on every exit path (normal completion, `exit 1` from a
# failure branch, or an interrupting signal). Guarded by CLEANED so a signal
# handler that itself calls `exit` (which re-triggers the EXIT trap) cannot run
# teardown twice.
cleanup() {
    if [ "$CLEANED" -eq 1 ]; then
        return
    fi
    CLEANED=1

    if [ "$LOADED" -eq 1 ] && [ -n "$PLIST_PATH" ]; then
        launchctl unload "$PLIST_PATH" >/dev/null 2>&1
        # Independent confirmation: do not trust unload's own exit status. A
        # residual job under this run's exact label, OR any orphaned job still
        # carrying the fixed label prefix, is a failed teardown.
        if launchctl list 2>/dev/null | grep -q "$LABEL_PREFIX"; then
            log_err "FAIL: teardown could not be confirmed -- a job carrying label prefix '$LABEL_PREFIX' is still registered."
            log_err "Remove it by hand: launchctl unload '$PLIST_PATH' (or launchctl list | grep $LABEL_PREFIX to find it, then launchctl bootout gui/\$(id -u)/<label>)."
            TEARDOWN_OK=0
        else
            echo "teardown confirmed: no job carrying prefix '$LABEL_PREFIX' remains (label was '$LABEL')"
        fi
    fi

    if [ -n "$WORK" ] && [ -d "$WORK" ]; then
        if [ "$TEARDOWN_OK" -eq 1 ]; then
            rm -rf "$WORK"
        else
            log_err "leaving work dir in place for manual cleanup (it holds \$PLIST_PATH named above): $WORK"
        fi
    fi
}

on_exit() {
    rc=$?
    cleanup
    if [ "$TEARDOWN_OK" -ne 1 ]; then
        exit 1
    fi
    exit "$rc"
}
on_signal() {
    sig_rc=$1
    cleanup
    exit "$sig_rc"
}
trap on_exit EXIT
trap 'on_signal 130' INT
trap 'on_signal 143' TERM

fail() {
    log_err "FAIL: $1"
    exit 1
}

# --- precondition: launchd must be usable for the current user -------------------
if ! command -v launchctl >/dev/null 2>&1; then
    fail "launchd unavailable -- launchctl not found on PATH. Proof not obtained (not assumed)."
fi
if ! launchctl list >/dev/null 2>&1; then
    fail "launchd unavailable -- 'launchctl list' failed for the current user session. Proof not obtained (not assumed)."
fi

# --- locate real plugin sources ---------------------------------------------------
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
SWEEP_SHIM_SRC="$REPO_ROOT/operator-claude-plugin/scripts/sweep_shim.py"
DURABLE_PATHS_SRC="$REPO_ROOT/operator-claude-plugin/scripts/durable_paths.py"
WRAPPER_SRC="$REPO_ROOT/operator-claude-plugin/skills/backend-sweep/lv-sweep-run.sh"

for f in "$SWEEP_SHIM_SRC" "$DURABLE_PATHS_SRC" "$WRAPPER_SRC"; do
    [ -f "$f" ] || fail "missing real plugin source file: $f"
done

PYTHON3=$(command -v python3) || fail "python3 not found on PATH"

# --- build the isolated world under mktemp -d -------------------------------------
WORK=$(mktemp -d "${TMPDIR:-/tmp}/sweep-shim-proof.XXXXXX") || fail "mktemp -d failed"
CACHE_ROOT="$WORK/cache"
DURABLE_DIR="$WORK/durable"
LOG_PATH="$WORK/sweep.log"
PLIST_PATH="$WORK/${LABEL}.plist"

mkdir -p "$CACHE_ROOT" "$DURABLE_DIR" || fail "could not create temporary world under $WORK"

make_version() {
    # $1 = version directory name, $2 = distinguishing marker string this
    # version's stubbed sweep_entry.py reports as a single notice's headline.
    _version="$1"
    _marker="$2"
    _vdir="$CACHE_ROOT/$_version"
    mkdir -p "$_vdir/scripts" "$_vdir/skills/backend-sweep" || fail "could not create version dir $_vdir"
    cp "$SWEEP_SHIM_SRC" "$_vdir/scripts/sweep_shim.py" || fail "could not copy sweep_shim.py into $_vdir"
    cp "$DURABLE_PATHS_SRC" "$_vdir/scripts/durable_paths.py" || fail "could not copy durable_paths.py into $_vdir"
    cp "$WRAPPER_SRC" "$_vdir/skills/backend-sweep/lv-sweep-run.sh" || fail "could not copy lv-sweep-run.sh into $_vdir"
    chmod +x "$_vdir/skills/backend-sweep/lv-sweep-run.sh"
    # Stub entrypoint: no network call, no credential, no n8n execution. Reports
    # one notice whose headline IS the marker, so the wrapper's own `stamp "$OUT"`
    # line carries version-attributable content into the shared log.
    printf 'print(%s)\n' "'[{\"headline\": \"$_marker\"}]'" > "$_vdir/scripts/sweep_entry.py"
}

MARKER_100="SWEEP_PROOF_MARKER_1_0_0_UNUSED"
MARKER_110="SWEEP_PROOF_MARKER_1_1_0"
MARKER_120="SWEEP_PROOF_MARKER_1_2_0"

make_version "1.0.0" "$MARKER_100"
make_version "1.1.0" "$MARKER_110"

# --- install the shim via the real CLI, pointed only at the temporary world ------
SHIM_PATH=$("$PYTHON3" "$CACHE_ROOT/1.1.0/scripts/sweep_shim.py" --install \
    --cache-root "$CACHE_ROOT" --durable-dir "$DURABLE_DIR") || fail "shim install failed"
[ -f "$SHIM_PATH" ] || fail "installed shim not found at reported path: $SHIM_PATH"
echo "shim installed at $SHIM_PATH (cache root baked in: $CACHE_ROOT)"

# --- register a real, uniquely labelled, temporary launchd agent -----------------
cat > "$PLIST_PATH" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/sh</string>
    <string>$SHIM_PATH</string>
    <string>$CACHE_ROOT/1.1.0</string>
    <string>$PYTHON3</string>
    <string>$LOG_PATH</string>
  </array>
  <key>StartInterval</key>
  <integer>60</integer>
</dict>
</plist>
PLISTEOF

echo "registering launchd label: $LABEL"
launchctl load "$PLIST_PATH" || fail "launchctl load failed for $PLIST_PATH"
LOADED=1

# --- poll the shared log for a marker, up to a timeout ----------------------------
wait_for_marker() {
    _marker="$1"
    _timeout="$2"
    _elapsed=0
    while [ "$_elapsed" -lt "$_timeout" ]; do
        if [ -f "$LOG_PATH" ] && grep -qF "$_marker" "$LOG_PATH"; then
            echo "$_elapsed"
            return 0
        fi
        sleep "$POLL_INTERVAL"
        _elapsed=$((_elapsed + POLL_INTERVAL))
    done
    return 1
}

# --- observation phase 1: the first genuine scheduled fire must resolve 1.1.0 ----
PHASE1_START=$(date +%s)
if ! PHASE1_WAITED=$(wait_for_marker "$MARKER_110" "$FIRST_FIRE_TIMEOUT"); then
    fail "inconclusive: no scheduled fire observed carrying marker $MARKER_110 within ${FIRST_FIRE_TIMEOUT}s. A run in which the scheduled fire never happened is reported as inconclusive, never as a pass."
fi
FIRST_LINE=$(grep -F "$MARKER_110" "$LOG_PATH" | tail -n 1)
echo "OK: first scheduled fire observed after ${PHASE1_WAITED}s -- marker=$MARKER_110"
echo "observed log line: $FIRST_LINE"
PRE_UPDATE_COUNT_110=$(grep -cF "$MARKER_110" "$LOG_PATH")

# --- simulate a plugin update: add 1.2.0, no edit to the plist or the shim ------
make_version "1.2.0" "$MARKER_120"
echo "simulated plugin update: added $CACHE_ROOT/1.2.0 (no plist edit, no shim edit)"

# --- observation phase 2: the NEXT fire must follow the update, unaided --------
PHASE2_START=$(date +%s)
if ! PHASE2_WAITED=$(wait_for_marker "$MARKER_120" "$SECOND_FIRE_TIMEOUT"); then
    # Distinguish "no fire at all" from "fires continued but stuck on 1.1.0" by
    # comparing the 1.1.0 marker's line COUNT before/after -- this only decides
    # which of two FAILURE messages to print; the pass/fail decision above and
    # below is always made from marker CONTENT, never from a line count.
    POST_COUNT_110=$(grep -cF "$MARKER_110" "$LOG_PATH" 2>/dev/null || echo 0)
    if [ "$POST_COUNT_110" -gt "$PRE_UPDATE_COUNT_110" ]; then
        fail "the second fire still resolved 1.1.0 (marker count grew from $PRE_UPDATE_COUNT_110 to $POST_COUNT_110 with no $MARKER_120 line) -- the shim did not follow the simulated update."
    fi
    fail "inconclusive: no further scheduled fire observed (neither $MARKER_110 nor $MARKER_120) within ${SECOND_FIRE_TIMEOUT}s after the simulated update. A run in which the scheduled fire never happened is reported as inconclusive, never as a pass."
fi
SECOND_LINE=$(grep -F "$MARKER_120" "$LOG_PATH" | tail -n 1)
echo "OK: second scheduled fire observed after ${PHASE2_WAITED}s post-update -- marker=$MARKER_120"
echo "observed log line: $SECOND_LINE"

ELAPSED_BETWEEN_PHASE_STARTS=$(( PHASE2_START - PHASE1_START ))
echo "elapsed between phase starts (poll-loop clock, not wrapper timestamps): ${ELAPSED_BETWEEN_PHASE_STARTS}s"

echo "PASS: a genuine scheduled launchd fire resolved through the installed shim to 1.1.0 (the newest install at that time); after a simulated update with no schedule/shim edit, the next genuine fire resolved to 1.2.0."
exit 0
