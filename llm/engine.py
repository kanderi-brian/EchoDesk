from typing import Optional

from .ollama_provider import OllamaProvider
from .provider import BaseLLMProvider
from .prompts import ASK_PROMPT, EXPLAIN_PROMPT, REASON_PROMPT, SUMMARIZE_PROMPT


class LLMEngine:
    """Modular reasoning engine that delegates generation to an LLM provider."""

    def __init__(self, provider: Optional[BaseLLMProvider] = None):
        if provider is None:
            provider = OllamaProvider()
        self.provider = provider

    def ask(self, prompt: str) -> str:
        """Ask the provider a direct prompt and return its response."""
        full_prompt = ASK_PROMPT.format(prompt=prompt)
        return self.provider.generate(full_prompt)

    def summarize(self, text: str) -> str:
        """Ask the provider to summarize the provided text."""
        prompt = SUMMARIZE_PROMPT.format(text=text)
        return self.provider.generate(prompt)

    def explain(self, text: str) -> str:
        """Ask the provider to explain the provided content."""
        prompt = EXPLAIN_PROMPT.format(text=text)
        return self.provider.generate(prompt)

    def reason(self, question: str, context: str) -> str:
        """Ask the provider to reason over context and answer a question."""
        prompt = REASON_PROMPT.format(question=question, context=context)
        return self.provider.generate(prompt)
