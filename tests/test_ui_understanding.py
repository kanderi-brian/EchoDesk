"""Regression coverage for semantic desktop vision."""

import unittest
from PIL import Image

from vision.models import UIElement, UIWindow
from vision.scene_graph import SceneGraph
from vision.ui_understanding import UIUnderstanding
from vision.vision_engine import VisionEngine


class TestUIModelsAndGraph(unittest.TestCase):
    def setUp(self):
        self.window = UIWindow(title="Demo", bounding_box=(0, 0, 500, 400), active=True)
        self.toolbar = UIElement("toolbar", bounding_box=(0, 0, 500, 50))
        self.save = UIElement("button", "Save", .9, (20, 70, 80, 30), clickable=True)
        self.name = UIElement("text_field", "Username", .9, (20, 120, 200, 30), editable=True)
        self.scene = SceneGraph().build(500, 400, [self.toolbar, self.save, self.name], [self.window])

    def test_scene_preserves_parent_child_relationships(self):
        self.assertEqual(self.save.parent, self.window.id)
        self.assertIn(self.save.id, self.window.children)

    def test_center_is_derived_from_bounds(self):
        self.assertEqual(self.save.center, (60, 85))

    def test_contains_detects_nested_element(self):
        self.assertTrue(self.window.contains(self.save))

    def test_find_by_label_and_type(self):
        engine = VisionEngine()
        self.assertIs(engine.find_element("Save button", self.scene), self.save)

    def test_find_textbox_alias(self):
        engine = VisionEngine()
        self.assertIs(engine.find_element("Username textbox", self.scene), self.name)

    def test_relative_positioning(self):
        engine = VisionEngine()
        self.assertTrue(engine.is_relative_to(self.name, "below", self.save))

    def test_scene_comparison_detects_text_change(self):
        altered = UIElement("button", "Saved", .9, (20, 70, 80, 30), clickable=True)
        after = SceneGraph().build(500, 400, [altered], [UIWindow(title="Demo", bounding_box=(0, 0, 500, 400))])
        self.assertTrue(SceneGraph().compare(self.scene, after).changed)

    def test_recovery_falls_back_to_label_words(self):
        engine = VisionEngine()
        self.assertIs(engine.recover_element("Save action button", self.scene), self.save)

    def test_ui_understanding_detects_common_controls(self):
        entries = [{"text": text, "confidence": .9, "box": [10, 10, 100, 30]} for text in ("Save", "Username", "Remember me", "File")]
        elements, _ = UIUnderstanding().detect(300, 200, entries)
        self.assertTrue({"button", "text_field", "checkbox", "menu"}.issubset({item.type for item in elements}))

    def test_capture_scene_from_image_uses_pipeline(self):
        engine = VisionEngine()
        engine.ocr_reader = None
        scene = engine.capture_scene(Image.new("RGB", (32, 24)))
        self.assertEqual((scene.width, scene.height), (32, 24))


def _make_control_test(label, expected_type):
    def test(self):
        elements, _ = UIUnderstanding().detect(200, 100, [{"text": label, "confidence": .8, "box": [1, 1, 20, 10]}])
        self.assertEqual(elements[0].type, expected_type)
    return test


# Each control phrase is a separate regression case; this also guards profile-
# independent baseline detection when OCR and visual classifiers evolve.
for _number, (_label, _kind) in enumerate([
    ("OK", "button"), ("Cancel", "button"), ("Apply", "button"), ("Download", "button"),
    ("Password", "text_field"), ("Search", "text_field"), ("Email", "text_field"),
    ("Check box", "checkbox"), ("Enable feature", "checkbox"), ("Agree", "checkbox"),
    ("Radio option", "radio_button"), ("Option A", "radio_button"),
    ("Select item", "dropdown"), ("Choose language", "dropdown"),
    ("File", "menu"), ("Edit", "menu"), ("Tools", "menu"), ("Help", "menu"),
    ("Home", "tab"), ("Insert", "tab"), ("View", "tab"), ("Advanced", "tab"),
    ("Toolbar", "toolbar"), ("Status", "status_bar"), ("Ready", "status_bar"),
    ("Warning", "dialog"), ("Error", "dialog"), ("Confirm", "dialog"),
    ("Scroll", "scroll_bar"), ("Open", "button"), ("Close", "button"),
    ("Next", "button"), ("Back", "button"), ("Address", "text_field"),
], start=1):
    setattr(TestUIModelsAndGraph, f"test_control_detection_{_number:02d}", _make_control_test(_label, _kind))
