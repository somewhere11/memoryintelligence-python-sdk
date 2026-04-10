# Frequently Asked Questions

## General

### What is Memory Intelligence?

Memory Intelligence is a meaning infrastructure for AI applications. It extracts structured meaning (entities, topics, relationships) from text and enables semantic search with full provenance tracking.

### What's the difference between v1 and v2?

| Feature | v1 | v2 |
|---------|-----|-----|
| Encryption | Optional | Mandatory |
| API Pattern | `mi.process()` | `mi.umo.process()` |
| User ID | `user_id` (any) | `user_ulid` (ULID) |
| Models | Dataclasses | Pydantic |
| EdgeClient | No | Yes (ENTERPRISE) |
| Async Support | No | Yes |

### Is my data encrypted?

**Yes.** All data is encrypted client-side with AES-256-GCM before being sent to the API. We never see your raw content.

## Installation

### What Python versions are supported?

Python 3.10, 3.11, and 3.12.

### Do I need any system dependencies?

No. The SDK is pure Python with dependencies that have wheels for all platforms.

### How do I upgrade from v1?

```bash
pip install --upgrade memoryintelligence>=2.0.0
```

See [Migration Guide](migration_v1_to_v2.md) for details.

## Authentication

### Where do I get an API key?

Sign up at [memoryintelligence.io](https://memoryintelligence.io).

### How do I set my API key?

```bash
export MI_API_KEY="mi_sk_your_key_here"
```

Or pass explicitly:
```python
mi = MemoryClient(api_key="mi_sk_your_key_here")
```

### Can I use different keys for different environments?

Yes. Use environment variables:
```bash
# Development
export MI_API_KEY="mi_sk_dev_key"

# Production
export MI_API_KEY="mi_sk_prod_key"
```

## Encryption

### Do I need to set an encryption key?

For production, **yes**. Set `MI_ENCRYPTION_KEY`:
```bash
export MI_ENCRYPTION_KEY=$(openssl rand -base64 32)
```

Without it, the SDK uses an ephemeral key that's lost on exit.

### How do I generate an encryption key?

```python
import base64, os
key = base64.b64encode(os.urandom(32)).decode()
print(f"MI_ENCRYPTION_KEY={key}")
```

### Can I rotate my encryption key?

Yes, but you'll need to re-process existing data:
1. Generate new key
2. Fetch and re-process content
3. Delete old UMOs

### What happens if I lose my encryption key?

**Your data is unrecoverable.** Store your key securely in a secrets manager.

## Usage

### What's a ULID?

ULID (Universally Unique Lexicographically Sortable Identifier) is a 26-character identifier that includes a timestamp.

Example: `01USER12345678901234567890`

### How do I generate a ULID?

```python
from ulid import ULID
user_ulid = str(ULID())
print(user_ulid)  # 01ABC12345678901234567890
```

### What's the difference between `user_ulid` and `scope_id`?

- `user_ulid`: Identifies the user who owns the content
- `scope_id`: Identifies the isolation scope (client, organization)

### When should I use `for_user()`?

When processing for multiple users in the same application:
```python
mi = MemoryClient()

for user_id in user_ids:
    user_client = mi.for_user(user_id)
    user_client.umo.process(f"Content for {user_id}")
```

## Licensing

### What license tier do I need?

| Feature | Required Tier |
|---------|---------------|
| `umo.process()` | Any |
| `umo.search()` | Any |
| `umo.match()` | PROFESSIONAL+ |
| `umo.explain()` | PROFESSIONAL+ |
| `EdgeClient` | ENTERPRISE |

### How do I upgrade my license?

Visit [memoryintelligence.io/billing](https://memoryintelligence.io/billing).

### What happens when my license expires?

You have a 14-day grace period (30 days for air-gapped). After that, operations will raise `LicenseError`.

## EdgeClient

### What's the difference between MemoryClient and EdgeClient?

| Feature | MemoryClient | EdgeClient |
|---------|--------------|------------|
| Deployment | Cloud | On-premises |
| Data leaves network | Yes | No |
| HIPAA mode | No | Yes |
| License | Any | ENTERPRISE |

### Do I need an internet connection for EdgeClient?

Not if you use `air_gapped=True`:
```python
edge = EdgeClient(
    endpoint="https://mi.local",
    air_gapped=True
)
```

### What's HIPAA mode?

HIPAA mode enforces:
- `pii_handling=HASH` (non-negotiable)
- `provenance_mode=AUDIT` (non-negotiable)

## Troubleshooting

### `ModuleNotFoundError: No module named 'memoryintelligence'`

**Fix:** Install the SDK:
```bash
pip install memoryintelligence
```

### `ConfigurationError: API key is required`

**Fix:** Set your API key:
```bash
export MI_API_KEY="mi_sk_your_key_here"
```

### `LicenseError: umo.match() requires PROFESSIONAL`

**Fix:** Upgrade your license or use allowed features:
```python
# STARTER tier can use:
mi.umo.process()
mi.umo.search()

# PROFESSIONAL+ can also use:
mi.umo.match()
mi.umo.explain()
```

### `ConfigurationError: user_ulid is required`

**Fix:** Provide a ULID:
```python
umo = mi.umo.process("content", user_ulid="01USER12345678901234567890")
```

### `ValueError: Decryption failed`

**Fix:** Use the same encryption key that was used for encryption:
```bash
export MI_ENCRYPTION_KEY="your-original-key"
```

## Performance

### How fast is processing?

Typical latency:
- Small text (<1KB): 100-200ms
- Medium text (1-10KB): 200-500ms
- Large text (10-100KB): 500ms-2s

### Can I process multiple items in parallel?

Use `AsyncMemoryClient`:
```python
from memoryintelligence import AsyncMemoryClient

mi = await AsyncMemoryClient()

# Process concurrently
import asyncio
await asyncio.gather(
    mi.umo.process("Item 1", user_ulid="01USER1"),
    mi.umo.process("Item 2", user_ulid="01USER2"),
    mi.umo.process("Item 3", user_ulid="01USER3"),
)
```

## Security & Compliance

### Is the SDK HIPAA compliant?

Use `EdgeClient` with `hipaa_mode=True` for HIPAA compliance. Data never leaves your infrastructure.

### How do I delete user data for GDPR?

```python
result = mi.umo.delete(user_ulid="01USER12345678901234567890")
print(f"Deleted {result.deleted_count} UMOs")
```

### Where is data stored?

- **MemoryClient**: Encrypted in Memory Intelligence cloud
- **EdgeClient**: Your infrastructure only

## Support

### Where can I get help?

- **Documentation:** [docs.memoryintelligence.io](https://docs.memoryintelligence.io)
- **Email:** sdk@memoryintelligence.io
- **Issues:** [github.com/memoryintelligence/sdk-python/issues](https://github.com/memoryintelligence/sdk-python/issues)

### How do I report a security issue?

Email security@memoryintelligence.io with details.

### Is there enterprise support?

Yes. Contact enterprise@memoryintelligence.io for SLAs and dedicated support.
