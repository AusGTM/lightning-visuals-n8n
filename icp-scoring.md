# **Lightning Visuals — ICP / Anti-ICP Validation**

**Prepared for:** Alex · **Job:** Phase 1 / JTBD 1 · **Basis:** 92 closed HubSpot deals (39 won / 53 lost) **Status:** For sign-off before rubric build (JTBD 2\)

---

## **1\. Executive summary**

We reconciled Alex’s working ICP against what actually won and lost. Headline: the **core ICP direction is partly right, but the unit of targeting is wrong.**

·      ✅ **Best-fit is real and identifiable:** Australian **racing & sport governing / league bodies** that produce broadcast/streaming content win **83%** of the time (10 of 12 new-business deals) — more than **2.4×** the 34% baseline.

·      ⚠️ **The most-pursued segment is the weakest:** individual **clubs/teams** are the single biggest group of deals (36) yet convert at only **19%** — we chase them hardest and close them least.

·      ✅ **Geography assumption holds:** Australia wins **42%** vs non-Australia **11%**.

·      ✅ **“Produces broadcast content” qualifier holds:** content producers win **38%** vs **17%** for organisations with no content output.

·      ❌ **Two assumptions don’t hold as stated:** company-size “sweet spot” (10–200 employees) does **not** predict winning, and the buyer **persona/title** does not either.

·      🔎 **Real market ≠ assumed market:** the pipeline is overwhelmingly the **Australian racing industry** (thoroughbred / harness / greyhound) plus a few national sport bodies. The ICP’s marquee targets — **AFL/NRL/A-League clubs, NBL teams, and Kayo/Stan/FTA networks — are essentially absent** from won *and* lost deals.

**Read this as direction, not proof.** These are 92 deals that already entered the pipeline, so this measures *which engaged deals convert* — not the whole addressable market. Cells are small (n ≥ 3 shown); treat as hypotheses to test downstream, not statistical certainty. Anti-ICP signals are *inferred from firmographics* because closed\_lost\_reason is **0% filled** in HubSpot — though discovery calls now supply the real reasons directly (price \+ cloud-fear, see §4). One data limit to note: **pre-HubSpot deals (the prior founder’s video-production work) are missing**, so the CRM likely *undercounts wins* and over-weights the lost column — the true win rate is probably higher than the 34% shown.

---

## **2\. Method (brief)**

Closed deals → primary company via hs\_primary\_associated\_company (87/92 matched), and → contacts via associations. **Renewals removed** (existing business wins 90% and would distort everything) → analysis runs on **79 new-business deals, 34% baseline win**. Each company was **web-enriched** (live research on 66 companies, 49 high-confidence) to derive the ICP-decisive signals HubSpot does not hold: org type, content output, sponsorship reliance, AU presence. Every attribute is reported on three separate axes — **conversion** (win %), **value** (deal size), **coverage** (how many deals exist).

HubSpot’s native industry tag proved unreliable (e.g. “The Creek Agency” is actually Albion Park Harness Racing Club; Australian Turf Club tagged “Gambling/Casinos”). Conclusions below lead with **enriched** signals, not native tags.

---

## **3\. ICP assumption scorecard**

