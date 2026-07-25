"""Vision engine module for EchoDesk."""

import os
import hashlib
import logging
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, List

from PIL import Image
import numpy as np
from mss import MSS

from .models import UIActionTarget, UIElement, UIScene, UIWindow
from .scene_graph import SceneDifference, SceneGraph
from .ui_understanding import UIUnderstanding
from performance.metrics import TTLCache


@dataclass
class VisionResult:
    text: str
    confidence: float
    ui_elements: list[str]
    width: int
    height: int
    summary: str


class VisionEngine:
    """Capture, understand, search, and compare desktop user interfaces.

    ``analyze`` and ``VisionResult`` retain the original OCR API.  New callers
    use ``capture_scene``/``find_element`` and therefore work from semantic UI
    elements rather than brittle absolute coordinates.
    """

    APPLICATION_PROFILES = {
        "windows explorer": {"aliases": ("file explorer", "explorer"), "controls": ("toolbar", "address", "search")},
        "vs code": {"aliases": ("visual studio code", "code"), "controls": ("tab", "editor", "status_bar")},
        "chrome": {"aliases": ("google chrome",), "controls": ("tab", "address", "toolbar")},
        "edge": {"aliases": ("microsoft edge",), "controls": ("tab", "address", "toolbar")},
        "settings": {"aliases": ("windows settings",), "controls": ("search", "navigation")},
        "notepad": {"aliases": (), "controls": ("menu", "text_field", "status_bar")},
        "calculator": {"aliases": (), "controls": ("button", "display")},
    }

    def __init__(self) -> None:
        self.sct = MSS()
        self.ocr_reader = None
        self._ocr_initialized = False
        self.ui_understanding = UIUnderstanding()
        self.scene_graph = SceneGraph()
        self._scene_cache: UIScene | None = None
        self._ocr_cache = TTLCache(ttl=30.0, maxsize=8, name="vision_ocr")
        self._scene_results = TTLCache(ttl=30.0, maxsize=8, name="vision_scene")
        self._logger = logging.getLogger("echodesk.vision")
        if not self._logger.handlers:
            os.makedirs("logs", exist_ok=True)
            handler = logging.FileHandler(os.path.join("logs", "vision.log"), encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

    def _initialize_ocr_reader(self) -> None:
        if self._ocr_initialized:
            return

        try:
            import easyocr

            self.ocr_reader = easyocr.Reader(["en"], gpu=False)
        except Exception:
            self.ocr_reader = None
        finally:
            self._ocr_initialized = True

    def capture_screen(self) -> Image.Image:
        """Capture the primary screen and return a PIL Image."""
        self._logger.info("Capturing screen")

        monitors = self.sct.monitors
        monitor = monitors[1] if len(monitors) > 1 else monitors[0]

        screenshot = self.sct.grab(monitor)
        image = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
        return image

    def extract_text(self, image: Image.Image) -> list[dict[str, Any]]:
        """Run OCR on the provided image and return detected text with metadata."""
        self._logger.info("Running OCR")
        digest = hashlib.sha256(image.tobytes()).hexdigest()
        cached = self._ocr_cache.get(digest)
        if cached is not None:
            self._logger.info("OCR cache hit")
            return [dict(item) for item in cached]
        self._initialize_ocr_reader()
        if self.ocr_reader is None:
            result = [
                {
                    "text": "",
                    "confidence": 0.0,
                    "box": None,
                }
            ]
            self._ocr_cache.set(digest, result)
            return result

        try:
            image_array = np.array(image)
            raw_results = self.ocr_reader.readtext(image_array)
        except Exception:
            result = [
                {
                    "text": "",
                    "confidence": 0.0,
                    "box": None,
                }
            ]
            self._ocr_cache.set(digest, result)
            return result

        extracted = []
        for result in raw_results:
            box, text, confidence = result
            extracted.append(
                {
                    "text": text,
                    "confidence": float(confidence),
                    "box": [int(point[0]) for point in box[0:2]] + [int(point[2]) for point in box[2:4]] if isinstance(box, list) and len(box) >= 4 else None,
                }
            )
        self._ocr_cache.set(digest, extracted)
        return extracted

    def describe_image(self, image: Image.Image) -> VisionResult:
        """Return a structured description of the image contents."""
        text_entries = self.extract_text(image)
        detected_text = "\n".join(entry["text"] for entry in text_entries if entry.get("text"))
        trimmed_text = detected_text.strip()
        confidences = [entry["confidence"] for entry in text_entries if isinstance(entry.get("confidence"), (int, float))]
        confidence = float(sum(confidences) / len(confidences)) if confidences else 0.0

        width, height = image.size
        ui_elements = self._detect_ui_elements(trimmed_text)
        summary = self._build_summary(trimmed_text, ui_elements, width, height)

        self._logger.info("Analysis complete: %s controls inferred", len(ui_elements))
        return VisionResult(
            text=trimmed_text,
            confidence=confidence,
            ui_elements=ui_elements,
            width=width,
            height=height,
            summary=summary,
        )

    def analyze(self, source: str | Image.Image | None = None) -> VisionResult:
        """Analyze an image or capture the screen if no image source is provided."""
        if isinstance(source, Image.Image):
            image = source
            return self.describe_image(image)

        if isinstance(source, str) and os.path.exists(source):
            with Image.open(source) as image:
                return self.describe_image(image.copy())

        image = self.capture_screen()
        return self.describe_image(image)

    def capture_scene(self, source: str | Image.Image | None = None, refresh: bool = True) -> UIScene:
        """Run the complete desktop vision pipeline and return a scene graph."""
        if isinstance(source, Image.Image):
            image = source
        elif isinstance(source, str) and os.path.exists(source):
            with Image.open(source) as opened:
                image = opened.copy()
        else:
            image = self.capture_screen()
        digest = hashlib.sha256(image.tobytes()).hexdigest()
        cached_scene = self._scene_results.get(digest)
        if cached_scene is not None:
            self._scene_cache = cached_scene
            return cached_scene
        if not refresh and self._scene_cache and self._scene_cache.image_hash == digest:
            return self._scene_cache
        entries = self.extract_text(image)
        active_title = self._active_window_title()
        elements, windows = self.ui_understanding.detect(*image.size, entries, active_title=active_title)
        scene = self.scene_graph.build(*image.size, elements, windows, image_hash=digest, captured_at=datetime.now(timezone.utc).isoformat(), profile=self._profile_for(active_title))
        scene.image_hash = digest
        scene.captured_at = datetime.now(timezone.utc).isoformat()
        self._scene_cache = scene
        self._scene_results.set(digest, scene)
        self._logger.info("Scene captured: windows=%s controls=%s profile=%s", len(scene.windows), len(scene.elements), scene.metadata.get("profile"))
        return scene

    analyze_scene = capture_scene

    def list_windows(self, scene: UIScene | None = None) -> list[UIWindow]:
        """Return windows in a supplied scene or in a fresh desktop scene."""
        return (scene or self.capture_scene()).windows

    def get_active_window(self, scene: UIScene | None = None) -> UIWindow | None:
        """Return the active visual window when one can be identified."""
        windows = self.list_windows(scene)
        return next((window for window in windows if window.active), windows[0] if windows else None)

    def find_element(self, query: str, scene: UIScene | None = None, parent: UIElement | str | None = None) -> UIElement | None:
        """Find the strongest semantic match for queries such as ``Save button``."""
        if not isinstance(query, str) or not query.strip():
            return None
        terms = query.casefold().replace("textbox", "text field").split()
        wanted_type = next((kind for kind in ("button", "text_field", "checkbox", "radio_button", "dropdown", "icon", "tab", "menu", "window", "toolbar", "dialog", "scroll_bar", "status_bar", "context_menu") if kind.replace("_", " ") in query.casefold()), None)
        parent_id = parent.id if isinstance(parent, UIElement) else parent
        candidates = (scene or self.capture_scene()).all_elements()
        scored: list[tuple[float, UIElement]] = []
        for item in candidates:
            if parent_id and item.parent != parent_id:
                continue
            label = f"{item.label} {item.ocr_text}".casefold()
            overlap = sum(term in label or term in item.type.replace("_", " ") for term in terms)
            type_bonus = 2 if wanted_type == item.type else 0
            if overlap or type_bonus:
                scored.append((overlap + type_bonus + item.confidence, item))
        result = max(scored, key=lambda match: match[0])[1] if scored else None
        self._logger.info("Element search query=%r found=%s", query, result.id if result else None)
        return result

    def resolve_action_target(self, query: str, action: str = "click", scene: UIScene | None = None) -> UIActionTarget | None:
        element = self.find_element(query, scene)
        return UIActionTarget(element, action, element.confidence, "semantic label match") if element else None

    def compare_scene(self, before: UIScene, after: UIScene | None = None) -> SceneDifference:
        """Compare two scene graphs to verify a visible desktop change."""
        result = self.scene_graph.compare(before, after or self.capture_scene())
        self._logger.info("Scene comparison changed=%s", result.changed)
        return result

    def verify_change(self, before: UIScene, expectation: str | None = None, after: UIScene | None = None) -> bool:
        """Verify an action's expected visual effect instead of assuming success."""
        difference = self.compare_scene(before, after)
        if not expectation:
            return difference.changed
        text = expectation.casefold()
        candidates = difference.opened_windows + difference.appeared + [item for item, _ in difference.changed_text]
        if "closed" in text or "disappeared" in text:
            candidates += difference.closed_windows + difference.disappeared
        return any(term in f"{item.label} {item.ocr_text}".casefold() for item in candidates for term in text.split() if len(term) > 2)

    def recover_element(self, query: str, scene: UIScene | None = None) -> UIElement | None:
        """Retry a lookup using label fragments, hierarchy, and control type."""
        scene = scene or self.capture_scene(refresh=False)
        found = self.find_element(query, scene)
        if found:
            return found
        words = [word for word in query.split() if word.casefold() not in {"button", "textbox", "text", "field", "icon", "menu"}]
        for word in words:
            found = self.find_element(word, scene)
            if found:
                self._logger.info("Recovery succeeded query=%r strategy=nearby-label", query)
                return found
        self._logger.warning("Recovery exhausted query=%r", query)
        return None

    def is_relative_to(self, element: UIElement, relation: str, reference: UIElement) -> bool:
        """Evaluate natural relative relations: below, inside, under, beside."""
        ex, ey, ew, eh = element.bounding_box
        rx, ry, rw, rh = reference.bounding_box
        relation = relation.casefold()
        if relation in {"inside", "in"}:
            return reference.contains(element)
        if relation in {"below", "under"}:
            return ey >= ry + rh
        if relation in {"above", "over"}:
            return ey + eh <= ry
        if relation in {"beside", "next to"}:
            return abs((ey + eh / 2) - (ry + rh / 2)) <= max(eh, rh)
        return False

    def _active_window_title(self) -> str:
        try:
            from desktop.controller import DesktopController
            result = DesktopController().get_active_window()
            return str(result.get("result") or "") if result.get("success") else ""
        except Exception:
            return ""

    def _profile_for(self, title: str) -> str | None:
        normalized = title.casefold()
        for name, profile in self.APPLICATION_PROFILES.items():
            if name in normalized or any(alias in normalized for alias in profile["aliases"]):
                return name
        return None

    def _detect_ui_elements(self, detected_text: str) -> list[str]:
        elements: list[str] = []
        normalized = detected_text.lower()

        if "button" in normalized or "ok" in normalized or "cancel" in normalized:
            elements.append("button")
        if "menu" in normalized or "file" in normalized or "edit" in normalized:
            elements.append("menu")
        if "window" in normalized or "dialog" in normalized:
            elements.append("window")
        if "form" in normalized or "input" in normalized or "search" in normalized:
            elements.append("form")
        if not elements and detected_text:
            elements.append("text content")

        return sorted(set(elements))

    def _build_summary(self, detected_text: str, ui_elements: list[str], width: int, height: int) -> str:
        parts = [f"Image size: {width}x{height}."]
        if ui_elements:
            parts.append(f"Detected UI elements: {', '.join(ui_elements)}.")
        if detected_text:
            parts.append(f"Detected text length: {len(detected_text)} characters.")
        else:
            parts.append("No readable text detected.")
        return " ".join(parts)
