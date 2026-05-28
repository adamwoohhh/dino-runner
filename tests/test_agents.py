import importlib
import unittest


class RuleAgentTest(unittest.TestCase):
    def dino_game(self):
        return importlib.import_module("dino_game")

    def test_rule_agent_jumps_for_low_obstacles_in_reaction_window(self):
        dino_game = self.dino_game()
        agent = dino_game.RuleAgent()

        action = agent.decide({
            "dino_y": 0.0,
            "jumping": False,
            "speed": dino_game.INITIAL_SPEED,
            "obstacles": [{
                "kind": "cactus_group",
                "distance": 10,
                "height": 0,
                "h": 4,
            }],
        })

        self.assertEqual(action, "jump")

    def test_rule_agent_ducks_under_mid_bird(self):
        dino_game = self.dino_game()
        agent = dino_game.RuleAgent()

        action = agent.decide({
            "dino_y": 0.0,
            "jumping": False,
            "speed": dino_game.INITIAL_SPEED,
            "obstacles": [{
                "kind": "bird",
                "distance": 10,
                "height": 4,
                "h": 2,
            }],
        })

        self.assertEqual(action, "duck")

