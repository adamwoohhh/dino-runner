# LLM Frame Window Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `dino play --llm` request future per-frame action windows and pause the simulation when the buffer runs dry.

**Architecture:** Keep the single-module structure. Add small helper functions/constants for LLM lookahead state, JSON action window parsing, and waiting decisions; update `LLMAgent` from a single pending action to a frame-indexed buffer; thread the LLM-specific spawn position into game creation.

**Tech Stack:** Python standard library, `unittest`, curses renderer.

---

### Task 1: Action Window Helpers

**Files:**
- Modify: `dino_game.py`
- Test: `tests/test_packaging.py`

- [ ] Add failing tests for parsing a JSON window, rejecting invalid actions, and detecting missing current-frame actions.
- [ ] Implement constants, parser, and buffer/wait helper.
- [ ] Run focused unittest.

### Task 2: LLM Agent Buffer

**Files:**
- Modify: `dino_game.py`
- Test: `tests/test_packaging.py`

- [ ] Add failing tests for `LLMAgent` consuming frame-indexed actions and generating a request window from current frame/state.
- [ ] Replace `pending_action` with `planned_actions` and `requested_until_frame`.
- [ ] Keep API failure bounded by inserting a short `none` window.

### Task 3: Game Loop and Lookahead

**Files:**
- Modify: `dino_game.py`
- Test: `tests/test_packaging.py`

- [ ] Add failing tests for LLM spawn X and larger state lookahead.
- [ ] Thread spawn X through `DinoGame` and use the larger value for LLM recording runs.
- [ ] Render loading state and skip frame advancement while waiting.
- [ ] Run focused tests and `python3 -m py_compile dino_game.py`.
