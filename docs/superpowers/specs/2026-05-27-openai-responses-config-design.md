# OpenAI Responses Config Design

## Goal

Move `dino llm` from the Anthropic Messages API to the OpenAI Responses API and add local interactive configuration management.

## Configuration

The CLI stores user-level LLM settings at:

```text
~/.config/ai-dino-in-terminal/config.json
```

The file contains JSON:

```json
{
  "api_key": "sk-...",
  "base_url": "https://api.openai.com/v1",
  "model": "gpt-5.4-mini"
}
```

`api_key`, `base_url`, and `model` are required to run the LLM agent. `base_url` and `model` may be prefilled with defaults during interactive setup.

## CLI Behavior

`dino config` prints the current configuration. The API key is never printed in full; it is masked.

`dino config +setup` prompts for `api_key`, `base_url`, and `model`, then always writes the result to the config file.

`dino config +reset` removes the config file if it exists and reports the result.

`dino llm` reads the config before curses starts. If required values are missing, it prompts for them. After collecting values, it asks whether to persist them. The default is `N`, which means the collected config is used only for the current run. Choosing `y` writes the config file.

## LLM Agent

`LLMAgent` calls `POST {base_url}/responses` with an OpenAI Responses API payload:

```json
{
  "model": "gpt-5.4-mini",
  "input": "..."
}
```

The agent extracts an action from `output_text` when present. It also supports the structured `output[].content[].text` shape so tests and compatible providers can return either form.

Failures during background API calls do not crash the game. The pending action falls back to `none`, matching the current fault-tolerant behavior.

## Testing

Tests cover:

- CLI parsing and help for `config`, `config +setup`, and `config +reset`.
- Config path, read, write, reset, and masked rendering.
- Interactive setup behavior with and without persistence.
- OpenAI Responses request construction and output parsing.
- Existing game, replay, and packaging contracts.
