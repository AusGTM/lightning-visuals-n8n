# Batch Dry-Run Report — 2026-07-17

**Mode:** DRY RUN (no HubSpot write) · read-only provider calls + HubSpot search only.

## Provider + gate matrix

| Candidate | Company | Lusha | Apollo | ZoomInfo | #cand | best email | best phone | best title | HS match | gate |
|---|---|---|---|---|---|---|---|---|---|---|
| Gerry Harvey | Harvey Norman | 200 | 200 | 200 | 2 | — | — | Co-Founder (zoominfo) | 0 | create |
| Kyle Bettler | Racing NSW | 200 | 200 | 200 | 10 | kyle.bettler@entaingroup.com.au (lusha) | +61 425 908 432 (zoominfo) | Head of Live Racing (lusha) | 1 | enrich |
| Kieran Granger | Melbourne Racing Club | 200 | 200 | 200 | 8 | kgranger@mrc.net.au (apollo) | +61 466 249 266 (lusha) | Graphic Designer (lusha) | 1 | enrich |
| Mick James | Australian Turf Club | 200 | 200 | 200 | 9 | mjames@australianturfclub.com.au (lusha) | +61 412 867 770 (lusha) | General Manager, AV Broadcast (zoominfo) | 1 | enrich |
| David Preschlack | FanDuel | 200 | 200 | 200 | 5 | preschlack@fanduelsportsnetwork.com (zoominfo) | — | Chief Executive Officer (lusha) | 0 | create |

_Gate acts on read-only search only; no create/update/patch issued this run._

## Raw provider responses

### Gerry Harvey — Harvey Norman  ·  _1&2 rich AU exec (ZoomInfo 200 + Apollo reveal)_

**lusha** — HTTP 200

```json
{
  "contact": {
    "error": {
      "name": "EMPTY_DATA",
      "code": 3
    },
    "isCreditCharged": false,
    "data": null
  }
}
```

**apollo** — HTTP 200

```json
{
  "person": {
    "id": "6a59a19003fa97001cc6ebfb",
    "first_name": "Gerry",
    "last_name": "Harvey",
    "name": "Gerry Harvey",
    "linkedin_url": null,
    "title": null,
    "photo_url": null,
    "twitter_url": null,
    "github_url": null,
    "facebook_url": null,
    "extrapolated_email_confidence": null,
    "headline": null,
    "organization_id": "54a122e769702d84c5ef4b03",
    "employment_history": [
      {
        "_id": "6a59a19103fa97001cc6ebfc",
        "created_at": null,
        "current": true,
        "degree": null,
        "description": null,
        "emails": null,
        "end_date": null,
        "grade_level": null,
        "kind": null,
        "major": null,
        "org_matched_by_name": null,
        "organization_id": "54a122e769702d84c5ef4b03",
        "organization_name": "Harvey Norman",
        "raw_address": null,
        "start_date": null,
        "title": null,
        "updated_at": null,
        "id": "6a59a19103fa97001cc6ebfc",
        "key": "6a59a19103fa97001cc6ebfc"
      }
    ],
    "email": null,
    "email_status": null,
    "organization": {
      "id": "54a122e769702d84c5ef4b03",
      "name": "Harvey Norman Seconds World",
      "website_url": "http://www.harveynorman.com.au",
      "angellist_url": null,
      "linkedin_url": "http://www.linkedin.com/company/2nds-world",
      "twitter_url": "https://twitter.com/2ndsworld",
      "facebook_url": "https://facebook.com/2ndsworld",
      "primary_phone": {
        "number": "+61 2 9748 4898",
        "source": "Owler",
        "sanitized_number": "+61297484898"
      },
      "languages": [
        "English"
      ],
      "alexa_ranking": 13570,
      "phone": "+61 2 9748 4898",
      "linkedin_uid": "2574808",
      "founded_year": 2019,
      "publicly_traded_symbol": null,
      "publicly_traded_exchange": null,
      "logo_url": "https://zenprospect-production.s3.amazonaws.com/uploads/pictures/66e7e2268ccb3f000109e3ed/picture",
      "crunchbase_url": null,
      "primary_domain": "harveynorman.com.au",
      "sic_codes": [
        "2300"
      ],
      "naics_codes": [
        "44-45"
      ],
      "sanitized_phone": "+61297484898",
      "industry": "consumer electronics",
      "estimated_num_employees": 28,
      "keywords": [
        "carton damaged electrical appliances",
        "factory refurbished electrical appliances",
        "factory 2nd electrical appliances",
        "new run out electrical appliances",
        "b2c",
        "e-commerce",
        "retail",
        "consumer internet",
        "consumers",
        "internet",
        "information technology & services",
        "appliances",
        "home & garden",
        "shopping"
      ],
      "organization_revenue_printed": "33.6M",
      "organization_revenue": 33613000,
      "industries": [
        "consumer electronics",
        "retail"
      ],
      "secondary_industries": [
        "retail"
      ],
      "snippets_loaded": true,
      "industry_tag_id": "5567e1947369641ead570000",
      "industry_tag_hash": {
        "consumer electronics": "5567e1947369641ead570000",
        "retail": "5567ced173696450cb580000"
      },
      "retail_location_count": 2,
      "raw_address": "237 Military Road, Cremorne, NSW 2090, AU",
      "street_address": "237 Military Rd",
      "city": "Sydney",
      "state": "New South Wales",
      "postal_code": "2090",
      "country": "Australia",
      "owned_by_organization_id": null,
      "short_description": "Harvey Norman Seconds World offers genuine Factory Seconds, Carton Damaged, Factory Run Out Models and Brand New gas and electrical appliances – all directly from the manufacturers complete with the manufacturers warranty.",
      "suborganizations": [],
      "num_suborganizations": 0,
      "annual_revenue_printed": "33.6M",
      "annual_revenue": 33613000,
      "total_funding": null,
      "total_funding_printed": null,
      "latest_funding_round_date": null,
      "latest_funding_stage": 
```

