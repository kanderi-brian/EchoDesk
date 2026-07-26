"""Offline voice interface for EchoDesk."""

import queue
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

try:
    import speech_recognition as sr
except ImportError:
    sr = None

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None


@dataclass
class VoiceConfig:
    wake_word: str = "Echo"
    speech_rate: int = 170
    voice_enabled: bool = True
    microphone_timeout: float = 5.0
    phrase_time_limit: float = 10.0


@dataclass
class VoiceSession:
    active: bool = False
    listening: bool = False
    speaking: bool = False
    paused: bool = False

    def start(self) -> None:
        self.active = True
        self.paused = False

    def stop(self) -> None:
        self.active = False
        self.listening = False
        self.speaking = False
        self.paused = False

    def pause(self) -> None:
        if self.active:
            self.paused = True
            self.listening = False

    def resume(self) -> None:
        if self.active:
            self.paused = False


class VoiceEngine:
    """A complete offline voice engine with speech I/O and session control."""

    def __init__(
        self,
        config: Optional[VoiceConfig] = None,
        sr_module: Optional[Any] = None,
        tts_module: Optional[Any] = None,
    ) -> None:
        self.config = config or VoiceConfig()
        self.logger = logging.getLogger("echodesk.voice")
        self.session = VoiceSession()
        self.sr_module = sr_module if sr_module is not None else sr
        self.tts_module = tts_module if tts_module is not None else pyttsx3
        self.recognizer = None
        self.audio_data = None
        self.tts_engine = None
        self.speech_queue: "queue.Queue[str]" = queue.Queue()
        self.speech_stop = threading.Event()
        self.speak_lock = threading.Lock()
        self.speech_thread = threading.Thread(target=self._speech_worker, daemon=True)
        self._start_speech_worker()

    def _start_speech_worker(self) -> None:
        if not self.speech_thread.is_alive():
            self.speech_thread.start()

    def _initialize_recognizer(self) -> bool:
        if not self.sr_module:
            return False
        if self.recognizer is not None:
            return True
        try:
            self.recognizer = self.sr_module.Recognizer()
            return True
        except Exception:
            self.recognizer = None
            return False

    def _initialize_tts(self) -> bool:
        if not self.tts_module:
            return False
        if self.tts_engine is not None:
            return True
        try:
            self.tts_engine = self.tts_module.init()
            self.tts_engine.setProperty("rate", self.config.speech_rate)
            return True
        except Exception:
            self.tts_engine = None
            return False

    def _speech_worker(self) -> None:
        while not self.speech_stop.is_set():
            try:
                text = self.speech_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if not self.config.voice_enabled:
                self.speech_queue.task_done()
                continue

            self.session.speaking = True
            self.logger.debug("Speaking")
            if self._initialize_tts():
                try:
                    with self.speak_lock:
                        self.tts_engine.say(text)
                        self.tts_engine.runAndWait()
                except Exception as exc:
                    self.logger.warning("Speech output failed: %s", exc)
            else:
                self.logger.debug("Text-to-speech engine is unavailable")

            self.session.speaking = False
            self.logger.debug("Speech complete")
            self.speech_queue.task_done()

    def _process_wake_word(self, transcript: str) -> tuple[bool, str]:
        wake_word = self.config.wake_word.strip().lower()
        normalized = transcript.strip()
        if not wake_word:
            return True, normalized
        lower = normalized.lower()
        if lower.startswith(wake_word + " "):
            return True, normalized[len(wake_word) + 1 :].strip()
        if lower.startswith(wake_word + ","):
            return True, normalized[len(wake_word) + 1 :].strip()
        if wake_word in lower and lower.index(wake_word) == 0:
            return True, normalized[len(wake_word) :].strip(" ,")
        return False, ""

    def listen(self) -> Dict[str, Any]:
        if not self.config.voice_enabled:
            return {
                "success": False,
                "message": "Voice is disabled in configuration.",
            }

        if self.session.paused:
            return {
                "success": False,
                "message": "Voice session is paused.",
            }

        self.session.start()
        self.logger.debug("Listening")

        if not self._initialize_recognizer():
            return {
                "success": False,
                "message": "Speech recognition library is unavailable.",
            }

        if not hasattr(self.sr_module, "Microphone"):
            return {
                "success": False,
                "message": "Microphone support is unavailable.",
            }

        try:
            with self.sr_module.Microphone() as source:
                self.session.listening = True
                start_time = time.perf_counter()
                audio = self.recognizer.listen(
                    source,
                    timeout=self.config.microphone_timeout,
                    phrase_time_limit=self.config.phrase_time_limit,
                )
                duration = time.perf_counter() - start_time
                self.audio_data = audio
        except self.sr_module.WaitTimeoutError:
            self.session.listening = False
            return {
                "success": False,
                "message": "Microphone timeout while waiting for speech.",
                "confidence": 0.0,
                "duration": self.config.microphone_timeout,
                "wake_word_detected": False,
                "transcript": "",
            }
        except Exception as exc:
            self.session.listening = False
            return {
                "success": False,
                "message": "Failed to capture microphone input.",
                "details": str(exc),
                "confidence": 0.0,
                "duration": 0.0,
                "wake_word_detected": False,
                "transcript": "",
            }
        finally:
            self.session.listening = False

        if self.audio_data is None:
            return {
                "success": False,
                "message": "No audio was captured.",
                "confidence": 0.0,
                "duration": 0.0,
                "wake_word_detected": False,
                "transcript": "",
            }

        transcript = ""
        confidence = 0.0
        try:
            if hasattr(self.recognizer, "recognize_sphinx"):
                transcript = self.recognizer.recognize_sphinx(self.audio_data)
            else:
                return {
                    "success": False,
                    "message": "Offline speech recognizer is unavailable.",
                    "confidence": 0.0,
                    "duration": duration,
                    "wake_word_detected": False,
                    "transcript": "",
                }
        except self.sr_module.UnknownValueError:
            return {
                "success": False,
                "message": "Speech was not understood.",
                "confidence": 0.0,
                "duration": duration,
                "wake_word_detected": False,
                "transcript": "",
            }
        except self.sr_module.RequestError as exc:
            return {
                "success": False,
                "message": "Speech recognition request failed.",
                "details": str(exc),
                "confidence": 0.0,
                "duration": duration,
                "wake_word_detected": False,
                "transcript": "",
            }
        except Exception as exc:
            return {
                "success": False,
                "message": "Failed to recognize speech.",
                "details": str(exc),
                "confidence": 0.0,
                "duration": duration,
                "wake_word_detected": False,
                "transcript": "",
            }

        wake_detected, wake_transcript = self._process_wake_word(transcript)
        if not wake_detected:
            self.logger.debug("Wake word not detected")
            return {
                "success": True,
                "message": "Wake word not detected.",
                "transcript": "",
                "raw_transcript": transcript,
                "confidence": confidence,
                "duration": duration,
                "wake_word_detected": False,
            }

        self.logger.debug("Wake word detected")
        return {
            "success": True,
            "message": "Voice command captured.",
            "transcript": wake_transcript,
            "raw_transcript": transcript,
            "confidence": confidence,
            "duration": duration,
            "wake_word_detected": True,
        }

    def speak(self, text: str) -> Dict[str, Any]:
        if not isinstance(text, str) or not text.strip():
            return {
                "success": False,
                "message": "No text provided for speech output.",
            }

        if not self.config.voice_enabled:
            return {
                "success": False,
                "message": "Voice output is disabled in configuration.",
            }

        if self.session.paused:
            return {
                "success": False,
                "message": "Voice session is paused.",
            }

        self.session.start()
        self.speech_queue.put(text)

        return {
            "success": True,
            "message": "Speech queued.",
            "spoken_text": text,
            "voice_enabled": self.config.voice_enabled,
        }

    def start(self) -> Dict[str, Any]:
        self.session.start()
        self.speech_stop.clear()
        if not self.speech_thread.is_alive():
            self.speech_thread = threading.Thread(target=self._speech_worker, daemon=True)
            self._start_speech_worker()
        return {"success": True, "message": "Voice session started."}

    def stop(self) -> Dict[str, Any]:
        self.session.stop()
        self.speech_stop.set()
        if self.tts_engine is not None and hasattr(self.tts_engine, "stop"):
            try:
                self.tts_engine.stop()
            except Exception:
                pass
        if self.speech_thread.is_alive() and self.speech_thread is not threading.current_thread():
            self.speech_thread.join(timeout=2.0)
        return {"success": True, "message": "Voice session stopped."}

    def pause(self) -> Dict[str, Any]:
        self.session.pause()
        return {"success": True, "message": "Voice session paused."}

    def resume(self) -> Dict[str, Any]:
        self.session.resume()
        return {"success": True, "message": "Voice session resumed."}

    def status(self) -> Dict[str, Any]:
        return {
            "active": self.session.active,
            "listening": self.session.listening,
            "speaking": self.session.speaking,
            "paused": self.session.paused,
        }
