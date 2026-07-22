import base64
import re
import secrets
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


SESSION_TOKEN_ENV = "VIBECLEANER_SESSION_TOKEN"
TOKEN_HEADER = "X-VibeCleaner-Token"
REQUEST_ID_HEADER = "X-VibeCleaner-Request-ID"
HEALTH_CHALLENGE_HEADER = "X-VibeCleaner-Challenge"
HEALTH_PROOF_HEADER = "X-VibeCleaner-Proof"
HEALTH_PREFIX = "vibecleaner-health-v1:"

_BASE64URL_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def decode_32_byte_base64url(value: str | None, *, label: str) -> bytes:
    if not value or "=" in value or not _BASE64URL_RE.fullmatch(value):
        raise ValueError(f"{label} must be unpadded Base64URL")
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError(f"{label} must be valid Base64URL") from exc
    if len(decoded) != 32:
        raise ValueError(f"{label} must decode to exactly 32 bytes")
    if base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii") != value:
        raise ValueError(f"{label} must use canonical Base64URL encoding")
    return decoded


def canonical_token(value: str) -> bytes:
    return decode_32_byte_base64url(value, label="session token")


def request_id(value: str | None) -> str:
    if value and _REQUEST_ID_RE.fullmatch(value):
        return value
    return secrets.token_urlsafe(16).rstrip("=")


class SessionAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        correlation_id = request_id(request.headers.get(REQUEST_ID_HEADER))
        request.state.request_id = correlation_id
        if request.url.path != "/health":
            provided = request.headers.get(TOKEN_HEADER, "")
            try:
                provided_bytes = decode_32_byte_base64url(provided, label="session token")
            except ValueError:
                provided_bytes = b""
            expected = request.app.state.session_token_bytes
            if not secrets.compare_digest(provided_bytes, expected):
                response: Response = JSONResponse(
                    {
                        "detail": {
                            "code": "BACKEND_UNAUTHORIZED",
                            "message": "The local backend session token is missing or invalid.",
                        }
                    },
                    status_code=401,
                )
                response.headers[REQUEST_ID_HEADER] = correlation_id
                response.headers["Cache-Control"] = "no-store"
                return response
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = correlation_id
        return response
