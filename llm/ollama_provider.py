import requests
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout

from .provider import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """Provider for Ollama local LLM serving via HTTP."""

    def __init__(
        self,
        model: str = "phi3:latest",
        endpoint: str = "http://localhost:11434/api/generate",
        timeout: int = 120,
    ):
        self.model = model
        self.endpoint = endpoint
        self.timeout = timeout

    def generate(self, prompt: str) -> str:
        """Generate a response from the Ollama server for the given prompt."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }

        try:
            response = requests.post(self.endpoint, json=payload, timeout=self.timeout)
            response.raise_for_status()
            parsed = response.json()

            if isinstance(parsed, dict):
                if isinstance(parsed.get("response"), str):
                    return parsed["response"]

                if isinstance(parsed.get("text"), str):
                    return parsed["text"]

                results = parsed.get("results")
                if isinstance(results, list) and results:
                    first = results[0]
                    if isinstance(first, dict) and isinstance(first.get("output"), str):
                        return first["output"]

            return f"Unexpected Ollama response: {parsed}"
        except Timeout:
            return "OllamaProvider timeout error: server did not respond in time."
        except ConnectionError as error:
            return f"OllamaProvider connection error: {error}."
        except HTTPError as error:
            status_code = error.response.status_code if error.response is not None else "unknown"
            reason = error.response.reason if error.response is not None else "unknown"
            return f"OllamaProvider HTTP error {status_code}: {reason}."
        except ValueError as error:
            return f"OllamaProvider invalid JSON response: {error}."
        except RequestException as error:
            return f"OllamaProvider request error: {error}."
        except Exception as error:
            return f"OllamaProvider unexpected error: {error}."
