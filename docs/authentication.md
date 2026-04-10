# Authentication Guide

Complete guide to API authentication with the Memory Intelligence SDK.

## API Key Format

Memory Intelligence API keys follow this format:

```
mi_sk_<40-character-random-string>
```

Example:
```
mi_sk_abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
```

## Methods to Provide API Key

### Method 1: Environment Variable (Recommended)

Set `MI_API_KEY` in your environment:

```bash
# Linux/macOS
export MI_API_KEY="mi_sk_your_key_here"

# Windows PowerShell
$env:MI_API_KEY="mi_sk_your_key_here"

# Windows CMD
set MI_API_KEY=mi_sk_your_key_here
```

Then initialize without explicit key:

```python
from memoryintelligence import MemoryClient

mi = MemoryClient()  # Reads from MI_API_KEY
```

### Method 2: Explicit API Key

Pass the key directly:

```python
from memoryintelligence import MemoryClient

mi = MemoryClient(api_key="mi_sk_your_key_here")
```

### Method 3: Configuration File

Load from a configuration file:

```python
import os
from memoryintelligence import MemoryClient

# Load from config
from dotenv import load_dotenv
load_dotenv(".env")

mi = MemoryClient()
```

## Best Practices

### 1. Never Commit API Keys

Use `.gitignore`:

```gitignore
# Environment variables
.env
.env.local
.env.production

# API keys
api_keys.txt
secrets.json
```

### 2. Use Different Keys per Environment

```python
import os

ENV = os.environ.get("ENVIRONMENT", "development")

if ENV == "production":
    mi = MemoryClient()  # Uses MI_API_KEY from production env
else:
    mi = MemoryClient(api_key=os.environ.get("MI_API_KEY_TEST"))
```

### 3. Validate Key Format

The SDK validates key format on initialization:

```python
from memoryintelligence import MemoryClient, ConfigurationError

try:
    mi = MemoryClient(api_key="invalid_key")
except ConfigurationError as e:
    print(f"Invalid key: {e}")
```

## Key Rotation

### Check Expiration

```python
info = mi._license.validate_on_init()
print(f"License expires: {info.expires_at}")
```

### Grace Periods

Expired licenses have grace periods:

| Mode | Grace Period |
|------|--------------|
| Cloud (default) | 14 days |
| Air-gapped | 30 days |

```python
from memoryintelligence import LicenseError

try:
    mi = MemoryClient()
except LicenseError as e:
    if "expired" in str(e):
        print(f"License expired {e.days_expired} days ago")
        print(f"Renew at: {e.renew_url}")
```

## EdgeClient Authentication

EdgeClient requires an ENTERPRISE license:

```python
from memoryintelligence import EdgeClient

# Standard edge deployment
edge = EdgeClient(
    endpoint="https://mi.internal.yourcompany.com",
    api_key="mi_sk_enterprise_key",
)
```

### Air-Gapped Mode

For air-gapped deployments (no network), API key is optional:

```python
# Air-gapped - no external network calls
edge = EdgeClient(
    endpoint="https://mi.internal.yourcompany.com",
    air_gapped=True  # No API key needed
)
```

## Troubleshooting

### Invalid Key Format

```
ConfigurationError: Invalid key prefix. Expected 'mi_sk_', got 'invalid_key'
```

**Fix:** Use the correct key format starting with `mi_sk_`.

### Missing API Key

```
ConfigurationError: API key is required. Set MI_API_KEY environment variable or pass api_key
```

**Fix:** Set the environment variable or pass the key explicitly.

### Expired License

```
LicenseError: License expired 20 days ago. Renew at https://memoryintelligence.io/billing
```

**Fix:** Renew your license at the provided URL.

### Revoked License

```
LicenseError: License has been revoked. Contact support@memoryintelligence.io
```

**Fix:** Contact support for license restoration.

## Security Considerations

### Key Storage

| Environment | Recommended Storage |
|-------------|---------------------|
| Development | `.env` file (gitignored) |
| CI/CD | Repository secrets |
| Production | Secrets manager (AWS Secrets Manager, HashiCorp Vault) |

### Example: AWS Secrets Manager

```python
import boto3
from memoryintelligence import MemoryClient

# Retrieve from AWS Secrets Manager
client = boto3.client("secretsmanager")
response = client.get_secret_value(SecretId="mi-api-key")
api_key = response["SecretString"]

mi = MemoryClient(api_key=api_key)
```

### Example: HashiCorp Vault

```python
import hvac
from memoryintelligence import MemoryClient

# Retrieve from Vault
client = hvac.Client(url="https://vault.yourcompany.com")
api_key = client.secrets.kv.v2.read_secret_version(
    path="mi/api-key"
)["data"]["data"]["key"]

mi = MemoryClient(api_key=api_key)
```

## Async Authentication

Same authentication methods work for AsyncMemoryClient:

```python
from memoryintelligence import AsyncMemoryClient

# Environment variable
mi = await AsyncMemoryClient()

# Explicit key
mi = await AsyncMemoryClient(api_key="mi_sk_your_key_here")
```

## API Key Permissions

API keys are tied to your license tier:

| Tier | Capabilities |
|------|--------------|
| TRIAL | 7-day trial, limited features |
| STARTER | process, search only |
| PROFESSIONAL | process, search, match, explain |
| ENTERPRISE | All features + EdgeClient |

Attempting to use restricted features raises `LicenseError`.

## Getting Help

- **Documentation:** [docs.memoryintelligence.io](https://docs.memoryintelligence.io)
- **Support:** support@memoryintelligence.io
- **Status:** [status.memoryintelligence.io](https://status.memoryintelligence.io)
