#!/usr/bin/env python3
"""scripts/role_vocabulary.py

Phase 62 Plan 02 Task 1 (D-62-05/D-62-06/D-62-07) — read-only, paged live inventory of
every distinct `jobtitle` value on HubSpot contact records, clustered ONCE (Haiku) into
named role families and cached to a committed YAML the plugin reads
(`role_classify.load_families()`). NOT re-clustered per round.

Lives at the REPO ROOT beside its exact analog, scripts/inventory_org_type_values.py —
NOT under operator-claude-plugin/scripts/. No plugin script has ever held a HubSpot
credential (`grep -rl "HUBSPOT_PRIVATE_APP_TOKEN|api.hubapi.com"
operator-claude-plugin/scripts/` returns nothing) and every HubSpot read the plugin makes
goes through an n8n webhook. This script WRITES the cache; the plugin only ever reads it.

Read-only throughout: only a paged POST .../search sweep plus one Anthropic clustering
call, no write key, no PATCH, no property mutation. Same idiom as
inventory_org_type_values.py: env-gated, `_has_credentials()` skip-to-exit-0, the same
portal guard, refuse with no API call on a portal mismatch.

D-62-07: below `SPARSE_THRESHOLD` distinct titles, the portal cannot evidence a
vocabulary — serve the disclosed generic fallback instead, and never make the Haiku call.

Usage:
    python scripts/role_vocabulary.py              # live inventory + derived-file write
    python scripts/role_vocabulary.py --dry-run     # print the would-be YAML, write nothing
    python scripts/role_vocabulary.py --head 400    # cluster a larger recurrence head

Quick task 260904-39r (closes G-62-5): this script now WRITES its output to
`role_vocabulary.derived.yaml`, a sibling of the shipped, live-proven 17-family
`role_vocabulary.yaml` -- it never overwrites the shipped file. `role_classify.py` only
ever reads the shipped file, so a derived run is inert to the plugin until an operator
deliberately reviews the drop-list this script prints and copies the derived file over.
"""
import argparse
import html
import json
import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve

# CACHE_PATH names the shipped, plugin-read file -- read-only from this script's own
# perspective (used only to print the drop-list comparison in D-4). This script's write
# target is DERIVED_PATH, below.
CACHE_PATH = ROOT / "operator-claude-plugin" / "config" / "role_vocabulary.yaml"

# Quick task 260904-39r, D-4: a sibling of CACHE_PATH, never merged into it and never
# auto-adopted. Kept out of git (see .gitignore) -- it is a run artifact, not a deliverable.
DERIVED_PATH = CACHE_PATH.parent / "role_vocabulary.derived.yaml"

# Same portal guard as every other schema/migration script in this repo.
EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")

JOBTITLE_PROPERTY = "jobtitle"
PAGE_LIMIT = 100

# D-62-06: offer the top N roles by recurrence, N fixed and scannable.
TOP_N_FAMILIES = 8

# Quick task 260904-39r, D-1: only the recurrence HEAD is ever sent to the clustering
# call -- ranking runs first, over ALL distinct titles (cheap, no model call); clustering
# runs second, over the head only. Fixed N, not a "count >= k" cutoff -- see D-1 for why a
# fixed size is the actual fix and a recurrence cutoff would not be.
HEAD_N = 200

# D-62-07: the minimum distinct-title count needed to evidence a vocabulary. Below it,
# the portal cannot support a derived list.
SPARSE_THRESHOLD = 20

# Quick task 260904-447: the portal stores DOUBLE-encoded HTML entities (measured
# 2026-09-04, e.g. 'Finance &amp;amp; Admin Officer'), so a single html.unescape() pass
# leaves one layer behind. This bounds the fixed-point unescape loop in _normalize_title
# so a pathologically nested input still terminates in fixed time.
MAX_UNESCAPE_PASSES = 5

VOCABULARY_VERSION = "lv-role-vocabulary-v2"

# D-62-07's disclosed fallback: a generic B2B buying-committee list, served ONLY when the
# portal is too sparse to evidence one, and marked un-evidenced at every level so it can
# never be mistaken for a portal-derived list.
GENERIC_FALLBACK_LABELS = [
    "CEO", "CMO", "Head of Broadcast", "Head of Marketing", "Marketing Manager",
    "Operations Manager", "General Manager", "Communications Manager",
]

