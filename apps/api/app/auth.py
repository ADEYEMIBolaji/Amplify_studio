import uuid
from dataclasses import dataclass

from fastapi import Depends, Header
from jose import JWTError, jwt

from app.config import get_settings
from app.errors import UnauthorizedError

settings = get_settings()


@dataclass(frozen=True)
class AuthUser:
    id: uuid.UUID
    email: str


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

    if not settings.supabase_jwt_secret:
        raise UnauthorizedError("Auth is not configured.")

    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except JWTError as exc:
        raise UnauthorizedError("Invalid or expired session.") from exc

    sub = payload.get("sub")
    email = payload.get("email")
    if not sub or not email:
        raise UnauthorizedError("Session is missing required claims.")

    return AuthUser(id=uuid.UUID(sub), email=email)


CurrentAuthUser = Depends(get_current_auth_user)
