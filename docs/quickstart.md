# Quickstart Guide

Get started with the Memory Intelligence Python SDK in under 5 minutes.

## Installation

```bash
pip install memoryintelligence
```

## Prerequisites

1. **Sign up** at [memoryintelligence.io](https://memoryintelligence.io) to get your API key
2. **Set your API key** as an environment variable:
   ```bash
   export MI_API_KEY="mi_sk_your_key_here"
   ```

## Basic Usage

### Process Content

Extract meaning from text:

```python
from memoryintelligence import MemoryClient

# Initialize client
mi = MemoryClient()

# Process content
umo = mi.umo.process(
    "The budget meeting with Sarah was approved for Q4 planning.",
    user_ulid="01USER12345678901234567890"
)

print(f"UMO ID: {umo.umo_id}")
print(f"Summary: {umo.summary}")
print(f"Entities: {[e.text for e in umo.entities]}")
```

Output:
```
UMO ID: 01ABC12345678901234567890
Summary: Budget approved for Q4
Entities: ['Sarah', 'Q4']
```

### Search Memories

Find relevant UMOs with semantic search:

```python
results = mi.umo.search(
    "What did we decide about the budget?",
    user_ulid="01USER12345678901234567890",
    limit=5
)

for result in results.results:
    print(f"Score: {result.score:.2f} - {result.umo.summary}")
```

### Scoped Client

Process for multiple users with `for_user()`:

```python
# Create base client
mi = MemoryClient()

# Create user-scoped clients
user_a = mi.for_user("01USER_A12345678901234567890")
user_b = mi.for_user("01USER_B12345678901234567890")

# Process without repeating user_ulid
umo_a = user_a.umo.process("Sarah's project update...")
umo_b = user_b.umo.process("Budget discussion...")
```

## Understanding UMOs

A **UMO** (Unit of Meaning Object) contains:

| Field | Description |
|-------|-------------|
| `umo_id` | Unique ULID identifier |
| `entities` | Named entities (people, orgs, locations) |
| `topics` | Semantic topics with confidence scores |
| `svo_triples` | Subject-Verb-Object relationships |
| `summary` | Auto-generated summary |
| `provenance` | Audit trail with semantic hash |

## Next Steps

- **[Authentication](authentication.md)** - API keys and environment setup
- **[Encryption](encryption.md)** - Client-side encryption details
- **[Licensing](licensing.md)** - License tiers and feature access
- **[API Reference](api_reference.md)** - Complete API documentation

## Quick Examples

### With Explainability

```python
# Get explanation for why content matched
result = mi.umo.search(
    "budget decisions",
    user_ulid="01USER12345678901234567890",
    explain=True
)

print(result.results[0].explain.human.summary)
```

### Delete User Data

```python
# Delete all UMOs for a user
result = mi.umo.delete(user_ulid="01USER12345678901234567890")
print(f"Deleted {result.deleted_count} UMOs")
```

### Match UMOs

```python
# Compare two UMOs for semantic similarity
match = mi.umo.match(
    "01UMO_A12345678901234567890",
    "01UMO_B12345678901234567890"
)

print(f"Similarity: {match.score:.2f}")
print(f"Is match: {match.match}")
```

## Troubleshooting

### Import Error

```bash
ModuleNotFoundError: No module named 'memoryintelligence'
```

**Fix:** Install the SDK:
```bash
pip install memoryintelligence
```

### Authentication Error

```
memoryintelligence.AuthenticationError: Invalid API key
```

**Fix:** Set your API key:
```bash
export MI_API_KEY="mi_sk_your_key_here"
```

Or pass it explicitly:
```python
mi = MemoryClient(api_key="mi_sk_your_key_here")
```

### License Error

```
memoryintelligence.LicenseError: umo.match() requires PROFESSIONAL or ENTERPRISE
```

**Fix:** Upgrade your license tier at [memoryintelligence.io/billing](https://memoryintelligence.io/billing)

## Support

- **Documentation:** [docs.memoryintelligence.io](https://docs.memoryintelligence.io)
- **Issues:** [github.com/memoryintelligence/sdk-python/issues](https://github.com/memoryintelligence/sdk-python/issues)
- **Email:** sdk@memoryintelligence.io