CLUSTER_SYSTEM_PROMPT = """
You are clustering real job titles from a CRM into named role families.
Return only valid JSON: {"families": [{"label": "...", "members": ["...", ...]}, ...]}.
Every member of every family MUST be a title that was in the input -- never invent a
title, and never invent a family with no members from the input. Group titles that
describe the same functional role even when worded differently (e.g. "Head of
Broadcast" and "Broadcast Manager" belong together). Prefer fewer, clearly-named
families over many overlapping ones.
"""


def _has_credentials() -> bool:
    return bool(os.getenv("HUBSPOT_PRIVATE_APP_TOKEN"))


def _portal_ok() -> bool:
    return os.getenv("HUBSPOT_PORTAL_ID") == EXPECTED_PORTAL_ID


def _search_contacts_page(after, limit=PAGE_LIMIT) -> dict:
    import requests
    from src.hubspot_client import hs_headers, BASE_URL
    body = {"filterGroups": [], "properties": [JOBTITLE_PROPERTY], "limit": limit}
    if after:
        body["after"] = after
    r = requests.post(f"{BASE_URL}/crm/v3/objects/contacts/search", headers=hs_headers(),
                       json=body, timeout=30)
    r.raise_for_status()
    return r.json()


def _normalize_title(raw) -> str:
    """Quick task 260904-39r, D-3: html.unescape then collapse internal whitespace then
    strip. Applied ONCE at count time (inside sweep_all_jobtitles) so `counts` KEYS are
    already the exact strings sent to the model -- and applied AGAIN to each member the
    model returns before the `in counts` check in rank_top_families. That is the whole
    fix: the same normalisation on both sides of the exact-match seam, so
    'AV &amp; Broadcast Senior Executive' and 'AV & Broadcast Senior Executive' become one
    key instead of two competing (and silently-dropped) head slots.

    Deliberately nothing heavier: no `&`-to-`and`, no punctuation stripping, no
    case-folding. role_classify.py's _tokenize does that at MATCH time; doing it here
    would mangle the verbatim titles the model is required to echo back.

    Quick task 260904-447: the portal stores DOUBLE-encoded entities (measured
    2026-09-04, e.g. 'Finance &amp;amp; Admin Officer'), so a single unescape pass left
    one layer of encoding behind. This loop now unescapes to a bounded fixed point
    (MAX_UNESCAPE_PASSES) instead of once. The sibling copy of this loop is
    operator-claude-plugin/scripts/role_classify.py::_tokenize -- deliberate duplication
    across two trees (the plugin ships standalone, so no cross-tree import), pinned equal
    by test_both_trees_unescape_to_the_same_bounded_fixed_point. Accepted cost: a title
    whose literal intended text is '&amp;' would be decoded to '&' -- vanishingly
    unlikely in a job title."""
    text = str(raw or "")
    for _ in range(MAX_UNESCAPE_PASSES):
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded
    return " ".join(text.split())


def _is_junk_title(title: str) -> bool:
    """D-3's deliberately conservative junk rule: fewer than 2 alphabetic characters.
    Drops phone numbers and punctuation-only values ('+61407 911 185'). Keeps a bare 'AV'
    on purpose -- two letters, may be a real department label, and an unrecurring value
    never reaches the head anyway (see D-3's stated divergence from the UAT)."""
    return sum(c.isalpha() for c in title) < 2


def sweep_all_jobtitles() -> Counter:
    """Read-only paged sweep of every contact's jobtitle. Returns a Counter mapping each
    normalised (D-3), non-junk distinct value to its recurrence."""
    counts: Counter = Counter()
    after = None
    while True:
        page = _search_contacts_page(after)
        for result in page.get("results", []):
            raw = (result.get("properties", {}) or {}).get(JOBTITLE_PROPERTY)
            title = _normalize_title(raw)
            if title and not _is_junk_title(title):
                counts[title] += 1
        after = page.get("paging", {}).get("next", {}).get("after")
        if not after:
            break
    return counts


def head_titles(counts: Counter, n: int = HEAD_N) -> list:
    """Quick task 260904-39r, D-1: the n most-recurrent titles, ordered `(-count, title)`
    so the selection (and any tie-break) is deterministic and never depends on dict
    order. Titles outside the head never reach the clustering call and so can never join
    or become a family."""
    return sorted(counts.keys(), key=lambda t: (-counts[t], t))[:n]


# Quick task 260904-39r, D-2: sized from the measured live failure (2,045 titles /
# 16,079 input tokens truncated at the old 2000-token ceiling). Task 1 lands the naming
# + repair fix at this ceiling; Task 2 bounds the input that makes 8000 sufficient.
MAX_TOKENS = 8000


