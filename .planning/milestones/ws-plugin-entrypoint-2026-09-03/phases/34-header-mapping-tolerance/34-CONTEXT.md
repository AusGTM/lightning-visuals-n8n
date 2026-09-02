# Phase 34: Header Mapping Tolerance — Context & Handover

**Written:** 2026-08-04 for a context clear. **Read this first; it is self-contained.**
**Workstream:** `plugin-entrypoint` · **Target releases:** plugin `0.8.0` + one backend redeploy

---

## 1. Where things stand right now

- **Milestone v0.6 SEALED** 2026-08-04 (49/49). **Phase 33 COMPLETE** — RB-10 walked live.
- **Plugin `0.7.3` is published, installed, and active.** Marketplace clone synced. Config and
  the dashboard pointer live in
  `~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/` and survive updates.
- **Suites (baselines to beat):** plugin **960 passed / 5 skipped** · full python **1841 / 6** ·
  node **550** · disarmed-artifact gate **0**.
- **Tenant disarmed.** Nothing armed, no gate variables set, crontab empty.
- Branch `feat/v0.6-plugin-entrypoint`, pushed to `origin/master`, tree clean.

**UAT session 2 is walked.** 2.1 / 2.3 / 2.6 / 2.7 **PASS**. 2.2 **FAILS the criterion as
written** — that failure is this phase's reason to exist.

---

## 2. The problem, precisely

UAT 2.2 reads, verbatim:

> Give it a CSV or XLSX with messy headers (`E-mail Address`, `Ph.`) — Reads them without you
> renaming anything first

**Neither named alias exists.** `config/column_mapping.yaml` has `email address` and `e-mail`, but
not `e-mail address`; `phone`/`mobile`/`tel`, but not `ph.`. Also missing: `org.`,
`linkedin profile`. `Full Name` cannot work at all — there is no name-splitter, by design.

Against `operator-claude-plugin/tests/samples/22-messy-headers.csv`, **6 of 7 headers drop** and
every row would land `needs_review` carrying only a job title.

**The plugin behaved correctly.** It predicted the drop per-header and refused to present the file
as send-ready. The requirement and the mapping disagree — the code does not.

**Only visible since `0.7.3`.** Before that, `column_mapping.yaml` was unpackaged, so the preview
could never predict mapping. The earlier 2.2 PASS was real but tested `Email Address`/`Phone`,
which do map.

Full write-up: `.planning/todos/pending/2026-08-04-uat-22-names-aliases-the-mapping-lacks.md`.

---

## 3. The decision (operator, 2026-08-04) — build BOTH, split by ambiguity

### Half A — widen the alias table (deterministic, backend-owned)

Add the unambiguous near-misses: **`e-mail address`, `org.`, `linkedin profile`**, and consider
`company name`, `work email`, `mobile phone`, `e-mail address:`. These are lookups, not judgment.

**This is a BACKEND change.** Two files must move together:

- `config/column_mapping.yaml` — the repo copy AND `operator-claude-plugin/config/column_mapping.yaml`
  (shipped in 0.7.3; `test_column_mapping_shipped.py` pins them byte-identical — if you edit one,
  re-copy, never hand-edit both)
- `n8n/code/columnMap.js` — the backend's own alias map

⚠ **The two alias sets agree today by hand, not by construction.** `build_cloud_workflows.py` does
NOT generate the JS from the YAML. **Widening one without the other makes the preview lie about the
backend, confidently** — the worst direction. **Add a test pinning the YAML alias map equal to
`columnMap.js`'s before changing either.** That test is the real deliverable of Half A.

Then: rebuild workflows, **disarmed redeploy + bounce every active workflow** (see §6).

### Half B — suggest-and-confirm for the genuine tail (client)

Modelled explicitly on Phase 31's `_hintLabels` in `n8n/code/hubspotEnums.js`, which is
**"MESSAGE HINT ONLY … Never consulted by `normalizeEnumValue`; only used to make the refusal
sentence actionable."** Same rule one layer up: **fuzzy suggests, human decides, the deterministic
engine executes.**

Shape:

> `Ph.` isn't a header the backend recognises. I think you mean **phone** — confirm and I'll
> correct the header row before sending. `Org.` → **company**?

- Operator confirms **each** non-exact match. No silent renames, ever.
- After correction, re-preview so the operator sees the real mapping prediction before approving.
- The client corrects the **header row of the file it sends**; it does NOT map data. The backend's
  `Map Columns` remains the single authority.

**Why this is allowed where enum mapping was not:** 7 candidate props vs 148 enum values; the
operator sees `header → canonical prop` in the preview (0.7.3 unlocked this); and aborting costs
nothing. Enum mapping had no human in the loop — this does, by construction.

### What Half B must REFUSE, not guess

- **`Ph.` is the cautionary case, not the easy one.** It could plausibly be a *photo* column.
  Silently guessing puts image URLs into a phone field. This is why confirmation is load-bearing,
  not ceremonial.
- **`Full Name` is not a header problem.** Splitting it is a *data transform*, and there is
  deliberately no name-splitter anywhere in this system. Say so plainly; do not offer a split that
  handles "van der Berg" or "Maria de los Santos" badly. A refusal that names the reason beats a
  guess.

---

## 4. The scope amendment — required, not optional

`REQUIREMENTS.md` Out of Scope says: *"Re-implementing column mapping, phone/email normalization,
verification, or dedupe — these live in n8n and must stay single-source-of-truth."*

Half B touches that line. **Record it as entry 6 in STATE.md's "Accepted requirement amendments"
table**, worded precisely:

> Header-alias **suggestion** with per-header operator confirmation is permitted in the client.
> **Silent client-side column mapping remains excluded.** The backend's `Map Columns` stays the
> single authority on what a header means; the client only helps the operator produce a file the
> backend can read, and never rewrites a header without an explicit yes.

