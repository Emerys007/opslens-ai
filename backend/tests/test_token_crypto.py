from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
from sqlalchemy import text

from app import db as db_module
from app.config import settings
from app.models.hubspot_installation import HubSpotInstallation
from app.services.token_crypto import decrypt_token, encrypt_token

_KEYATTR = "token_encryption_key"


class TokenCryptoUnitTests(unittest.TestCase):
    def test_round_trip_with_key(self) -> None:
        key = Fernet.generate_key().decode()
        with patch.object(settings, _KEYATTR, key):
            ciphertext = encrypt_token("super-secret-refresh-token")
            self.assertTrue(ciphertext.startswith("enc:v1:"))
            self.assertNotIn("super-secret", ciphertext)
            self.assertEqual(
                "super-secret-refresh-token", decrypt_token(ciphertext)
            )

    def test_decrypt_tolerates_legacy_plaintext(self) -> None:
        key = Fernet.generate_key().decode()
        with patch.object(settings, _KEYATTR, key):
            # A value written before encryption was enabled has no prefix.
            self.assertEqual("legacy-plaintext", decrypt_token("legacy-plaintext"))

    def test_no_key_is_passthrough(self) -> None:
        with patch.object(settings, _KEYATTR, ""):
            self.assertEqual("tok", encrypt_token("tok"))
            self.assertEqual("tok", decrypt_token("tok"))

    def test_empty_and_none(self) -> None:
        key = Fernet.generate_key().decode()
        with patch.object(settings, _KEYATTR, key):
            self.assertEqual("", encrypt_token(""))
            self.assertIsNone(encrypt_token(None))
            self.assertIsNone(decrypt_token(None))

    def test_already_encrypted_is_not_double_encrypted(self) -> None:
        key = Fernet.generate_key().decode()
        with patch.object(settings, _KEYATTR, key):
            once = encrypt_token("tok")
            twice = encrypt_token(once)
            self.assertEqual(once, twice)


class TokenCryptoStorageTests(unittest.TestCase):
    PORTAL_ID = "51300126"

    def setUp(self) -> None:
        self._key = Fernet.generate_key().decode()
        self._patcher = patch.object(settings, _KEYATTR, self._key)
        self._patcher.start()
        self._tempdir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_URL"] = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'token-crypto.sqlite')}"
        )
        db_module._engine = None
        db_module._SessionLocal = None
        db_module.init_db()

    def tearDown(self) -> None:
        self._patcher.stop()
        if db_module._engine is not None:
            db_module._engine.dispose()
        db_module._engine = None
        db_module._SessionLocal = None
        os.environ.pop("DATABASE_URL", None)
        self._tempdir.cleanup()

    def test_tokens_encrypted_at_rest_but_transparent_via_orm(self) -> None:
        session = db_module.get_session()
        try:
            session.add(
                HubSpotInstallation(
                    portal_id=self.PORTAL_ID,
                    access_token="AT-plaintext-123",
                    refresh_token="RT-plaintext-456",
                )
            )
            session.commit()
        finally:
            session.close()

        # Raw SQL (no ORM type) sees ciphertext on disk.
        session = db_module.get_session()
        try:
            raw = session.execute(
                text(
                    "SELECT access_token, refresh_token FROM hubspot_installations "
                    "WHERE portal_id = :p"
                ),
                {"p": self.PORTAL_ID},
            ).first()
            self.assertTrue(str(raw[0]).startswith("enc:v1:"))
            self.assertNotIn("AT-plaintext-123", str(raw[0]))
            self.assertTrue(str(raw[1]).startswith("enc:v1:"))
            self.assertNotIn("RT-plaintext-456", str(raw[1]))

            # ORM read transparently decrypts.
            row = session.get(HubSpotInstallation, self.PORTAL_ID)
            self.assertEqual("AT-plaintext-123", row.access_token)
            self.assertEqual("RT-plaintext-456", row.refresh_token)
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
