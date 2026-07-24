import unittest
from PIL import Image

from vision.vision_engine import VisionEngine, VisionResult


class TestVisionEngine(unittest.TestCase):
    def test_describe_image_returns_vision_result_for_blank_image(self):
        engine = VisionEngine()
        engine.ocr_reader = None

        image = Image.new("RGB", (100, 60), color=(255, 255, 255))
        result = engine.describe_image(image)

        self.assertIsInstance(result, VisionResult)
        self.assertEqual(result.confidence, 0.0)
        self.assertEqual(result.width, 100)
        self.assertEqual(result.height, 60)
        self.assertIn("No readable text detected", result.summary)

    def test_analyze_uses_image_path_when_valid(self):
        engine = VisionEngine()
        engine.ocr_reader = None

        image = Image.new("RGB", (80, 40), color=(200, 200, 200))
        image_path = "test_image.png"
        image.save(image_path)

        try:
            result = engine.analyze(image_path)
            self.assertIsInstance(result, VisionResult)
            self.assertEqual(result.width, 80)
            self.assertEqual(result.height, 40)
        finally:
            import os

            if os.path.exists(image_path):
                os.remove(image_path)


if __name__ == "__main__":
    unittest.main()
