"""tests/test_role_vocabulary_derivation.py

Quick task 260904-39r (closes G-62-5 in .planning/phases/62-.../62-UAT.md).

Offline-only. No HubSpot read, no Anthropic call, no credential -- tests/conftest.py's
autouse `no_ambient_credentials` fixture already strips both guarded env vars for every
test in this module; the `anthropic.Anthropic` class itself is monkeypatched to a fake
that never opens a socket.

Fixture disclosure (tests/fixtures/role_vocabulary_truncated_response.txt): this is a
SHAPE-FAITHFUL RECONSTRUCTION of the response measured live during the Phase 62 UAT
sitting (G-62-5), not the byte-exact live capture -- the probe script that produced the
original (`scripts/uat62_cluster_probe.py`) was untracked and was deleted by plan 62-10,
so the original bytes are unrecoverable. It reproduces every marker `62-UAT.md` § G-62-5
actually measured: opens with a ```json fence, never closes it, contains several
well-formed families of plausible racing/media job titles, and terminates mid-object with
the exact tail `"Senior Stipendiary Steward"\\n      ]\\n    },\\n    {`.
"""
import json
import sys
from pathlib import Path

import anthropic
import pytest
import yaml

import scripts.role_vocabulary as role_vocabulary

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "role_vocabulary_truncated_response.txt"
TRUNCATED_TEXT = FIXTURE_PATH.read_text()


# --------------------------------------------------------------------------------------
# Fake Anthropic client plumbing. cluster_titles() does `from anthropic import Anthropic`
# inside the function body, so patching the attribute on the `anthropic` MODULE is what
# takes effect -- the local import re-reads `anthropic.Anthropic` on every call.
# --------------------------------------------------------------------------------------

class _FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _FakeMessage:
    def __init__(self, text, stop_reason="end_turn"):
        self.content = [_FakeBlock(text)]
        self.stop_reason = stop_reason


