from app.security import create_access_token, decode_token, verify_credentials


def test_verify_credentials_ok(settings):
    assert verify_credentials("admin", "secret", settings) is True


def test_verify_credentials_wrong_user(settings):
    assert verify_credentials("root", "secret", settings) is False


def test_verify_credentials_empty(settings):
    assert verify_credentials("", "", settings) is False


def test_token_roundtrip(settings):
    token, ttl = create_access_token("admin", settings)
    assert ttl > 0
    payload = decode_token(token, settings)
    assert payload["sub"] == "admin"
    assert "exp" in payload
