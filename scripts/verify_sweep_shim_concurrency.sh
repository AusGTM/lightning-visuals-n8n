#!/bin/sh
set -u

# scripts/verify_sweep_shim_concurrency.sh
#
# Concurrency and interruption backstop for the sweep launcher shim (T-63-A, the
# `verification: backstop` must-have that 63-VERIFICATION.md tags
# `insufficient_spec` and routes to Human Verification).
#
# SIBLING of scripts/verify_sweep_shim_scheduler.sh, which proves a DIFFERENT
# thing (a genuine scheduled fire resolves the newest install, and follows a
# simulated update). That file is 63-02's committed proof artifact and is not
# modified by this one. The isolated-world / uniquely-labelled-agent /
# teardown-on-every-path skeleton is copied from it deliberately.
#
# What this harness proves, and how:
#
#   Phase 1 -- INTERRUPTION. A genuine scheduled fire is killed mid-run (the
#   resolved wrapper's exec, which the UAT text explicitly permits) while its
#   payload is still sleeping. The harness then asserts that a LATER genuine fire
#   resolves and stamps a COMPLETE line -- i.e. the interrupted fire left no
#   lockfile, no half-written artifact and no partial log line for the next fire
#   to trip on.
#
#   Phase 2 -- OVERLAP. Two launchd jobs are registered against the SAME shim and
#   the SAME log. Two labels are required, not one: launchd never runs two
#   instances of a single label concurrently, so a same-label StartInterval can
#   never produce overlapping fires however long the payload runs. With both jobs
#   on a 60s StartInterval and a 90s payload, the two live intervals must overlap
#   by construction (any two fires start within one interval of each other, and
#   each lasts longer than that interval) -- overlap here is structural, not luck.
#
# The shipped shim and the shipped `lv-sweep-run.sh` both run UNMODIFIED. The
# sleep lives in the neutralized `sweep_entry.py` payload, not in a fake wrapper.
# This is a deliberate deviation from the checkpoint's "plant a fake wrapper"
# sketch and it is strictly stronger: the UAT names `stamp()`'s append target as
# the thing that must not tear, and `stamp()` is the SHIPPED wrapper's function --
# a planted wrapper would have tested a stub's appender instead of the real one.
#
# EVIDENCE IS READ BY LINE CONTENT ONLY, never by line count or line position
# (the plan's own prohibition). Each fire's payload embeds its own pid and its own
# start/end epochs into the notice headline, so every log line is attributable to
# a specific fire from its text alone, and overlap is decided by comparing two
# fires' embedded intervals -- not by where their lines landed in the file. Line
# ORDER between two concurrent fires' stamp sequences is expected and is not a
# failure; only INTRA-line tearing is.
#
# D-63-03: this harness contains no `crontab` invocation of any form. It writes
# nothing outside its own `mktemp -d` work directory except the two launchd
# registrations it removes by label, and never touches a real install directory
# under the operator's plugin cache root. Zero network calls, zero provider
# credits, zero n8n executions.
#
# NOTE: the shipped wrapper posts a macOS notification per notice headline via
# osascript. This harness therefore produces a small number of real desktop
# notifications carrying SWEEP_CONC markers, exactly as the scheduler proof did.
#
# Re-runnable: both launchd labels embed this run's own PID, so two runs in
# succession never collide, and each run's teardown leaves no residue.
#
# Expect roughly 8-12 minutes of wall time. Run it in the background.

LABEL_PREFIX="com.lightningvisuals.sweep-shim-conc"
LABEL_A="${LABEL_PREFIX}.$$.a"
LABEL_B="${LABEL_PREFIX}.$$.b"

START_INTERVAL=60
PAYLOAD_SLEEP=90
POLL_INTERVAL=2

WRAPPER_APPEAR_TIMEOUT=240
POST_KILL_TIMEOUT=360
OVERLAP_TIMEOUT=420

CLEANED=0
WORK=""
PLIST_A=""
PLIST_B=""
LOADED_A=0
LOADED_B=0
TEARDOWN_OK=1

