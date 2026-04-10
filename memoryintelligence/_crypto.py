"""Memory Intelligence SDK - Cryptography.

AES-256-GCM encryption for client-side content protection.
All content is encrypted before leaving the caller's environment.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger("memoryintelligence")

# AES-256 requires 32-byte keys
KEY_SIZE = 32
# GCM nonce size (96 bits / 12 bytes is recommended)
NONCE_SIZE = 12
# PBKDF2 iteration count (NIST recommends 100,000+)
PBKDF2_ITERATIONS = 100000

# Fixed salt for API-key-derived encryption.
# Deterministic: same api_key → same 32-byte key on both client and server.
# Provides domain separation; rotates automatically when API key rotates.
FIXED_SALT = b"memoryintelligence:v1:content-key"


@dataclass
class EncryptedPayload:
    """Encrypted content payload for transmission."""
    ciphertext: str  # base64
    nonce: str  # base64
    tag: str  # base64
    key_id: str  # SHA-256 hash of key (for server-side key rotation support)
    algorithm: str = "AES-256-GCM"


class Encryptor:
    """
    AES-256-GCM Encryptor for secure payload handling.

    Features:
    - AES-256-GCM authenticated encryption
    - Key derivation from passphrase using PBKDF2 (100,000 iterations)
    - Nonce management for security
    - Associated data support for binding ciphertext to owner
    - Base64 encoding for transport

    Security Properties:
    - Confidentiality: AES-256 provides strong encryption
    - Integrity: GCM mode provides authentication
    - Protection against tampering and replay attacks
    """

    def __init__(self, key: bytes | None = None, passphrase: str | None = None):
        """
        Initialize the encryptor.

        Args:
            key: 32-byte encryption key (will be generated if not provided)
            passphrase: Passphrase to derive key from (alternative to direct key)

        Raises:
            ValueError: If key is provided but not 32 bytes
        """
        if key is not None:
            if len(key) != KEY_SIZE:
                raise ValueError(f"Key must be exactly {KEY_SIZE} bytes")
            self.key = key
        elif passphrase is not None:
            self.key = self._derive_key_from_passphrase(passphrase)
        else:
            # Generate a secure random key
            self.key = os.urandom(KEY_SIZE)

        self.aesgcm = AESGCM(self.key)

    def _derive_key_from_passphrase(
        self,
        passphrase: str,
        salt: bytes | None = None
    ) -> bytes:
        """
        Derive encryption key from passphrase using PBKDF2.

        Args:
            passphrase: User-provided passphrase
            salt: Optional salt (will be generated if not provided)

        Returns:
            32-byte derived key
        """
        if salt is None:
            salt = os.urandom(16)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_SIZE,
            salt=salt,
            iterations=PBKDF2_ITERATIONS,
        )

        return kdf.derive(passphrase.encode('utf-8'))

    def _generate_nonce(self) -> bytes:
        """
        Generate a cryptographically secure random nonce.

        Returns:
            12-byte nonce
        """
        return os.urandom(NONCE_SIZE)

    def encrypt_payload(
        self,
        plaintext: bytes,
        associated_data: bytes | None = None
    ) -> EncryptedPayload:
        """
        Encrypt payload using AES-256-GCM.

        Args:
            plaintext: Data to encrypt
            associated_data: Optional associated data (authenticated but not encrypted)

        Returns:
            EncryptedPayload with ciphertext and metadata
        """
        # Generate unique nonce for this encryption
        nonce = self._generate_nonce()

        # Encrypt with authenticated encryption
        ciphertext_with_tag = self.aesgcm.encrypt(nonce, plaintext, associated_data)

        # GCM combines ciphertext and tag, extract tag (last 16 bytes)
        tag = ciphertext_with_tag[-16:]
        ciphertext_only = ciphertext_with_tag[:-16]

        # Calculate key_id (SHA-256 hash of key)
        key_id = hashlib.sha256(self.key).hexdigest()

        return EncryptedPayload(
            ciphertext=base64.b64encode(ciphertext_only).decode('utf-8'),
            nonce=base64.b64encode(nonce).decode('utf-8'),
            tag=base64.b64encode(tag).decode('utf-8'),
            key_id=key_id,
        )

    def decrypt_payload(
        self,
        payload: EncryptedPayload,
        associated_data: bytes | None = None
    ) -> bytes:
        """
        Decrypt payload using AES-256-GCM.

        Args:
            payload: Encrypted payload with ciphertext, nonce, tag
            associated_data: Associated data (if used during encryption)

        Returns:
            Decrypted plaintext bytes

        Raises:
            ValueError: If decryption or authentication fails
        """
        try:
            # Decode base64 components
            ciphertext = base64.b64decode(payload.ciphertext)
            nonce = base64.b64decode(payload.nonce)
            tag = base64.b64decode(payload.tag)

            # Combine ciphertext and tag for GCM
            combined = ciphertext + tag

            # Decrypt and verify
            plaintext = self.aesgcm.decrypt(nonce, combined, associated_data)

            return plaintext

        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}") from e

    def get_key_id(self) -> str:
        """
        Get SHA-256 hash of encryption key for identification.

        Returns:
            Hex-encoded SHA-256 hash of key
        """
        return hashlib.sha256(self.key).hexdigest()

    def export_key(self) -> str:
        """
        Export key as base64-encoded string.

        WARNING: Store securely! Anyone with this key can decrypt your data.

        Returns:
            Base64-encoded encryption key
        """
        return base64.b64encode(self.key).decode('utf-8')

    @classmethod
    def from_exported_key(cls, exported_key: str) -> "Encryptor":
        """
        Create encryptor from exported key.

        Args:
            exported_key: Base64-encoded key

        Returns:
            Encryptor instance
        """
        key = base64.b64decode(exported_key)
        return cls(key=key)


class SDKEncryptor:
    """
    SDK-level encryption adapter.

    Key resolution priority:
      1. Explicit key passed to constructor
      2. MI_ENCRYPTION_KEY environment variable (base64-encoded 32-byte key)
      3. Auto-generated ephemeral key (warn user: data not recoverable across sessions)
    """

    def __init__(self, key: str | None = None):
        """
        Initialize SDK encryptor with key resolution.

        Args:
            key: Optional explicit key (base64-encoded 32-byte key)
        """
        self._ephemeral = False
        self._key_source = "explicit"

        # Priority 1: Explicit key
        if key is not None:
            try:
                decoded_key = base64.b64decode(key)
                if len(decoded_key) != KEY_SIZE:
                    raise ValueError(f"Key must be {KEY_SIZE} bytes, got {len(decoded_key)}")
                self._encryptor = Encryptor(key=decoded_key)
                self._key_source = "explicit"
                return
            except Exception as e:
                raise ValueError(f"Invalid explicit encryption key: {e}") from e

        # Priority 2: Environment variable
        env_key = os.environ.get("MI_ENCRYPTION_KEY")
        if env_key:
            try:
                decoded_key = base64.b64decode(env_key.strip())
                if len(decoded_key) != KEY_SIZE:
                    raise ValueError(f"Key must be {KEY_SIZE} bytes, got {len(decoded_key)}")
                self._encryptor = Encryptor(key=decoded_key)
                self._key_source = "environment"
                return
            except Exception as e:
                raise ValueError(f"Invalid MI_ENCRYPTION_KEY: {e}") from e

        # Priority 3: Auto-generated ephemeral key
        self._encryptor = Encryptor()  # Generates random key
        self._ephemeral = True
        self._key_source = "ephemeral"

    def encrypt_content(self, content: str, user_ulid: str) -> EncryptedPayload:
        """
        Encrypt content before sending to API.

        Args:
            content: Plaintext content to encrypt
            user_ulid: Owner's ULID (used as associated data to bind ciphertext)

        Returns:
            EncryptedPayload with ciphertext, nonce, tag, key_id
        """
        # Serialize content to JSON for consistent encoding
        plaintext = json.dumps({"content": content}, separators=(',', ':')).encode('utf-8')

        # Associated data = user_ulid (binds ciphertext to owner)
        associated_data = user_ulid.encode('utf-8')

        # Encrypt
        payload = self._encryptor.encrypt_payload(plaintext, associated_data)

        return payload

    def decrypt_content(self, payload: EncryptedPayload, user_ulid: str) -> str:
        """
        Decrypt content from API response.

        Args:
            payload: Encrypted payload
            user_ulid: Owner's ULID (must match encryption)

        Returns:
            Decrypted plaintext content

        Raises:
            ValueError: If decryption fails (wrong key or user_ulid)
        """
        associated_data = user_ulid.encode('utf-8')
        plaintext = self._encryptor.decrypt_payload(payload, associated_data)

        # Parse JSON
        data = json.loads(plaintext.decode('utf-8'))
        return data["content"]

    @classmethod
    def from_api_key(cls, api_key: str) -> "SDKEncryptor":
        """
        Create an SDKEncryptor whose key is derived from the API key.

        This is the default mode for MemoryClient when no MI_ENCRYPTION_KEY
        is set. Both client and server independently derive the same key from
        the API key using PBKDF2-SHA256 with a fixed salt, so no explicit
        key registration or exchange is needed.

        Args:
            api_key: The API key string

        Returns:
            SDKEncryptor instance using the derived key
        """
        derived = derive_key_from_api_key(api_key)
        instance = cls.__new__(cls)
        instance._encryptor = Encryptor(key=derived)
        instance._ephemeral = False
        instance._key_source = "api_key_derived"
        return instance

    def is_ephemeral(self) -> bool:
        """
        Check if using auto-generated key.

        Returns:
            True if using auto-generated key (no MI_ENCRYPTION_KEY set)
        """
        return self._ephemeral

    def get_key_id(self) -> str:
        """
        Get key identifier (SHA-256 hash of key).

        Returns:
            Hex-encoded SHA-256 hash
        """
        return self._encryptor.get_key_id()

    def export_key(self) -> str:
        """
        Export the current encryption key.

        WARNING: Store securely! Anyone with this key can decrypt your data.

        Returns:
            Base64-encoded encryption key
        """
        return self._encryptor.export_key()


# ---------------------------------------------------------------------------
# Server-side utility: derive the same key the SDK used
# ---------------------------------------------------------------------------
def derive_key_from_api_key(api_key: str) -> bytes:
    """
    Derive a 32-byte AES-256 key from an API key using PBKDF2-SHA256.

    Both the SDK (client) and the API server call this function with the same
    api_key string to independently arrive at the same encryption key — no
    explicit key exchange needed.

    Security properties:
      - 100,000 PBKDF2 iterations: brute-force resistant
      - Fixed salt provides domain separation between uses
      - Key rotates automatically when the API key is rotated

    Args:
        api_key: The API key string (e.g. "mi_sk_beta_xxx...")

    Returns:
        32-byte derived key for AES-256-GCM
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=FIXED_SALT,
        iterations=PBKDF2_ITERATIONS,
    )
    return kdf.derive(api_key.encode("utf-8"))


def log_ephemeral_warning() -> None:
    """
    Log the ephemeral key warning exactly once.
    Called by MemoryClient on initialization if is_ephemeral() is True.
    """
    logger.warning(
        "WARNING: No MI_ENCRYPTION_KEY set. Using ephemeral session key.\n"
        "Content encrypted with this key cannot be decrypted after process restart.\n"
        "Set MI_ENCRYPTION_KEY to enable persistent encryption.\n"
        "See: https://docs.memoryintelligence.io/encryption"
    )
