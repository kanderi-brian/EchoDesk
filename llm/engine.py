import logging
from typing import Optional

from .ollama_provider import OllamaProvider
from .provider import BaseLLMProvider
from .prompts import ASK_PROMPT, CONTEXT_PROMPT, EXPLAIN_PROMPT, REASON_PROMPT, SUMMARIZE_PROMPT


class LLMEngine:
    """Modular reasoning engine that delegates generation to an LLM provider."""

    MAX_PROMPT_LENGTH = 4000
    MAX_CONTEXT_LENGTH = 2000

    def __init__(self, provider: Optional[BaseLLMProvider] = None):
        if provider is None:
            provider = OllamaProvider()
        self.provider = provider
        self.logger = logging.getLogger("echodesk.llm")

    def ask(self, prompt: str, context: str | None = None) -> str:
        """Ask the provider a direct prompt and return its response."""
        if context and isinstance(context, str) and context.strip():
            full_prompt = CONTEXT_PROMPT.format(context=context.strip(), prompt=prompt)
        else:
            full_prompt = ASK_PROMPT.format(prompt=prompt)

        truncated_prompt = self._truncate_prompt(full_prompt)
        self.logger.debug("LLM prompt size=%d", len(truncated_prompt))
        return self.provider.generate(truncated_prompt)

    def summarize(self, text: str) -> str:
        """Ask the provider to summarize the provided text."""
        prompt = SUMMARIZE_PROMPT.format(text=text)
        return self.provider.generate(self._truncate_prompt(prompt))

    def explain(self, text: str) -> str:
        """Ask the provider to explain the provided content."""
        prompt = EXPLAIN_PROMPT.format(text=text)
        return self.provider.generate(self._truncate_prompt(prompt))

    def reason(self, question: str, context: str) -> str:
        """Ask the provider to reason over context and answer a question."""
        prompt = REASON_PROMPT.format(question=question, context=context)
        return self.provider.generate(self._truncate_prompt(prompt))

    def _truncate_prompt(self, prompt: str) -> str:
        if not isinstance(prompt, str):
            return str(prompt)

        if len(prompt) <= self.MAX_PROMPT_LENGTH:
            return prompt

        self.logger.warning(
            "Truncating prompt from %d to %d characters to avoid oversized LLM requests.",
            len(prompt),
            self.MAX_PROMPT_LENGTH,
        )

        return prompt[: self.MAX_PROMPT_LENGTH]
