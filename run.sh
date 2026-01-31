#!/usr/bin/env bash
cd "$(dirname "$0")"
export PYTHONPATH=$(pwd):$PYTHONPATH
nohup python -m ui.app "$@" &
