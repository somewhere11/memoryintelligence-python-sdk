# Migration Guide: v1 to v2

Migrate from Memory Intelligence SDK v1.x to v2.0.

## Breaking Changes

### 1. UMO Namespace Pattern

**v1.x:**
```python
mi = MemoryClient()
umo = mi.process("content", user_id="user123")
results = mi.search("query", user_id="user123")
```

**v2.0:**
```python
mi = MemoryClient()
umo = mi.umo.process("content", user_ulid="01USER12345678901234567890")
results = mi.umo.search("query", user_ulid="01USER12345678901234567890")
```

| Change | v1 | v2 |
|--------|-----|-----|
| Method access | `mi.process()` | `mi.umo.process()` |
| User ID param | `user_id` | `user_ulid` |
| ID format | Any string | ULID format (26 chars) |

### 2. Mandatory Encryption

**v1.x:**
```python
# Optional encryption
mi = MemoryClient(enable_encryption=True)
```

**v2.0:**
```python
# Always encrypted
mi = MemoryClient()  # Uses MI_ENCRYPTION_KEY or ephemeral key
```

### 3. Dual Identity Pattern

**v1.x:**
```python
# Single user per client
mi = MemoryClient(user_id="user123")
umo = mi.process("content")  # Uses client user_id
```

**v2.0:**
```python
# Multi-user with for_user()
mi = MemoryClient()
user_a = mi.for_user("01USER_A12345678901234567890")
user_b = mi.for_user("01USER_B12345678901234567890")

umo_a = user_a.umo.process("content")
umo_b = user_b.umo.process("content")
```

### 4. Model Changes

**v1.x (Dataclass):**
```python
from dataclasses import asdict
umo = mi.process("content")
data = asdict(umo)
```

**v2.0 (Pydantic):**
```python
umo = mi.umo.process("content")
data = umo.model_dump()  # Pydantic method
json_str = umo.model_dump_json()
```

### 5. Error Classes

**v1.x:**
```python
from memoryintelligence import MIError, AuthError
```

**v2.0:**
```python
from memoryintelligence import (
    MIError,
    AuthenticationError,  # Renamed from AuthError
    LicenseError,         # New
    PIIViolationError,    # New
)
```

## Step-by-Step Migration

### Step 1: Install v2

```bash
pip install --upgrade memoryintelligence>=2.0.0
```

### Step 2: Update Imports

```python
# v2
from memoryintelligence import (
    MemoryClient,
    AuthenticationError,
    ValidationError,
    LicenseError,
)
```

### Step 3: Set Encryption Key

```bash
export MI_ENCRYPTION_KEY="your-base64-key"
```

### Step 4: Update Method Calls

```python
# v2
mi = MemoryClient()
user_client = mi.for_user("01USER12345678901234567890")
umo = user_client.umo.process("content")
```

## Feature Mapping

| v1 Feature | v2 Equivalent |
|------------|-----------------|
| `mi.process()` | `mi.umo.process()` |
| `mi.search()` | `mi.umo.search()` |
| `mi.match()` | `mi.umo.match()` (PROFESSIONAL+) |
| `user_id` | `user_ulid` |
| `enable_encryption=True` | Always on |

## Support

- **Migration Help:** migration@memoryintelligence.io
- **Documentation:** [docs.memoryintelligence.io/migration](https://docs.memoryintelligence.io/migration)
