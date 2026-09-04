---
phase: 54-single-pass-armed-dispatch
reviewed: 2026-08-27T03:58:51Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - n8n/code/reviewApply.js
  - n8n/code/reviewDecision.js
  - operator-claude-plugin/scripts/measure_dispatch.py
  - operator-claude-plugin/scripts/report_enrichment.py
  - operator-claude-plugin/scripts/write_grant.py
  - scripts/build_cloud_workflows.py
  - tests/n8n/reviewDecisionEndpoint.test.mjs
  - operator-claude-plugin/tests/test_enrich_skill_contract.py
  - operator-claude-plugin/tests/test_measure_dispatch.py
  - operator-claude-plugin/tests/test_report_enrichment.py
  - operator-claude-plugin/tests/test_watch_settle_reporting.py
  - operator-claude-plugin/tests/test_write_grant.py
  - operator-claude-plugin/skills/enrich-records/SKILL.md
  - operator-claude-plugin/skills/review-triage/SKILL.md
findings:
  critical: 0
  warning: 4
  info: 2
  total: 6
status: issues_found
---

# Phase 54: Code Review Report

**Reviewed:** 2026-08-27T03:58:51Z
**Depth:** standard
**Files Reviewed:** 14
**Status:** issues_found

## Summary

Phase 54 does five things: measures the G-3 execution saving against real n8n history
(read-only), names two previously-`unknown` report outcomes, extends `reviewApply.js` to
take an injectable field policy so `reviewDecision.js`'s contacts approve branch can reuse
the companies compare-and-set engine, deploys that change, and live-proves the clear
branch against one real contact. The mechanics of all five are sound: `reviewApply`'s third
parameter is additive and every pre-existing two-argument call site is untouched;
`reviewDecision.js` correctly threads `DEFAULT_CONTACT_POLICY`/`DEFAULT_COMPANY_POLICY`
and the matching provenance property by object type; `measure_dispatch.py` is genuinely
GET-only and never imports the arming module; the inline-module bundling in
`build_cloud_workflows.py` was swept for the exact "module referenced by inlined code but
not itself inlined" class of bug this phase already hit once (the `mergeContacts.js`
omission, `a0d0df5`) — no live-reachable second instance exists (the apparent gaps in the
`CONTACTS_TARGET` research/judge bundles are provably inert: the functions that would
reference the missing symbols are never called on that code path).

No Critical findings. Four Warnings, all concrete and traceable to this phase's own diff:
a dropped follow-up (twice) that leaves stale, actively wrong comments describing
pre-fix contacts-approve behavior in the one file whose own header calls itself "the
single source of truth"; a compare-and-set baseline gap this phase's own plan named and
handed to a later plan, which never landed it; an enum guard that the phase's comments
describe as symmetric across both policies but is a silent no-op for every contacts field;
and a self-contradictory operator-facing cost sentence ("worst case" next to "a floor")
introduced by this phase's own relabelling commit. Two Info-level documentation
inconsistencies round out the list.

## Warnings

### WR-01: Two stale comments in `build_cloud_workflows.py` still describe pre-54-03 contacts-approve behavior — one of them ships inside the deployed node's own code

**File:** `scripts/build_cloud_workflows.py:7215-7220` and `scripts/build_cloud_workflows.py:7049-7055`
**Issue:** 54-03-SUMMARY.md explicitly flagged this as a residual and told the next plan to
fix it: *"54-04 should update both the property list and the comment when it rebuilds the
workflow, or a future contacts candidate would compare against fields the fetch never
retrieved."* 54-04's rebuild (`a0d0df5`) touched only the two inlined Code-node bodies
(`Apply Review`, `Build Review Decision`); it did not touch either of these two spots, so
both still assert the old, now-false behavior:

