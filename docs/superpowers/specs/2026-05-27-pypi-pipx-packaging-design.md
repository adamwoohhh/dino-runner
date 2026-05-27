# PyPI and pipx Packaging Design

## Goal

Make the project installable from PyPI with either `pip` or `pipx`.
The published package name will be `ai-dino-in-terminal`; the installed
command will remain `dino`.

## Scope

- Update Python package metadata for PyPI publication.
- Preserve the current single-module implementation in `dino_game.py`.
- Preserve the current console command: `dino`.
- Add local build and publish commands for maintainers.
- Update user and contributor documentation for PyPI, pip, and pipx usage.
- Extend packaging tests to cover the PyPI package name and install docs.

## Out of Scope

- Moving `dino_game.py` into a package directory.
- Adding CI release automation.
- Publishing to PyPI from this workspace.
- Changing game logic, replay behavior, or the command-line interface beyond
  installation and packaging metadata.

## Packaging

`pyproject.toml` will stay on `setuptools` and continue to publish a single
module:

```toml
[project]
name = "ai-dino-in-terminal"
version = "0.1.0"

[project.scripts]
dino = "dino_game:cli"

[tool.setuptools]
py-modules = ["dino_game"]
```

The project metadata will be expanded with PyPI-friendly fields:

- `authors`
- `license`
- `keywords`
- `classifiers`
- `project.urls`

The package will keep zero required runtime dependencies. The optional Claude
LLM mode already uses the standard library HTTP path and environment variable
configuration, so no dependency split is needed.

## Installation Experience

`README.md` will present PyPI install paths first:

```bash
pipx install ai-dino-in-terminal
dino
```

and:

```bash
pip install ai-dino-in-terminal
dino
```

Local development installation remains documented in `CONTRIBUTING.md` with
`make dev-install` and the project `.venv`.

## Build and Publish Commands

`Makefile` will gain maintainer-oriented targets:

- `build`: build both wheel and source distribution with `python -m build`
- `publish-test`: upload `dist/*` to TestPyPI with `twine`
- `publish`: upload `dist/*` to PyPI with `twine`
- `clean`: also remove `dist/`, `build/`, and generated egg-info metadata

`build` and `twine` will be documented as maintainer tools, not runtime
dependencies.

## Tests

The existing packaging test will be extended to verify:

- `[project].name` is `ai-dino-in-terminal`
- the `dino` console script points to `dino_game:cli`
- the old `trex` console script is absent
- README documents both `pip install ai-dino-in-terminal` and
  `pipx install ai-dino-in-terminal`

The verification commands are:

```bash
env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_packaging.py
env PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile dino_game.py
```

If local build tooling is available, run:

```bash
python3 -m build
```

## Acceptance Criteria

- `pip install ai-dino-in-terminal` and `pipx install ai-dino-in-terminal`
  are the documented user install paths.
- A built wheel exposes the `dino` command.
- Tests cover the package name and command entry point.
- Existing game behavior remains unchanged.
