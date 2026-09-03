#!/usr/bin/env bash
# D-59-06 (2026-08-28): this note exists INSTEAD OF a revocation-aware, chunk-granular
# dispatch loop. The alternative would change the shared dispatch loop every lane in
# this plugin uses; telling the operator the true behaviour once, before any send, is
# the cheap and honest version. Full rationale:
# .planning/phases/59-frictionless-write-path/59-CONTEXT.md, decision D-59-06.
#
# Second note added 2026-09-04 (operator request): the permission-prompt disclosure. Every
# skill in this plugin does its work by running `python3 scripts/...` through Bash, so in
# the default permission mode the operator is prompted repeatedly during one ordinary task.
# Disclosed at session start rather than mid-task, because the moment to weigh it is before
# a batch is underway, not while approving the fourth prompt of one. The note deliberately
# presents the settings allowlist FIRST and states what bypass does NOT change: an operator
# who flips bypass could otherwise reasonably conclude they have just removed the safeguard
# standing between them and a live HubSpot write. They have not -- the write path is gated
# by the write-grant switch in the operator's settings file, by the grant itself, and by
# record-scoped arming -- none of which is a Claude permission prompt.
#
# This script has NO dependencies: no config read, no credential read, no network call,
# no filesystem write, no reading of grant state. It must exit 0 unconditionally, so the
# note still appears on a fresh, unconfigured install. Keep it that way -- the second note
# must NOT start inspecting the operator's settings to decide whether to print.
set -eu

cat <<'NOTE'
Relay the following to the operator once, near the start of this session, in your own
words, without asking anything and without waiting on a reply — this is background
information for the decision to begin, not a prompt.

Once enrichment and writing to HubSpot start for a batch, the run continues until it is
done. Revoking a write grant refuses the NEXT send. A dispatch that is already running
finishes its remaining chunks; a revoke arriving mid-run does not stop it.

This is information, not a decision — nothing here is waiting on the operator.

Also relay, once, in the same way: every task in this plugin works by running local
Python scripts, so in Claude Code's default permission mode the operator is asked to
approve each one — several times during a single ordinary batch. Two ways to stop that,
and they are NOT equivalent:

- Allowlist just these commands, in ~/.claude/settings.json under permissions.allow. It
  removes the prompting for this plugin's own scripts and leaves every other prompt in
  place. This is the one to prefer.
- Bypass permissions mode. It stops the prompting, but for the WHOLE session, not just
  this plugin — anything else run in that session also proceeds unprompted.

What neither changes: whether HubSpot can be written to. That is gated by the
write-grant switch an admin sets in the operator's settings file, by the grant they open
for a named batch, and by an arming window scoped to that send's records. A Claude permission
prompt is not part of that chain, so turning the prompts off does not loosen it, and
leaving them on does not protect against a write the operator has approved.

This is information, not a decision — nothing here is waiting on the operator.
NOTE
