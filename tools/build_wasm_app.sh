#!/bin/bash
# Build the Quantish Physics site (static, WASM).
# Usage: build_wasm_app.sh <repo> <outdir>
set -euo pipefail
REPO=${1:?repo dir}
OUT=${2:?output dir}
cd "$REPO"

# 0) the build stamp: commit (plus '+wip' when the tree has uncommitted
#    changes) and UTC time. It lands under the home section's text
#    (public/version.json) and in version.json at the site root, so a
#    visitor can tell which build they are looking at.
COMMIT=$(git rev-parse --short HEAD)
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  BUILD="$COMMIT+wip"
else
  BUILD="$COMMIT"
fi
BUILT_AT=$(date -u +'%Y-%m-%d %H:%M UTC')
VERSION_JSON=$(printf '{"build": "%s", "commit": "%s", "built_at": "%s"}' \
               "$BUILD" "$COMMIT" "$BUILT_AT")
echo "build $BUILD ($BUILT_AT)"

# 1) fresh wheel of the quantish package
uv build --wheel -q
WHEEL=$(ls -t dist/quantish-*.whl | head -1)

# 2) export the site (from notebooks/ so the relative css_file
#    resolves): the suite notebook, which holds the five apps as its
#    sections, is the site root, and edit/ is the same notebook in the
#    full in-browser editor. Its stylesheet is the two apps' stylesheets
#    and the suite's joined. The layout before 2026-09-16 (one directory
#    per app plus a landing page) is cleared out of the output first.
rm -rf "$OUT"/quantish_app "$OUT"/quantish_app_edit "$OUT"/double_slit_app \
       "$OUT"/double_slit_app_edit "$OUT"/builder_app "$OUT"/builder_app_edit \
       "$OUT"/decoherence_app "$OUT"/decoherence_app_edit \
       "$OUT"/weight_split_app "$OUT"/weight_split_app_edit "$OUT"/suite "$OUT"/suite_edit
cat notebooks/css/quantish_app.css notebooks/css/double_slit_app.css notebooks/css/suite.css > notebooks/css/quantish_suite_app.css
(cd notebooks && uv run marimo export html-wasm quantish_suite_app.py -o "$OUT" --mode run -f)
(cd notebooks && uv run marimo export html-wasm quantish_suite_app.py -o "$OUT/edit" --mode edit -f)
# Two config patches on the exported pages. The exporter pins
# auto_instantiate off for editable exports; we want the notebooks to
# run on load. And it bakes in theme "system", which hands dark-mode
# visitors marimo's dark theme under stylesheets tuned for the light
# one — pin every app to light.
python3 - "$OUT"/index.html "$OUT"/edit/index.html <<'PYPATCH'
import os
import sys
for path in sys.argv[1:]:
    with open(path) as f:
        t = f.read()
    t = t.replace('"theme": "system"', '"theme": "light"')
    if os.path.basename(os.path.dirname(path)) == 'edit':
        t = t.replace('"auto_instantiate": false', '"auto_instantiate": true')
    with open(path, 'w') as f:
        f.write(t)
PYPATCH

# 3) bundle the wheels (the page resolves them relative to itself via
#    mo.notebook_location)
for W in "$OUT"/public/wheels "$OUT"/edit/public/wheels; do
  mkdir -p "$W"
  cp "$WHEEL" "$W/"
  if [ ! -f "$W/addict-2.4.0-py3-none-any.whl" ]; then
    curl -sL -o "$W/addict-2.4.0-py3-none-any.whl" \
      "https://files.pythonhosted.org/packages/6a/00/b08f23b7d7e1e14ce01419a467b583edbb93c6cdb8654e54a9cc579cd61f/addict-2.4.0-py3-none-any.whl"
  fi
done

# 3b) the build stamp beside each page, and at the site root
for D in "$OUT" "$OUT"/edit; do
  echo "$VERSION_JSON" > "$D/public/version.json"
