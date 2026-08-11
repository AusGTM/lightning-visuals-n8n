# Phase 47 Plan 03 -- Run Report (D-21 full evidence trail)

Generated: 2026-08-11T22:02:57.225974+00:00
Cost estimate: {"web_research_calls": 17, "redundant_research_calls": 4, "n8n_executions": 17, "n8n_budget_month": 2500, "lusha_credits": 0, "lusha_credits_note": "D-08: web research only, no provider waterfall -- zero Lusha credits drawn.", "anthropic_estimate_usd": 1.1662, "anthropic_estimate_note": "Derived from the Phase 20 canary figure ($0.0686/record), measured on the n8n Haiku-plus-Sonnet path -- NOT this script's single claude-sonnet-5 + native web_search call, and excludes that call's per-search billing. An under-estimate, not a live-measured figure for this path."}

Both HubSpot write surfaces are disarmed for every record below (DRY_RUN default, ALLOW_VETO_REMEDIATION unset). D-21: only lv_org_type_verified_at, lv_produces_content_verified_at are ever PATCHed to HubSpot -- every other D-09 field is recorded here, never on the live record.

| id | name | lv_org_type | lv_produces_content | lv_country_region_normalized | predicted_score | predicted_tier | outcome |
|---|---|---|---|---|---|---|---|
| 9604732797 | Tweed Valley Jockey Club | UNRESOLVED: research returned 'Sporting club / Racecourse operator', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17) | true | AU | 30 | Needs Review | clears veto |
| 9604794661 | Sapphire Coast Turf Club (Bega Valley) | UNRESOLVED: research returned 'Sports club / Racing club', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17) | true | AU | 30 | Needs Review | clears veto |
| 9605273630 | Port Macquarie Race Club | UNRESOLVED: research returned 'racing_club', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17) | true | AU | 30 | Needs Review | clears veto |
| 9604732795 | Rockhampton Jockey Club | UNRESOLVED: research returned 'Not-for-Profit Racing Club', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17) | true | AU | 40 | Needs Review | clears veto |
| 9604738976 | Bunbury Turf Club | UNRESOLVED: research returned 'Non-profit Racing Club', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17) | true | AU | 30 | Needs Review | clears veto |
| 9604787229 | The Alice Springs Turf Club | UNRESOLVED: research returned 'Sports Club - Racecourse Operator', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17) | true | AU | 40 | Needs Review | clears veto |
| 10152138518 | Thoroughbred Park | UNRESOLVED: research returned 'Horse racing track / Sports venue', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17) | true | AU | 40 | Needs Review | clears veto |
| 10215097384 | Wyong | UNRESOLVED: research returned 'Thoroughbred racecourse operator / Recreational facilities management', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17) | true | AU | 40 | Needs Review | clears veto |
| 14752488879 | Coffs Harbour Racing Club | UNRESOLVED: research returned 'Sports/Racing Club', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17) | UNRESOLVED: produces_content requires an evidence URL and none was cited | AU | 10 | Unscored | clears veto |
| 17317381378 | Editix | UNRESOLVED: research did not establish an org type | UNRESOLVED: research did not establish content output | UNRESOLVED: research did not establish a region in AU/NZ/ANZ/Other | 0 | Unscored | clears veto |
| 17317850381 | Jam TV | UNRESOLVED: research returned 'Media company / Web television broadcaster', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17) | true | UNRESOLVED: research returned 'Italy', not confidently AU/NZ -- left unresolved rather than defaulted to Other (a genuine veto would follow from a wrong guess) | 20 | Needs Review | clears veto |
| 17696004613 | Pinjarra Park | UNRESOLVED: research returned 'Association/Non-profit racing club', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17) | true | AU | 30 | Needs Review | clears veto |
| 18047161864 | Simtech LED | hardware_vendor | true | AU | 40 | B | clears veto |
| 18796602894 | The Kalgoorlie-Boulder Racing Club | UNRESOLVED: research returned 'Thoroughbred racing club', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17) | true | AU | 40 | Needs Review | clears veto |
| 19100977027 | Newcastle Harness Racing Club | UNRESOLVED: research returned 'not-for-profit sports club', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17) | true | AU | 30 | Needs Review | clears veto |
| 20538284384 | Waikato Racing Club Inc | UNRESOLVED: research returned 'Racing Club / Sports Organization', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17) | true | NZ | 30 | Needs Review | clears veto |
| 20943964946 | The Rumble / Pacific Action Sports | UNRESOLVED: research returned 'Event organizer / Sports league operator', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17) | true | AU | 40 | Needs Review | clears veto |

## Full D-09 evidence trail per record (never PATCHed to HubSpot)

### 9604732797 -- Tweed Valley Jockey Club

