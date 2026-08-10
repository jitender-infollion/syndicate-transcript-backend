# Services Layer

This document explains each module under `src/services/`, what it's responsible for, the config/env vars it depends on, and which parts of the API (`src/apis/...`) call into it.

The services layer holds infrastructure/integration code — encryption, the DB connection, outbound email, payments, PDF generation, and the external file-signing client. Controllers/handlers in `src/apis/controllers/*` call these services; they never talk to SMTP, Postgres, Razorpay, etc. directly.

```
src/services/
├── crypto/          email + OTP hashing/encryption
├── database/        Postgres connection + Alembic migrations
├── email/           SMTP sending (OTP, reset, invoice emails)
├── payment/         Razorpay integration
├── receipt/         Purchase receipt PDF generation
├── storage/         External file-signing client (transcript access URLs)
└── transcript_pdf/  Transcript content PDF generation
```

---

## 1. Crypto (`services/crypto/`)

Two independent modules — one for reversible email encryption, one for one-way OTP hashing. Neither talks to the DB; they're pure functions over config secrets.

### `email_crypto.py`

Emails are stored encrypted at rest (`users.email_encrypted`) but still need to be looked up by exact match, so a separate deterministic hash column (`users.email_hash`) exists for lookups without ever decrypting.

```python
def _fernet() -> Fernet:
    return Fernet(get_settings().secrets.email_encryption_key.encode())

def encrypt_email(email: str) -> str:
    return _fernet().encrypt(email.encode()).decode()

def decrypt_email(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()

def hash_email(email: str) -> str:
    """Deterministic keyed hash for exact-match lookup - never decrypted, never
    used to derive the plaintext. Lowercased first so lookup stays case-insensitive."""
    secret = get_settings().secrets.email_hash_secret.encode()
    return hmac.new(secret, email.strip().lower().encode(), hashlib.sha256).hexdigest()
```

- `encrypt_email` / `decrypt_email` — symmetric Fernet encryption, used to store/read the actual plaintext email.
- `hash_email` — HMAC-SHA256 keyed with `email_hash_secret`, used only as a lookup key (login by email, uniqueness checks). The hash can never be reversed to recover the email.

**Config:** `secrets.email_encryption_key` (Fernet key), `secrets.email_hash_secret` (HMAC pepper) — both from `SecretsConfig` in `config.py`.

**Consumers:** `apis/models/user/model.py` (encrypt on write / decrypt on read, hash for the lookup column), `apis/controllers/auth/auth_handler.py` (looking up users by email during login/registration).

### `otp_crypto.py`

```python
def hash_otp(code: str) -> str:
    """Keyed hash (HMAC pepper) rather than a bare hash - a 6-digit code has only
    1M possible values, trivially brute-forced offline from a stolen DB dump
    without the server-side secret."""
    secret = get_settings().secrets.otp_hash_secret.encode()
    return hmac.new(secret, code.encode(), hashlib.sha256).hexdigest()
```

A 6-digit OTP only has 1,000,000 possible values, so a plain SHA-256 hash would be brute-forceable offline from a leaked DB dump in seconds. Keying it with a server-side secret (`otp_hash_secret`) that never leaves the app makes that infeasible.

**Config:** `secrets.otp_hash_secret`.

**Consumers:** `apis/controllers/auth/auth_handler.py` — hashes the OTP before storing it, and hashes the user-submitted code the same way to compare during verification (never stores/compares plaintext OTPs).

---

## 2. Database (`services/database/postgres/`)

### `connection.py`

Lazily-initialized SQLAlchemy engine and session factory, plus the `Base` declarative class every ORM model inherits from.

```python
Base = declarative_base()

_engine = None
_SessionLocal = None

def get_engine():
    global _engine
    if _engine is None:
        logger.info("Initializing SQLAlchemy engine")
        _engine = create_engine(get_settings().database.url, pool_pre_ping=True)
    return _engine

def get_session() -> Session:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal()
```

