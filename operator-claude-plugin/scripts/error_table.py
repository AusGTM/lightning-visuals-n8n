"""operator-claude-plugin/scripts/error_table.py

Translates an n8n / provider / HubSpot failure message into one plain sentence and an
attribution of who can act on it (STATUS-02, 27-CONTEXT.md D-04).

Pure lookup: standard library only, no network, no file read. That purity is what lets
the unmatched branch's guardrail (D-05) be proven exhaustively by unit test.

The table is expected to grow (D-06): every signature the in-session Claude fallback
handles more than once is a candidate for promotion into it. Promoting one is appending
one ``_Entry`` to ``TABLE`` and nothing else.

Matching is free-text and case-insensitive on purpose. 27-RESEARCH.md assumption A4 notes
the per-node and execution-level error field shapes are cited from public docs and were
never observed live in this instance, so nothing here may depend on a particular field
being present.
"""
import re

# Who can act. Three of the four seeded causes are credential- or balance-shaped: the
# operator holds no credential and cannot top up a provider balance, so those are an
# admin's. A record the CRM rejected came from the operator's own file, so that one is
# theirs.
ADMIN = "admin"
OPERATOR = "operator"

_NO_TEXT = "(no error text was supplied)"


class _Entry:
    """One row of the table: what to match, what it means, and whose problem it is."""

    __slots__ = ("pattern", "cause", "sentence", "who_can_fix")

    def __init__(self, pattern, cause, sentence, who_can_fix):
        self.pattern = re.compile(pattern, re.IGNORECASE)
        self.cause = cause
        self.sentence = sentence
        self.who_can_fix = who_can_fix


# Order is load-bearing: the first match wins. Authentication is checked before quota so
# a message carrying both ("401 ... balance exhausted") reads as the credential problem,
# which is the one that blocks everything rather than one provider.
TABLE = (
    _Entry(
        r"\b(401|403)\b|unauthori[sz]ed|forbidden|invalid[ _-]?(api[ _-]?)?"
        r"(key|token|credential)|authentication (failed|error)|expired token",
        "expired_credential",
        "The saved login for one of the connected services was rejected, so nothing could "
        "be looked up until it is renewed.",
        ADMIN,
    ),
    _Entry(
        r"\b429\b|too many requests|rate[ _-]?limit",
        "rate_limit",
        "One of the services was asked for more than it allows in a short window and made "
        "us wait, which clears on its own.",
        ADMIN,
    ),
    _Entry(
        r"\b402\b|payment required|quota|insufficient (credit|balance|fund)"
        r"|out of credit|credit(s)? (exhausted|depleted)|no credits remaining",
        "exhausted_quota",
        "A data provider's prepaid balance has run out, so no further lookups can be made "
        "until it is topped up.",
        ADMIN,
    ),
    _Entry(
        r"\b400\b|bad request|validation[ _-]?error|property values were not valid"
        r"|invalid (input|property|email|value)|does not exist for object type",
        "malformed_record",
        "The CRM refused a record because one of its values was not in a form it accepts, "
        "so that row was not saved.",
        OPERATOR,
    ),
)


def translate(text):
    """Translate ``text`` into a plain-language cause, or say honestly that we cannot.

    Returns a mapping with ``matched``, ``cause``, ``sentence``, ``who_can_fix``,
    ``is_interpretation`` and ``raw``. Never raises: a status surface must not blow up
    while explaining why something else blew up, so a null, empty or non-string input is
    simply the unmatched result.
    """
    raw = text if isinstance(text, str) and text.strip() else _NO_TEXT

    for entry in TABLE:
        if entry.pattern.search(raw):
            return {
                "matched": True,
                "cause": entry.cause,
                "sentence": entry.sentence,
                "who_can_fix": entry.who_can_fix,
                "is_interpretation": False,
                "raw": raw,
            }

    return {
        "matched": False,
        "cause": None,
        "sentence": (
            "This failure signature is not one the plugin recognises, so anything said "
            "about it below is an interpretation rather than a known fact."
        ),
        "who_can_fix": ADMIN,
        "is_interpretation": True,
        "raw": raw,
    }