```json
{
  "lv_produces_content_source": "claude_web",
  "lv_produces_content_confidence": 90,
  "lv_produces_content_evidence_url": "https://www.tweedriverjockeyclub.com.au/race-day-information",
  "lv_produces_content_evidence_summary": "Tweed River Jockey Club is confirmed as a regional Australian horse racing club operating the Tygalgah racecourse in Murwillumbah, NSW. It conducts 11 race meetings per year (9 TAB meetings and 2 community meetings). All race meetings except Big Dance Raceday and ANZAC Day are broadcast live via Sky Racing Network and Sky Sports Radio, establishing strong sports media fit and broadcast signals. No hardware vendor or gambling operator status found in sources\u2014TAB and bookmaker facilities are on-site but operation appears limited to facility provision rather than gambling operator role. Sponsorship reliance information not found in available sources.",
  "lv_produces_content_verified_at": "2026-08-11T22:02:53.341828+00:00",
  "lv_produces_content_verified_by_model": "claude-haiku-4-5",
  "lv_produces_content_validation_status": "web_researched",
  "lv_country_region_normalized_source": "claude_web",
  "lv_country_region_normalized_confidence": 90,
  "lv_country_region_normalized_evidence_url": "https://www.tweedriverjockeyclub.com.au/about-us",
  "lv_country_region_normalized_evidence_summary": "Tweed River Jockey Club is confirmed as a regional Australian horse racing club operating the Tygalgah racecourse in Murwillumbah, NSW. It conducts 11 race meetings per year (9 TAB meetings and 2 community meetings). All race meetings except Big Dance Raceday and ANZAC Day are broadcast live via Sky Racing Network and Sky Sports Radio, establishing strong sports media fit and broadcast signals. No hardware vendor or gambling operator status found in sources\u2014TAB and bookmaker facilities are on-site but operation appears limited to facility provision rather than gambling operator role. Sponsorship reliance information not found in available sources.",
  "lv_country_region_normalized_verified_at": "2026-08-11T22:02:53.341828+00:00",
  "lv_country_region_normalized_verified_by_model": "claude-haiku-4-5",
  "lv_country_region_normalized_validation_status": "web_researched"
}
```

D-14 unresolved reasons: {"lv_org_type": "research returned 'Sporting club / Racecourse operator', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17)"}

### 9604794661 -- Sapphire Coast Turf Club (Bega Valley)

```json
{
  "lv_produces_content_source": "claude_web",
  "lv_produces_content_confidence": 92,
  "lv_produces_content_evidence_url": "https://sapphirecoastturfclub.com.au/sponsors/",
  "lv_produces_content_evidence_summary": "Sapphire Coast Turf Club is a modern country racecourse and sports club in Kalaru, Bega Valley, NSW. It operates 12 race meetings per year. TAB race meets are broadcast nationally on TV, radio, and internet. The club generates revenue through memberships ($60 annual fee), race day entry ($15 adults), TAB betting facilities, bookmakers, and sponsorships. The organization is highly sponsorship-reliant per its own marketing materials. Annual operational costs are approximately AUD $400,000.",
  "lv_produces_content_verified_at": "2026-08-11T22:02:53.753769+00:00",
  "lv_produces_content_verified_by_model": "claude-haiku-4-5",
  "lv_produces_content_validation_status": "web_researched",
  "lv_country_region_normalized_source": "claude_web",
  "lv_country_region_normalized_confidence": 92,
  "lv_country_region_normalized_evidence_url": "https://sapphirecoastturfclub.com.au/contact-us/",
  "lv_country_region_normalized_evidence_summary": "Sapphire Coast Turf Club is a modern country racecourse and sports club in Kalaru, Bega Valley, NSW. It operates 12 race meetings per year. TAB race meets are broadcast nationally on TV, radio, and internet. The club generates revenue through memberships ($60 annual fee), race day entry ($15 adults), TAB betting facilities, bookmakers, and sponsorships. The organization is highly sponsorship-reliant per its own marketing materials. Annual operational costs are approximately AUD $400,000.",
  "lv_country_region_normalized_verified_at": "2026-08-11T22:02:53.753769+00:00",
  "lv_country_region_normalized_verified_by_model": "claude-haiku-4-5",
  "lv_country_region_normalized_validation_status": "web_researched"
}
```

D-14 unresolved reasons: {"lv_org_type": "research returned 'Sports club / Racing club', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17)"}

### 9605273630 -- Port Macquarie Race Club

```json
{
  "lv_produces_content_source": "claude_web",
  "lv_produces_content_confidence": 85,
  "lv_produces_content_evidence_url": "https://portmacquarieraceclub.com.au/racing.html",
  "lv_produces_content_evidence_summary": "Port Macquarie Race Club is a regional thoroughbred racing venue located in NSW, Australia. It operates a racecourse hosting approximately 23 meetings annually including the Port Macquarie Cup carnival. The club produces content through live racing events and entertainment programming. Betting facilities with TAB are available on-site. No evidence of live streaming or broadcast distribution was found, though the club promotes 'race day highlights' on social media. Annual revenue estimated at $3M based on 2026 data. Sponsorship-reliant model evidenced by branded race meetings (Carlton Mid Port Macquarie Cup). Not a hardware vendor; operates as a racing operator with gambling components.",
  "lv_produces_content_verified_at": "2026-08-11T22:02:53.910557+00:00",
  "lv_produces_content_verified_by_model": "claude-haiku-4-5",
  "lv_produces_content_validation_status": "web_researched",
  "lv_country_region_normalized_source": "claude_web",
  "lv_country_region_normalized_confidence": 85,
  "lv_country_region_normalized_evidence_url": "https://portmacquarieraceclub.com.au/",
  "lv_country_region_normalized_evidence_summary": "Port Macquarie Race Club is a regional thoroughbred racing venue located in NSW, Australia. It operates a racecourse hosting approximately 23 meetings annually including the Port Macquarie Cup carnival. The club produces content through live racing events and entertainment programming. Betting facilities with TAB are available on-site. No evidence of live streaming or broadcast distribution was found, though the club promotes 'race day highlights' on social media. Annual revenue estimated at $3M based on 2026 data. Sponsorship-reliant model evidenced by branded race meetings (Carlton Mid Port Macquarie Cup). Not a hardware vendor; operates as a racing operator with gambling components.",
  "lv_country_region_normalized_verified_at": "2026-08-11T22:02:53.910557+00:00",
  "lv_country_region_normalized_verified_by_model": "claude-haiku-4-5",
  "lv_country_region_normalized_validation_status": "web_researched"
}
```