**zoominfo** — HTTP 200

```json
{
  "data": [
    {
      "attributes": {
        "company": {
          "id": 52709582
        },
        "contactAccuracyScore": "90.0",
        "directPhoneDoNotCall": false,
        "firstName": "Gerry",
        "jobTitle": "Co-Founder",
        "lastName": "Harvey",
        "lastUpdatedDate": "2026-04-26T03:28:00Z",
        "managementLevel": [
          "C-Level"
        ],
        "mobilePhoneDoNotCall": false,
        "validDate": "2026-04-26T03:28:00Z"
      },
      "id": "1667598370",
      "meta": {
        "input": {
          "companyName": "harvey norman",
          "firstName": "gerry",
          "lastName": "harvey"
        },
        "matchStatus": "FULL_MATCH"
      },
      "type": "Contact"
    }
  ]
}
```

**HubSpot search** — HTTP 200, 0 match(es). **Gate:** create (no existing record).

---

### Kyle Bettler — Racing NSW  ·  _3&5 enrich + provider disagreement_

**lusha** — HTTP 200

```json
{
  "contact": {
    "error": null,
    "isCreditCharged": true,
    "data": {
      "firstName": "Kyle",
      "lastName": "Bettler",
      "fullName": "Kyle Bettler",
      "companyId": 6442819,
      "contactTags": [],
      "emailAddresses": [
        {
          "email": "kyle.bettler@entaingroup.com.au",
          "emailType": "work",
          "updateDate": "2026-06-14",
          "emailConfidence": "A+"
        }
      ],
      "phoneNumbers": [],
      "personId": 133767926,
      "location": {
        "country": "Australia",
        "country_iso2": "AU",
        "continent": "Oceania",
        "is_eu_contact": false,
        "city": "Sydney",
        "city_id": 2147714,
        "location_coordinates": [
          151.2073211669922,
          -33.86785125732422
        ],
        "non_accent_country": "Australia"
      },
      "jobTitle": {
        "title": "Head of Live Racing",
        "departments": [
          "Other"
        ],
        "seniority": "Director"
      },
      "socialLinks": {
        "linkedin": "https://www.linkedin.com/in/kyle-bettler-0aab6016a"
      },
      "jobStartDate": "2025-03-01",
      "previousJob": {
        "company": {
          "name": "Racing NSW",
          "domain": "racingnsw.com.au"
        },
        "jobTitle": {
          "title": "Race Fields and Operations Manager",
          "departments": [
            "Operations"
          ],
          "seniority": "manager"
        }
      },
      "updateDate": "2026-05-22",
      "linkedinFollowersCount": 514,
      "linkedinConnectionsCount": 510,
      "company": {
        "name": "Entain Australia & New Zealand",
        "description": "Entain Australia and New Zealand brings effective, sustainable and purposeful solutions to the wagering and entertainment industry. We aim to protect our people, players and partners to ensure they make their game theirs.  \n\nHaving started our journey as Ladbrokes Australia and neds, we have built an obsession with delivering results for our customers, putting them at the core of all we do. We’re a team of leaders, doers and thinkers – with the sum of all our parts equalling a diverse, inclusive and fundamentally different community.  \n\nIn June 2023, we began our strategic partnership in New Zealand, elevating the wagering experience for New Zealand's sports and racing fans.\n\nEntain Australia and New Zealand is the home of Ladbrokes, neds, TAB, betcha, Trackside and Sport Nation - a diverse group of brands created and driven by our region's best talent. We are constantly working to provide a richer and more engaging experience for our customers.\n\nFind out more about us at https://entaingroup.com.au/.",
        "domains": {
          "homepage": "entaingroup.com.au",
          "email": "entaingroup.com.au"
        },
        "homepageUrl": "https://entaingroup.com.au",
        "fqdn": "www.entaingroup.com.au",
        "location": {
          "city": "Brisbane",
          "continent": "Oceania",
          "country": "Australia",
          "countryIso2": "AU",
          "state": "Queensland",
          "stateCode": "QLD"
        },
        "companySize": [
          501,
          1000
        ],
        "revenueRange": [],
        "logoUrl": "https://logo.lusha.co/brightdata/year=2024/month=04/day=30/j_lvlw11g91sii32utf9.44a3221812a6b7776f724838ce18fc2561ced8c6.file_lvlwx1b222azggwai0.logo_cached.jpg",
        "social": {
          "linkedin": "https://www.linkedin.com/company/ladbrokes-australia"
        },
        "specialities": [
          "customer service",
          "entertainment providers",
          "information technology",
          "marketing",
          "mobile betting",
          "sports betting",
          "wagering"
        ],
        "technologies": null,
        "funding": null,
        "intent": null,
        "mainIndustry": "Entertainment",
        "subIndustry": "Entertainment Providers",
        "industryPrimaryGroupDetails": {
          "sics": [
            {
     
```

