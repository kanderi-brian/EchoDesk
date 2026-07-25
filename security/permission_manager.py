from __future__ import annotations


class PermissionManager:
    PERMISSIONS = {"internet", "filesystem_read", "filesystem_write", "desktop_control", "process_control", "clipboard", "microphone", "camera", "plugins", "learning", "memory"}
    ALIASES = {"internet_access": "internet", "clipboard_access": "clipboard", "voice_access": "microphone", "vision_access": "camera", "learning_access": "learning", "memory_access": "memory"}
    def __init__(self, policy_manager, audit_logger=None) -> None: self.policy, self.audit, self.temporary = policy_manager, audit_logger, set()
    def normalize(self, permission: str) -> str: return self.ALIASES.get(permission, permission)
    def allows(self, permission: str, component: str = "security") -> bool:
        allowed = self.normalize(permission) in self.temporary or self.policy.allows(self.normalize(permission))
        if self.audit: self.audit.log("permission_check" if allowed else "permission_denied", component, permission=self.normalize(permission), allowed=allowed)
        return allowed
    def grant_temporary(self, permission: str) -> bool:
        permission = self.normalize(permission)
        if permission not in self.PERMISSIONS: return False
        self.temporary.add(permission); return True
    def revoke_temporary(self, permission: str) -> None: self.temporary.discard(self.normalize(permission))
    def cleanup(self) -> None: self.temporary.clear()