D-14 unresolved reasons: {"lv_org_type": "research returned 'racing_club', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17)"}

### 9604732795 -- Rockhampton Jockey Club

```json
{
  "lv_produces_content_source": "claude_web",
  "lv_produces_content_confidence": 95,
  "lv_produces_content_evidence_url": "https://www.youtube.com/@rockhamptonjockeyclub6459",
  "lv_produces_content_evidence_summary": "Rockhampton Jockey Club is a not-for-profit organization established 1868, operating Callaghan Park Racecourse in North Rockhampton, Queensland. Conducts 35-45 thoroughbred horse race meetings annually. Produces original content including YouTube channel with 'Rocky Turf Talk' educational series and race coverage. Revenue model dependent on race day attendance, sponsorships (XXXX Gold branding), and wagering. No hard veto characteristics identified for hardware vendor status. Gambling operations occur through betting at racecourse events (typical of such clubs). Strong sports media fit as provincial racing hub.",
  "lv_produces_content_verified_at": "2026-08-11T22:02:54.175528+00:00",
  "lv_produces_content_verified_by_model": "claude-haiku-4-5",
  "lv_produces_content_validation_status": "web_researched",
  "lv_country_region_normalized_source": "claude_web",
  "lv_country_region_normalized_confidence": 95,
  "lv_country_region_normalized_evidence_url": "https://callaghanpark.com.au/about/",
  "lv_country_region_normalized_evidence_summary": "Rockhampton Jockey Club is a not-for-profit organization established 1868, operating Callaghan Park Racecourse in North Rockhampton, Queensland. Conducts 35-45 thoroughbred horse race meetings annually. Produces original content including YouTube channel with 'Rocky Turf Talk' educational series and race coverage. Revenue model dependent on race day attendance, sponsorships (XXXX Gold branding), and wagering. No hard veto characteristics identified for hardware vendor status. Gambling operations occur through betting at racecourse events (typical of such clubs). Strong sports media fit as provincial racing hub.",
  "lv_country_region_normalized_verified_at": "2026-08-11T22:02:54.175528+00:00",
  "lv_country_region_normalized_verified_by_model": "claude-haiku-4-5",
  "lv_country_region_normalized_validation_status": "web_researched"
}
```

D-14 unresolved reasons: {"lv_org_type": "research returned 'Not-for-Profit Racing Club', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17)"}

### 9604738976 -- Bunbury Turf Club

```json
{
  "lv_produces_content_source": "claude_web",
  "lv_produces_content_confidence": 90,
  "lv_produces_content_evidence_url": "https://www.bunburyturfclub.com.au/",
  "lv_produces_content_evidence_summary": "Bunbury Turf Club is a non-profit racing club established in 1868 operating Western Australia's primary thoroughbred racing facility. The organization hosts race meetings September-April (per first-party sources) and produces live racing events for attendance and broadcast. Revenue estimated at $4 million annually. Club facilitates gambling/wagering through race betting operations and member betting facilities. Race events are broadcast nationally via Sky Racing Channel to TAB agencies and Foxtel. Substantial sponsorship dependency evident from branded race events (Swan Draught Bunbury Cup, XXXX Gold Bunbury Cup). High sports media relevance as major provincial racing venue attracting 8,000+ attendees at annual carnival events.",
  "lv_produces_content_verified_at": "2026-08-11T22:02:54.349634+00:00",
  "lv_produces_content_verified_by_model": "claude-haiku-4-5",
  "lv_produces_content_validation_status": "web_researched",
  "lv_country_region_normalized_source": "claude_web",
  "lv_country_region_normalized_confidence": 90,
  "lv_country_region_normalized_evidence_url": "https://www.bunburyturfclub.com.au/about",
  "lv_country_region_normalized_evidence_summary": "Bunbury Turf Club is a non-profit racing club established in 1868 operating Western Australia's primary thoroughbred racing facility. The organization hosts race meetings September-April (per first-party sources) and produces live racing events for attendance and broadcast. Revenue estimated at $4 million annually. Club facilitates gambling/wagering through race betting operations and member betting facilities. Race events are broadcast nationally via Sky Racing Channel to TAB agencies and Foxtel. Substantial sponsorship dependency evident from branded race events (Swan Draught Bunbury Cup, XXXX Gold Bunbury Cup). High sports media relevance as major provincial racing venue attracting 8,000+ attendees at annual carnival events.",
  "lv_country_region_normalized_verified_at": "2026-08-11T22:02:54.349634+00:00",
  "lv_country_region_normalized_verified_by_model": "claude-haiku-4-5",
  "lv_country_region_normalized_validation_status": "web_researched"
}
```

