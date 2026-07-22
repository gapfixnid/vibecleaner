import base64
import hashlib
import hmac

import pytest
from fastapi.testclient import TestClient

from backend.api.security import HEALTH_PREFIX
from backend.main import create_app


TOKEN_BYTES = bytes([7]) * 32
TOKEN = base64.urlsafe_b64encode(TOKEN_BYTES).rstrip(b"=").decode("ascii")
CHALLENGE_BYTES = bytes([9]) * 32
CHALLENGE = base64.urlsafe_b64encode(CHALLENGE_BYTES).rstrip(b"=").decode("ascii")


def test_create_app_rejects_missing_or_noncanonical_tokens():
    for token in ["", "short", f"{TOKEN}=", "!" * 43]:
        with pytest.raises(ValueError):
            create_app(token)


def test_health_uses_the_canonical_hmac_contract():
    with TestClient(create_app(TOKEN)) as client:
        response = client.get("/health", headers={"X-VibeCleaner-Challenge": CHALLENGE})

    expected = hmac.new(
        TOKEN_BYTES,
        f"{HEALTH_PREFIX}{CHALLENGE}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    expected_proof = base64.urlsafe_b64encode(expected).rstrip(b"=").decode("ascii")
    assert response.status_code == 200
    assert response.json()["protocol_version"] == 1
    assert response.headers["X-VibeCleaner-Proof"] == expected_proof
    assert response.headers["Cache-Control"] == "no-store"


def test_health_rejects_missing_padded_or_wrong_length_challenges():
    with TestClient(create_app(TOKEN)) as client:
        assert client.get("/health").status_code == 400
        assert client.get(
            "/health", headers={"X-VibeCleaner-Challenge": f"{CHALLENGE}="}
        ).status_code == 400
        assert client.get(
            "/health", headers={"X-VibeCleaner-Challenge": "YQ"}
        ).status_code == 400


def test_all_non_health_routes_require_the_session_token():
    with TestClient(create_app(TOKEN)) as client:
        missing = client.get("/api/settings", headers={"Origin": "tauri://localhost"})
        wrong = client.get("/api/settings", headers={"X-VibeCleaner-Token": "wrong"})
        allowed = client.get("/api/settings", headers={"X-VibeCleaner-Token": TOKEN})
        protected_404 = client.get("/not-a-route")

    assert missing.status_code == 401
    assert missing.json()["detail"]["code"] == "BACKEND_UNAUTHORIZED"
    assert wrong.status_code == 401
    assert allowed.status_code == 200
    assert protected_404.status_code == 401
    assert "access-control-allow-origin" not in allowed.headers
    assert "X-VibeCleaner-Request-ID" in allowed.headers
