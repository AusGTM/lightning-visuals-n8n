# Concurrency + interruption proof: the sweep launcher shim holds no lock and tears no log line

**Date:** 2026-09-03
**Harness:** `scripts/verify_sweep_shim_concurrency.sh`
**Host:** macOS (Darwin), `launchctl` and `pgrep` present and usable for the current user session.
**Closes:** must-have 13 in `63-VERIFICATION.md` (`⚠️ insufficient_spec`, `verification: backstop`),
and the single human-verification item in `63-UAT.md`.

## Why this proof exists

`63-VERIFICATION.md` verified 26 of 28 must-haves from tests and source. One could not be:

> Two overlapping scheduled fires produce two independent sweeps (shim holds no lock; evidence
> read from log line CONTENT, never count/position) — backstop-tier.

The plan itself tagged it `verification: backstop`. No test in
`operator-claude-plugin/tests/test_sweep_shim.py` interrupts a shim mid-run, and the three live
runs recorded in `63-SWEEP-SHIM-SCHEDULER-PROOF.md` fired **sequentially, 60 seconds apart, never
overlapping**. The truth had only ever been asserted by source-reading — no lockfile, no `mkdir`,
no `flock` in `_SHIM_TEMPLATE`, an append-only `stamp()`. Source-reading is presence, not
behaviour. This harness supplies the behaviour.

It is a **sibling** of `scripts/verify_sweep_shim_scheduler.sh`, which proves a different thing
(a genuine scheduled fire resolves the newest install, and follows a simulated update). That file
is 63-02's committed proof artifact and was not modified (`git diff --stat` on it: empty).

## Two design decisions, and why

**Two launchd labels, not one.** launchd never runs two instances of a single label concurrently
— a job still running when its `StartInterval` elapses has the tick coalesced, not doubled. A
same-label schedule therefore *cannot* produce overlapping fires however long its payload runs.
The harness registers two uniquely-labelled jobs (`…<pid>.a`, `…<pid>.b`) against the **same
installed shim** and the **same log**. With both on a 60s `StartInterval` and a 90s payload, any
two fires start within one interval of each other and each outlives that interval, so overlap is
**structural, not lucky**.

**The sleep lives in the neutralized `sweep_entry.py` payload, not in a planted wrapper.** This is
a deliberate deviation from the pause-handoff's "plant a fake wrapper that sleeps" sketch, and it
is strictly stronger. The UAT names **`stamp()`'s append target** as the thing that must not tear,
and `stamp()` is the *shipped* `lv-sweep-run.sh`'s function. A planted wrapper would have exercised
a stub's appender instead of the real one. Here the shipped shim and the shipped wrapper both run
**unmodified**; only the payload they eventually invoke is stubbed.

## Evidence is read by line CONTENT only

The plan prohibits deciding anything from line count or line position. Each fire's stubbed
`sweep_entry.py` embeds **its own pid and its own start/end epochs** into the notice headline it
reports, so the wrapper's own `stamp()` carries a per-fire identity into the shared log as text.
Every assertion below is made from that text:

- a line with no `stamp()` timestamp prefix is a headless fragment → torn write;
- a line carrying **two** fire markers is two appends interleaved into one physical line;
- a marker line whose notice JSON is not intact end to end is a partial write;
- **overlap** is decided by comparing two fires' embedded intervals
  (`start_B < end_A && start_A < end_B`), never by where their lines landed.

Line *order* between two concurrent fires' stamp sequences is expected and is not a failure. Only
intra-line tearing is.

The evidence reader was self-checked against three crafted logs before the live run: a clean
two-fire log (0 offenders, 1 overlap pair), a deliberately torn log (caught all three offender
classes — headless fragment, two markers on one line, truncated JSON), and a sequential log
(0 offenders, **0** overlap pairs, i.e. inconclusive rather than pass).

## What was run, and the result

| Run | Labels | Outcome | Exit | Post-run `launchctl list` residue |
|---|---|---|---|---|
| 1 | `com.lightningvisuals.sweep-shim-conc.35105.{a,b}` | **inconclusive** — see below | 1 | 0 |
| 2 (recorded run) | `com.lightningvisuals.sweep-shim-conc.51374.{a,b}` | **PASS** | 0 | 0 |

### Run 1 was inconclusive, and is recorded rather than discarded

Run 1 reported *"no scheduled fire was observed running within 240s, so there was nothing to
interrupt"* and exited 1. **This was a harness detection defect, not a finding about the shim.**

macOS `$TMPDIR` ends in `/`, so `mktemp -d "${TMPDIR}/sweep-shim-conc.XXXXXX"` yields a path
containing `//`. The shim execs the wrapper with the root `sweep_shim.newest_install_root()`
returned — a `pathlib.Path`, which **collapses `//` to `/`**. The `pgrep -f` pattern built from
the un-normalized shell value could therefore never match the running wrapper, and phase 1 waited
out its timeout while fires were happening. The scheduler proof never hit this because it uses no
`pgrep`.

Three fixes landed before run 2: `$WORK` is canonicalized immediately after `mktemp`; the pgrep
pattern is anchored on the unique mktemp directory **name** so it survives any prefix
normalization (still scoped strictly inside the temporary world); and an appear-timeout now
reports whether completed fires exist in the log, so *"the scheduler never fired"* and *"fires
happened but detection missed them"* can never again be reported as one thing. The corrected
pattern was verified against a real running wrapper before run 2.

Run 1's teardown was clean — `launchctl` confirmed zero residue under the prefix on both runs.

### Recorded run (run 2) — verbatim evidence

**Labels used:** `com.lightningvisuals.sweep-shim-conc.51374.a` and `…51374.b`