D-14 unresolved reasons: {"lv_org_type": "research returned 'Non-profit Racing Club', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17)"}

### 9604787229 -- The Alice Springs Turf Club

```json
{
  "lv_produces_content_source": "claude_web",
  "lv_produces_content_confidence": 92,
  "lv_produces_content_evidence_url": "https://www.alicespringsturfclub.org.au/about",
  "lv_produces_content_evidence_summary": "The Alice Springs Turf Club is a regional thoroughbred racing club operator in Alice Springs, Northern Territory, Australia. The organization produces horse racing content distributed via Sky Racing broadcasts (nationally/internationally) and YouTube race replays. Strong sponsorship reliance evidenced by Ladbrokes partnership (facility naming: Ladbrokes Pioneer Park, Ladbrokes Cup Carnival, Ladbrokes Next Gen Marquee). TAB wagering facilities present on-site. Organization is recognized as a single entity sports club operating as Alice Springs Turf Club Inc, member of Thoroughbred Racing NT. Good fit for sports media as host of racing events and content producer/distributor.",
  "lv_produces_content_verified_at": "2026-08-11T22:02:54.617918+00:00",
  "lv_produces_content_verified_by_model": "claude-haiku-4-5",
  "lv_produces_content_validation_status": "web_researched",
  "lv_country_region_normalized_source": "claude_web",
  "lv_country_region_normalized_confidence": 92,
  "lv_country_region_normalized_evidence_url": "https://www.alicespringsturfclub.org.au/about",
  "lv_country_region_normalized_evidence_summary": "The Alice Springs Turf Club is a regional thoroughbred racing club operator in Alice Springs, Northern Territory, Australia. The organization produces horse racing content distributed via Sky Racing broadcasts (nationally/internationally) and YouTube race replays. Strong sponsorship reliance evidenced by Ladbrokes partnership (facility naming: Ladbrokes Pioneer Park, Ladbrokes Cup Carnival, Ladbrokes Next Gen Marquee). TAB wagering facilities present on-site. Organization is recognized as a single entity sports club operating as Alice Springs Turf Club Inc, member of Thoroughbred Racing NT. Good fit for sports media as host of racing events and content producer/distributor.",
  "lv_country_region_normalized_verified_at": "2026-08-11T22:02:54.617918+00:00",
  "lv_country_region_normalized_verified_by_model": "claude-haiku-4-5",
  "lv_country_region_normalized_validation_status": "web_researched"
}
```

D-14 unresolved reasons: {"lv_org_type": "research returned 'Sports Club - Racecourse Operator', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17)"}

### 10152138518 -- Thoroughbred Park

```json
{
  "lv_produces_content_source": "claude_web",
  "lv_produces_content_confidence": 85,
  "lv_produces_content_evidence_url": "https://bets.com.au/horse-racing/race-courses/canberra-races-live-stream-20210329-0015/",
  "lv_produces_content_evidence_summary": "Thoroughbred Park is a thoroughbred horse racing venue operated by the Canberra Racing Club in Lyneham, Australian Capital Territory. It conducts 25 race meetings annually including major branded events. The venue produces live racing content that is distributed through third-party broadcasting platforms (Sky Racing, Ladbrokes, bet365, Racing.com) rather than proprietary channels. The organization is heavily sponsor-reliant (major sponsors include John McGrath Auto Group, Kia Australia) and receives government funding via MOU. No evidence found of in-house broadcast or streaming production facility\u2014races are broadcast through established racing platforms. The venue is not a gambling operator (wagering is managed through external TAB platforms) and is not a hardware vendor. Strong sports media relevance due to hosting premium racing events for major Australian racing calendar.",
  "lv_produces_content_verified_at": "2026-08-11T22:02:54.858952+00:00",
  "lv_produces_content_verified_by_model": "claude-haiku-4-5",
  "lv_produces_content_validation_status": "web_researched",
  "lv_country_region_normalized_source": "claude_web",
  "lv_country_region_normalized_confidence": 85,
  "lv_country_region_normalized_evidence_url": "https://thoroughbredpark.com.au/about-us/",
  "lv_country_region_normalized_evidence_summary": "Thoroughbred Park is a thoroughbred horse racing venue operated by the Canberra Racing Club in Lyneham, Australian Capital Territory. It conducts 25 race meetings annually including major branded events. The venue produces live racing content that is distributed through third-party broadcasting platforms (Sky Racing, Ladbrokes, bet365, Racing.com) rather than proprietary channels. The organization is heavily sponsor-reliant (major sponsors include John McGrath Auto Group, Kia Australia) and receives government funding via MOU. No evidence found of in-house broadcast or streaming production facility\u2014races are broadcast through established racing platforms. The venue is not a gambling operator (wagering is managed through external TAB platforms) and is not a hardware vendor. Strong sports media relevance due to hosting premium racing events for major Australian racing calendar.",
  "lv_country_region_normalized_verified_at": "2026-08-11T22:02:54.858952+00:00",
  "lv_country_region_normalized_verified_by_model": "claude-haiku-4-5",
  "lv_country_region_normalized_validation_status": "web_researched"
}
```

