#!/usr/bin/env bash
set -eu
root=$(cd "$(dirname "$0")/../.." && pwd)
export PYTHONPATH="$root/remora/src"
cd "$root"
case "${1:-}" in
    --help|-h) echo 'Usage: run-tests.sh [--smoke | PYTEST_ARGS...]'; exit 0 ;;
    --smoke) shift; exec remora/.venv/bin/python -m remora.smoke "$@" ;;
    *) exec remora/.venv/bin/python -m pytest remora/tests "$@" ;;
esac