| Client assumption | Verdict | Evidence (new-business, base 34%) |
| :---- | :---- | :---- |
| Australia is the market | ✅ **Validated** | AU **42%** (n=55) vs non-AU **11%** (n=18) |
| Produces live/broadcast content | ✅ **Validated** | content **38%** (n=64) vs none **17%** (n=12) |
| Three org types (club / league / broadcaster) | ⚠️ **Reframed** | **League/Governing-Body 83%** (n=12) ≫ Broadcaster **40%** (n=15) ≫ **Club/Team 19%** (n=36) |
| Sponsorship-reliant buyers | ⚠️ **Partial** | win-rate flat (33% vs 36%) **but** won-deal size higher ($27k vs $9k) — drives *value*, not *conversion* |
| Sweet-spot 10–200 employees | ❌ **Not supported** | win-rate flat across all size bands (31–38%); size does not discriminate |
| Buyer persona \= CxO / Head of Broadcast | ❌ **Not supported** | title groups flat (C-suite 29%, GM/Dir 36%, Media 33%) |
| Mid-market revenue | ✅ **Validated (refined)** | $5–50M **50%**, $50–500M **47%** vs $1–5M **21%**, $500M+ **17%** |
| Disqualify oversized / enterprise | ✅ **Validated (by revenue)** | $500M+ revenue **17%** (n=6). *Soft: lost deals also skew larger in $ — but those are unrealized estimates, not facts.* |
| Sports vs non-sports | 🔎 **Not discriminating** | sports 34% vs non-sports 33% — within this racing-heavy base, “sports” alone is not a signal |

---

## **4\. Best-fit ICP & Anti-ICP**

**Best-fit profile:** AU-based · **governing-body or league** (or content producer) · produces live/near-live broadcast/streaming content · mid-market revenue ($5–500M).

·      **Primary — AU racing & sport governing / league bodies that produce content** (83% win). *Won:* Racing Queensland, Harness Racing Victoria & NSW, Racing & Wagering WA, Tasracing, AusCycling, Surfing Australia. Logic fits: a governing body buys once and standardises branding **league-wide**. *(Bucket is slightly mixed — e.g. QRIC is a regulator, not a content buyer — so JTBD 2 shouldn’t treat “governing body” as monolithic.)*

·      **Secondary — AU sports content producers / OB houses** (\~40% win): Gravity Media, Panasonic Studio Productions, Jam TV, ABC. Real but more competitive, lower value.

**Anti-ICP (suppress / disqualify):** \- **Individual clubs/teams as the direct target** — 19% win over 36 deals; high effort, low yield (single-venue racing clubs: Shepparton, Scone, Toowoomba, Geraldton…). *Reach them via their governing body, not directly.* 

\- **Non-Australian** (11% win) · **no broadcast/streaming content** (17%) · **$500M+ revenue / enterprise (17% — graduated deduction, not a veto: penalty decays toward near-veto at $1.2B+, so strong-fit large prospects remain targetable)**. 

\- **Not sports-media at all: AV/LED-hardware vendors (Supertech, Simtech) \= veto. Gambling operators (Sportsbet, Entain) \= graduated deduction, not a veto — targetable proactively where other fit signals are strong.**

**Why deals are lost (from discovery calls, since closed\_lost\_reason is blank):** \#1 is **price / affordability** — “everyone wants it, it’s that they can’t afford it”; \#2 is **fear of cloud**, especially in horse racing. Plus disqualifiers: happy with the incumbent, no streaming/broadcast, or sub-professional production kit. **Deal-size note:** the headline $100–500K deals (a jurisdiction, racing.com, A-League) are a *tiny tier — fewer than 10 prospects exist*; most CRM wins are smaller racing-template deals (won-median \~$20K). So “we lose the big ones” is real but is largely a **small-TAM \+ price/cloud-fear** story, not a firmographic one — capture lv\_closed\_lost\_reason to track it systematically (§6).

---

## **5\. Proposed scoring & tiering categories**

All signals below are available **at lead/account-scoring time** (firmographic \+ enrichment). *Deal value is deliberately excluded — it doesn’t exist until a deal is open, so it cannot score a prospect.*

| Category | Signals (with data source) | Direction |
| :---- | :---- | :---- |
| **Firmographic** | org\_type *(web-enriched → Claude/Orchestrator classifier in prod)*; country=AU *(HubSpot)*; revenue band *(HubSpot \+ Apollo/ZoomInfo)* | League/Gov **\+++**, Producer **\+**, Club **–**, Other **– –**; AU **\++**; $5–500M **\++** |
| **Product-fit (technographic)** | produces broadcast/streaming content *(web-enriched → Claude \+ Apollo/Zoominfo)* | content **\++**; no content \= **disqualify** |
| **Intent** | buying-committee / topic affinity *(ZoomInfo/Hubspot pixel — forward-looking, none in historical data)* | **\+** when present |
| **Lifecycle** | new vs existing business; lead source *(HubSpot)* | renewals scored separately, scoring rubric here is for new business, omit scoring for existing |
| **Anti-ICP deductions** | Hard veto: non-AU; no content; hardware-vendor. Graduated deduction (targetable): gambling-operator; $500M+ revenue | Negative deduction OR veto |

