"""operator-claude-plugin/scripts/enrichment.py

The enrichment lane's client half: resolve a provider selection, build the envelope the
deployed `Parse HubSpot Event` node accepts, and POST it — disarmed by default.

Three facts this module exists to honour, each of which fails SILENTLY if forgotten:

1. `Parse HubSpot Event` has NO server-side default for `providers`. An absent or
   unrecognized value resolves to ZERO providers enabled and still returns a clean 200
   (25-CONTEXT D-06a). So `resolve_providers()` is total — every input path yields a
   concrete list — and every envelope carries the key explicitly, including the empty
   selection.
2. HubSpot exposes no API for saved views (25-BLOCKERS.md, amendment #7). A view name is
   refused with `VIEW_REFUSAL`, never resolved against the list endpoint: a view name
   colliding with a real list name would enrich the wrong record set with no error.
3. `armed` has NO default, mirroring dispatch.py exactly. A caller that forgets it gets a
   TypeError, never a silent send (Phase 23 D-11). Nothing about the grant is persisted;
   it exists only as this call's argument.

Only `objectId` and `objectType` are sent per event. The deployed parser spreads any
extra event keys onto the row for a direct-field test payload, which does nothing for a
record that already exists in HubSpot and only widens what crosses the boundary.
"""
import json
import re

import requests

import config_gate
from dispatch import DispatchError, NotArmedError  # one arming error for the whole plugin

ENRICHMENT_PATH = "webhook/hubspot/enrichment/event"
DEFAULT_TIMEOUT = 120  # above the ~100s Cloudflare response ceiling, so a chunk that
# breaches the ceiling reads as the backend's timeout rather than as ours.

# The three providers the deployed `resolveEnabledProviders` recognizes. Anything else it
# drops silently, which is why an unknown name raises here instead.
KNOWN_PROVIDERS = ("zoominfo", "apollo", "lusha")

# "The full waterfall" = config/provider_priority.yaml's default order. `claude_web` is a
# research step inside the workflow, not a credit provider the burn gate knows, so it is
# deliberately absent.
FULL_WATERFALL = ["zoominfo", "apollo", "lusha"]

# The shipped default (D-03). Also the fallback when the operator's config omits the key,
# so behaviour does not change depending on whether the key was copied across.
DEFAULT_PROVIDER_SELECTION_KEY = "enrichment_providers"

# 25-BLOCKERS.md records this sentence verbatim. 25-03 refuses with the same words — two
# phrasings for one refusal is its own defect, so this string is copied, not paraphrased.
VIEW_REFUSAL = (
    "I can't resolve a HubSpot *view* — HubSpot doesn't expose views through its API. "
    "Save that view as a **list** in HubSpot and give me the list name, or paste the "
    "record IDs directly."
)

_OBJECT_TYPES = {
    "contact": "contacts", "contacts": "contacts", "0-1": "contacts",
    "company": "companies", "companies": "companies", "0-2": "companies",
}

# The frozen lookup allowlist for a rows envelope's per-event projection. These are the
# ONLY row fields that cross the boundary on a rows/match envelope, because they are the
# only ones the backend's `Build Identity` reads into `identity_keys` and the only ones
# the match search filters on (37-CONTEXT §7). Widening this tuple widens what leaves the
# operator's machine — a row's `phone`, `jobtitle` and `linkedin_url` never cross it.
MATCH_LOOKUP_KEYS = ("email", "firstname", "lastname", "company")


def _lookup_value(row, key):
    """A row's value for `key`, normalized to `None` when absent, `None`, or a string
    that strips to empty — never the string `"None"`."""
    value = row.get(key)
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return value


class ProviderSelectionError(Exception):
    """Raised when a selection names a provider the backend does not recognize.

    Dropping the name instead would burn fewer providers than the operator approved,
    with a clean 200 and no report (T-25-02).
    """


class RecordSpecError(Exception):
    """Raised when a record specification cannot become a batch — empty, unrecognized,
    or naming an object type the backend would resolve to "unknown"."""


class ViewNotSupportedError(RecordSpecError):
    """A saved view was named. Carries the operator-facing sentence verbatim."""

    def __init__(self):
        super().__init__(VIEW_REFUSAL)


