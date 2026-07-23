import json
import unittest
from unittest.mock import Mock, patch

from llm.engine import LLMEngine
from llm.ollama_provider import OllamaProvider
from llm.provider import BaseLLMProvider


class DummyProvider(BaseLLMProvider):
    def __init__(self):
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return f"Echo: {prompt}"


class TestLLMEngine(unittest.TestCase):
    def test_ask_delegates_to_provider(self):
        provider = DummyProvider()
        engine = LLMEngine(provider)

        response = engine.ask("Hello")

        self.assertEqual(response, "Echo: " + provider.prompts[0])

    def test_summarize_delegates_to_provider(self):
        provider = DummyProvider()
        engine = LLMEngine(provider)
        response = engine.summarize("Some long text.")

        self.assertIn("Some long text.", provider.prompts[0])
        self.assertTrue(response.startswith("Echo:"))

    def test_explain_delegates_to_provider(self):
        provider = DummyProvider()
        engine = LLMEngine(provider)
        response = engine.explain("Explain this")

        self.assertIn("Explain this", provider.prompts[0])
        self.assertTrue(response.startswith("Echo:"))

    def test_reason_delegates_to_provider(self):
        provider = DummyProvider()
        engine = LLMEngine(provider)
        response = engine.reason("Why?", "Because")

        self.assertIn("Why?", provider.prompts[0])
        self.assertIn("Because", provider.prompts[0])
        self.assertTrue(response.startswith("Echo:"))


class TestOllamaProvider(unittest.TestCase):
    @patch("llm.ollama_provider.requests.post")
    def test_generate_returns_response_text(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"text": "hello"}
        mock_post.return_value = mock_response

        provider = OllamaProvider()
        output = provider.generate("test prompt")

        self.assertEqual(output, "hello")
        mock_post.assert_called_once()

    @patch("llm.ollama_provider.requests.post")
    def test_generate_handles_invalid_json(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_post.return_value = mock_response

        provider = OllamaProvider()
        output = provider.generate("test prompt")

        self.assertIn("invalid json", output.lower())

    @patch("llm.ollama_provider.requests.post")
    def test_generate_handles_timeout(self, mock_post):
        from requests.exceptions import Timeout

        mock_post.side_effect = Timeout("timed out")

        provider = OllamaProvider()
        output = provider.generate("test prompt")

        self.assertIn("timeout error", output.lower())

    @patch("llm.ollama_provider.requests.post")
    def test_generate_handles_connection_error(self, mock_post):
        from requests.exceptions import ConnectionError

        mock_post.side_effect = ConnectionError("connection refused")

        provider = OllamaProvider()
        output = provider.generate("test prompt")

        self.assertIn("connection error", output.lower())


if __name__ == "__main__":
    unittest.main()
