import unittest
from unittest.mock import MagicMock, patch

from voice.voice_engine import VoiceEngine, VoiceConfig, VoiceSession


class TestVoiceEngine(unittest.TestCase):
    def test_session_lifecycle(self):
        engine = VoiceEngine(VoiceConfig())

        self.assertFalse(engine.session.active)
        engine.start()
        self.assertTrue(engine.session.active)
        self.assertFalse(engine.session.paused)

        engine.pause()
        self.assertTrue(engine.session.paused)

        engine.resume()
        self.assertFalse(engine.session.paused)

        engine.stop()
        self.assertFalse(engine.session.active)
        self.assertFalse(engine.session.speaking)
        self.assertFalse(engine.session.listening)

    @patch("voice.voice_engine.VoiceEngine._initialize_recognizer")
    @patch("voice.voice_engine.sr")
    def test_listen_returns_wake_word_transcript(self, mock_sr, mock_init):
        mock_init.return_value = True
        mock_recognizer = MagicMock()
        mock_recognizer.recognize_sphinx.return_value = "Echo, what is the weather"
        mock_sr.Recognizer.return_value = mock_recognizer

        mock_source = MagicMock()
        mock_microphone = MagicMock()
        mock_microphone.__enter__.return_value = mock_source
        mock_microphone.__exit__.return_value = None
        mock_sr.Microphone.return_value = mock_microphone

        engine = VoiceEngine(VoiceConfig())
        engine.recognizer = mock_recognizer
        engine.sr_module = mock_sr

        result = engine.listen()

        self.assertTrue(result["success"])
        self.assertTrue(result["wake_word_detected"])
        self.assertEqual(result["transcript"], "what is the weather")

    @patch("voice.voice_engine.pyttsx3")
    def test_speak_queues_text_and_returns_success(self, mock_pyttsx3):
        mock_engine = MagicMock()
        mock_pyttsx3.init.return_value = mock_engine

        engine = VoiceEngine(VoiceConfig())
        response = engine.speak("Hello world")

        self.assertTrue(response["success"])
        self.assertEqual(response["spoken_text"], "Hello world")

    def test_listen_when_paused_returns_error(self):
        engine = VoiceEngine(VoiceConfig())
        engine.start()
        engine.pause()

        result = engine.listen()

        self.assertFalse(result["success"])
        self.assertIn("paused", result["message"].lower())

    def test_wake_word_detection_ignores_non_wake(self):
        engine = VoiceEngine(VoiceConfig())
        detected, transcript = engine._process_wake_word("What's the weather?")

        self.assertFalse(detected)
        self.assertEqual(transcript, "")

    def test_wake_word_detection_strips_wake_word(self):
        engine = VoiceEngine(VoiceConfig())
        detected, transcript = engine._process_wake_word("Echo, turn on the lights")

        self.assertTrue(detected)
        self.assertEqual(transcript, "turn on the lights")


if __name__ == "__main__":
    unittest.main()
