#!/usr/bin/env sh
cd "$(dirname "$0")"
uv run src/main.py "$@"
