#!/usr/bin/env bash
# One-command setup for Spec2Ship on macOS / Linux: checks every prerequisite and installs only what is missing.
#
#   bash install/install.sh              # check, then ask before each install
#   bash install/install.sh --yes        # accept every install
#   bash install/install.sh --check-only # report only
#
# Checks: Claude Code CLI, Git, Python 3.9+, Node.js 20+ (bundled Figma bridge), pypdf (optional), Figma Desktop
# (optional, macOS), the claude-code-harness plugin and the Spec2Ship plugin. Uses Homebrew (macOS) or apt/dnf
# (Linux). Nothing is downloaded unless you confirm. The script never reads .env files or secrets.
set -uo pipefail
YES=0; CHECK_ONLY=0
for a in "$@"; do
  case "$a" in
    --yes|-y) YES=1 ;;
    --check-only) CHECK_ONLY=1 ;;
    *) echo "unknown option: $a" >&2; exit 2 ;;
  esac
done
MARKETPLACE="hthai1523/spec2ship"
HARNESS_MARKETPLACE="Chachamaru127/claude-code-harness"
TODO=()

say() { printf '[%-9s] %s: %s\n' "$1" "$2" "$3"; }
has() { command -v "$1" >/dev/null 2>&1; }
confirm() {
  [ "$CHECK_ONLY" = 1 ] && return 1
  [ "$YES" = 1 ] && return 0
  read -r -p "$1 [y/N] " ans </dev/tty || return 1
  [[ "$ans" =~ ^([yY]|yes|c|co)$ ]]
}
pkg_install() {  # $1 label, $2 brew formula, $3 apt package, $4 dnf package
  local label="$1"
  if [ "$(uname)" = "Darwin" ]; then
    has brew || { say FAILED "$label" "Homebrew not found (https://brew.sh); install $label manually"; TODO+=("$label"); return 1; }
    confirm "Install $label with Homebrew (brew install $2)?" || { say SKIPPED "$label" "brew install $2"; TODO+=("$label"); return 1; }
    brew install $2
  elif has apt-get; then
    confirm "Install $label with apt (sudo apt-get install -y $3)?" || { say SKIPPED "$label" "sudo apt-get install -y $3"; TODO+=("$label"); return 1; }
    sudo apt-get update -y && sudo apt-get install -y $3
  elif has dnf; then
    confirm "Install $label with dnf (sudo dnf install -y $4)?" || { say SKIPPED "$label" "sudo dnf install -y $4"; TODO+=("$label"); return 1; }
    sudo dnf install -y $4
  else
    say FAILED "$label" "no supported package manager; install $label manually"; TODO+=("$label"); return 1
  fi
}
major() { echo "$1" | sed -E 's/[^0-9]*([0-9]+).*/\1/'; }

echo "Spec2Ship setup ($(uname))"
echo

if has claude; then say OK "Claude Code" "$(claude --version 2>&1 | head -1)"
else say MISSING "Claude Code" "install it first: https://claude.com/claude-code"; TODO+=("Claude Code"); fi

if has git; then say OK "Git" "$(git --version)"
else pkg_install "Git" git git git && say INSTALLED "Git" "$(git --version)"; fi

PY=""
for c in python3 python; do
  if has "$c" && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then PY="$c"; break; fi
done
if [ -n "$PY" ]; then say OK "Python 3.9+" "$($PY --version 2>&1)"
else pkg_install "Python 3.9+" python@3.12 python3 python3 && PY=python3 && say INSTALLED "Python 3.9+" "$(python3 --version 2>&1)"; fi

if has node && [ "$(major "$(node --version)")" -ge 20 ]; then say OK "Node.js 20+" "$(node --version)"
else pkg_install "Node.js 20+" node nodejs nodejs && say INSTALLED "Node.js 20+" "$(node --version 2>/dev/null)"; fi

if [ -n "$PY" ]; then
  if "$PY" -c 'import pypdf' 2>/dev/null; then say OK "pypdf (optional)" "installed"
  elif confirm "Install pypdf for better PDF extraction ($PY -m pip install --user pypdf)?"; then
    "$PY" -m pip install --user pypdf && say INSTALLED "pypdf (optional)" "pypdf"
  else say SKIPPED "pypdf (optional)" "$PY -m pip install --user pypdf"; fi
fi

if [ "$(uname)" = "Darwin" ]; then
  if [ -d "/Applications/Figma.app" ]; then say OK "Figma Desktop (optional)" "/Applications/Figma.app"
  elif confirm "Install Figma Desktop (brew install --cask figma)?"; then brew install --cask figma && say INSTALLED "Figma Desktop (optional)" "Figma.app"
  else say SKIPPED "Figma Desktop (optional)" "brew install --cask figma"; fi
else
  say SKIPPED "Figma Desktop (optional)" "Figma Desktop is macOS/Windows only; the design capture needs it"
fi

if has claude; then
  PLUGINS="$(claude plugin list 2>&1)"
  if echo "$PLUGINS" | grep -q "claude-code-harness"; then say OK "claude-code-harness plugin" "installed"
  elif confirm "Install the claude-code-harness plugin?"; then
    claude plugin marketplace add "$HARNESS_MARKETPLACE" && claude plugin install "claude-code-harness@claude-code-harness-marketplace" \
      && say INSTALLED "claude-code-harness plugin" "installed" || { say FAILED "claude-code-harness plugin" "see output above"; TODO+=("claude-code-harness plugin"); }
  else say SKIPPED "claude-code-harness plugin" "/plugin install claude-code-harness@claude-code-harness-marketplace"; TODO+=("claude-code-harness plugin"); fi

  if echo "$PLUGINS" | grep -q "spec2ship@"; then say OK "Spec2Ship plugin" "installed (update: claude plugin update spec2ship@spec2ship-marketplace)"
  elif confirm "Install the Spec2Ship plugin?"; then
    claude plugin marketplace add "$MARKETPLACE" && claude plugin install "spec2ship@spec2ship-marketplace" \
      && say INSTALLED "Spec2Ship plugin" "installed" || { say FAILED "Spec2Ship plugin" "see output above"; TODO+=("Spec2Ship plugin"); }
  else say SKIPPED "Spec2Ship plugin" "/plugin install spec2ship@spec2ship-marketplace"; TODO+=("Spec2Ship plugin"); fi
fi

echo
if [ ${#TODO[@]} -eq 0 ]; then
  echo "Ready. Restart Claude Code, then run /spec2ship:spec2ship-setup inside your project."
else
  echo "Still missing:"; for t in "${TODO[@]}"; do echo "  - $t"; done
fi
echo
echo "Figma (once per machine, manual): Figma Desktop > Plugins > Development > Import plugin from manifest >"
echo "  <Spec2Ship plugin folder>/vendor/figma-bridge/plugin/manifest.json"
echo "  (/spec2ship:spec2ship-setup prints the exact path), then run 'Spec2Ship Figma Bridge (read-only)' in your design file."
[ ${#TODO[@]} -eq 0 ]
