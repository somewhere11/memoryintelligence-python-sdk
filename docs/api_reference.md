# API Reference

Complete API reference for the Memory Intelligence Python SDK.

## MemoryClient

Main synchronous client for Memory Intelligence API.

```python
from memoryintelligence import MemoryClient

mi = MemoryClient(
    api_key=None,           # API key or reads from MI_API_KEY
    base_url=None,        # Custom API endpoint
    user_ulid=None,       # Default user ULID
    encryption_key=None,  # Custom encryption key
    max_retries=3,        # Retry attempts for failed requests
)
```

### Methods

#### `for_user(user_ulid)`

Create a scoped client for a specific user.

```python
user_client = mi.for_user("01USER12345678901234567890")
umo = user_client.umo.process("Content")  # Uses scoped user_ulid
```

#### `close()`

Close HTTP connections.

```python
mi.close()
```

## UMONamespace

Accessed via `mi.umo`. Provides UMO operations.

### `process(content, user_ulid, **kwargs)`

Process content into a MeaningObject.

```python
umo = mi.umo.process(
    content="The budget meeting with Sarah...",
    user_ulid="01USER12345678901234567890",
    pii_handling=PIIHandling.EXTRACT_AND_REDACT,
    provenance_mode=ProvenanceMode.STANDARD,
    scope=Scope.USER,
    retention_policy=RetentionPolicy.MEANING_ONLY,
)

# Returns: MeaningObject
print(umo.umo_id)      # Unique ULID
print(umo.summary)     # Auto-generated summary
print(umo.entities)    # Named entities
print(umo.topics)      # Semantic topics
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `content` | str | Yes | - | Text to process |
| `user_ulid` | str | Yes* | - | User identifier |
| `pii_handling` | PIIHandling | No | `EXTRACT_AND_REDACT` | How to handle PII |
| `provenance_mode` | ProvenanceMode | No | `STANDARD` | Provenance detail level |
| `scope` | Scope | No | `USER` | Isolation scope |
| `scope_id` | str | No | None | Scope identifier |
| `retention_policy` | RetentionPolicy | No | `MEANING_ONLY` | What to retain |

*Required if not set on client or via `for_user()`

**Returns:** `MeaningObject`

### `search(query, user_ulid, **kwargs)`

Search UMOs with semantic query.

```python
results = mi.umo.search(
    query="budget decisions",
    user_ulid="01USER12345678901234567890",
    limit=10,
    topics=["budget"],
    date_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
    explain=False,
)

print(f"Found {results.total_count} results")
for result in results.results:
    print(f"Score: {result.score:.2f}")
    print(f"Summary: {result.umo.summary}")
```

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `query` | str | Yes | - | Natural language query |
| `user_ulid` | str | Yes | - | User identifier |
| `limit` | int | No | 10 | Max results |
| `topics` | list[str] | No | None | Filter by topics |
| `date_from` | datetime | No | None | Start date filter |
| `date_to` | datetime | No | None | End date filter |
| `explain` | bool | No | False | Include explanation |

**Returns:** `SearchResponse`

### `match(source_ulid, candidate_ulid, **kwargs)`

Compare two UMOs for semantic similarity.

```python
result = mi.umo.match(
    source_ulid="01SOURCE12345678901234567890",
    candidate_ulid="01CANDIDATE12345678901234567890",
    explain=True,
)

print(f"Similarity: {result.score:.2f}")
print(f"Is match: {result.match}")

if result.explain:
    print(result.explain.human.summary)
```

**License Required:** PROFESSIONAL or ENTERPRISE

**Returns:** `MatchResult`

### `explain(umo_id, **kwargs)`

Get explanation for a UMO.

```python
explanation = mi.umo.explain("01ABC12345678901234567890")

print(explanation.human.summary)
print(explanation.human.key_reasons)
print(explanation.audit.semantic_score)
print(explanation.audit.reproducible)
```

**License Required:** PROFESSIONAL or ENTERPRISE

**Returns:** `Explanation`

### `delete(**kwargs)`

Delete UMOs.

```python
result = mi.umo.delete(
    user_ulid="01USER12345678901234567890",
    scope=Scope.USER,
)

print(f"Deleted {result.deleted_count} UMOs")
```

**Returns:** `DeleteResult`

## EdgeClient

On-premises deployment client for regulated industries.

```python
from memoryintelligence import EdgeClient

