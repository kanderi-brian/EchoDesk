from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Any
from .audit_logger import AuditLogger
from .policy_manager import PolicyManager
from .approval_manager import ApprovalManager
from .credential_manager import CredentialManager
from .permission_manager import PermissionManager


class RiskLevel(str, Enum): LOW="low"; MEDIUM="medium"; HIGH="high"
@dataclass
class SecurityDecision:
    allowed: bool; risk: RiskLevel; reason: str = ""; approval_id: str | None = None


class SecurityEngine:
    HIGH = ("delete", "remove file", "overwrite", "install", "system setting", "security policy", "registry", "terminate", "unknown executable", "downloaded script", "credential")
    MEDIUM = ("write", "modify", "rename", "move", "clipboard")
    def __init__(self, policy: str = "balanced", policies: dict | None = None) -> None:
        self.audit = AuditLogger(); self.policies = PolicyManager(policy, policies); self.approvals = ApprovalManager(self.audit); self.permissions = PermissionManager(self.policies, self.audit); self.credentials = CredentialManager(self.audit)
        self.learning_engine = None
    def set_learning_engine(self, learning_engine) -> None: self.learning_engine = learning_engine
    def _learn(self, event: str, success: bool, risk: RiskLevel, component: str) -> None:
        if self.learning_engine is not None:
            try: self.learning_engine.record_security_event(event, success, risk=risk.value, component=component)
            except Exception: pass
    def classify_risk(self, action: str) -> RiskLevel:
        text = str(action).casefold()
        return RiskLevel.HIGH if any(term in text for term in self.HIGH) else RiskLevel.MEDIUM if any(term in text for term in self.MEDIUM) else RiskLevel.LOW
    def authorize(self, action: str, component: str = "security", reason: str = "", permission: str | None = None, approval_id: str | None = None) -> SecurityDecision:
        risk = self.classify_risk(action)
        if permission and not self.permissions.allows(permission, component):
            self.audit.log("denied", component, action=action, reason="permission denied", risk=risk.value); self._learn("denied", False, risk, component); return SecurityDecision(False, risk, "Permission denied.")
        if self.policies.requires_approval(risk.value) and not self.approvals.approved(approval_id):
            request = self.approvals.request(action, reason or action, risk.value, component)
            self._learn("approval_required", False, risk, component)
            return SecurityDecision(False, risk, "Approval required.", request.id)
        self.audit.log("authorized", component, action=action, risk=risk.value); self._learn("authorized", True, risk, component); return SecurityDecision(True, risk)
    def change_policy(self, name: str, approval_id: str | None = None) -> bool:
        decision = self.authorize("change security policy", "security_engine", "Policy changes affect all security controls.", approval_id=approval_id)
        if not decision.allowed: return False
        changed = self.policies.set_policy(name)
        if changed: self.audit.log("policy_changed", "security_engine", policy=name)
        return changed
    def summary(self) -> dict[str, Any]:
        events = self.audit.recent(100)
        return {"active_policy": self.policies.active_policy, "recent_approvals": [item.__dict__.copy() for item in self.approvals.active()], "denied_actions": [item for item in events if item["event"] in {"denied", "permission_denied"}], "credential_usage": self.credentials.usage_count, "audit_summary": {"event_count": len(events)}, "risk_statistics": {level.value: sum(item.get("risk") == level.value for item in events) for level in RiskLevel}}
    def cleanup_session(self) -> None: self.approvals.cleanup(); self.permissions.cleanup(); self.credentials.cleanup(); self.audit.log("session_cleanup", "security_engine")
