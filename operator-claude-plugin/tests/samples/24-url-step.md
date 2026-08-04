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