edge = EdgeClient(
    endpoint="https://mi.internal.com",
    api_key="mi_sk_enterprise_key",
    hipaa_mode=False,
    air_gapped=False,
    metering_enabled=True,
)
```

**License Required:** ENTERPRISE

### Methods

#### `aggregate(query, **kwargs)`

Federated aggregation with privacy.

```python
result = edge.aggregate(
    query="average patient age",
    scope=Scope.ORGANIZATION,
    minimum_cohort_size=50,
    return_format="statistics_only",
)
```

#### `verify_phi_handling(umo_id)`

Verify PHI handling for a UMO.

```python
result = edge.verify_phi_handling("01ABC12345678901234567890")
print(result["phi_detected"])
print(result["handling_applied"])
```

#### `export_audit_log(start_date, end_date, **kwargs)`

Export audit logs.

```python
logs = edge.export_audit_log(
    start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    end_date=datetime(2024, 1, 31, tzinfo=timezone.utc),
    format="json",
)
```

## AsyncMemoryClient

Asynchronous client for non-blocking operations.

```python
from memoryintelligence import AsyncMemoryClient

mi = await AsyncMemoryClient()

# All methods are async
umo = await mi.umo.process("Content", user_ulid="01USER123")
results = await mi.umo.search("query", user_ulid="01USER123")

await mi.close()
```

## Models

### MeaningObject

```python
class MeaningObject:
    umo_id: str                    # Unique ULID
    user_ulid: str                 # Owner user ULID
    entities: list[Entity]         # Named entities
    topics: list[Topic]            # Semantic topics
    svo_triples: list[SVOTriple]   # Subject-Verb-Object
    key_phrases: list[str]         # Key phrases
    summary: str                   # Auto-generated summary
    sentiment_label: str           # positive/negative/neutral
    sentiment_score: float         # -1.0 to 1.0
    provenance: Provenance         # Audit trail
    pii: PIIInfo                   # PII detection info
    scope: str                     # Isolation scope
    timestamp: datetime            # Creation time
    ingested_at: datetime          # Ingestion time
```

### Entity

```python
class Entity:
    text: str          # Entity text
    type: str          # Entity type (PERSON, ORG, etc.)
    confidence: float  # 0.0 to 1.0
    start: int         # Start position
    end: int           # End position
```

### SearchResponse

```python
class SearchResponse:
    results: list[SearchResult]
    total_count: int
    query: str
```

### SearchResult

```python
class SearchResult:
    umo: MeaningObject
    score: float           # Similarity score 0.0 to 1.0
    explain: Explanation | None
```

### MatchResult

```python
class MatchResult:
    score: float           # Similarity score
    match: bool            # Whether they match
    source_ulid: str
    candidate_ulid: str
    explain: Explanation | None
```

### Explanation

```python
class Explanation:
    human: HumanExplanation
    audit: AuditExplanation

class HumanExplanation:
    summary: str
    key_reasons: list[str]

class AuditExplanation:
    semantic_score: float
    feature_weights: dict
    model_version: str
    reproducible: bool
```

## Enums

### Scope

```python
from memoryintelligence import Scope

Scope.USER         # User-isolated
Scope.CLIENT       # Client-isolated
Scope.ORGANIZATION # Org-wide
```

### PIIHandling

```python
from memoryintelligence import PIIHandling

PIIHandling.EXTRACT_AND_REDACT  # Extract PII, redact text
PIIHandling.HASH                # One-way hash
PIIHandling.REJECT              # Reject if PII detected
```

### RetentionPolicy

```python
from memoryintelligence import RetentionPolicy

RetentionPolicy.FULL           # Keep everything
RetentionPolicy.MEANING_ONLY     # Keep only meaning (default)
RetentionPolicy.NO_STORAGE       # Process only, don't store
```

### ProvenanceMode

```python
from memoryintelligence import ProvenanceMode

ProvenanceMode.MINIMAL     # Basic hash
ProvenanceMode.STANDARD    # Full provenance (default)
ProvenanceMode.AUDIT       # Complete audit trail
```

## Exceptions

All exceptions inherit from `MIError`.

### Exception Hierarchy

```
MIError
├── ConfigurationError
├── AuthenticationError
├── PermissionError
├── PaymentRequiredError
├── NotFoundError
├── ConflictError
├── ValidationError
├── RateLimitError
├── PIIViolationError
├── LicenseError
├── EncryptionError
├── TimeoutError
├── ConnectionError
└── ServerError
```

### Common Exceptions

```python
from memoryintelligence import (
    AuthenticationError,
    LicenseError,
    RateLimitError,
    ValidationError,
)

try:
    umo = mi.umo.process("content", user_ulid="01USER123")
except AuthenticationError:
    print("Invalid API key")
except LicenseError as e:
    print(f"License issue: {e}")
    print(f"Renew at: {e.renew_url}")
except RateLimitError as e:
    print(f"Rate limited. Retry after {e.retry_after}s")
except ValidationError as e:
    print(f"Invalid {e.field}: {e}")
```

## Constants

```python
from memoryintelligence._version import __version__

print(__version__)  # "2.0.0"
```
