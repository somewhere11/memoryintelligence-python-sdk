# Memory Intelligence Python SDK

The official Python SDK for Memory Intelligence—verifiable meaning infrastructure for AI applications.

## Installation

```bash
pip install memoryintelligence
```

## Quick Start

```python
from memoryintelligence import MemoryClient

# Initialize
mi = MemoryClient(api_key="mi_sk_...")

# Process content → meaning (raw content discarded by default)
umo = mi.process(
    "Sarah mentioned the Q4 budget needs review by Friday",
    user_ulid="01ABC..."
)

print(umo.entities)      # [Entity(text="Sarah", type="PERSON"), ...]
print(umo.topics)        # [Topic(name="budget"), Topic(name="Q4")]
print(umo.summary)       # "Budget review deadline discussed"
print(umo.provenance)    # Cryptographic proof of processing

# Search with explanation
results = mi.search(
    "What did Sarah say about budget?",
    user_ulid="01ABC...",
    explain=True
)

for r in results.results:
    print(f"Score: {r.score}")
    print(f"Why: {r.explain.human.summary}")
```

## Core Operations

### 1. Process: Content → Meaning

```python
umo = mi.process(
    content="Meeting notes from today...",
    user_ulid="01ABC...",
    retention_policy=RetentionPolicy.MEANING_ONLY,  # Default: discard raw
    pii_handling=PIIHandling.EXTRACT_AND_REDACT,    # Default: redact PII
    scope=Scope.USER                                 # Default: user scope
)
```

### 2. Search: Find Relevant Meaning

```python
results = mi.search(
    query="What do I know about project X?",
    user_ulid="01ABC...",
    explain=True,
    limit=10
)

# With scope isolation
results = mi.search(
    query="Acme's current concerns",
    user_ulid="01ABC...",
    scope=Scope.CLIENT,
    scope_id=acme_ulid
)
```

### 3. Match: Compare for Relevance

```python
# Is this content relevant to this user?
match = mi.match(
    source_ulid=user_ulid,
    candidate_ulid=post_ulid,
    explain=True
)

if match.match:
    print(f"Relevant! {match.explain.human.summary}")
```

### 4. Delete: GDPR Compliance

```python
# Delete all user data
result = mi.delete(user_ulid="01ABC...")
print(f"Deleted {result.deleted_count} memories")
print(f"Audit proof: {result.audit_proof}")
```

### 5. Verify: Provenance Check

```python
# Verify authorship before using content
result = mi.verify_provenance(content_hash)

if result.valid:
    print(f"Original author: {result.original_author_ulid}")
    print(f"First published: {result.first_published}")
```

## Edge Deployment (HIPAA/Regulated)

For regulated industries where data cannot leave your infrastructure:

```python
from memoryintelligence import EdgeClient

mi = EdgeClient(
    endpoint="https://mi.internal.yourcompany.com",
    api_key="mi_sk_...",
    hipaa_mode=True
)

# Process locally—data never leaves your infrastructure
umo = mi.process(
    clinical_note,
    patient_ulid="01ABC...",
    pii_handling=PIIHandling.HASH
)

# Verify PHI handling
proof = mi.verify_phi_handling(umo.umo_id)
print(proof)  # {"raw_phi_stored": False, "raw_phi_transmitted": False, ...}

# Aggregate without exposing individual records
insights = mi.aggregate(
    "Patients with symptom X who responded to treatment Y",
    scope=Scope.ORGANIZATION,
    minimum_cohort_size=50  # K-anonymity
)
```

## Scope Isolation

Cryptographic boundaries between data scopes:

```python
from memoryintelligence import Scope

# Client isolation (consulting, legal)
mi.process(content, scope=Scope.CLIENT, scope_id=client_ulid)
mi.search(query, scope=Scope.CLIENT, scope_id=client_ulid)

# Project isolation
mi.process(content, scope=Scope.PROJECT, scope_id=project_ulid)

# Team isolation
mi.process(content, scope=Scope.TEAM, scope_id=team_ulid)
```

## Error Handling

```python
from memoryintelligence import (
    MIError,
    AuthenticationError,
    RateLimitError,
    ScopeViolationError,
    PIIViolationError,
)

try:
    umo = mi.process(content, user_ulid=user)
except AuthenticationError:
    print("Invalid API key")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after}s")
except ScopeViolationError:
    print("Cross-scope access denied")
except PIIViolationError as e:
    print(f"PII detected and rejected: {e.detected_types}")
except MIError as e:
    print(f"API error: {e}")
```

## Response Types

All responses are typed dataclasses:

```python
MeaningObject      # Core output with entities, topics, embedding
SearchResponse     # Search results with explanations
MatchResult        # Match score with explanation
DeleteResult       # Deletion confirmation with audit proof
VerifyResult       # Provenance verification result
Explanation        # Human + audit explanation
```

## Configuration

Environment variables:

```bash
MI_API_KEY=mi_sk_...        # API key (required)
MI_API_URL=https://...      # Custom endpoint (optional)
MI_TIMEOUT=30               # Request timeout (optional)
```

## Pricing

| Tier | Price | Volume |
|------|-------|--------|
| Free | $0 | 1K UMOs/month |
| Starter | $29/month | 25K UMOs/month |
| Pro | $149/month | 250K UMOs/month |
| Enterprise | Custom | Unlimited + Edge |

## Support

- Documentation: https://docs.memoryintelligence.io
- Issues: https://github.com/memoryintelligence/sdk-python/issues
- Email: support@memoryintelligence.io

## License

MIT License - see LICENSE file
