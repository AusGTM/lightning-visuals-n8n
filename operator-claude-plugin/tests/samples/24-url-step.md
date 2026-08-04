# 2.4 — the public-URL step

This step cannot ship a sample file: the point is that the skill **fetches a real page** with the
native `web_fetch` tool and extracts from what it actually gets back.

Pick a page you are comfortable demoing in front of the client. Good properties:

- **Public and unauthenticated** — no login wall. Authenticated and paywalled scraping is listed
  under Out of Scope in `REQUIREMENTS.md`, and the plugin will not route around it.
- **A real "about", "team", or "contact" page** — somewhere a company genuinely publishes names,
  titles and contact details.
- **Not LinkedIn.** LinkedIn profile data comes from the licensed provider waterfall, never from
  scraping the site. Handing the skill a LinkedIn URL is testing the refusal, not the adapter.

Sensible choices: your own site, the client's own site, or the public "about" page of an
organisation already in their target list.

**Also worth demoing — the negative case.** Give it a URL with no contact data at all (a news
article, a pricing page). "The fetch failed" and "the page had nothing usable" must read as two
different answers. A page that yields nothing is not an error.

---

## Candidate URLs — with what was actually checked

Fetched 2026-08-04. **Verify these yourself before demoing** — pages move, and a 404 in front of a
client is avoidable. The verification status is stated per URL so you know which claims were
tested and which were not.

### Negative case — VERIFIED, use this one

```
https://www.racingvictoria.com.au/about-us/contact-us
```

**Checked and confirmed: zero named individuals, zero job titles, zero email addresses, zero
direct phone numbers.** It is a navigation and footer page — real, public, fetches fine, and
carries nothing extractable.

This is the more interesting half of step 2.4. The fetch **succeeds** and the page is legitimate,
so "the fetch failed" and "there was nothing usable on it" have to read as different answers. And
it is a live invention test: **any contact row returned from this page was fabricated.** That is
STRUCT-04, the most serious defect in the whole UAT.

### Positive case — PICK YOUR OWN, and prefer a page you control

Recommended: your own site, or the client's, on a page you already know publishes names.

Two reasons over a third-party page:

1. **Consent is unambiguous.** A real staff page means real people's names, titles and contact
   details flowing through the demo. Session 2 previews only and dispatch stays disarmed, so
   nothing reaches HubSpot — but extracting a stranger's details live in front of an audience is
   a different proposition from extracting your own team's.
2. **You know it has names on it**, rather than discovering mid-demo that the leadership page moved.

**What makes a good one:** names and titles with **incomplete** contact details — someone with a
title and no email, or a name with no title. Better than a page where everything is present,
because it is the case that tempts the model to fill the gap, and 2.7 is precisely the check that
it did not.

```
POSITIVE-CASE URL: ______________________________________________
```

### Tried and rejected — recorded so nobody re-tries them

| URL | Result |
|---|---|
| `https://www.racingvictoria.com.au/about-us/our-people/executive-team` | **HTTP 404** |
| `https://www.racingnsw.com.au/about-racing-nsw/racing-nsw-staff/` | **HTTP 404** |
| `https://www.mrc.racing.com/about-us/contact-us` | **fetch refused** — the host would not serve the request |

These were guesses at deep paths and all three failed. Noted rather than deleted: the useful
finding is that ANZ racing bodies do not reliably publish a staff page at a predictable URL, so
do not improvise one during a demo.

### Do not use

- **LinkedIn, any profile or company page.** LinkedIn data comes from the licensed provider
  waterfall (ZoomInfo, Apollo, Lusha), never from scraping the site — see the Out of Scope section
  of `REQUIREMENTS.md`. Handing the skill a LinkedIn URL tests the refusal, not the adapter.
- Anything behind a login or paywall. The plugin will not route around it, by design.
