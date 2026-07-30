---
name: contact-upload
description: Load a contact spreadsheet (CSV or XLSX) into HubSpot through the n8n enrichment backend. Use when the operator asks to load, upload, or import contacts into HubSpot from a spreadsheet — or invoke it directly as /operator-claude-plugin:contact-upload.
---

# Contact Upload

This skill turns a spreadsheet into a `hubspot/contact-upload` request. It never maps
columns, normalizes phone numbers, verifies emails, or resolves identity — n8n's
`Map Columns` node and everything downstream of it in `wf_contact_ingest_cloud.json`
already does that. This skill's whole job is: read the file unchanged, show what would
be sent, and — only when explicitly armed — send it.

## Steps

1. **State the target up front, before any other work.** Run:

   ```
   python3 scripts/config_gate.py
   ```

   If the JSON reports `"ok": false`, relay its `"error"` message to the operator
   exactly as given, then STOP. Never show, echo, or ask for a secret, and never
   surface a raw socket or parser error — the script has already translated that.

   If it reports `"ok": true`, tell the operator the endpoint from `"target"` and that
   dispatch is currently **disarmed** for this conversation. Say this even if the
   operator only asked a question, before doing anything else.

2. **Resolve the input file.** If the operator has attached a file in this session, try
   reading it at whatever path the attachment resolves to, inside a single try/except.
   If that is unavailable, ask the operator to `@mention` the spreadsheet by name (the
   autocomplete picker, not a typed path) — `@` reaches any file already in the
   workspace, and this is the reliable leg for a file that lives elsewhere on disk (a
   Downloads folder, a Desktop file) once attached. If neither path resolves, ask the
   operator directly for one. Do not scan temp directories, retry in a loop, or guess at
   a storage convention.

3. **Read the file.**

   ```
   python3 scripts/tabular.py <path>
   ```

   <!-- PREVIEW-STEP-OWNER: scripts/tabular.py owns this entire preview step in this
        plan. Plan 23-05 replaces it with the real adaptive preview (per-column fill
        rates, first-10/last-3 for large batches, an Artifact on request) — that plan
        edits this step, it does not rewrite it. -->

   Show the operator the header list and row count this reports.

4. **Ask for approval.** If the operator declines, STOP here — nothing is sent, and
   nothing beyond reading the file has happened.

5. **Check arming.** Disarmed is the default and the state of every new conversation.
   Say plainly that sending is off, and that the operator can turn it on for this
   conversation only by saying: **"arm the upload"**. This state is never written to
   disk — it exists only as the `armed` flag passed to the one dispatch call below, for
   this turn only.

6. **Dispatch only once the operator has said the arming phrase this turn.**

   ```
   python3 scripts/dispatch.py <path> armed
   ```

   Report the result as "the POST was accepted, n8n returned this" — never as a
   per-record outcome. Parsing per-record results is Phase 26's job, not this one's.
