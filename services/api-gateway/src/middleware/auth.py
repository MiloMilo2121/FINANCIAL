"""JWT authentication middleware for the API Gateway.

Validates Bearer tokens on all protected endpoints.
Uses PyJWT with HS256 algorithm (symmetric key for simplicity).
In production: use RS256 with asymmetric keys stored in GCP Secret Manager.

mTLS between microservices is handled at the Kubernetes level via
GKE Managed Workload Identities — not at the application layer.
"""

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security_scheme = HTTPBearer()


def create_access_token(
    subject: str,
    secret_key: str,
    algorithm: str = "HS256",
    expires_minutes: int = 60,
) -> str:
    """Create a signed JWT access token."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret_key, algorithm=algorithm)


def verify_token(token: str, secret_key: str, algorithm: str = "HS256") -> dict:
    """Verify and decode a JWT token.

    Raises HTTPException 401 if token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")


async def require_auth(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme),
    secret_key: str = "",
) -> dict:
    """FastAPI dependency for authenticated routes."""
    return verify_token(credentials.credentials, secret_key)