D-14 unresolved reasons: {"lv_org_type": "research returned 'Horse racing track / Sports venue', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17)"}

### 10215097384 -- Wyong

```json
{
  "lv_produces_content_source": "claude_web",
  "lv_produces_content_confidence": 92,
  "lv_produces_content_evidence_url": "https://www.bets.com.au/horse-racing/race-courses/wyong-races-live-stream-20210406-0030/",
  "lv_produces_content_evidence_summary": "Wyong Race Club is a well-established provincial racecourse operator in Wyong, NSW, hosting approximately 22 thoroughbred race meetings annually. The organisation produces and broadcasts live racing content via multiple platforms (Sky Racing, betting sites, YouTube). The club is sponsorship-reliant, having secured a major three-year agreement with Wyong Leagues Group in 2024 for naming rights to key events. Regarding gambling operations: while Wyong Race Club does not directly operate betting services, wagering on races is facilitated by external bookmakers and betting agencies (Tabcorp, NEDS, Ladbrokes, bet365), and the racecourse facilitates on-course betting promotions. The distinction between venue operations and gambling operations is sufficient to mark this as null rather than true. Revenue band $9.2-11.8M based on 2026 data ($9.2M) and 2017-18 report ($11.76M excluding grants).",
  "lv_produces_content_verified_at": "2026-08-11T22:02:55.035667+00:00",
  "lv_produces_content_verified_by_model": "claude-haiku-4-5",
  "lv_produces_content_validation_status": "web_researched",
  "lv_country_region_normalized_source": "claude_web",
  "lv_country_region_normalized_confidence": 92,
  "lv_country_region_normalized_evidence_url": "https://www.centralcoastaustralia.com.au/15764/wyong-race-club/",
  "lv_country_region_normalized_evidence_summary": "Wyong Race Club is a well-established provincial racecourse operator in Wyong, NSW, hosting approximately 22 thoroughbred race meetings annually. The organisation produces and broadcasts live racing content via multiple platforms (Sky Racing, betting sites, YouTube). The club is sponsorship-reliant, having secured a major three-year agreement with Wyong Leagues Group in 2024 for naming rights to key events. Regarding gambling operations: while Wyong Race Club does not directly operate betting services, wagering on races is facilitated by external bookmakers and betting agencies (Tabcorp, NEDS, Ladbrokes, bet365), and the racecourse facilitates on-course betting promotions. The distinction between venue operations and gambling operations is sufficient to mark this as null rather than true. Revenue band $9.2-11.8M based on 2026 data ($9.2M) and 2017-18 report ($11.76M excluding grants).",
  "lv_country_region_normalized_verified_at": "2026-08-11T22:02:55.035667+00:00",
  "lv_country_region_normalized_verified_by_model": "claude-haiku-4-5",
  "lv_country_region_normalized_validation_status": "web_researched"
}
```

D-14 unresolved reasons: {"lv_org_type": "research returned 'Thoroughbred racecourse operator / Recreational facilities management', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17)"}

### 14752488879 -- Coffs Harbour Racing Club

```json
{
  "lv_country_region_normalized_source": "claude_web",
  "lv_country_region_normalized_confidence": 85,
  "lv_country_region_normalized_evidence_url": "https://www.crunchbase.com/organization/coffs-harbour-racing-club",
  "lv_country_region_normalized_evidence_summary": "Coffs Harbour Racing Club is a regional thoroughbred horse racing club in NSW, Australia that operates 16 racing events annually. As a racing club, it operates wagering/betting facilities and relies on sponsorship opportunities. The club does not produce its own broadcast or streaming content; Race.com.au provides coverage of their meetings. Revenue ~$2M AUD (2025). Primary business is horse racing events and function venue operations.",
  "lv_country_region_normalized_verified_at": "2026-08-11T22:02:55.232768+00:00",
  "lv_country_region_normalized_verified_by_model": "claude-haiku-4-5",
  "lv_country_region_normalized_validation_status": "web_researched"
}
```

D-14 unresolved reasons: {"lv_org_type": "research returned 'Sports/Racing Club', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17)", "lv_produces_content": "produces_content requires an evidence URL and none was cited"}

### 17317381378 -- Editix

```json
{}
```

D-14 unresolved reasons: {"lv_org_type": "research did not establish an org type", "lv_produces_content": "research did not establish content output", "lv_country_region_normalized": "research did not establish a region in AU/NZ/ANZ/Other"}

### 17317850381 -- Jam TV

