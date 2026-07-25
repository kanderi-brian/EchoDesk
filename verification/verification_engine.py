"""Verification helpers for autonomous goal execution."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass
class VerificationResult:
    success: bool
    method: str
    message: str
    details: Any = None


class VerificationEngine:
    """Verify task results without coupling verification to a single engine."""

    def __init__(self, llm_engine: Any | None = None) -> None:
        self.llm_engine = llm_engine

    def verify(self, method: str, result: Any = None, expected: Any = None, **options: Any) -> VerificationResult:
        method = (method or "expected_output").strip().lower()
        if method in ("expected_output", "output", "match"):
            return self.verify_expected_output(result, expected)
        if method in ("file_exists", "file"):
            return self.verify_file_exists(options.get("path") or expected)
        if method in ("exit_code", "exit"):
            return self.verify_exit_code(options.get("exit_code", result), expected if expected is not None else 0)
        if method in ("process_status", "process"):
            return self.verify_process_status(options.get("process") or expected)
        if method == "ocr":
            return self.verify_ocr(result, expected)
        if method in ("internet_response", "internet"):
            return self.verify_internet_response(result)
        if method in ("llm_evaluation", "llm"):
            return self.verify_with_llm(result, expected)
        return VerificationResult(False, method, "Unknown verification method.")

    def verify_expected_output(self, result: Any, expected: Any = None) -> VerificationResult:
        if expected is None:
            return VerificationResult(bool(result is not None), "expected_output", "A result was returned.")
        success = str(expected).casefold() in str(result).casefold()
        return VerificationResult(success, "expected_output", "Expected output matched." if success else "Expected output was not found.")

    def verify_file_exists(self, path: str | Path | None) -> VerificationResult:
        exists = bool(path) and Path(path).exists()
        return VerificationResult(exists, "file_exists", "File exists." if exists else "Expected file does not exist.", str(path or ""))

    def verify_exit_code(self, exit_code: Any, expected: Any = 0) -> VerificationResult:
        success = exit_code == expected
        return VerificationResult(success, "exit_code", "Exit code matched." if success else f"Expected exit code {expected}, received {exit_code}.")

    def verify_process_status(self, process: Any) -> VerificationResult:
        try:
            if hasattr(process, "poll"):
                running = process.poll() is None
            elif isinstance(process, int):
                import psutil
                running = psutil.pid_exists(process)
            else:
                running = bool(process)
        except Exception:
            running = False
        return VerificationResult(running, "process_status", "Process is running." if running else "Process is not running.")

    def verify_ocr(self, text: Any, expected: Any) -> VerificationResult:
        return self.verify_expected_output(text, expected)

    def verify_internet_response(self, response: Any) -> VerificationResult:
        success = isinstance(response, str) and bool(response.strip()) and "couldn't find a clear answer" not in response.lower()
        return VerificationResult(success, "internet_response", "Internet returned usable content." if success else "Internet did not return usable content.")

    def verify_with_llm(self, result: Any, expected: Any) -> VerificationResult:
        if self.llm_engine is None:
            return self.verify_expected_output(result, expected)
        try:
            evaluation = self.llm_engine.ask(f"Answer only YES or NO. Does this result satisfy '{expected}'?\nResult: {result}")
            success = isinstance(evaluation, str) and evaluation.strip().lower().startswith("yes")
            return VerificationResult(success, "llm_evaluation", str(evaluation))
        except Exception as exc:
            return VerificationResult(False, "llm_evaluation", "LLM verification failed.", str(exc))
