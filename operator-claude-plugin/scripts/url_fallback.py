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
    `[{"url", "rung", "why"}, ...]` in the locked order from 35-CONTEXT.md §3: WordPress
    REST pages-by-slug, then posts-by-slug, then the two same-host sitemap rungs. A
    slug-less URL (the site root, or a path with no final segment) skips the two
    WordPress-REST rungs — there is no slug to look up — but still offers both sitemap
    rungs, since those address the whole host rather than one page.
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
        candidates.append({
            "url": f"{scheme}://{host}/wp-json/wp/v2/posts?slug={slug}",
            "rung": 2,
            "why": "The same page filed as a WordPress post rather than a page.",
        })
    else:
        notes.append(
            "The pasted URL has no path slug (it points at the site root, or a path "
            "with no final segment), so the WordPress-REST rungs cannot be built."
        )

    candidates.append({
        "url": f"{scheme}://{host}/sitemap.xml",
        "rung": 3,
        "why": "The site's general sitemap, which may list an individual profile page for this content.",
    })
    candidates.append({
        "url": f"{scheme}://{host}/wp-sitemap.xml",
        "rung": 4,
        "why": "WordPress's own default sitemap path, in case the general one is not served.",
    })

    return {
        "pasted_url": pasted_url,
        "host": host,
        "cap": MAX_FOLLOWUP_FETCHES,
        "candidates": candidates,
        "notes": notes,
    }


def same_host(pasted_url, candidate_url):
    """True only when `candidate_url` is on exactly `pasted_url`'s host: netloc (host and
    port together), case-folded. A `www.` variant is a DIFFERENT netloc and is refused —
    the deliberate strictness is the safe side of the line, because the alternative is a
    rule that has to guess which host variants are "really" the same site. Scheme is not
    required to match (http vs. https is not a different host)."""
    return urlsplit(pasted_url).netloc.casefold() == urlsplit(candidate_url).netloc.casefold()


def filter_candidates(pasted_url, urls, already_fetched=0):
    """The guard every candidate URL must pass before it may be fetched.

    This is the guard on sitemap-derived candidates SPECIFICALLY: those URLs come out of
    fetched page content, which is attacker-influenceable data (a page can list any URL
    it likes), so a candidate is never fetched without passing through here first.

    Returns `{"accepted", "refused", "cap", "budget_remaining"}`. `refused` entries are
    `{"url", "reason"}`. Checks run in this order — scheme, then host, then budget — so
    an off-host URL is refused for being off-host rather than for exhausting a budget it
    was never entitled to spend in the first place.
    """
    pasted_host = urlsplit(pasted_url).netloc
    budget_remaining = max(MAX_FOLLOWUP_FETCHES - already_fetched, 0)

    accepted = []
    refused = []
    for url in urls:
        scheme = urlsplit(url).scheme
        if scheme not in ("http", "https"):
            refused.append({
                "url": url,
                "reason": f"{scheme or '(no scheme)'!r} is not an http or https URL — refusing to fetch it.",
            })
            continue
        if not same_host(pasted_url, url):
            refused.append({
                "url": url,
                "reason": (
                    f"{urlsplit(url).netloc} is not the pasted URL's host "
                    f"({pasted_host}) — refusing to follow it off-host."
                ),
            })
            continue
        if len(accepted) >= budget_remaining:
            refused.append({
                "url": url,
                "reason": (
                    f"the follow-up fetch cap ({MAX_FOLLOWUP_FETCHES}) is exhausted "
                    f"({already_fetched} already spent this run)."
                ),
            })
            continue
        accepted.append(url)

    return {
        "accepted": accepted,
        "refused": refused,
        "cap": MAX_FOLLOWUP_FETCHES,
        "budget_remaining": budget_remaining,
    }


def give_up_message(pasted_url, attempts):
    """The final give-up paragraph: what was tried, in order, and NOTHING about why the
    page was empty.

    The rule this function enforces: it reports what was tried and draws no conclusion
    about the cause. The previous version of this contract handed the model a rendering
    verdict ("likely a client-rendered page this tool cannot execute"); the live GCTC
    walk (35-CONTEXT.md §2) repeated that verdict back to the operator, and it was
    wrong — the content was server-side available the whole time, at a URL this very
    module can build. `attempts` is `[{"url", "outcome"}, ...]`, the model's own record
    of what it tried after the pasted URL fetched but came back empty.
    """
    lines = [f"Could not find usable contact or company data at {pasted_url}."]
    if attempts:
        lines.append("Also tried, in this order:")
        for attempt in attempts:
            lines.append(f"- {attempt['url']} — {attempt['outcome']}")
    else:
        lines.append("No follow-up candidate was attempted.")
    lines.append(
        "Next step: supply a different page for this content, paste the content "
        "directly, or hand over a screenshot of it."
    )
    return "\n".join(lines)


if __name__ == "__main__":
    import pathlib

    _args = sys.argv[1:]
    try:
        if not _args:
            raise ValueError(
                "usage: url_fallback.py <url> | "
                "url_fallback.py <url> --filter <urls.json> [--already-fetched N] | "
                "url_fallback.py <url> --attempted <attempted.json>"
            )
        _pasted, _rest = _args[0], _args[1:]

        _filter_path = None
        _attempted_path = None
        _already_fetched = 0
        _i = 0
        while _i < len(_rest):
            _a = _rest[_i]
            if _a == "--filter" and _i + 1 < len(_rest):
                _filter_path, _i = _rest[_i + 1], _i + 2
            elif _a == "--already-fetched" and _i + 1 < len(_rest):
                _already_fetched, _i = int(_rest[_i + 1]), _i + 2
            elif _a == "--attempted" and _i + 1 < len(_rest):
                _attempted_path, _i = _rest[_i + 1], _i + 2
            else:
                raise ValueError(f"unrecognized argument: {_a!r}")

        if _filter_path:
            _urls = json.loads(pathlib.Path(_filter_path).read_text(encoding="utf-8"))
            print(json.dumps({
                "ok": True,
                **filter_candidates(_pasted, _urls, already_fetched=_already_fetched),
            }))
        elif _attempted_path:
            _attempts = json.loads(pathlib.Path(_attempted_path).read_text(encoding="utf-8"))
            print(json.dumps({"ok": True, "message": give_up_message(_pasted, _attempts)}))
        else:
            print(json.dumps({"ok": True, **plan_ladder(_pasted)}))
    except Exception as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)
