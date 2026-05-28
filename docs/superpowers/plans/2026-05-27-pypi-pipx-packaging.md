# PyPI pipx Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the project publishable as `ai-dino-in-terminal` on PyPI and installable with `pip` or `pipx`, while keeping the installed command as `dino`.

**Architecture:** Keep the current single-module `setuptools` package around `dino_game.py`. Strengthen packaging tests first, then update `pyproject.toml`, documentation, and maintainer Makefile targets without touching game behavior.

**Tech Stack:** Python 3.11+, `setuptools>=77.0.3`, standard-library `unittest`, `python -m build`, `twine`.

---

## File Structure

- Modify `tests/test_packaging.py`: add packaging metadata and README install documentation assertions.
- Modify `pyproject.toml`: rename the distribution to `ai-dino-in-terminal` and add PyPI metadata.
- Modify `README.md`: make PyPI `pipx` and `pip` installation the primary user path.
- Modify `CONTRIBUTING.md`: keep local development setup and add maintainer build/publish instructions.
- Modify `Makefile`: add `build`, `publish-test`, and `publish` targets; expand `clean`.
- Do not modify `dino_game.py`: game logic and the `dino` entry point target remain unchanged.

### Task 1: Add Packaging and Install Documentation Tests

**Files:**
- Modify: `tests/test_packaging.py:1-21`
- Test: `tests/test_packaging.py`

- [ ] **Step 1: Write the failing tests**

Replace the current `PackagingTest` class with this version:

```python
class PackagingTest(unittest.TestCase):
    def project_root(self):
        return pathlib.Path(__file__).resolve().parents[1]

    def load_pyproject(self):
        return tomllib.loads((self.project_root() / "pyproject.toml").read_text())

    def test_distribution_name_is_ai_dino_in_terminal(self):
        pyproject = self.load_pyproject()

        self.assertEqual(pyproject["project"]["name"], "ai-dino-in-terminal")

    def test_dino_console_script_points_at_cli_entrypoint(self):
        pyproject = self.load_pyproject()

        scripts = pyproject["project"]["scripts"]
        self.assertEqual(scripts["dino"], "dino_game:cli")
        self.assertNotIn("trex", scripts)

        dino_game = importlib.import_module("dino_game")
        self.assertTrue(callable(dino_game.cli))

    def test_readme_documents_pip_and_pipx_installation(self):
        readme = (self.project_root() / "README.md").read_text()

        self.assertIn("pipx install ai-dino-in-terminal", readme)
        self.assertIn("pip install ai-dino-in-terminal", readme)
        self.assertIn("dino", readme)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_packaging.py
```

Expected: FAIL with an assertion showing the current package name is still
`terminal-dino-runner` or that the README does not contain the new install
commands.

- [ ] **Step 3: Keep the red test uncommitted**

Run:

```bash
git diff -- tests/test_packaging.py
```

Expected: diff shows only the new packaging assertions. Do not commit yet;
the next task will make the new tests pass before committing.

### Task 2: Update PyPI Package Metadata

**Files:**
- Modify: `pyproject.toml:1-26`
- Test: `tests/test_packaging.py`

- [ ] **Step 1: Update `pyproject.toml`**

Replace the file with:

```toml
[build-system]
requires = ["setuptools>=77.0.3"]
build-backend = "setuptools.build_meta"

[project]
name = "ai-dino-in-terminal"
version = "0.1.0"
description = "A terminal Chrome dino runner with human, rule-agent, and LLM modes."
readme = "README.md"
requires-python = ">=3.11"
authors = [
  { name = "AI Dino in Terminal contributors" },
]
license = "MIT"
keywords = ["terminal", "game", "dino", "runner", "agent", "llm"]
classifiers = [
  "Development Status :: 3 - Alpha",
  "Environment :: Console :: Curses",
  "Intended Audience :: End Users/Desktop",
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3.11",
  "Programming Language :: Python :: 3.12",
  "Programming Language :: Python :: 3.13",
  "Topic :: Games/Entertainment :: Arcade",
]

[project.urls]
Homepage = "https://github.com/bytedance/agents-competition"
Repository = "https://github.com/bytedance/agents-competition"
Issues = "https://github.com/bytedance/agents-competition/issues"

[project.scripts]
dino = "dino_game:cli"

[tool.setuptools]
py-modules = ["dino_game"]
```

- [ ] **Step 2: Run package metadata tests**

Run:

```bash
env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_packaging.py
```

Expected: package-name test passes; README install documentation test may still
fail until Task 3.

- [ ] **Step 3: Keep metadata change uncommitted**

Run:

```bash
git diff -- pyproject.toml tests/test_packaging.py
```

Expected: diff shows the package rename, PyPI metadata, and test changes.
Do not commit yet because the README install documentation test is still red.

### Task 3: Update User and Maintainer Documentation

**Files:**
- Modify: `README.md:5-57`
- Modify: `CONTRIBUTING.md:5-91`
- Test: `tests/test_packaging.py`

- [ ] **Step 1: Update README install section**

Replace the `README.md` content from `## 安装` through the end of the
"底层命令" block with:

