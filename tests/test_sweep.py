# tests/test_sweep.py
#
# Phase 9 (P9-SC2) offline proof for the weekly dedupe/mangled maintenance sweep
# (CLAUDE.md §13.4 Workflow D). dedupe_sweep is PURE: records are an injected in-memory
# list, so there is no fixture file, no monkeypatching, and zero network. The load-bearing
# claim is normalize-BEFORE-compare — two phones in different raw formats collapse to one
# E.164 group, which a naive raw-string compare would miss.
from src.sweep import dedupe_sweep


def _rec(id, **props):
    return {"id": id, "properties": props}


# Two email dups, two phone dups (DIFFERENT raw formats), two linkedin dups
# (trailing-slash + host case), one garbage email, one unparseable phone, one clean.
RECORDS = [
    _rec("1", email="shared@example.com"),
    _rec("2", email="shared@example.com"),
    _rec("3", phone="+61412345678"),
    _rec("4", phone="0412 345 678"),
    _rec("5", linkedin_url="https://linkedin.com/in/jane/"),
    _rec("6", linkedin_url="https://LinkedIn.com/in/jane"),
    _rec("7", email="not-an-email"),
    _rec("8", phone="abc123"),
    _rec("9", email="clean.unique@example.com", phone="+61400111222",
         linkedin_url="https://linkedin.com/in/unique"),
]


def test_duplicate_groups_are_exact():
    report = dedupe_sweep(RECORDS)
    groups = {(d["key_type"], d["key_value"]): set(d["ids"]) for d in report.duplicates}
    assert groups == {
        ("email", "shared@example.com"): {"1", "2"},
        ("phone", "+61412345678"): {"3", "4"},
        ("linkedin_url", "https://linkedin.com/in/jane"): {"5", "6"},
    }
    assert report.duplicate_count == 3


def test_phone_dup_proves_normalize_before_compare():
    # THE load-bearing case: raw "+61412345678" (id 3) and raw "0412 345 678" (id 4)
    # normalize to the SAME E.164 and MUST collapse into one group. If the sweep compared
    # raw strings this assertion fails — this is the normalize-before-compare proof.
    report = dedupe_sweep(RECORDS)
    phone_groups = [d for d in report.duplicates if d["key_type"] == "phone"]
    assert len(phone_groups) == 1
    assert phone_groups[0]["key_value"] == "+61412345678"
    assert set(phone_groups[0]["ids"]) == {"3", "4"}


def test_mangled_findings_are_exact():
    report = dedupe_sweep(RECORDS)
    mangled = {(m["id"], m["field"]): m for m in report.mangled}
    assert set(mangled) == {("7", "email"), ("8", "phone")}
    assert mangled[("7", "email")]["raw"] == "not-an-email"
    assert mangled[("7", "email")]["reason"] == "invalid email"
    assert mangled[("8", "phone")]["raw"] == "abc123"
    assert mangled[("8", "phone")]["reason"] == "unparseable phone"
    assert report.mangled_count == 2


def test_to_review_ids_is_sorted_unique_union_and_clean_absent():
    report = dedupe_sweep(RECORDS)
    expected = sorted({"1", "2", "3", "4", "5", "6", "7", "8"})
    assert report.to_review_ids == expected
    assert report.to_review_ids == sorted(report.to_review_ids)  # itself sorted
    assert "9" not in report.to_review_ids                        # clean record excluded


def test_deterministic_across_runs():
    a = dedupe_sweep(RECORDS)
    b = dedupe_sweep(RECORDS)
    assert a.model_dump() == b.model_dump()
