import importlib
import unittest


class ConstantsTest(unittest.TestCase):
    def dino_game(self):
        return importlib.import_module("dino_game")

    def test_frame_and_llm_window_constants_are_consistent(self):
        dino_game = self.dino_game()

        self.assertEqual(dino_game.FRAME_MS, 1000 // dino_game.FPS)
        self.assertEqual(
            dino_game.LLM_ACTION_WINDOW_FRAMES,
            dino_game.FPS * dino_game.LLM_ACTION_WINDOW_SECONDS,
        )

