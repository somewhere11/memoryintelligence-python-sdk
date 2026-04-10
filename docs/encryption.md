# Encryption Guide

Memory Intelligence SDK uses **mandatory client-side encryption** to protect your data.

## Overview

All content is encrypted using **AES-256-GCM** before being sent over the network:

- **Algorithm:** AES-256-GCM (Authenticated Encryption)
- **Key Derivation:** PBKDF2 with 100,000 iterations
- **Key Size:** 256 bits (32 bytes)
- **Nonce:** 96 bits (12 bytes), random per encryption
- **Associated Data:** user_ulid for binding

## Quick Start

### Default Behavior

By default, the SDK generates an **ephemeral session key**:

```python
from memoryintelligence import MemoryClient

mi = MemoryClient()
# WARNING: No MI_ENCRYPTION_KEY set. Using ephemeral session key.
```

**⚠️ Warning:** Ephemeral keys are lost when the process exits. For production, set a persistent key.

### Production Setup

Set `MI_ENCRYPTION_KEY` environment variable:

```bash
# Generate a secure key
export MI_ENCRYPTION_KEY=$(openssl rand -base64 32)

# Or use Python
export MI_ENCRYPTION_KEY=$(python3 -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())")
```

```python
from memoryintelligence import MemoryClient

mi = MemoryClient()  # Uses MI_ENCRYPTION_KEY
```

## Understanding Encryption Keys

### Key Types

| Type | Persistence | Use Case |
|------|-------------|----------|
| **Persistent** | Saved in env var | Production |
| **Ephemeral** | Lost on exit | Development, testing |

### Check Key Type

```python
from memoryintelligence._crypto import SDKEncryptor

encryptor = SDKEncryptor()
if encryptor.is_ephemeral():
    print("⚠️ Using ephemeral key - data will be unreadable after restart")
else:
    print("✓ Using persistent encryption key")
```

## Key Management

### Generate a New Key

```python
import base64
import os

# Generate 32 random bytes
key_bytes = os.urandom(32)
key_b64 = base64.b64encode(key_bytes).decode("utf-8")

print(f"MI_ENCRYPTION_KEY={key_b64}")
```

## How Encryption Works

### Encryption Flow

```
1. User content: "The budget meeting with Sarah..."
2. Serialize: {"content": "The budget meeting with Sarah..."}
3. Encrypt with AES-256-GCM:
   - Key: Your MI_ENCRYPTION_KEY
   - Nonce: Random 12 bytes
   - Associated Data: user_ulid
4. Result: EncryptedPayload
   - ciphertext: bytes
   - nonce: bytes
   - tag: 16 bytes (authentication)
   - key_id: SHA-256 hash of key
   - algorithm: "AES-256-GCM"
```

## Security Properties

### Confidentiality

- **AES-256-GCM** provides industry-standard encryption
- **256-bit keys** are unbreakable with current technology
- **Unique nonce** per encryption prevents pattern analysis

### Authenticity

- **GCM authentication tag** ensures data hasn't been tampered
- **Associated Data (user_ulid)** binds ciphertext to specific user

### User Binding

Content is cryptographically bound to the user_ulid:

```python
# Encrypt for user A
payload = encryptor.encrypt_content("Secret", "01USER_A12345678901234567890")

# Cannot decrypt for user B
try:
    encryptor.decrypt_content(payload, "01USER_B12345678901234567890")
except ValueError as e:
    print(f"Decryption failed: {e}")  # Wrong associated data
```

## Enterprise Key Management

### AWS KMS Integration

```python
import boto3
from memoryintelligence import MemoryClient

# Decrypt key from AWS KMS
kms = boto3.client("kms")
encrypted_key = get_encrypted_key_from_secrets_manager()

response = kms.decrypt(CiphertextBlob=encrypted_key)
encryption_key = base64.b64encode(response["Plaintext"]).decode()

mi = MemoryClient(encryption_key=encryption_key)
```

## Compliance

### HIPAA

For HIPAA compliance, use EdgeClient with `hipaa_mode=True`:

```python
from memoryintelligence import EdgeClient

edge = EdgeClient(
    endpoint="https://mi.internal.hospital.com",
    api_key="mi_sk_enterprise_key",
    hipaa_mode=True  # Enforces pii_handling=HASH, provenance_mode=AUDIT
)
```

### GDPR

Right to erasure is supported:

```python
# Delete all data for a user
result = mi.umo.delete(user_ulid="01USER12345678901234567890")
print(f"Deleted {result.deleted_count} UMOs")
```

## Best Practices

1. **Use persistent keys in production**
2. **Rotate keys quarterly**
3. **Store keys in secrets manager (AWS Secrets Manager, HashiCorp Vault)**
4. **Never commit keys to version control**
5. **Use different keys per environment**

## Support

- **Documentation:** [docs.memoryintelligence.io](https://docs.memoryintelligence.io)
- **Security:** security@memoryintelligence.io
