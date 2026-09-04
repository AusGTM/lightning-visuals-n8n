# Operator-chair walk — brief (P1.2)

**Written:** 2026-08-30
**For:** the operator, running in **Claude Desktop**, driving the **installed plugin**
**Prereqs:** both now met — `origin/master` at `18f30af`, installed plugin cache at `0.28.6`

---

## Why this run exists

GRANT-01 is already ticked. Walk run 3 (2026-08-29) carried a batch ingest → enrich → HubSpot
write under one grant and created contact `348695309760`. The composition is proven.

What is **not** proven is the thing the whole v1.1 milestone exists for. Both prior limitations
were recorded rather than waived (`53-WALK-RECORD-2.md` § Verdict):

| # | Limitation | Status now |
| --- | --- | --- |
| 1 | All three walks ran from **Claude Code with a terminal**, not the operator's chair | **STILL OPEN — this is what this run closes** |
| 2 | All three ran the **repo**, not the installed plugin | **CLOSED** — installed plugin is at 0.28.6 |
| 3 | FINDING C (written_records missed the contacts write) | **CLOSED** — fixed as bug_004, plugin 0.28.2 |

**G-2 — the original client blocker, "the operator cannot do this unaided" — has still never
been disproven by an actual operator.** That is the only question this run answers. Everything
else about the flow already works.

So the bar is not "did it work". It is: **did YOU do it, from Desktop, without a terminal and
without an admin step.** If at any point you need a terminal, that is the finding — stop and
record it. A walk that succeeds only because someone dropped to a shell has failed.

---

## Before you start — pick a FRESH record

Run 3 already created `348695309760` from
`https://www.linkedin.com/in/joshua-fusco-481309247/`.

**Do not reuse that URL.** A record that already exists is an UPDATE, and an update has an
`hsObjectId`, so it sails through the write-safety gate on the id allowlist. That skips the
exact thing worth testing.

The create path is the interesting one because the shared write-safety gate is:

```js
if (!allowedDomains.length && !allowedIds.length) return false;  // empty allowlist denies everything
if (hsObjectId && allowedIds.indexOf(String(hsObjectId)) !== -1) return true;
if (domain && allowedDomains.indexOf(String(domain).toLowerCase()) !== -1) return true;
return false;
```

A record that does not exist yet **has no `hsObjectId`**, so it can only be allowlisted by
DOMAIN — and a contact sourced from a LinkedIn profile with no email may have no domain either.
Run 3 showed `allow_create` carried it. Confirming that from Desktop, on a record the system has
never seen, is worth the one write.

**Pick one new LinkedIn profile URL you are willing to have created in HubSpot.** Write it here
before you start:

```
Record for this walk: ______________________________________________
```

---

## The walk — steps 2 to 7

Step 1 is already done (D-59-01). All of these run from Desktop. **No terminal at any point.**

### 2. Ask the plugin whether it is set up
Expected: it says write grants are **enabled**.

### 3. Open a write grant over 1–2 records you are willing to have written
Check all of:
- [ ] it names the **lane**, the **records**, and whether **creates are included**
- [ ] cost figures are plausible, and the **rate table's age** is shown
- [ ] it says the figure **discloses rather than prevents**, and that the remaining monthly
      allowance is **not yet checked**
- [ ] there is exactly **one** yes

### 4. Send the batch
- [ ] you are **NOT** asked for an arming phrase
- [ ] the grant states plainly that it enables enrichment **and writes to HubSpot**, non-blocking

**Do not** look for the old "authorized before the enriched preview existed" sentence — that text
was retired by D-59-07.

- [ ] at the end of the run, something lists **the records actually written**

That last one used to be absent, and its absence was FINDING C. It is now fixed (bug_004), so
**expect it to be PRESENT** — a `written_records-<run_id>.json` naming what landed. If it is
missing or reports `not_written` for a run that wrote, that is a regression and the most
important thing you will find today.

### 5. Revoke
- [ ] the next send **refuses by name**
- [ ] a dispatch **already running** finishes its chunks rather than stopping
      (this is re-scoped GRANT-05 behaviour, **not** a bug)

### 6. Open a second grant covering a record NOT in the first, then attempt a send for a record outside it
- [ ] refused **by name**, and refused **before anything is armed**

### 7. With the key unset, open a grant
- [ ] it names **the key, the file, and who sets it**
- [ ] it does **NOT** tell you to set a shell environment variable

Step 7 is a direct G-2 probe. Being told to export an env var is the failure mode this whole
milestone exists to remove.

---

## What it should cost

~4 n8n executions against the 2,500/month budget, ~2 provider credits, ~$0.07 Anthropic, and
**one live HubSpot write** on the record you named.

HubSpot has **no rollback** and ~700 live company records are reachable. The grant is what keeps
this bounded — do not widen it to "make something work". If a send is refused, the refusal is
data, not an obstacle.

---

## Recording the result

Append to `53-WALK-RECORD-2.md` as **WALK RUN 4**, or start `53-WALK-RECORD-3.md`. Either way
record, per step: what you did, what you saw **verbatim**, and pass/fail.

Two rules from the prior records that matter more than tidiness:

1. **Record what happened, not what should have happened.** Run 2's value was FINDING B, not its
   passes.
2. **A halt is a result.** Runs 1 and 2 both halted (step 5, then step 7) and both were worth
   more than a clean pass would have been. If this one halts, that is the finding — do not work
   around it and call it green.

If it completes cleanly from your chair with no terminal, **G-2 is disproven** and limitation 1
comes off the Verdict — the thing the v1.1 milestone was built to establish.
