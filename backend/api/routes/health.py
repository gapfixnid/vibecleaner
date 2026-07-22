import base64
import hashlib
import hmac

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ...core.version import __version__ as APP_VERSION
from ..security import (
    HEALTH_CHALLENGE_HEADER,
    HEALTH_PREFIX,
    HEALTH_PROOF_HEADER,
    decode_32_byte_base64url,
)


router = APIRouter()


@router.get("/health")
def health(request: Request):
    challenge = request.headers.get(HEALTH_CHALLENGE_HEADER)
    try:
        decode_32_byte_base64url(challenge, label="health challenge")
    except ValueError as exc:
        return JSONResponse(
            {"detail": {"code": "INVALID_HEALTH_CHALLENGE", "message": str(exc)}},
            status_code=400,
            headers={"Cache-Control": "no-store"},
        )

    message = f"{HEALTH_PREFIX}{challenge}".encode("utf-8")
    proof_bytes = hmac.new(request.app.state.session_token_bytes, message, hashlib.sha256).digest()
    proof = base64.urlsafe_b64encode(proof_bytes).rstrip(b"=").decode("ascii")
    return JSONResponse(
        {"status": "ok", "version": APP_VERSION, "protocol_version": 1},
        headers={HEALTH_PROOF_HEADER: proof, "Cache-Control": "no-store"},
    )
