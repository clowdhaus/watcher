SHELL = /usr/bin/env bash

.PHONY: help
.DEFAULT_GOAL := help

help:
	@awk 'BEGIN {FS = ":.*##"; printf "Usage: make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-25s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Development

.PHONY: setup
setup: ## Setup local pipenv environment
	@pip3 install pipenv && pipenv install --dev --pre --skip-lock && pipenv update
	@yarn

.PHONY: test
test: ## Execute unit tests
	@pipenv run test

cover:
	@pipenv run cover && open "file://$(shell pwd)/htmlcov/index.html"

coverage: test cover clean ## Execute unit tests and  generate test coverage report

.PHONY: clean
clean: ## Remove generated development artifacts to start with a clean slate to develop
	@find . | grep -E "(__pycache__|\.pyc|\.pyo$$|\.pytest_cache|\.coverage.$$|core.zip)" | xargs rm -rf
	rm -rf node_modules Pipfile.lock yarn.lock .serverless
	pipenv --rm

.PHONY: lint
lint: ## Execute static linting on codebase and display results
	@echo "============== Lint =============="
	@pipenv run lint

.PHONY: cyclomatic_complexity
cyclomatic_complexity: ## Report cyclomatic complexity values
	@echo "============== Cyclomatic Complexity =============="
	@pipenv run radon cc lambdas/*.py -a

.PHONY: halstead_complexity
halstead_complexity: ## Report Halstead complexity measures
	@echo "============== Halstead Complexity =============="
	@pipenv run radon hal lambdas/*.py

.PHONY: typecheck ## Type check codebase and report errors
	@echo "============== Type Check =============="
	@pipenv run typecheck

.PHONY: check
check: lint cyclomatic_complexity halstead_complexity typecheck ## Run all static analysis checks on codebase

.PHONY: format
format: ## Format codebase
	@pipenv run imports
	@pipenv run format

##@ Pre-Deploy

generate_artifacts: ## Generate artifacts for use in lambda layers
	@for LAYER in $$(find layers -mindepth 1 -maxdepth 1 -type d); do \
		pushd $$LAYER ; ./generate.sh ; popd ; \
	done