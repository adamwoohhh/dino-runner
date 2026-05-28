import unittest

import dino_game


class InitTest(unittest.TestCase):
    def test_package_reexports_public_runtime_api(self):
        self.assertTrue(callable(dino_game.cli))
        self.assertTrue(callable(dino_game.parse_cli_args))
        self.assertTrue(callable(dino_game.DinoGame))
        self.assertTrue(callable(dino_game.LLMAgent))
        self.assertTrue(callable(dino_game.ReplayPlayer))

