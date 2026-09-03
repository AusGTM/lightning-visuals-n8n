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
    python scripts/role_vocabulary.py              # live inventory + cache write
    python scripts/role_vocabulary.py --dry-run     # print the would-be YAML, write nothing
"""
import argparse
import json
import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # repo root on sys.path so `src.*` imports resolve

CACHE_PATH = ROOT / "operator-claude-plugin" / "config" / "role_vocabulary.yaml"

# Same portal guard as every other schema/migration script in this repo.
EXPECTED_PORTAL_ID = os.getenv("HUBSPOT_EXPECTED_PORTAL_ID", "22617666")

JOBTITLE_PROPERTY = "jobtitle"
PAGE_LIMIT = 100

# D-62-06: offer the top N roles by recurrence, N fixed and scannable.
TOP_N_FAMILIES = 8

# D-62-07: the minimum distinct-title count needed to evidence a vocabulary. Below it,
# the portal cannot support a derived list.
SPARSE_THRESHOLD = 20

VOCABULARY_VERSION = "lv-role-vocabulary-v1"

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


def sweep_all_jobtitles() -> Counter:
    """Read-only paged sweep of every contact's jobtitle. Returns a Counter mapping each
    non-blank, whitespace-trimmed distinct value to its recurrence."""
    counts: Counter = Counter()
    after = None
    while True:
        page = _search_contacts_page(after)
        for result in page.get("results", []):
            raw = (result.get("properties", {}) or {}).get(JOBTITLE_PROPERTY)
            title = (raw or "").strip()
            if title:
                counts[title] += 1
        after = page.get("paging", {}).get("next", {}).get("after")
        if not after:
            break
    return counts


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
    D-62-07)."""
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
    defensive backstop for the system prompt's own "never invent a title" rule."""
    ranked = []
    for family in families:
        members = [m for m in (family.get("members") or []) if m in counts]
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


def build_portal_vocabulary(counts: Counter) -> dict:
    families = cluster_titles(sorted(counts))
    top_families = rank_top_families(families, counts)
    return {
        "version": VOCABULARY_VERSION,
        "built_on": date.today().isoformat(),
        "source": "portal_jobtitle_inventory",
        "evidenced": True,
        "top_n": TOP_N_FAMILIES,
        "distinct_titles_sampled": len(counts),
        "families": top_families,
    }


def _write_cache(vocabulary: dict, path: Path = CACHE_PATH) -> Path:
    path.write_text(yaml.safe_dump(vocabulary, sort_keys=False))
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                         help="Print the would-be YAML to stdout without writing the cache.")
    args = parser.parse_args(argv)

    if not _has_credentials():
        print("skipped (no credentials): HUBSPOT_PRIVATE_APP_TOKEN must be set to run this inventory.")
        return 0

    if not _portal_ok():
        print(f"REFUSED: HUBSPOT_PORTAL_ID does not match the expected portal "
              f"({EXPECTED_PORTAL_ID}). No API call made.")
        return 1

    counts = sweep_all_jobtitles()

    if len(counts) < SPARSE_THRESHOLD:
        vocabulary = build_generic_fallback(distinct_titles_sampled=len(counts))
        print(f"SPARSE PORTAL: {len(counts)} distinct jobtitle values found, below the "
              f"threshold of {SPARSE_THRESHOLD}. Serving the disclosed generic fallback.")
    else:
        vocabulary = build_portal_vocabulary(counts)
        print(f"CLUSTERED: {len(counts)} distinct jobtitle values into "
              f"{len(vocabulary['families'])} top families.")

    if args.dry_run:
        print(yaml.safe_dump(vocabulary, sort_keys=False))
        return 0

    path = _write_cache(vocabulary)
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
