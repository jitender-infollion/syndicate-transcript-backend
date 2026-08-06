import json
import uuid

from sqlalchemy import text

from test_transcripts_api import _auth_headers, _grant_entitlement, _seed_author, _seed_transcript, _signup_and_verify


class _FakeGateway:
    """Stands in for RazorpayService - no network calls, deterministic signature checks."""

    _counter = 0

    def __init__(self, settings):
        self.settings = settings
        self.currency = settings.payment.currency

    def create_order(self, amount, currency, receipt):
        _FakeGateway._counter += 1
        return {"id": f"order_fake_{_FakeGateway._counter}"}

    def verify_payment_signature(self, order_id, payment_id, signature):
        return signature == "valid-signature"

    def verify_webhook_signature(self, payload, signature):
        return signature == "valid-signature"

    def parse_webhook_event(self, payload):
        data = json.loads(payload)
        return {
            "event_type": data["event"],
            "gateway_order_id": data["gateway_order_id"],
            "gateway_payment_id": data.get("gateway_payment_id"),
        }


def _use_fake_gateway(monkeypatch):
    monkeypatch.setattr("apis.dependencies.RazorpayService", _FakeGateway)


def _create_order(client, token, transcript_ids, idempotency_key=None, amount=1, currency="USD"):
    headers = _auth_headers(token)
    headers["Idempotency-Key"] = idempotency_key or str(uuid.uuid4())
    return client.post(
        "/api/orders",
        json={"amount": amount, "currency": currency, "transcriptIds": transcript_ids},
        headers=headers,
    )


def _verify(client, token, razorpay_order_id, signature="valid-signature", payment_id="pay_1"):
    return client.post(
        "/api/orders/verify",
        json={
            "razorpay_order_id": razorpay_order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        },
        headers=_auth_headers(token),
    )


def _webhook(client, event, gateway_order_id, gateway_payment_id=None, signature="valid-signature", event_id="evt_1"):
    return client.post(
        "/api/orders/webhook/razorpay",
        json={"event": event, "gateway_order_id": gateway_order_id, "gateway_payment_id": gateway_payment_id},
        headers={"X-Razorpay-Signature": signature, "X-Razorpay-Event-Id": event_id},
    )


def test_create_order_ignores_client_amount_and_recomputes_from_price(client, monkeypatch, engine):
    _use_fake_gateway(monkeypatch)
    token, _ = _signup_and_verify(client, monkeypatch)
    author_id = _seed_author(engine)
    t1 = _seed_transcript(engine, author_id, price=49)
    t2 = _seed_transcript(engine, author_id, price=99)

    resp = _create_order(client, token, [t1, t2], amount=1, currency="INR")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["amount"] == 148
    assert data["currency"] == "USD"
    assert sorted(data["transcriptIds"]) == sorted([t1, t2])
    assert data["razorpayOrderId"].startswith("order_fake_")


def test_create_order_requires_idempotency_key_header(client, monkeypatch):
    _use_fake_gateway(monkeypatch)
    token, _ = _signup_and_verify(client, monkeypatch)

    resp = client.post(
        "/api/orders",
        json={"amount": 1, "currency": "USD", "transcriptIds": [1]},
        headers=_auth_headers(token),
    )
    assert resp.status_code == 422, resp.text


def test_create_order_same_idempotency_key_returns_same_order(client, monkeypatch, engine):
    _use_fake_gateway(monkeypatch)
    token, _ = _signup_and_verify(client, monkeypatch)
    author_id = _seed_author(engine)
    transcript_id = _seed_transcript(engine, author_id)
    key = str(uuid.uuid4())

    first = _create_order(client, token, [transcript_id], idempotency_key=key)
    second = _create_order(client, token, [transcript_id], idempotency_key=key)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["data"]["orderId"] == second.json()["data"]["orderId"]
    assert first.json()["data"]["razorpayOrderId"] == second.json()["data"]["razorpayOrderId"]

    orders_resp = client.get("/api/orders", headers=_auth_headers(token))
    assert len(orders_resp.json()["data"]) == 1


