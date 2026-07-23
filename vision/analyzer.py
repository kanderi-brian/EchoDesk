import re
from typing import List, Optional

from llm import LLMEngine, OllamaProvider

from .screen_context import ScreenContext


class ScreenAnalyzer:
    """Converts OCR text into a structured screen context and natural explanation."""

    _NO_ENGINE = object()

    def __init__(self, llm_engine: Optional[LLMEngine] = _NO_ENGINE):
        if llm_engine is self._NO_ENGINE:
            try:
                self.llm_engine = LLMEngine(OllamaProvider())
            except Exception:
                self.llm_engine = None
        else:
            self.llm_engine = llm_engine

    def analyze(self, text):
        if not text or text == "No text detected.":
            return "I couldn't detect any readable text on the screen."

        context = self.build_context(text)

        explanation = self._explain_with_llm(context)
        if explanation:
            return explanation

        return self._build_structured_summary(context)

    def detect_application(self, text: str) -> Optional[str]:
        lower = text.lower()

        if "visual studio code" in lower or "vscode" in lower:
            return "Visual Studio Code"
        if "google chrome" in lower or "chrome" in lower:
            return "Google Chrome"
        if "mozilla firefox" in lower or "firefox" in lower:
            return "Firefox"
        if "microsoft edge" in lower or "edge" in lower:
            return "Microsoft Edge"
        if "powerpoint" in lower:
            return "PowerPoint"
        if "excel" in lower:
            return "Excel"
        if "word" in lower:
            return "Microsoft Word"
        if "powershell" in lower or "command prompt" in lower or "cmd.exe" in lower:
            return "Terminal"
        if "terminal" in lower:
            return "Terminal"
        if "settings" in lower:
            return "Settings"
        if "file explorer" in lower or "this pc" in lower or "quick access" in lower:
            return "File Explorer"
        return None

    def detect_window_title(self, text: str) -> Optional[str]:
        if not text:
            return None

        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in lines[:6]:
            if " - " in line or " | " in line:
                return line

        return lines[0] if lines else None

    def detect_sections(self, text: str) -> List[str]:
        lower = text.lower()
        sections: List[str] = []

        if any(key in lower for key in ("file edit view", "edit view help", "file edit selection view")):
            sections.append("Top menu")
        if any(key in lower for key in ("explorer", "outline", "project", "folders", "navigator", "sidebar", "side bar")):
            sections.append("Side bar")
        if any(key in lower for key in ("status bar", "ln", "col", "ins", "line ")):
            sections.append("Status bar")
        if any(key in lower for key in ("terminal", "bash", "powershell", "command prompt", "cmd.exe", "zsh")):
            sections.append("Terminal")
        if any(key in lower for key in ("output", "problems", "debug console", "console")):
            sections.append("Output")
        if any(key in lower for key in ("back", "forward", "nav", "navigation", "home")):
            sections.append("Navigation")

        if not sections:
            sections.append("Main content")

        return sections

    def detect_errors(self, text: str) -> List[str]:
        lower = text.lower()
        error_terms = [
            "traceback",
            "exception",
            "error",
            "failed",
            "module not found",
            "importerror",
            "attributerror",
            "404",
        ]

        return sorted({term for term in error_terms if term in lower})

    def detect_buttons(self, text: str) -> Optional[List[str]]:
        labels = [
            "OK",
            "Cancel",
            "Close",
            "Save",
            "Submit",
            "Next",
            "Back",
            "Apply",
            "Retry",
            "Update",
            "Install",
            "Continue",
            "Disconnect",
            "Delete",
        ]

        found = []
        for label in labels:
            if re.search(rf"\b{re.escape(label)}\b", text, re.IGNORECASE):
                found.append(label)

        return found if found else None

    def detect_menus(self, text: str) -> Optional[List[str]]:
        lower = text.lower()
        menus = []

        if any(key in lower for key in ("file edit view", "edit view help", "file edit selection view")):
            menus.append("Top menu")
        if any(key in lower for key in ("home insert draw", "insert layout design")):
            menus.append("Ribbon menu")

        return menus if menus else None

    def detect_warnings(self, text: str) -> Optional[List[str]]:
        if re.search(r"\bwarning\b", text, re.IGNORECASE):
            return ["Warning"]
        return None

    def detect_language(self, text: str) -> Optional[str]:
        if re.search(r"\b(bonjour|merci|au revoir|s'il vous plaît)\b", text, re.IGNORECASE):
            return "French"
        if re.search(r"\b(hola|gracias|adiós|por favor)\b", text, re.IGNORECASE):
            return "Spanish"
        if re.search(r"[\u4e00-\u9fff]+", text):
            return "Chinese"
        if re.search(r"[\u0400-\u04FF]+", text):
            return "Russian"
        if re.search(r"[\u0600-\u06FF]+", text):
            return "Arabic"
        return "English"

    def build_context(self, text: str) -> ScreenContext:
        return ScreenContext(
            application=self.detect_application(text),
            window_title=self.detect_window_title(text),
            visible_text=text,
            sections=self.detect_sections(text),
            buttons=self.detect_buttons(text),
            menus=self.detect_menus(text),
            errors=self.detect_errors(text),
            warnings=self.detect_warnings(text),
            language=self.detect_language(text),
        )

    def _explain_with_llm(self, context: ScreenContext) -> Optional[str]:
        if self.llm_engine is None:
            return None

        prompt = self._build_explanation_prompt(context)
        try:
            explanation = self.llm_engine.explain(prompt)
            if not isinstance(explanation, str) or not explanation.strip():
                return None
            if self._looks_like_error_output(explanation):
                return None
            return explanation
        except Exception:
            return None

    def _build_explanation_prompt(self, context: ScreenContext) -> str:
        lines = []
        if context.application:
            lines.append(f"You are using {context.application}.")
        if context.window_title:
            lines.append(f"The current window title appears to be '{context.window_title}'.")
        if context.language:
            lines.append(f"Detected language: {context.language}.")
        if context.sections:
            lines.append(f"Detected screen sections: {', '.join(context.sections)}.")
        if context.errors:
            lines.append(f"The screen contains the following errors or warnings: {', '.join(context.errors)}.")
        if context.warnings:
            lines.append(f"The screen contains warnings: {', '.join(context.warnings)}.")
        if context.buttons:
            lines.append(f"Visible buttons or actions include: {', '.join(context.buttons)}.")
        if context.menus:
            lines.append(f"Detected menu structures: {', '.join(context.menus)}.")

        lines.append("Visible text from the screen is below:\n")
        lines.append(context.visible_text or "")
        lines.append(
            "\nPlease explain the user's current screen in natural language and offer a helpful recommendation based on the application, layout, and any detected errors."
        )
        return "\n".join(lines)

    def _build_structured_summary(self, context: ScreenContext) -> str:
        parts = [
            f"Application: {context.application}." if context.application else None,
            f"Window title: {context.window_title}." if context.window_title else None,
            f"Language: {context.language}." if context.language else None,
            f"Sections: {', '.join(context.sections)}." if context.sections else None,
            f"Errors or warnings: {', '.join(context.errors)}." if context.errors else None,
            f"Buttons: {', '.join(context.buttons)}." if context.buttons else None,
        ]
        summary_text = [part for part in parts if part]
        summary_text.append("Visible screen text preview:")
        summary_text.append((context.visible_text or "").strip()[:600])
        return "\n".join(summary_text)

    def _looks_like_error_output(self, text: str) -> bool:
        lowered = text.lower()
        return "ollama" in lowered and "error" in lowered