def resolve_providers(override, config):
    """The effective provider selection for this batch. TOTAL — always a concrete list.

    `override` is the per-batch value (None means "no override"); `config` supplies the
    admin default. Accepts a list of names, `"all"`, `"none"`, or an empty list. An empty
    selection is legal and means no providers; it is still SENT, never omitted (D-06a).
    """
    selection = override if override is not None else (config or {}).get(
        DEFAULT_PROVIDER_SELECTION_KEY, FULL_WATERFALL
    )
    if selection is None:
        selection = FULL_WATERFALL

    if isinstance(selection, str):
        keyword = selection.strip().lower()
        if keyword == "all":
            return list(FULL_WATERFALL)
        if keyword in ("none", ""):
            return []
        raise ProviderSelectionError(
            f"{selection!r} is not a provider selection. Use 'all', 'none', or a list "
            f"drawn from {', '.join(KNOWN_PROVIDERS)}."
        )

    if not isinstance(selection, (list, tuple)):
        raise ProviderSelectionError(
            f"A provider selection must be a list of provider names, 'all' or 'none' — "
            f"got {type(selection).__name__}."
        )

    resolved = []
    for name in selection:
        cleaned = str(name).strip().lower()
        if cleaned not in KNOWN_PROVIDERS:
            raise ProviderSelectionError(
                f"{name!r} is not a provider this backend knows. Valid names are "
                f"{', '.join(KNOWN_PROVIDERS)}. Nothing was sent — a name the backend "
                f"does not recognize is dropped silently, so the batch would have "
                f"enriched with fewer providers than you approved."
            )
        if cleaned not in resolved:
            resolved.append(cleaned)
    return resolved


def normalize_object_type(value):
    """The deployed `normalizeObjectType`'s table — except that its "unknown" fallback
    raises here. Unknown reaches the backend as an event nothing can process, returning a
    clean 200 having enriched nothing."""
    normalized = _OBJECT_TYPES.get(str(value or "").strip().lower())
    if normalized is None:
        raise RecordSpecError(
            f"{value!r} is not a HubSpot object type this lane handles. Say 'contacts' "
            f"or 'companies'."
        )
    return normalized


# Hosts that are somebody's PROFILE PAGE, never a company's own domain. Mirrors
# n8n/code/companyLink.js's NOT_A_COMPANY_DOMAIN — the two must agree, because the client
# refuses here and the backend resolves there, and a domain one accepts and the other
# rejects is a silent divergence.
#
# Found live 2026-08-25 during the Phase 53 operator walk: an operator holding only a
# LinkedIn URL is the NORMAL case, and naive host extraction turned
# `linkedin.com/company/futsal-australia` into the domain `linkedin.com`. That searches
# HubSpot for domain=linkedin.com, finds nothing, and creates a company whose domain IS
# linkedin.com — after which every later LinkedIn-sourced company MATCHES that one poisoned
# record. One bad row swallowing every future company, with no error anywhere.
NOT_A_COMPANY_DOMAIN = frozenset({
    "linkedin.com", "lnkd.in", "facebook.com", "fb.com", "instagram.com", "twitter.com",
    "x.com", "youtube.com", "youtu.be", "tiktok.com", "threads.net", "medium.com",
    "crunchbase.com", "wikipedia.org", "en.wikipedia.org", "bloomberg.com", "zoominfo.com",
    "apollo.io", "abn.business.gov.au", "linktr.ee", "about.me", "sites.google.com",
    "wixsite.com", "squarespace.com", "godaddysites.com",
})


def _clean_domain(raw):
    """The deployed `Build Company Identity`'s cleanDomain(), mirrored: lowercase, strip
    scheme and `www.`, keep the host only. Same string on both sides of the boundary or
    the backend searches for something the operator never saw.

    Returns None for a host that cannot BE a company domain, so the caller refuses by name
    with guidance rather than searching HubSpot for a social-network host."""
    if not raw:
        return None
    domain = str(raw).strip().lower()
    domain = re.sub(r"^https?://", "", domain)
    domain = re.sub(r"^www\.", "", domain)
    domain = domain.split("/")[0].split("?")[0]
    if not domain or domain in NOT_A_COMPANY_DOMAIN:
        return None
    return domain