def test_create_order_rejects_inactive_or_missing_transcript(client, monkeypatch):
    _use_fake_gateway(monkeypatch)
    token, _ = _signup_and_verify(client, monkeypatch)

    resp = _create_order(client, token, [999999])
    assert resp.status_code == 400, resp.text


def test_create_order_rejects_already_owned_transcript(client, monkeypatch, engine):
    _use_fake_gateway(monkeypatch)
    token, user_id = _signup_and_verify(client, monkeypatch)
    author_id = _seed_author(engine)
    transcript_id = _seed_transcript(engine, author_id)
    _grant_entitlement(engine, user_id, transcript_id)

    resp = _create_order(client, token, [transcript_id])
    assert resp.status_code == 400, resp.text


def test_create_order_requires_auth(client, monkeypatch):
    _use_fake_gateway(monkeypatch)
    resp = client.post(
        "/api/orders",
        json={"amount": 1, "currency": "USD", "transcriptIds": [1]},
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert resp.status_code == 401, resp.text


def test_verify_payment_valid_signature_marks_paid_and_grants_entitlement(client, monkeypatch, engine):
    _use_fake_gateway(monkeypatch)
    token, _ = _signup_and_verify(client, monkeypatch)
    author_id = _seed_author(engine)
    transcript_id = _seed_transcript(engine, author_id)

    create_resp = _create_order(client, token, [transcript_id])
    razorpay_order_id = create_resp.json()["data"]["razorpayOrderId"]

    verify_resp = _verify(client, token, razorpay_order_id)
    assert verify_resp.status_code == 200, verify_resp.text
    assert verify_resp.json()["data"]["status"] == "paid"

    purchased = client.get("/api/transcripts/me/purchased", headers=_auth_headers(token))
    assert transcript_id in [item["id"] for item in purchased.json()["data"]["items"]]


def test_verify_payment_creates_invoice(client, monkeypatch, engine):
    _use_fake_gateway(monkeypatch)
    token, user_id = _signup_and_verify(client, monkeypatch)
    author_id = _seed_author(engine)
    transcript_id = _seed_transcript(engine, author_id, price=49)

    create_resp = _create_order(client, token, [transcript_id])
    razorpay_order_id = create_resp.json()["data"]["razorpayOrderId"]
    order_id = int(create_resp.json()["data"]["orderId"])

    verify_resp = _verify(client, token, razorpay_order_id)
    assert verify_resp.status_code == 200, verify_resp.text

    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT order_id, user_id, amount, currency, invoice_number FROM invoices WHERE order_id = :order_id"),
            {"order_id": order_id},
        ).fetchone()
    assert row is not None
    assert row.user_id == user_id
    assert row.amount == 49
    assert row.currency == "USD"
    assert row.invoice_number.startswith("INV-")


def test_verify_payment_invalid_signature_marks_failed(client, monkeypatch, engine):
    _use_fake_gateway(monkeypatch)
    token, _ = _signup_and_verify(client, monkeypatch)
    author_id = _seed_author(engine)
    transcript_id = _seed_transcript(engine, author_id)

    create_resp = _create_order(client, token, [transcript_id])
    razorpay_order_id = create_resp.json()["data"]["razorpayOrderId"]

    verify_resp = _verify(client, token, razorpay_order_id, signature="bad-signature")
    assert verify_resp.status_code == 200, verify_resp.text
    assert verify_resp.json()["data"]["status"] == "failed"


def test_webhook_after_verify_does_not_double_grant(client, monkeypatch, engine):
    _use_fake_gateway(monkeypatch)
    token, _ = _signup_and_verify(client, monkeypatch)
    author_id = _seed_author(engine)
    transcript_id = _seed_transcript(engine, author_id)

    create_resp = _create_order(client, token, [transcript_id])
    razorpay_order_id = create_resp.json()["data"]["razorpayOrderId"]

    _verify(client, token, razorpay_order_id)

    webhook_resp = _webhook(client, "payment.captured", razorpay_order_id, "pay_1")
    assert webhook_resp.status_code == 200, webhook_resp.text

    purchased = client.get("/api/transcripts/me/purchased", headers=_auth_headers(token))
    purchased_ids = [item["id"] for item in purchased.json()["data"]["items"]]
    assert purchased_ids.count(transcript_id) == 1


