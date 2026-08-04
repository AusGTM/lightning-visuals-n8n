"""operator-claude-plugin/scripts/url_fallback.py

Turn a pasted page URL into an ordered, same-host, capped list of candidate URLs the
model can offer to `web_fetch` when the pasted URL itself fetched but yielded nothing
usable (35-CONTEXT.md §2). `web_fetch` is a model-invoked SERVER tool — this module does
not and cannot call it. Everything here builds strings and nothing else: no HTTP client,
no scraping library, no headless browser, no I/O of any kind. That is what satisfies the
autouse `no_network` guard in tests/conftest.py by construction rather than by a mock —
there is nothing here that could reach the network, so there is nothing to stub.

The safety property this module holds: every candidate URL is on the pasted URL's own
host (`same_host`), and the number of follow-up fetches across the WHOLE ladder is
bounded by one named constant (`MAX_FOLLOWUP_FETCHES`). A sitemap can list thousands of
URLs; an uncapped ladder is a crawler, and a crawler is out of scope per REQUIREMENTS.md.
"""
import json
import sys
from urllib.parse import urlsplit

# Bounds ALL follow-up fetches across the WHOLE ladder (not per rung — four constructed
# candidates against this cap leaves exactly one fetch for a sitemap-derived profile
# page). A sitemap can list thousands of URLs; without a cap, walking one is a crawler,
# and a crawler is explicitly out of scope (REQUIREMENTS.md Out of Scope).
MAX_FOLLOWUP_FETCHES = 5


def slug_of(url):
    """The last non-empty path segment of `url`, trailing extension stripped, or `None`
    when the path has no segment (e.g. the bare site root). Used to build the
    WordPress-REST rungs, which address a page/post by its slug."""
    path = urlsplit(url).path
    segments = [s for s in path.split("/") if s]
    if not segments:
        return None
    last = segments[-1]
    if "." in last:
        last = last.rsplit(".", 1)[0]
    return last or None


def plan_ladder(pasted_url):
    """The ordered candidate ladder for `pasted_url`.

    Returns `{"pasted_url", "host", "cap", "candidates", "notes"}`. `candidates` is
    `[{"url", "rung", "why"}, ...]` in the locked order from 35-CONTEXT.md §3. This task
    (35-01 Task 1) implements rung 1 only — the WordPress-REST pages-by-slug lookup, the
    URL measured live to return all 9 directors for the acceptance case. Later tasks add
    the remaining rungs (posts-by-slug, then the two sitemap rungs) to this same function.
    """
    parts = urlsplit(pasted_url)
    host = parts.netloc
    scheme = parts.scheme or "https"
    slug = slug_of(pasted_url)

    candidates = []
    notes = []

    if slug:
        candidates.append({
            "url": f"{scheme}://{host}/wp-json/wp/v2/pages?slug={slug}",
            "rung": 1,
            "why": "The WordPress REST representation of the same page, if the site runs WordPress.",
        })
    else:
        notes.append(
            "The pasted URL has no path slug (it points at the site root, or a path "
            "with no final segment), so the WordPress-REST rungs cannot be built."
        )

    return {
        "pasted_url": pasted_url,
        "host": host,
        "cap": MAX_FOLLOWUP_FETCHES,
        "candidates": candidates,
        "notes": notes,
    }


if __name__ == "__main__":
    _args = sys.argv[1:]
    try:
        if not _args:
            raise ValueError("usage: url_fallback.py <url>")
        print(json.dumps({"ok": True, **plan_ladder(_args[0])}))
    except Exception as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)
