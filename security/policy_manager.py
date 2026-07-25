"""Configurable policy presets; callers may supply policy dictionaries at runtime."""
from __future__ import annotations
from copy import deepcopy
from typing import Any


class PolicyManager:
    PRESETS = {
        "safe": {"permissions": {"filesystem_read", "internet", "memory"}, "approval_risks": {"medium", "high"}, "allow_unrestricted": False},
        "balanced": {"permissions": {"filesystem_read", "filesystem_write", "internet", "desktop_control", "process_control", "clipboard", "microphone", "camera", "plugins", "learning", "memory"}, "approval_risks": {"high"}, "allow_unrestricted": False},
        "unrestricted": {"permissions": {"filesystem_read", "filesystem_write", "internet", "desktop_control", "process_control", "clipboard", "microphone", "camera", "plugins", "learning", "memory"}, "approval_risks": set(), "allow_unrestricted": True},
    }
    def __init__(self, policy: str = "balanced", policies: dict[str, dict[str, Any]] | None = None) -> None:
        self.policies = deepcopy(self.PRESETS)
        if policies: self.policies.update(deepcopy(policies))
        self.active_policy = "balanced"
        self.set_policy(policy)
    def set_policy(self, name: str) -> bool:
        if name not in self.policies: return False
        self.active_policy = name; return True
    def current(self) -> dict[str, Any]: return deepcopy(self.policies[self.active_policy])
    def allows(self, permission: str) -> bool: return permission in self.current()["permissions"]
    def requires_approval(self, risk: str) -> bool: return risk in self.current()["approval_risks"]
