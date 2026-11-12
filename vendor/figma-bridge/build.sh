#!/usr/bin/env bash
# Rebuild the Spec2Ship read-only Figma bridge from the vendored source.
# Maintainer tool only: it downloads npm build dependencies (never at plugin runtime).
# Package install scripts are disabled (--ignore-scripts).
#
#   bash vendor/figma-bridge/build.sh            # server bundle + Figma plugin
#   bash vendor/figma-bridge/build.sh server     # server bundle only
#   bash vendor/figma-bridge/build.sh plugin     # Figma plugin only
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
WHAT="${1:-all}"
ESBUILD_VERSION="0.24.2"

install_deps() {
  if [ -f package-lock.json ]; then
    npm ci --ignore-scripts --no-audit --no-fund
  else
    npm install --ignore-scripts --no-audit --no-fund
  fi
}

build_server() {
  echo "== server =="
  cd "$HERE/server"
  install_deps
  npx --no-install tsc --noEmit -p .
  npm install --no-save --ignore-scripts --no-audit --no-fund "esbuild@${ESBUILD_VERSION}"
  npx --no-install esbuild src/index.ts --bundle --platform=node --format=esm --target=node20 \
    --outfile="$HERE/dist/server.mjs" \
    --banner:js="import { createRequire as __s2sCreateRequire } from 'node:module'; const require = __s2sCreateRequire(import.meta.url);"
}

build_plugin() {
  echo "== Figma plugin =="
  cd "$HERE/plugin"
  install_deps
  npx --no-install tsc --noEmit -p .
  npm run build
  grep -q "Spec2Ship read-only" dist/code.js || { echo "read-only guard missing from dist/code.js" >&2; exit 1; }
  grep -q "ws://localhost:3994/ws" dist/index.html || { echo "plugin UI is not pointed at port 3994" >&2; exit 1; }
}

case "$WHAT" in
  server) build_server ;;
  plugin) build_plugin ;;
  all) build_server; build_plugin ;;
  *) echo "usage: build.sh [all|server|plugin]" >&2; exit 2 ;;
esac

cd "$HERE"
echo "== sha256 =="
for f in dist/server.mjs plugin/dist/code.js plugin/dist/index.html; do
  [ -f "$f" ] && sha256sum "$f"
done
echo "Update the hashes in vendor/figma-bridge/UPSTREAM.md, then run the Spec2Ship tests."
