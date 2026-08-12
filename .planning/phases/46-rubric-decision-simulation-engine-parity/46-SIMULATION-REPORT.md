# Phase 46 Rubric Simulation Report

- **Run (UTC):** 2026-08-11T07:59:01.631351+00:00
- **Portal:** 22617666
- **Rows simulated:** 66
- **Row-set cross-check vs `41-final-population.json`:** live=66, cross-check=66, symmetric difference=0 (sets match exactly)

This report shows, per company, three numbers: what HubSpot's live score/tier says today (**Live**), what the scoring oracle computes from that same live data under today's rubric (**Oracle-Current**, the control), and what the oracle would compute under the proposed rubric change (**Oracle-Proposed**, the effect being measured). Rows flagged `blank_org_type` or `false_veto` are shown exactly as HubSpot holds them today, with no projected or speculative column -- they read as Tier D or unknown for reasons unrelated to this weight change (Phase 47 clears the 17 false vetoes, Phase 48 enriches the 18 blank org types) and must not be misread as genuine outcomes of the proposed change.

**Applied overrides (never written to `config/icp_scoring.yaml` in this wave):**
- `base_score.org_type.individual_club_team` -> `15`
- `base_score.org_type.regulator` -> `-20`
- `graduated_deductions.gambling_operator` -> `None`

## Tier Distribution

| Scenario | A | B | C | D | Unscored | Needs Review |
|---|---|---|---|---|---|---|
| Live (HubSpot today) | 7 | 18 | 17 | 24 | 0 | 0 |
| Oracle -- current rubric | 7 | 17 | 16 | 7 | 17 | 2 |
| Oracle -- proposed rubric (club=15) | 7 | 31 | 2 | 7 | 17 | 2 |

## Sensitivity (club weight 10 / 20)

| Scenario | A | B | C | D | Unscored | Needs Review |
|---|---|---|---|---|---|---|
| Oracle -- proposed (club_10) | 7 | 31 | 2 | 7 | 17 | 2 |
| Oracle -- proposed (club_20) | 7 | 31 | 2 | 7 | 17 | 2 |

## Movement Summary (Oracle-Current -> Oracle-Proposed, primary scenario)

- Rows that change tier: 14 of 66
- Rows unchanged: 52

| lv_org_type | changed | unchanged |
|---|---|---|
| broadcaster | 0 | 10 |
| gambling_operator | 0 | 2 |
| governing_body_league | 0 | 8 |
| hardware_vendor | 0 | 1 |
| individual_club_team | 14 | 10 |
| other | 0 | 2 |
| regulator | 0 | 1 |
| unknown | 0 | 18 |

## Per-Company Detail