log_err() {
    echo "$1" >&2
}

# --- teardown --------------------------------------------------------------------
# Runs from the EXIT trap on every exit path (normal completion, `exit 1` from a
# failure branch, or an interrupting signal). Guarded by CLEANED so a signal
# handler that itself calls `exit` (which re-triggers the EXIT trap) cannot run
# teardown twice. BOTH labels are unloaded; the confirmation grep is on the shared
# prefix, so a residual job from either label fails teardown.
cleanup() {
    if [ "$CLEANED" -eq 1 ]; then
        return
    fi
    CLEANED=1

    if [ "$LOADED_A" -eq 1 ] && [ -n "$PLIST_A" ]; then
        launchctl unload "$PLIST_A" >/dev/null 2>&1
    fi
    if [ "$LOADED_B" -eq 1 ] && [ -n "$PLIST_B" ]; then
        launchctl unload "$PLIST_B" >/dev/null 2>&1
    fi

    if [ "$LOADED_A" -eq 1 ] || [ "$LOADED_B" -eq 1 ]; then
        # Independent confirmation: do not trust unload's own exit status. Any job
        # still carrying the fixed label prefix -- this run's or an orphan from an
        # earlier one -- is a failed teardown.
        if launchctl list 2>/dev/null | grep -q "$LABEL_PREFIX"; then
            log_err "FAIL: teardown could not be confirmed -- a job carrying label prefix '$LABEL_PREFIX' is still registered."
            log_err "Remove it by hand: launchctl list | grep $LABEL_PREFIX to find it, then launchctl bootout gui/\$(id -u)/<label>."
            TEARDOWN_OK=0
        else
            echo "teardown confirmed: no job carrying prefix '$LABEL_PREFIX' remains (labels were '$LABEL_A', '$LABEL_B')"
        fi
    fi

    if [ -n "$WORK" ] && [ -d "$WORK" ]; then
        if [ "$TEARDOWN_OK" -eq 1 ]; then
            rm -rf "$WORK"
        else
            log_err "leaving work dir in place for manual cleanup (it holds both plists): $WORK"
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
if ! command -v pgrep >/dev/null 2>&1; then
    fail "pgrep not found on PATH -- phase 1 cannot detect the running fire it must interrupt. Proof not obtained (not assumed)."
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
WORK=$(mktemp -d "${TMPDIR:-/tmp}/sweep-shim-conc.XXXXXX") || fail "mktemp -d failed"
# Canonicalize. macOS `$TMPDIR` ends in `/`, so the mktemp template yields a path
# containing `//`. That matters here in a way it did not for the scheduler proof:
# the shim execs the wrapper with the root that `newest_install_root` returned, and
# that is a `pathlib.Path`, which COLLAPSES `//` to `/`. A `pgrep -f` pattern built
# from the un-normalized shell value would then never match the running wrapper, and
# phase 1 would report "no fire observed" forever while fires were happening.
WORK=$(CDPATH= cd -- "$WORK" && pwd) || fail "could not canonicalize work dir"
WORK_NAME=$(basename "$WORK")
CACHE_ROOT="$WORK/cache"
DURABLE_DIR="$WORK/durable"
LOG_PATH="$WORK/sweep.log"
PLIST_A="$WORK/${LABEL_A}.plist"
PLIST_B="$WORK/${LABEL_B}.plist"
EVIDENCE_PY="$WORK/read_evidence.py"
EVIDENCE_OUT="$WORK/evidence.txt"

mkdir -p "$CACHE_ROOT" "$DURABLE_DIR" || fail "could not create temporary world under $WORK"

make_version() {
    # $1 = version directory name. The stubbed sweep_entry.py sleeps PAYLOAD_SLEEP
    # seconds and then reports ONE notice whose headline embeds this process's own
    # pid and its own start/end epochs -- that is what makes every resulting log
    # line attributable to a specific fire by CONTENT alone.
    _version="$1"
    _vdir="$CACHE_ROOT/$_version"
    mkdir -p "$_vdir/scripts" "$_vdir/skills/backend-sweep" || fail "could not create version dir $_vdir"
    cp "$SWEEP_SHIM_SRC" "$_vdir/scripts/sweep_shim.py" || fail "could not copy sweep_shim.py into $_vdir"
    cp "$DURABLE_PATHS_SRC" "$_vdir/scripts/durable_paths.py" || fail "could not copy durable_paths.py into $_vdir"
    cp "$WRAPPER_SRC" "$_vdir/skills/backend-sweep/lv-sweep-run.sh" || fail "could not copy lv-sweep-run.sh into $_vdir"
    chmod +x "$_vdir/skills/backend-sweep/lv-sweep-run.sh"
    cat > "$_vdir/scripts/sweep_entry.py" <<PAYLOADEOF
import os, time
_start = int(time.time())
time.sleep($PAYLOAD_SLEEP)
_end = int(time.time())
print('[{"headline": "SWEEP_CONC pid=%d start=%d end=%d"}]' % (os.getpid(), _start, _end))
PAYLOADEOF
}

make_version "1.0.0"
make_version "1.1.0"

# --- the evidence reader: CONTENT ONLY --------------------------------------------
# Reads the shared log and reports, from line text alone:
#   * lines that do not carry the wrapper's `stamp()` timestamp prefix -- a headless
#     fragment is what a torn append looks like;
#   * lines carrying MORE THAN ONE fire marker -- two appends interleaved into one
#     physical line;
#   * marker lines whose notice JSON is not intact end to end;
#   * every distinct fire (pid + its own start/end epochs), and how many pairs of
#     those fires had OVERLAPPING live intervals.
# Nothing here reads a line count or a line position to decide pass/fail: counts are
# reported so the shell can assert "zero offenders", and the offenders themselves are
# identified by their text.
cat > "$EVIDENCE_PY" <<'EVIDENCEEOF'
import json
import re
import sys

STAMP_RE = re.compile(r"^\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{4}\] ")
MARK_RE = re.compile(r"SWEEP_CONC pid=(\d+) start=(\d+) end=(\d+)")

path = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        raw = fh.read()
except FileNotFoundError:
    raw = ""

lines = [ln for ln in raw.split("\n") if ln != ""]

bad_shape = []
multi_marker = []
malformed_marker = []
runs = {}

for ln in lines:
    if not STAMP_RE.match(ln):
        bad_shape.append(ln)
        continue
    found = MARK_RE.findall(ln)
    if len(found) > 1:
        multi_marker.append(ln)
        continue
    if len(found) == 1:
        pid, start, end = found[0]
        # The wrapper stamps the payload's raw stdout verbatim. An intact line
        # therefore carries the complete notice JSON. Anything short of that is a
        # partial write, however plausible the prefix looks.
        expected = '[{"headline": "SWEEP_CONC pid=%s start=%s end=%s"}]' % (pid, start, end)
        body = ln[ln.index("] ") + 2:]
        if body != expected:
            # `sweep found N notice(s)` never carries a marker, so the only marker
            # lines are the verbatim-stdout ones; a marker line that is not exactly
            # the notice JSON is either torn or truncated.
            malformed_marker.append(ln)
            continue
        runs[(pid, start, end)] = ln

ordered = sorted(runs.items(), key=lambda kv: int(kv[0][1]))
overlaps = []
for i in range(len(ordered)):
    (pa, sa, ea), la = ordered[i]
    for j in range(i + 1, len(ordered)):
        (pb, sb, eb), lb = ordered[j]
        if int(sb) < int(ea) and int(sa) < int(eb):
            overlaps.append(((pa, sa, ea), (pb, sb, eb)))

print("EVIDENCE_LINES=%d" % len(lines))
print("EVIDENCE_BAD_SHAPE=%d" % len(bad_shape))
print("EVIDENCE_MULTI_MARKER=%d" % len(multi_marker))
print("EVIDENCE_MALFORMED_MARKER=%d" % len(malformed_marker))
print("EVIDENCE_RUNS=%d" % len(runs))
print("EVIDENCE_OVERLAP_PAIRS=%d" % len(overlaps))
for ln in bad_shape:
    print("OFFENDER_BAD_SHAPE %s" % ln)
for ln in multi_marker:
    print("OFFENDER_MULTI_MARKER %s" % ln)
for ln in malformed_marker:
    print("OFFENDER_MALFORMED_MARKER %s" % ln)
for (pid, start, end), ln in ordered:
    print("RUN %s %s %s" % (pid, start, end))
    print("RUN_LINE %s" % ln)
for a, b in overlaps:
    print("OVERLAP pid=%s[%s,%s] pid=%s[%s,%s]" % (a[0], a[1], a[2], b[0], b[1], b[2]))
EVIDENCEEOF

read_evidence() {
    "$PYTHON3" "$EVIDENCE_PY" "$LOG_PATH" > "$EVIDENCE_OUT" 2>/dev/null || fail "evidence reader failed"
}

ev() {
    # $1 = EVIDENCE_* key. Prints its value, or 0 if the reader never emitted it.
    _v=$(sed -n "s/^$1=//p" "$EVIDENCE_OUT" | tail -n 1)
    [ -n "$_v" ] || _v=0
    echo "$_v"
}

assert_no_torn_writes() {
    # $1 = phase label used in the failure message.
    _phase="$1"
    _bad=$(ev EVIDENCE_BAD_SHAPE)
    _multi=$(ev EVIDENCE_MULTI_MARKER)
    _malformed=$(ev EVIDENCE_MALFORMED_MARKER)
    if [ "$_bad" -ne 0 ] || [ "$_multi" -ne 0 ] || [ "$_malformed" -ne 0 ]; then
        log_err "offending lines (verbatim):"
        grep -E '^OFFENDER_' "$EVIDENCE_OUT" >&2
        fail "$_phase: the shared log contains torn or interleaved writes -- ${_bad} line(s) with no stamp() prefix, ${_multi} line(s) carrying two fire markers, ${_malformed} marker line(s) with incomplete notice JSON. This is a REAL GAP, not a harness artifact: record it as an issue, do not report a pass."
    fi
}

# --- install the shim via the real CLI, pointed only at the temporary world ------
SHIM_PATH=$("$PYTHON3" "$CACHE_ROOT/1.1.0/scripts/sweep_shim.py" --install \
    --cache-root "$CACHE_ROOT" --durable-dir "$DURABLE_DIR") || fail "shim install failed"
[ -f "$SHIM_PATH" ] || fail "installed shim not found at reported path: $SHIM_PATH"
echo "shim installed at $SHIM_PATH (cache root baked in: $CACHE_ROOT)"

# Anchored on this run's unique mktemp directory NAME rather than its absolute path,
# so the match survives any prefix normalization between the shell's value and the
# one `pathlib.Path` hands the shim's exec. Still unique to this run, and still
# scoped strictly inside the temporary world -- nothing outside it can ever match.
WRAPPER_PATTERN="$WORK_NAME/cache/1.1.0/skills/backend-sweep/lv-sweep-run.sh"

write_plist() {
    # $1 = plist path, $2 = label.
    cat > "$1" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>$2</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/sh</string>
    <string>$SHIM_PATH</string>
    <string>$CACHE_ROOT/1.1.0</string>
    <string>$PYTHON3</string>
    <string>$LOG_PATH</string>
  </array>
  <key>StartInterval</key>
  <integer>$START_INTERVAL</integer>
</dict>
</plist>
PLISTEOF
}

write_plist "$PLIST_A" "$LABEL_A"
write_plist "$PLIST_B" "$LABEL_B"

echo "registering launchd label: $LABEL_A"
launchctl load "$PLIST_A" || fail "launchctl load failed for $PLIST_A"
LOADED_A=1

# =================================================================================
# PHASE 1 -- INTERRUPTION
# =================================================================================
echo ""
echo "=== phase 1: interruption ==="

# Wait for a genuine scheduled fire to be RUNNING. The healthy path stamps only
# after the payload returns, so a running fire is invisible in the log -- process
# detection is the only way to catch one mid-run. The content-only rule governs
# EVIDENCE, not process detection; no pass/fail decision below is made from `ps`.
WRAPPER_PID=""
elapsed=0
while [ "$elapsed" -lt "$WRAPPER_APPEAR_TIMEOUT" ]; do
    WRAPPER_PID=$(pgrep -f "$WRAPPER_PATTERN" 2>/dev/null | head -n 1)
    [ -n "$WRAPPER_PID" ] && break
    sleep "$POLL_INTERVAL"
    elapsed=$((elapsed + POLL_INTERVAL))
done

if [ -z "$WRAPPER_PID" ]; then
    # Distinguish "the scheduler never fired" from "fires happened but detection
    # missed them" -- these need different fixes and must not be reported as one.
    read_evidence
    _seen=$(ev EVIDENCE_RUNS)
    if [ "$_seen" -gt 0 ]; then
        log_err "note: ${_seen} fire(s) DID complete and stamp the log during the window -- the scheduler fired, but pgrep never matched the running wrapper. That is a harness detection defect, not a finding about the shim."
        grep -E '^RUN_LINE ' "$EVIDENCE_OUT" >&2
    else
        log_err "note: the log holds no completed fire either -- the scheduler appears not to have fired at all."
    fi
    fail "inconclusive: no scheduled fire was observed running within ${WRAPPER_APPEAR_TIMEOUT}s, so there was nothing to interrupt. A run in which the scheduled fire never happened is reported as inconclusive, never as a pass."
fi
echo "observed a running scheduled fire after ${elapsed}s -- wrapper pid $WRAPPER_PID"

# Baseline the fires already complete BEFORE the kill, so the assertion after it is
# about a genuinely LATER fire and not about one that finished while we were
# polling. Baselining is by marker CONTENT (the pid/start/end triples), not by count.
read_evidence
BASELINE_RUNS="$WORK/baseline-runs.txt"
grep -E '^RUN ' "$EVIDENCE_OUT" | sort > "$BASELINE_RUNS"
BASELINE_RUN_COUNT=$(ev EVIDENCE_RUNS)
echo "fires complete before the interruption: $BASELINE_RUN_COUNT"

# Kill the resolved wrapper's exec mid-payload. The UAT text explicitly permits
# this, in place of chasing the microsecond window inside the shim between
# `--newest` resolution and `exec`.
kill "$WRAPPER_PID" 2>/dev/null
sleep 2
if kill -0 "$WRAPPER_PID" 2>/dev/null; then
    kill -9 "$WRAPPER_PID" 2>/dev/null
    sleep 1
fi
if kill -0 "$WRAPPER_PID" 2>/dev/null; then
    fail "could not kill the running wrapper (pid $WRAPPER_PID) -- the interruption case was not actually exercised."
fi
echo "interrupted wrapper pid $WRAPPER_PID mid-payload (killed while its sweep_entry.py was still sleeping)"
# The orphaned python child sleeps out its remaining seconds and then dies writing
# to a closed pipe. It can never reach the log -- only the wrapper's `stamp()` opens
# it -- so it is deliberately not chased here.

# The interrupted fire must have left nothing behind for the next one: no lockfile
# anywhere in the durable home or the cache root, and no partial line in the log.
STRAY=$(find "$DURABLE_DIR" "$CACHE_ROOT" -name '*.lock' -o -name '*.lck' -o -name '*.pid' 2>/dev/null)
if [ -n "$STRAY" ]; then
    log_err "$STRAY"
    fail "the interrupted fire left lock/pid state behind -- a subsequent fire could trip on it."
fi
read_evidence
assert_no_torn_writes "phase 1 (immediately after the interruption)"
echo "no lockfile, pidfile or partial log line survived the interruption"

# A LATER genuine fire must now resolve and stamp a COMPLETE line.
echo "waiting for a later scheduled fire to resolve and complete (up to ${POST_KILL_TIMEOUT}s)..."
NEW_RUN=""
elapsed=0
while [ "$elapsed" -lt "$POST_KILL_TIMEOUT" ]; do
    read_evidence
    # A "new" fire is one whose pid/start/end triple was NOT in the pre-kill
    # baseline -- identity by marker CONTENT, never by count or position.
    NEW_RUN=$(grep -E '^RUN ' "$EVIDENCE_OUT" | sort | comm -13 "$BASELINE_RUNS" - | head -n 1)
    [ -n "$NEW_RUN" ] && break
    sleep "$POLL_INTERVAL"
    elapsed=$((elapsed + POLL_INTERVAL))
done

if [ -z "$NEW_RUN" ]; then
    fail "inconclusive: no fire completed in the ${POST_KILL_TIMEOUT}s after the interruption. Either the scheduler stopped firing, or the interrupted fire DID leave something the next fire tripped on -- inspect $LOG_PATH before concluding. Reported as inconclusive, never as a pass."
fi
read_evidence
assert_no_torn_writes "phase 1 (after the recovery fire)"
echo "OK: a later scheduled fire resolved and stamped a complete line after the interruption:"
grep -E '^RUN_LINE ' "$EVIDENCE_OUT" | tail -n 1
echo "phase 1 PASSED -- an interrupted fire left no partial state, and the next fire completed normally."

# =================================================================================
# PHASE 2 -- OVERLAP
# =================================================================================
echo ""
echo "=== phase 2: overlapping scheduled fires ==="
echo "registering a SECOND launchd label against the same shim and the same log: $LABEL_B"
echo "(one label cannot overlap itself -- launchd never runs two instances of a single label concurrently)"
launchctl load "$PLIST_B" || fail "launchctl load failed for $PLIST_B"
LOADED_B=1

echo "waiting for two fires whose live intervals overlap (up to ${OVERLAP_TIMEOUT}s)..."
OVERLAP_PAIRS=0
elapsed=0
while [ "$elapsed" -lt "$OVERLAP_TIMEOUT" ]; do
    read_evidence
    OVERLAP_PAIRS=$(ev EVIDENCE_OVERLAP_PAIRS)
    [ "$OVERLAP_PAIRS" -ge 1 ] && break
    sleep "$POLL_INTERVAL"
    elapsed=$((elapsed + POLL_INTERVAL))
done

read_evidence
assert_no_torn_writes "phase 2 (overlapping fires)"

OVERLAP_PAIRS=$(ev EVIDENCE_OVERLAP_PAIRS)
TOTAL_RUNS=$(ev EVIDENCE_RUNS)
if [ "$OVERLAP_PAIRS" -lt 1 ]; then
    fail "inconclusive: ${TOTAL_RUNS} fire(s) completed but no two of them had overlapping live intervals within ${OVERLAP_TIMEOUT}s, so the concurrent case was never actually exercised. Reported as inconclusive, never as a pass. Log: $LOG_PATH"
fi

echo "OK: overlapping fires observed (${OVERLAP_PAIRS} overlapping pair(s) among ${TOTAL_RUNS} completed fire(s)):"
grep -E '^OVERLAP ' "$EVIDENCE_OUT"
echo ""
echo "every completed fire's stamped line, verbatim:"
grep -E '^RUN_LINE ' "$EVIDENCE_OUT"

echo ""
echo "PASS: a scheduled fire killed mid-payload left no lockfile, no pidfile and no partial log line, and the next genuine fire resolved and completed normally; two genuinely overlapping scheduled fires each resolved --newest independently and each stamped its own complete, uninterleaved line into the shared log. All evidence read from line CONTENT (embedded pid/start/end markers), never from line count or position."
exit 0
