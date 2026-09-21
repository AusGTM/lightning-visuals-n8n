#!/bin/bash
# Lightning Visuals — operator plugin installer.
#
# Run from Terminal (no double-click, no admin rights, no Gatekeeper prompt):
#
#     cd <this folder>
#     bash install.sh
#
# Installs (or updates) the HubSpot enrichment operator plugin into Claude Code on THIS
# machine, puts the settings file (operator.local.json, next to this script) where the plugin
# looks for it, removes stale plugin versions so a session cannot bind to an old one, and
# allowlists the plugin's own script commands so Claude stops asking before each one.
# Needs no copy of the source repository. Safe to re-run.
#
# What it does, in order:
#   1. checks `claude`, `git`, `python3` are on PATH
#   2. registers the plugin marketplace and installs or updates the plugin
#   3. copies operator.local.json to
#        ~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/operator.local.json
#      (backing up any different file already there), permissions 600
#   4. installs the three Python packages the plugin needs (openpyxl, requests, PyYAML)
#   5. SWEEP: deletes every plugin version folder under ~/.claude/plugins/cache/... that is
#      NOT the one Claude Code's own registry says is installed. It never touches the
#      settings folder above, and it deletes nothing if the registry cannot be read.
#   6. adds "Bash(python3 scripts/*)" to permissions.allow in ~/.claude/settings.json
#      (backing the file up first; nothing else in that file is changed)
#
# It never prints the contents of operator.local.json, and it never sets ALLOW_N8N_ARM:
# that variable is the headless/cron authority only — the interactive path is authorised by
# allow_write_grants inside operator.local.json, which the admin sets in that file.
set -euo pipefail

MARKETPLACE_URL="https://github.com/AusGTM/lightning-visuals-n8n.git"
MARKETPLACE_NAME="lightning-visuals-operator"
PLUGIN_NAME="operator-claude-plugin"
PLUGIN_ID="${PLUGIN_NAME}@${MARKETPLACE_NAME}"
DATA_DIR="${CLAUDE_PLUGIN_DATA:-$HOME/.claude/plugins/data/${PLUGIN_NAME}-${MARKETPLACE_NAME}}"
CACHE_DIR="$HOME/.claude/plugins/cache/${MARKETPLACE_NAME}/${PLUGIN_NAME}"
CLONE_DIR="$HOME/.claude/plugins/marketplaces/${MARKETPLACE_NAME}"
SETTINGS_JSON="$HOME/.claude/settings.json"
PERMISSION_RULE="Bash(python3 scripts/*)"

# Desktop installs of `claude` commonly live in ~/.local/bin; be generous about PATH.
export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

HERE="$(cd "$(dirname "$0")" && pwd)"
SETTINGS_SRC="$HERE/operator.local.json"