````markdown
## 安装

推荐用 `pipx` 安装，这样会把命令行工具放在独立环境里：

```bash
pipx install ai-dino-in-terminal
dino
```

也可以用 `pip` 安装：

```bash
pip install ai-dino-in-terminal
dino
```

本地开发安装见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 启动

```bash
# 人类手动玩
dino

# 规则 Agent 自动玩
dino play --auto

# LLM Agent 自动玩
dino config +setup
dino play --llm

# 选择历史运行记录并重放
dino replay

# 选择历史运行记录并进入竞技模式
dino compete
```

也可以直接运行源码：

```bash
python3 dino_game.py
python3 -m dino_game.cli play --auto
python3 -m dino_game.cli play --llm
python3 -m dino_game.cli replay
python3 -m dino_game.cli compete
python3 -m dino_game.cli play
python3 -m dino_game.cli replay run.json
python3 -m dino_game.cli compete run.json
```
````

- [ ] **Step 2: Update CONTRIBUTING development and release docs**

In `CONTRIBUTING.md`, keep local development setup first and add this section
after the command-entry verification paragraph:

````markdown
## 构建和发布

PyPI 包名是 `ai-dino-in-terminal`，安装后暴露的命令是 `dino`。

构建发布包需要本地安装维护者工具：

```bash
python3 -m pip install build twine
```

构建 wheel 和 source distribution：

```bash
make build
```

上传到 TestPyPI：

```bash
make publish-test
```

上传到 PyPI：

```bash
make publish
```

发布前至少运行：

```bash
make check
make build
```
````

Also update the `pyproject.toml` example in `CONTRIBUTING.md` to:

```toml
[project]
name = "ai-dino-in-terminal"

[project.scripts]
dino = "dino_game:cli"
```

- [ ] **Step 3: Run tests to verify docs satisfy coverage**

Run:

```bash
env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_packaging.py
```

Expected: all `tests/test_packaging.py` tests pass.

- [ ] **Step 4: Commit passing packaging and docs change**

Run:

```bash
git add tests/test_packaging.py pyproject.toml README.md CONTRIBUTING.md
git commit -m "build: prepare pypi package metadata"
```

### Task 4: Add Build and Publish Make Targets

**Files:**
- Modify: `Makefile:1-37`
- Test: `Makefile`

- [ ] **Step 1: Update `Makefile` phony targets and commands**

Replace the current `Makefile` with:

```make
.PHONY: venv install dev-install test check build publish-test publish run compete agent llm clean

SYSTEM_PYTHON ?= python3
VENV ?= .venv
PYTHON := $(VENV)/bin/python
PIP := $(PYTHON) -m pip
DINO := $(VENV)/bin/dino

venv:
	$(SYSTEM_PYTHON) -m venv $(VENV)

install: venv
	$(PIP) install .

dev-install: venv
	$(PIP) install -e .

test: venv
	env PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m unittest tests/test_packaging.py

check: test
	env PYTHONDONTWRITEBYTECODE=1 $(PYTHON) -m py_compile dino_game.py

build:
	$(SYSTEM_PYTHON) -m build

publish-test:
	$(SYSTEM_PYTHON) -m twine upload --repository testpypi dist/*

publish:
	$(SYSTEM_PYTHON) -m twine upload dist/*

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
```

- [ ] **Step 2: Run tests and syntax check**

Run:

```bash
env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_packaging.py
env PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile dino_game.py
```

Expected: both commands exit 0.

- [ ] **Step 3: Check build tool availability**

Run:

```bash
python3 -m build
```

Expected if `build` is installed: exits 0 and creates `dist/*.whl` and
`dist/*.tar.gz`. Expected if `build` is not installed: fails with
`No module named build`; in that case, report that local build verification
requires `python3 -m pip install build`.

- [ ] **Step 4: Commit Makefile change**

Run:

```bash
git add Makefile
git commit -m "build: add pypi publish targets"
```

### Task 5: Final Verification

**Files:**
- Read: `pyproject.toml`
- Read: `README.md`
- Read: `CONTRIBUTING.md`
- Read: `Makefile`
- Read: `tests/test_packaging.py`

- [ ] **Step 1: Run full test command**

Run:

```bash
env PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_packaging.py
```

Expected: `Ran 53 tests` or more, with `OK`.

- [ ] **Step 2: Run syntax check**

Run:

```bash
env PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile dino_game.py
```

Expected: exits 0 with no output.

- [ ] **Step 3: Verify command references**

Run:

```bash
rg -n "terminal-dino-runner|trex|pipx install ai-dino-in-terminal|pip install ai-dino-in-terminal" pyproject.toml README.md CONTRIBUTING.md Makefile tests/test_packaging.py
```

Expected: no `terminal-dino-runner`; no `trex` except the test assertion
`self.assertNotIn("trex", scripts)`; README contains both pip and pipx install
commands.

- [ ] **Step 4: Inspect git state**

Run:

```bash
git status --short
```

Expected: no uncommitted changes after the task commits, unless the local build
step created ignored or intentionally cleaned artifacts.
