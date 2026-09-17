#!/bin/bash
# Release the Quantish Physics site: build the production dir, refresh
# the two handoff tarballs, deploy to Cloudflare Pages (quantish.pages.dev).
# Usage: tools/release.sh   (from anywhere; commit and push first)
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
HANDOFF=~/Documents/quantish-handoff
SITE=$HANDOFF/quantish-wasm-site
export PATH=/opt/homebrew/bin:$PATH   # node/npx for wrangler (PyCharm's PATH may lack it)
cd "$REPO"

# a release is a commit: refuse a dirty tree (the stamp would read +wip)
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "release.sh: uncommitted changes; commit (and push) first" >&2
  exit 1
fi
# ...and warn (not stop) if HEAD is not on origin/main yet
git fetch -q origin main || true
if ! git merge-base --is-ancestor HEAD origin/main 2>/dev/null; then
  echo "release.sh: note: HEAD is not pushed to origin/main yet" >&2
fi

# 1) the production build
bash tools/build_wasm_app.sh "$REPO" "$SITE"

# 2) the handoff tarballs (the site dir; the source as a git archive of HEAD)
tar -czf "$HANDOFF/quantish-wasm-site.tar.gz" -C "$HANDOFF" quantish-wasm-site
git archive HEAD --prefix=quantish/ -o "$HANDOFF/quantish.tar.gz"

# 3) deploy
npx wrangler pages deploy "$SITE" --project-name quantish
echo "released $(cat "$SITE/version.json")"
