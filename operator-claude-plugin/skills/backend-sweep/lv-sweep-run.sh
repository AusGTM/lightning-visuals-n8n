#!/bin/sh
set -u

# LV backend sweep trigger. No LLM in this path, no credential that can expire --
# this wrapper runs sweep_entry.py directly with the python it is handed. Every path
# that is not the single healthy stamp below is loud: non-zero exit and a banner.
#
# Three positional arguments, in order: $1 the plugin root (the directory containing
# both scripts/ and skills/), $2 the python interpreter with this plugin's
# requirements.txt installed, $3 the log path. See SWEEP-CRON-TEMPLATE.md for how a
# schedule supplies them.

banner() {
    /usr/bin/osascript -e "display notification \"$1\" with title \"LV Backend Sweep\""
}

if [ "$#" -ne 3 ]; then
    banner "LV backend sweep: cannot run - wrong number of arguments"
    exit 1
fi

LOG="$3"

stamp() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*" >> "$LOG"
}

# Staleness self-check (D-63-02): loud, never refusing. A third state alongside
# "healthy" and "found notices" below — the sweep always runs; this only signals
# whether the code about to run is the newest installed version. $1 is the root THIS
# invocation is actually running from, so its parent IS the cache root -- no baked
# cache-root value is needed here (unlike the shim, which bakes one at install time
# because it runs before any root is known).
NEWEST_ROOT=$("$2" "$1/scripts/sweep_shim.py" --newest --cache-root "$(dirname "$1")")
STALE_RC=$?

if [ "$STALE_RC" -eq 0 ] && [ -n "$NEWEST_ROOT" ]; then
    if [ "$1" != "$NEWEST_ROOT" ]; then
        stamp "sweep running from $1, newest installed is $NEWEST_ROOT"
        banner "LV backend sweep is running an old version - ask the admin to check the log"
    fi
else
    stamp "could not check sweep staleness (resolver exit $STALE_RC)"
fi

OUT=$(cd "$1" && "$2" scripts/sweep_entry.py 2>&1)
RC=$?

if [ "$RC" -ne 0 ]; then
    stamp "sweep exited $RC: $OUT"
    banner "LV backend sweep could not run - ask the admin to check the log"
    exit "$RC"
fi

COUNT=$("$2" -c '
import json, sys
try:
    d = json.loads(sys.argv[1])
    print(len(d) if isinstance(d, list) else -1)
except Exception:
    print(-1)
' "$OUT")

if [ "$COUNT" = "-1" ]; then
    stamp "sweep returned unreadable output: $OUT"
    banner "LV backend sweep returned something unreadable - ask the admin to check the log"
    exit 1
fi

if [ "$COUNT" = "0" ]; then
    stamp "LV sweep ran, backend healthy, no notices."
    exit 0
fi

stamp "sweep found $COUNT notice(s)"
stamp "$OUT"

HEADLINES=$("$2" -c '
import json, sys
d = json.loads(sys.argv[1])
for n in d:
    h = n.get("headline") or ""
    if h:
        print(h)
' "$OUT")

printf '%s\n' "$HEADLINES" | while IFS= read -r HEADLINE; do
    [ -n "$HEADLINE" ] || continue
    ESCAPED=$(printf '%s' "$HEADLINE" | sed 's/\\/\\\\/g; s/"/\\"/g' | cut -c1-200)
    banner "$ESCAPED"
done

stamp "posted $COUNT notification(s)"
exit 0
