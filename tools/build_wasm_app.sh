#!/bin/bash
# Build the quantish app as a static WASM site.
# Usage: build_wasm_app.sh <repo> <outdir>
set -euo pipefail
REPO=${1:?repo dir}
OUT=${2:?output dir}
cd "$REPO"

# 1) fresh wheel of the quantish package
uv build --wheel -q
WHEEL=$(ls -t dist/quantish-*.whl | head -1)

# 2) export both apps (from notebooks/ so the relative css_file
#    resolves), each into its own subdirectory, in two variants: the
#    read-only app view and the full in-browser editor. The site root
#    is a landing page linking to all of them.
(cd notebooks && uv run marimo export html-wasm quantish_app.py -o "$OUT/quantish_app" --mode run -f)
(cd notebooks && uv run marimo export html-wasm double_slit_app.py -o "$OUT/double_slit_app" --mode run -f)
(cd notebooks && uv run marimo export html-wasm quantish_app.py -o "$OUT/quantish_app_edit" --mode edit -f)
(cd notebooks && uv run marimo export html-wasm double_slit_app.py -o "$OUT/double_slit_app_edit" --mode edit -f)
# the exporter pins auto_instantiate off for editable exports; we want
# the notebooks to run on load
python3 - "$OUT/quantish_app_edit/index.html" "$OUT/double_slit_app_edit/index.html" <<'PYPATCH'
import sys
for path in sys.argv[1:]:
    with open(path) as f:
        t = f.read()
    t = t.replace('"auto_instantiate": false', '"auto_instantiate": true')
    with open(path, 'w') as f:
        f.write(t)
PYPATCH

# 3) bundle the wheels (both apps resolve them relative to their own
#    page via mo.notebook_location)
for W in "$OUT"/quantish_app/public/wheels "$OUT"/double_slit_app/public/wheels \
         "$OUT"/quantish_app_edit/public/wheels "$OUT"/double_slit_app_edit/public/wheels; do
  mkdir -p "$W"
  cp "$WHEEL" "$W/"
  if [ ! -f "$W/addict-2.4.0-py3-none-any.whl" ]; then
    curl -sL -o "$W/addict-2.4.0-py3-none-any.whl" \
      "https://files.pythonhosted.org/packages/6a/00/b08f23b7d7e1e14ce01419a467b583edbb93c6cdb8654e54a9cc579cd61f/addict-2.4.0-py3-none-any.whl"
  fi
done

# 4) bundle the model library as a single JSON manifest
python3 - "$OUT" <<'PYEOF'
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])
models = {}
top = Path('models')
for p in sorted(top.rglob('*.yaml')):
    models[str(p.relative_to(top))] = p.read_text()
payload = json.dumps(models)
for app_dir in ('quantish_app', 'quantish_app_edit'):
    (out / app_dir / 'public' / 'models.json').write_text(payload)
print(f'bundled {len(models)} model files')
PYEOF

# 5) the site root: a landing page linking to both apps, a serve
#    script, and a short readme
cat > "$OUT/index.html" <<'HTML'
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Quantish Physics</title>
  <style>
    body { font-family: -apple-system, "Segoe UI", Helvetica, Arial,
           sans-serif; color: #000; background: #fff; max-width: 44em;
           margin: 3em auto; padding: 0 1em; line-height: 1.5; }
    h1 { font-weight: 600; }
    a.app { display: block; border: 1px solid #ccc; border-radius: 8px;
            padding: 1em 1.2em; margin: 1em 0; text-decoration: none;
            color: #000; }
    a.app:hover { border-color: #5c64d1; background: #f6f7ff; }
    a.app b { color: #2b3aa0; }
  </style>
</head>
<body>
  <h1>Quantish Physics</h1>
  <p>Simulations of the &ldquo;quantish&rdquo; universe from Chapter 4
     of <i>Good and Real</i> (Gary L. Drescher). Everything runs in
     your browser &mdash; the first visit downloads the Python runtime
     and may take a minute or two; later visits start in seconds.</p>
  <a class="app" href="quantish_app/">
    <b>Quantish app</b><br>
    Load any figure from the chapter as a live circuit, run it, and
    explore exact weights, probabilities, Monte&nbsp;Carlo sampling,
    and the EPR/Bell experiment.
  </a>
  <a class="app" href="double_slit_app/">
    <b>Double-slit app</b><br>
    The classic double-slit experiment in the quantish framework:
    fire particles, watch fringes build up dot by dot, and see the
    circuits behind each condition.
  </a>
  <p>Each app also comes as an editable notebook: the same simulation
     in the full marimo editor, where you can read the code, change it,
     and re-run cells. Edits run entirely in your browser and affect
     only your copy &mdash; reload to start fresh, or use the editor's
     download button to keep your changes.</p>
  <p><a href="quantish_app_edit/">Quantish app (editable)</a> &middot;
     <a href="double_slit_app_edit/">Double-slit app (editable)</a></p>
</body>
</html>
HTML

cat > "$OUT/serve.sh" <<'SH'
#!/bin/bash
# Serve the quantish WASM apps.
#
# Static files only: no Python code runs on this machine; the quantish
# engine executes in each visitor's browser via Pyodide (WebAssembly).

DEFAULT_PORT=2718

usage() {
  cat <<USAGE
Usage: ./serve.sh [options] [PORT]

Serves the app directory over HTTP. One server covers both apps:

    http://<host>:<port>/                   a landing page linking to all
    http://<host>:<port>/quantish_app/      the quantish app
    http://<host>:<port>/double_slit_app/   the double-slit app
    (plus quantish_app_edit/ and double_slit_app_edit/: the same
    notebooks in the in-browser editor)

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
echo "  landing page:    http://localhost:$PORT/"
echo "  quantish app:    http://localhost:$PORT/quantish_app/"
echo "  double-slit app: http://localhost:$PORT/double_slit_app/"
exec python3 -m http.server --directory "$DIR" "$PORT"
SH
chmod +x "$OUT/serve.sh"

cat > "$OUT/README-wasm.txt" <<'TXT'
Quantish apps, compiled to WebAssembly (static site).

  ./serve.sh [-d DIR] [-p PORT]     # default port 2718

then open  http://<host>:<port>/  in a browser: the root is a landing
page linking to the quantish app (quantish_app/), the double-slit app
(double_slit_app/), and editable-notebook variants of both
(quantish_app_edit/, double_slit_app_edit/). Edits run entirely in the
visitor's browser and affect only their own copy.

Notes:
- Nothing runs server-side: the Python engine executes in the visitor's
  browser via Pyodide. Any static file server works (nginx, Caddy,
  GitHub Pages, python -m http.server).
- First load downloads ~40MB (Pyodide + sympy/scipy/pandas) from CDNs,
  taking a couple of minutes; after browser caching, ~10-15 seconds.
- Rebuilt from the repo with tools/build_wasm_app.sh; the model library
  is frozen into quantish_app/public/models.json at build time.
TXT

echo "site built at $OUT"
