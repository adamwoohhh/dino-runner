# LLM Frame Window Design

## Goal

Make `dino llm` resilient to model/API latency by asking the model for a future window of per-frame actions, pausing game simulation when the action plan is exhausted, and exposing obstacles earlier than the normal screen spawn point.

## Behavior

- LLM mode uses a farther obstacle spawn X than manual and rule-agent modes.
- LLM state includes a larger lookahead range so off-screen future obstacles are visible to the model.
- The model is prompted to return JSON with a `start_frame` and an `actions` array. Each action maps to one future frame and must be `jump`, `duck`, or `none`.
- The local agent stores returned actions in a frame-indexed buffer.
- The game loop executes the buffered action for the current `event_frame`.
- If the current frame has no buffered action in LLM mode, the loop renders a loading/planning state and does not advance physics, spawn timers, score, replay frame count, or recording.
- If an API call fails or returns invalid data, the agent inserts a short `none` window so the loop cannot block forever.

## Scope

Only `dino_game.py`, tests, and this design/plan documentation change. Replay files continue recording only actual executed frames and actions; loading waits are not replay frames.