**apollo** — HTTP 200

```json
{
  "person": {
    "id": "5d39210280f93eb316641b74",
    "first_name": "Kyle",
    "last_name": "Bettler",
    "name": "Kyle Bettler",
    "linkedin_url": "http://www.linkedin.com/in/kyle-bettler-0aab6016a",
    "title": "Head of Live Racing",
    "photo_url": "https://media.licdn.com/dms/image/v2/D5603AQHC2kaa293e5A/profile-displayphoto-shrink_200_200/profile-displayphoto-shrink_200_200/0/1691661318667?e=2147483647&v=beta&t=goE2EO5m3HGt-SnM0ddci_iUYbJ_bPNrEA_kV3ZaqrY",
    "twitter_url": null,
    "github_url": null,
    "facebook_url": null,
    "extrapolated_email_confidence": null,
    "headline": null,
    "organization_id": "65ed4f0affa71f01aeff7160",
    "employment_history": [
      {
        "_id": "6a527c1f487fe20001b54bac",
        "created_at": null,
        "current": true,
        "degree": null,
        "description": null,
        "emails": null,
        "end_date": null,
        "grade_level": null,
        "kind": null,
        "major": null,
        "org_matched_by_name": null,
        "organization_id": "65ed4f0affa71f01aeff7160",
        "organization_name": "Entain Media",
        "raw_address": null,
        "start_date": null,
        "title": "Head of Live Racing",
        "updated_at": null,
        "id": "6a527c1f487fe20001b54bac",
        "key": "6a527c1f487fe20001b54bac"
      },
      {
        "_id": "6a527c1f487fe20001b54bad",
        "created_at": null,
        "current": false,
        "degree": null,
        "description": null,
        "emails": null,
        "end_date": null,
        "grade_level": null,
        "kind": null,
        "major": null,
        "org_matched_by_name": false,
        "organization_id": "55696bc073696425492b2400",
        "organization_name": "Entain Australia & New Zealand",
        "raw_address": null,
        "start_date": "2025-03-01",
        "title": "Head of Live Racing - Entain Media",
        "updated_at": null,
        "id": "6a527c1f487fe20001b54bad",
        "key": "6a527c1f487fe20001b54bad"
      },
      {
        "_id": "6a527c1f487fe20001b54bae",
        "created_at": null,
        "current": false,
        "degree": null,
        "description": null,
        "emails": null,
        "end_date": null,
        "grade_level": null,
        "kind": null,
        "major": null,
        "org_matched_by_name": false,
        "organization_id": "65f54c1342bf150007720f4b",
        "organization_name": "Race Connects",
        "raw_address": null,
        "start_date": "2022-12-01",
        "title": "Director",
        "updated_at": null,
        "id": "6a527c1f487fe20001b54bae",
        "key": "6a527c1f487fe20001b54bae"
      },
      {
        "_id": "6a527c1f487fe20001b54baf",
        "created_at": null,
        "current": false,
        "degree": null,
        "description": null,
        "emails": null,
        "end_date": "2025-03-01",
        "grade_level": null,
        "kind": null,
        "major": null,
        "org_matched_by_name": false,
        "organization_id": "55696bc073696425492b2400",
        "organization_name": "Entain Australia & New Zealand",
        "raw_address": null,
        "start_date": "2024-08-01",
        "title": "Head of Programming and Performance",
        "updated_at": null,
        "id": "6a527c1f487fe20001b54baf",
        "key": "6a527c1f487fe20001b54baf"
      },
      {
        "_id": "6a527c1f487fe20001b54bb0",
        "created_at": null,
        "current": false,
        "degree": null,
        "description": null,
        "emails": null,
        "end_date": "2024-08-01",
        "grade_level": null,
        "kind": null,
        "major": null,
        "org_matched_by_name": false,
        "organization_id": "5d0998c5a3ae615347d95c79",
        "organization_name": "Racing NSW",
        "raw_address": null,
        "start_date": "2022-05-01",
        "title": "Race Fields and Operations Manager",
        "updated_at": null,
        "id": "6a527c1f487fe20001b54bb0",
        "key": "6a527c1f487fe20001b54bb0"
      },
```

**zoominfo** — HTTP 200

```json
{
  "data": [
    {
      "attributes": {
        "company": {
          "id": 1334841652
        },
        "contactAccuracyScore": "93.0",
        "directPhoneDoNotCall": false,
        "email": "kyle.bettler@entaingroup.com.au",
        "firstName": "Kyle",
        "jobTitle": "Live Racing Entain Media Head",
        "lastName": "Bettler",
        "lastUpdatedDate": "2025-07-16T08:25:00Z",
        "managementLevel": [
          "Director"
        ],
        "mobilePhone": "+61 425 908 432",
        "mobilePhoneDoNotCall": false,
        "validDate": "2025-12-30T00:00:00Z"
      },
      "id": "6320514648",
      "meta": {
        "input": {
          "companyName": "racing nsw",
          "firstName": "kyle",
          "lastName": "bettler"
        },
        "matchStatus": "FULL_MATCH"
      },
      "type": "Contact"
    }
  ]
}
```