```json
{
  "lv_produces_content_source": "claude_web",
  "lv_produces_content_confidence": 85,
  "lv_produces_content_evidence_url": "https://jamtv.it/",
  "lv_produces_content_evidence_summary": "Jam TV is confirmed as an Italian music television platform dedicated to rock and related genres. It operates as a web-based television service with daily streaming content including interviews, live sessions, and music programming. The platform originated from the magazine 'Jam - Viaggio nella Musica' and launched as a web television service on February 1, 2016. Based in Milan (Segrate area), it maintains presence across multiple platforms including its website, YouTube, social media, and X/Twitter. No gambling operations, hardware vendor activities, or sports media content identified. Revenue information not available from public sources.",
  "lv_produces_content_verified_at": "2026-08-11T22:02:55.573235+00:00",
  "lv_produces_content_verified_by_model": "claude-haiku-4-5",
  "lv_produces_content_validation_status": "web_researched"
}
```

D-14 unresolved reasons: {"lv_org_type": "research returned 'Media company / Web television broadcaster', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17)", "lv_country_region_normalized": "research returned 'Italy', not confidently AU/NZ -- left unresolved rather than defaulted to Other (a genuine veto would follow from a wrong guess)"}

### 17696004613 -- Pinjarra Park

```json
{
  "lv_produces_content_source": "claude_web",
  "lv_produces_content_confidence": 92,
  "lv_produces_content_evidence_url": "https://www.pinjarrapark.com.au/",
  "lv_produces_content_evidence_summary": "<cite index=\"1-1\">Pinjarra Park is a Thoroughbred horse racing venue located in the town of Pinjarra, Western Australia</cite>. <cite index=\"2-4\">The racecourse is home to the Pinjarra Race Club, which hosts thoroughbred racing events from December to August each year</cite>. <cite index=\"17-2\">The venue offers bars, hospitality outlets, TAB, Sky Racing, live racing, and members facilities</cite>. <cite index=\"17-9\">Platinum Club provides a low-cost entry point to sponsorship, with fantastic benefits for one low packaged price</cite>, indicating sponsorship reliance. <cite index=\"11-1,11-2\">Pinjarra Races live streams are available via Sky Racing Channels and online through bet365 or Ladbrokes</cite>, confirming broadcast and streaming signals.",
  "lv_produces_content_verified_at": "2026-08-11T22:02:55.753347+00:00",
  "lv_produces_content_verified_by_model": "claude-haiku-4-5",
  "lv_produces_content_validation_status": "web_researched",
  "lv_country_region_normalized_source": "claude_web",
  "lv_country_region_normalized_confidence": 92,
  "lv_country_region_normalized_evidence_url": "https://en.wikipedia.org/wiki/Pinjarra_Park",
  "lv_country_region_normalized_evidence_summary": "<cite index=\"1-1\">Pinjarra Park is a Thoroughbred horse racing venue located in the town of Pinjarra, Western Australia</cite>. <cite index=\"2-4\">The racecourse is home to the Pinjarra Race Club, which hosts thoroughbred racing events from December to August each year</cite>. <cite index=\"17-2\">The venue offers bars, hospitality outlets, TAB, Sky Racing, live racing, and members facilities</cite>. <cite index=\"17-9\">Platinum Club provides a low-cost entry point to sponsorship, with fantastic benefits for one low packaged price</cite>, indicating sponsorship reliance. <cite index=\"11-1,11-2\">Pinjarra Races live streams are available via Sky Racing Channels and online through bet365 or Ladbrokes</cite>, confirming broadcast and streaming signals.",
  "lv_country_region_normalized_verified_at": "2026-08-11T22:02:55.753347+00:00",
  "lv_country_region_normalized_verified_by_model": "claude-haiku-4-5",
  "lv_country_region_normalized_validation_status": "web_researched"
}
```

D-14 unresolved reasons: {"lv_org_type": "research returned 'Association/Non-profit racing club', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17)"}

### 18047161864 -- Simtech LED

