#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
export PYTHONPATH="$root/remora/src"
export GRADIO_ANALYTICS_ENABLED=False
case "${1:-}" in
  --stop|--url|--help|-h) exec "$root/remora/.venv/bin/python" -m remora.share "$@" ;;
esac
export PATH="$HOME/.local/bin:$PATH"
exec uv run --no-project --python "$root/remora/.venv/bin/python" \
    --with-requirements "$root/remora/share-requirements.txt" python -m remora.share "$@"