class RoleVocabularyDerivationError(Exception):
    """Quick task 260904-39r, D-2. Raised when the Haiku clustering call cannot be turned
    into a families list: either the response was truncated (`stop_reason ==
    "max_tokens"`, a capacity failure -- retrying identically would truncate identically
    and spend a call to learn nothing) or a repair retry also failed to parse. Named so
    both cases fail loudly and by name instead of surfacing as an opaque
    json.JSONDecodeError several frames from its actual cause."""


def _cluster_call(client, model, messages):
    return client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        temperature=0,
        system=CLUSTER_SYSTEM_PROMPT,
        messages=messages,
    )


def _require_not_truncated(msg, head_size: int) -> None:
    """D-2: checked BEFORE the response text is ever touched -- a max_tokens response is
    a capacity failure, not a malformed one, and parsing it would only ever surface the
    truncation as a confusing JSONDecodeError instead of naming the real cause."""
    if getattr(msg, "stop_reason", None) == "max_tokens":
        raise RoleVocabularyDerivationError(
            f"Haiku clustering response truncated (stop_reason=max_tokens) after sending "
            f"{head_size} titles against a max_tokens ceiling of {MAX_TOKENS}. Retrying "
            f"identically would truncate identically and spend a call to learn nothing -- "
            f"lower --head or raise MAX_TOKENS."
        )


def _text_of(msg) -> str:
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")


def cluster_titles(distinct_titles: list) -> list:
    """ONE Anthropic Haiku call, plus at most one repair retry (D-2, CLAUDE.md §26.3:
    "Haiku invalid JSON -> Retry once with repair prompt"). Returns a list of {"label",
    "members"} dicts. Only called when the portal is NOT sparse (main() gates this per
    D-62-07), and only ever on the recurrence HEAD (D-1) -- the caller ranks first."""
    from anthropic import Anthropic
    from src.web_research import _extract_json  # reuse -- do not write a second parser

    client = Anthropic()
    model = os.getenv("ANTHROPIC_HAIKU_MODEL", "claude-haiku-4-5")

    messages = [{"role": "user", "content": json.dumps({"titles": distinct_titles})}]
    msg = _cluster_call(client, model, messages)
    _require_not_truncated(msg, len(distinct_titles))
    text = _text_of(msg)

    try:
        data = _extract_json(text)
    except json.JSONDecodeError:
        repair_messages = messages + [
            {"role": "assistant", "content": text},
            {"role": "user", "content": (
                "That was not valid JSON. Return ONLY the JSON object -- no prose, no "
                "markdown fences."
            )},
        ]
        repair_msg = _cluster_call(client, model, repair_messages)
        _require_not_truncated(repair_msg, len(distinct_titles))
        repair_text = _text_of(repair_msg)
        try:
            data = _extract_json(repair_text)
        except json.JSONDecodeError as exc:
            raise RoleVocabularyDerivationError(
                "Haiku clustering response could not be parsed as JSON, even after one "
                "repair retry."
            ) from exc

    return data.get("families") or []


def rank_top_families(families: list, counts: Counter, top_n: int = TOP_N_FAMILIES) -> list:
    """Rank clustered families by summed recurrence (D-62-06) and keep the top N. Drops
    any member the model returned that was not actually in the sampled titles -- a
    defensive backstop for the system prompt's own "never invent a title" rule.

    D-3's exact-match seam: each returned member is normalised with the SAME
    `_normalize_title` used to build `counts`, before the `in counts` check -- otherwise
    an HTML-escaped or re-whitespaced echo of a real title is silently dropped."""
    ranked = []
    for family in families:
        members = []
        for raw_member in family.get("members") or []:
            normalized = _normalize_title(raw_member)
            if normalized in counts:
                members.append(normalized)
        if not members:
            continue
        recurrence = sum(counts[m] for m in members)
        ranked.append({
            "label": family.get("label"),
            "recurrence": recurrence,
            "evidenced": True,
            "members": members,
        })
    ranked.sort(key=lambda f: f["recurrence"], reverse=True)
    return ranked[:top_n]


