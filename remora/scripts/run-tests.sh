#!/usr/bin/env bash
set -eu
root=$(cd "$(dirname "$0")/../.." && pwd)
export PYTHONPATH="$root/remora/src"
cd "$root"
case "${1:-}" in
    --help|-h) echo 'Usage: run-tests.sh [--smoke | --recovery | --update | --station | PYTEST_ARGS...]'; exit 0 ;;
    --station) shift; exec remora/.venv/bin/python -m pytest -s remora/tests/live_bow.py "$@" ;;
    --update) shift; exec remora/.venv/bin/python -m pytest -s remora/tests/live_update.py "$@" ;;
    --recovery) shift; exec remora/.venv/bin/python -m pytest -s remora/tests/live_recovery.py "$@" ;;
    --smoke) shift; exec remora/.venv/bin/python -m remora.smoke "$@" ;;
    *) exec remora/.venv/bin/python -m pytest remora/tests "$@" ;;
esac
