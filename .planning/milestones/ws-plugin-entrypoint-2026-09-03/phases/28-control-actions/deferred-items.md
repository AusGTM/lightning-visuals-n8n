## Deferred — logged by 28-01 (2026-07-31)

status: resolved
resolved: 2026-07-31
resolved_by: commit 6408981 — "fix(tests): strip prefixed verified_at stamps, killing the 1 ms merge flake"

**RESOLVED — no outstanding items in this file.** The one entry below was fixed the same
day it was logged; the record was simply never updated, so `audit-uat` kept counting it as
open debt for five weeks.

Kept verbatim for history, NOT as an open item:

> **Flaky node test:** `tests/n8n/mergeContacts.test.mjs:67` failed once on a 1ms
> `lv_jobtitle_verified_at` timestamp mismatch inside a `deepStrictEqual`, then passed on two
> reruns. Pre-existing, out of 28-01's scope (no node file touched). The fixture bakes a
> wall-clock timestamp into an expected object; it should be injected or frozen.

The fix took the "injected or frozen" route the note asked for, as a shared helper rather
than a per-test fixture edit: `tests/n8n/verifiedAtStrip.mjs` exports `stripVerifiedAt`,
which normalizes every wall-clock stamp in a merge result before comparison. Its own header
records why the naive fix would not have worked — the key shape is both bare
(`verified_at`, inside provenance entries) and prefixed (`lv_jobtitle_verified_at`, in the
canonical patch), and a pattern anchored on `"verified_at":` misses the prefixed form, which
is precisely the stamp that produced the 1 ms flake. `mergeContacts.test.mjs` imports it at
line 16 and uses it at lines 67 and 132 — the two `deepEqual` sites.