def build_envelope(spec, providers):
    """The POST body, from a record specification and an already-resolved selection.

    `spec` is one of:
      {"record_ids": [...], "object_type": "companies"}  -> an events array
      {"list": "<name>", "object_type": "contacts"}      -> the identifier, verbatim
      {"rows": [...], "object_type": "contacts"}         -> a `mode: "propose"` events array
      {"companies": [{"name","domain"}]}                 -> a WRITE-mode events array
      {"companies": [...], "propose": True}              -> a `mode: "propose"` events array
      {"people": [{firstname,lastname,company|email|linkedin_url}]} -> a WRITE-mode events array
      {"view": "<name>"}                                 -> refused (amendment #7)

    A list identifier is carried through untouched: the client does not resolve it, does
    not count it, and does not fabricate a count (D-01, D-02). Every form carries
    `providers`.

    A ROWS FORM DESCRIBES RECORDS THAT ARE NOT IN HUBSPOT (37-CONTEXT §5). Because of
    that, `mode: "propose"` is set inside this branch only — never read from `spec`,
    never accepted as a parameter — so the backend's write mode is structurally
    unreachable from a rows form rather than being a caller's responsibility to withhold.
    Only `MATCH_LOOKUP_KEYS` cross the boundary per row; every other row key (`phone`,
    `jobtitle`, `linkedin_url`) is dropped, because those are the only fields the
    backend's `Build Identity` reads into `identity_keys` and the match search filters
    on.

    THE LIST ENVELOPE IS NESTED, and it has to be (D-19). `n8n/code/listExpansion.js`
    reads `isPlainObject(body.list)` and then `body.list.name` / `body.list.objectType`.
    A flat `{"list": "<name>", "objectType": ...}` passes the `IF List Input` gate — a
    string is non-null — and is then refused by every request with "the enrichment request
    named no list", because `isPlainObject("Acme")` is false. That shape shipped briefly
    and broke the whole list lane while both sides' own tests stayed green, each testing
    its own half of a boundary neither crossed. `test_list_envelope_contract.py` and
    `tests/n8n/listEnvelopeContract.test.mjs` now pin the SAME literal from both sides.
    """
    if not isinstance(spec, dict):
        raise RecordSpecError(
            "A record specification must name record IDs, a list, or a view."
        )
    if spec.get("view"):
        raise ViewNotSupportedError()

    envelope = {"providers": list(providers)}

    if spec.get("list"):
        envelope["list"] = {
            "name": spec["list"],
            "objectType": normalize_object_type(spec.get("object_type")),
        }
        return envelope

    if "rows" in spec:
        rows = spec["rows"]
        if not isinstance(rows, (list, tuple)) or not rows:
            raise RecordSpecError(
                "No rows were given, so there is nothing to match or enrich. Provide at "
                "least one row."
            )
        object_type = normalize_object_type(spec.get("object_type"))
        events = []
        for row in rows:
            if not isinstance(row, dict) or not str(row.get("row_id") or "").strip():
                raise RecordSpecError(
                    "A row without a `row_id` can never be matched back to its response "
                    "— `row_id` is the join key every downstream verdict is keyed on."
                )
            event = {"row_id": str(row["row_id"]), "objectType": object_type}
            for key in MATCH_LOOKUP_KEYS:
                event[key] = _lookup_value(row, key)
            events.append(event)
        envelope["mode"] = "propose"
        envelope["events"] = events
        return envelope

    if "people" in spec:
        # A PEOPLE form names contacts the way an operator does — "John Tsatsimas at
        # Football NSW" — rather than by a HubSpot record id nobody carries in their head.
        # Found live 2026-08-25 in the Phase 53 walk: the backend has resolved contacts by
        # name since Phase 36 (`IF Name Searchable` -> `HubSpot Name Search` ->
        # `Adapt Name Search`, and `Build Identity` reads firstname/lastname/company), but
        # no client form emitted it, so the one sentence a non-technical operator would
        # actually say hit a wall between two halves that both supported it.
        #
        # This is deliberately NOT the `rows` form. Rows describes people who are NOT in
        # HubSpot and is pinned to `mode: propose` for that reason. This form describes
        # someone the operator believes IS in HubSpot, so it carries no mode and may write.
        #
        # Safety is inherited, not re-invented: the backend's own match lane decides. An
        # exact identity (email or LinkedIn URL) writes; a MEDIUM name+company match
        # becomes `needs_match_review` at Decide Action rather than writing, so a
        # same-named person is surfaced, never silently overwritten (36-CONTEXT §4).
        people = spec["people"]
        if not isinstance(people, (list, tuple)) or not people:
            raise RecordSpecError(
                "No people were given, so there is nothing to enrich. Name at least one "
                "person — a full name and their company, or an email address."
            )
        events = []
        for person in people:
            if not isinstance(person, dict):
                raise RecordSpecError("Each person must give a name, an email, or a "
                                      "LinkedIn URL.")
            event = {"objectType": "contacts"}
            for key in ("firstname", "lastname", "company", "email", "linkedin_url"):
                value = str(person.get(key) or "").strip()
                if value:
                    event[key] = value
            # The backend's own gate skips a row with no email, no linkedin_url and not
            # both a surname and a company — it would burn three provider calls on a row
            # that can only return nothing. Refuse it here instead, where the operator can
            # still fix it, and say which of the three would resolve it.
            has_identity = (
                event.get("email")
                or event.get("linkedin_url")
                or (event.get("lastname") and event.get("company"))
            )
            if not has_identity:
                named = event.get("firstname") or event.get("lastname") or "that person"
                raise RecordSpecError(
                    f"There is not enough to find {named} in HubSpot or at any provider. "
                    f"Add their company, or an email address, or a LinkedIn profile URL — "
                    f"any one of the three is enough."
                )
            events.append(event)
        envelope["events"] = events
        return envelope

    if "companies" in spec:
        # A COMPANIES form describes companies that may not be in HubSpot yet
        # (2026-08-25). It is the only write-mode form built from operator-typed input,
        # and `domain` is mandatory for exactly that reason: domain is the identity
        # anchor the backend's company lane searches on, and a domainless company can
        # neither be deduped nor matched — it could only ever be created, which is the
        # duplicate-company shape this form exists to avoid.
        #
        # `mode: "propose"` (2026-08-26, Phase 58) — set on this branch ONLY when the
        # caller opts in via `spec.get("propose")`; the default (no `propose` key) leaves
        # every event exactly as before: mode-less, write-mode. Per
        # `58-SPIKE-VERDICT.md` (live execution `11972`, OBSERVED rather than merely
        # traced from source), a request-level `mode` key on a companies event rides
        # `Parse HubSpot Event`'s row spread intact and IS read by `Decide Company
        # Action`'s `isReturnOnly`, forcing the non-writing `action: "proposed"` branch
        # before the write-safety allowlist check ever runs. The key is set PER EVENT —
        # that is the exact shape 58-02's probe exercised and the shape `isReturnOnly`
        # reads — the envelope-level key is set too, for parity with the `rows` form's
        # `envelope["mode"]`, but is harmless/unproven rather than the load-bearing one.
        companies = spec["companies"]
        if not isinstance(companies, (list, tuple)) or not companies:
            raise RecordSpecError(
                "No companies were given, so there is nothing to enrich or create. "
                "Name at least one company with its website domain."
            )
        propose = bool(spec.get("propose"))
        events = []
        for company in companies:
            if not isinstance(company, dict):
                raise RecordSpecError(
                    "Each company must give a name and a domain."
                )
            domain = _clean_domain(company.get("domain") or company.get("website"))
            name = str(company.get("name") or "").strip()
            # 2026-08-25, operator ruling from the Phase 53 walk: a blanket refusal hands
            # the research back to the operator, who does not want to do it. The guard is
            # "never silently invent a domain", not "go and find one yourself". So a
            # company with no usable domain is ACCEPTED when it has a name — the backend's
            # exact-name company search (added 2026-08-25) can resolve it — and only the
            # CREATE path still needs a domain, because domain is the dedupe anchor and a
            # domainless new company poisons every later match against it.
            if not domain and not name:
                given = str(company.get("domain") or company.get("website") or "").strip()
                if given:
                    # UNCHANGED verbatim (2026-08-25) — pinned by not being reworded here.
                    raise RecordSpecError(
                        f"{given!r} is a profile page rather than a company's own "
                        f"website, and no company name came with it, so there is "
                        f"nothing to look up. Give the company's name — the backend "
                        f"can match that on its own."
                    )
                if "name" in company:
                    # New 2026-08-26 (Phase 58): a bare-name-list row, or a mixed-lane
                    # row, that carried an empty/blank name and no website at all.
                    raise RecordSpecError(
                        "A company's name came through blank, and no website came "
                        "with it either, so there is nothing to look up. Give the "
                        "company's actual name — a blank line in a name list can't "
                        "be matched on its own."
                    )
                # New 2026-08-26 (Phase 58): the row never carried a `name` key at all
                # — e.g. a search-results-screenshot row whose name never rendered.
                raise RecordSpecError(
                    "This company's name never came through, and it has no website "
                    "either, so there is nothing to look up. Give the company's "
                    "name, or its own website."
                )
            event = {"objectType": "companies"}
            if domain:
                event["domain"] = domain
            if name:
                event["name"] = name
            if propose:
                event["mode"] = "propose"
            events.append(event)
        if propose:
            envelope["mode"] = "propose"
        envelope["events"] = events
        return envelope

    if "record_ids" in spec:
        record_ids = spec["record_ids"]
        if not isinstance(record_ids, (list, tuple)) or not record_ids:
            raise RecordSpecError(
                "No record IDs were given, so there is nothing to enrich. Paste the "
                "record IDs, or name a HubSpot list."
            )
        object_type = normalize_object_type(spec.get("object_type"))
        envelope["events"] = [
            {"objectId": str(record_id), "objectType": object_type}
            for record_id in record_ids
        ]
        return envelope

    raise RecordSpecError(
        "A record specification must name record IDs, a list, or a view."
    )


