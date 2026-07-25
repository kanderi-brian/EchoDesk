import json
import html
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol
from urllib.error import HTTPError, URLError

from llm.engine import LLMEngine


@dataclass
class SearchResult:
    """Structured provider search result."""

    success: bool
    summary: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None


class SearchProvider(Protocol):
    """Provider abstraction for internet search services."""

    def search(self, query: str, timeout: float) -> SearchResult:
        """Perform a search and return a SearchResult."""
        ...


class DuckDuckGoInstantAnswerProvider:
    """DuckDuckGo provider using the Instant Answer JSON API."""

    API_URL = "https://api.duckduckgo.com/"
    USER_AGENT = "EchoDesk InternetEngine/1.0"

    def search(self, query: str, timeout: float) -> SearchResult:
        if not isinstance(query, str) or not query.strip():
            return SearchResult(False, error="The search query was empty.")

        url = self._build_url(query)

        try:
            request = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    return SearchResult(False, error=f"Search provider returned status {response.status}.")

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


# Kept as an alias for callers using the original public provider name.
DuckDuckGoProvider = DuckDuckGoInstantAnswerProvider


class DuckDuckGoHtmlProvider:
    """DuckDuckGo provider scraping HTML results for structured search data."""

    API_URL = "https://html.duckduckgo.com/html/"
    USER_AGENT = "EchoDesk InternetEngine/1.0"

    def search(self, query: str, timeout: float) -> SearchResult:
        if not isinstance(query, str) or not query.strip():
            return SearchResult(False, error="The search query was empty.")

        url = f"{self.API_URL}?{urllib.parse.urlencode({'q': query})}"

        try:
            request = urllib.request.Request(url, headers={"User-Agent": self.USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    return SearchResult(False, error=f"Search provider returned status {response.status}.")
                html = response.read().decode("utf-8", errors="ignore")
        except HTTPError:
            return SearchResult(False, error="The search provider could not complete the request.")
        except URLError:
            return SearchResult(False, error="I could not reach the internet. Please check your connection.")
        except Exception:
            return SearchResult(False, error="The search provider failed unexpectedly.")

        results = self._parse_results(html)
        if not results:
            return SearchResult(False, error="No search results were returned by the provider.")

        summary = self._summarize_results(results)
        return SearchResult(True, summary=summary, results=results)

    def _parse_results(self, html: str) -> List[Dict[str, Any]]:
        titles = re.findall(
            r'<a[^>]*class=["\"][^"\"]*result__a[^"\"]*["\"][^>]*href=["\"]([^"\"]+)["\"][^>]*>(.*?)</a>',
            html,
            flags=re.S | re.I,
        )
        snippets = re.findall(
            r'<a[^>]*class=["\"][^"\"]*result__snippet[^"\"]*["\"][^>]*>(.*?)</a>',
            html,
            flags=re.S | re.I,
        )

        results: List[Dict[str, Any]] = []
        for index, (url, title_html) in enumerate(titles[:10]):
            title = self._clean_html(title_html)
            snippet = self._clean_html(snippets[index]) if index < len(snippets) else None
            if title and url:
                results.append(
                    {
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                        "content": None,
                    }
                )
            if len(results) >= 5:
                break

        return results

    def _summarize_results(self, results: List[Dict[str, Any]]) -> str:
        if not results:
            return ""

        lines = []
        for result in results[:3]:
            title = result.get("title") or "No title"
            snippet = result.get("snippet") or "No snippet available."
            lines.append(f"{title}: {snippet}")

        return " \n".join(lines)

    def _clean_html(self, html: str) -> str:
        text = re.sub(r"<[^>]+>", "", html)
        text = html_module_unescape(text)
        text = re.sub(r"\s+", " ", text).strip()
        return text


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
        self.providers = providers if providers is not None else [DuckDuckGoHtmlProvider(), DuckDuckGoInstantAnswerProvider()]
        self.llm_engine = llm_engine

    def search_structured(self, query: str) -> dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            return {
                "status": "failed",
                "query": query,
                "error": "The search query was empty.",
            }

        errors: List[str] = []
        for provider in self.providers:
            try:
                result = provider.search(query, self.timeout)
            except Exception:
                errors.append("A search provider failed unexpectedly.")
                continue

            if result.success:
                output: dict[str, Any] = {
                    "status": "success",
                    "query": query,
                    "summary": result.summary or "",
                    "results": result.results or [],
                }
                if self.llm_engine:
                    if output["results"]:
                        output["summary"] = self._summarize_results_with_llm(output["results"], query)
                    elif output["summary"]:
                        output["summary"] = self._summarize_text_with_llm(output["summary"])
                return output

            errors.append(result.error or "The search provider did not return a usable result.")

        return {
            "status": "failed",
            "query": query,
            "error": " ".join(errors).strip() or "No internet results were available.",
        }

    def search(self, query: str) -> str:
        structured = self.search_structured(query)
        if structured.get("status") == "success":
            summary = structured.get("summary")
            if isinstance(summary, str) and summary.strip():
                return summary
            results = structured.get("results") or []
            if results:
                return self._format_results_summary(results)

        error = structured.get("error")
        if error:
            return f"{self.FALLBACK_MESSAGE} {error}"
        return self.FALLBACK_MESSAGE

    def _summarize_results_with_llm(self, results: List[Dict[str, Any]], query: str) -> str:
        if self.llm_engine is None:
            return self._format_results_summary(results)

        text = self._format_results_for_llm(results, query)
        try:
            summary = self.llm_engine.summarize(text)
            if isinstance(summary, str) and summary.strip() and not self._looks_like_llm_error(summary):
                return summary.strip()
        except Exception:
            pass
        return self._format_results_summary(results)

    def _summarize_text_with_llm(self, text: str) -> str:
        """Summarize provider text while retaining a useful response on LLM failure."""
        if self.llm_engine is None:
            return text
        try:
            summary = self.llm_engine.summarize(text[:2000])
            if isinstance(summary, str) and summary.strip() and not self._looks_like_llm_error(summary):
                return summary.strip()
        except Exception:
            pass
        return text

    def _format_results_for_llm(self, results: List[Dict[str, Any]], query: str) -> str:
        lines = [f"Query: {query}"]
        for result in results[:3]:
            lines.append(f"Title: {result.get('title')}")
            lines.append(f"URL: {result.get('url')}")
            if result.get("snippet"):
                lines.append(f"Snippet: {result.get('snippet')}")
        return "\n".join(lines)

    def _format_results_summary(self, results: List[Dict[str, Any]]) -> str:
        if not results:
            return "I could not summarize the search results."

        lines = []
        for result in results[:3]:
            title = result.get("title") or "Unknown title"
            snippet = result.get("snippet") or "No snippet available."
            lines.append(f"{title}: {snippet}")
        return "\n".join(lines)

    def _looks_like_llm_error(self, response: str) -> bool:
        lowered = response.lower()
        return (
            response.startswith("OllamaProvider")
            or ("ollama" in lowered and "error" in lowered)
            or ("could not" in lowered and "ollama" in lowered)
        )


def html_module_unescape(value: str) -> str:
    """Decode search-result entities without exposing parser internals."""
    return html.unescape(value)