class _FakeMessages:
    """Returns queued responses in order, one per `.create()` call. Records every call's
    kwargs so a test can assert what was actually sent (D-1's head-only assertion)."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("FakeMessages.create() called more times than responses queued")
        return self._responses.pop(0)


def _fake_anthropic_class(responses):
    """Factory returning a class usable as `anthropic.Anthropic` -- constructed with no
    args (as cluster_titles does), exposing `.messages` (a _FakeMessages queue)."""
    class _FakeClient:
        def __init__(self, *args, **kwargs):
            self.messages = _FakeMessages(list(responses))
    return _FakeClient


class _RaisingAnthropicClient:
    """Construction itself raises -- used to prove a code path never even tries to build
    a real client (D-62-07's sparse-path guarantee)."""

    def __init__(self, *args, **kwargs):
        raise AssertionError("Anthropic() must not be constructed on this path")


# ============================== Task 1 ==============================

def test_truncated_response_raises_named_error_not_jsondecodeerror(monkeypatch):
    fake_cls = _fake_anthropic_class([_FakeMessage(TRUNCATED_TEXT, stop_reason="max_tokens")])
    monkeypatch.setattr(anthropic, "Anthropic", fake_cls)

    with pytest.raises(role_vocabulary.RoleVocabularyDerivationError) as excinfo:
        role_vocabulary.cluster_titles(["Track Manager", "Broadcast Manager"])

    message = str(excinfo.value)
    assert "max_tokens" in message
    assert "2" in message  # number of titles sent
    assert str(role_vocabulary.MAX_TOKENS) in message


def test_fenced_but_complete_response_parses(monkeypatch):
    complete_json = json.dumps({
        "families": [
            {"label": "Broadcast", "members": ["Broadcast Manager", "Broadcast Technician"]},
        ]
    })
    fenced = f"```json\n{complete_json}\n```"
    fake_cls = _fake_anthropic_class([_FakeMessage(fenced, stop_reason="end_turn")])
    monkeypatch.setattr(anthropic, "Anthropic", fake_cls)

    families = role_vocabulary.cluster_titles(["Broadcast Manager", "Broadcast Technician"])

    assert families == [{"label": "Broadcast", "members": ["Broadcast Manager", "Broadcast Technician"]}]


def test_complete_unparseable_response_triggers_one_repair_call_that_succeeds(monkeypatch):
    garbage = "not json at all, sorry"
    complete_json = json.dumps({"families": [{"label": "Ops", "members": ["Ops Manager"]}]})
    fake_cls = _fake_anthropic_class([
        _FakeMessage(garbage, stop_reason="end_turn"),
        _FakeMessage(complete_json, stop_reason="end_turn"),
    ])
    monkeypatch.setattr(anthropic, "Anthropic", fake_cls)

    families = role_vocabulary.cluster_titles(["Ops Manager"])

    assert families == [{"label": "Ops", "members": ["Ops Manager"]}]


def test_repair_response_itself_truncated_raises_named_error(monkeypatch):
    garbage = "not json at all, sorry"
    fake_cls = _fake_anthropic_class([
        _FakeMessage(garbage, stop_reason="end_turn"),
        _FakeMessage(TRUNCATED_TEXT, stop_reason="max_tokens"),
    ])
    monkeypatch.setattr(anthropic, "Anthropic", fake_cls)

    with pytest.raises(role_vocabulary.RoleVocabularyDerivationError) as excinfo:
        role_vocabulary.cluster_titles(["Ops Manager"])

    assert not isinstance(excinfo.value, json.JSONDecodeError)
    assert "max_tokens" in str(excinfo.value)


def test_two_unparseable_responses_raise_named_error(monkeypatch):
    fake_cls = _fake_anthropic_class([
        _FakeMessage("garbage one", stop_reason="end_turn"),
        _FakeMessage("garbage two", stop_reason="end_turn"),
    ])
    monkeypatch.setattr(anthropic, "Anthropic", fake_cls)

    with pytest.raises(role_vocabulary.RoleVocabularyDerivationError):
        role_vocabulary.cluster_titles(["Ops Manager"])


# ============================== Task 2 ==============================

def test_normalize_title_merges_html_entity_variants():
    a = role_vocabulary._normalize_title("AV &amp; Broadcast Senior Executive")
    b = role_vocabulary._normalize_title("AV & Broadcast Senior Executive")
    assert a == b == "AV & Broadcast Senior Executive"


# ==================== Quick task 260904-447 (double-encoded entities) ====================

def test_normalize_title_fully_decodes_double_encoded_entities():
    assert role_vocabulary._normalize_title("President &amp;amp; Chief Executive Officer") == \
        "President & Chief Executive Officer"


def test_normalize_title_unescape_is_bounded_at_max_passes():
    assert role_vocabulary.MAX_UNESCAPE_PASSES == 5
    seven_times_encoded = "&" + "amp;" * 7
    two_times_encoded = "&" + "amp;" * 2
    assert role_vocabulary._normalize_title(seven_times_encoded) == two_times_encoded


def test_sweep_merges_double_encoded_and_plain_spellings_into_one_key(monkeypatch):
    page = {
        "results": [
            {"properties": {"jobtitle": "President &amp;amp; CEO"}},
            {"properties": {"jobtitle": "President & CEO"}},
        ],
        "paging": {},
    }
    monkeypatch.setattr(role_vocabulary, "_search_contacts_page", lambda after, limit=100: page)

    counts = role_vocabulary.sweep_all_jobtitles()

    assert counts["President & CEO"] == 2
    assert not any("amp" in key for key in counts)


def test_sweep_merges_entity_variants_and_drops_junk_but_keeps_av(monkeypatch):
    page = {
        "results": [
            {"properties": {"jobtitle": "AV &amp; Broadcast Senior Executive"}},
            {"properties": {"jobtitle": "AV & Broadcast Senior Executive"}},
            {"properties": {"jobtitle": "+61407 911 185"}},
            {"properties": {"jobtitle": "AV"}},
        ],
        "paging": {},
    }
    monkeypatch.setattr(role_vocabulary, "_search_contacts_page", lambda after, limit=100: page)

    counts = role_vocabulary.sweep_all_jobtitles()

    assert counts["AV & Broadcast Senior Executive"] == 2
    assert "+61407 911 185" not in counts
    assert counts["AV"] == 1


def test_head_titles_returns_exactly_n_ordered_by_count_then_title():
    counts = role_vocabulary.Counter()
    # 2045-key-scale counter: 5 titles with distinct high counts, then 200 titles all
    # sharing a lower count (so ordering within the tie must fall back to title asc).
    for i in range(5):
        counts[f"top-{i}"] = 1000 - i
    for i in range(2040):
        counts[f"tail-{i:04d}"] = 1

    head = role_vocabulary.head_titles(counts, 200)

    assert len(head) == 200
    assert head[:5] == ["top-0", "top-1", "top-2", "top-3", "top-4"]
    # Remaining 195 slots come from the tied tail, ascending by title.
    expected_tail = sorted(f"tail-{i:04d}" for i in range(2040))[:195]
    assert head[5:] == expected_tail
    # The 201st-ranked title must be absent.
    all_ranked = sorted(counts.keys(), key=lambda t: (-counts[t], t))
    assert all_ranked[200] not in head


def test_build_portal_vocabulary_clusters_only_the_head(monkeypatch):
    counts = role_vocabulary.Counter()
    for i in range(5):
        counts[f"top-{i}"] = 100 - i
    for i in range(300):
        counts[f"tail-{i:04d}"] = 1

    captured = {}

    def fake_cluster_titles(titles):
        captured["titles"] = list(titles)
        return []

    monkeypatch.setattr(role_vocabulary, "cluster_titles", fake_cluster_titles)

    role_vocabulary.build_portal_vocabulary(counts, head_n=10)

    assert len(captured["titles"]) == 10
    assert captured["titles"][:5] == ["top-0", "top-1", "top-2", "top-3", "top-4"]
    for t in captured["titles"]:
        assert t.startswith("top-") or t.startswith("tail-")


def test_rank_top_families_keeps_html_escaped_member_when_counts_holds_unescaped():
    counts = role_vocabulary.Counter({"AV & Broadcast Senior Executive": 3})
    families = [{"label": "AV", "members": ["AV &amp; Broadcast Senior Executive"]}]

    ranked = role_vocabulary.rank_top_families(families, counts)

    assert len(ranked) == 1
    assert ranked[0]["members"] == ["AV & Broadcast Senior Executive"]
    assert ranked[0]["recurrence"] == 3


def test_sparse_path_never_constructs_anthropic_client(monkeypatch):
    monkeypatch.setattr(anthropic, "Anthropic", _RaisingAnthropicClient)
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", role_vocabulary.EXPECTED_PORTAL_ID)

    sparse_counts = role_vocabulary.Counter({f"title-{i}": 1 for i in range(5)})
    monkeypatch.setattr(role_vocabulary, "sweep_all_jobtitles", lambda: sparse_counts)

    rc = role_vocabulary.main(["--dry-run"])

    assert rc == 0  # no AssertionError from _RaisingAnthropicClient escaped


# ============================== Task 3 ==============================

def test_full_stubbed_run_writes_derived_path_and_leaves_shipped_file_untouched(monkeypatch, tmp_path, capsys):
    derived_path = tmp_path / "role_vocabulary.derived.yaml"
    monkeypatch.setattr(role_vocabulary, "DERIVED_PATH", derived_path)

    shipped_before = role_vocabulary.CACHE_PATH.read_bytes()

    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", role_vocabulary.EXPECTED_PORTAL_ID)

    non_sparse_counts = role_vocabulary.Counter({f"title-{i}": 1 for i in range(25)})
    monkeypatch.setattr(role_vocabulary, "sweep_all_jobtitles", lambda: non_sparse_counts)
    monkeypatch.setattr(
        role_vocabulary, "cluster_titles",
        lambda titles: [{"label": "Ops", "members": ["title-0"]}],
    )

    rc = role_vocabulary.main([])

    assert rc == 0
    assert derived_path.exists()
    written = yaml.safe_load(derived_path.read_text())
    assert written["families"][0]["label"] == "Ops"

    shipped_after = role_vocabulary.CACHE_PATH.read_bytes()
    assert shipped_after == shipped_before


def test_both_trees_unescape_to_the_same_bounded_fixed_point():
    # Quick task 260904-447: pins the two deliberately-duplicated bounded unescape loops
    # (scripts/role_vocabulary.py::_normalize_title and
    # operator-claude-plugin/scripts/role_classify.py::_tokenize) equal, so they cannot
    # silently drift apart.
    plugin_scripts_dir = str(role_vocabulary.ROOT / "operator-claude-plugin" / "scripts")
    if plugin_scripts_dir not in sys.path:
        sys.path.insert(0, plugin_scripts_dir)
    import role_classify

    assert role_vocabulary.MAX_UNESCAPE_PASSES == role_classify.MAX_UNESCAPE_PASSES

    double_encoded = "President &amp;amp; Chief Executive Officer"
    normalized = role_vocabulary._normalize_title(double_encoded)
    tokens = role_classify._tokenize(double_encoded)

    assert "amp" not in normalized
    assert "amp" not in tokens


def test_default_write_path_is_not_the_plugin_read_path():
    # Mirrors operator-claude-plugin/tests/conftest.py's own sys.path insert (the plugin
    # scripts dir is also literally named `scripts`, which would otherwise shadow this
    # repo's root-level `scripts` package) -- done locally here rather than importing
    # that conftest, since this test lives in the ROOT suite, not the plugin's.
    plugin_scripts_dir = str(role_vocabulary.ROOT / "operator-claude-plugin" / "scripts")
    if plugin_scripts_dir not in sys.path:
        sys.path.insert(0, plugin_scripts_dir)
    import role_classify

    assert role_vocabulary.DERIVED_PATH != role_classify.DEFAULT_VOCABULARY_PATH
    assert role_vocabulary.DERIVED_PATH == role_vocabulary.CACHE_PATH.parent / "role_vocabulary.derived.yaml"


def test_dry_run_creates_no_file_anywhere(monkeypatch, tmp_path):
    derived_path = tmp_path / "role_vocabulary.derived.yaml"
    monkeypatch.setattr(role_vocabulary, "DERIVED_PATH", derived_path)
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", role_vocabulary.EXPECTED_PORTAL_ID)

    non_sparse_counts = role_vocabulary.Counter({f"title-{i}": 1 for i in range(25)})
    monkeypatch.setattr(role_vocabulary, "sweep_all_jobtitles", lambda: non_sparse_counts)
    monkeypatch.setattr(
        role_vocabulary, "cluster_titles",
        lambda titles: [{"label": "Ops", "members": ["title-0"]}],
    )

    before = set(tmp_path.iterdir())
    rc = role_vocabulary.main(["--dry-run"])
    after = set(tmp_path.iterdir())

    assert rc == 0
    assert before == after
    assert not derived_path.exists()


def test_dry_run_prints_the_drop_list_too(monkeypatch, tmp_path, capsys):
    """Quick task 260904-39r UAT, 2026-09-04. `--dry-run` is the mode an operator EVALUATES
    an adoption in, and it used to return before `_print_drop_list` — so it showed the
    derived families with no warning that adopting them drops curated ones. The disclosure
    matters most before anything is written, not only after."""
    shipped_path = tmp_path / "role_vocabulary.yaml"
    shipped_path.write_text(yaml.safe_dump({
        "families": [
            {"label": "Chair", "members": ["Chairman"]},
            {"label": "Ops", "members": ["title-0"]},
        ]
    }))
    derived_path = tmp_path / "role_vocabulary.derived.yaml"
    monkeypatch.setattr(role_vocabulary, "CACHE_PATH", shipped_path)
    monkeypatch.setattr(role_vocabulary, "DERIVED_PATH", derived_path)
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "fake-token")
    monkeypatch.setenv("HUBSPOT_PORTAL_ID", role_vocabulary.EXPECTED_PORTAL_ID)

    non_sparse_counts = role_vocabulary.Counter({f"title-{i}": 1 for i in range(25)})
    monkeypatch.setattr(role_vocabulary, "sweep_all_jobtitles", lambda: non_sparse_counts)
    monkeypatch.setattr(
        role_vocabulary, "cluster_titles",
        lambda titles: [{"label": "Ops", "members": ["title-0"]}],
    )

    rc = role_vocabulary.main(["--dry-run"])
    out = capsys.readouterr().out

    assert rc == 0
    drop_line = next(line for line in out.splitlines() if "would drop" in line)
    assert "Chair" in drop_line
    assert f"cp {derived_path} {shipped_path}" in out
    # still writes nothing — the disclosure is printed against the path a real run WOULD use
    assert not derived_path.exists()


def test_drop_list_names_omitted_shipped_labels_and_prints_cp_command(monkeypatch, tmp_path, capsys):
    shipped_path = tmp_path / "role_vocabulary.yaml"
    shipped_path.write_text(yaml.safe_dump({
        "families": [
            {"label": "Chair", "members": ["Chairman"]},
            {"label": "Treasurer", "members": ["Treasurer"]},
        ]
    }))
    monkeypatch.setattr(role_vocabulary, "CACHE_PATH", shipped_path)
    derived_path = tmp_path / "role_vocabulary.derived.yaml"

    derived_vocabulary = {"families": [{"label": "Treasurer", "members": ["Treasurer"]}]}
    role_vocabulary._print_drop_list(derived_vocabulary, derived_path)

    out = capsys.readouterr().out
    drop_line = next(line for line in out.splitlines() if "would drop" in line)
    assert "Chair" in drop_line
    assert "Treasurer" not in drop_line
    assert f"cp {derived_path} {shipped_path}" in out


def test_gitignore_contains_derived_path():
    gitignore = (role_vocabulary.ROOT / ".gitignore").read_text()
    assert "operator-claude-plugin/config/role_vocabulary.derived.yaml" in gitignore
