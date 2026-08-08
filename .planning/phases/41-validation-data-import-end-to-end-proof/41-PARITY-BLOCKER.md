# Operational defect: `HUBSPOT_PORTAL_ID` in `.env` is corrupted to `'!'`

> **RESOLVED 2026-08-08.** The operator fixed `.env`
> (`HUBSPOT_PORTAL_ID='22617666'`). Verified by running the sweep with **no** inline
> override: PASS, 67 assertions, 0 real findings. The standing scheduled guard runs again.


**Found:** 2026-08-08, attempting the parity sweep over the landed canary records.
**Severity:** HIGH operationally — the standing scoring-drift guard is currently inoperable.
**Not a code defect.** Every affected component behaved correctly. The `.env` value is wrong.

## Symptom

```
REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal (22617666). No API call made.
```

## Diagnosis

```
HUBSPOT_PORTAL_ID set: True | value: '!'
token set: True
```

The variable is present but holds the literal single character `!`. The private-app token
is fine — every other live call this session (record reads, batch updates, schema snapshot,
drift check, n8n reads and the deploy) worked against portal 22617666 without complaint,
because none of them consult `HUBSPOT_PORTAL_ID`.

`scripts/run_scoring_parity.py:141` compares it against `EXPECTED_PORTAL_ID = "22617666"`
(line 56) *before any network call* — the same fail-closed discipline the snapshot tool
uses. The guard is correct and did its job.

Likely cause: shell history expansion. An unquoted `!` in a double-quoted string is
consumed by bash history expansion, so a line like

    echo "HUBSPOT_PORTAL_ID=22617666!" >> .env

or an interactive edit containing `!` can leave the mangled value behind.

## Why this matters more than a one-off failure

`scripts/run_scoring_parity.py` is **the standing drift guard** for the scoring engine
(Phase 40 PARITY-01/PARITY-02, D-12's read-only scheduled tier). While this value is
corrupted, that guard refuses on every invocation. Scoring could drift portfolio-wide and
the harness designed to detect it would never execute a single assertion.

## The false-green guard worked — this is the good news

The run did **not** report a hollow pass. It wrote:

> `FAIL: zero assertions executed. A sweep that checked nothing must never report success
> (D-13) -- empty sample, missing credentials, portal mismatch, or every read raised.`

That is Phase 40's D-13 false-green guard catching exactly the class of failure it was
built for. A less careful harness would have reported `PASS: 0 mismatches` and been
believed.

## Earlier runs were NOT affected

Checked every committed parity report:

| Report | assertions_executed | verdict |
|---|---|---|
| `40-…/parity-report-20260806.json` | 1 | PASS (1 documented divergence) |
| `40-…/parity-report-final.json` | 1 | PASS (1 documented divergence) |
| `43-…/parity-report-20260807.json` | 1 | PASS |

All executed real assertions, so PARITY-01's verdict and 43-04's breakdown proof stand.
The corruption happened after 2026-08-07.

## Fix (operator — `.env` is permission-blocked to Claude)

Set the value correctly, quoting to defeat history expansion:

```
HUBSPOT_PORTAL_ID='22617666'
```

Then confirm:

```
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(repr(os.getenv('HUBSPOT_PORTAL_ID')))"
```

Expected: `'22617666'`. After that the parity sweep runs normally.

## Consequence for Phase 41

DATA-02's closure needs a parity sweep over the landed population. That sweep cannot run
until this is fixed — independent of the arm/release step. **Both are required to close
Phase 41**, and this one is a one-line `.env` correction rather than a live-write decision.

---

## Stopgap confirmed working (2026-08-08)

The corrupted `.env` value can be overridden per-invocation without editing `.env`:

```
HUBSPOT_PORTAL_ID=22617666 PARITY_SAMPLE_IDS=<ids> PARITY_REQUIRE_PROVENANCE=true \
  .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv(); import runpy; \
  runpy.run_path('scripts/run_scoring_parity.py', run_name='__main__')"
```

This is **not** defeating the guard. The guard exists to stop the harness running against
an *unexpected* portal; supplying `22617666` asserts the expected one, which is the portal
the private-app token already authenticates against (every other live call this session
proves that). It restores the intended check rather than skipping it.

Verified live on the landed canary records:

```
PASS (with 1 documented Needs Review divergence): 2 sampled companies checked,
every mismatch is the accepted oracle-vs-live-enum divergence (40-02), zero real findings.
assertions_executed: 2
```

| Record | live score/tier | oracle score | verdict |
|---|---|---|---|
| Melbourne Racing Club (9604614548) | 25 / C | 25 | match; tier label is the documented PARITY-01 divergence |
| Sportsbet (17861423879) | 0 / D | 0 | match |

**The permanent fix is still the one-line `.env` correction** — the scheduled read-only
sweep (D-12) loads `.env` and has no opportunity to pass an inline override, so the standing
drift guard stays inoperable until that value is corrected.
