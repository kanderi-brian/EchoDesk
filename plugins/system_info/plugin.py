import platform
import logging
import sys

try:
    import psutil
except Exception:
    psutil = None

from ..plugin import Plugin


class SystemInfoPlugin(Plugin):
    name = "system_info"
    description = "Provides basic system information"
    version = "1.0.0"
    author = "EchoDesk"
    capabilities = ["System"]

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("echodesk.plugin.system_info")

    def can_handle(self, command: str) -> bool:
        normalized = command.strip().lower()
        return normalized in {"system info", "computer info", "pc info"}

    def execute(self, command: str):
        data = {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_count": None,
            "memory": None,
        }

        try:
            data["cpu_count"] = getattr(__import__("os"), "cpu_count", None)() if hasattr(__import__("os"), "cpu_count") else None
        except Exception:
            try:
                import multiprocessing

                data["cpu_count"] = multiprocessing.cpu_count()
            except Exception:
                data["cpu_count"] = None

        if psutil:
            try:
                vm = psutil.virtual_memory()
                data["memory"] = {"total": vm.total, "available": vm.available}
            except Exception:
                data["memory"] = None

        # Return a human readable string
        parts = [f"Python: {data['python_version']}", f"Platform: {data['platform']}"]
        if data.get("processor"):
            parts.append(f"Processor: {data['processor']}")
        if data.get("cpu_count"):
            parts.append(f"CPU count: {data['cpu_count']}")
        if data.get("memory"):
            mem = data["memory"]
            parts.append(f"Memory: total={mem.get('total')}, available={mem.get('available')}")

        return " | ".join(parts)