**HubSpot search** — HTTP 200, 1 match(es). **Gate:** enrich (missing: jobtitle,mobilephone).

---

### Kieran Granger — Melbourne Racing Club  ·  _4 skip (existing, fresh)_

**lusha** — HTTP 200

```json
{
  "contact": {
    "error": null,
    "isCreditCharged": true,
    "data": {
      "firstName": "Kieran",
      "lastName": "Granger",
      "fullName": "Kieran Granger",
      "companyId": 1806312,
      "contactTags": [],
      "emailAddresses": [
        {
          "email": "kgranger@mrc.net.au",
          "emailType": "work",
          "updateDate": "2025-03-09",
          "emailConfidence": "A+"
        },
        {
          "email": "kgranger@melbourneracingclub.net.au",
          "emailType": "work",
          "updateDate": "2025-09-06",
          "emailConfidence": "A+"
        }
      ],
      "phoneNumbers": [
        {
          "number": "+61 466 249 266",
          "phoneType": "mobile",
          "doNotCall": false
        }
      ],
      "personId": 5705598,
      "location": {
        "country": "Australia",
        "country_iso2": "AU",
        "continent": "Oceania",
        "is_eu_contact": false,
        "city": "Melbourne",
        "city_id": 2158177,
        "location_coordinates": [
          144.96331787109375,
          -37.81399917602539
        ],
        "non_accent_country": "Australia"
      },
      "jobTitle": {
        "title": "Graphic Designer",
        "departments": [
          "Other"
        ],
        "seniority": "Non-Manager"
      },
      "socialLinks": {
        "linkedin": "https://www.linkedin.com/in/kieran-granger-79517599"
      },
      "jobStartDate": "2014-08-01",
      "previousJob": {
        "company": {
          "name": "Coles Group",
          "domain": "colescareers.com.au"
        },
        "jobTitle": {
          "title": "Digital Designer",
          "departments": [
            "Product"
          ]
        }
      },
      "updateDate": "2026-05-04",
      "linkedinFollowersCount": 166,
      "linkedinConnectionsCount": 165,
      "company": {
        "name": "Melbourne Racing Club",
        "description": "The Melbourne Racing Club (MRC) is proud to be recognised as a 2022, 2023 & 2024 Winner of The Australian Business Award for Employer of Choice. \n\nThe Melbourne Racing Club is one of Australia’s most vibrant Sporting and Event providers comprising of Caulfield, Sportsbet Sandown and Mornington Racecourses as well as Pegasus Leisure Group, a suite of 14 hotel and club venues located across Metropolitan Melbourne. \n\nAlong with horse racing, the Melbourne Racing Club holds functions and events of all sizes across our racing venues that include lifestyle and leisure shows, trade shows, festivals and university exams to name a few. Sportsbet Sandown is also one of Australia’s premier motorsport facilities and hosts race days for various motorsport clubs throughout the year in addition to being one of the locations used by the V8 Supercars. \n\nWe employ over 1500 employees in casual, part time and full time roles across the many areas of the business.",
        "domains": {
          "homepage": "mrc.racing.com",
          "email": "melbourneracingclub.net.au"
        },
        "homepageUrl": "https://mrc.racing.com",
        "fqdn": "mrc.racing.com",
        "location": {
          "city": "Caulfield East",
          "continent": "Oceania",
          "country": "Australia",
          "countryIso2": "AU",
          "state": "Victoria",
          "stateCode": "VIC"
        },
        "companySize": [
          1001,
          5000
        ],
        "revenueRange": [
          250000000,
          500000000
        ],
        "logoUrl": "https://logo.lusha.co/brightdata/year=2024/month=05/day=05/j_lvsyu4uf7zrxokw6h.a97e0fe75be87e5d3b26b7306136d1561590d153.file_lvsyv1651picjj7564.logo_cached.jpg",
        "social": {
          "linkedin": "https://www.linkedin.com/company/melbourne-racing-club"
        },
        "specialities": [
          "entertainment",
          "event venue",
          "events services",
          "gaming",
          "horse racing",
          "hospitality",
          "hotel operations",
          "member experience",
          "specta
```

**apollo** — HTTP 200

