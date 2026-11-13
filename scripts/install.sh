#!/usr/bin/env bash
# Spec2Ship one-command installer (macOS / Linux / Git Bash).
#
#   curl -fsSL https://raw.githubusercontent.com/XuanDuy2309/spec2ship/main/scripts/install.sh | bash
#
# Adds the Harness and Spec2Ship marketplaces, then installs both plugins with the `claude` CLI.
# Safe to re-run. Set SPEC2SHIP_SOURCE to install from a local checkout or fork:
#   SPEC2SHIP_SOURCE=/path/to/spec2ship bash scripts/install.sh
set -euo pipefail

HARNESS_MARKETPLACE_SOURCE="Chachamaru127/claude-code-harness"
HARNESS_MARKETPLACE="claude-code-harness-marketplace"
HARNESS_PLUGIN="harness"   # renamed from "claude-code-harness" upstream
SPEC2SHIP_SOURCE="${SPEC2SHIP_SOURCE:-XuanDuy2309/spec2ship}"
SPEC2SHIP_MARKETPLACE="spec2ship-marketplace"

if ! command -v claude >/dev/null 2>&1; then
  echo 'Claude Code CLI ("claude") was not found on PATH. Install it first: https://code.claude.com/docs' >&2
  exit 1
fi

add_marketplace() {
  local name="$1" source="$2"
  if claude plugin marketplace list 2>/dev/null | grep -qF "$name"; then
    echo "[skip] marketplace $name already added"
  else
    echo "[add ] marketplace $name  <-  $source"
    claude plugin marketplace add "$source"
  fi
}

add_marketplace "$HARNESS_MARKETPLACE" "$HARNESS_MARKETPLACE_SOURCE"
add_marketplace "$SPEC2SHIP_MARKETPLACE" "$SPEC2SHIP_SOURCE"

echo "[inst] ${HARNESS_PLUGIN}@${HARNESS_MARKETPLACE}"
claude plugin install "${HARNESS_PLUGIN}@${HARNESS_MARKETPLACE}"
echo "[inst] spec2ship@${SPEC2SHIP_MARKETPLACE}"
claude plugin install "spec2ship@${SPEC2SHIP_MARKETPLACE}"

echo
echo 'Done. Restart Claude Code, then run: /spec2ship:spec2ship-setup'
echo 'Figma Desktop still needs the figma-mcp-go plugin imported once (see README > Figma setup).'