| Name | HubSpot ID | lv_org_type | Flags | Live Score/Tier | Oracle-Current Score/Tier | Oracle-Proposed Score/Tier | Sens. club=10 | Sens. club=20 |
|---|---|---|---|---|---|---|---|---|
| Melbourne Racing Club | 9604614548 | individual_club_team |  | 25/C | 25/Needs Review | 35/Needs Review | Needs Review | Needs Review |
| Australian Turf Club | 9605284724 | individual_club_team |  | 45/B | 45/B | 55/B | B | B |
| Tamworth Jockey Club | 9604738975 | individual_club_team |  | 35/C | 35/C | 45/B | B | B |
| Tweed Valley Jockey Club | 9604732797 | (blank) | blank_org_type, false_veto | 0/D | 0/Unscored | 0/Unscored | Unscored | Unscored |
| Sapphire Coast Turf Club (Bega Valley) | 9604794661 | (blank) | blank_org_type, false_veto | 0/D | 0/Unscored | 0/Unscored | Unscored | Unscored |
| Port Macquarie Race Club | 9605273630 | (blank) | blank_org_type, false_veto | 0/D | 0/Unscored | 0/Unscored | Unscored | Unscored |
| Victoria Racing Club | 9605291627 | individual_club_team |  | 45/B | 45/B | 55/B | B | B |
| Rockhampton Jockey Club | 9604732795 | (blank) | blank_org_type, false_veto | 10/D | 10/Unscored | 10/Unscored | Unscored | Unscored |
| Toowoomba Turf Club | 9605244179 | individual_club_team |  | 45/B | 45/B | 55/B | B | B |
| Brisbane Racing Club (BRC) | 9605284723 | individual_club_team |  | 45/B | 45/B | 55/B | B | B |
| Bunbury Turf Club | 9604738976 | (blank) | blank_org_type, false_veto | 0/D | 0/Unscored | 0/Unscored | Unscored | Unscored |
| South Australian Jockey Club | 9604753960 | individual_club_team |  | 35/C | 35/C | 45/B | B | B |
| Geraldton Turf Club | 9605284721 | individual_club_team |  | 35/C | 35/C | 45/B | B | B |
| Racing and Wagering Western Australia | 9605284722 | governing_body_league |  | 80/A | 80/A | 80/A | A | A |
| The Alice Springs Turf Club | 9604787229 | (blank) | blank_org_type, false_veto | 10/D | 10/Unscored | 10/Unscored | Unscored | Unscored |
| Racing Queensland | 9648957286 | governing_body_league |  | 80/A | 80/A | 80/A | A | A |
| Tasracing Pty | 9663194467 | governing_body_league |  | 80/A | 80/A | 80/A | A | A |
| Auckland Thoroughbred Racing | 9680571285 | individual_club_team |  | 45/B | 45/B | 55/B | B | B |
| Sunshine Coast Turf Club | 9680907342 | individual_club_team |  | 45/B | 45/B | 55/B | B | B |
| The Creek Agency | 9681041418 | individual_club_team |  | 35/C | 35/C | 45/B | B | B |
| Redcliffe Harness RC | 9680908136 | individual_club_team |  | 35/C | 35/C | 45/B | B | B |
| Cairns Jockey Club | 10021900550 | individual_club_team |  | 35/C | 35/C | 45/B | B | B |
| Entain | 10024564084 | gambling_operator |  | -70/D | -70/D | -50/D | D | D |
| Thoroughbred Park | 10152138518 | (blank) | blank_org_type, false_veto | 10/D | 10/Unscored | 10/Unscored | Unscored | Unscored |
| Harness Racing ACT | 10152245364 | individual_club_team |  | 35/C | 35/C | 45/B | B | B |
| Wyong | 10215097384 | (blank) | blank_org_type, false_veto | 10/D | 10/Unscored | 10/Unscored | Unscored | Unscored |
| Global Advance StreamLined | 12427415589 | broadcaster |  | 50/B | 50/B | 50/B | B | B |
| Scone Race Club | 14748141740 | individual_club_team |  | 35/C | 35/C | 45/B | B | B |
| Albury Racing Club | 14752422181 | individual_club_team |  | 35/C | 35/C | 45/B | B | B |
| Coffs Harbour Racing Club | 14752488879 | (blank) | blank_org_type, false_veto | 0/D | 0/Unscored | 0/Unscored | Unscored | Unscored |
| Racing NSW | 15008671672 | (blank) | blank_org_type | 40/B | 40/Needs Review | 40/Needs Review | Needs Review | Needs Review |
| Panasonic Studio Productions | 15042301818 | broadcaster |  | 60/B | 60/B | 60/B | B | B |
| Supertech Electronics | 15274105699 | hardware_vendor |  | 10/D | 10/D | 10/D | D | D |
| Gloucester Park | 15387953738 | individual_club_team |  | 45/B | 45/B | 55/B | B | B |
| Bunbury Trotting Club | 15388186399 | individual_club_team |  | 35/C | 35/C | 45/B | B | B |
| GRAVITY MEDIA | 15860277364 | broadcaster |  | 50/D | 50/D | 50/D | D | D |
| Harness Racing Victoria | 15860116585 | governing_body_league |  | 80/A | 80/A | 80/A | A | A |
| Queensland Racing Integrity Commission | 16047156820 | regulator |  | 25/D | 25/D | 0/D | D | D |
| Roving Enterprises | 17317337782 | broadcaster |  | 60/B | 60/B | 60/B | B | B |
| Endemol Shine Australia | 17317147787 | broadcaster |  | 60/B | 60/B | 60/B | B | B |
| Ironman | 17317184159 | governing_body_league |  | 70/D | 70/D | 70/D | D | D |
| Editix | 17317381378 | (blank) | blank_org_type, false_veto | 0/D | 0/Unscored | 0/Unscored | Unscored | Unscored |
| Jam TV | 17317850381 | (blank) | blank_org_type, ~~false_veto~~ **TRUE veto — see D-23** | 0/D | 0/Unscored | 0/Unscored | Unscored | Unscored |
| Pinjarra Park | 17696004613 | (blank) | blank_org_type, false_veto | 0/D | 0/Unscored | 0/Unscored | Unscored | Unscored |
| Big Screen Video | 17791151956 | other |  | 20/D | 20/D | 20/D | D | D |
| Sportsbet | 17861423879 | gambling_operator |  | 0/D | 0/D | 20/D | D | D |
| Simtech LED | 18047161864 | (blank) | blank_org_type, false_veto | 10/D | 10/Unscored | 10/Unscored | Unscored | Unscored |
| Surfing Australia | 18647353914 | governing_body_league |  | 70/A | 70/A | 70/A | A | A |
| Southside Racing | 18756544344 | individual_club_team |  | 45/B | 45/B | 55/B | B | B |
| Harness Racing New South Wales | 18756544347 | governing_body_league |  | 70/A | 70/A | 70/A | A | A |
| AusCycling | 18756544359 | governing_body_league |  | 80/A | 80/A | 80/A | A | A |
| Addington | 18756544407 | individual_club_team |  | 45/B | 45/B | 55/B | B | B |
| The Kalgoorlie-Boulder Racing Club | 18796602894 | (blank) | blank_org_type, false_veto | 10/D | 10/Unscored | 10/Unscored | Unscored | Unscored |
| LiveHeats | 18811366029 | other |  | 30/C | 30/C | 30/C | C | C |
| Shepparton Harness Racing Club | 18973591368 | individual_club_team |  | 35/C | 35/C | 45/B | B | B |
| Bathurst Harness Racing Club | 19099896622 | individual_club_team |  | 35/C | 35/C | 45/B | B | B |
| Newcastle Harness Racing Club | 19100977027 | (blank) | blank_org_type, false_veto | 0/D | 0/Unscored | 0/Unscored | Unscored | Unscored |
| Bendigo Harness Racing Club | 19154355339 | individual_club_team |  | 35/C | 35/C | 45/B | B | B |
| Racing.com Pty Ltd | 19363725157 | broadcaster |  | 60/B | 60/B | 60/B | B | B |
| Waikato Racing Club Inc | 20538284384 | (blank) | blank_org_type, false_veto | 0/D | 0/Unscored | 0/Unscored | Unscored | Unscored |
| RACE (Racing at Awapuni and Trentham Combined Enterprise Incorporated) | 20538599475 | individual_club_team |  | 35/C | 35/C | 45/B | B | B |
| The Rumble / Pacific Action Sports | 20943964946 | (blank) | blank_org_type, false_veto | 10/D | 10/Unscored | 10/Unscored | Unscored | Unscored |
| Surge Productions | 22477285976 | broadcaster |  | 50/B | 50/B | 50/B | B | B |
| ABC (Australian Broadcasting Corporation) | 22477259590 | broadcaster |  | 20/C | 20/C | 20/C | C | C |
| The Stream Shop | 26149144628 | broadcaster |  | 50/B | 50/B | 50/B | B | B |
| Jam TV Australia | 40613322263 | broadcaster |  | 50/B | 50/B | 50/B | B | B |