- Module-level singletons (`_engine`, `_SessionLocal`) so the engine/pool is created once per process, not per request.
- `pool_pre_ping=True` checks a connection is alive before handing it out — avoids errors from Postgres closing idle connections.
- `get_session()` returns a **new** `Session` on every call — callers are responsible for closing it (typically via FastAPI's dependency injection with a `try/finally` in `apis/dependencies.py`).

**Config:** `database.url` (`DATABASE_URL` env var).

**Consumers:** every handler (`auth_handler`, `cart_handler`, `inquiries_handler`, `orders_handler`, `transcripts_handler`, `users_handler`) calls `get_session()` to get a DB session; every ORM model (`apis/models/*/model.py`) inherits from `Base`.

### `migrations/`

Alembic migration environment (`env.py`) and version scripts under `migrations/versions/`. Each file is a single schema change (e.g. `add_orders_and_order_items_tables.py`, `add_idempotency_key_to_orders.py`, `scope_idempotency_key_uniqueness_to_...py`). These aren't imported by application code — they're run via the Alembic CLI (`alembic upgrade head`) against `database.url`.

---

## 3. Email (`services/email/email_service.py`)

Sends transactional email over SMTP using `smtplib`, with HTML bodies rendered from Jinja2 templates (`templates/otp_code.html`, `templates/invoice_email.html`).

```python
def _send_email(
    to_email: str,
    subject: str,
    body: str,
    html: str | None = None,
    attachment_bytes: bytes | None = None,
    attachment_filename: str | None = None,
) -> None:
    email_config = get_settings().email
    if not email_config.is_configured:
        logger.warning("SMTP is not configured; logging email instead of sending. To: %s | %s", to_email, body)
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = email_config.from_email
    message["To"] = to_email
    message.set_content(body)
    if html:
        message.add_alternative(html, subtype="html")
    if attachment_bytes and attachment_filename:
        message.add_attachment(attachment_bytes, maintype="application", subtype="pdf", filename=attachment_filename)

    try:
        if email_config.use_tls:
            with smtplib.SMTP(email_config.smtp_host, email_config.smtp_port, timeout=10) as server:
                server.starttls()
                server.login(email_config.smtp_username, email_config.smtp_password)
                server.send_message(message)
        else:
            with smtplib.SMTP_SSL(email_config.smtp_host, email_config.smtp_port, timeout=10) as server:
                server.login(email_config.smtp_username, email_config.smtp_password)
                server.send_message(message)
    except Exception:
        logger.exception("Failed to send email to %s", to_email)
        raise
```

If SMTP isn't configured (no host/user/pass/from), it logs the email content instead of sending — this is what lets local dev run without real SMTP credentials, but it silently "succeeds" without delivering anything, so it's worth checking logs if an email seems missing in dev.

Four public functions build on `_send_email`, each rendering its own template/plain-text body:

| Function | Purpose | Template |
|---|---|---|
| `send_registration_otp(email, otp)` | Email verification OTP during signup | `otp_code.html` |
| `send_login_otp(email, otp)` | Login OTP | `otp_code.html` |
| `send_password_reset_link(email, reset_link)` | Password reset | plain text only |
| `send_invoice_email(email, name, invoice_number, pdf_bytes)` | Purchase receipt, PDF attached | `invoice_email.html` |

**Config:** `email.smtp_host/port/username/password/from_email/use_tls` (`SMTP_*` env vars), `services.frontend_base_url` (used to build the logo URL embedded in emails). `OTP_TTL_MINUTES = 10` is a module constant, shown to the user in the email copy.

**Consumers:** `auth_handler.py` (registration/login OTP, password reset), `orders_handler.py` (`send_invoice_email` after a successful payment, attaching the receipt PDF from the **receipt** service).

---

## 4. Payment (`services/payment/core.py`)

`RazorpayService` wraps the `razorpay` SDK for order creation and signature verification (both for direct payment confirmation and for the async webhook).

```python
class RazorpayService:
    def __init__(self, settings):
        self.settings = settings
        payment = settings.payment
        self.currency = payment.currency
        self.client = razorpay.Client(auth=(payment.razorpay_key_id, payment.razorpay_key_secret))
        self._webhook_secret = payment.razorpay_webhook_secret

    def create_order(self, amount: int, currency: str, receipt: str) -> dict | None:
        try:
            return self.client.order.create(
                {"amount": amount, "currency": currency, "receipt": receipt, "payment_capture": 1}
            )
        except Exception:
            logger.exception("Razorpay order creation failed")
            return None

    def verify_payment_signature(self, order_id: str, payment_id: str, signature: str) -> bool:
        try:
            self.client.utility.verify_payment_signature({...})
            return True
        except SignatureVerificationError:
            return False
        except Exception:
            logger.exception("Razorpay payment signature verification errored")
            return False

    def verify_webhook_signature(self, payload: bytes, signature: str) -> bool:
        try:
            self.client.utility.verify_webhook_signature(payload.decode("utf-8"), signature, self._webhook_secret)
            return True
        except SignatureVerificationError:
            return False
        except Exception:
            logger.exception("Razorpay webhook signature verification errored")
            return False

    def parse_webhook_event(self, payload: bytes) -> dict | None:
        try:
            data = json.loads(payload)
        except Exception:
            logger.exception("Failed to parse Razorpay webhook payload")
            return None

        entity = data.get("payload", {}).get("payment", {}).get("entity", {})
        return {
            "event_type": data.get("event"),
            "gateway_order_id": entity.get("order_id"),
            "gateway_payment_id": entity.get("id"),
        }
```

- `create_order` — creates a Razorpay order server-side (`payment_capture: 1` auto-captures on success) before the client opens the checkout widget.
- `verify_payment_signature` — validates the `order_id`/`payment_id`/`signature` triple the frontend gets back from Razorpay's checkout, proving the payment wasn't tampered with client-side.
- `verify_webhook_signature` / `parse_webhook_event` — validates and parses Razorpay's async webhook callback (the authoritative payment-status source, independent of the frontend confirmation).

Every method swallows exceptions and returns `None`/`False` rather than raising, pushing the "what does failure mean" decision to the caller (order route returns an error; signature checks reject the payment).

**Config:** `payment.razorpay_key_id/razorpay_key_secret/razorpay_webhook_secret/currency` (`RAZORPAY_*`, `PAYMENT_CURRENCY` env vars — all default empty, see `PaymentConfig.is_configured`).

**Consumers:** `apis/dependencies.py` constructs the `RazorpayService` singleton (FastAPI dependency); `orders_handler.py` uses it for order creation and both signature-verification paths.

---

## 5. Receipt (`services/receipt/receipt_generator.py`)

Builds the PDF receipt attached to `send_invoice_email`, using ReportLab (`SimpleDocTemplate` + `Table`/`Paragraph` flowables).

```python
def generate_receipt_pdf(order, item_rows, user, invoice_number: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, title=f"Receipt {order.id}", ...)
    ...
    # Bill to - user-controlled fields, must be escaped before reaching
    # Paragraph's mini-XML parser (malformed markup in a name/company would
    # otherwise crash receipt generation for that user, permanently).
    elements.append(Paragraph("BILL TO", section_heading))
    bill_lines = [user.name or "-", user.email]
    if user.company_name:
        bill_lines.append(user.company_name)
    for line in bill_lines:
        elements.append(Paragraph(escape(line), body))
    ...
    doc.build(elements)
    return buffer.getvalue()
```

Layout, top to bottom:
1. **Header** — logo + "Infollion" (left), "PAYMENT RECEIPT" title + date/invoice number/customer ID (right).
2. **Bill To** — user's name, email, company (if set). `xml.sax.saxutils.escape()` is applied to every user-controlled string before it reaches `Paragraph`, since ReportLab's `Paragraph` parses its input as a small XML-like markup — an unescaped `<` or `&` in a name would otherwise raise and break receipt generation for that user permanently.
3. **Items table** — one row per purchased transcript (`item_rows` is a list of `(price, topic)` tuples).
4. **Totals** — subtotal + total paid (no tax/discount line — the system doesn't model either yet).
5. **License** — bullet list of usage terms. Note: one bullet says "Download transcript", but `transcripts_handler.get_transcript_access(mode="download")` currently returns `501 Not Implemented` — the receipt promises a capability that isn't live yet.
6. **Footer** — support email (from `email.from_email`) + thank-you line.

**Config:** reads `email.from_email` for the support contact line (no dedicated config of its own).

**Consumers:** `orders_handler.py` — generates the PDF right after a payment is confirmed, then passes the bytes into `send_invoice_email`.

---

## 6. Storage (`services/storage/signing_client.py`)

Thin HTTP client to a **separate, external backend service** that signs URLs for transcript files stored in Linode Object Storage (S3-compatible). This service itself has no AWS/S3 SDK — it delegates signing entirely.

```python
def get_signed_url(transcript_id: int, final_transcript: dict) -> str:
    """Ask the external signing service for a fresh presigned URL for this transcript's file.

    Endpoint path and auth header format are placeholders (TBD) pending that
    service's real contract - this posts the whole config.base_url as the
    endpoint for now.
    """
    settings = get_settings().signing_service
    if not settings.is_configured:
        raise HTTPException(status_code=500, detail="Signing service is not configured.")

    try:
        response = httpx.post(
            settings.base_url,
            json={"transcript_id": transcript_id, "final_transcript": final_transcript},
            headers={"Authorization": f"Bearer {settings.api_key}"},
            timeout=10,
        )
        response.raise_for_status()
        body = response.json()
    except Exception:
        logger.exception("Failed to fetch signed URL for transcript %s", transcript_id)
        raise HTTPException(status_code=502, detail="Failed to generate file access link.") from None

    url = body.get("data")
    if not url:
        logger.error("Signing service returned no url for transcript %s: %s", transcript_id, body)
        raise HTTPException(status_code=502, detail="Failed to generate file access link.")
    return url
```

**Important caveat (from the code's own docstring):** the endpoint path, request shape, and `Authorization` header format are **placeholders** — `base_url` is currently posted to directly as if it were the full endpoint, with no sub-path. This is expected to change once the actual signing service's contract is finalized; treat this client as provisional.

Any failure (misconfiguration, network error, non-2xx, missing `data` in the response) is converted to an `HTTPException` — 500 if unconfigured, 502 if the upstream call fails — so callers don't need their own error handling.

**Config:** `signing_service.base_url`, `signing_service.api_key` (`SIGNING_SERVICE_URL`, `SIGNING_SERVICE_API_KEY` — both default empty; see `SigningServiceConfig.is_configured`).

**Consumers:** `transcripts_handler.py` calls `get_signed_url` when a user requests view access to a transcript they're entitled to.

---

## 7. Transcript PDF (`services/transcript_pdf/transcript_pdf_generator.py`)

Generates a plain PDF rendering of a transcript's text content — separate and simpler than the receipt generator (no header/table layout, just a title and body paragraphs).

```python
def generate_transcript_pdf(transcript, full_text: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, title=transcript.topic or "Transcript", ...)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", parent=styles["Heading1"], fontSize=18)
    body_style = ParagraphStyle("body", parent=styles["Normal"], fontSize=10, leading=16, textColor=colors.HexColor("#374151"))

    elements = [Paragraph(escape(transcript.topic or "Untitled transcript"), title_style), Spacer(1, 0.3 * inch)]
    for line in full_text.split("\n"):
        if line.strip():
            elements.append(Paragraph(escape(line), body_style))
            elements.append(Spacer(1, 0.1 * inch))

    doc.build(elements)
    return buffer.getvalue()
```

- Title = transcript's `topic` field (falls back to "Untitled transcript").
- Body = `full_text` split on newlines, one `Paragraph` per non-blank line.
- Same `escape()` treatment as the receipt generator, and for the same reason — `full_text`/`topic` are ultimately transcript content that isn't guaranteed free of `<`/`&`, and `Paragraph` would raise on malformed markup otherwise.

No config dependency — pure function of its inputs.

**Consumers:** `transcripts_handler.py`, presumably as (or in place of) the download path — note this currently coexists with the fact that `get_transcript_access(mode="download")` returns `501` (see the Receipt section above), so it's worth confirming with the team whether this generator is fully wired up yet or still in progress.

---

## Cross-service dependency map

```
auth_handler       → crypto.email_crypto, crypto.otp_crypto, database.connection, email.email_service
cart_handler       → database.connection
inquiries_handler  → database.connection
orders_handler     → database.connection, email.email_service, payment, receipt
transcripts_handler→ database.connection, storage.signing_client, transcript_pdf
users_handler      → database.connection
apis/dependencies  → payment (RazorpayService singleton)
apis/models/*      → database.connection (Base), crypto.email_crypto (user model)
```

## Config reference (`src/config.py`)

| Service | Settings block | Env vars |
|---|---|---|
| crypto | `SecretsConfig` | `EMAIL_ENCRYPTION_KEY`, `EMAIL_HASH_SECRET`, `OTP_HASH_SECRET` |
| database | `DatabaseConfig` | `DATABASE_URL` |
| email | `EmailConfig`, `ServicesConfig.frontend_base_url` | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM`, `SMTP_USE_TLS`, `FRONTEND_BASE_URL` |
| payment | `PaymentConfig` | `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET`, `PAYMENT_CURRENCY` |
| receipt | `EmailConfig.from_email` | `SMTP_FROM` |
| storage | `SigningServiceConfig` | `SIGNING_SERVICE_URL`, `SIGNING_SERVICE_API_KEY` |
| transcript_pdf | — | — |

All of `email`, `payment`, and `storage.signing_client` degrade gracefully when unconfigured in dev (email logs instead of sending; payment/`signing_service` expose an `is_configured` flag callers can check), except `signing_client.get_signed_url`, which raises a `500` if called while unconfigured rather than silently no-op'ing.
