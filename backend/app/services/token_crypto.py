"""Encryption-at-rest for OAuth tokens.

HubSpot access/refresh tokens are encrypted with Fernet (AES-128-CBC + HMAC)
when ``TOKEN_ENCRYPTION_KEY`` is configured. Storage is **decrypt-tolerant**:
legacy plaintext rows (written before a key existed) are read back unchanged
and re-encrypted on their next write (e.g. the next token refresh). When no key
is set this is a transparent no-op, so turning encryption on is a zero-downtime
change — set the env var and tokens encrypt as they rotate.

The key MUST be a urlsafe-base64 32-byte Fernet key and MUST stay stable:
rotating it makes previously-encrypted tokens undecryptable (those portals must
reconnect). Generate one with:

    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from __future__ import annotations

import logging

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

from app.config import settings

logger = logging.getLogger(__name__)

# Marks a value as Fernet-encrypted by this module. Anything without the prefix
# is treated as legacy plaintext and returned as-is on read.
_PREFIX = "enc:v1:"


def _fernet():
    """Return a Fernet instance if a valid key is configured, else None.

    Not cached, so tests can patch ``settings.token_encryption_key`` per case.
    Construction is cheap (just decodes the key)."""
    key = str(getattr(settings, "token_encryption_key", "") or "").strip()
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet

        return Fernet(key.encode("utf-8"))
    except Exception:  # noqa: BLE001 — misconfigured key must not crash the app
        logger.error("token_crypto.invalid_key — TOKEN_ENCRYPTION_KEY is not a valid Fernet key")
        return None


def encrypt_token(plaintext: str | None) -> str | None:
    """Encrypt a token for storage. No-op when no key is set or the value is
    empty/already-encrypted."""
    if plaintext is None:
        return None
    text = str(plaintext)
    if not text or text.startswith(_PREFIX):
        return text
    fernet = _fernet()
    if fernet is None:
        return text  # no key configured -> plaintext pass-through
    return _PREFIX + fernet.encrypt(text.encode("utf-8")).decode("utf-8")


def decrypt_token(stored: str | None) -> str | None:
    """Decrypt a stored token. Legacy plaintext (no prefix) is returned as-is."""
    if stored is None:
        return None
    text = str(stored)
    if not text.startswith(_PREFIX):
        return text  # legacy plaintext or empty
    fernet = _fernet()
    if fernet is None:
        logger.error("token_crypto.cannot_decrypt — encrypted token but no/invalid key")
        return ""
    try:
        return fernet.decrypt(text[len(_PREFIX) :].encode("utf-8")).decode("utf-8")
    except Exception:  # noqa: BLE001 — wrong key / tampered data
        logger.error("token_crypto.decrypt_failed — token unreadable with current key")
        return ""


class EncryptedToken(TypeDecorator):
    """A TEXT column that transparently encrypts on write and decrypts on read.

    DB type stays TEXT, so no schema migration is needed — only the Python-side
    value transform changes."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):  # write
        return encrypt_token(value)

    def process_result_value(self, value, dialect):  # read
        return decrypt_token(value)
