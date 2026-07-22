import unittest
from unittest.mock import MagicMock, patch

from voice.controller import VoiceController
from voice.speech_synthesizer import SpeechSynthesizer


class TestSpeechSynthesizer(unittest.TestCase):

    def test_initialize_returns_error_when_library_missing(self):
        with patch("voice.speech_synthesizer.pyttsx3", None):
            synthesizer = SpeechSynthesizer()

            result = synthesizer.initialize()

            self.assertFalse(result["success"])
            self.assertIn(
                "Speech engine is unavailable",
                result["message"],
            )

    def test_available_returns_success_when_engine_present(self):
        mock_engine = MagicMock()

        mock_pyttsx3 = MagicMock(
            init=MagicMock(return_value=mock_engine)
        )

        synthesizer = SpeechSynthesizer(
            pyttsx3_module=mock_pyttsx3
        )

        result = synthesizer.available()

        self.assertTrue(result["success"])
        self.assertEqual(result["action"], "available")

    def test_speak_calls_engine_and_returns_success(self):
        mock_engine = MagicMock()

        mock_pyttsx3 = MagicMock(
            init=MagicMock(return_value=mock_engine)
        )

        synthesizer = SpeechSynthesizer(
            pyttsx3_module=mock_pyttsx3
        )

        result = synthesizer.speak("Hello EchoDesk")

        self.assertTrue(result["success"])

        mock_engine.say.assert_called_once_with(
            "Hello EchoDesk"
        )

        mock_engine.runAndWait.assert_called_once()

    def test_speak_empty_text_returns_error(self):
        mock_pyttsx3 = MagicMock(
            init=MagicMock(return_value=MagicMock())
        )

        synthesizer = SpeechSynthesizer(
            pyttsx3_module=mock_pyttsx3
        )

        result = synthesizer.speak("")

        self.assertFalse(result["success"])
        self.assertIn(
            "No text was provided",
            result["message"],
        )

    def test_stop_speech_returns_error_when_not_initialized(self):
        mock_pyttsx3 = MagicMock(
            init=MagicMock(return_value=MagicMock())
        )

        synthesizer = SpeechSynthesizer(
            pyttsx3_module=mock_pyttsx3
        )

        result = synthesizer.stop()

        self.assertFalse(result["success"])
        self.assertIn(
            "Speech engine is not initialized",
            result["message"],
        )

    def test_stop_speech_calls_engine_stop(self):
        mock_engine = MagicMock()

        mock_pyttsx3 = MagicMock(
            init=MagicMock(return_value=mock_engine)
        )

        synthesizer = SpeechSynthesizer(
            pyttsx3_module=mock_pyttsx3
        )

        synthesizer.initialize()

        result = synthesizer.stop()

        self.assertTrue(result["success"])

        mock_engine.stop.assert_called_once()


class TestVoiceControllerSpeechSynthesisIntegration(unittest.TestCase):

    def test_speech_available_delegates_to_synthesizer(self):
        mock_synthesizer = MagicMock()

        mock_synthesizer.available.return_value = {
            "success": True,
            "action": "available",
        }

        controller = VoiceController(
            synthesizer=mock_synthesizer
        )

        result = controller.speech_available()

        mock_synthesizer.available.assert_called_once()

        self.assertTrue(result["success"])

    def test_speak_response_delegates_to_synthesizer(self):
        mock_synthesizer = MagicMock()

        mock_synthesizer.speak.return_value = {
            "success": True,
            "action": "speak",
        }

        controller = VoiceController(
            synthesizer=mock_synthesizer
        )

        result = controller.speak_response("Hello")

        mock_synthesizer.speak.assert_called_once_with(
            "Hello"
        )

        self.assertTrue(result["success"])

    def test_stop_speech_delegates_to_synthesizer(self):
        mock_synthesizer = MagicMock()

        mock_synthesizer.stop.return_value = {
            "success": True,
            "action": "stop",
        }

        controller = VoiceController(
            synthesizer=mock_synthesizer
        )

        result = controller.stop_speech()

        mock_synthesizer.stop.assert_called_once()

        self.assertTrue(result["success"])


if __name__ == "__main__":
    unittest.main()