def enrichment_target(config):
    """The endpoint this module POSTs to. Never includes the secret."""
    return f"{str((config or {}).get('n8n_url') or '').rstrip('/')}/{ENRICHMENT_PATH}"


def dispatch_enrichment(envelope, armed, config, transport=requests):
    """One JSON POST. `armed` has NO default — see the module docstring.

    Returns the parsed response body when it is JSON, or `{status_code, text}` when it is
    not. Never a per-record outcome claim: reading the response per record is Phase 26's
    job.
    """
    # load_config() only enforces n8n_url (the universal minimum) — this is the guard
    # that stops a webhook_secret-less config from reaching the transmit path below
    # (mirrors review_queue.fetch_queue()'s require_capability call).
    config_gate.require_capability(config, "enrichment")

    if not armed:
        raise NotArmedError(
            "Live writes are off for this send — nothing was sent. They turn on only "
            "when the operator says yes to the send just described, and that yes "
            "covers that one send."
        )

    headers = {"X-Enrichment-Secret": config["webhook_secret"]}

    try:
        response = transport.post(
            enrichment_target(config),
            headers=headers,
            json=envelope,
            timeout=DEFAULT_TIMEOUT,
        )
    except Exception:
        # Never relay the transport exception's text — it can echo request headers.
        raise DispatchError(
            "Could not reach the n8n enrichment webhook. Check the connection and try "
            "again, or ask an admin to check the n8n Cloud instance if this persists."
        ) from None

    try:
        return response.json()
    except Exception:
        return {
            "status_code": getattr(response, "status_code", None),
            "text": getattr(response, "text", None),
        }


if __name__ == "__main__":
    import sys

    if len(sys.argv) not in (3, 4) or sys.argv[2] not in ("armed", "disarmed"):
        print(json.dumps({
            "ok": False,
            "error": "usage: enrichment.py <spec-json> armed|disarmed [providers-json]",
        }))
        raise SystemExit(1)

    _armed = sys.argv[2] == "armed"

    try:
        _spec = json.loads(sys.argv[1])
        _override = json.loads(sys.argv[3]) if len(sys.argv) == 4 else None
    except json.JSONDecodeError as _e:
        print(json.dumps({"ok": False, "error": f"could not parse argument as JSON: {_e}"}))
        raise SystemExit(1)

    try:
        _cfg = config_gate.load_config()
        _providers = resolve_providers(_override, _cfg)
        _envelope = build_envelope(_spec, _providers)
        _result = dispatch_enrichment(_envelope, _armed, _cfg)
    except (config_gate.ConfigError, ProviderSelectionError, RecordSpecError,
            NotArmedError, DispatchError) as _e:
        print(json.dumps({"ok": False, "error": str(_e)}))
        raise SystemExit(1)

    print(json.dumps({"ok": True, "envelope": _envelope, "response": _result}))
