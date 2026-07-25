"""Permission checks for plugin actions."""
from __future__ import annotations


class PluginPermissions:
    ALLOWED = {"internet_access", "filesystem_read", "filesystem_write", "desktop_control", "clipboard_access", "voice_access", "memory_access", "learning_access", "vision_access", "process_control"}
    def __init__(self, granted: set[str] | list[str] | None = None) -> None:
        self.granted = set(self.ALLOWED if granted is None else granted)
    def validate(self, permissions: list[str]) -> bool:
        return set(permissions).issubset(self.ALLOWED)
    def allows(self, permissions: list[str]) -> bool:
        return self.validate(permissions) and set(permissions).issubset(self.granted)
    def grant(self, permission: str) -> bool:
        if permission not in self.ALLOWED: return False
        self.granted.add(permission); return True
    def revoke(self, permission: str) -> None:
        self.granted.discard(permission)

    def set_granted(self, permissions: set[str] | list[str]) -> bool:
        """Replace grants only when every supplied permission is known."""
        candidate = set(permissions)
        if not candidate.issubset(self.ALLOWED):
            return False
        self.granted = candidate
        return True