- Line 7215-7220, **inside the `r"""..."""` jsCode literal for the `Build Review Decision`
  node** (the string opens at line 7209, right after `mergeContacts.js` was added to the
  inline list by this same phase's bug fix): *"A contacts APPROVE resolves to `no_candidate`
  and writes nothing... reviewApply's allowlist is the COMPANY policy's key set — handing
  it a contact candidate would drop every field as un-allowlisted."* Since 54-03,
  `reviewDecision.js`'s approve branch selects `DEFAULT_CONTACT_POLICY` for a contact
  (`n8n/code/reviewDecision.js:244`) and its no-candidate branch returns outcome `applied`
  (a real write), never `no_candidate` (`n8n/code/reviewDecision.js:253-276`). This text is
  in the string a Code-node editor in the n8n UI would read directly above jsCode that does
  the opposite of what it says.
- Line 7049-7055, governing why `REVIEW_CONTACT_PROPERTIES_CSV` deliberately omits the
  contacts field-policy keys: *"no contacts apply engine exists to compare against (see
  n8n/code/reviewDecision.js's header — a contacts approve resolves to `no_candidate`)."*
  Same stale premise — see WR-02, which is the live consequence of this comment's
  reasoning never being revisited.

**Fix:**
```python
# Replace 7215-7220 (and the analogous premise in 7049-7055) with the current, correct
# reasoning already stated in n8n/code/reviewDecision.js's own header (2026-08-27, Phase
# 54 Plan 03): a contacts approve now calls the SAME reviewApply engine as companies, keyed
# on DEFAULT_CONTACT_POLICY. It resolves to `applied` with a real write in the current
# deployment ONLY because the one candidate producer in this repo
# (`Decide Company Action`) never stages a contacts candidate -- not because the code
# forces `no_candidate`. State plainly that this is a live-shape fact ("today"), not a
# structural guarantee.
```

### WR-02: `REVIEW_CONTACT_PROPERTIES_CSV` still doesn't fetch `DEFAULT_CONTACT_POLICY`'s field keys — the compare-and-set baseline gap 54-03 named and handed off was never closed

**File:** `scripts/build_cloud_workflows.py:7060-7062`
**Issue:** `REVIEW_CONTACT_PROPERTIES_CSV` fetches only `hs_object_id, email, firstname,
lastname, jobtitle` plus the review-flag family and the provenance blob. Compare that
against `DEFAULT_CONTACT_POLICY`'s twelve keys
(`n8n/code/mergeContacts.js:47-60`): `email, phone, mobilephone, jobtitle,
lv_linkedin_url, seniority, lv_persona_group, city, state, country, hs_state_code,
hs_country_region_code`. Ten of the twelve are never fetched — `phone`, `mobilephone`,
`lv_linkedin_url`, `seniority`, `lv_persona_group`, `city`, `state`, `country`,
`hs_state_code`, `hs_country_region_code`.

This is the exact compare-and-set baseline 54-03's own reviewApply.js compares against
(`n8n/code/reviewApply.js:69-72`): `refetchedProperties[d.field]`. For any of the ten
unfetched fields, `refetchedProperties[field]` is always `undefined` regardless of the
record's real live value, which `reviewApply.js:70` normalizes to `null`
(`normalizedLive = liveValue === undefined ? null : liveValue`). If a future contacts
candidate's stored `current_value` for that field also happens to be `null` (the field was
blank when the candidate was frozen), the compare-and-set will see `null === null` and
treat the field as unchanged — even if a human has since manually entered a value on that
exact field. This is a genuine non-clobber bypass on the branch this phase built and
deployed: `reviewApply`'s whole reason for existing is to refuse a write when the live
record disagrees with the frozen baseline, and for ten of twelve contacts fields it cannot
see the live record at all.

Currently dormant — no live contacts candidate producer exists (the phase's own stated
residual), so no real candidate holds any of these ten fields today. But this was named,
in writing, as 54-04's job, and 54-04's own SUMMARY confirms its rebuild diff was "confined
to the two Code nodes that inline those modules" — `REVIEW_CONTACT_PROPERTIES_CSV` is a
plain Python string constant, not inlined jsCode, and was not part of that diff.

**Fix:**
```python
# scripts/build_cloud_workflows.py, mirroring REVIEW_DECISION_PROPERTIES_CSV's own
# pattern (line 7041-7043), which derives its set from _COMPANY_POLICY_FIELDS:
_CONTACT_POLICY_FIELDS = tuple(DEFAULT_CONTACT_POLICY.keys())  # or the config/
                                                                 # field_policy.yaml
                                                                 # `contacts` keys, same
                                                                 # discipline the company
                                                                 # set already uses
REVIEW_CONTACT_PROPERTIES_CSV = ",".join(dict.fromkeys(
    ("hs_object_id", "email", "firstname", "lastname", "jobtitle")
    + _REVIEW_FAMILY + ("lv_contact_enrichment_provenance",)
    + _CONTACT_POLICY_FIELDS))
```

### WR-03: reviewApply's ENUM GUARD is a silent no-op for every contacts field — Phase 54's "one engine, two policies" claim is not symmetric on this guard

**File:** `n8n/code/reviewApply.js:36-44, 76-80`; `n8n/code/hubspotEnums.generated.js`
**Issue:** `reviewApply.js`'s header (updated this phase) and `reviewDecision.js`'s header
both describe the reused engine as running "the SAME compare-and-set, staleness and enum
guards" against either policy's field set. The compare-and-set and staleness guards are
genuinely field-policy-agnostic. The enum guard is not: `normalizeEnumValue(d.field,
d.chosen_value)` (`n8n/code/reviewApply.js:76`) delegates to
`hubspotEnums.js:isEnumBound`, which checks membership in `COMPANY_ENUM_PROPERTIES`
(`n8n/code/hubspotEnums.generated.js`). That table's only keys are `industry`,
`lv_content_type`, `lv_country_region_normalized`, `lv_employee_band`, `lv_org_type`,
`lv_revenue_band` — six company-only properties. None of `DEFAULT_CONTACT_POLICY`'s
twelve fields (`email, phone, mobilephone, jobtitle, lv_linkedin_url, seniority,
lv_persona_group, city, state, country, hs_state_code, hs_country_region_code`) is a key
of that table, so `isEnumBound()` returns `false` for every one of them, and
`normalizeEnumValue` returns `{ok: true, value, reason: null}` unconditionally
(`n8n/code/hubspotEnums.js:95-96`) — the guard never runs.

