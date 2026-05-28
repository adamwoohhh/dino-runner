# OpenAI Responses Config Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Anthropic-only LLM mode with OpenAI Responses API configuration and add `dino config` commands.

**Architecture:** Keep the single-file project structure. Add config helpers, interactive prompting helpers, and config CLI parsing near the existing CLI functions; update `LLMAgent` to accept an `LLMConfig` and call `{base_url}/responses`.

**Tech Stack:** Python 3.11 standard library (`json`, `os`, `urllib.request`, `unittest`, `tempfile`, `unittest.mock`).

---

### Task 1: Config Model And Storage

**Files:**
- Modify: `tests/test_packaging.py`
- Modify: `dino_game.py`

- [ ] Write failing tests for `config_file_path`, `load_llm_config`, `save_llm_config`, `reset_llm_config`, and `render_config`.
- [ ] Run `python3 -m unittest tests.test_packaging.CliContractTest` and verify the new tests fail because helpers are missing.
- [ ] Add `LLMConfig`, default constants, JSON load/save/reset helpers, and masked config rendering.
- [ ] Run the same test class and verify it passes.

### Task 2: Config CLI Parsing And Commands

**Files:**
- Modify: `tests/test_packaging.py`
- Modify: `dino_game.py`
- Modify: `README.md`

- [ ] Write failing tests for `parse_cli_args(["config"])`, `["config", "+setup"]`, `["config", "+reset"]`, config help text, and main help listing.
- [ ] Run `python3 -m unittest tests.test_packaging.CliContractTest` and verify the tests fail because `config` is unknown.
- [ ] Extend `CliArgs`, command groups, command help, parser, and `cli()` handling.
- [ ] Update README command examples and mode table to mention OpenAI LLM config.
- [ ] Run the CLI contract tests and verify they pass.

### Task 3: Interactive Setup Flow

**Files:**
- Modify: `tests/test_packaging.py`
- Modify: `dino_game.py`

- [ ] Write failing tests for interactive setup using injected input/output callables: setup writes directly; llm startup asks whether to persist and defaults to no.
- [ ] Run the focused tests and verify they fail.
- [ ] Add `prompt_for_llm_config`, `resolve_llm_config_for_run`, and `run_config_setup`.
- [ ] Make `cli()` resolve LLM config before `curses.wrapper`.
- [ ] Run the focused tests and verify they pass.

### Task 4: OpenAI Responses Agent

**Files:**
- Modify: `tests/test_packaging.py`
- Modify: `dino_game.py`
- Modify: `CONTRIBUTING.md`

- [ ] Write failing tests for Responses request URL, authorization header, payload, `output_text` parsing, and structured output parsing.
- [ ] Run the focused tests and verify they fail against the old Anthropic implementation.
- [ ] Update `LLMAgent` to accept `LLMConfig`, call `POST {base_url}/responses`, parse Responses output, and remove Anthropic env-key dependency.
- [ ] Update docs and user-facing labels from Claude/Anthropic to OpenAI.
- [ ] Run the focused tests and verify they pass.

### Task 5: Full Verification

**Files:**
- No source edits unless verification exposes an issue.

- [ ] Run `python3 -m unittest`.
- [ ] Run `python3 -m py_compile dino_game.py`.
- [ ] Inspect `git diff --check`.
- [ ] Fix any reported issue and rerun the relevant command.
