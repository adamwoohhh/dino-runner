# LLM Loading Dino UI Design

## Goal

Show a front-facing blinking dino while `dino play --llm` is waiting for the model, without changing game physics, collision boxes, replay timing, or normal non-loading sprite behavior.

## Approved Visual Direction

Use the E1 variation from the brainstorming preview:

- The loading dino face is filled with block characters.
- Only the eye positions are hollow.
- There is no mouth cutout.
- The blink is shown by filling one eye hole while the other remains hollow.
- Loading supports standing, jumping, and ducking silhouettes.

## Implementation

Add dedicated loading dino sprites in `dino_game.py` instead of replacing the normal gameplay sprites. `TerminalRenderer.draw()` will select those sprites only when `loading_text` is present and the game is not paused. The selected loading sprite will still use the current game state: ducking first, jumping second, otherwise standing.

The loading sprite arrays must keep the same row count and practical footprint as the existing standing, jumping, and ducking sprites. Collision logic stays in `DinoGame.update()` and is not modified.

## Testing

Add unit coverage in `tests/test_packaging.py` that checks:

- loading sprites exist for standing, jumping, and ducking;
- loading standing and jumping sprites are 6 rows tall;
- loading ducking sprite is 6 rows tall with the top two rows blank, matching the existing ducking footprint;
- loading sprites have no non-space characters outside the existing dino sprite width;
- the `DinoGame.update()` collision-box source remains based on `ducking` and `dino_y`, not loading UI state.
