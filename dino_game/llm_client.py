"""Transport wrapper for OpenAI-compatible Responses API calls."""

from __future__ import annotations

import json
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
        )

