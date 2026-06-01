.PHONY: venv install dev-install test check build check-dist publish-test publish run compete auto llm clean

SYSTEM_PYTHON ?= python3.13
VENV ?= .venv
PYTHON := $(VENV)/bin/python
PIP := $(PYTHON) -m pip
DINO := $(VENV)/bin/dino

venv:
	$(SYSTEM_PYTHON) -m venv $(VENV)

install: venv
	$(PIP) install .

dev-install: venv
	$(PIP) install -e ".[dev]"

test: venv
	env PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest discover -s tests

check: test
	env PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m compileall dino_game

build: dev-install
	rm -rf dist
	$(PYTHON) -m build

check-dist: build
	$(PYTHON) -m twine check dist/*

publish-test: check-dist
	$(PYTHON) -m twine upload --repository testpypi dist/*

publish: check-dist
	$(PYTHON) -m twine upload dist/*

run:
	$(DINO)

compete:
	$(DINO) compete

auto:
	$(DINO) play --auto

llm:
	$(DINO) play --llm

clean:
	rm -rf __pycache__ tests/__pycache__ *.egg-info build dist