done
# the suite embeds the five notebooks: it fetches them from its page
for D in "$OUT" "$OUT"/edit; do
  mkdir -p "$D/public/notebooks"
  cp notebooks/weight_split_app.py notebooks/double_slit_app.py notebooks/quantish_app.py \
     notebooks/network_builder_app.py notebooks/decoherence_app.py "$D/public/notebooks/"
  # ...and the sections' texts (notebooks/text/*.md)
  mkdir -p "$D/public/text"
  cp notebooks/text/*.md "$D/public/text/"
done
echo "$VERSION_JSON" > "$OUT/version.json"

# 3c) Cloudflare Pages headers: every file revalidates on each visit
#     (ETag round trips, not re-downloads), so a fresh deploy is never
#     hidden behind a phone's cached copy of the previous one
cat > "$OUT/_headers" <<'HDR'
/*
  Cache-Control: no-cache
HDR

# 4) bundle the model library as a single JSON manifest
python3 - "$OUT" <<'PYEOF'
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
models = {}
top = Path('models')
for p in sorted(top.rglob('*.yaml')):
    # personal scratch models, editor droppings, and the schema are
    # not part of the shipped library
    if p.name.startswith(('.', '#')) or p.name in ('schema.yaml',
                                                   'my_network.yaml') \
            or 'uploads' in p.parts:
        continue
    models[str(p.relative_to(top))] = p.read_text()
payload = json.dumps(models)
for app_dir in ('.', 'edit'):
    (out / app_dir / 'public' / 'models.json').write_text(payload)
print(f'bundled {len(models)} model files')
PYEOF

# 5) a serve script and a short readme
cat > "$OUT/serve.sh" <<'SH'
#!/bin/bash
# Serve the Quantish Physics site.
#
# Static files only: no Python code runs on this machine; the quantish
# engine executes in each visitor's browser via Pyodide (WebAssembly).

DEFAULT_PORT=2718

usage() {
  cat <<USAGE
Usage: ./serve.sh [options] [PORT]

Serves the site directory over HTTP:

    http://<host>:<port>/        the site
    http://<host>:<port>/edit/   the same notebook in the in-browser editor

Options:
  -d, --directory DIR   directory to serve
                        (default: the directory containing this script)
  -p, --port PORT       port to listen on; a bare number works too:
                        ./serve.sh 8080  (default: $DEFAULT_PORT)
  -h, --help            show this message and exit

Nothing runs server-side, so any static file server can substitute for
this script (nginx, Caddy, GitHub Pages, python3 -m http.server ...).
USAGE
}

DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=$DEFAULT_PORT

need_value() {
  case "${2-}" in
    ''|-*)
      echo "error: $1 requires a value (see --help)" >&2
      exit 2 ;;
  esac
}

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help)      usage; exit 0 ;;
    -d|--directory) need_value "$1" "${2-}"; DIR="$2"; shift 2 ;;
    --directory=*)  DIR="${1#*=}"; shift ;;
    -p|--port)      need_value "$1" "${2-}"; PORT="$2"; shift 2 ;;
    --port=*)       PORT="${1#*=}"; shift ;;
    -*)             echo "error: unknown option '$1' (see --help)" >&2; exit 2 ;;
    *)              PORT="$1"; shift ;;
  esac
done

case "$PORT" in
  ''|*[!0-9]*) echo "error: port must be a number, got '$PORT'" >&2; exit 2 ;;
esac
if [ ! -d "$DIR" ]; then
  echo "error: no such directory: $DIR" >&2
  exit 2
fi

echo "Serving $DIR"
echo "  the site:   http://localhost:$PORT/"
echo "  editable:   http://localhost:$PORT/edit/"
exec python3 -m http.server --directory "$DIR" "$PORT"
SH
chmod +x "$OUT/serve.sh"

cat > "$OUT/README-wasm.txt" <<'TXT'
Quantish Physics, compiled to WebAssembly (static site).

  ./serve.sh [-d DIR] [-p PORT]     # default port 2718

then open  http://<host>:<port>/  in a browser: the site is one page
with its sections (the Weight-split Explorer, the double-slit
experiment, the book's figures, the network builder, the decoherence
lab), and edit/ is the same notebook in the in-browser editor. Edits run entirely in the visitor's browser and affect only
their own copy.

Notes:
- Nothing runs server-side: the Python engine executes in the visitor's
  browser via Pyodide. Any static file server works (nginx, Caddy,
  GitHub Pages, python -m http.server).
- First load downloads ~30MB (Pyodide + sympy/scipy) from CDNs,
  taking a couple of minutes; after browser caching, ~10-15 seconds.
- Rebuilt from the repo with tools/build_wasm_app.sh; the model library
  is frozen into public/models.json at build time.
TXT

echo "site built at $OUT"