Concretely: if a future contacts candidate producer stages a `seniority` (a plausible
HubSpot dropdown-shaped classification field, per `DEFAULT_CONTACT_POLICY`'s own
`system_owned` classification) or `country`/`state`/`hs_state_code`/
`hs_country_region_code` value that HubSpot's live schema would refuse, `reviewApply`
promotes it into `canonicalPatch` unguarded, and the failure surfaces as a live HubSpot
PATCH rejection instead of the deterministic, pre-flight refusal
(`invalid`/`refused`, REVIEW-05) that the same guard already provides for companies. This
is the identical failure shape BUG 28/29 fixed for the companies lane — silently
unreproduced for contacts, because no `CONTACT_ENUM_PROPERTIES` table exists.

Not exploitable today (no live contacts candidate producer, per the phase's own stated
residual — this mirrors known-issue #2), but it is a real gap in what "one engine, two
policies" actually delivers, and it is not disclosed anywhere the header comments claim
symmetric guard coverage.

**Fix:** Either generate a `CONTACT_ENUM_PROPERTIES` table (mirroring
`hubspotEnums.generated.js`'s company generator, scoped to the contacts object) and extend
`isEnumBound`/`normalizeEnumValue` to consult the right table by object type, or state
explicitly in `reviewApply.js`'s header that the enum guard is company-only today and
name it as a gap a contacts candidate producer must close before shipping.

### WR-04: `write_grant.py`'s Anthropic-spend sentence says "worst case" and "a floor" in the same breath

**File:** `operator-claude-plugin/scripts/write_grant.py:304-306`
**Issue:** The rendered operator-facing text reads: *"Anthropic model spend: **$X** worst
case — a floor from the dated rate table above, not a measurement."* "Worst case" means an
upper bound (the real cost should never exceed this figure); "a floor" means a lower bound
(the real cost is guaranteed to be at least this figure). The two cannot both be true of
the same number. "Worst case" predates this phase; "a floor from the dated rate table" was
added by this phase's own relabelling commit (`9990d2f`, Task 3) without reconciling the
two. `test_write_grant.py::test_the_anthropic_figure_is_labelled_projected_never_measured`
only asserts `"floor" in figures["block"].lower()` — it pins the contradiction rather than
catching it.

An operator reading this line cannot tell whether their real spend could exceed the
displayed dollar figure or is guaranteed to be at least it — the opposite intents point in
opposite directions on the one question a cost-disclosure sentence exists to answer.

**Fix:**
```python
# operator-claude-plugin/scripts/write_grant.py, pick one framing and drop the other:
lines += ["", f"Anthropic model spend: **{_usd(figures.get('anthropic_usd'))}** "
              f"— a projection from the dated rate table above, not a measurement "
              f"(this repo never reads back real Anthropic usage)."]
# (drop "worst case" entirely, or drop "a floor" and keep "worst case" -- whichever
# matches how config/cost_rates.json's anthropic_usd_per_record was actually derived)
```

## Info

### IN-01: `measure_dispatch.py`'s module docstring claims a call it never makes

**File:** `operator-claude-plugin/scripts/measure_dispatch.py:8`
**Issue:** The top-of-file docstring states the module "calls exactly two read-only
`executions_client` functions (`list_executions`, `get_execution`)". The code never calls
`get_execution` anywhere — confirmed by grep, and by the module's own, more accurate,
per-function docstring at line 49: *"Only calls `executions_client.list_executions` — no
`get_execution`, no arming call."* The behavior (genuinely read-only, GET-only, no arming
import) is correct; only the top-level summary overstates what the module touches.
**Fix:** Drop `, get_execution` from the top docstring's function list, or add a call site
if a future use needs one.

### IN-02: `review-triage/SKILL.md`'s rewritten `no_candidate` bullet overclaims permanence

**File:** `operator-claude-plugin/skills/review-triage/SKILL.md:122`
**Issue:** *"A contacts approve does **not** land here anymore"* is stated as an
unconditional, permanent fact. It is true only because no live contacts candidate producer
exists today (the phase's own residual, restated in 54-03/54-04's SUMMARYs as "every
contact that can reach the review queue today"). `reviewDecision.js:311-315` keeps
`no_candidate` reachable for a contact whose held candidate cannot be parsed
(`reviewApply`'s fail-closed path: `if (Object.keys(applied.clearPatch).length === 0)`) —
this is unreachable only because no producer stages a candidate to fail parsing, not
because the code forbids it.
**Fix:** Scope the sentence to the current live shape — e.g. "A contacts approve does not
land here today, because no contact currently in the review queue holds a candidate" —
rather than an unconditional "not anymore."

---

_Reviewed: 2026-08-27T03:58:51Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
