import importlib
import json
import os
import pathlib
import tempfile
import tomllib
import unittest
from unittest import mock


class LoadingDinoSpriteTest(unittest.TestCase):
    def test_loading_dino_sprites_keep_existing_footprint(self):
        dino_game = importlib.import_module("dino_game")

        for sprite in (
            dino_game.DINO_LOADING_STAND,
            dino_game.DINO_LOADING_JUMP,
            dino_game.DINO_LOADING_DUCK,
        ):
            self.assertEqual(len(sprite), 6)
            self.assertLessEqual(max(len(line) for line in sprite), 10)

        self.assertEqual(dino_game.DINO_LOADING_DUCK[:2], ["          ", "          "])

    def test_loading_dino_open_frames_use_original_side_facing_sprites(self):
        dino_game = importlib.import_module("dino_game")

        self.assertEqual(dino_game.DINO_LOADING_STAND, dino_game.DINO_RUN_1)
        self.assertEqual(dino_game.DINO_LOADING_JUMP_OPEN, dino_game.DINO_JUMP)
        self.assertEqual(dino_game.DINO_LOADING_DUCK_OPEN, dino_game.DINO_DUCK)

    def test_loading_dino_blink_frames_only_change_the_eye_line(self):
        dino_game = importlib.import_module("dino_game")

        self.assertEqual(dino_game.DINO_LOADING_STAND_BLINK[0], dino_game.DINO_RUN_1[0])
        self.assertNotEqual(dino_game.DINO_LOADING_STAND_BLINK[1], dino_game.DINO_RUN_1[1])
        self.assertEqual(dino_game.DINO_LOADING_STAND_BLINK[2:], dino_game.DINO_RUN_1[2:])

        self.assertEqual(dino_game.DINO_LOADING_JUMP[0], dino_game.DINO_JUMP[0])
        self.assertNotEqual(dino_game.DINO_LOADING_JUMP[1], dino_game.DINO_JUMP[1])
        self.assertEqual(dino_game.DINO_LOADING_JUMP[2:], dino_game.DINO_JUMP[2:])

        self.assertEqual(dino_game.DINO_LOADING_DUCK[:3], dino_game.DINO_DUCK[:3])
        self.assertNotEqual(dino_game.DINO_LOADING_DUCK[3], dino_game.DINO_DUCK[3])
        self.assertEqual(dino_game.DINO_LOADING_DUCK[4:], dino_game.DINO_DUCK[4:])

    def test_loading_dino_art_animates_in_each_pose(self):
        dino_game = importlib.import_module("dino_game")
        game = dino_game.DinoGame()

        standing_open = dino_game.dino_art_for_state(
            game,
            loading=True,
            animation_time=0.0,
        )
        standing_blink = dino_game.dino_art_for_state(
            game,
            loading=True,
            animation_time=dino_game.LOADING_DINO_ANIM_INTERVAL,
        )
        self.assertNotEqual(standing_open, standing_blink)

        game.jumping = True
        jumping_open = dino_game.dino_art_for_state(
            game,
            loading=True,
            animation_time=0.0,
        )
        jumping_blink = dino_game.dino_art_for_state(
            game,
            loading=True,
            animation_time=dino_game.LOADING_DINO_ANIM_INTERVAL,
        )
        self.assertNotEqual(jumping_open, jumping_blink)

        game.jumping = False
        game.ducking = True
        ducking_open = dino_game.dino_art_for_state(
            game,
            loading=True,
            animation_time=0.0,
        )
        ducking_blink = dino_game.dino_art_for_state(
            game,
            loading=True,
            animation_time=dino_game.LOADING_DINO_ANIM_INTERVAL,
        )
        self.assertNotEqual(ducking_open, ducking_blink)
