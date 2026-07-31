from urllib.parse import parse_qs, urlparse


def _signup(client, monkeypatch, email="jane@example.com", password="s3cret123", name="Jane Doe"):
    captured = {}

    def fake_send_otp(to_email, otp):
        captured["otp"] = otp

    monkeypatch.setattr("apis.controllers.auth.auth_handler.send_registration_otp", fake_send_otp)

    resp = client.post(
        "/api/auth/register",
        json={"name": name, "email": email, "password": password, "companyName": "Acme Inc"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return body["data"]["pendingToken"], captured["otp"]


def _signup_and_verify(client, monkeypatch, email="jane@example.com", password="s3cret123", name="Jane Doe"):
    pending_token, otp = _signup(client, monkeypatch, email=email, password=password, name=name)
    return client.post("/api/auth/register/verify-otp", json={"pendingToken": pending_token, "otp": otp})


def test_register_stores_account_before_verification(client, monkeypatch):
    resp = client.post(
        "/api/auth/register",
        json={"name": "Jane Doe", "email": "jane@example.com", "password": "s3cret123", "companyName": "Acme"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["pendingToken"]

    # Not verified yet, so login must be rejected even with the correct password.
    resp = client.post("/api/auth/login", json={"email": "jane@example.com", "password": "s3cret123"})
    assert resp.status_code == 403
    assert resp.json()["data"]["pendingToken"]


def test_verify_otp_completes_registration_and_returns_token(client, monkeypatch):
    resp = _signup_and_verify(client, monkeypatch)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["token"]
    assert body["data"]["user"]["email"] == "jane@example.com"
    assert body["data"]["user"]["companyName"] == "Acme Inc"


def test_verify_otp_with_wrong_code_fails(client, monkeypatch):
    pending_token, _ = _signup(client, monkeypatch, email="bob@example.com")

    resp = client.post("/api/auth/register/verify-otp", json={"pendingToken": pending_token, "otp": "000000"})
    assert resp.status_code == 400
    assert resp.json()["success"] is False


def test_verify_otp_with_invalid_pending_token_fails(client):
    resp = client.post("/api/auth/register/verify-otp", json={"pendingToken": "not-a-real-token", "otp": "123456"})
    assert resp.status_code == 401


def test_login_succeeds_after_verification(client, monkeypatch):
    _signup_and_verify(client, monkeypatch, email="login@example.com", password="s3cret123")

    resp = client.post("/api/auth/login", json={"email": "login@example.com", "password": "s3cret123"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["token"]


def test_login_with_wrong_password_fails(client, monkeypatch):
    _signup_and_verify(client, monkeypatch, email="wrongpw@example.com", password="s3cret123")

    resp = client.post("/api/auth/login", json={"email": "wrongpw@example.com", "password": "nope"})
    assert resp.status_code == 401


def test_login_with_unknown_email_fails(client):
    resp = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "whatever"})
    assert resp.status_code == 401


def test_login_blocked_then_resend_otp_then_verify_flow(client, monkeypatch):
    # Sign up but never verify - simulates the OTP window lapsing, and the
    # user closing the tab before completing verification.
    _signup(client, monkeypatch, email="lapsed@example.com", password="s3cret123", name="Lapsed User")

    login_resp = client.post(
        "/api/auth/login", json={"email": "lapsed@example.com", "password": "s3cret123"}
    )
    assert login_resp.status_code == 403
    pending_token = login_resp.json()["data"]["pendingToken"]

    captured = {}
    monkeypatch.setattr(
        "apis.controllers.auth.auth_handler.send_registration_otp",
        lambda to_email, otp: captured.update(otp=otp),
    )
    resp = client.post("/api/auth/register/resend-otp", json={"pendingToken": pending_token})
    assert resp.status_code == 200, resp.text
    assert "otp" in captured
    refreshed_pending_token = resp.json()["data"]["pendingToken"]

    resp = client.post(
        "/api/auth/register/verify-otp",
        json={"pendingToken": refreshed_pending_token, "otp": captured["otp"]},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["token"]

    resp = client.post("/api/auth/login", json={"email": "lapsed@example.com", "password": "s3cret123"})
    assert resp.status_code == 200


def test_resend_otp_with_invalid_pending_token_fails(client):
    resp = client.post("/api/auth/register/resend-otp", json={"pendingToken": "not-a-real-token"})
    assert resp.status_code == 401


def test_resend_otp_for_already_verified_account_fails(client, monkeypatch):
    pending_token, otp = _signup(client, monkeypatch, email="alreadyverified@example.com", password="s3cret123")
    client.post("/api/auth/register/verify-otp", json={"pendingToken": pending_token, "otp": otp})

    resp = client.post("/api/auth/register/resend-otp", json={"pendingToken": pending_token})
    assert resp.status_code == 409


def test_me_requires_auth(client):
    resp = client.get("/api/users/me")
    assert resp.status_code == 401
    assert resp.json()["success"] is False


def test_me_returns_profile_with_valid_token(client, monkeypatch):
    verify_resp = _signup_and_verify(client, monkeypatch, email="profile@example.com")
    token = verify_resp.json()["data"]["token"]

    resp = client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["email"] == "profile@example.com"


def test_logout_requires_auth(client):
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 401


def test_logout_succeeds_with_valid_token(client, monkeypatch):
    verify_resp = _signup_and_verify(client, monkeypatch, email="logout@example.com")
    token = verify_resp.json()["data"]["token"]

    resp = client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_forgot_password_then_reset_password_flow(client, monkeypatch):
    _signup_and_verify(client, monkeypatch, email="reset@example.com", password="oldpass123")

    captured = {}
    monkeypatch.setattr(
        "apis.controllers.auth.auth_handler.send_password_reset_link",
        lambda to_email, reset_link: captured.update(reset_link=reset_link),
    )

    resp = client.post("/api/auth/forgot-password", json={"email": "reset@example.com"})
    assert resp.status_code == 200
    assert "reset_link" in captured

    token = parse_qs(urlparse(captured["reset_link"]).query)["token"][0]

    resp = client.post("/api/auth/reset-password", json={"token": token, "password": "newpass123"})
    assert resp.status_code == 200, resp.text

    resp = client.post("/api/auth/login", json={"email": "reset@example.com", "password": "oldpass123"})
    assert resp.status_code == 401

    resp = client.post("/api/auth/login", json={"email": "reset@example.com", "password": "newpass123"})
    assert resp.status_code == 200


def test_forgot_password_for_unknown_email_still_returns_success(client):
    resp = client.post("/api/auth/forgot-password", json={"email": "unknown@example.com"})
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_reset_password_with_invalid_token_fails(client):
    resp = client.post("/api/auth/reset-password", json={"token": "not-a-real-token", "password": "newpass123"})
    assert resp.status_code == 400
