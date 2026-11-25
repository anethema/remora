#!/usr/bin/env bash
set -euo pipefail
case "${1:-}" in --help|-h) echo 'Usage: bootstrap.sh (Linux/WSL, Python 3.11/3.12, build-essential, gawk, git, iproute2 and util-linux). Optional PYTHON and JOBS.'; exit 0;; "") ;; *) exit 2;; esac
cd "$(dirname "$0")/../.."
git merge-base --is-ancestor d9c5097c3d8333435712ffed86bca8ce00c4bb46 HEAD
git submodule sync --recursive
git submodule update --init --recursive --jobs 6
export PATH="$HOME/.local/bin:$PATH"
if [[ ! -x remora/.venv/bin/python ]]; then
    if [[ -n "${PYTHON:-}" ]]; then "$PYTHON" -m venv remora/.venv
    elif command -v python3.12 >/dev/null; then python3.12 -m venv remora/.venv
    elif command -v python3.11 >/dev/null; then python3.11 -m venv remora/.venv
    elif command -v uv >/dev/null; then uv venv --seed --python 3.12 remora/.venv
    else echo 'Set PYTHON to a Python 3.11 or 3.12 interpreter with venv.' >&2; exit 1; fi
fi
source remora/.venv/bin/activate
# Waf also consults PYTHON when choosing its code-generator interpreter.
export PYTHON="$VIRTUAL_ENV/bin/python"
python -m pip install -r remora/requirements.lock
./waf configure --board sitl
./waf rover -j"${JOBS:-8}"
