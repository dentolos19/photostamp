@echo off
cd /d %~dp0
uv run src/main.py %*
