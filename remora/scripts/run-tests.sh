#!/usr/bin/env bash
set -eu
root=$(cd "$(dirname "$0")/../.." && pwd)
export PYTHONPATH="$root/remora/src"
cd "$root"
case "${1:-}" in
    --help|-h) echo 'Usage: run-tests.sh [--smoke | --recovery | PYTEST_ARGS...]'; exit 0 ;;
    --recovery) shift; exec remora/.venv/bin/python -m pytest -s remora/tests/live_recovery.py "$@" ;;
    --smoke) shift; exec remora/.venv/bin/python -m remora.smoke "$@" ;;
    *) exec remora/.venv/bin/python -m pytest remora/tests "$@" ;;
esac
