# Plan 23-02 — Summary

**Phase:** 23 — Walking Skeleton — Plugin Shell & Tabular Dispatch
**Plan:** 02 — Code-tab file-handoff smoke test
**Type:** `checkpoint:human-verify` (blocking)
**Executed by:** the operator, in a live Claude Desktop **Code tab** session
**Date:** 2026-07-31
**Outcome:** ✅ Complete — all four observations positive

---

## Why this plan existed

`23-RESEARCH.md` could not settle from documentation whether an operator-attached file in the
Claude Desktop Code tab resolves to a real filesystem path a plugin's Python script can open. An
open upstream issue (`anthropics/claude-code#54062`) describes exactly that gap for images. D-14a
therefore ordered a single cheap live probe **before** any file-handoff code was written, so that
plan 23-04 would not sink effort into temp-directory scanning or an upload shim for a leg that
could not work.

Research Pitfall 3 named that failure explicitly. This plan prevented it.

---

## Observed results

All four observations were run in a real Code-tab session with this repository as the working
folder. A throwaway CSV was created **outside** the repo at `~/Desktop/lv-smoke-test.csv` with
deliberately messy headers (`Email Address`, `First Name`, `Notes`) and two rows of invented data
using RFC 6761 reserved `.test` domains — no real contact data was used to answer an environment
question (mitigates T-23-07).

### (a) Does an attachment resolve to a readable path? — **YES**

The attached file resolved to an absolute path and a shell command read its first line:

```
/Users/robertli/Desktop/lv-smoke-test.csv
Email Address,First Name,Notes
```

**This refutes the pessimistic assumption D-14a was written against.** The file was not merely
visible as conversation content — it was a real path on disk, openable by a script.

### (b) Is `python3` available in that session? — **YES**

```
Python 3.14.5
```

### (c) Do the three dependencies import? — **YES**

```
python3 -c "import openpyxl, requests, yaml; print('deps ok')"
deps ok
```

No install step was required. Step (3) of the probe — whether installing them is blocked — was
therefore moot and not exercised.

**Important nuance recorded by the operator:** system `python3` carries these three packages, but
the **repo's test suite still requires `.venv/bin/python -m pytest`** (system python lacks the
suite's broader dependency set). These are two different interpreters serving two different
purposes, and conflating them will break test runs.

### (d) Does `@mention` resolve to a real path? — **YES**

`@` indexes the **workspace**, so the Desktop file was out of its reach and a repo file was used
instead. `@operator-claude-plugin/README.md` resolved and read:

```
/Users/robertli/Desktop/consulting/lightning-visuals/lv-n8n-poc/operator-claude-plugin/README.md
# Operator Claude Plugin
```

---

## What this means for plan 23-04

D-14a instructed: build `@mention` as the reliable mechanism, attempt attachment opportunistically
behind one try/except, and build **no** attachment plumbing beyond that. That instruction was
conditional on the attachment leg being unproven. **It is now proven.**

**Revised build instruction for 23-04:**

1. **Both legs are real.** Implement a two-legged file handoff rather than one leg plus a
   defensive stub:
   - **`@mention`** — for files already inside the repo/workspace. `@` only indexes the workspace,
     so this leg cannot reach files elsewhere.
   - **Attachment** — for files anywhere on disk, which is the realistic operator case (a
     spreadsheet in Downloads or on the Desktop, not committed to the repo).
2. **Still build no speculative plumbing.** The probe licenses reading a path that the session
   hands over. It does **not** license temp-directory scanning, upload shims, or guessing at
   attachment storage conventions. If a path is not supplied, ask for one — do not go hunting.
3. **Dependency install is not a phase concern.** `openpyxl`, `requests`, and `PyYAML` import
   cleanly from the session's `python3`. The plugin still ships its own `requirements.txt` (D-01)
   for portability, but 23-04 needs no install step or bootstrap path.
4. **Interpreter discipline.** Plugin scripts run under the session's `python3`. The repo's tests
   run under `.venv/bin/python`. Do not substitute one for the other.

---

## Acceptance criteria — met

- [x] SUMMARY records, as yes/no with observed evidence: (a) attachment resolves to a readable
      path — **yes**; (b) python3 available — **yes**; (c) three dependencies import or can be
      installed — **yes, import directly**; (d) `@mention` resolves to a real path — **yes**.
- [x] The "(a) is no" clause does not apply. Recorded above instead: the attachment leg **is**
      viable, and 23-04 builds it as a real leg rather than a single try/except.

## Threats addressed

- **T-23-07 (information disclosure via smoke-test CSV):** mitigated — invented values only,
  reserved `.test` domains, no real contact data.
- **T-23-08 (attachment-path guessing):** mitigated — the probe replaced guesswork with an
  observed answer. The answer happened to be positive, which removes the guessing pressure
  entirely rather than merely bounding it.

## Deviation from plan

None in execution. The plan anticipated a likely "no" on (a) and pre-authorized the degraded
single-leg build. The observed "yes" **widens** what 23-04 may build, and that widening is
recorded here as an explicit instruction rather than left for the executor to infer.

`23-CONTEXT.md` D-14a has been amended to match.