```json
{
  "lv_org_type_source": "claude_web",
  "lv_org_type_confidence": 85,
  "lv_org_type_evidence_url": "https://simtechled.com/about/",
  "lv_org_type_evidence_summary": "Simtech LED is a private LED display manufacturer and content creation company headquartered in Queensland, Australia. Founded in 1980s as digital printing firm, evolved to specialize in LED signage and displays for gaming, hospitality, sports, retail, corporate, and education sectors. Produces custom content and animations in-house via 4th Gen Studio. Operates offices in Macau, Singapore, Las Vegas, and Philippines. No evidence of broadcasting/streaming operations or gambling operation. Does produce hardware (LED displays) and has sports media applications through stadium and venue installations.",
  "lv_org_type_verified_at": "2026-08-11T22:02:55.945345+00:00",
  "lv_org_type_verified_by_model": "claude-haiku-4-5",
  "lv_org_type_validation_status": "web_researched",
  "lv_produces_content_source": "claude_web",
  "lv_produces_content_confidence": 85,
  "lv_produces_content_evidence_url": "https://simtechled.com/about/",
  "lv_produces_content_evidence_summary": "Simtech LED is a private LED display manufacturer and content creation company headquartered in Queensland, Australia. Founded in 1980s as digital printing firm, evolved to specialize in LED signage and displays for gaming, hospitality, sports, retail, corporate, and education sectors. Produces custom content and animations in-house via 4th Gen Studio. Operates offices in Macau, Singapore, Las Vegas, and Philippines. No evidence of broadcasting/streaming operations or gambling operation. Does produce hardware (LED displays) and has sports media applications through stadium and venue installations.",
  "lv_produces_content_verified_at": "2026-08-11T22:02:55.945345+00:00",
  "lv_produces_content_verified_by_model": "claude-haiku-4-5",
  "lv_produces_content_validation_status": "web_researched",
  "lv_country_region_normalized_source": "claude_web",
  "lv_country_region_normalized_confidence": 85,
  "lv_country_region_normalized_evidence_url": "https://asgam.com/2023/08/01/let-there-be-light/",
  "lv_country_region_normalized_evidence_summary": "Simtech LED is a private LED display manufacturer and content creation company headquartered in Queensland, Australia. Founded in 1980s as digital printing firm, evolved to specialize in LED signage and displays for gaming, hospitality, sports, retail, corporate, and education sectors. Produces custom content and animations in-house via 4th Gen Studio. Operates offices in Macau, Singapore, Las Vegas, and Philippines. No evidence of broadcasting/streaming operations or gambling operation. Does produce hardware (LED displays) and has sports media applications through stadium and venue installations.",
  "lv_country_region_normalized_verified_at": "2026-08-11T22:02:55.945345+00:00",
  "lv_country_region_normalized_verified_by_model": "claude-haiku-4-5",
  "lv_country_region_normalized_validation_status": "web_researched"
}
```

### 18796602894 -- The Kalgoorlie-Boulder Racing Club

```json
{
  "lv_produces_content_source": "claude_web",
  "lv_produces_content_confidence": 92,
  "lv_produces_content_evidence_url": "https://www.youtube.com/channel/UCENGnQVMjYPZuB-rlIASddQ",
  "lv_produces_content_evidence_summary": "The Kalgoorlie-Boulder Racing Club is a confirmed single-entity sports organization operating as a thoroughbred racing club in Western Australia. It operates as a membership-based organization that produces content (race replays via YouTube) and generates revenue from race day attendance, punter betting operations, sponsorships, and venue hire. The organization has clear sports media signals through multiple broadcast channels and YouTube content distribution.",
  "lv_produces_content_verified_at": "2026-08-11T22:02:56.117358+00:00",
  "lv_produces_content_verified_by_model": "claude-haiku-4-5",
  "lv_produces_content_validation_status": "web_researched",
  "lv_country_region_normalized_source": "claude_web",
  "lv_country_region_normalized_confidence": 92,
  "lv_country_region_normalized_evidence_url": "https://www.kbrc.com.au/",
  "lv_country_region_normalized_evidence_summary": "The Kalgoorlie-Boulder Racing Club is a confirmed single-entity sports organization operating as a thoroughbred racing club in Western Australia. It operates as a membership-based organization that produces content (race replays via YouTube) and generates revenue from race day attendance, punter betting operations, sponsorships, and venue hire. The organization has clear sports media signals through multiple broadcast channels and YouTube content distribution.",
  "lv_country_region_normalized_verified_at": "2026-08-11T22:02:56.117358+00:00",
  "lv_country_region_normalized_verified_by_model": "claude-haiku-4-5",
  "lv_country_region_normalized_validation_status": "web_researched"
}
```

D-14 unresolved reasons: {"lv_org_type": "research returned 'Thoroughbred racing club', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17)"}

### 19100977027 -- Newcastle Harness Racing Club

```json
{
  "lv_produces_content_source": "claude_web",
  "lv_produces_content_confidence": 92,
  "lv_produces_content_evidence_url": "https://www.harness.org.au/video-replays.cfm",
  "lv_produces_content_evidence_summary": "Newcastle Harness Racing Club is confirmed as a not-for-profit, member-based sports organization operating a harness racing venue in New South Wales, Australia. The club produces racing content distributed through the Australian Harness Racing website's video replay section and social media channels. Betting operations are facilitated through an on-site covered betting ring. No specific revenue figures located. The organization has clear sports media fit with regular ~70 annual race meetings and feature events including the $100,000 Newcastle Mile.",
  "lv_produces_content_verified_at": "2026-08-11T22:02:56.662505+00:00",
  "lv_produces_content_verified_by_model": "claude-haiku-4-5",
  "lv_produces_content_validation_status": "web_researched",
  "lv_country_region_normalized_source": "claude_web",
  "lv_country_region_normalized_confidence": 92,
  "lv_country_region_normalized_evidence_url": "https://www.newcastleharness.com.au/",
  "lv_country_region_normalized_evidence_summary": "Newcastle Harness Racing Club is confirmed as a not-for-profit, member-based sports organization operating a harness racing venue in New South Wales, Australia. The club produces racing content distributed through the Australian Harness Racing website's video replay section and social media channels. Betting operations are facilitated through an on-site covered betting ring. No specific revenue figures located. The organization has clear sports media fit with regular ~70 annual race meetings and feature events including the $100,000 Newcastle Mile.",
  "lv_country_region_normalized_verified_at": "2026-08-11T22:02:56.662505+00:00",
  "lv_country_region_normalized_verified_by_model": "claude-haiku-4-5",
  "lv_country_region_normalized_validation_status": "web_researched"
}
```

