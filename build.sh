#!/usr/bin/env sh
cd "$(dirname "$0")"
uv run pyinstaller src/main.py --onefile --name app "$@"
