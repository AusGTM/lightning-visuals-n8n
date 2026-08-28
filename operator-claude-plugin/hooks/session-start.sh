#!/usr/bin/env bash
# D-59-06 (2026-08-28): this note exists INSTEAD OF a revocation-aware, chunk-granular
# dispatch loop. The alternative would change the shared dispatch loop every lane in
# this plugin uses; telling the operator the true behaviour once, before any send, is
# the cheap and honest version. Full rationale:
# .planning/phases/59-frictionless-write-path/59-CONTEXT.md, decision D-59-06.
#
# This script has NO dependencies: no config read, no credential read, no network call,
# no filesystem write, no reading of grant state. It must exit 0 unconditionally, so the
# note still appears on a fresh, unconfigured install.
set -eu

cat <<'NOTE'
Relay the following to the operator once, near the start of this session, in your own
words, without asking anything and without waiting on a reply — this is background
information for the decision to begin, not a prompt.

Once enrichment and writing to HubSpot start for a batch, the run continues until it is
done. Revoking a write grant refuses the NEXT send. A dispatch that is already running
finishes its remaining chunks; a revoke arriving mid-run does not stop it.

This is information, not a decision — nothing here is waiting on the operator.
NOTE
