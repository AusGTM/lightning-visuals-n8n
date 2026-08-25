"""The two findings from the Phase 53 operator walk, 2026-08-25.

Both came from a non-technical operator saying an ordinary sentence, and both are the same
shape: the backend could do the thing, and the client stood in the way.

**Finding 1 — a profile URL is not a company domain.** The operator's realistic input is a
LinkedIn page, not a domain. Naive host extraction turned
`linkedin.com/company/futsal-australia` into the domain `linkedin.com`. That searches HubSpot
for domain=linkedin.com, finds nothing, and CREATES a company whose domain is linkedin.com —
after which every later LinkedIn-sourced company MATCHES that one poisoned record. One bad
row swallowing every future company, with no error at any point.

**Finding 2 — "John Tsatsimas at Football NSW" had nowhere to go.** The backend has resolved
contacts by name since Phase 36 (`IF Name Searchable` -> `HubSpot Name Search`), but no client
form emitted it, so the skill asked the operator for a HubSpot record id — which nobody
carries in their head. The `rows` form looks similar and is NOT the same thing: it describes
people who are not in HubSpot and is pinned to `mode: propose` for that reason.
"""
import sys
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import chunking  # noqa: E402
import enrichment  # noqa: E402
import preview_enrichment  # noqa: E402


# ---------------------------------------------------------------- finding 1: profile URLs

@pytest.mark.parametrize("url", [
    "https://www.linkedin.com/company/futsal-australia/",
    "https://linkedin.com/in/john-tsatsimas-b193a3193/",
    "https://www.facebook.com/racingnsw",
    "https://x.com/racingnsw",
    "https://www.crunchbase.com/organization/whatever",
])
def test_a_profile_url_never_becomes_a_company_domain(url):
    assert enrichment._clean_domain(url) is None, (
        f"{url} normalised to a domain; searching HubSpot for that host matches no company "
        f"and creates one whose domain is the social network"
    )


@pytest.mark.parametrize("url,expected", [
    ("https://www.futsalaustralia.org.au/about", "futsalaustralia.org.au"),
    ("HTTP://PerthRacing.com.au", "perthracing.com.au"),
    ("grv.org.au/contact-us?utm_source=x", "grv.org.au"),
])
def test_a_real_website_still_normalises(url, expected):
    assert enrichment._clean_domain(url) == expected


def test_a_linkedin_page_plus_a_name_is_ACCEPTED_by_name_not_refused():
    """Operator ruling, 2026-08-25 walk: a blanket refusal hands the research back to the
    operator, who does not want to do it. The guard is "never silently invent a domain",
    not "go and find one yourself" — so the unusable host is dropped and the company is
    looked up by its name, which the backend's exact-name search can resolve."""
    envelope = enrichment.build_envelope(
        {"companies": [{"name": "Futsal Australia",
                        "domain": "https://www.linkedin.com/company/futsal-australia/"}]},
        [],
    )
    assert envelope["events"] == [{"objectType": "companies", "name": "Futsal Australia"}], (
        "the profile host must be dropped, not passed through as a domain, and the name "
        "must survive as the thing to look up"
    )


def test_a_company_with_only_a_name_is_accepted():
    envelope = enrichment.build_envelope(
        {"companies": [{"name": "Harness Racing New South Wales"}]}, [])
    assert envelope["events"][0] == {
        "objectType": "companies", "name": "Harness Racing New South Wales"}


def test_only_an_unusable_url_and_no_name_is_refused_because_nothing_can_be_looked_up():
    with pytest.raises(enrichment.RecordSpecError) as excinfo:
        enrichment.build_envelope(
            {"companies": [{"domain": "https://linkedin.com/company/x"}]}, [])
    message = str(excinfo.value)
    assert "profile page" in message
    assert "name" in message, "the refusal must say what would make it work"