D-14 unresolved reasons: {"lv_org_type": "research returned 'not-for-profit sports club', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17)"}

### 20538284384 -- Waikato Racing Club Inc

```json
{
  "lv_produces_content_source": "claude_web",
  "lv_produces_content_confidence": 85,
  "lv_produces_content_evidence_url": "https://waikatoracing.co.nz/",
  "lv_produces_content_evidence_summary": "Waikato Racing Club Inc is a thoroughbred horse racing organization operating the Te Rapa Racecourse in Hamilton, New Zealand. It merged with Cambridge Jockey Club and Waipa Racing Club to form Waikato Thoroughbred Racing in August 2023. The organization is classified as a gambling operator because it receives New Zealand Racing Board distributions and operates licensed race meetings with TAB betting facilities. It produces live horse racing content across 30+ annual race meetings. The organization is sponsorship-reliant as noted in official descriptions. It has clear sports media fit as a racing event operator. Broadcasting/streaming signals are present through its role as a licensed racing venue that feeds into national racing broadcast networks.",
  "lv_produces_content_verified_at": "2026-08-11T22:02:56.825759+00:00",
  "lv_produces_content_verified_by_model": "claude-haiku-4-5",
  "lv_produces_content_validation_status": "web_researched",
  "lv_country_region_normalized_source": "claude_web",
  "lv_country_region_normalized_confidence": 85,
  "lv_country_region_normalized_evidence_url": "https://www.teraparacing.co.nz/about",
  "lv_country_region_normalized_evidence_summary": "Waikato Racing Club Inc is a thoroughbred horse racing organization operating the Te Rapa Racecourse in Hamilton, New Zealand. It merged with Cambridge Jockey Club and Waipa Racing Club to form Waikato Thoroughbred Racing in August 2023. The organization is classified as a gambling operator because it receives New Zealand Racing Board distributions and operates licensed race meetings with TAB betting facilities. It produces live horse racing content across 30+ annual race meetings. The organization is sponsorship-reliant as noted in official descriptions. It has clear sports media fit as a racing event operator. Broadcasting/streaming signals are present through its role as a licensed racing venue that feeds into national racing broadcast networks.",
  "lv_country_region_normalized_verified_at": "2026-08-11T22:02:56.825759+00:00",
  "lv_country_region_normalized_verified_by_model": "claude-haiku-4-5",
  "lv_country_region_normalized_validation_status": "web_researched"
}
```

D-14 unresolved reasons: {"lv_org_type": "research returned 'Racing Club / Sports Organization', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17)"}

### 20943964946 -- The Rumble / Pacific Action Sports

```json
{
  "lv_produces_content_source": "claude_web",
  "lv_produces_content_confidence": 92,
  "lv_produces_content_evidence_url": "https://www.therumble.com.au/",
  "lv_produces_content_evidence_summary": "The Rumble is owned and operated by Pacific Action Sports, an Australian spectator sports company founded in 2017 based in Mackay, Queensland. The organization produces skateboarding content through the Rumble Pro Tour and Amateur Series events held across Australia. Events are broadcast with average viewership exceeding 740,000 across attendance, social media, and broadcast channels. The organization is highly sponsorship-reliant with title sponsorships (e.g., BMD Rumble Pro Tour) and partnership support from Skate Australia. Broadcasting partnerships include KommunityTV and streamer.com.au/league/rumbleskatetours.",
  "lv_produces_content_verified_at": "2026-08-11T22:02:57.012088+00:00",
  "lv_produces_content_verified_by_model": "claude-haiku-4-5",
  "lv_produces_content_validation_status": "web_researched",
  "lv_country_region_normalized_source": "claude_web",
  "lv_country_region_normalized_confidence": 92,
  "lv_country_region_normalized_evidence_url": "https://au.linkedin.com/company/therumble",
  "lv_country_region_normalized_evidence_summary": "The Rumble is owned and operated by Pacific Action Sports, an Australian spectator sports company founded in 2017 based in Mackay, Queensland. The organization produces skateboarding content through the Rumble Pro Tour and Amateur Series events held across Australia. Events are broadcast with average viewership exceeding 740,000 across attendance, social media, and broadcast channels. The organization is highly sponsorship-reliant with title sponsorships (e.g., BMD Rumble Pro Tour) and partnership support from Skate Australia. Broadcasting partnerships include KommunityTV and streamer.com.au/league/rumbleskatetours.",
  "lv_country_region_normalized_verified_at": "2026-08-11T22:02:57.012088+00:00",
  "lv_country_region_normalized_verified_by_model": "claude-haiku-4-5",
  "lv_country_region_normalized_validation_status": "web_researched"
}
```

D-14 unresolved reasons: {"lv_org_type": "research returned 'Event organizer / Sports league operator', not a recognized lv_org_type enum value and no boolean signal confirmed a mapping -- left unresolved rather than guessed (D-17)"}
