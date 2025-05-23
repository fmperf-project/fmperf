SHELL := /usr/bin/env bash
VENV := .venv

##@ General

# The help target prints out all targets with their descriptions organized
# beneath their categories. The categories are represented by '##@' and the
# target descriptions by '##'. The awk commands is responsible for reading the
# entire set of makefiles included in this invocation, looking for lines of the
# file as xyz: ## something, and then pretty-format the target and help. Then,
# if there's a line with ##@ something, that gets pretty-printed as a category.
# More info on the usage of ANSI control characters for terminal formatting:
# https://en.wikipedia.org/wiki/ANSI_escape_code#SGR_parameters
# More info on the awk command:
# http://linuxcommand.org/lc3_adv_awk.php

.PHONY: help
help: ## Print help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_0-9-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

.PHONY: install
install: ## Install core requirements
	@echo "Installing core requirements..."
	pip install -r requirements.txt

.PHONY: venv
venv: ## Create a Python virtual environment with core requirements
	@echo "Creating virtual environment..."
	@if [ ! -d $(VENV) ]; then \
	    python3 -m venv $(VENV); \
		source $(VENV)/bin/activate; \
		pip install --upgrade pip; \
	else \
		echo "Virtual environment already exists, leaving as-is"; \
		exit 1; \
	fi
	@echo "Installing core dependencies..."
	@source $(VENV)/bin/activate; pip install -r requirements.txt; pip install -e .;
	@printf "\nRun \033[35msource $(VENV)/bin/activate\033[0m to activate the virtual environment\n"

##@ Development

.PHONY: format
format: ## Autoformat code
	@echo "Formatting Python code..."
	ruff format ./fmperf
	ruff format ./examples
	@echo "Sorting requirements..."
	@for req in $$(ls requirements*.txt); do sort -f $$req -o $$req; done

.PHONY: lint
lint: ## Perform linting
	black --check ./fmperf
	black --check ./examples

.PHONY: type-check
type-check: ## Perform type checking
	@echo "Running type checking with mypy..."
	mypy --strict ./fmperf
	mypy --strict ./examples

.PHONY: test
test: ## Run tests
	pytest fmperf/tests/

.PHONY: install-dev
install-dev: ## Install development requirements
	@echo "Installing development requirements..."
	pip install -r requirements-dev.txt

.PHONY: install-all
install-all: install install-dev ## Install core and development requirements

.PHONY: venv-dev
venv-dev: venv ## Create a Python virtual environment with core and dev requirements
	@echo "Installing dev dependencies..."
	@source $(VENV)/bin/activate; pip install -r requirements-dev.txt
	@printf "\nRun \033[35msource $(VENV)/bin/activate\033[0m to activate the virtual environment\n"

.PHONY: clean
clean: ## Remove cache, backup, and temporary files
	@echo "Running cleanup"
	find fmperf/ -depth -name '__pycache__' -exec rm -vrf {} \;
	rm -vrf fmperf.egg-info
	find -depth -name '.pytest_cache' -exec rm -vrf {} \;
	find -depth -name '.ipynb_checkpoints' -exec rm -vrf {} \;
	ruff clean
	rm -rf .mypy_cache
