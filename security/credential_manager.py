"""Session-only encrypted credential vault. Platform vaults can replace this adapter later."""
from __future__ import annotations
import base64, hashlib, secrets


class CredentialManager:
    def __init__(self, audit_logger=None) -> None:
        self._key, self._vault, self.audit, self.usage_count = secrets.token_bytes(32), {}, audit_logger, 0
    def _crypt(self, value: bytes) -> bytes:
        stream = hashlib.pbkdf2_hmac("sha256", self._key, b"echodesk-session-vault", 1000, dklen=max(1, len(value)))
        return bytes(left ^ right for left, right in zip(value, stream))
    def store(self, name: str, secret: str, component: str = "credential_manager") -> bool:
        if not name or not isinstance(secret, str): return False
        self._vault[name] = base64.b64encode(self._crypt(secret.encode("utf-8"))).decode("ascii")
        if self.audit: self.audit.log("credential_stored", component, credential_name=name)
        return True
    def retrieve(self, name: str, component: str = "credential_manager") -> str | None:
        item = self._vault.get(name)
        if item is None: return None
        self.usage_count += 1
        if self.audit: self.audit.log("credential_access", component, credential_name=name)
        return self._crypt(base64.b64decode(item)).decode("utf-8")
    def delete(self, name: str, component: str = "credential_manager") -> bool:
        existed = self._vault.pop(name, None) is not None
        if existed and self.audit: self.audit.log("credential_deleted", component, credential_name=name)
        return existed
    def list(self) -> list[str]: return sorted(self._vault)
    def cleanup(self) -> None: self._vault.clear()