```json
{
  "person": {
    "id": "54a511047468692fa2257d7a",
    "first_name": "Kieran",
    "last_name": "Granger",
    "name": "Kieran Granger",
    "linkedin_url": "http://www.linkedin.com/in/kieran-granger-79517599",
    "title": "Graphic Designer",
    "photo_url": "https://static.licdn.com/aero-v1/sc/h/9c8pery4andzj6ohjkjp54ma2",
    "twitter_url": null,
    "github_url": null,
    "facebook_url": null,
    "extrapolated_email_confidence": null,
    "headline": "Graphic Designer",
    "organization_id": "5f497714d2af3f000121ef6b",
    "employment_history": [
      {
        "_id": "6a2475360bc5f70001f80c31",
        "created_at": null,
        "current": true,
        "degree": null,
        "description": null,
        "emails": null,
        "end_date": null,
        "grade_level": null,
        "kind": null,
        "major": null,
        "org_matched_by_name": false,
        "organization_id": "5f497714d2af3f000121ef6b",
        "organization_name": "Melbourne Racing Club",
        "raw_address": null,
        "start_date": "2014-08-01",
        "title": "Graphic Designer",
        "updated_at": null,
        "id": "6a2475360bc5f70001f80c31",
        "key": "6a2475360bc5f70001f80c31"
      },
      {
        "_id": "6a2475360bc5f70001f80c32",
        "created_at": null,
        "current": false,
        "degree": null,
        "description": null,
        "emails": null,
        "end_date": "2014-07-01",
        "grade_level": null,
        "kind": null,
        "major": null,
        "org_matched_by_name": false,
        "organization_id": "54a1274d69702d90a267a700",
        "organization_name": "Coles",
        "raw_address": null,
        "start_date": "2014-05-01",
        "title": "Digital Designer",
        "updated_at": null,
        "id": "6a2475360bc5f70001f80c32",
        "key": "6a2475360bc5f70001f80c32"
      },
      {
        "_id": "6a2475360bc5f70001f80c33",
        "created_at": null,
        "current": false,
        "degree": null,
        "description": null,
        "emails": null,
        "end_date": "2014-02-01",
        "grade_level": null,
        "kind": null,
        "major": null,
        "org_matched_by_name": false,
        "organization_id": null,
        "organization_name": "Whitebait TV",
        "raw_address": null,
        "start_date": "2010-05-01",
        "title": "Website and Social Media Coordinator",
        "updated_at": null,
        "id": "6a2475360bc5f70001f80c33",
        "key": "6a2475360bc5f70001f80c33"
      }
    ],
    "street_address": "",
    "city": "Melbourne",
    "state": "Victoria",
    "country": "Australia",
    "postal_code": null,
    "formatted_address": "Melbourne VIC, Australia",
    "time_zone": "Australia/Sydney",
    "email": "kgranger@mrc.net.au",
    "email_status": "verified",
    "contact_id": "6681eed91a1ab90001345f45",
    "contact": {
      "contact_roles": [],
      "id": "6681eed91a1ab90001345f45",
      "first_name": "Kieran",
      "last_name": "Granger",
      "name": "Kieran Granger",
      "linkedin_url": "http://www.linkedin.com/in/kieran-granger-79517599",
      "title": "Senior Designer",
      "contact_stage_id": "66455252610ab3074641db8a",
      "owner_id": "66455254610ab3074641dcee",
      "creator_id": "66455254610ab3074641dcee",
      "person_id": "54a511047468692fa2257d7a",
      "email_needs_tickling": null,
      "organization_name": "Melbourne Race Club",
      "source": "crm",
      "original_source": "email_import",
      "organization_id": "5f497714d2af3f000121ef6b",
      "headline": "Graphic Designer",
      "photo_url": null,
      "present_raw_address": "Caulfield East, VIC, Australia",
      "linkedin_uid": null,
      "extrapolated_email_confidence": null,
      "salesforce_id": null,
      "salesforce_lead_id": null,
      "salesforce_contact_id": null,
      "salesforce_account_id": null,
      "crm_owner_id": "225679910",
      "created_at": "2024-06-30T23:48:41.060Z",
      "emailer_campaign_ids": [],
      "direct_di
```

**zoominfo** — HTTP 200

```json
{
  "data": [
    {
      "id": "163d9a75-2211-4787-8621-38384f897e64",
      "meta": {
        "input": {
          "companyName": "melbourne racing club",
          "firstName": "kieran",
          "lastName": "granger"
        },
        "matchStatus": "NO_MATCH"
      },
      "type": "NoMatch"
    }
  ]
}
```

**HubSpot search** — HTTP 200, 1 match(es). **Gate:** enrich (stale: jobtitle,mobilephone; invalid: mobilephone).

---

### Mick James — Australian Turf Club  ·  _4 skip (existing, fresh)_

**lusha** — HTTP 200