step() { printf '\n==> %s\n' "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

# The plugin version Claude Code's OWN registry says is installed — never "newest folder".
# A stale registry pointing at an old folder is exactly the confusion the sweep removes.
installed_path() {
  claude plugin list --json 2>/dev/null | python3 -c '
import json, sys
for p in json.load(sys.stdin):
    if p.get("id") == sys.argv[1]:
        print(p.get("installPath", "")); break
' "$PLUGIN_ID" 2>/dev/null || true
}

step "Checking prerequisites"
for tool in claude git python3; do
  command -v "$tool" >/dev/null 2>&1 || fail "'$tool' is not on PATH. Install it, then run this again. (claude: https://claude.com/claude-code)"
  printf '  %s: %s\n' "$tool" "$(command -v "$tool")"
done
[ -f "$SETTINGS_SRC" ] || fail "operator.local.json is missing next to this script ($HERE). Ask your admin for the bundle again."

step "Registering marketplace $MARKETPLACE_NAME"
if claude plugin marketplace list 2>/dev/null | grep -q "$MARKETPLACE_NAME"; then
  claude plugin marketplace update "$MARKETPLACE_NAME" || echo "  (marketplace update failed — continuing with the local copy)"
else
  claude plugin marketplace add "$MARKETPLACE_URL"
fi

step "Placing settings file"
mkdir -p "$DATA_DIR"
chmod 700 "$DATA_DIR" 2>/dev/null || true
TARGET="$DATA_DIR/operator.local.json"
if [ -f "$TARGET" ]; then
  if cmp -s "$SETTINGS_SRC" "$TARGET"; then
    echo "  identical file already in place — nothing to do"
  else
    BACKUP="$TARGET.bak-$(date +%Y%m%dT%H%M%S)"
    cp -p "$TARGET" "$BACKUP"; chmod 600 "$BACKUP"
    echo "  existing file backed up to $(basename "$BACKUP")"
    cp "$SETTINGS_SRC" "$TARGET"
  fi
else
  cp "$SETTINGS_SRC" "$TARGET"
fi
chmod 600 "$TARGET"
echo "  settings at: $TARGET"

step "Installing plugin $PLUGIN_ID"
if claude plugin list 2>/dev/null | grep -q "$PLUGIN_NAME"; then
  claude plugin update "$PLUGIN_ID" || echo "  (already installed; update failed or not needed)"
else
  claude plugin install "$PLUGIN_ID"
fi
INSTALLED="$(installed_path)"
[ -n "$INSTALLED" ] && [ -d "$INSTALLED" ] || fail "Claude Code's registry does not show $PLUGIN_ID installed. Run 'claude plugin list' and check."
INSTALLED_VERSION="$(basename "$INSTALLED")"
echo "  installed: $INSTALLED_VERSION ($INSTALLED)"

# Loud mismatch check: the version the marketplace clone offers vs the one installed.
CLONE_VERSION="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["version"])' "$CLONE_DIR/$PLUGIN_NAME/.claude-plugin/plugin.json" 2>/dev/null || true)"
if [ -n "$CLONE_VERSION" ] && [ "$CLONE_VERSION" != "$INSTALLED_VERSION" ]; then
  echo "  WARNING: marketplace offers $CLONE_VERSION but $INSTALLED_VERSION is installed — run this script again; if it persists, tell your admin."
fi

step "Installing Python packages"
REQ="$INSTALLED/requirements.txt"
if [ -f "$REQ" ]; then
  python3 -m pip install --quiet --user -r "$REQ" || python3 -m pip install --quiet --user --break-system-packages -r "$REQ" || echo "  (pip install failed — install openpyxl, requests, PyYAML by hand)"
else
  python3 -m pip install --quiet --user openpyxl requests PyYAML || python3 -m pip install --quiet --user --break-system-packages openpyxl requests PyYAML || echo "  (pip install failed — install openpyxl, requests, PyYAML by hand)"
fi
python3 - <<'PY' || fail "a Python package is still missing (see above)"
import importlib
for m in ("openpyxl", "requests", "yaml"):
    importlib.import_module(m)
print("  openpyxl, requests, PyYAML import OK")
PY

step "Sweeping stale plugin versions"
# First Claude Code's own cleanup of versions it already marked orphaned (docs: otherwise
# they linger ~14 days), then the belt-and-braces sweep below for anything it did not mark.
claude plugin prune --force >/dev/null 2>&1 || true
# Only sibling version folders of the INSTALLED one, under the plugin's own cache dir.
# The settings folder ($DATA_DIR) and Claude Code's registry are never touched.
SWEPT=0
if [ -d "$CACHE_DIR" ]; then
  for d in "$CACHE_DIR"/*/; do
    [ -d "$d" ] || continue
    d="${d%/}"
    case "$d" in
      "$CACHE_DIR"/*) ;;
      *) continue ;;
    esac
    if [ "$d" != "$INSTALLED" ]; then
      rm -rf "$d" && echo "  removed $(basename "$d")" && SWEPT=$((SWEPT + 1))
    fi
  done
fi
echo "  $SWEPT stale version folder(s) removed; keeping $INSTALLED_VERSION"

step "Allowlisting the plugin's script commands in Claude Code"
python3 - "$SETTINGS_JSON" "$PERMISSION_RULE" <<'PY' || echo "  (could not update settings.json — add the rule by hand, see USAGE.md 'Fewer permission prompts')"
import json, os, shutil, sys, time
path, rule = sys.argv[1], sys.argv[2]
data = {}
if os.path.exists(path):
    with open(path) as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise SystemExit("settings.json is not a JSON object")
perms = data.setdefault("permissions", {})
allow = perms.setdefault("allow", [])
if rule in allow:
    print("  rule already present: %s" % rule)
else:
    if os.path.exists(path):
        backup = "%s.bak-%s" % (path, time.strftime("%Y%m%dT%H%M%S"))
        shutil.copy2(path, backup)
        print("  settings.json backed up to %s" % os.path.basename(backup))
    allow.append(rule)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp, path)
    print("  added to permissions.allow: %s" % rule)
PY

step "Done"
cat <<TXT

Installed plugin: $INSTALLED_VERSION
Settings file:    $TARGET

Next: RESTART Claude Code (skills bind to the installed plugin when a session starts), then say:
  "Is the plugin configured?"    -> expected: already set up
  "What's the backend doing?"    -> read-only status call, proves the connection
TXT