**Tiers (illustrative):** **A** \= AU governing-body/league, produces content, mid-market → priority. **B** \= AU content producer or strong club-via-league. **C** \= individual club, AU, content → nurture via league. **D** \= anti-ICP (non-AU / no-content / non-media) → disqualify.

**Scoring model** 

| Signal / attribute | Points |
| :---- | :---- |
| Org: governing-body / league | \+40 |
| Org: content producer | \+20 |
| Org: individual club | \+5 |
| Other | 0 |
| Produces broadcast/streaming content | \+20 (none \= hard veto) |
| Geography: ANZ | \+10 (non-ANZ \= hard veto) |
| Revenue: $5–500M | \+10 (see decay table for \>$500M) |

**Graduated deductions** (negative exponential decay scoring model, don’t set lv\_anti\_icp\_flag; applied after base points):

| Signal / attribute | Points |
| :---- | :---- |
| $500M–750M | –5 |
| $750M–1B | –15 |
| $1B–1.2B | –30 |
| $1.2B+ | –50 (near-veto, but never auto-disqualify) |
| Gambling Operator | –20 (can be surfaced with strong other attributes) |

**Intent signals** (HubSpot-pixel-driven scheme):

| Pixel signal | Points |
| :---- | :---- |
| Any tracked website visit (known company) | \+3 |
| Visited pricing / product / demo page | \+7 |
| Return visit within 14 days | \+5 |
| ≥3 sessions or multi-contact from same company | \+10 |
| No activity | 0 |

**How the properties map to the rubric** — they play three different roles:

| Property | Role | Rubric mapping |
| :---- | :---- | :---- |
| lv\_org\_type | **Input** (enrichment writes) | Firmographic row: governing-body/league \+++, producer \+, club – |
| lv\_produces\_content | **Input** (enrichment writes) | Product-fit row: content \++, no content \= veto |
| country, annualrevenue | **Input** (already exist) | ANZ \++, $5–500M \++; non-ANZ \= veto; revenue \>$500M \= graduated deduction, decaying to near-veto at $1.2B+ (targetable, not disqualified) |
| lv\_icp\_fit\_score | **Output** (rubric writes) | The computed number — sorts the stack-ranked view |
| lv\_icp\_tier | **Output** (rubric writes) | Score bands \+ veto rules → the A/B/C/D label reps act on |
| lv\_anti\_icp\_flag | **Output** (rubric writes) | True only when a hard veto fires (non-AU / no-content / hardware); gambling and $500M+ revenue are graduated deductions and never set this flag — filters records out of working views |
| lv\_closed\_lost\_reason | **Hygiene** (not scoring) | Closes audit F2; feeds the *next* rubric revision with real loss reasons |
| deal\_source | **Hygiene** (not scoring) | Closes audit F1 — channel attribution |

**How score becomes tier** (point values illustrative — weights are the JTBD 2 sign-off):

| Tier | Rule | Worked example |
| :---- | :---- | :---- |
| **A** | score ≥ 70 | Harness Racing NZ: governing body \+40, content \+20, ANZ \+10, mid-market \+10 \= 80 |
| **B** | 40–69 | Producer \+20, content \+20, ANZ \+10 \= 50; or club whose league is a customer |
| **C** | 15–39 | Club \+5, content \+20, ANZ \+10 \= 35 → nurture via its league, not worked directly |
| **D** | any veto fired (lv\_anti\_icp\_flag \= true) | Sportsbet: wagering-operator deduction (–20) \+ high-revenue decay, scored deduction → typically Tier C, targetable |

