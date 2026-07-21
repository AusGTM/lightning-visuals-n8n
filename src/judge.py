# src/judge.py
#
# Python side of the Phase 14 judge wiring. Reads config/escalation_policy.yaml at
# runtime, exactly as src/taxonomy.py reads config/taxonomy.yaml (module-level cache,
# repo-root-relative path). scripts/gen_escalation_js.py imports these constants (not a
# re-implementation) so the generated JS literal and this module agree by construction.
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


if __name__ == "__main__":
    # ponytail: smallest runnable self-check for the YAML-lookup logic.
    assert ESCALATION_CONFIDENCE_BAND == [75, 85]
    assert JUDGE_MIN_CONFIDENCE == 80
    assert "youtube.com" in KNOWN_VIDEO_HOSTS
    assert KNOWN_VIDEO_HOSTS == sorted(KNOWN_VIDEO_HOSTS)
    print("src/judge.py self-check OK")
