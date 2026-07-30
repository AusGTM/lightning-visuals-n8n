# Reading Non-Tabular Input

This file is instructions for you, Claude, not documentation about the plugin. It loads only
when the operator's input is not already a spreadsheet — a paste of prose, a foreign-shaped JSON
blob, a public URL, or one or more screenshots. If the input is a CSV or XLSX file, you do not
need this file at all; `scripts/tabular.py` reads it unchanged and nothing below applies.

## You are the extractor. There is no model call.

For anything that is not already a spreadsheet, **you** read the source and write the rows down.
There is no Anthropic API call, no API key anywhere in this plugin, and no extraction library —
per D-01/D-02 you, the assistant already running this conversation, are the extraction engine.
`scripts/extraction.py` never extracts anything; it only validates what you already wrote. Do not
reach for an HTTP client, an OCR library, or the Anthropic API for any part of this — all three
are outside this design, and none of the adapters below need them.

## The no-invention rule

This governs every adapter below, and it is the single most important rule in this file. Where a
row still fails after following it, the failure is the correct outcome:

1. **A field the source does not supply is left out of the row entirely.** Never fill it from
   what you already know about the person or the company — a blank cell is honest; a plausible
   guess is not.
2. **A value the source renders unclearly goes in the ambiguity list, and the field is left out
   of the row it belongs to.** Do not put your best reading in the row and hope it is right.
3. **Never fill a gap to make a row satisfy the identity rule** (a non-blank `email`, or all
   three of `firstname`/`lastname`/`company`). A row that gets rejected with a stated reason is
   the correct outcome. A row you completed just to get it past that check is not — it is
   invention with extra steps.

`scripts/extraction.py` can only check the structural half of this rule (every accepted row
carries provenance; a field flagged as an ambiguity cannot also carry a value). It cannot check
whether what you wrote down is true. That half is this file, not the script.

## The handoff: write a file, then run the validator

Write everything you extracted as one JSON object to a file inside the plugin's scratch
directory (`operator-claude-plugin/scratch/`), then run:

```
python3 scripts/extraction.py <path-to-the-file-you-wrote>
```

and read its JSON output from stdout. Do this even for a single small paste — never rely on
someone (or something) parsing rows back out of your own chat reply. A file the validator opens
and either parses or names an error is the only version of this handoff that fails loudly; a
sentence of commentary next to a fenced JSON block in a chat turn is exactly the kind of thing
that quietly breaks that parse.

The validator's JSON output on stdout carries `accepted` (rows with provenance), `rejected`
(index + reason), `dropped_keys` (index + key, for anything outside the canonical set), and
`ambiguities`. If it exits non-zero instead, its output carries a `code` and an `error` — relay
that message, do not reinterpret it, and do not retry by guess-fixing the file yourself.

## Artifact schema

The file you write is one JSON object with these top-level keys:

- `batch_id` — any string identifying this batch.
- `source` — `{"kind": "prose" | "json" | "url" | "screenshot", "detail": "..."}`, a short note
  on where this batch came from.
- `records` — a list of `{"row": {...}, "provenance": {...}}` objects, one per person you
  identified. `row` carries canonical props (see below) and may also carry a key outside that
  set — the validator strips and reports it, it does not reject the record for it alone.
  `provenance` is `{"input": "...", "locator": "..."}`: which input this came from, and where in
  it (a span of pasted text, a JSON path, a URL, or an image name and region).
- `ambiguities` — a list of entries, each naming the record index, the field, what you saw, and
  why it is uncertain. Empty list if there are none — never omit the key.

This is a complete, valid example — two records (one via the `email` identity group, one via
`firstname`+`lastname`+`company`) and one ambiguity:

```json
{
  "batch_id": "batch-2026-07-31-001",
  "source": {"kind": "prose", "detail": "pasted email signature block"},
  "records": [
    {
      "row": {
        "email": "priya.nair@example.com",
        "firstname": "Priya",
        "lastname": "Nair",
        "jobtitle": "Head of Broadcast Ops",
        "company": "Example Racing League"
      },
      "provenance": {
        "input": "pasted_text",
        "locator": "lines 4-7: 'Priya Nair | Head of Broadcast Ops | Example Racing League | priya.nair@example.com'"
      }
    },
    {
      "row": {
        "firstname": "Ben",
        "lastname": "Ito",
        "company": "Example Racing League"
      },
      "provenance": {
        "input": "pasted_text",
        "locator": "line 9: 'Ben Ito, Example Racing League'"
      }
    }
  ],
  "ambiguities": [
    {
      "record_index": 1,
      "field": "jobtitle",
      "seen": "'Snr Prod...' — the line wraps mid-word",
      "reason": "the pasted text wraps before the title finishes and the rest is not legible"
    }
  ]
}
```

That block is executable documentation, not decoration: a test in this plugin's suite parses it
out of this file and runs it through the real validator, so it cannot quietly stop matching what
`scripts/extraction.py` actually accepts.

## Canonical props — the entire vocabulary

```
company, email, firstname, jobtitle, lastname, linkedin_url, phone
```

These seven are all there is. The backend's `Map Columns` node drops anything outside this set
with no error and no report of its own — so a key outside this set only ever reaches the
operator because the validator here surfaces it first. Never assume the backend will tell anyone
about a key it silently dropped.

## Adapter: pasted freeform text (INGEST-01)

Signature blocks, a typed list of names and companies, an email thread pasted into the
conversation. Read it and produce one row per person you can actually identify — do not force a
row for a name with nothing else attached to it unless it satisfies the identity rule on its own.

- **Provenance locator:** the span of the paste that produced the row — enough surrounding text
  that the operator can find it by eye in what they pasted (a line range and a short quote is
  usually right; "the paste" alone is not enough).
- **Named empty outcome:** a paste with no identifiable person in it is a named empty result —
  say so plainly (what you looked for, why nothing qualified) — never a silent zero-row batch
  with no comment.

## Adapter: foreign-shaped JSON (INGEST-03)

A JSON blob from some other system's export, shaped however that system shapes it. Translate
each key to the canonical prop it means (a `"work_email"` key means `email`, a `"linkedin"` key
means `linkedin_url`, and so on) and build rows over the canonical set.

Where a source key has no canonical meaning, **carry it onto the row as-is rather than dropping
it.** The validator's existing strip-and-report path then surfaces it to the operator — this is
the same mechanism that reports an invented field, not a second reporting channel that could
disagree with the first.

- **Provenance locator:** the path to the source object (e.g. an array index, or a key path
  like `contacts[3]`).
- **Named empty outcome:** JSON that parses but contains no person-shaped object is a named empty
  result, worded as such.
- **Named unreadable outcome:** JSON that does not parse at all is a named unreadable result,
  worded differently from the empty case — the operator's next move differs: a malformed export
  needs a different file, an empty one needs a different search or query.
