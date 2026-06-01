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

    def test_readme_documents_github_release_install_script(self):
        readme = (self.project_root() / "README.md").read_text()

        self.assertIn("install.sh", readme)
        self.assertIn("GitHub Release", readme)
        self.assertIn("curl -fsSL", readme)
        self.assertIn("latest release", readme)
        self.assertIn("DINO_INSTALL_SOURCE=github", readme)

    def test_readme_documents_tag_triggered_github_release_publish(self):
        readme = (self.project_root() / "README.md").read_text()

        self.assertIn("git tag v0.1.1", readme)
        self.assertIn("git push origin v0.1.1", readme)
        self.assertIn("GitHub Actions", readme)
        self.assertIn("dist/*.whl", readme)

    def test_github_actions_release_workflow_publishes_release_assets(self):
        workflow = (self.project_root() / ".github" / "workflows" / "release.yml").read_text()

        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("tags:", workflow)
        self.assertIn("'v*'", workflow)
        self.assertIn("python-version: '3.13'", workflow)
        self.assertIn("python -m unittest discover -s tests", workflow)
        self.assertIn("python -m build", workflow)
        self.assertIn("python -m twine check dist/*", workflow)
        self.assertIn("tag_version", workflow)
        self.assertIn("pyproject_version", workflow)
        self.assertIn("softprops/action-gh-release", workflow)
        self.assertIn("dist/*.whl", workflow)
        self.assertIn("dist/*.tar.gz", workflow)
        self.assertNotIn("twine upload", workflow)

    def test_github_actions_release_workflow_has_no_accidental_top_level_script_lines(self):
        workflow = (self.project_root() / ".github" / "workflows" / "release.yml").read_text()
        allowed_top_level_prefixes = ("name:", "on:", "permissions:", "jobs:")

        for line_number, line in enumerate(workflow.splitlines(), start=1):
            if not line or line.startswith(" "):
                continue
            self.assertTrue(
                line.startswith(allowed_top_level_prefixes),
                f"unexpected top-level workflow line {line_number}: {line}",
            )

    def test_install_script_installs_release_wheel_without_pypi_or_pipx(self):
        install_script = (self.project_root() / "install.sh").read_text()

        self.assertIn("DEFAULT_VERSION=\"latest\"", install_script)
        self.assertIn("resolve_latest_version", install_script)
        self.assertIn("/releases/latest", install_script)
        self.assertIn("url_effective", install_script)
        self.assertIn("/download/$latest_tag", install_script)
        self.assertIn("DINO_INSTALL_SOURCE=\"${DINO_INSTALL_SOURCE:-github}\"", install_script)
        self.assertIn("DEFAULT_REPO=\"https://github.com/adamwoohhh/agents-competition\"", install_script)
        self.assertIn("/releases/download/v$DINO_VERSION", install_script)
        self.assertIn("ai_dino_in_terminal-${DINO_VERSION}-py3-none-any.whl", install_script)
        self.assertIn("-m venv", install_script)
        self.assertIn("pip install --no-index", install_script)
        self.assertIn("ln -sf", install_script)
        self.assertNotIn("pipx", install_script)

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
