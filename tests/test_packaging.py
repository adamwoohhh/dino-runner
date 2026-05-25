import importlib
import pathlib
import tomllib
import unittest


class PackagingTest(unittest.TestCase):
    def test_trex_console_script_points_at_cli_entrypoint(self):
        project_root = pathlib.Path(__file__).resolve().parents[1]
        pyproject = tomllib.loads((project_root / "pyproject.toml").read_text())

        scripts = pyproject["project"]["scripts"]
        self.assertEqual(scripts["trex"], "dino_game:cli")

        dino_game = importlib.import_module("dino_game")
        self.assertTrue(callable(dino_game.cli))


if __name__ == "__main__":
    unittest.main()
