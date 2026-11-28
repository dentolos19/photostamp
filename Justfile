set dotenv-load
set dotenv-filename := dotenv_file
set dotenv-override

environment := ""
dotenv_file := if environment == "" { ".env" } else { ".env." + environment }

setup: install

install:
    uv sync --frozen

start *args:
    uv run python src/main.py {{ args }}

check:
    uv run ruff check --fix && uv run ruff format && uv run ty check

test:
    uv run python -m unittest discover -s tests