def test_duplicate_webhook_event_id_is_noop(client, monkeypatch, engine):
    _use_fake_gateway(monkeypatch)
    token, _ = _signup_and_verify(client, monkeypatch)
    author_id = _seed_author(engine)
    transcript_id = _seed_transcript(engine, author_id)

    create_resp = _create_order(client, token, [transcript_id])
    razorpay_order_id = create_resp.json()["data"]["razorpayOrderId"]

    first = _webhook(client, "payment.captured", razorpay_order_id, "pay_1", event_id="evt_dup")
    assert first.status_code == 200, first.text

    second = _webhook(client, "payment.captured", razorpay_order_id, "pay_1", event_id="evt_dup")
    assert second.status_code == 200, second.text

    purchased = client.get("/api/transcripts/me/purchased", headers=_auth_headers(token))
    purchased_ids = [item["id"] for item in purchased.json()["data"]["items"]]
    assert purchased_ids.count(transcript_id) == 1


def test_list_orders_returns_only_own_orders(client, monkeypatch, engine):
    _use_fake_gateway(monkeypatch)
    token_a, _ = _signup_and_verify(client, monkeypatch, email="a@example.com")
    token_b, _ = _signup_and_verify(client, monkeypatch, email="b@example.com")
    author_id = _seed_author(engine)
    transcript_id = _seed_transcript(engine, author_id)

    _create_order(client, token_a, [transcript_id])

    resp_a = client.get("/api/orders", headers=_auth_headers(token_a))
    resp_b = client.get("/api/orders", headers=_auth_headers(token_b))
    assert len(resp_a.json()["data"]) == 1
    assert len(resp_b.json()["data"]) == 0


def test_receipt_404_for_unpaid_order(client, monkeypatch, engine):
    _use_fake_gateway(monkeypatch)
    token, _ = _signup_and_verify(client, monkeypatch)
    author_id = _seed_author(engine)
    transcript_id = _seed_transcript(engine, author_id)

    create_resp = _create_order(client, token, [transcript_id])
    order_id = create_resp.json()["data"]["orderId"]

    resp = client.get(f"/api/orders/{order_id}/receipt", headers=_auth_headers(token))
    assert resp.status_code == 404, resp.text


def test_receipt_404_for_other_users_order(client, monkeypatch, engine):
    _use_fake_gateway(monkeypatch)
    token_a, _ = _signup_and_verify(client, monkeypatch, email="owner@example.com")
    token_b, _ = _signup_and_verify(client, monkeypatch, email="other@example.com")
    author_id = _seed_author(engine)
    transcript_id = _seed_transcript(engine, author_id)

    create_resp = _create_order(client, token_a, [transcript_id])
    razorpay_order_id = create_resp.json()["data"]["razorpayOrderId"]
    order_id = create_resp.json()["data"]["orderId"]

    _verify(client, token_a, razorpay_order_id)

    resp = client.get(f"/api/orders/{order_id}/receipt", headers=_auth_headers(token_b))
    assert resp.status_code == 404, resp.text


def test_receipt_returns_pdf_for_paid_order(client, monkeypatch, engine):
    _use_fake_gateway(monkeypatch)
    token, _ = _signup_and_verify(client, monkeypatch)
    author_id = _seed_author(engine)
    transcript_id = _seed_transcript(engine, author_id)

    create_resp = _create_order(client, token, [transcript_id])
    razorpay_order_id = create_resp.json()["data"]["razorpayOrderId"]
    order_id = create_resp.json()["data"]["orderId"]

    _verify(client, token, razorpay_order_id)

    resp = client.get(f"/api/orders/{order_id}/receipt", headers=_auth_headers(token))
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"