def build_generic_fallback(distinct_titles_sampled: int = 0) -> dict:
    """D-62-07's disclosed un-evidenced fallback. No network call, no credentials
    needed -- this both seeds the committed cache before any operator has run the live
    inventory, and is what the live script itself falls back to below
    SPARSE_THRESHOLD. Document-level AND every family carry evidenced=False, recurrence
    0, so no reader can mistake an invented family for a counted one."""
    return {
        "version": VOCABULARY_VERSION,
        "built_on": date.today().isoformat(),
        "source": "generic_fallback",
        "evidenced": False,
        "top_n": TOP_N_FAMILIES,
        "distinct_titles_sampled": distinct_titles_sampled,
        "families": [
            {"label": label, "recurrence": 0, "evidenced": False, "members": [label]}
            for label in GENERIC_FALLBACK_LABELS
        ],
    }


def build_portal_vocabulary(counts: Counter, head_n: int = HEAD_N) -> dict:
    head = head_titles(counts, head_n)
    families = cluster_titles(head)
    top_families = rank_top_families(families, counts)

    distinct_total = len(counts)
    contacts_total = sum(counts.values())
    contacts_covered = sum(counts[t] for t in head)
    # D-1's honesty requirement: a MEASURED coverage line, not an assumption that head_n
    # was enough.
    print(f"HEAD COVERAGE: clustered {len(head)}/{distinct_total} distinct titles; "
          f"covers {contacts_covered}/{contacts_total} titled contacts.")

    return {
        "version": VOCABULARY_VERSION,
        "built_on": date.today().isoformat(),
        "source": "portal_jobtitle_inventory",
        "evidenced": True,
        "top_n": TOP_N_FAMILIES,
        "distinct_titles_sampled": distinct_total,
        "head_titles_clustered": len(head),
        "families": top_families,
    }


def _write_cache(vocabulary: dict, path: Path = None) -> Path:
    # `path` looked up against DERIVED_PATH at call time (not bound into the default
    # value) so tests can monkeypatch the module-level constant.
    target = path if path is not None else DERIVED_PATH
    target.write_text(yaml.safe_dump(vocabulary, sort_keys=False))
    return target


def _print_drop_list(vocabulary: dict, derived_path: Path, shipped_path: Path = None) -> None:
    """D-4's discharge of the highest-risk constraint: never let a derived run silently
    look like a safe upgrade over the shipped, live-proven vocabulary. Read-only against
    the shipped file -- never writes it. Tolerates the shipped file being absent (a fresh
    checkout with no plugin config yet) by simply staying quiet.

    Quick task 260904-447: adopting the derived file over the curated one was considered
    live on 2026-09-04 and REJECTED -- the derived output is portal-wide-recurrence-only
    and drops every racing-governance family the curated file carries. Before acting on
    the `cp` command this function prints, read
    .planning/decisions/2026-09-04-derived-role-vocabulary-rejected.md."""
    shipped_path = shipped_path if shipped_path is not None else CACHE_PATH
    if not shipped_path.exists():
        return
    try:
        shipped = yaml.safe_load(shipped_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return

    shipped_labels = {f.get("label") for f in (shipped.get("families") or []) if f.get("label")}
    derived_labels = {f.get("label") for f in (vocabulary.get("families") or []) if f.get("label")}
    dropped = sorted(shipped_labels - derived_labels)

    if dropped:
        print(f"adopting this file would drop {len(dropped)} families the shipped "
              f"vocabulary carries: {', '.join(dropped)}")
    print(f"To adopt: cp {derived_path} {shipped_path}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                         help="Print the would-be YAML to stdout without writing anything.")
    parser.add_argument("--head", type=int, default=HEAD_N,
                         help=f"Recurrence head size to cluster (default {HEAD_N}, D-1).")
    args = parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this inventory.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    counts = sweep_all_jobtitles()

    # Sparse check runs on the already-cleaned (normalised, junk-dropped) counts, since
    # sweep_all_jobtitles now does that cleaning itself -- junk is not evidence of a
    # vocabulary (D-3's ordering decision).
    if len(counts) < SPARSE_THRESHOLD:
        vocabulary = build_generic_fallback(distinct_titles_sampled=len(counts))
        print(f"SPARSE PORTAL: {len(counts)} distinct jobtitle values found, below the "
              f"threshold of {SPARSE_THRESHOLD}. Serving the disclosed generic fallback.")
    else:
        vocabulary = build_portal_vocabulary(counts, head_n=args.head)
        print(f"CLUSTERED: {len(counts)} distinct jobtitle values into "
              f"{len(vocabulary['families'])} top families.")

    if args.dry_run:
        print(yaml.safe_dump(vocabulary, sort_keys=False))
        return 0

    path = _write_cache(vocabulary)
    print(f"wrote {path}")
    _print_drop_list(vocabulary, path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
