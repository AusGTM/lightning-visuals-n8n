# Decision record — derived (portal-wide) role vocabulary rejected

**Decided:** 2026-09-04
**Decided by:** operator, in session, reviewing the live `scripts/role_vocabulary.py --dry-run`
acceptance run
**Status:** LOCKED

## Decision

**REJECT and record.** The curated 17-family `operator-claude-plugin/config/role_vocabulary.yaml`
stays exactly as shipped. A segment-scoped evidenced vocabulary is deliberately **not scoped** —
no future work is implied by this record.

## Measured evidence (verbatim from the acceptance run, `260904-39r-SUMMARY.md` §
"Operator acceptance run, 2026-09-04")

- Portal-wide derivation produced 8 families, all entirely corporate: Chief Executive, Director,
  Owner/Founder, President, General Manager, Marketing Leadership, Managing Director/Partner,
  Operations Leadership.
- **Not one racing-governance family** — no Chairman, Committee member, Secretary Manager,
  Treasurer, Track & Facilities, Catering & Events, Administration.
- Head coverage: 200/2,044 distinct titles, covering 1,855/3,771 titled contacts (49%).
- Adopting the derived file would drop the 9 governance families plan 62-09 added and take Roma
  Turf Club from 16-selected back to 0.
- Raising `--head` does not fix it: governance titles are rare portal-wide by construction, so
  they sit in the tail regardless of head size.
- The derivation is behaving CORRECTLY and producing a misleading answer — this is not a defect
  in the derivation code.

## Not affected by this decision

The double-unescape fix landed by Tasks 1 and 2 of this same quick task (260904-447) is a
normalisation bug fix at both seams (`scripts/role_vocabulary.py::_normalize_title` and
`operator-claude-plugin/scripts/role_classify.py::_tokenize`) and is independent of this REJECT
— the curated file's content is not changed by it.

## Standing rule

The derived output is useful as **EVIDENCE** of what recurs portal-wide, never as a replacement
for the curated file.
