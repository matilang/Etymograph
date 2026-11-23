# EtymoGraph pipeline. Every target runs inside the uv-managed venv (uv.lock).

.PHONY: setup lint typecheck test check

setup:      ## create or update the venv from uv.lock
	uv sync --frozen

lint:       ## ruff lint + format check
	uv run ruff check etymo tests
	uv run ruff format --check etymo tests

typecheck:  ## mypy strict on the package
	uv run mypy

test:       ## unit tests
	uv run pytest

check: lint typecheck test
