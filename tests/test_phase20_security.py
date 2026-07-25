"""Regression coverage for Phase 20 centralized safety controls."""
from __future__ import annotations
import unittest
from security import SecurityEngine, PolicyManager, PermissionManager, CredentialManager, ApprovalManager, AuditLogger, RiskLevel


class TestPhase20Security(unittest.TestCase):
    def test_risk_classification(self):
        security = SecurityEngine()
        self.assertEqual(security.classify_risk("read file"), RiskLevel.LOW)
        self.assertEqual(security.classify_risk("rename folder"), RiskLevel.MEDIUM)
        self.assertEqual(security.classify_risk("delete file"), RiskLevel.HIGH)

    def test_high_risk_requires_explicit_approval(self):
        security = SecurityEngine()
        denied = security.authorize("delete file", "test")
        self.assertFalse(denied.allowed)
        self.assertTrue(denied.approval_id)
        self.assertTrue(security.approvals.decide(denied.approval_id, True))
        self.assertTrue(security.authorize("delete file", "test", approval_id=denied.approval_id).allowed)

    def test_safe_policy_requires_medium_approval(self):
        security = SecurityEngine("safe")
        self.assertFalse(security.authorize("rename folder", "test").allowed)

    def test_policy_change_requires_approval(self):
        security = SecurityEngine()
        self.assertFalse(security.change_policy("safe"))
        request = security.approvals.active()[0]
        security.approvals.decide(request.id, True)
        self.assertTrue(security.change_policy("safe", request.id))

    def test_permissions_and_temporary_grants(self):
        security = SecurityEngine("safe")
        self.assertFalse(security.permissions.allows("filesystem_write"))
        self.assertTrue(security.permissions.grant_temporary("filesystem_write"))
        self.assertTrue(security.permissions.allows("filesystem_write"))
        security.permissions.cleanup()
        self.assertFalse(security.permissions.allows("filesystem_write"))

    def test_credentials_are_session_encrypted_and_redacted(self):
        audit, vault = AuditLogger(), CredentialManager(AuditLogger())
        self.assertTrue(vault.store("api", "secret-value"))
        self.assertNotIn("secret-value", str(vault._vault))
        self.assertEqual(vault.retrieve("api"), "secret-value")
        self.assertTrue(vault.delete("api"))
        audit.log("test", token="secret-value")
        self.assertEqual(audit.recent()[-1]["token"], "[REDACTED]")

    def test_approval_denial_is_final(self):
        manager = ApprovalManager()
        request = manager.request("delete", "test", "high", "test")
        self.assertTrue(manager.decide(request.id, False))
        self.assertFalse(manager.approved(request.id))
        self.assertFalse(manager.decide(request.id, True))

    def test_summary_and_cleanup(self):
        security = SecurityEngine()
        security.credentials.store("token", "value")
        security.authorize("delete data", "test")
        summary = security.summary()
        self.assertEqual(summary["active_policy"], "balanced")
        self.assertTrue(summary["recent_approvals"])
        security.cleanup_session()
        self.assertEqual(security.credentials.list(), [])
        self.assertEqual(security.approvals.active(), [])

    def test_learning_records_security_without_changing_policy(self):
        class Learning:
            def __init__(self): self.calls = []
            def record_security_event(self, *args, **kwargs): self.calls.append((args, kwargs))
        security, learning = SecurityEngine(), Learning()
        security.set_learning_engine(learning)
        security.authorize("delete file", "test")
        self.assertTrue(learning.calls)
        self.assertEqual(security.policies.active_policy, "balanced")

    def test_unknown_permissions_are_denied(self):
        permissions = PermissionManager(PolicyManager())
        self.assertFalse(permissions.allows("invented_permission"))

    def test_policy_customization(self):
        policies = {"locked": {"permissions": set(), "approval_risks": {"low", "medium", "high"}, "allow_unrestricted": False}}
        manager = PolicyManager("locked", policies)
        self.assertFalse(manager.allows("internet"))
        self.assertTrue(manager.requires_approval("low"))

    def test_audit_is_bounded(self):
        audit = AuditLogger(limit=2)
        for index in range(3): audit.log("event", value=index)
        self.assertEqual(len(audit.recent(10)), 2)

    def test_plugin_security_requires_approval_for_high_risk_command(self):
        from plugins.plugin import Plugin
        from plugins.plugin_manager import PluginManager
        class PluginUnderTest(Plugin):
            name = "security_test"
            def can_handle(self, command): return True
            def execute(self, command): return "should not run"
        manager = PluginManager(security_engine=SecurityEngine())
        self.assertTrue(manager.install(PluginUnderTest()))
        result = manager.execute("delete file")
        self.assertFalse(result["success"])
        self.assertIn("Approval", result["message"])


def _permission_case(permission):
    def test(self):
        self.assertTrue(PermissionManager(PolicyManager("balanced")).allows(permission))
    return test


def _risk_case(action, expected):
    def test(self): self.assertEqual(SecurityEngine().classify_risk(action), expected)
    return test


def _credential_case(index):
    def test(self):
        vault = CredentialManager(); name = f"credential_{index}"
        self.assertTrue(vault.store(name, f"value-{index}")); self.assertEqual(vault.retrieve(name), f"value-{index}")
    return test


for _permission in sorted(PermissionManager.PERMISSIONS):
    setattr(TestPhase20Security, f"test_balanced_permission_{_permission}", _permission_case(_permission))
for _index, (_action, _risk) in enumerate((("open app", RiskLevel.LOW), ("internet search", RiskLevel.LOW), ("write note", RiskLevel.MEDIUM), ("move folder", RiskLevel.MEDIUM), ("clipboard update", RiskLevel.MEDIUM), ("install software", RiskLevel.HIGH), ("terminate process", RiskLevel.HIGH), ("change system setting", RiskLevel.HIGH), ("execute downloaded script", RiskLevel.HIGH), ("access credential", RiskLevel.HIGH))):
    setattr(TestPhase20Security, f"test_risk_matrix_{_index}", _risk_case(_action, _risk))
for _index in range(15):
    setattr(TestPhase20Security, f"test_credential_roundtrip_{_index}", _credential_case(_index))
