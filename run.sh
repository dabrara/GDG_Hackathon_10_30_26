#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
command -v ollama >/dev/null || { echo "Install Ollama first, then rerun this script."; exit 1; }
ollama --version
if ! ollama list >/dev/null 2>&1; then
  echo "Ollama is not running. Start 'ollama serve' in another terminal, then retry."
  exit 1
fi
if [[ -n "${MODEL:-}" ]]; then
  [[ "$MODEL" =~ ^gemma(2|3|3n|4)?:[a-z0-9._-]+$ && "$MODEL" != *cloud* ]] || {
    echo "MODEL must be a local Gemma tag, for example gemma4:e4b, gemma3n:e4b, gemma3:12b or gemma2:9b."; exit 1;
  }
  SELECTED_MODEL="$MODEL"
else
  SELECTED_MODEL="$(python3 scripts/select_model.py --model-only)"
  echo "Selected $SELECTED_MODEL based on detected system RAM."
fi
ollama pull "$SELECTED_MODEL"
export MODEL="$SELECTED_MODEL"
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/make_samples.py
printf '
Open http://localhost:8000
'
exec uvicorn app.main:app --host "${HOST:-127.0.0.1}" --port "${PORT:-8000}"
