import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from verification.verification_engine import VerificationEngine


class TestVerificationEngine(unittest.TestCase):
    def setUp(self):
        self.engine = VerificationEngine()

    def test_expected_output_matches_case_insensitively(self):
        self.assertTrue(self.engine.verify("expected_output", "Hello EchoDesk", "hello").success)

    def test_expected_output_failure(self):
        self.assertFalse(self.engine.verify("expected_output", "one", "two").success)

    def test_expected_output_accepts_any_non_none_result_without_expected_value(self):
        self.assertTrue(self.engine.verify("expected_output", "result").success)

    def test_file_exists_success(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.txt"
            path.touch()
            self.assertTrue(self.engine.verify("file_exists", expected=str(path)).success)

    def test_file_exists_failure(self):
        self.assertFalse(self.engine.verify("file_exists", expected="missing-file").success)

    def test_exit_code_success(self):
        self.assertTrue(self.engine.verify("exit_code", result=0).success)

    def test_exit_code_failure(self):
        self.assertFalse(self.engine.verify("exit_code", result=1).success)

    def test_process_status_accepts_running_process_like_object(self):
        process = Mock()
        process.poll.return_value = None
        self.assertTrue(self.engine.verify("process_status", expected=process).success)

    def test_process_status_rejects_finished_process(self):
        process = Mock()
        process.poll.return_value = 0
        self.assertFalse(self.engine.verify("process_status", expected=process).success)

    def test_ocr_verification(self):
        self.assertTrue(self.engine.verify("ocr", "Invoice total: 12", "total").success)

    def test_internet_response_requires_usable_content(self):
        self.assertTrue(self.engine.verify("internet_response", "A useful search result").success)

    def test_internet_response_rejects_fallback_message(self):
        self.assertFalse(self.engine.verify("internet_response", "I couldn't find a clear answer from the internet right now.").success)

    def test_llm_evaluation_uses_llm_when_available(self):
        llm = Mock()
        llm.ask.return_value = "YES"
        self.assertTrue(VerificationEngine(llm).verify("llm", "done", "done").success)

    def test_llm_evaluation_falls_back_when_unavailable(self):
        self.assertTrue(self.engine.verify("llm", "done", "done").success)

    def test_unknown_verification_method_fails_cleanly(self):
        self.assertFalse(self.engine.verify("not-a-method").success)


if __name__ == "__main__":
    unittest.main()
