"""Lightweight, extensible UI control detection for captured desktop images."""

from __future__ import annotations

from typing import Any, Iterable

from .models import UIElement, UIWindow


class UIUnderstanding:
    """Turns OCR and visual cues into semantic controls.

    The heuristics form a dependency-free baseline.  Application profiles can
    refine the output later without changing the scene or automation APIs.
    """

    TYPE_WORDS = {
        "button": ("ok", "cancel", "save", "open", "close", "apply", "submit", "next", "back", "download", "delete"),
        "text_field": ("username", "password", "search", "email", "textbox", "input", "address"),
        "checkbox": ("checkbox", "check box", "remember me", "enable ", "agree"),
        "radio_button": ("radio", "option "),
        "dropdown": ("dropdown", "select", "choose ", "combo box"),
        "tab": ("home", "insert", "view", "settings", "general", "advanced"),
        "menu": ("file", "edit", "help", "tools", "window"),
        "toolbar": ("toolbar",),
        "status_bar": ("status", "ready"),
        "dialog": ("dialog", "warning", "error", "confirm"),
        "scroll_bar": ("scroll",),
    }
    INTERACTIVE = {"button", "checkbox", "radio_button", "dropdown", "tab", "menu", "icon", "context_menu"}

    def detect(self, width: int, height: int, ocr_entries: Iterable[dict[str, Any]], active_title: str = "") -> tuple[list[UIElement], list[UIWindow]]:
        entries = list(ocr_entries)
        elements: list[UIElement] = []
        for entry in entries:
            text = str(entry.get("text") or "").strip()
            if not text:
                continue
            kind = self._classify(text)
            box = self._box(entry.get("box"), width, height)
            confidence = float(entry.get("confidence") or 0.5)
            elements.append(UIElement(type=kind, label=text, ocr_text=text, confidence=confidence, bounding_box=box, clickable=kind in self.INTERACTIVE, editable=kind == "text_field"))
        windows = self._detect_windows(width, height, entries, active_title)
        elements.extend(self._structural_elements(width, height, elements))
        return elements, windows

    def _classify(self, text: str) -> str:
        normalized = text.casefold()
        for kind, words in self.TYPE_WORDS.items():
            if any(word in normalized for word in words):
                return kind
        if normalized.endswith(("…", ">")):
            return "menu"
        return "text"

    def _detect_windows(self, width: int, height: int, entries: list[dict[str, Any]], active_title: str) -> list[UIWindow]:
        title = active_title or (str(entries[0].get("text") or "") if entries else "Desktop")
        return [UIWindow(title=title, label=title, ocr_text=title, confidence=0.8 if active_title else 0.5, bounding_box=(0, 0, width, height), active=True, clickable=False)]

    def _structural_elements(self, width: int, height: int, elements: list[UIElement]) -> list[UIElement]:
        detected = {item.type for item in elements}
        structural: list[UIElement] = []
        if any(item.type in {"menu", "tab"} for item in elements) and "toolbar" not in detected:
            structural.append(UIElement(type="toolbar", label="Toolbar", confidence=0.45, bounding_box=(0, 0, width, min(100, height)), clickable=False))
        if "status_bar" not in detected:
            structural.append(UIElement(type="status_bar", label="Status bar", confidence=0.25, bounding_box=(0, max(0, height - 28), width, min(28, height)), clickable=False))
        return structural

    @staticmethod
    def _box(raw: Any, width: int, height: int) -> tuple[int, int, int, int]:
        if isinstance(raw, (list, tuple)) and len(raw) == 4:
            x1, y1, x2, y2 = (int(value) for value in raw)
            # OCR commonly yields two corners; accept already-normalized boxes too.
            return (x1, y1, max(1, x2 - x1), max(1, y2 - y1)) if x2 > x1 and y2 > y1 else (x1, y1, max(1, x2), max(1, y2))
        return (0, 0, width, height)
