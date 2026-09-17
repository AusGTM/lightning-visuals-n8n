# Operator install bundle

Hand this **folder** to an operator who needs the plugin on their own machine and has no
access to this repository. It is gitignored: `operator.local.json` holds live secrets
(n8n URL, webhook secret, n8n API key) and must never be committed. Only this README and
`install.command` are tracked.

Contents:

| File | Tracked | Purpose |
| --- | --- | --- |
| `install.command` | yes | double-click on macOS: registers the marketplace, installs/updates the plugin, copies the settings file to its default location, installs the Python packages |
| `README.md` | yes | this file |
| `operator.local.json` | **no** | the settings file, copied here from the admin's own working install (`~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/operator.local.json`) |

Refreshing the bundle on the admin machine (never open the file — copy it):

```
cp -p ~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/operator.local.json \
      operator-claude-plugin/install/operator.local.json
```

On the operator's machine: double-click `install.command`, then restart Claude Code. On
another OS, run it with `bash install.command`.

Where the plugin looks for the settings file, first hit wins (see `scripts/durable_paths.py`):
`LV_OPERATOR_CONFIG` env var → `~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/operator.local.json`
→ a legacy copy inside the installed plugin folder. The installer writes the second one, so
every plugin script finds it with no further configuration; this folder is not consulted at
run time and can be deleted after the install.

Prerequisites on the target machine: Claude Code CLI with plugins enabled, `git`, Python 3.
The marketplace is fetched from GitHub over HTTPS.
