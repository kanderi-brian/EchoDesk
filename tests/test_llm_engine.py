import unittest
from unittest.mock import Mock, patch

from llm.engine import LLMEngine
from llm.ollama_provider import OllamaProvider


class TestLLMEngineModule(unittest.TestCase):

    def test_ask_delegates_to_the_provider(self):
        provider = Mock()
        provider.generate.return_value = "generated response"
        engine = LLMEngine(provider=provider)

        response = engine.ask("Hello")

        provider.generate.assert_called_once_with("Hello")
        self.assertEqual(response, "generated response")

    def test_engine_uses_default_ollama_provider_when_none_provided(self):
        engine = LLMEngine()

        self.assertIsInstance(engine.provider, OllamaProvider)
        self.assertEqual(engine.provider.model, "phi3:latest")
        self.assertIsNone(engine.provider.timeout)


class TestOllamaProviderModule(unittest.TestCase):

    @patch("llm.ollama_provider.requests.get")
    def test_is_running_returns_false_without_daemon(self, mock_get):
        from requests.exceptions import ConnectionError
        mock_get.side_effect = ConnectionError("refused")
        self.assertFalse(OllamaProvider().is_running())

    @patch("llm.ollama_provider.requests.get")
    def test_is_running_closes_health_response(self, mock_get):
        response = Mock(); response.ok = True; mock_get.return_value = response
        self.assertTrue(OllamaProvider().is_running())
        response.close.assert_called_once()

    @patch("llm.ollama_provider.requests.post")
    def test_generate_returns_response_text(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"response": "hello"}
        mock_post.return_value = mock_response

        provider = OllamaProvider()
        output = provider.generate("test prompt")

        self.assertEqual(output, "hello")
        mock_post.assert_called_once()

    @patch("llm.ollama_provider.requests.post")
    def test_generate_parses_phi3_latest_response(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "model": "phi3:latest",
            "created_at": "2026-07-23T15:00:00Z",
            "response": "Hello from Phi-3!",
            "done": True,
        }
        mock_post.return_value = mock_response

        provider = OllamaProvider()
        self.assertEqual(provider.generate("test prompt"), "Hello from Phi-3!")

    @patch("llm.ollama_provider.requests.post")
    def test_generate_handles_connection_error(self, mock_post):
        from requests.exceptions import ConnectionError

        mock_post.side_effect = ConnectionError("connection refused")

        provider = OllamaProvider()
        output = provider.generate("test prompt")

        self.assertIn("connection error", output.lower())

    @patch("llm.ollama_provider.requests.post")
    def test_generate_handles_timeout(self, mock_post):
        from requests.exceptions import Timeout

        mock_post.side_effect = Timeout("timed out")

        provider = OllamaProvider()
        output = provider.generate("test prompt")

        self.assertIn("timeout error", output.lower())

    @patch("llm.ollama_provider.requests.post")
    def test_generate_handles_invalid_json(self, mock_post):
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_post.return_value = mock_response

        provider = OllamaProvider()
        output = provider.generate("test prompt")

        self.assertIn("invalid json", output.lower())


if __name__ == "__main__":
    unittest.main()
