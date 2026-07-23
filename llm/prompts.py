"""Reusable prompt templates for the LLM reasoning engine."""

DEFAULT_ASSISTANT = (
    "You are EchoDesk, a helpful AI desktop assistant. Answer clearly, concisely, and in a friendly tone."
)

CODING_ASSISTANT = (
    "You are a coding assistant. Provide accurate code examples, explanations, and best practices."
)

SCREEN_ANALYSIS = (
    "Analyze screen content in detail and describe what is visible, what is important, and what actions might be useful."
)

PLANNING = (
    "Suggest a step-by-step plan to accomplish the user's requested task using available tools."
)

ASK_PROMPT = "{prompt}"
SUMMARIZE_PROMPT = (
    "Summarize the following text in a clear and concise way:\n\n"
    "{text}\n\nSummary:"
)
EXPLAIN_PROMPT = (
    "Explain the following content in plain language and provide helpful context:\n\n"
    "{text}\n\nExplanation:"
)
REASON_PROMPT = (
    "Use the context below to answer the question precisely and with reasoning:\n\n"
    "Context:\n{context}\n\nQuestion:\n{question}\n\nAnswer:"
)
SCREEN_ANALYSIS_PROMPT = (
    "Analyze the following screen content and describe what is visible, what is important, and what actions might be useful:\n\n"
    "{text}\n\nAnalysis:"
)
INTERNET_SUMMARY_PROMPT = (
    "Summarize the key points from the following internet content so it is easy to understand:\n\n"
    "{text}\n\nSummary:"
)
KNOWLEDGE_EXPANSION_PROMPT = (
    "Expand on the following knowledge item by adding detail, examples, and useful next steps:\n\n"
    "{text}\n\nExpansion:"
)