**Verdict:** OK: 66 row(s) simulated.

---

## Correction (2026-08-12, from Phase 47's armed window) — Jam TV `17317850381`

**This report's `false_veto` label on Jam TV `17317850381` was wrong. Do NOT re-target that
row as a false veto in Phase 49 or anywhere else.**

The classifier keyed `false_veto` off a blank `lv_country_region_normalized` — but blank
means *never determined*, not *determined to be ANZ*. Jam TV `17317850381` is the **Italian**
broadcaster `jamtv.it` (`country: Italy`, `industry: BROADCAST_MEDIA`). Its non-ANZ veto is
**correct** and was deliberately preserved: Phase 47 wrote it
`lv_country_region_normalized = "Other"`, so it now reads `lv_anti_icp_flag = "true"`,
`lv_anti_icp_reason = "Non-ANZ geography"`, Tier D — with the region populated, which also
moves it outside VETO-03's blank-region search. Operator-confirmed as D-23 in
`.planning/phases/47-veto-remediation/47-CONTEXT.md`.

Note the portal holds **two** separate Jam TV records, and row 115 of this same table is the
other one — `Jam TV Australia` (`40613322263`, `broadcaster`, Tier B), the Australian
company. They are different organisations; do not merge or dedupe them on name.

The other 16 rows this report flagged `false_veto` were genuine false vetoes and all cleared
in Phase 47. Evidence: `.planning/phases/47-veto-remediation/47-RUN-REPORT.md` § "Plan 04 —
the armed window (actuals)".
