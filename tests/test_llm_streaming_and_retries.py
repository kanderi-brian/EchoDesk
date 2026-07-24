import unittest
from unittest.mock import Mock, patch

import requests

from llm.ollama_provider import OllamaProvider
from llm.engine import LLMEngine


class FakeStreamResponse:
    def __init__(self, lines):
        self._lines = lines
        self.status_code = 200

    def iter_lines(self, decode_unicode=True):
        for l in self._lines:
            yield l

    def raise_for_status(self):
        return None

    def json(self):
        raise ValueError("No JSON")


class TestOllamaStreamingAndRetries(unittest.TestCase):
    @patch("llm.ollama_provider.requests.post")
    def test_streaming_assembly(self, mock_post):
        # simulate SSE lines
        lines = [b'data: {"text": "Hello"}\n', b'data: {"text": " world"}\n']
        mock_post.return_value = FakeStreamResponse(lines)

        provider = OllamaProvider()
        out = provider.generate("prompt")
        self.assertIn("Hello", out)
        self.assertIn("world", out)

    @patch("llm.ollama_provider.requests.post")
    def test_retry_on_timeout_then_success(self, mock_post):
        from requests.exceptions import Timeout

        # First two attempts raise Timeout, third returns simple JSON
        def side_effect(*args, **kwargs):
            if side_effect.count < 2:
                side_effect.count += 1
                raise Timeout("timed out")
            mock_resp = Mock()
            mock_resp.raise_for_status.return_value = None
            mock_resp.iter_lines.return_value = []
            mock_resp.json.return_value = {"text": "final"}
            return mock_resp

        side_effect.count = 0
        mock_post.side_effect = side_effect

        provider = OllamaProvider()
        out = provider.generate("prompt")
        self.assertEqual(out, "final")


class DummyProvider:
    def __init__(self):
        self.calls = []

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        return "ok"


class TestPromptTruncation(unittest.TestCase):
    def test_llm_engine_truncates_large_prompt(self):
        provider = DummyProvider()
        engine = LLMEngine(provider=provider)
        long_context = "A" * 10000
        resp = engine.ask("Short prompt", context=long_context)
        # provider was called and received a truncated prompt
        self.assertTrue(len(provider.calls[0]) <= engine.MAX_PROMPT_LENGTH)


if __name__ == '__main__':
    unittest.main()
