.PHONY: setup check

setup:
	uv sync

check:
	uv run ruff format
	uv run ruff check --fix
