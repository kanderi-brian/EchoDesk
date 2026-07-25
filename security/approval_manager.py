from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid


@dataclass
class ApprovalRequest:
    action: str; reason: str; risk_level: str; component: str; timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat()); id: str = field(default_factory=lambda: str(uuid.uuid4())); status: str = "pending"


class ApprovalManager:
    def __init__(self, audit_logger=None) -> None: self.requests: dict[str, ApprovalRequest] = {}; self.audit = audit_logger
    def request(self, action: str, reason: str, risk_level: str, component: str) -> ApprovalRequest:
        item = ApprovalRequest(action, reason, risk_level, component); self.requests[item.id] = item
        if self.audit: self.audit.log("approval_requested", component, approval_id=item.id, action=action, risk=risk_level)
        return item
    def decide(self, request_id: str, approved: bool) -> bool:
        item = self.requests.get(request_id)
        if not item or item.status != "pending": return False
        item.status = "approved" if approved else "denied"
        if self.audit: self.audit.log("approval_" + item.status, item.component, approval_id=item.id, action=item.action)
        return True
    def approved(self, request_id: str | None) -> bool: return bool(request_id and self.requests.get(request_id) and self.requests[request_id].status == "approved")
    def active(self) -> list[ApprovalRequest]: return [item for item in self.requests.values() if item.status == "pending"]
    def cleanup(self) -> None: self.requests.clear()
