# Memory Intelligence SDK

The official Python SDK for Memory Intelligence - Verifiable meaning infrastructure for AI.

[![PyPI](https://img.shields.io/pypi/v/memoryintelligence.svg)](https://pypi.org/project/memoryintelligence/)
[![License](https://img.shields.io/pypi/l/memoryintelligence.svg)](https://pypi.org/project/memoryintelligence/)

## Quick Start

```python
from memoryintelligence import MemoryClient

# Initialize client
mi = MemoryClient(api_key="mi_sk_...")

# Process content → meaning
umo = mi.umo.process("Meeting notes from today", user_ulid="01ABC...")

# Search meaning
results = mi.umo.search("What did we discuss?", user_ulid="01ABC...", explain=True)

# Match for recommendations
match = mi.umo.match("01ABC...", "01XYZ...", explain=True)

# Get explanation
explanation = mi.umo.explain("01ABC...")

# Delete for GDPR
result = mi.umo.delete(user_ulid="01ABC...")
```

## Key Features

- **Meaning-First Architecture**: Raw content discarded after processing
- **Five Core Operations**: Process, Search, Match, Explain, Delete
- **Provenance Tracking**: Cryptographic verification of content lineage
- **GDPR Compliance**: One-call data deletion with audit proof
- **Built-in Telemetry**: Debug logs for content processing
- **Simplified API**: Only 12 essential exports

## Installation

```bash
pip install memoryintelligence
```

## Usage Guide

### Initialize the Client

```python
from memoryintelligence import MemoryClient

# For production (API key required)
mi = MemoryClient(api_key="mi_sk_prod_...")

# For development
mi = MemoryClient(api_key="mi_sk_dev_...")

# For specific user (multi-tenant)
user_mi = mi.for_user("01USER12345678901234567890")
```

### Process Content

Convert raw content to meaning (discards raw content by default):

```python
from memoryintelligence import RetentionPolicy, PIIHandling, ProvenanceMode

umo = mi.umo.process(
    "Budget approved for Q3 initiatives",
    user_ulid="01ABC...",
    retention_policy=RetentionPolicy.MEANING_ONLY,
    pii_handling=PIIHandling.EXTRACT_AND_REDACT,
    provenance_mode=ProvenanceMode.STANDARD
)

print(umo.entities)      # [Entity(text="Q3", type="DATE"), ...]
print(umo.topics)        # ["budget", "initiatives"]
print(umo.svo_triples)   # [SVOTriple(subject="budget", verb="approved", object="initiatives")]
print(umo.umo_id)        # "01KGE95Q4P9H89H63T26FNKKBR"
```

### Search for Meaning

Find relevant memories with explanation:

```python
from datetime import datetime, timezone

results = mi.umo.search(
    "Q3 budget decisions",
    user_ulid="01ABC...",
    explain=True,
    limit=5,
    topics=["budget", "finance"],
    date_from=datetime(2024, 1, 1, tzinfo=timezone.utc)
)

for result in results.results:
    print(f"Score: {result.score:.2f}")
    print(f"Summary: {result.umo.summary}")
    if result.explain:
        print(f"Why: {result.explain.human.summary}")
```

### Match for Recommendations

Compare two memories for relevance:

```python
match = mi.umo.match(
    source_ulid="01ABC...",
    candidate_ulid="01XYZ...",
    explain=True
)

print(f"Match score: {match.score}")
print(f"Is match: {match.match}")
if match.explain:
    print(f"Reason: {match.explain.human.summary}")
```

### Get Explanations

Understand why content is relevant:

```python
from memoryintelligence import ExplainLevel

explanation = mi.umo.explain(
    "01ABC...",
    level=ExplainLevel.FULL
)

print(explanation.human.summary)
print(explanation.human.key_reasons)
print(explanation.audit.semantic_score)
```

### Delete Data

GDPR-compliant data removal:

```python
from memoryintelligence import Scope

result = mi.umo.delete(
    user_ulid="01ABC...",
    scope=Scope.USER
)

print(f"Deleted {result.deleted_count} memories")
```

## Async Support

For async frameworks:

```python
from memoryintelligence import AsyncMemoryClient

mi = AsyncMemoryClient(api_key="mi_sk_...")

# Process
umo = await mi.umo.process("Content", user_ulid="01ABC...")

# Search with iteration
async for result in mi.umo.search_iter("query", user_ulid="01ABC..."):
    print(result.umo.summary)

# Batch processing
contents = ["Note 1", "Note 2", "Note 3"]
results = await mi.umo.process_batch(contents, user_ulid="01ABC...")
```

## Edge Deployment (HIPAA/Air-gapped)

For regulated industries:

```python
from memoryintelligence import EdgeClient

# HIPAA-compliant edge deployment
edge = EdgeClient(
    endpoint="https://mi.internal.yourcompany.com",
    api_key="mi_sk_...",
    hipaa_mode=True
)

# Process locally (data never leaves)
umo = edge.umo.process(clinical_note, user_ulid="01PATIENT...")

# Air-gapped (no external calls)
air_gapped = EdgeClient(
    endpoint="https://mi.internal.com",
    air_gapped=True  # No API key needed
)
```

## Error Handling

```python
from memoryintelligence import (
    MemoryClient,
    LicenseError,
    RateLimitError,
    ValidationError,
    AuthenticationError
)

try:
    mi = MemoryClient(api_key="mi_sk_...")
    umo = mi.umo.process("Content", user_ulid="01ABC...")
except LicenseError as e:
    print(f"License expired {e.days_expired} days ago")
    print(f"Renew at: {e.renew_url}")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after} seconds")
except ValidationError as e:
    print(f"Validation failed: {e.message}")
except AuthenticationError:
    print("Invalid API key")
```

## Webhook Verification

```python
from memoryintelligence import verify_webhook_signature

# Verify webhook from Memory Intelligence
is_valid = verify_webhook_signature(
    payload=request_body,
    signature=headers["X-MI-Signature"],
    secret="whsec_..."
)
```

## Monitoring & Telemetry

The SDK provides built-in telemetry for operational visibility:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Key Log Events:
- `DEBUG`: Content processing metrics (size, time)
- `INFO`: Operation completion with results
- `WARNING`: PII detection events
- `ERROR`: API and integration errors

## Configuration

Environment variables:

```bash
# Required for persistent encryption
export MI_ENCRYPTION_KEY="$(openssl rand -base64 32)"

# API configuration
export MI_API_KEY="mi_sk_live_..."
export MI_BASE_URL="https://api.memoryintelligence.io"
```

## Documentation

Full documentation is available at:
- [API Reference](https://docs.memoryintelligence.io)
- [Getting Started Guide](https://memoryintelligence.io/docs/getting-started)

## Support

For SDK issues, please contact:
- support@memoryintelligence.io
- GitHub Issues: [Create New Issue](https://github.com/memoryintelligence/sdk-python/issues/new)

## License

This SDK is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
