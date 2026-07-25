"""Structured models used by EchoDesk desktop vision."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
import uuid


BoundingBox = tuple[int, int, int, int]


@dataclass
class UIElement:
    """A visible desktop control, expressed independently of screen coordinates."""

    type: str
    label: str = ""
    confidence: float = 0.0
    bounding_box: BoundingBox = (0, 0, 0, 0)
    ocr_text: str = ""
    parent: str | None = None
    children: list[str] = field(default_factory=list)
    clickable: bool = False
    editable: bool = False
    enabled: bool = True
    visible: bool = True
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def box(self) -> BoundingBox:
        """Compatibility-friendly shorthand for ``bounding_box``."""
        return self.bounding_box

    @property
    def center(self) -> tuple[int, int]:
        x, y, width, height = self.bounding_box
        return x + width // 2, y + height // 2

    def contains(self, other: "UIElement") -> bool:
        x, y, w, h = self.bounding_box
        ox, oy, ow, oh = other.bounding_box
        return x <= ox and y <= oy and x + w >= ox + ow and y + h >= oy + oh


@dataclass
class UIWindow(UIElement):
    """A detected application, dialog, modal, or floating window."""

    type: str = field(default="window", init=False)
    title: str = ""
    active: bool = False
    modal: bool = False
    window_kind: str = "application"

    def __post_init__(self) -> None:
        self.type = "window"
        if not self.title:
            self.title = self.label or self.ocr_text
        if not self.label:
            self.label = self.title


@dataclass
class UIScene:
    """A complete, queryable representation of a captured desktop."""

    width: int
    height: int
    elements: list[UIElement] = field(default_factory=list)
    windows: list[UIWindow] = field(default_factory=list)
    image_hash: str = ""
    captured_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def all_elements(self) -> list[UIElement]:
        return [*self.windows, *[item for item in self.elements if item.id not in {window.id for window in self.windows}]]

    def get(self, element_id: str) -> UIElement | None:
        return next((element for element in self.all_elements() if element.id == element_id), None)


@dataclass
class UIActionTarget:
    """A resolved control and the action that should be performed on it."""

    element: UIElement
    action: str = "click"
    confidence: float = 0.0
    reason: str = ""

    @property
    def coordinates(self) -> tuple[int, int]:
        return self.element.center
