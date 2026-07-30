## Deferred — logged by 28-01 (2026-07-31)

- **Flaky node test:** `tests/n8n/mergeContacts.test.mjs:67` failed once on a 1ms
  `lv_jobtitle_verified_at` timestamp mismatch inside a `deepStrictEqual`, then passed on two
  reruns. Pre-existing, out of 28-01's scope (no node file touched). The fixture bakes a
  wall-clock timestamp into an expected object; it should be injected or frozen.
