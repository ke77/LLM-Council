.PHONY: build check

check:
	python -m mypy src/
	python -m ruff check src/

build: check
	python -m build
