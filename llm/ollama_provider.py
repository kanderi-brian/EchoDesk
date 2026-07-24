import json
import logging
import time

import requests
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout

from .provider import BaseLLMProvider


class OllamaProvider(BaseLLMProvider):
    """Provider for Ollama local LLM serving via HTTP.

    Supports streaming responses, exponential backoff retry, and robust parsing
    of various Ollama response formats. Returns friendly error messages on
    failure.
    """

    MAX_RETRIES = 3
    BACKOFF_BASE = 0.2

    def __init__(
        self,
        model: str = "phi3:latest",
        endpoint: str = "http://localhost:11434/api/generate",
        timeout: int = 300,
    ):
        self.model = model
        self.endpoint = endpoint
        self.timeout = timeout
        self.logger = logging.getLogger("echodesk.llm.ollama_provider")

    def generate(self, prompt: str) -> str:
        """Generate a response from the Ollama server for the given prompt.

        Attempts streaming first, falls back to JSON body parsing, and retries on
        transient network errors.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
        }

        last_error = None
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                self.logger.debug("Ollama request attempt %d", attempt)
                response = requests.post(self.endpoint, json=payload, timeout=self.timeout, stream=True)
                response.raise_for_status()

                # Try to read a streaming response first
                streamed = self._read_stream(response)
                if streamed is not None:
                    return streamed

                # If no streaming data found, try to parse the JSON body
                try:
                    parsed = response.json()
                except ValueError as e:
                    last_error = f"OllamaProvider invalid JSON response: {e}."
                    self.logger.warning("Invalid JSON from Ollama on attempt %d: %s", attempt, e)
                    raise

                return self._parse_response(parsed)

            except Timeout as error:
                last_error = f"OllamaProvider timeout error: server did not respond in time."
                self.logger.warning("Ollama timeout on attempt %d: %s", attempt, error)
            except ConnectionError as error:
                last_error = f"OllamaProvider connection error: {error}."
                self.logger.warning("Ollama connection error on attempt %d: %s", attempt, error)
            except HTTPError as error:
                status_code = error.response.status_code if error.response is not None else "unknown"
                reason = error.response.reason if error.response is not None else "unknown"
                last_error = f"OllamaProvider HTTP error {status_code}: {reason}."
                self.logger.warning("Ollama HTTP error on attempt %d: %s", attempt, last_error)
                # For HTTP errors we do not retry normally
                break
            except RequestException as error:
                last_error = f"OllamaProvider request error: {error}."
                self.logger.warning("Ollama request exception on attempt %d: %s", attempt, error)
            except ValueError as error:
                # JSON decode errors bubbled up earlier
                last_error = f"OllamaProvider invalid JSON response: {error}."
                self.logger.warning("Ollama invalid JSON on attempt %d: %s", attempt, error)
            except Exception as error:
                last_error = f"OllamaProvider unexpected error: {error}."
                self.logger.warning("Ollama unexpected error on attempt %d: %s", attempt, error)

            if attempt < self.MAX_RETRIES:
                backoff = self.BACKOFF_BASE * (2 ** (attempt - 1))
                self.logger.debug("Retrying Ollama after %.1fs backoff", backoff)
                time.sleep(backoff)

        return last_error or "OllamaProvider failed to generate a response."

    def _read_stream(self, response: requests.Response) -> str | None:
        """Read streaming response (SSE-like) and assemble text chunks.

        Returns the assembled text if any chunks found, otherwise None.
        """
        try:
            collected = []
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue

                # Ensure we are working with text, not bytes
                if isinstance(raw_line, bytes):
                    try:
                        line = raw_line.decode("utf-8", errors="replace").strip()
                    except Exception:
                        line = str(raw_line)
                else:
                    line = str(raw_line).strip()

                # SSE-style prefixed data
                if line.startswith("data:"):
                    line = line[len("data:"):].strip()

                # Try parsing JSON chunk
                try:
                    part = json.loads(line)
                except Exception:
                    part = line

                if isinstance(part, dict):
                    # phi/ollama chunk fields
                    if isinstance(part.get("text"), str):
                        collected.append(part.get("text"))
                        continue
                    if isinstance(part.get("response"), str):
                        collected.append(part.get("response"))
                        continue
                    results = part.get("results")
                    if isinstance(results, list) and results:
                        first = results[0]
                        if isinstance(first, dict) and isinstance(first.get("output"), str):
                            collected.append(first.get("output"))
                            continue
                    # fallback: stringify
                    try:
                        collected.append(json.dumps(part))
                    except Exception:
                        collected.append(str(part))
                else:
                    collected.append(str(part))

            if collected:
                return "".join(collected)
            return None
        except Exception as err:
            self.logger.debug("Error reading Ollama stream: %s", err)
            return None

    def _parse_response(self, parsed: object) -> str:
        """Parse non-streamed JSON response from Ollama into a plain string."""
        try:
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

            # fallback
            return str(parsed)
        except Exception as e:
            self.logger.debug("Failed to parse Ollama response: %s", e)
            return "OllamaProvider produced an unexpected response format."
