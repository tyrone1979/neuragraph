#!/usr/bin/env bash
cd "$(dirname "$0")"
export PYTHONPATH=$(pwd):$PYTHONPATH
python -m ui.app "$@"
