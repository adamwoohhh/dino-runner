import importlib
import json
import os
import pathlib
import tempfile
import tomllib
import unittest
from unittest import mock


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
        self.assertEqual(scripts["dino"], "dino_game.cli:cli")
        self.assertNotIn("trex", scripts)

        dino_game = importlib.import_module("dino_game")
        self.assertTrue(callable(dino_game.cli))

    def test_readme_documents_pip_and_pipx_installation(self):
        readme = (self.project_root() / "README.md").read_text()

        self.assertIn("pipx install ai-dino-in-terminal", readme)
        self.assertIn("pip install ai-dino-in-terminal", readme)
        self.assertIn("dino", readme)

    def test_makefile_publish_targets_build_and_check_fresh_artifacts(self):
        makefile = (self.project_root() / "Makefile").read_text()

        self.assertIn("SYSTEM_PYTHON ?= python3.13", makefile)
        self.assertIn("build: dev-install\n\trm -rf dist\n\t$(PYTHON) -m build", makefile)
        self.assertIn("check-dist: build\n\t$(PYTHON) -m twine check dist/*", makefile)
        self.assertIn("publish-test: check-dist", makefile)
        self.assertIn("publish: check-dist", makefile)

    def test_dev_extra_declares_packaging_tools(self):
        pyproject = self.load_pyproject()

        dev_dependencies = pyproject["project"]["optional-dependencies"]["dev"]
        self.assertTrue(any(dep.startswith("build>=") for dep in dev_dependencies))
        self.assertTrue(any(dep.startswith("twine>=") for dep in dev_dependencies))

    def test_developer_setup_installs_dev_extra(self):
        makefile = (self.project_root() / "Makefile").read_text()
        contributing = (self.project_root() / "CONTRIBUTING.md").read_text()

        self.assertIn('dev-install: venv\n\t$(PIP) install -e ".[dev]"', makefile)
        self.assertIn('python3 -m pip install -e ".[dev]"', contributing)
        self.assertNotIn("python3 -m pip install build twine", contributing)
