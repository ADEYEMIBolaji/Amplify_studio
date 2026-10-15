import time
import uuid
from dataclasses import dataclass

import httpx
from fastapi import Depends, Header
from jose import JWTError, jwt

from app.config import get_settings
from app.errors import UnauthorizedError

settings = get_settings()


@dataclass(frozen=True)
class AuthUser:
    id: uuid.UUID
    email: str


# Newer Supabase projects sign access tokens asymmetrically (ES256, rotating
# keys) rather than with the legacy shared HS256 secret; either can appear
# depending on when the project was created, so both are supported here.
# The JWKS is small and rotates rarely — an in-process cache with a short
# TTL avoids a round trip on every request without risking a stale key.
_jwks_cache: dict = {"keys": None, "fetched_at": 0.0}
_JWKS_TTL_SECONDS = 3600


async def _get_jwks() -> list[dict]:
    now = time.monotonic()
    if _jwks_cache["keys"] is None or now - _jwks_cache["fetched_at"] > _JWKS_TTL_SECONDS:
        url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(url)
            response.raise_for_status()
            _jwks_cache["keys"] = response.json()["keys"]
            _jwks_cache["fetched_at"] = now
    return _jwks_cache["keys"]


async def get_current_auth_user(
    authorization: str | None = Header(default=None),
) -> AuthUser:
    """Verifies the Supabase-issued JWT sent by the frontend.

    FastAPI connects to Supabase with the service role (bypasses RLS), so
    this is the only place that establishes *who* is calling — every
    downstream handler must still check workspace ownership explicitly
    (FRD section 1, non-negotiable rule 1).
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Missing or malformed Authorization header.")

    token = authorization.split(" ", 1)[1]

    try:
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg", "HS256")
        key: str | dict

        if algorithm == "HS256":
            if not settings.supabase_jwt_secret:
                raise UnauthorizedError("Auth is not configured.")
            key = settings.supabase_jwt_secret
        else:
            keys = await _get_jwks()
            jwk = next((k for k in keys if k.get("kid") == header.get("kid")), None)
            if jwk is None:
                raise UnauthorizedError("Session was signed with an unrecognised key.")
            key = jwk

        payload = jwt.decode(token, key, algorithms=[algorithm], audience="authenticated")
    except JWTError as exc:
        raise UnauthorizedError("Invalid or expired session.") from exc
    except httpx.HTTPError as exc:
        raise UnauthorizedError("Couldn't verify the session right now.") from exc

    sub = payload.get("sub")
    email = payload.get("email")
    if not sub or not email:
        raise UnauthorizedError("Session is missing required claims.")

    return AuthUser(id=uuid.UUID(sub), email=email)


CurrentAuthUser = Depends(get_current_auth_user)