```json
{
  "contact": {
    "error": null,
    "isCreditCharged": true,
    "data": {
      "firstName": "Mick",
      "lastName": "James",
      "fullName": "Mick James",
      "companyId": 966219,
      "contactTags": [],
      "emailAddresses": [
        {
          "email": "mjames@australianturfclub.com.au",
          "emailType": "work",
          "updateDate": "2023-07-21",
          "emailConfidence": "A+"
        }
      ],
      "phoneNumbers": [
        {
          "number": "+61 412 867 770",
          "phoneType": "mobile",
          "doNotCall": false,
          "updateDate": "2026-07-06"
        }
      ],
      "personId": 1000685546,
      "location": {
        "country": "Australia",
        "country_iso2": "AU",
        "continent": "Oceania",
        "is_eu_contact": false,
        "state": "New South Wales",
        "state_code": "NSW",
        "non_accent_country": "Australia",
        "non_accent_state": "New South Wales"
      },
      "jobTitle": {
        "title": "General Manager of Broadcast",
        "departments": [
          "Other"
        ],
        "seniority": "Manager"
      },
      "socialLinks": {
        "linkedin": "https://www.linkedin.com/in/mick-james-a63390183"
      },
      "jobStartDate": "2022-11-01",
      "previousJob": {
        "company": {
          "name": "Australian Turf Club",
          "domain": "australianturfclub.com.au"
        },
        "jobTitle": {
          "title": "General Manager Av Broadcast",
          "departments": [
            "General Management"
          ],
          "seniority": "c-suite"
        }
      },
      "updateDate": "2026-06-11",
      "linkedinFollowersCount": 279,
      "linkedinConnectionsCount": 275,
      "company": {
        "name": "Australian Turf Club",
        "description": "The Australian Turf Club prides itself on being one of the world's most desirable destinations for thoroughbred racing, events and hospitality. Born from a proud and iconic heritage of racing and entertainment in New South Wales, the Australian Turf Club is a uniting celebration of what Sydney truly has to offer.\n\nWe bring together the past with the future, pedigree with performance, youth with experience and style with excitement. We deliver the very best in Australian racing week in week out, through our world-class venues that effortlessly imbue fashion, sophistication and elegance into every experience.\n\nTo our most prized assets, our members, we provide a constantly evolving portfolio of products and services that ultimately delivers a desirable, rewarding and exclusive experience.\n\nTogether with our winning network of members, sponsors, racing industry partners, event customers and suppliers, we create mutual, enduring value to entertainment in NSW.\n\nWelcome to the heart of Sydney racing.",
        "domains": {
          "homepage": "australianturfclub.com.au",
          "email": "australianturfclub.com.au"
        },
        "homepageUrl": "https://australianturfclub.com.au",
        "fqdn": "www.australianturfclub.com.au",
        "location": {
          "city": "Randwick",
          "continent": "Oceania",
          "country": "Australia",
          "countryIso2": "AU",
          "state": "New South Wales",
          "stateCode": "NSW"
        },
        "companySize": [
          201,
          500
        ],
        "revenueRange": [
          250000000,
          500000000
        ],
        "logoUrl": "https://logo.lusha.co/brightdata/year=2024/month=04/day=30/j_lvlwj21o2g5cgcaxt8.e8019ee90860267ba88237c5513b09b0bd87d28f.file_lvlxasaa2fqojy12ul.logo_cached.jpg",
        "social": {
          "linkedin": "https://www.linkedin.com/company/australian-turf-club"
        },
        "specialities": [
          "event venue",
          "events",
          "events services",
          "hospitality",
          "member services",
          "thoroughbred racing"
        ],
        "technologies": null,
        "funding": null,
        "intent": null,
  
```

**apollo** — HTTP 200

```json
{
  "person": {
    "id": "63f6f635a5c1560001ade989",
    "first_name": "Mick",
    "last_name": "James",
    "name": "Mick James",
    "linkedin_url": "http://www.linkedin.com/in/mick-james-a63390183",
    "title": "General Manager AV Broadcast",
    "photo_url": "https://media.licdn.com/dms/image/v2/C5603AQFKgWU0WXdL_g/profile-displayphoto-shrink_200_200/profile-displayphoto-shrink_200_200/0/1659345659857?e=2147483647&v=beta&t=IOWBjVspLU5_vZ0QFLcnQdwYBHMzgjt4HEVRgaCUk8s",
    "twitter_url": null,
    "github_url": null,
    "facebook_url": null,
    "extrapolated_email_confidence": null,
    "headline": "General Manager AV Broadcast - Australian Turf Club.",
    "organization_id": "54a12a5769702d9b8b011302",
    "employment_history": [
      {
        "_id": "6a478193ecb759000183522e",
        "created_at": null,
        "current": true,
        "degree": null,
        "description": null,
        "emails": null,
        "end_date": null,
        "grade_level": null,
        "kind": null,
        "major": null,
        "org_matched_by_name": false,
        "organization_id": "54a12a5769702d9b8b011302",
        "organization_name": "Australian Turf Club",
        "raw_address": null,
        "start_date": "2022-11-01",
        "title": "General Manager AV Broadcast",
        "updated_at": null,
        "id": "6a478193ecb759000183522e",
        "key": "6a478193ecb759000183522e"
      },
      {
        "_id": "6a478193ecb759000183522f",
        "created_at": null,
        "current": false,
        "degree": null,
        "description": null,
        "emails": null,
        "end_date": "2022-11-01",
        "grade_level": null,
        "kind": null,
        "major": null,
        "org_matched_by_name": false,
        "organization_id": "54a12a5769702d9b8b011302",
        "organization_name": "Australian Turf Club",
        "raw_address": null,
        "start_date": "2022-08-01",
        "title": "Head of AV",
        "updated_at": null,
        "id": "6a478193ecb759000183522f",
        "key": "6a478193ecb759000183522f"
      },
      {
        "_id": "6a478193ecb7590001835230",
        "created_at": null,
        "current": false,
        "degree": null,
        "description": null,
        "emails": null,
        "end_date": "2022-07-01",
        "grade_level": null,
        "kind": null,
        "major": null,
        "org_matched_by_name": false,
        "organization_id": "54a12a5769702d9b8b011302",
        "organization_name": "Australian Turf Club",
        "raw_address": null,
        "start_date": "2017-09-01",
        "title": "Technical Manager AV",
        "updated_at": null,
        "id": "6a478193ecb7590001835230",
        "key": "6a478193ecb7590001835230"
      },
      {
        "_id": "6a478193ecb7590001835231",
        "created_at": null,
        "current": false,
        "degree": null,
        "description": null,
        "emails": null,
        "end_date": "2017-09-01",
        "grade_level": null,
        "kind": null,
        "major": null,
        "org_matched_by_name": false,
        "organization_id": "54a12a5769702d9b8b011302",
        "organization_name": "Australian Turf Club",
        "raw_address": null,
        "start_date": "2015-09-01",
        "title": "Digital Content & Asset Manager",
        "updated_at": null,
        "id": "6a478193ecb7590001835231",
        "key": "6a478193ecb7590001835231"
      },
      {
        "_id": "6a478193ecb7590001835232",
        "created_at": null,
        "current": false,
        "degree": null,
        "description": null,
        "emails": null,
        "end_date": "2015-09-01",
        "grade_level": null,
        "kind": null,
        "major": null,
        "org_matched_by_name": false,
        "organization_id": "57c4bbd8a6da98370bc98b10",
        "organization_name": "The Star Entertainment Group",
        "raw_address": null,
        "start_date": "2011-09-01",
        "title": "Digital Media Operations Manager",
        "updated_at": null,
        "i
```

