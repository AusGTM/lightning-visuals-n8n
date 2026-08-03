---
name: backend-sweep
description: Run one unattended read of the HubSpot enrichment backend and report back only what needs a human's attention — a failed scheduled run, a credential or quota failure, a stuck lock, or a review backlog past its threshold — or nothing at all when the backend is healthy. This is the skill an unattended scheduled routine invokes on a cadence; the operator never needs to ask for it by name, though it can be run on demand as /operator-claude-plugin:backend-sweep to see exactly what the next unattended fire would report.
---

# Backend Sweep

> **Where commands run:** the one command below runs from the **plugin root** — the
> directory that contains both `scripts/` and `skills/`, i.e. two levels up from this
> SKILL.md. `cd` there first. When the plugin is installed (not a repo checkout), that is
> the versioned plugin-cache directory this file lives under.

**This skill reads. It changes nothing, ever.** Its entire job is to run the sweep
entrypoint and hand back exactly what it returns — nothing else. It names one script and
nothing beyond it. Do not extend this skill to also check something else, dispatch a
batch, retry a run, or arm anything — widening what this skill reaches is a NOTICE-05
violation, and `tests/test_sweep_read_only.py` exists to catch exactly that widening
before it ships.

## Steps

1. Run:

   ```
   python3 scripts/sweep_entry.py
   ```

   This prints one JSON value: a list of notice objects, or `[]`. There is nothing else
   to run and nothing else to check — the sweep already read everything it watches
   (`sweep_read.gather`) and already decided what fired (`sweep_conditions.evaluate`).
   If the config is missing the keys this capability needs, the same command prints a
   single admin-attributed notice saying so — it never raises, and it is not silence.

2. **If the list is `[]`, the whole answer is silence.** Say nothing further — do not
   report "backend healthy" or manufacture any other all-clear line. Silence IS the
   answer (NOTICE-04). Inventing a healthy-report line is exactly the noise that trains
   an operator, or an unattended cron wrapper's log, to start ignoring this sweep.

3. **If the list has one or more notice objects, hand them back verbatim** — each one's
   `headline`, `detail`, and `who_can_fix`. Do not summarise, merge, or reword them: they
   already carry the one-line banner budget and the full log detail, already attributed
   to the operator or an admin. Do not add advice of your own beyond what `detail`
   already says.

This skill never turns anything on or off, starts, stops, or retries a run, or writes to
any record — the same posture as `backend-status`, enforced the same way: nothing this
skill reaches has a code path to a mutation.
