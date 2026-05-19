"""OAuth ID-token verification.

The frontend obtains an ID token via the provider's SDK and POSTs it here. We
verify the signature against the provider's published JWKS, then return a
normalized claims dict.
"""
import os

import jwt
from jwt import PyJWKClient


class OAuthError(Exception):
    def __init__(self, message: str, status: int = 401):
        super().__init__(message)
        self.message = message
        self.status = status


_JWKS_CLIENTS: dict[str, PyJWKClient] = {}


def _jwks_client(uri: str) -> PyJWKClient:
    client = _JWKS_CLIENTS.get(uri)
    if client is None:
        client = PyJWKClient(uri, cache_keys=True, lifespan=3600)
        _JWKS_CLIENTS[uri] = client
    return client


def _verify(token: str, *, jwks_uri: str, audience, issuer) -> dict:
    try:
        signing_key = _jwks_client(jwks_uri).get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "iat", "iss", "sub", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise OAuthError(f"Invalid token: {exc}")


def verify_google(token: str) -> dict:
    audience = os.environ.get("GOOGLE_CLIENT_ID")
    if not audience:
        raise OAuthError("Google sign-in not configured", status=503)
    claims = _verify(
        token,
        jwks_uri="https://www.googleapis.com/oauth2/v3/certs",
        audience=audience,
        issuer=["https://accounts.google.com", "accounts.google.com"],
    )
    return {
        "sub": claims["sub"],
        "email": claims.get("email"),
        "email_verified": bool(claims.get("email_verified")),
        "name": claims.get("name"),
    }


VERIFIERS = {
    "google": verify_google,
}
