import json
import types
import unittest
from unittest import mock

from dino_game.llm_client import CodexLLMClient, LLMClient


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
                return json.dumps({
                    "output_text": "jump",
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 20,
                        "total_tokens": 120,
                    },
                }).encode()

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
        self.assertEqual(response.raw_response, {
            "output_text": "jump",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 20,
                "total_tokens": 120,
            },
        })
        self.assertEqual(response.response_text, "jump")
        self.assertEqual(response.token_usage, {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
        })

    def test_codex_client_runs_codex_exec_and_reads_stdout(self):
        completed = types.SimpleNamespace(
            returncode=0,
            stdout='{"start_frame": 10, "actions": ["jump"]}\n',
            stderr="progress\ntokens used\n7,470\n",
        )
        schema = {
            "type": "object",
            "properties": {
                "start_frame": {"type": "integer", "enum": [10]},
                "actions": {"type": "array", "minItems": 1, "maxItems": 1},
            },
            "required": ["start_frame", "actions"],
            "additionalProperties": False,
        }
        captured = {}

        def fake_run(command, **kwargs):
            schema_path = command[command.index("--output-schema") + 1]
            captured["schema_path"] = schema_path
            with open(schema_path, "r", encoding="utf-8") as f:
                captured["schema"] = json.load(f)
            return completed

        with mock.patch("subprocess.run", side_effect=fake_run) as run:
            client = CodexLLMClient()
            response = client.create_response(
                prompt="plan",
                text_format={
                    "type": "json_schema",
                    "name": "dino_action_window",
                    "schema": schema,
                },
                extract_text=lambda result: result["stdout"],
                timeout=9,
            )

        run.assert_called_once_with(
            [
                "codex",
                "exec",
                "--sandbox",
                "read-only",
                "--ephemeral",
                "--skip-git-repo-check",
                "--output-schema",
                mock.ANY,
                "plan",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        command = run.call_args.args[0]
        schema_path = command[command.index("--output-schema") + 1]
        self.assertEqual(captured.get("schema_path"), schema_path)
        self.assertEqual(captured.get("schema"), schema)
        self.assertEqual(response.response_text, '{"start_frame": 10, "actions": ["jump"]}')
        self.assertEqual(response.raw_response["stdout"], '{"start_frame": 10, "actions": ["jump"]}\n')
        self.assertEqual(response.raw_response["stderr"], "progress\ntokens used\n7,470\n")
        self.assertEqual(response.raw_response["returncode"], 0)
        self.assertEqual(response.token_usage, {
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": 7470,
        })

    def test_codex_client_hides_stdout_on_nonzero_exit(self):
        completed = types.SimpleNamespace(
            returncode=1,
            stdout='{"start_frame": 10, "actions": ["jump"]}\n',
            stderr="failed\n",
        )

        with mock.patch("subprocess.run", return_value=completed):
            client = CodexLLMClient()
            response = client.create_response(
                prompt="plan",
                text_format={"type": "json_schema"},
                extract_text=lambda result: result["stdout"],
            )

        self.assertEqual(response.response_text, "")
        self.assertEqual(response.raw_response["stdout"], '{"start_frame": 10, "actions": ["jump"]}\n')
        self.assertEqual(response.raw_response["returncode"], 1)
        self.assertIn("error", response.raw_response)
