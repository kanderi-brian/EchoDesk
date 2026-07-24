import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import List, Optional, Protocol
from urllib.error import HTTPError, URLError

from llm.engine import LLMEngine


@dataclass
class SearchResult:
    """Structured provider search result."""

    success: bool
    summary: Optional[str] = None
    error: Optional[str] = None


class SearchProvider(Protocol):
    """Provider abstraction for internet search services."""

    def search(self, query: str, timeout: float) -> SearchResult:
        """Perform a search and return a SearchResult."""
        ...


class DuckDuckGoProvider:
    """DuckDuckGo provider using the Instant Answer JSON API."""

    API_URL = "https://api.duckduckgo.com/"
    USER_AGENT = "EchoDesk InternetEngine/1.0"

    def search(self, query: str, timeout: float) -> SearchResult:
        if not isinstance(query, str) or not query.strip():
            return SearchResult(False, error="The search query was empty.")

        url = self._build_url(query)

        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": self.USER_AGENT},
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    return SearchResult(
                        False,
                        error=f"Search provider returned status {response.status}.",
                    )

                payload = response.read()
                data = json.loads(payload.decode("utf-8", errors="ignore"))
        except HTTPError:
            return SearchResult(False, error="The search provider could not complete the request.")
        except URLError:
            return SearchResult(False, error="I could not reach the internet. Please check your connection.")
        except json.JSONDecodeError:
            return SearchResult(False, error="The search provider returned invalid data.")
        except Exception:
            return SearchResult(False, error="The search provider failed unexpectedly.")

        summary = self._summarize_result(data)
        if summary:
            return SearchResult(True, summary=summary)

        return SearchResult(False, error="The search provider returned no useful results.")

    def _build_url(self, query: str) -> str:
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }
        return f"{self.API_URL}?{urllib.parse.urlencode(params)}"

    def _summarize_result(self, data: dict) -> Optional[str]:
        if not isinstance(data, dict):
            return None

        answer = self._extract_string(data, "Answer")
        if answer:
            return self._clean(answer)

        abstract = self._extract_string(data, "AbstractText")
        if abstract:
            return self._clean(abstract)

        related = self._extract_related_topics(data)
        if related:
            return related

        if self._extract_string(data, "Redirect"):
            return "I found a related result but could not summarize it cleanly."

        return None

    def _extract_string(self, data: dict, key: str) -> Optional[str]:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _extract_related_topics(self, data: dict) -> Optional[str]:
        topics = data.get("RelatedTopics")
        if not isinstance(topics, list):
            return None

        for item in topics:
            if isinstance(item, dict):
                text = self._extract_string(item, "Text")
                if text:
                    return self._clean(text)

                nested = item.get("Topics")
                if isinstance(nested, list):
                    for child in nested:
                        if isinstance(child, dict):
                            child_text = self._extract_string(child, "Text")
                            if child_text:
                                return self._clean(child_text)

        return None

    def _clean(self, text: str) -> str:
        return " ".join(text.split())


class InternetEngine:
    """A reusable internet search engine with provider abstraction."""

    FALLBACK_MESSAGE = (
       "I couldn't find a clear answer from the internet right now. "
       "Please try again later or ask something else."
    )

    def __init__(
       self,
       providers: Optional[List[SearchProvider]] = None,
       timeout: float = 5.0,
       llm_engine: Optional[LLMEngine] = None,
    ) -> None:
       self.timeout = float(timeout)
       self.providers = providers if providers is not None else [DuckDuckGoProvider()]
       self.llm_engine = llm_engine

    def search(self, query: str) -> str:
        if not isinstance(query, str) or not query.strip():
            return self.FALLBACK_MESSAGE

        last_error: Optional[str] = None
        for provider in self.providers:
            try:
                result = provider.search(query, self.timeout)
            except Exception:
                last_error = "A search provider failed unexpectedly."
                continue

            if result.success and result.summary:
                return self._summarize_with_llm(result.summary)

            last_error = result.error or last_error

        if last_error:
            return f"{self.FALLBACK_MESSAGE} {last_error}"

        return self.FALLBACK_MESSAGE

    def _summarize_with_llm(self, text: str) -> str:
        if self.llm_engine is None:
            return text

        # Prevent sending oversized internet content to the LLM
        max_chars = 2000
        safe_text = text if len(text) <= max_chars else text[:max_chars]
        try:
            summary = self.llm_engine.summarize(safe_text)
            if not isinstance(summary, str) or not summary.strip():
                return text

            if self._looks_like_llm_error(summary):
                return text

            return summary
        except Exception:
            return text

    def _looks_like_llm_error(self, response: str) -> bool:
        lowered = response.lower()
        return (
            response.startswith("OllamaProvider")
            or "ollama" in lowered and "error" in lowered
            or "could not" in lowered and "ollama" in lowered
        )
