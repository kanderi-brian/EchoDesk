"""Vision engine module for EchoDesk."""

import os
from dataclasses import dataclass
from typing import Any, List

from PIL import Image
import numpy as np
from mss import MSS


@dataclass
class VisionResult:
    text: str
    confidence: float
    ui_elements: list[str]
    width: int
    height: int
    summary: str


class VisionEngine:
    """A vision engine for screen capture, OCR, and image description."""

    def __init__(self) -> None:
        self.sct = MSS()
        self.ocr_reader = self._initialize_ocr_reader()

    def _initialize_ocr_reader(self) -> Any:
        try:
            import easyocr

            return easyocr.Reader(["en"], gpu=False)
        except Exception:
            return None

    def capture_screen(self) -> Image.Image:
        """Capture the primary screen and return a PIL Image."""
        print("[Vision] Capturing screen")

        monitors = self.sct.monitors
        monitor = monitors[1] if len(monitors) > 1 else monitors[0]

        screenshot = self.sct.grab(monitor)
        image = Image.frombytes("RGB", screenshot.size, screenshot.rgb)
        return image

    def extract_text(self, image: Image.Image) -> list[dict[str, Any]]:
        """Run OCR on the provided image and return detected text with metadata."""
        print("[Vision] Running OCR")
        if self.ocr_reader is None:
            return [
                {
                    "text": "",
                    "confidence": 0.0,
                    "box": None,
                }
            ]

        try:
            image_array = np.array(image)
            raw_results = self.ocr_reader.readtext(image_array)
        except Exception:
            return [
                {
                    "text": "",
                    "confidence": 0.0,
                    "box": None,
                }
            ]

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

        print("[Vision] Analysis complete")
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
