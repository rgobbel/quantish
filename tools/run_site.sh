#!/bin/bash
# Run the Quantish Physics site on this machine, for editing and testing.
# Nothing is written outside the repo except, with --wasm, a scratch
# build directory (never ~/Documents/quantish-handoff: that is the
# release's, tools/release.sh).
#
#   tools/run_site.sh            the site run natively by marimo, straight
#                                from the working tree: no build, starts in
#                                seconds. After an edit, stop it (ctrl-C)
#                                and start it again.
#   tools/run_site.sh --edit     the same notebook in marimo's editor
#   tools/run_site.sh --wasm     the site as visitors get it: the static
#                                WASM build (about a minute to build, and
#                                the page takes ~40 s to load), built into
#                                a scratch directory and served from there
#
# Options:
#   -p, --port PORT   port to serve on (default 2741; 2718 is marimo's own
#                     default and 2740 is the preview Claude serves, so
#                     neither is used here)
#   -o, --out DIR     --wasm only: the build directory
#                     (default: $TMPDIR/quantish-site)
#   --no-build        --wasm only: serve the build directory as it is
#   -h, --help        this text
set -euo pipefail
REPO=$(cd "$(dirname "$0")/.." && pwd)
PORT=2741
MODE=run
OUT="${TMPDIR:-/tmp}/quantish-site"
OUT=${OUT//\/\//\/}
BUILD=yes

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help)  sed -n '2,/^set -euo/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//'; exit 0 ;;
    --edit)     MODE=edit; shift ;;
    --wasm)     MODE=wasm; shift ;;
    --no-build) BUILD=no; shift ;;
    -p|--port)  PORT=${2:?--port needs a number}; shift 2 ;;
    -o|--out)   OUT=${2:?--out needs a directory}; shift 2 ;;
    *)          echo "run_site.sh: unknown argument '$1' (see --help)" >&2; exit 2 ;;
  esac
done
case "$PORT" in ''|*[!0-9]*) echo "run_site.sh: port must be a number, got '$PORT'" >&2; exit 2 ;; esac
case "$OUT" in *quantish-handoff*) echo "run_site.sh: $OUT is the release's directory; pick another" >&2; exit 2 ;; esac

# A port already taken gives a page from whatever holds it (a marimo
# server on 127.0.0.1 answers ahead of a static server on the same
# number). An earlier run of this script is simply replaced: that is
# the edit loop. Anything else is left alone, and the script refuses.
for PID in $(lsof -nP -t -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null); do
  CMD=$(ps -o command= -p "$PID")
  case "$CMD" in
    *"quantish_suite_app.py --port $PORT"*|*"python3 - "*" $PORT")
      echo "run_site.sh: replacing the earlier run on port $PORT (pid $PID)"
      kill "$PID"
      for _ in 1 2 3 4 5 6 7 8 9 10; do
        kill -0 "$PID" 2>/dev/null || break
        sleep 0.5
      done ;;
    *)
      echo "run_site.sh: port $PORT is in use by another program:" >&2
      echo "  pid $PID: $CMD" >&2
      echo "stop it, or pick another port with -p" >&2
      exit 1 ;;
  esac
done

cd "$REPO"
if [ "$MODE" = wasm ]; then
  if [ "$BUILD" = yes ]; then
    bash tools/build_wasm_app.sh "$REPO" "$OUT"
  elif [ ! -f "$OUT/index.html" ]; then
    echo "run_site.sh: nothing built at $OUT (drop --no-build)" >&2; exit 1
  fi
  echo
  echo "the site:   http://localhost:$PORT/"
  echo "editable:   http://localhost:$PORT/edit/"
  echo "(ctrl-C stops the server; rerun this script after an edit)"
  # a static server that tells the browser to revalidate every file, so
  # a rebuild is never hidden behind the cached copy of the last one
  exec python3 - "$OUT" "$PORT" <<'PY'
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()

    def log_message(self, *args):   # quiet: the WASM page fetches ~1500 files
        pass


directory, port = sys.argv[1], int(sys.argv[2])
server = ThreadingHTTPServer(('127.0.0.1', port), partial(Handler, directory=directory))
try:
    server.serve_forever()
except KeyboardInterrupt:
    pass
PY
fi

# natively: the suite's stylesheet is generated (gitignored), the two
# apps' stylesheets and the suite's joined, as the build does it
cat notebooks/css/quantish_app.css notebooks/css/double_slit_app.css notebooks/css/suite.css \
    > notebooks/css/quantish_suite_app.css
cd notebooks
if [ "$MODE" = edit ]; then
  exec uv run marimo edit quantish_suite_app.py --port "$PORT"
fi
exec uv run marimo run quantish_suite_app.py --port "$PORT"