**zoominfo** — HTTP 200

```json
{
  "data": [
    {
      "attributes": {
        "company": {
          "id": 345601557
        },
        "contactAccuracyScore": "91.0",
        "directPhoneDoNotCall": false,
        "firstName": "Michael",
        "jobTitle": "General Manager, AV Broadcast",
        "lastName": "James",
        "lastUpdatedDate": "2026-05-01T12:04:00Z",
        "managementLevel": [
          "Director"
        ],
        "mobilePhoneDoNotCall": false,
        "validDate": "2026-04-29T12:59:00Z"
      },
      "id": "9703587928",
      "meta": {
        "input": {
          "companyName": "australian turf club",
          "firstName": "mick",
          "lastName": "james"
        },
        "matchStatus": "FULL_MATCH"
      },
      "type": "Contact"
    }
  ]
}
```

**HubSpot search** — HTTP 200, 1 match(es). **Gate:** enrich (stale: jobtitle,mobilephone).

---

### David Preschlack — FanDuel  ·  _6 non-AU (US) — phone normalizer -> review_

**lusha** — HTTP 200

```json
{
  "contact": {
    "error": null,
    "isCreditCharged": true,
    "data": {
      "firstName": "David",
      "lastName": "Preschlack",
      "fullName": "David Preschlack",
      "companyId": 71647200,
      "contactTags": [],
      "emailAddresses": [],
      "phoneNumbers": [
        {
          "number": "+1 203-260-8401",
          "phoneType": "mobile",
          "doNotCall": true
        }
      ],
      "personId": 107336886,
      "location": {
        "country": "United States",
        "country_iso2": "US",
        "continent": "North America",
        "is_eu_contact": false,
        "state": "Connecticut",
        "state_code": "CT",
        "city": "Southport",
        "city_id": 4843395,
        "location_coordinates": [
          -73.283447265625,
          41.13648986816406
        ],
        "non_accent_country": "United States",
        "non_accent_state": "Connecticut"
      },
      "jobTitle": {
        "title": "Chief Executive Officer",
        "departments": [
          "General Management"
        ],
        "seniority": "C-Suite"
      },
      "socialLinks": {
        "linkedin": "https://www.linkedin.com/in/david-preschlack-66570a3"
      },
      "jobStartDate": "2022-12-01",
      "previousJob": {
        "company": {},
        "jobTitle": {
          "title": "Executive Vice President of Affiliate Sales and Marketing",
          "departments": [
            "Sales",
            "Marketing"
          ],
          "seniority": "vice president"
        }
      },
      "updateDate": "2026-06-03",
      "linkedinFollowersCount": 2261,
      "linkedinConnectionsCount": 500,
      "linkedinAwards": [
        {
          "companyName": "Denison University",
          "dateYear": 2015,
          "title": "Alumni Citation Award"
        },
        {
          "companyName": "NCTA",
          "dateYear": 2013,
          "title": "Vanguard Award for Young Leadership"
        },
        {
          "companyName": "Sports Business Journal",
          "dateYear": 2009,
          "title": "Forty Under 40 Hall of Fame"
        }
      ],
      "company": {
        "name": "FanDuel Sports Network",
        "description": "FanDuel Sports Network is the nation’s leading provider of local sports. Main Street Sports Group, LLC, formerly known as Diamond Sports Group, owns the FanDuel Sports Network Regional Sports Networks (RSNs). Its 15 owned-and-operated RSNs include FanDuel Sports Network Detroit, FanDuel Sports Network Florida, FanDuel Sports Network Kansas City, FanDuel Sports Network Indiana, FanDuel Sports Network Midwest, FanDuel Sports Network North, FanDuel Sports Network Ohio, FanDuel Sports Network Oklahoma, FanDuel Sports Network SoCal, FanDuel Sports Network South, FanDuel Sports Network Southeast, FanDuel Sports Network Southwest, FanDuel Sports Network Sun, FanDuel Sports Network West, and FanDuel Sports Network Wisconsin.",
        "domains": {
          "homepage": "fanduelsportsnetwork.com",
          "email": "ballysports.com"
        },
        "homepageUrl": "https://fanduelsportsnetwork.com",
        "fqdn": "www.fanduelsportsnetwork.com",
        "location": {
          "continent": "North America",
          "country": "United States",
          "countryIso2": "US",
          "state": "California",
          "stateCode": "CA"
        },
        "companySize": [
          501,
          1000
        ],
        "revenueRange": [
          1000000000,
          10000000000
        ],
        "logoUrl": "https://logo.lusha.co/brightdata/year=2024/month=04/day=30/j_lvludw3ia7j3h0bkh.0e3d0baa1ba2ce0e24564853026879cd4ca4118f.file_lvluegir2ks1seh29d.logo_cached.jpg",
        "social": {
          "linkedin": "https://www.linkedin.com/company/fanduel-sports-network"
        },
        "specialities": [
          "broadcast media",
          "original programming",
          "sports broadcasting",
          "sports content"
        ],
        "technologies": null,
        "funding": null,
        "i
```

