#!/bin/bash
# Lightning Visuals — operator plugin installer (macOS, double-click in Finder).
#
# Installs the HubSpot enrichment operator plugin into Claude Code on THIS machine and puts
# the settings file (operator.local.json, sitting next to this script) where the plugin
# looks for it by default. Needs no copy of the source repository. Run once per machine.
#
# What it does, in order:
#   1. checks `claude`, `git`, `python3` are available
#   2. registers the plugin marketplace and installs the plugin (or updates them)
#   3. copies operator.local.json to
#        ~/.claude/plugins/data/operator-claude-plugin-lightning-visuals-operator/operator.local.json
#      (backing up any file already there), permissions 600
#   4. installs the three Python packages the plugin needs (openpyxl, requests, PyYAML)
# It never prints the contents of operator.local.json.
set -euo pipefail

MARKETPLACE_URL="https://github.com/AusGTM/lightning-visuals-n8n.git"
MARKETPLACE_NAME="lightning-visuals-operator"
PLUGIN_NAME="operator-claude-plugin"
PLUGIN_ID="${PLUGIN_NAME}@${MARKETPLACE_NAME}"
DATA_DIR="${CLAUDE_PLUGIN_DATA:-$HOME/.claude/plugins/data/${PLUGIN_NAME}-${MARKETPLACE_NAME}}"
CACHE_DIR="$HOME/.claude/plugins/cache/${MARKETPLACE_NAME}/${PLUGIN_NAME}"

# A double-clicked .command gets a login shell, but be generous about where tools live.
export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

HERE="$(cd "$(dirname "$0")" && pwd)"
SETTINGS_SRC="$HERE/operator.local.json"

step() { printf '\n==> %s\n' "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; printf '\nPress Enter to close.'; read -r _; exit 1; }

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

step "Installing plugin $PLUGIN_ID"
if claude plugin list 2>/dev/null | grep -q "$PLUGIN_NAME"; then
  claude plugin update "$PLUGIN_ID" || echo "  (already installed; update failed or not needed)"
else
  claude plugin install "$PLUGIN_ID"
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

step "Installing Python packages"
REQ="$(ls -d "$CACHE_DIR"/*/ 2>/dev/null | sort -V | tail -1)requirements.txt"
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

step "Done"
cat <<TXT

Installed plugin: $(ls -d "$CACHE_DIR"/*/ 2>/dev/null | sort -V | tail -1)
Settings file:    $TARGET

Next: RESTART Claude Code (skills bind to the installed plugin when a session starts), then say:
  "Is the plugin configured?"    -> expected: already set up
  "What's the backend doing?"    -> read-only status call, proves the connection
TXT
printf '\nPress Enter to close.'; read -r _
