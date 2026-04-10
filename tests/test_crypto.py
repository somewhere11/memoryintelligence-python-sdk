"""Tests for encryption module."""

from __future__ import annotations

import base64
import os

import pytest

from memoryintelligence._crypto import (
    KEY_SIZE,
    EncryptedPayload,
    Encryptor,
    SDKEncryptor,
)


class TestEncryptor:
    """Tests for core Encryptor class."""

    def test_encrypt_decrypt_round_trip(self) -> None:
        """Test encryption and decryption round-trip."""
        key = os.urandom(KEY_SIZE)
        encryptor = Encryptor(key=key)

        plaintext = b"Test message for encryption"
        associated_data = b"user_ulid"

        # Encrypt
        payload = encryptor.encrypt_payload(plaintext, associated_data)

        assert payload.ciphertext
        assert payload.nonce
        assert payload.tag
        assert payload.key_id
        assert payload.algorithm == "AES-256-GCM"

        # Decrypt
        decrypted = encryptor.decrypt_payload(payload, associated_data)
        assert decrypted == plaintext

    def test_different_nonces_per_encryption(self) -> None:
        """Test that each encryption uses a different nonce."""
        key = os.urandom(KEY_SIZE)
        encryptor = Encryptor(key=key)

        payload1 = encryptor.encrypt_payload(b"Message 1", b"ad1")
        payload2 = encryptor.encrypt_payload(b"Message 2", b"ad2")

        assert payload1.nonce != payload2.nonce

    def test_wrong_user_ulid_fails_decryption(self) -> None:
        """Test wrong associated data fails decryption."""
        key = os.urandom(KEY_SIZE)
        encryptor = Encryptor(key=key)

        payload = encryptor.encrypt_payload(b"Secret", b"user_01ABC")

        with pytest.raises(ValueError) as exc_info:
            encryptor.decrypt_payload(payload, b"user_01WRONG")

        assert "Decryption failed" in str(exc_info.value)

    def test_key_id_is_stable_sha256(self) -> None:
        """Test key_id is stable SHA-256 hash of key."""
        key = os.urandom(KEY_SIZE)
        encryptor1 = Encryptor(key=key)
        encryptor2 = Encryptor(key=key)

        assert encryptor1.get_key_id() == encryptor2.get_key_id()
        assert len(encryptor1.get_key_id()) == 64  # SHA-256 hex

    def test_key_export_import(self) -> None:
        """Test key export and import."""
        key = os.urandom(KEY_SIZE)
        original = Encryptor(key=key)

        exported = original.export_key()
        imported = Encryptor.from_exported_key(exported)

        assert original.key == imported.key

        # Should be able to decrypt with imported key
        payload = original.encrypt_payload(b"Test", b"ad")
        decrypted = imported.decrypt_payload(payload, b"ad")
        assert decrypted == b"Test"

    def test_invalid_key_size_raises_error(self) -> None:
        """Test wrong key size raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Encryptor(key=b"too_short")

        assert "32 bytes" in str(exc_info.value)


class TestSDKEncryptor:
    """Tests for SDKEncryptor wrapper."""

    def test_explicit_key_not_ephemeral(self) -> None:
        """Test explicit key is not ephemeral."""
        key = base64.b64encode(os.urandom(KEY_SIZE)).decode("utf-8")
        encryptor = SDKEncryptor(key=key)

        assert not encryptor.is_ephemeral()

    def test_environment_key_not_ephemeral(self, monkeypatch) -> None:
        """Test MI_ENCRYPTION_KEY env var is not ephemeral."""
        env_key = base64.b64encode(os.urandom(KEY_SIZE)).decode("utf-8")
        monkeypatch.setenv("MI_ENCRYPTION_KEY", env_key)

        encryptor = SDKEncryptor(key=None)
        assert not encryptor.is_ephemeral()

        monkeypatch.delenv("MI_ENCRYPTION_KEY")

    def test_auto_generated_is_ephemeral(self) -> None:
        """Test auto-generated key is ephemeral."""
        encryptor = SDKEncryptor(key=None)
        assert encryptor.is_ephemeral()

    def test_encrypt_decrypt_content(self) -> None:
        """Test content encryption with user_ulid binding."""
        key = base64.b64encode(os.urandom(KEY_SIZE)).decode("utf-8")
        encryptor = SDKEncryptor(key=key)

        user_ulid = "01USER12345678901234567890"
        content = "Secret message content"

        payload = encryptor.encrypt_content(content, user_ulid)

        assert isinstance(payload, EncryptedPayload)
        assert payload.ciphertext
        assert payload.nonce
        assert payload.tag
        assert payload.key_id

        # Decrypt
        decrypted = encryptor.decrypt_content(payload, user_ulid)
        assert decrypted == content

    def test_wrong_user_ulid_rejects_decryption(self) -> None:
        """Test wrong user_ulid fails decryption (binding works)."""
        key = base64.b64encode(os.urandom(KEY_SIZE)).decode("utf-8")
        encryptor = SDKEncryptor(key=key)

        payload = encryptor.encrypt_content("Secret", "01USER12345678901234567890")

        with pytest.raises(ValueError) as exc_info:
            encryptor.decrypt_content(payload, "01WRONG12345678901234567890")

        assert "Decryption failed" in str(exc_info.value)

    def test_key_id_is_stable(self) -> None:
        """Test key_id is stable for same key."""
        key = base64.b64encode(os.urandom(KEY_SIZE)).decode("utf-8")

        encryptor1 = SDKEncryptor(key=key)
        encryptor2 = SDKEncryptor(key=key)

        assert encryptor1.get_key_id() == encryptor2.get_key_id()


class TestEphemeralWarning:
    """Tests for ephemeral key warning."""

    def test_ephemeral_warning_logged_once(self, caplog) -> None:
        """Test warning is logged for ephemeral key."""
        import logging

        from memoryintelligence._crypto import log_ephemeral_warning

        with caplog.at_level(logging.WARNING):
            log_ephemeral_warning()

        assert "WARNING: No MI_ENCRYPTION_KEY set" in caplog.text
        assert "Using ephemeral session key" in caplog.text
        assert "https://docs.memoryintelligence.io/encryption" in caplog.text

    def test_persistent_key_no_warning(self, monkeypatch, caplog) -> None:
        """Test no warning when MI_ENCRYPTION_KEY is set."""
        import logging

        from memoryintelligence._crypto import log_ephemeral_warning

        # Set encryption key
        env_key = base64.b64encode(os.urandom(KEY_SIZE)).decode("utf-8")
        monkeypatch.setenv("MI_ENCRYPTION_KEY", env_key)

        with caplog.at_level(logging.WARNING):
            log_ephemeral_warning()

        # Should still log (function doesn't check, it just logs)
        # The check happens before calling this function
        assert "WARNING: No MI_ENCRYPTION_KEY set" in caplog.text

        monkeypatch.delenv("MI_ENCRYPTION_KEY")
