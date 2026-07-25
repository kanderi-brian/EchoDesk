"""Scene graph construction and comparison for desktop UI scenes."""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher

from .models import UIElement, UIScene, UIWindow


@dataclass
class SceneDifference:
    opened_windows: list[UIWindow] = field(default_factory=list)
    closed_windows: list[UIWindow] = field(default_factory=list)
    moved_controls: list[tuple[UIElement, UIElement]] = field(default_factory=list)
    changed_text: list[tuple[UIElement, UIElement]] = field(default_factory=list)
    appeared: list[UIElement] = field(default_factory=list)
    disappeared: list[UIElement] = field(default_factory=list)
    loading_complete: bool = False

    @property
    def changed(self) -> bool:
        return bool(self.opened_windows or self.closed_windows or self.moved_controls or self.changed_text or self.appeared or self.disappeared or self.loading_complete)

    def as_dict(self) -> dict[str, object]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__} | {"changed": self.changed}


class SceneGraph:
    """Build parent/child UI relationships without depending on fixed coordinates."""

    CONTAINERS = {"window", "dialog", "toolbar", "menu", "context_menu", "tab", "status_bar"}

    def build(self, width: int, height: int, elements: list[UIElement], windows: list[UIWindow] | None = None, **metadata: object) -> UIScene:
        window_nodes = list(windows or [item for item in elements if isinstance(item, UIWindow)])
        all_nodes = [*window_nodes, *[item for item in elements if item.id not in {node.id for node in window_nodes}]]
        for child in all_nodes:
            if child.type == "window":
                continue
            parents = [candidate for candidate in all_nodes if candidate.id != child.id and candidate.type in self.CONTAINERS and candidate.contains(child)]
            if parents:
                parent = min(parents, key=lambda item: item.bounding_box[2] * item.bounding_box[3])
                child.parent = parent.id
                if child.id not in parent.children:
                    parent.children.append(child.id)
        return UIScene(width=width, height=height, elements=all_nodes, windows=window_nodes, metadata=dict(metadata))

    def compare(self, before: UIScene, after: UIScene, movement_threshold: int = 4) -> SceneDifference:
        difference = SceneDifference()
        old_windows = {self._key(item): item for item in before.windows}
        new_windows = {self._key(item): item for item in after.windows}
        difference.opened_windows = [item for key, item in new_windows.items() if key not in old_windows]
        difference.closed_windows = [item for key, item in old_windows.items() if key not in new_windows]
        old = {self._key(item): item for item in before.all_elements() if item.type != "window"}
        new = {self._key(item): item for item in after.all_elements() if item.type != "window"}
        difference.appeared = [item for key, item in new.items() if key not in old]
        difference.disappeared = [item for key, item in old.items() if key not in new]
        for key in old.keys() & new.keys():
            first, second = old[key], new[key]
            if self._distance(first.bounding_box, second.bounding_box) > movement_threshold:
                difference.moved_controls.append((first, second))
            if first.ocr_text != second.ocr_text or first.label != second.label:
                difference.changed_text.append((first, second))
        difference.loading_complete = any("loading" in item.label.casefold() for item in difference.disappeared)
        return difference

    @staticmethod
    def _key(item: UIElement) -> str:
        return f"{item.type}:{(item.label or item.ocr_text).casefold()}"

    @staticmethod
    def _distance(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])
