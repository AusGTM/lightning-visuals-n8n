# src/judge.py
#
# Python side of the Phase 14 judge wiring. Reads config/escalation_policy.yaml at
# runtime, exactly as src/taxonomy.py reads config/taxonomy.yaml (module-level cache,
# repo-root-relative path). scripts/gen_escalation_js.py imports these constants (not a
# re-implementation) so the generated JS literal and this module agree by construction.
#
# D4: only is_citation_sufficient gets the Python twin (NM-6 parity discipline). The
# judge's HTTP plumbing (payload build, verdict parse, verdict application) has no
# Python counterpart — a "parity test" against a second hand-written copy of glue code
# proves nothing.
from urllib.parse import urlsplit

import yaml


def load_yaml(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


_POLICY = load_yaml("config/escalation_policy.yaml")


def _lookup(use_when: list, key: str):
    # sonnet_5.use_when / human_review.use_when are lists of single-key dicts
    # (YAML shape chosen for CLAUDE.md §15.1 fidelity) — find the one entry with `key`.
    for entry in use_when:
        if key in entry:
            return entry[key]
    raise KeyError(f"{key} not found in use_when block")


# JG-1: escalation confidence band. Spec §8 JG-1 states "confidence in 75-85" normatively.
ESCALATION_CONFIDENCE_BAND = list(_lookup(_POLICY["sonnet_5"]["use_when"], "confidence_between"))

# JG-3: a judge verdict below this confidence never promotes.
JUDGE_MIN_CONFIDENCE = _lookup(_POLICY["human_review"]["use_when"], "sonnet_confidence_below")

# JG-2: required verdict keys, verbatim order from the YAML.
JUDGE_OUTPUT_REQUIRED = list(_POLICY["sonnet_5"]["output_required"])

# JG-4: hosts that substantiate content output even when not the company's own domain.
KNOWN_VIDEO_HOSTS = sorted(_POLICY["evidence_sufficiency"]["known_video_hosts"])


def is_citation_sufficient(url, company_domain) -> bool:
    """JG-4/TS-1 Python twin of n8n/code/judge.js's isCitationSufficient — same contract,
    same www.-stripping, same root-path rule. Any parse exception returns False (never
    raises). See judge.js for the full rule docstring and the 20-row validation table."""
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
    except (ValueError, AttributeError):
        return False

    def strip_www(h):
        return h[4:] if h.startswith("www.") else h

    host = strip_www(host)
    domain = strip_www(str(company_domain or "").lower())
    host_matches = host == domain or host in KNOWN_VIDEO_HOSTS
    non_root_path = parsed.path not in ("", "/")
    return bool(host_matches and non_root_path)


if __name__ == "__main__":
    # ponytail: smallest runnable self-check for the YAML-lookup logic.
    assert ESCALATION_CONFIDENCE_BAND == [75, 85]
    assert JUDGE_MIN_CONFIDENCE == 80
    assert "youtube.com" in KNOWN_VIDEO_HOSTS
    assert KNOWN_VIDEO_HOSTS == sorted(KNOWN_VIDEO_HOSTS)
    assert is_citation_sufficient(
        "https://www.youtube.com/user/AtcracesTV?cbrd=1", "australianturfclub.com.au"
    ) is True
    assert is_citation_sufficient("https://redcliffehrc.com.au/", "redcliffehrc.com.au") is False
    assert is_citation_sufficient("not a url", "example.com") is False
    print("src/judge.py self-check OK")
