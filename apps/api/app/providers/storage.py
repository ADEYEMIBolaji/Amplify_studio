"""StorageProvider — private media storage with signed-URL access.

FRD non-negotiable rule 8: media is private, served only through signed
URLs (default 15-minute expiry). `LocalStorageProvider` simulates that
property on the local filesystem for dev/test (HMAC-signed, time-limited
tokens resolved by GET /api/media/signed/{token}); a Supabase Storage
-backed provider implementing the same interface is a drop-in replacement
once a project is linked — nothing else in the codebase needs to change.
"""

import hashlib
import hmac
import time
from abc import ABC, abstractmethod
from pathlib import Path

from app.config import get_settings

settings = get_settings()


class ObjectNotFoundError(Exception):
    pass


class SignedUrlExpiredError(Exception):
    pass


class SignedUrlInvalidError(Exception):
    pass


class StorageProvider(ABC):
    @abstractmethod
    def save(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    def read(self, key: str) -> bytes: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def signed_url(self, key: str, expires_in_seconds: int = 900) -> str: ...

    @abstractmethod
    def resolve_signed_token(self, token: str) -> str:
        """Returns the object key for a valid, unexpired token, or raises."""
        ...


class LocalStorageProvider(StorageProvider):
    def __init__(self, root_dir: Path, signing_secret: str, base_url: str):
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.signing_secret = signing_secret.encode()
        self.base_url = base_url.rstrip("/")

    def _path(self, key: str) -> Path:
        path = (self.root_dir / key).resolve()
        if self.root_dir.resolve() not in path.parents and path != self.root_dir.resolve():
            raise SignedUrlInvalidError("Object key escapes storage root.")
        return path

    def save(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def read(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise ObjectNotFoundError(key)
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def _sign(self, key: str, expires_at: int) -> str:
        message = f"{key}:{expires_at}".encode()
        return hmac.new(self.signing_secret, message, hashlib.sha256).hexdigest()

    def signed_url(self, key: str, expires_in_seconds: int = 900) -> str:
        expires_at = int(time.time()) + expires_in_seconds
        signature = self._sign(key, expires_at)
        token = f"{key}|{expires_at}|{signature}"
        token_b64 = token.encode().hex()
        return f"{self.base_url}/api/media/signed/{token_b64}"

    def resolve_signed_token(self, token: str) -> str:
        try:
            decoded = bytes.fromhex(token).decode()
            key, expires_at_str, signature = decoded.split("|", 2)
            expires_at = int(expires_at_str)
        except (ValueError, UnicodeDecodeError) as exc:
            raise SignedUrlInvalidError("Malformed signed URL token.") from exc

        expected = self._sign(key, expires_at)
        if not hmac.compare_digest(expected, signature):
            raise SignedUrlInvalidError("Signature does not match.")
        if time.time() > expires_at:
            raise SignedUrlExpiredError("This link has expired.")
        return key


_provider: StorageProvider | None = None


def get_storage_provider() -> StorageProvider:
    global _provider
    if _provider is None:
        _provider = LocalStorageProvider(
            root_dir=Path(settings.storage_root),
            signing_secret=settings.media_signing_secret,
            base_url=settings.public_api_base_url,
        )
    return _provider