def test_the_two_engines_agree_on_what_is_not_a_company_domain():
    """The client refuses here; the ingest lane's resolver refuses there. A host one accepts
    and the other rejects is a silent divergence, so the tables are pinned equal."""
    js = (PLUGIN_ROOT.parent / "n8n" / "code" / "companyLink.js").read_text(encoding="utf-8")
    block = js.split("const NOT_A_COMPANY_DOMAIN = new Set([", 1)[1].split("]);", 1)[0]
    js_hosts = {piece.strip().strip('"').strip("'")
                for piece in block.replace("\n", " ").split(",")
                if piece.strip() and not piece.strip().startswith("//")}
    js_hosts.discard("")
    assert js_hosts == set(enrichment.NOT_A_COMPANY_DOMAIN)


# ---------------------------------------------------------------- finding 2: the people form

def test_a_person_named_the_way_an_operator_names_them_becomes_a_contacts_event():
    envelope = enrichment.build_envelope(
        {"people": [{"firstname": "John", "lastname": "Tsatsimas", "company": "Football NSW"}]},
        ["lusha"],
    )
    assert envelope["events"] == [{
        "objectType": "contacts", "firstname": "John", "lastname": "Tsatsimas",
        "company": "Football NSW",
    }]


def test_the_people_form_carries_no_propose_mode():
    """The `rows` form is pinned to propose because its people are NOT in HubSpot. This form
    describes someone the operator believes IS there, so it may write — a propose mode would
    report success having written nothing."""
    envelope = enrichment.build_envelope(
        {"people": [{"email": "jo@club.example"}]}, [])
    assert "mode" not in envelope


@pytest.mark.parametrize("person", [
    {"email": "jo@club.example"},
    {"linkedin_url": "https://www.linkedin.com/in/jo/"},
    {"lastname": "Tsatsimas", "company": "Football NSW"},
])
def test_any_one_of_the_three_identities_is_enough(person):
    envelope = enrichment.build_envelope({"people": [person]}, [])
    assert len(envelope["events"]) == 1


@pytest.mark.parametrize("person,named", [
    ({"firstname": "John"}, "John"),
    ({"lastname": "Tsatsimas"}, "Tsatsimas"),
    ({}, "that person"),
])
def test_too_little_to_find_anyone_is_refused_by_name_before_any_provider_is_called(person, named):
    """The backend's own gate would skip this row rather than burn three provider calls on it.
    Refusing here, where the operator can still fix it, is the difference between a wasted
    dispatch and a fixable sentence."""
    with pytest.raises(enrichment.RecordSpecError) as excinfo:
        enrichment.build_envelope({"people": [person]}, [])
    message = str(excinfo.value)
    assert named in message
    for remedy in ("company", "email", "LinkedIn"):
        assert remedy in message, "the refusal must say which of the three would fix it"


def test_the_plan_chunks_and_counts_a_people_batch():
    people = [{"lastname": f"P{i}", "company": "C"} for i in range(5)]
    plan = chunking.plan_chunks({"people": people}, 2)
    assert plan.record_count == 5
    assert plan.row_counts == (2, 2, 1)


def test_the_preview_says_how_a_person_is_matched_and_what_is_held():
    spec = {"people": [{"firstname": "John", "lastname": "Tsatsimas", "company": "Football NSW"}]}
    block = preview_enrichment.records_block(spec, chunking.plan_chunks(spec, 20))
    assert "John Tsatsimas" in block
    # The operator must be able to read that a same-surname match is not written over.
    assert "held" in block


def test_the_SKILL_documents_the_people_form_not_just_the_code():
    """Caught live 2026-08-25, the hard way. The `people` form shipped in enrichment.py with
    20 passing tests while SKILL.md never mentioned it — an earlier patch raised partway and
    aborted before writing the file. Every test passed, and the operator's Desktop still said
    "there's no search-a-contact-by-name path in this lane", because the SKILL is what the
    model reads. A module test proves the machinery; only this proves the operator can reach
    it."""
    skill = (PLUGIN_ROOT / "skills" / "enrich-records" / "SKILL.md").read_text(encoding="utf-8")
    assert '"people"' in skill, "the people form must be documented where the model reads it"
    assert "surname + company" in skill, "the three identities must be stated"
    assert "held for the operator to confirm" in skill, (
        "the skill must say a same-surname match is held rather than written over"
    )