**Phase 1 — interruption.** A genuine scheduled fire was detected running 60s after the job was
loaded (wrapper pid `54714`) and killed **mid-payload**, while its `sweep_entry.py` was still
sleeping — the UAT text explicitly permits killing *"the resolved wrapper's exec"* in place of
chasing the microsecond window inside the shim between `--newest` resolution and `exec`. Zero
fires had completed before the kill, so the assertion that follows is about a genuinely later
fire, identified by its marker content and not by a count.

After the kill, the harness confirmed:

- no `*.lock`, `*.lck` or `*.pid` anywhere under the durable home or the cache root;
- no headless, double-markered or truncated line anywhere in the log.

A later genuine scheduled fire then resolved and stamped a complete line:

```
[2026-09-03T13:33:35+1000] [{"headline": "SWEEP_CONC pid=55876 start=1788406325 end=1788406415"}]
```

**Phase 2 — overlap.** The second label was loaded against the same shim and the same log. Three
fires completed in total; two of them overlapped:

```
OVERLAP pid=59099[1788406476,1788406566] pid=59142[1788406477,1788406567]
```

Fire `59099` was live for epochs 1788406476–1788406566; fire `59142` for 1788406477–1788406567.
The two intervals overlap by **89 of their 90 seconds** — these fires were concurrent for
essentially their whole duration, not merely adjacent. Each resolved `--newest` independently and
each stamped its own complete line:

```
[2026-09-03T13:33:35+1000] [{"headline": "SWEEP_CONC pid=55876 start=1788406325 end=1788406415"}]
[2026-09-03T13:36:06+1000] [{"headline": "SWEEP_CONC pid=59099 start=1788406476 end=1788406566"}]
[2026-09-03T13:36:08+1000] [{"headline": "SWEEP_CONC pid=59142 start=1788406477 end=1788406567"}]
```

Offender counts across the whole log at both assertion points: **0** lines with no `stamp()`
prefix, **0** lines carrying two markers, **0** marker lines with incomplete notice JSON.

**Harness exit code:** `0`.

**Teardown / independent read:** the harness's own trap printed
`teardown confirmed: no job carrying prefix 'com.lightningvisuals.sweep-shim-conc' remains`.
SEPARATE commands run after the harness process exited confirmed the same from outside it:

```
$ launchctl list | grep -c "com.lightningvisuals.sweep-shim-conc"
0
$ launchctl list | grep -i lightningvisuals
(no output)
```

No temporary work directory survived (`ls -d "$TMPDIR"sweep-shim-conc.*` → none).

### Cost — explicit statement

- **Zero network calls.** Every version directory's `sweep_entry.py` is the stub above: `time.sleep`
  plus one `print`. No HTTP client, no socket, no DNS lookup.
- **Zero provider credits.** No ZoomInfo/Apollo/Lusha/Anthropic call is reachable from the stub or
  from `lv-sweep-run.sh`'s path for a stubbed `sweep_entry.py`.
- **Zero n8n executions.** Nothing in the harness or the real wrapper it drives posts to any n8n
  webhook; the real `sweep_entry.py` (which does) is replaced by the stub in every version
  directory.
- **Zero HubSpot writes.** No HubSpot credential, API key or portal ID is referenced anywhere.
- **Zero crontab contact** (D-63-03). `grep -v '^\s*#' scripts/verify_sweep_shim_concurrency.sh |
  grep -c crontab` reads `0`. Only uniquely-labelled temporary launchd agents, both torn down.
- **Zero contact with the real plugin cache root.** The harness builds and destroys its own
  `mktemp -d` world.

Side effect on the host, as with the scheduler proof: one macOS Notification Center banner per
completed fire, because the real `lv-sweep-run.sh`'s `banner()` posts the stub's headline. That is
the trigger's own delivery mechanism working, not a defect of the proof.

## What this proves, and what it does NOT prove

**Proves,** under genuine scheduler fires rather than interactive invocations:

- A fire killed mid-payload leaves **no lockfile, no pidfile and no partial log line** — the next
  genuine fire resolves and completes normally, tripping on nothing.
- **Two genuinely overlapping fires** (89s of concurrent life) each resolve `--newest`
  independently and each append a **complete, uninterleaved** line to the shared log. The shim
  holds no lock and the wrapper's `stamp()` does not tear under concurrency at this payload size.

**Does NOT prove**, stated rather than left implied:

- **Nothing about append atomicity at arbitrary line sizes.** `stamp()`'s writes here are short
  (a timestamp plus a ~70-character notice JSON), comfortably inside the single-`write()` append
  guarantee. A future payload emitting a much larger single stamp — a multi-kilobyte notice dump —
  is outside what this run observed and would need its own evidence.
- **Nothing about concurrency beyond two fires.** Two labels were used. Three or more simultaneous
  fires were not exercised.
- **Nothing about this machine's already-installed version directories,** for the same reason the
  scheduler proof records: this ran against a synthetic, isolated cache root. The one-time admin
  re-point documented in `SWEEP-CRON-TEMPLATE.md` remains the mechanism that reaches a real
  pre-existing schedule.

## Harness re-run instructions

```
./scripts/verify_sweep_shim_concurrency.sh
echo "rc=$?"
```

Roughly 8-12 minutes of wall time (measured run 2: ~10 minutes), because it waits on real 60s
scheduler ticks with a 90s payload. Run it in the background — a foreground `sleep` of that length
is blocked in this environment. Do not shorten `START_INTERVAL` below 60: a sub-minute interval
stops being a representative scheduled fire. Do not shorten `PAYLOAD_SLEEP` below `START_INTERVAL`
either — the overlap in phase 2 depends on each fire outliving the interval.
