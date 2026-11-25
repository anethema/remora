#!/usr/bin/env bash
set -eu
root=$(cd "$(dirname "$0")/../.." && pwd)
export PYTHONPATH="$root/remora/src"
exec "$root/remora/.venv/bin/python" -m remora.server "$@"
