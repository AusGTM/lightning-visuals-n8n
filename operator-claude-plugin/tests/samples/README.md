# Session 2 UAT samples — input adapters (2.1–2.7)

Sample inputs for walking **UAT session 2** in Claude Desktop, and for demoing the ingestion
adapters to an end client. Every step's expected outcome is below, including what a **FAIL**
looks like, so the walk produces a verdict rather than a vibe.

## Safety — read once before demoing

- **All data is fictional.** Domains use the RFC 2606 reserved `.example` TLD, so nothing here
  resolves, and no real person is named. There are deliberately **no invented staff at real
  organisations** — fabricating a named employee at a real company is the one thing a sample
  set must never do, because it looks exactly like real data once it is in a CRM.
- **Session 2 sends nothing.** Every step stops at the preview. Dispatch stays disarmed, so
  these rows reach HubSpot only if someone arms the lane and approves a send.
- **If you do demo a live send, expect nothing back from enrichment.** These companies do not
  exist, so providers will return no match — which is honest behaviour, not a broken demo.
  Use real record IDs for an enrichment demo (session 3/5), not these.

## The files

| Step | File | What it exercises |
|---|---|---|
| 2.1 | `21-prose-and-signature.txt` | Freeform prose + an email signature. Three people at three orgs, with **deliberate gaps**: Dan has no email or phone, "Wen" has a first name and no title, and the signature block is the sender (not a prospect). |
| 2.2 | `22-messy-headers.csv` **and** `clean-uat-contacts.csv` | Two CSVs on purpose — see "The two 2.2 files" below. The messy one exposes a real gap; the clean one is the one to demo. |
| 2.3 | `23-foreign-shape.json` | A badge-scanner export in a foreign shape — nested `badge`/`contact`/`employer` objects, `role_title: null`, an empty `social: {}`, and a person with `family: null`. |
| 2.4 | `24-url-step.md` | Instructions — this step needs a **real** public page, since the point is a live fetch. |
| 2.5 | `25-team-page-to-screenshot.html` | Open in a browser, screenshot it, hand the image to the skill. Four people; one has **no email**, one has **no contact details at all**, one is `R. Fontaine` with **no first name**. |
| 2.6 | `26-empty.csv`, `26-photo-no-text.pdf` | The two unreadable shapes: a zero-byte file, and a valid PDF whose only content is an image — **no extractable text**. |
| 2.7 | *(all of the above)* | Not a separate file. Every sample carries absent fields on purpose; 2.7 is the check that they came back **empty**. |

## The two 2.2 files, and why both exist

**`clean-uat-contacts.csv` — use this one in a client demo.** All 7 contact headers map
(`Email Address → email`, `Phone → phone`, `Company → company`, `LinkedIn → linkedin_url`, …).
Only `Notes` drops, correctly — it is not a contact field. It still carries the gaps that matter:
row 2 has no email, row 3 has almost nothing, so 2.7 and the `needs_review` routing are both
visible without the preview being a wall of red.

**`22-messy-headers.csv` — the adversarial one. It currently FAILS, and that is a real finding,
not a broken sample.** Its headers are taken verbatim from UAT 2.2's own wording (`E-mail
Address`, `Ph.`). Neither alias exists in `config/column_mapping.yaml`: the table has
`email address` and `e-mail` but not the hyphenated combination, and `phone`/`mobile`/`tel` but
not `ph.`. Six of seven headers drop.

The plugin handles this correctly — it predicts the drop per header and refuses to present the
file as send-ready, rather than sending four rows that would all land `needs_review` carrying only
a job title. **The requirement and the mapping disagree; the code does not.** Tracked as
`.planning/todos/pending/2026-08-04-uat-22-names-aliases-the-mapping-lacks.md` and being fixed in
Phase 34 (widen the unambiguous aliases, add suggest-and-confirm for the genuinely ambiguous ones).

Keep both. The messy file is what caught the gap, and it is the regression guard once Phase 34
lands — after it, `E-mail Address` and `Org.` should map, while `Ph.` should still ASK rather than
guess (it could be a photo column) and `Full Name` should still refuse (there is no name-splitter,
by design).

## What each step should produce

- **2.1 / 2.3 / 2.5** — rows come back with **provenance** (which input, and where in it). Absent
  values stay absent. Anything genuinely uncertain lands in the **one per-batch ambiguity list**,
  not asserted as fact and not repeated per row.
- **2.2** — reads straight through. No renaming, no manual mapping.
- **2.4** — contact/company data extracted from the fetched page, provenance naming the URL. A
  page that cannot be fetched and a page with nothing usable are **different outcomes** and must
  read differently.
- **2.6** — `26-photo-no-text.pdf` refuses by type (`Unsupported file extension: .pdf`).
  `26-empty.csv` must say the file carried **no data rows** and name the likely causes — and must
  **not** offer the arming phrase (added in plugin 0.7.1; before that it previewed a silent zero).
- **2.7** — inspect any row where the source had no value. It must be **empty**.

## What counts as a FAIL

1. **Any invented value.** A guessed email from a name and a domain, a title inferred from a
   company, a first name split out of `R. Fontaine`. This is the most serious defect in the whole
   UAT (STRUCT-04) — the samples are built to tempt it.
2. **A silent drop.** Zero rows with no explanation, or a row quietly discarded.
3. **The sender treated as a prospect.** `21-prose-and-signature.txt` signs off as Alex Whitfield
   of Lightning Visuals — that is *your own* signature block, not a lead.
4. **An ambiguity asserted as fact.** "Wen" has no surname in two of the inputs; a row that
   invents one, or silently drops the person, both fail.
