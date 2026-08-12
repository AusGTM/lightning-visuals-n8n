# Hardware-vendor hard veto keys off a boolean almost nothing populates

**Found:** 2026-08-12, Phase 47 Plan 04 armed window, from Simtech LED (`18047161864`).
**Type:** rubric / data-model inconsistency. Not a Phase 47 defect — Phase 47's outcome for
Simtech is correct under the rules as they are currently written.

## What happens

The hardware-vendor hard veto fires on `lv_is_hardware_vendor === true`, in both the
deployed `Decide Company Action` node and `src/icp_scoring.py`. It does **not** consider
`lv_org_type == "hardware_vendor"`.

Live portal count: **1 of 66 companies has `lv_is_hardware_vendor` populated at all** —
Supertech Electronics (`15274105699`, `true`, Tier D).

So two hardware vendors land on opposite sides of a hard veto:

| Company | `lv_org_type` | `lv_is_hardware_vendor` | Veto | Tier |
|---|---|---|---|---|
| Supertech Electronics `15274105699` | `hardware_vendor` | `true` | fires | D |
| Simtech LED `18047161864` | `hardware_vendor` | *(null)* | does not fire | **B** |

Simtech was researched in Phase 47 and classified `hardware_vendor` with evidence (an LED
display manufacturer). Its veto did not fire, so it now reads Tier B — a hardware vendor
sitting in the same band as mid-tier racing clubs.

## Why it matters

`lv_org_type` is the field the enrichment pipeline actually writes; `lv_is_hardware_vendor`
is one nothing in the current pipeline populates. A veto keyed to the unpopulated field is
effectively unreachable for every record enrichment touches — the rule exists but cannot
fire, which is the same shape as the `Company Gate` defect scoped in Phase 47.5: *a rule
that is correct on paper and unreachable in practice.*

The Phase 47 handover expected Simtech to be "a genuine hard veto, correct under D-16". It
was not, and that expectation was wrong about the mechanism rather than the company.

## Decide, don't just patch

This is a rubric question and should be answered explicitly, not silently fixed:

1. Should the hardware veto fire on `lv_org_type == "hardware_vendor"` as well as / instead
   of the boolean?
2. If yes, does it apply retroactively to Simtech (currently Tier B) and to any other record
   Phase 48 classifies `hardware_vendor`?
3. Same question for `lv_is_gambling_operator` vs `lv_org_type == "gambling_operator"` —
   likely the identical shape (gambling is a graduated deduction, not a veto, but it keys off
   the same style of boolean). Check before assuming.

Whatever is decided must land in all three scoring engines together — that parity rule is
Phase 46's, and `46-ENGINE-INVENTORY.md` lists them.

## Pointers

```
n8n/wf_enrichment_cloud.json    node "Decide Company Action": isHardwareVendor === true
src/icp_scoring.py              hard_vetoes.hardware_vendor
config/icp_scoring.yaml         hard_vetoes.hardware_vendor.reason
.planning/phases/47-veto-remediation/47-RUN-REPORT.md   § "Records legitimately not in a real tier"
```

Related: [[Phase 47.5 — Veto Recompute Path]]
(`.planning/phases/47.5-veto-recompute-path/47.5-CONTEXT.md`), same "unreachable rule" class.
