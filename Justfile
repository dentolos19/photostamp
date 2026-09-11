setup:
    uv sync

start *args:
    uv run python src/main.py {{ args }}

check:
    uv run ruff check --fix && uv run ruff format && uv run ty check
