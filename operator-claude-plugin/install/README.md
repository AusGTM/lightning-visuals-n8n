# Operator install bundle

Hand this **folder** to an operator who needs the plugin on their own machine and has no
access to this repository. It is gitignored: `operator.local.json` holds live secrets
(n8n URL, webhook secret, n8n API key) and must never be committed. Only this README and
`install.sh` are tracked.

Contents:

| File | Tracked | Purpose |
| --- | --- | --- |
| `install.sh` | yes | run with `bash install.sh` from Terminal: registers the marketplace, installs/updates the plugin, copies the settings file to its default location, installs the Python packages, removes stale plugin versions, allowlists the plugin's script commands in `~/.claude/settings.json` |
| `README.md` | yes | this file |
| `operator.local.json` | **no** | the settings file, copied here from the admin's own working install (`~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/operator.local.json`) |

Refreshing the bundle on the admin machine (never open the file — copy it):

```
cp -p ~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/operator.local.json \
      operator-claude-plugin/install/operator.local.json
```

On the operator's machine, open Terminal and run:

```
cd <the folder this README is in>
bash install.sh
```

then restart Claude Code. No double-click: a downloaded `.command` file is blocked by macOS
Gatekeeper for a user who cannot grant the "open anyway" permission, so the installer is a
plain script run through `bash`, which needs no executable bit, no quarantine removal and
no admin rights. Works the same on Linux.

**Stale versions.** Claude Code keeps every previously installed plugin version under
`~/.claude/plugins/cache/lightning-visuals-operator/operator-claude-plugin/<version>/`, and a
session binds to whichever one its registry points at when it starts. The installer runs
`claude plugin prune --force`, then deletes every version folder that is not the one
`claude plugin list --json` reports as installed. It deletes nothing if that registry read
fails, and it never touches the settings folder.

**Environment variables — none are needed, and one is deliberately not set.** The plugin
finds its settings at the durable path below with no variable set. `LV_OPERATOR_CONFIG`
is an admin escape hatch only. `ALLOW_N8N_ARM` is the authority for the headless/cron
paths and is NOT written anywhere persistent by this installer: a copy in
`~/.claude/settings.json`'s `env` would pre-authorise every desktop session and bypass the
grant chain. The interactive path is authorised by `allow_write_grants: true` inside
`operator.local.json` — which the admin sets in the file before bundling it.

What the installer does write persistently is one permission rule, so Claude stops asking
before each plugin script: `"Bash(python3 scripts/*)"` appended to `permissions.allow` in
`~/.claude/settings.json` (backed up first; no other key touched).

Where the plugin looks for the settings file, first hit wins (see `scripts/durable_paths.py`):
`LV_OPERATOR_CONFIG` env var → `~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/operator.local.json`
→ a legacy copy inside the installed plugin folder. The installer writes the second one, so
every plugin script finds it with no further configuration; this folder is not consulted at
run time and can be deleted after the install.

Prerequisites on the target machine: Claude Code CLI with plugins enabled, `git`, Python 3.
The marketplace is fetched from GitHub over HTTPS.