## **6\. Enrichment plan & HubSpot data gaps**

**What to enrich (and from where in the existing stack):** 

\- **Org type** (decisive, not in HubSpot) → Claude/Orchestrator classifier on name+website+industry (operationalise this analysis as a property). 

\- **Content output** → Claude/Orchestrator \+ Apollo/Zoominfo (news/site signals). 

\- **Seniority / persona** → Zoominfo → Lusha → Apollo → SignalHire waterfall (seniority is **1% filled** today; persona couldn’t be properly tested). 

\- **Revenue / employees refine** → Apollo / Zoominfo (native fill 78–82%, quality mixed). 

\- **Intent** (forward-looking) → ZoomInfo/Hubspot pixel (buying committee, topic affinity) — currently the only source of in-market signal. 

\- **Qualitative fit** (pain, budget, timeline) → Fathom \+ Claude on call transcripts (post-first-call scoring).

**Suggested custom HubSpot properties:** lv\_org\_type, lv\_produces\_content, lv\_icp\_tier, lv\_icp\_fit\_score, lv\_anti\_icp\_flag, and lv\_closed\_lost\_reason (picklist) — the empty loss-reason field is the single biggest blocker to *evidence-based* anti-ICP; capturing it now makes the next validation far stronger.

---

## **7\. External market check & competition**

Independent web research confirms the direction and sharpens the threat picture (full analysis \+ sources in the companion Market-Research).

·      **\#1 threat — LIGR.live:** an Australian, cloud, *pay-per-use* data-driven competitor **already running the governing-body “buy-once-deploy-league-wide” play we recommend** — it holds Football Australia’s current “gatekeeper” deal (3,500+ games/yr, all tiers) and lists Cricket Australia / QRL / AFL NAB League wins (per LIGR/press). Positioned as you described: LV between **Vizrt (premium)** and **LIGR (budget)**.

·      **Differentiate on automation, data, price and outbound — not “cloud.”** Vizrt and Ross now ship cloud too, so “low-cost cloud vs hardware” is eroding; incumbents stay passive/inbound, which is your opening.

·      **The virtual-advertising bet faces AU incumbents** (Broadcast Virtual, Girraphic already serve the majors)

## **8\. Market size → enrich & score, may not need prospecting at scale**

The validated best-fit is a **finite \~100–150 ANZ organisations** (racing core \~25–28; **fewer than 10** at $100K+ ACV). At that size, **building a high-volume / programmatic prospecting machine may not be justified**, a fallback cost effective motion is to **enrich and score a finite, named list** (which still fits Alex’s existing targeted outbound).

·      **The racing core.** Effectively all ANZ racing bodies are in the CRM (won, lost, or sitting untouched). Here it’s **enrich \+ score**, with \~zero net-new discovery.

·      **The non-racing best-fit (broadcast NSOs/leagues \+ producers) is \~half-missing** roughly **30–50 orgs not yet in HubSpot**. That’s a **one-time, hand-built list to *validate*** (these are unproven in the deal data), not automated prospecting.

·      **What this changes:** org-type is verified for only **66 of 712** companies in the CRM, so you can’t even know true coverage until the data is enriched. **Enrich first → score** *(Full saturation breakdown in Market-Research)*

---

## **9\. Next steps**

1\.        **Alex sign-off** on best-fit (governing-bodies-first) and anti-ICP (clubs-direct, non-AU, no-content).

2\.        **JTBD 2 — rubric:** turn §6 into weighted scores §5 \+ A/B/C/D thresholds; stage “scoreable now” (firmographic \+ content) vs “scoreable after enrichment” (intent, persona, qualitative).

3\.        **JTBD 4 — tier/orchestration:** HubSpot is on **Starter ($35)** today — scoring/workflows need a Pro tier (confirmed); **still open question about orchestration options**.