**apollo** — HTTP 200

```json
{
  "person": {
    "id": "6a59a1946b48980020951a04",
    "first_name": "David",
    "last_name": "Preschlack",
    "name": "David Preschlack",
    "linkedin_url": null,
    "title": null,
    "photo_url": null,
    "twitter_url": null,
    "github_url": null,
    "facebook_url": null,
    "extrapolated_email_confidence": null,
    "headline": null,
    "organization_id": "6708b8beba95b0000135ef29",
    "employment_history": [
      {
        "_id": "6a59a1946b48980020951a05",
        "created_at": null,
        "current": true,
        "degree": null,
        "description": null,
        "emails": null,
        "end_date": null,
        "grade_level": null,
        "kind": null,
        "major": null,
        "org_matched_by_name": null,
        "organization_id": "6708b8beba95b0000135ef29",
        "organization_name": "FanDuel",
        "raw_address": null,
        "start_date": null,
        "title": null,
        "updated_at": null,
        "id": "6a59a1946b48980020951a05",
        "key": "6a59a1946b48980020951a05"
      }
    ],
    "email": null,
    "email_status": null,
    "organization": {
      "id": "6708b8beba95b0000135ef29",
      "name": "FanDuel",
      "website_url": "http://www.fanduel.com",
      "angellist_url": null,
      "linkedin_url": "http://www.linkedin.com/company/fanduel",
      "twitter_url": "https://twitter.com/fanduelcareers",
      "facebook_url": "https://facebook.com/fanduel",
      "primary_phone": {},
      "languages": [
        "English"
      ],
      "alexa_ranking": 3470,
      "phone": null,
      "linkedin_uid": "1821549",
      "founded_year": 2009,
      "publicly_traded_symbol": null,
      "publicly_traded_exchange": null,
      "logo_url": "https://zenprospect-production.s3.amazonaws.com/uploads/pictures/6a39601f4beffb00019bedbd/picture",
      "crunchbase_url": null,
      "primary_domain": "fanduel.com",
      "sic_codes": [
        "7372"
      ],
      "naics_codes": [
        "713290",
        "519290"
      ],
      "industry": "entertainment",
      "estimated_num_employees": 4100,
      "keywords": [
        "entertainment providers"
      ],
      "organization_revenue_printed": "7.0B",
      "organization_revenue": 6967000000,
      "industries": [
        "entertainment",
        "gambling & casinos",
        "internet"
      ],
      "secondary_industries": [
        "gambling & casinos",
        "internet"
      ],
      "snippets_loaded": true,
      "industry_tag_id": "5567cdd37369643b80510000",
      "industry_tag_hash": {
        "entertainment": "5567cdd37369643b80510000",
        "gambling & casinos": "5567e0cf7369641233e50600",
        "internet": "5567cd4d736964397e020000"
      },
      "retail_location_count": 0,
      "raw_address": "300 Park Avenue South, New York, New York, United States, 10010",
      "street_address": "300 Park Avenue South",
      "city": "New York",
      "state": "New York",
      "postal_code": "10010",
      "country": "United States",
      "owned_by_organization_id": "5db035ea09a15d00da0aef4a",
      "owned_by_organization": {
        "id": "5db035ea09a15d00da0aef4a",
        "name": "Flutter Entertainment",
        "website_url": "http://www.flutter.com"
      },
      "short_description": "FanDuel is a leading American sportsbook and iGaming brand, providing a wide range of entertainment options including sports betting, daily fantasy sports, horse racing, and online casino services. Founded in 2009 in Edinburgh, Scotland, the company has grown significantly, especially after the legalization of sports betting in the U.S. in 2018. Headquartered in New York City, FanDuel employs around 4,000 people across various locations.\n\nThe company operates online sportsbooks in 25 states and offers a daily fantasy sports platform where users can draft teams and compete for cash prizes. FanDuel also features an advance-deposit wagering platform for horse racing and an online casino with various games. Additionally, FanDuel TV provides
```

**zoominfo** — HTTP 200

```json
{
  "data": [
    {
      "attributes": {
        "company": {
          "id": 1339119187
        },
        "contactAccuracyScore": "94.0",
        "directPhoneDoNotCall": false,
        "email": "preschlack@fanduelsportsnetwork.com",
        "firstName": "David",
        "jobTitle": "Chief Executive Officer",
        "lastName": "Preschlack",
        "lastUpdatedDate": "2026-06-04T17:38:00Z",
        "managementLevel": [
          "C-Level"
        ],
        "mobilePhone": "(475) 450-4590",
        "mobilePhoneDoNotCall": true,
        "validDate": "2025-08-13T00:00:00Z"
      },
      "id": "984052779",
      "meta": {
        "input": {
          "companyName": "fanduel",
          "firstName": "david",
          "lastName": "preschlack"
        },
        "matchStatus": "FULL_MATCH"
      },
      "type": "Contact"
    }
  ]
}
```

**HubSpot search** — HTTP 200, 0 match(es). **Gate:** create (no existing record).

---

