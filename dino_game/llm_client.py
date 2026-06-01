"""Transport wrappers for API and local Codex LLM calls."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import urllib.request
from dataclasses import dataclass
from typing import Protocol


class LLMTransportConfig(Protocol):
    api_key: str
    base_url: str
    model: str


@dataclass(frozen=True)
class LLMResponse:
    raw_response: dict
    response_text: str
    request_payload: dict
    token_usage: dict | None = None


def _int_or_none(value) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def token_usage_from_api_response(raw_response: dict) -> dict | None:
    usage = raw_response.get("usage")
    if not isinstance(usage, dict):
        return None
    prompt_tokens = _int_or_none(
        usage.get("input_tokens", usage.get("prompt_tokens")),
    )
    completion_tokens = _int_or_none(
        usage.get("output_tokens", usage.get("completion_tokens")),
    )
    total_tokens = _int_or_none(usage.get("total_tokens"))
    if prompt_tokens is None and completion_tokens is None and total_tokens is None:
        return None
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


def token_usage_from_codex_stderr(stderr: str | None) -> dict | None:
    if not isinstance(stderr, str):
        return None
    match = re.search(r"tokens used\s*\n\s*([\d,]+)", stderr, re.IGNORECASE)
    if not match:
        return None
    return {
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": int(match.group(1).replace(",", "")),
    }


class LLMClient:
    """HTTP transport for the Responses API.

    The action-window prompt and cache state live outside this class so tests can
    replace transport behavior without coupling to LLMAgent's frame state.
    """

    def __init__(self, config: LLMTransportConfig):
        self.config = config

    def create_response(
            self,
            *,
            prompt: str,
            text_format: dict,
            extract_text,
            timeout: int = 60) -> LLMResponse:
        data = json.dumps({
            "model": self.config.model,
            "input": prompt,
            "text": {
                "format": text_format,
            },
            "stream": False,
        }).encode()
        request_payload = json.loads(data.decode())
        req = urllib.request.Request(
            f"{self.config.base_url.rstrip('/')}/responses",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
        )

        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw_response = json.loads(resp.read())
        return LLMResponse(
            raw_response=raw_response,
            response_text=extract_text(raw_response),
            request_payload=request_payload,
            token_usage=token_usage_from_api_response(raw_response),
        )


class CodexLLMClient:
    """Local Codex CLI transport using non-interactive `codex exec`."""

    def create_response(
            self,
            *,
            prompt: str,
            text_format: dict,
            extract_text,
            timeout: int = 60) -> LLMResponse:
        schema = text_format.get("schema") if isinstance(text_format, dict) else None
        schema_path = None
        command = [
            "codex",
            "exec",
            "--sandbox",
            "read-only",
            "--ephemeral",
            "--skip-git-repo-check",
        ]
        if isinstance(schema, dict):
            with tempfile.NamedTemporaryFile(
                    "w",
                    encoding="utf-8",
                    suffix=".json",
                    delete=False) as schema_file:
                json.dump(schema, schema_file)
                schema_file.write("\n")
                schema_path = schema_file.name
            command.extend(["--output-schema", schema_path])
        command.append(prompt)
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            if schema_path is not None:
                try:
                    os.remove(schema_path)
                except FileNotFoundError:
                    pass
        raw_response = {
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "returncode": completed.returncode,
        }
        response_text = extract_text(raw_response).strip()
        if completed.returncode != 0:
            raw_response["error"] = f"codex exec exited with status {completed.returncode}"
            response_text = ""
        return LLMResponse(
            raw_response=raw_response,
            response_text=response_text,
            request_payload={
                "command": command[:-1] + ["<prompt>"],
                "prompt": prompt,
                "text_format": text_format,
            },
            token_usage=token_usage_from_codex_stderr(completed.stderr),
        )
