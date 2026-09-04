## Review Instructions

**Verify against source — do not review the plan text in isolation.** The plans reference real files, functions, and tests in this repo. You have repo access; use it.
1. Open the referenced files and check each claim against the actual code.
2. For every strength or concern, cite concrete `path/to/file:line` evidence plus the mechanism.
3. When a plan asserts a mechanism works (a guard, a flag separation, a test that exercises a path), trace whether it actually does what is claimed — do not take the plan's word for it.
4. If you cannot read the repo, say so explicitly and downgrade that finding to an open question rather than asserting it.

Findings citing `file:line` evidence are weighted far more heavily than impressionistic ones; a review that only restates the plan's own claims has low value.

Analyze each plan and provide:

1. **Summary** — One-paragraph assessment
2. **Strengths** — What's well-designed (bullet points)
3. **Concerns** — Potential issues, gaps, risks (bullets, each tagged HIGH/MEDIUM/LOW)
4. **Suggestions** — Specific improvements
5. **Risk Assessment** — Overall risk level (LOW/MEDIUM/HIGH) with justification

Focus on:
- Missing edge cases or error handling
- Dependency ordering issues (this phase has 3 waves; wave 2 runs 60-02 and 60-03 in parallel)
- Scope creep or over-engineering
- **Security considerations — this phase WIDENS a write authority.** The review lane was deliberately excluded from write grants by an earlier phase (30-01 D-02/D-08e); this phase reverses that on purpose. Scrutinize whether the reversal is bounded as claimed.
- Whether the plans actually achieve the phase goal

**Specific claims worth independent scrutiny — each is load-bearing and each could be wrong:**
- `disarm` is changed to clear every overlayable constant the *fetched workflow actually declares*, rather than a fixed tuple. Does this weaken any existing disarm guarantee? Does it behave correctly when the workflow read fails?
- The plans claim widening `write_grant.py`'s local `WRITE_ENABLING_FLAGS` breaks `test_write_grant_guardrails.py`'s `_gate()` fixture, and fix both in one task. Verify the coupling is real and that one task genuinely covers it.
- A claimed trap: calling `preflight_before_send` on the review lane *inside* an open review batch window would read the window's own arm as "writes still live" and disarm mid-batch. Is the prohibition sufficient, or does something still reach that path?
- `classify_review_item` deliberately sets `reason=None` because `_looks_forbidden` is a substring check on `arm`/`grant`/`permission` and operator free text could raise on a bookkeeping write that must never raise. Is dropping the reason the right trade, and is the forbidden-name scan actually the constraint claimed?
- D-60-07: a `reject` works with NO grant open, so a closed authority cannot strand a flagged record. Does any plan path let that carve-out authorize more than a reject?
