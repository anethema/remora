#!/usr/bin/env bash
set -eu
case "${1:-}" in --help|-h) echo 'Usage: doctor.sh — verify checkout, build, imports, and private SITL network'; exit 0;; "") ;; *) exit 2;; esac
cd "$(dirname "$0")/../.."
git rev-parse --show-toplevel HEAD
git merge-base --is-ancestor d9c5097c3d8333435712ffed86bca8ce00c4bb46 HEAD
pins=$(git submodule status --recursive)
if grep -Eq '^[-+U]' <<< "$pins"; then echo 'Submodule state differs from the baseline' >&2; exit 1; fi
test -x build/sitl/bin/ardurover
remora/.venv/bin/python -c 'import aiohttp, yaml, serial, geographiclib, pymavlink; import sys; print(sys.version)'
unshare --user --map-root-user --net sh -c 'ip link set lo up && ip -br address'
echo 'Built Rover and Python dependencies present. Run run-tests.sh --smoke for firmware verification.'
