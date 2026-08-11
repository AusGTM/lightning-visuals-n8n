# Phase 45: Burn-Rate Alarm - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-10
**Phase:** 45-Burn-Rate Alarm
**Areas discussed:** Todo folds, Rate sample + projection, Allowance plumbing, Threshold + repeat policy, Floor refusal shape

---

## Todo folds

| Option | Description | Selected |
|--------|-------------|----------|
| Cadence floor | runtime-cadence-has-no-budget-floor — prevention to the alarm's detection | ✓ |
| Sweep lookback window | fixed 100-row page → time-windowed; same plumbing the alarm needs | ✓ |
| Crontab versioned path | install-side; cron install out of milestone scope | |

---

## Rate sample + projection

**Q1 — How should the burn rate be sampled?**

| Option | Description | Selected |
|--------|-------------|----------|
| 24h target, honest span | Rate over the actually observed span; notice states it; shrunken window named | ✓ |
| Fixed 6h window | Faster reaction, but ~4 executions in 6h idle — noisy | |
| You decide | Lock the ALARM-02 principle, planning picks the number | |

**Q2 — Projection without a billing anchor?**

| Option | Description | Selected |
|--------|-------------|----------|
| Run-rate vs monthly allowance | Anchor-free `rate × 30d` vs allowance; amend ALARM-01 wording | ✓ |
| Config billing anchor day | More precise mid-cycle; one more key, wrong anchor silently mis-projects | |

**Q3 — What counts toward the rate?**

| Option | Description | Selected |
|--------|-------------|----------|
| Every execution | All workflows, all modes — what n8n bills; the runaway was sub-executions | ✓ |
| Exclude manual runs | Filters test noise, but would have shaved the runaway's own evidence | |

---

## Allowance plumbing

**Q1 — Where does the sweep get the allowance?**

| Option | Description | Selected |
|--------|-------------|----------|
| Plugin key + drift test | New plugin config key; repo test pins equality with execution_budget.yaml | ✓ |
| Read repo YAML directly | One physical source, but a filesystem dependency that can silently turn the alarm off | |
| You decide | Lock one-logical-source, planning picks plumbing | |

**Q2 — Missing allowance key: what refuses?**

| Option | Description | Selected |
|--------|-------------|----------|
| Condition-level notice | Burn-rate condition says "not watching the budget", names the key; rest of sweep runs | ✓ |
| Add to sweep capability row | Whole sweep refuses; a stuck lock would go unreported over a budget key | |

---

## Threshold + repeat policy

**Q1 — Fire threshold?**

| Option | Description | Selected |
|--------|-------------|----------|
| Configurable, default 1.0× | Idle ~4% of plan; real anomalies clear it by an order of magnitude | ✓ |
| Default 0.8× | Earlier warning; fires during legitimately heavy weeks | |

**Q2 — Burn continues — next sweep?**

| Option | Description | Selected |
|--------|-------------|----------|
| Re-notify while it persists | Active burn costs hourly; self-clearing via the windowed rate | ✓ |
| Once, then suppress | Quieter; a missed banner is an unwatched runaway | |

---

## Floor refusal shape

**Q1 — Which schedule changes does the floor bound?**

| Option | Description | Selected |
|--------|-------------|----------|
| Every trigger, every request | One rule; "hourly on all five" sums to 3,600/month while passing individually | ✓ |
| Sub-daily requests only | Fewer checks; misses the summed case | |

**Q2 — Conversational override of a floor refusal?**

| Option | Description | Selected |
|--------|-------------|----------|
| No — config is the override | Recommended: same posture as every other budget gate | |
| Override phrase allowed | Deliberate phrase lets one change through with the consequence restated | ✓ |

**Notes:** Operator selected the override against the recommendation — recorded as their
call. Agreed shape: arithmetic stated first, specific phrase, single-shot (never persists).

---

## Claude's Discretion

Notice wording; time-window and threshold key names; the override phrase's exact string;
drift-test mechanics.

## Deferred Ideas

Crontab versioned-path todo; email/Slack escalation; per-lane attribution; automatic
cadence throttling on alarm.
