import time

import pytest
from itsdangerous import BadSignature, SignatureExpired

from app.services.upload_token import make_upload_token, verify_upload_token


def test_round_trip_returns_payload() -> None:
    token = make_upload_token(42, (2026, 4))
    payload = verify_upload_token(token)
    assert payload == {"company_id": 42, "year": 2026, "month": 4}


def test_tampered_token_rejected() -> None:
    token = make_upload_token(42, (2026, 4))
    tampered = token[:-2] + ("aa" if token[-1] != "a" else "bb")
    with pytest.raises(BadSignature):
        verify_upload_token(tampered)


def test_expired_token_rejected() -> None:
    token = make_upload_token(42, (2026, 4))
    time.sleep(2)
    with pytest.raises(SignatureExpired):
        verify_upload_token(token, max_age=1)
