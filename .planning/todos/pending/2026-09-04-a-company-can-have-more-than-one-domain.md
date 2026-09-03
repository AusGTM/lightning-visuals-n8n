---
created: 2026-09-04T22:35:00.000Z
updated: 2026-09-04
title: a company can legitimately have more than one domain — the relatedness rule compares against exactly one and holds correct emails
area: operator-plugin
severity: major
files:
  - operator-claude-plugin/scripts/suggest_contacts.py
  - operator-claude-plugin/skills/suggest-contacts/SKILL.md
---

## The case, found live

Roma Turf Club round, 2026-09-04. HubSpot records the company's domain as
**`romaturfclub.com.au`** — and that is not wrong: the round's own discovery ladder fetched
`www.romaturfclub.com.au/sitemap.xml` successfully and read its committee page from that host.

But the club's published contact address is **`INFO@romaturfclub.org.au`** — a different
registrable domain, same organisation.

`email_domain_relation` treats "related" as `ed == cd or ed.endswith("." + cd)`. A `.org.au`
address measured against a `.com.au` record is neither, so **every genuine club email would be
held as `email_domain_mismatch`** — the same verdict a stranger's address gets.

## This is NOT the wrong-domain bug, and must not be merged with it

`.planning/todos/pending/2026-09-04-provenance-aware-manual-protected.md` and its companion
cover a domain that is WRONG and cannot self-correct (Brisbane Lions). This one is different:
the recorded domain is CORRECT, verifiably serving the company's own website. The record is
INCOMPLETE, not incorrect. A fix that "corrects" `.com.au` to `.org.au` would break the
discovery ladder, which needs the website host.

So the shape is **an alternate/secondary domain set**, not a better single value.

## Do not fix it by loosening the match rule

The obvious-looking fix — accept a shared registrable label across different eTLDs, so
`romaturfclub.com.au` matches `romaturfclub.org.au` — is unsafe as a general rule.
`<label>.com.au` and `<label>.org.au` are separately registrable in Australia and can be
different organisations entirely. That would reintroduce exactly the failure the ruling was
made to stop: the Craig Smith case, in the same round, where `thehartford.com` was correctly
held.

The single-directional suffix guard must also survive untouched — it is what refuses
`romaturfclub.com.au.attacker.tld`.

## Shape of the fix

- Let a company carry MORE THAN ONE known domain, and have `email_domain_relation` accept a
  match against any of them (each still by the existing equality-or-subdomain rule, applied
  per domain — not a new looser rule).
- Where the extra domains come from is the real design question: an operator-supplied
  alternate on the company record; the domain observed in a `mailto:` on the company's own
  crawled contact page (self-asserted by the site the record already points at, which is
  decent evidence); or an explicit confirm step. Decide deliberately — an auto-learned second
  domain is a widened send-gate, so it should probably be proposed and confirmed, never
  silently adopted.
- `company_domains` is currently `{name: website}`. Widening its value to a collection is the
  API change; its REQUIRED-ness and the suffix trap stay exactly as they are.

## Immediate operator workaround

Add the alternate domain to the company record (or supply it in `company_domains`) before a
round, and its committee emails will pass. Roma specifically: `romaturfclub.org.au` alongside
`romaturfclub.com.au`.
