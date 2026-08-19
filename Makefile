.PHONY: install test lint run clean

# Install in editable mode with dev deps
install:
	pip install -e ".[dev]"

# Run tests
test:
	pytest tests/ -v

# Lint & Format
lint:
	ruff check src/ tests/
	ruff format src/ tests/

# Type Check
typecheck:
	mypy src/

# Run CLI directly
run:
	python -m esim_tool_manager.main --help

# Clean build artifacts
clean:
	Remove-Item -Recurse -Force build, dist, .pytest_cache, .mypy_cache, .ruff_cache -ErrorAction SilentlyContinue

	Get-ChildItem -Path . -Filter "*.egg-info" -Directory |
		Remove-Item -Recurse -Force

	Get-ChildItem -Path . -Directory -Recurse -Filter "__pycache__" |
		Remove-Item -Recurse -Force
