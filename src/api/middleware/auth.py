import hashlib
from typing import Optional
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import structlog

from src.config import get_settings

logger = structlog.get_logger(__name__)

# Security schemes
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


class AuthContext(BaseModel):
    """Authentication context passed to route handlers."""
    user_id: str
    auth_type: str  # "api_key" or "jwt"
    scopes: list[str] = []


class AuthService:
    """
    Authentication service supporting API keys and JWT tokens.
    In production, integrate with Firebase Auth or Identity Platform.
    """

    def __init__(self):
        self.settings = get_settings()
        # Demo API keys - in production, store hashed keys in Firestore/Secret Manager
        self._demo_keys = {
            self._hash_key("demo-api-key-12345"): {
                "user_id": "demo-user",
                "scopes": ["documents:read", "documents:write"],
                "active": True
            }
        }

    def _hash_key(self, key: str) -> str:
        """Hash API key for secure comparison."""
        return hashlib.sha256(key.encode()).hexdigest()

    async def validate_api_key(self, api_key: str) -> Optional[AuthContext]:
        """Validate API key and return auth context."""
        key_hash = self._hash_key(api_key)
        key_data = self._demo_keys.get(key_hash)

        if not key_data or not key_data.get("active"):
            return None

        logger.info("api_key_authenticated", user_id=key_data["user_id"])

        return AuthContext(
            user_id=key_data["user_id"],
            auth_type="api_key",
            scopes=key_data.get("scopes", [])
        )

    async def validate_jwt(self, token: str) -> Optional[AuthContext]:
        """
        Validate JWT token from Firebase Auth.
        In production, use firebase_admin.auth.verify_id_token()
        """
        # For demo purposes, accept a simple token format
        # In production: decoded = firebase_admin.auth.verify_id_token(token)
        if token.startswith("demo-token-"):
            user_id = token.replace("demo-token-", "")
            return AuthContext(
                user_id=user_id,
                auth_type="jwt",
                scopes=["documents:read", "documents:write"]
            )
        return None


# Global auth service instance
auth_service = AuthService()


async def get_current_user(
    api_key: Optional[str] = Security(api_key_header),
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme)
) -> AuthContext:
    """
    Dependency to authenticate requests.
    Supports both API key and Bearer token authentication.
    """
    # Try API key first
    if api_key:
        auth_ctx = await auth_service.validate_api_key(api_key)
        if auth_ctx:
            return auth_ctx

    # Try Bearer token
    if bearer:
        auth_ctx = await auth_service.validate_jwt(bearer.credentials)
        if auth_ctx:
            return auth_ctx

    # No valid credentials
    logger.warning("authentication_failed", has_api_key=bool(api_key), has_bearer=bool(bearer))

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )


def require_scope(required_scope: str):
    """
    Dependency factory to require specific scopes.
    Usage: Depends(require_scope("documents:write"))
    """
    async def check_scope(auth: AuthContext = Depends(get_current_user)) -> AuthContext:
        if required_scope not in auth.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required scope: {required_scope}"
            )
        return auth

    return check_scope