Five amendments already exist in that table with this shape. Do not skip it — a scope line that
moves silently is how the next reader concludes the exclusion never meant anything.

---

## 5. Non-negotiables (learned the hard way, all of them live)

1. **Pin behaviour at the layer the operator reaches.** Drive the CLI as a subprocess against an
   isolated plugin root; unit tests only for pure logic. This plugin shipped a defect in EACH
   direction inside 24 hours (0.6.1 refused where it should degrade; 0.6.2 stopped refusing where
   the skill needed a verdict), and 0.7.2 + 0.7.3 both came from reading ONE caller and
   generalising. Harness to reuse: `tests/test_config_gate.py::_run_cli` (takes `env=`, fake `HOME`).
2. **Never fix a test by making its premise false.** 33-03 seeded a fixture to get past a
   fallthrough; that fallthrough WAS the bug, and seeding hid it for a release. If a test fails in
   a dev checkout, ask whether the environment or the code is wrong before touching the fixture.
3. **Red-check every new test** — revert the fix, confirm it fails, restore.
4. **Commit explicit paths only.** Never `git commit -a`; a parallel process once swept another's
   staged files.
5. **Never touch `~/.claude/plugins/` in tests or scripts.** Real config, live credentials.
6. **Release checklist** (bottom of `operator-claude-plugin/CHANGELOG.md`): bump
   `.claude-plugin/plugin.json` in the **SAME commit** as the CHANGELOG cut → push → refresh the
   marketplace clone (`git -C ~/.claude/plugins/marketplaces/lightning-visuals-operator fetch
   --depth=1 origin master && … reset --hard FETCH_HEAD`). An unbumped version = greyed-out Update
   button. A new version installs to a NEW cache directory — config now migrates itself (0.7.0+),
   so no manual copy is needed.

---

## 6. Backend redeploy (Half A only) — the exact ceremony

```bash
# rebuild the workflow JSON after editing n8n/code/columnMap.js
.venv/bin/python scripts/build_cloud_workflows.py

# disarmed deploy
DRY_RUN=false ALLOW_N8N_DEPLOY=true .venv/bin/python -c "from dotenv import load_dotenv; load_dotenv('.env'); import runpy; runpy.run_path('scripts/deploy_n8n_workflows.py', run_name='__main__')"

# BOUNCE every active workflow — deploy PUTs but never activates, and n8n serves the
# pre-PUT body until a deactivate→activate cycle. Read-backs only prove STORED content.
# (4 active; LV Review Decision is inactive at rest and must STAY inactive.)

# read back
.venv/bin/python -c "from dotenv import load_dotenv; load_dotenv('.env'); import runpy; runpy.run_path('scripts/verify_live_write_safety.py', run_name='__main__')" --expectation disarmed
```

**No arming is needed for this phase.** Header aliases are not a write gate. If you find yourself
reaching for `ENABLE_BAKED_FLAGS`, stop — that is out of scope here.

---

## 7. Test commands (exact forms — the alternatives are broken here)

```bash
.venv/bin/python -m pytest operator-claude-plugin/tests/ -q   # 960 passed, 5 skipped
.venv/bin/python -m pytest -q                                  # 1841 passed, 6 skipped
node --test tests/n8n/*.test.mjs                                # 550 pass (FILE glob only)
grep -c 'ALLOW_HUBSPOT_[A-Z_]* = "true"' n8n/*.json             # must be 0
```

System python lacks the deps. The node directory form is broken on node 24.

---

## 8. Definition of done

1. `e-mail address`, `org.`, `linkedin profile` map, in **both** the YAML and `columnMap.js`,
   pinned equal by a test.
2. `tests/samples/22-messy-headers.csv` previews with those headers mapping; `Ph.` and `Full Name`
   are handled by Half B (suggest / honest refusal), not silently.
3. A test proving **no header is rewritten without confirmation**.
4. STATE.md amendment #6 recorded.
5. UAT 2.2 re-walked by the operator and re-marked. **Do not flip it to PASS yourself** — a
   verified fix and an observed pass are different claims, which is the discipline this whole
   milestone runs on.
6. Suites green, plugin version bumped with the CHANGELOG cut, clone refreshed.

---

## 9. Other open work (do not absorb into this phase)

| Todo | Note |
|---|---|
| `2026-08-04-sweep-crontab-pins-a-versioned-plugin-path` | **major** — crontab pins a versioned path; an update leaves the sweep running stale code or firing nothing. Next after this phase. |
| `2026-08-04-enrichment-throughput-ceiling` | **major** — measured: judge 16.1 s (47%), research 12.1 s (35%), providers <12%. Levers costed; awaiting a decision. |
| `2026-08-03-sweep-lookback-has-no-time-window` | major — repeat notices for a fixed failure |
| RB-10 leftovers | `0.1.0`/`0.6.1` still hold credential copies (scan takes only the newest sibling) |
| UAT | 2.4 + 2.5 need the operator's URL and screenshot; 1.1 needs a re-walk on 0.6.2's changed behaviour; 1.2 + 2.6 marked fixed-awaiting-walk |

---

## 10. First actions on resume

1. Read this file, then
   `.planning/todos/pending/2026-08-04-uat-22-names-aliases-the-mapping-lacks.md`.
2. `git log --oneline -12` — the last commits are 0.7.3 and the session-2 UAT marks.
3. **Write the YAML↔JS alias-equality test FIRST, before changing any alias.** It is the guard the
   rest of Half A depends on, and it should pass against today's two copies.
4. Then `/gsd-plan-phase 34 --ws plugin-entrypoint`.
