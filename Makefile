SHELL := bash
.ONESHELL:
.SHELLFLAGS := -eu -o pipefail -c
.DELETE_ON_ERROR:
MAKEFLAGS += --warn-undefined-variables
MAKEFLAGS += --no-builtin-rules

.DEFAULT_GOAL := help

.PHONY: help ## Shows help for all PHONY targets with help text
help:
	@grep -E '^.PHONY:.*?## .*$$' $(MAKEFILE_LIST) \
	| sort \
	| sed 's/^Makefile:.PHONY: //' \
	| awk ' \
		BEGIN {FS = " *?## "}; \
		{printf "\033[36m%-30s\033[0m %s\n", $$1, $$2} \
	' \
	;

.SECONDEXPANSION:

-include .env
export

RUN := uv run
PYTHON := uv python
SRC_PATH := src/disambiguate
TEST_PATH := tests
DEV_CLI_PATH := dev_cli.py
UNIT_TEST_PATH := tests/unit
E2E_TEST_PATH := tests/e2e
VERSION := $(shell uv version --short)
CLAUDE_BUNDLE := dist/disambiguate-v$(VERSION)-claude-bundle.zip

.env:
	cp .env.example $@
	@echo "Created .env from .env.example"

.PHONY: install ## Installs all dependencies
install: .env install-uv
	uvx prek install -f

.PHONY: install-uv ## Installs all dependencies via uv
install-uv:
	uv sync

.PHONY: build ## Builds the package
build:
	uv build

.PHONY: build-claude-bundle ## Builds the Claude release bundle for the current version
build-claude-bundle:
	$(MAKE) $(CLAUDE_BUNDLE)

dist/disambiguate-v%-claude-bundle.zip: build
	bash scripts/build_claude_bundle.sh "$*"

.PHONY: clean ## Cleans the build artifacts
clean:
	rm -rf dist/

.PHONY: check ## Runs all code checks and tests
check: auto-format lint type-check test

.PHONY: type-check ## Run all type checks
type-check: mypy

.PHONY: auto-format ## Auto-format all code
auto-format: $(SRC_PATH) $(TEST_PATH) $(DEV_CLI_PATH)
	$(RUN) ruff check --fix $^
	$(RUN) ruff format $^

.PHONY: lint ## Run all linters
lint: $(SRC_PATH) $(TEST_PATH) $(DEV_CLI_PATH)
	$(RUN) ruff check $^
	$(RUN) ruff format --check $^

.PHONY: mypy ## Run mypy
mypy: $(SRC_PATH) $(TEST_PATH) $(DEV_CLI_PATH)
	$(RUN) mypy $^

.PHONY: main ## Runs the main program (default disambiguate invocation)
main:
	$(RUN) python $(DEV_CLI_PATH)

.PHONY: explain ## Runs --explain via the development CLI
explain:
	$(RUN) python $(DEV_CLI_PATH) --explain

.PHONY: run ## Run everything
run: main

.PHONY: test ## Run all tests
test: unit-test e2e-test

.PHONY: unit-test ## Run all unit tests
unit-test:
	$(RUN) pytest $(UNIT_TEST_PATH)

.PHONY: e2e-test ## Run all end-to-end tests
e2e-test:
	$(RUN) pytest $(E2E_TEST_PATH)

.PHONY: dogfood ## Lint the project's own glossary against the README root
dogfood:
	$(RUN) python $(DEV_CLI_PATH) --lint
	$(RUN) python $(DEV_CLI_PATH) --drift
