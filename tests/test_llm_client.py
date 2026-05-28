import json
import types
import unittest
from unittest import mock

from dino_game.llm_client import LLMClient


class LLMClientTest(unittest.TestCase):
    def test_create_response_posts_to_responses_endpoint_and_extracts_text(self):
        config = types.SimpleNamespace(
            api_key="sk-test",
            base_url="https://example.test/v1/",
            model="gpt-test",
        )
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return json.dumps({"output_text": "jump"}).encode()

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            captured["headers"] = dict(req.header_items())
            captured["payload"] = json.loads(req.data.decode())
            captured["timeout"] = timeout
            return FakeResponse()

        client = LLMClient(config)
        with mock.patch("urllib.request.urlopen", side_effect=fake_urlopen):
            response = client.create_response(
                prompt="plan",
                text_format={"type": "json_schema"},
                extract_text=lambda result: result["output_text"],
                timeout=7,
            )

        self.assertEqual(captured["url"], "https://example.test/v1/responses")
        self.assertEqual(captured["headers"]["Authorization"], "Bearer sk-test")
        self.assertEqual(captured["payload"]["model"], "gpt-test")
        self.assertEqual(captured["payload"]["input"], "plan")
        self.assertEqual(captured["payload"]["text"]["format"], {"type": "json_schema"})
        self.assertEqual(captured["timeout"], 7)
        self.assertEqual(response.raw_response, {"output_text": "jump"})
        self.assertEqual(response.response_text, "jump")

