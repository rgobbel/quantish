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

# 2) export the app (from notebooks/ so the relative css_file resolves)
(cd notebooks && uv run marimo export html-wasm quantish_app.py -o "$OUT" --mode run -f)

# 3) bundle the wheels
mkdir -p "$OUT/public/wheels"
cp "$WHEEL" "$OUT/public/wheels/"
if [ ! -f "$OUT/public/wheels/addict-2.4.0-py3-none-any.whl" ]; then
  curl -sL -o "$OUT/public/wheels/addict-2.4.0-py3-none-any.whl" \
    "https://files.pythonhosted.org/packages/6a/00/b08f23b7d7e1e14ce01419a467b583edbb93c6cdb8654e54a9cc579cd61f/addict-2.4.0-py3-none-any.whl"
fi

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
(out / 'public' / 'models.json').write_text(json.dumps(models))
print(f'bundled {len(models)} model files')
PYEOF

echo "site built at $OUT"
