# Memory Intelligence Python SDK

**Build apps that remember what matters.**

This SDK helps you turn raw content—text, images, conversations—into structured meaning that can be searched, compared, and reasoned about in Python. Think of it as giving your backend a memory that actually understands context.

We built this because we were tired of vector databases that forget context, RAG systems that hallucinate, and "AI memory" that's just glorified search. Memory Intelligence is different: it captures **meaning**, not just words.

---

## 🔐 Security First

**Python SDK is designed for backend/server-side use only.**

Your API key grants full access to your account. Never:
- ❌ Expose it in client-side code
- ❌ Commit it to version control
- ❌ Send it to frontend applications
- ❌ Log it in error messages

**✅ Always:**
- Store in environment variables (`MI_API_KEY`)
- Use `.env` files (never committed)
- Keep on server-side (FastAPI, Django, Flask)
- Use your own auth for frontend → backend access

For frontend access: Build a proxy API that uses your API key server-side, then expose restricted endpoints with your own authentication.

---

## What You Can Build

- **Personal memory apps** — backends for second-brain apps that actually remember context
- **Enterprise knowledge bases** — where tribal knowledge doesn't vanish when people leave
- **AI assistants** — with memory that spans conversations and stays grounded
- **Content recommendation engines** — that understand context, not just keywords
- **Research tools** — that connect ideas across documents and time
- **Data pipelines** — that preserve meaning through transformations

**Works everywhere:** Django, FastAPI, Flask, AWS Lambda, Google Cloud Functions, async or sync.

---

## Why This SDK Exists

Most "AI memory" tools are just fancy search. They store your data, chunk it up, embed it, and hope for the best. When you search, you get back... whatever the embedding model thinks is similar. No explanation, no provenance, no guarantee it's relevant.

**We do it differently:**

- **Meaning-first:** We extract entities, topics, and structured meaning before discarding raw text (privacy by default)
- **Explainable:** Every search result tells you *why* it matched—semantic, temporal, graph connections
- **Provenance:** Cryptographic audit trail from raw content → meaning → retrieval
- **Privacy:** Your data isn't our business model. We process meaning, not raw content.

---

## What Makes This SDK Different

### Typed from the Ground Up

Full Pydantic models for every request and response. Type hints everywhere. No guessing, no `dict` soup.

### Async + Sync

Same API, two clients:
- `MemoryClient` — synchronous (uses `httpx`)
- `AsyncMemoryClient` — async/await (great for FastAPI, async workflows)

### Built for Real Apps

- **Auto-retry with backoff** — because networks fail
- **Request timeout control** — don't hang forever
- **Connection pooling** — reuse connections efficiently
- **Structured logging** — debug-friendly output

### Privacy by Design

- **ULID identifiers** — no external IDs, emails, or UUIDs stored
- **Meaning-first** — raw content discarded after processing (configurable)
- **GDPR-ready** — one-call data deletion with audit proof

### Developer-Friendly

- Type hints everywhere
- Comprehensive error messages
- Context manager support
- Extensive documentation

---

## Getting Started

### Installation

```bash
pip install memoryintelligence
```

### Environment Setup

Create a `.env` file (and **never commit it**):

```bash
MI_API_KEY=mi_sk_test_your_secret_key_here
```

Add it to `.gitignore`:

```bash
# .gitignore
.env
.env.local
```

### Initialize the Client

**Synchronous:**

```python
from memoryintelligence import MemoryClient

# Initialize with API key
mi = MemoryClient(api_key="mi_sk_test_...")

# Or use environment variable
mi = MemoryClient()  # reads MI_API_KEY from env
```

**Asynchronous:**

```python
from memoryintelligence import AsyncMemoryClient

mi = AsyncMemoryClient(api_key="mi_sk_test_...")
```

---

## Core Operations

### Process Content → Meaning

Turn raw content into a Unified Memory Object (UMO):

```python
from memoryintelligence import MemoryClient, RetentionPolicy, PIIHandling

mi = MemoryClient(api_key="mi_sk_test_...")

umo = mi.umo.process(
    "Meeting notes about Q2 strategy and hiring plans",
    user_ulid="01ABC...",
    retention_policy=RetentionPolicy.MEANING_ONLY,  # raw content discarded
    pii_handling=PIIHandling.EXTRACT_AND_REDACT,
)

print(umo.entities)  # [Entity(text="Q2", type="DATE"), ...]
print(umo.topics)    # ["strategy", "hiring"]
print(umo.summary)   # "Discussion of Q2 strategy and hiring..."
```

**Async version:**

```python
from memoryintelligence import AsyncMemoryClient

mi = AsyncMemoryClient(api_key="mi_sk_test_...")

umo = await mi.umo.process(
    "Meeting notes about Q2 strategy and hiring plans",
    user_ulid="01ABC...",
)
```

### Search for Meaning

Find memories by what they **mean**, not just keywords:

```python
results = mi.umo.search(
    "What were our hiring plans?",
    user_ulid="01ABC...",
    explain=True,  # tells you WHY each result matched
)

for result in results:
    print(result.umo.summary)
    print(result.explanation.why_summary)  # plain-language explanation
```

### Match Memories

Compare two memories for relevance (great for recommendations):

```python
match = mi.umo.match(
    "01UMO1...",  # UMO ID 1
    "01UMO2...",  # UMO ID 2
    explain=True,
)

print(match.score)  # 0.0 to 1.0
print(match.explanation.why_summary)  # "Both discuss Q2 hiring..."
```

### Explain a Memory

Get the full breakdown of what makes a memory meaningful:

```python
explanation = mi.umo.explain("01UMO...")

print(explanation.entities)   # all extracted entities
print(explanation.topics)     # key topics
print(explanation.relations)  # entity relationships
print(explanation.embedding_metadata)  # model version, dimensions
```

### Delete User Data (GDPR)

One-call data deletion with audit proof:

```python
result = mi.umo.delete(user_ulid="01ABC...")

print(result.deleted_count)  # number of UMOs deleted
print(result.audit_hash)     # cryptographic proof of deletion
```

---

## Advanced Features

### Batch Processing

Process multiple items efficiently:

```python
contents = [
    "Meeting notes from Monday",
    "Client feedback email",
    "Product brainstorm session",
]

for content in contents:
    umo = mi.umo.process(content, user_ulid="01ABC...")
    print(f"Processed: {umo.umo_id}")
```

**Async batch processing:**

```python
import asyncio
from memoryintelligence import AsyncMemoryClient

mi = AsyncMemoryClient(api_key="mi_sk_test_...")

async def process_batch(contents):
    tasks = [
        mi.umo.process(content, user_ulid="01ABC...")
        for content in contents
    ]
    return await asyncio.gather(*tasks)

contents = [...]
umos = await process_batch(contents)
```

### Context Manager Support

Automatically handle connection lifecycle:

```python
with MemoryClient(api_key="mi_sk_test_...") as mi:
    umo = mi.umo.process("Meeting notes", user_ulid="01ABC...")
    results = mi.umo.search("hiring", user_ulid="01ABC...")
# Connection closed automatically
```

**Async context manager:**

```python
async with AsyncMemoryClient(api_key="mi_sk_test_...") as mi:
    umo = await mi.umo.process("Meeting notes", user_ulid="01ABC...")
    results = await mi.umo.search("hiring", user_ulid="01ABC...")
```

### Custom Timeouts

Control request timeouts:

```python
mi = MemoryClient(
    api_key="mi_sk_test_...",
    timeout=30.0,  # 30 seconds
)

# Or per-request:
umo = mi.umo.process(
    content,
    user_ulid="01ABC...",
    timeout=60.0,  # 60 seconds for this request
)
```

### Cryptographic Verification

Verify content provenance:

```python
from memoryintelligence.crypto import compute_hash, verify_hash

# Compute hash before processing
original_hash = compute_hash("Meeting notes")

# Process content
umo = mi.umo.process("Meeting notes", user_ulid="01ABC...")

# Verify hash matches
assert verify_hash("Meeting notes", umo.provenance_hash)
```

---

## Working with FastAPI

Perfect for FastAPI backends:

```python
from fastapi import FastAPI, HTTPException, Depends
from memoryintelligence import AsyncMemoryClient
from pydantic import BaseModel

app = FastAPI()

# Dependency injection
async def get_mi_client():
    return AsyncMemoryClient(api_key="mi_sk_test_...")

class ProcessRequest(BaseModel):
    content: str
    user_ulid: str

@app.post("/api/process")
async def process_memory(
    req: ProcessRequest,
    mi: AsyncMemoryClient = Depends(get_mi_client)
):
    try:
        umo = await mi.umo.process(req.content, user_ulid=req.user_ulid)
        return {"umo_id": umo.umo_id, "summary": umo.summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search")
async def search_memories(
    query: str,
    user_ulid: str,
    mi: AsyncMemoryClient = Depends(get_mi_client)
):
    results = await mi.umo.search(query, user_ulid=user_ulid, explain=True)
    return {
        "results": [
            {
                "summary": r.umo.summary,
                "score": r.score,
                "why": r.explanation.why_summary,
            }
            for r in results
        ]
    }
```

---

## Response Types

All responses are Pydantic models with full type hints:

```python
from memoryintelligence.models import UMO, SearchResult, MatchResult, Entity

# Unified Memory Object
class UMO:
    umo_id: str
    entities: list[Entity]
    topics: list[str]
    summary: str
    embedding: list[float]
    timestamp: str
    ingested_at: str
    provenance_hash: str
    # ...and more

# Search result
class SearchResult:
    umo: UMO
    score: float
    explanation: Explanation

# Match result
class MatchResult:
    score: float
    explanation: Explanation
    shared_entities: list[str]
    shared_topics: list[str]
```

---

## Error Handling

All errors are structured and descriptive:

```python
from memoryintelligence.exceptions import (
    AuthenticationError,
    ValidationError,
    GovernanceError,
    RateLimitError,
    ServerError,
)

try:
    umo = mi.umo.process(content, user_ulid="01ABC...")
except AuthenticationError:
    print("Invalid API key")
except ValidationError as e:
    print(f"Invalid input: {e.message}")
except RateLimitError as e:
    print(f"Rate limit hit, retry after: {e.retry_after}")
except GovernanceError as e:
    print(f"Governance policy violation: {e.message}")
except ServerError as e:
    print(f"Server error: {e.message}")
```

---

## Logging

Built-in structured logging:

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

mi = MemoryClient(api_key="mi_sk_test_...")

# Will log all requests/responses
umo = mi.umo.process("Meeting notes", user_ulid="01ABC...")
```

---

## Testing

Use test API keys for development:

```python
# Test key (starts with mi_sk_test_)
mi = MemoryClient(api_key="mi_sk_test_...")

# Production key (starts with mi_sk_live_)
mi = MemoryClient(api_key="mi_sk_live_...")
```

Mock responses for unit tests:

```python
from unittest.mock import Mock
from memoryintelligence import MemoryClient
from memoryintelligence.models import UMO

def test_process():
    mi = MemoryClient(api_key="mi_sk_test_...")
    mi.umo.process = Mock(return_value=UMO(
        umo_id="01ABC...",
        summary="Test summary",
        # ...
    ))
    
    umo = mi.umo.process("Test content", user_ulid="01USER...")
    assert umo.umo_id == "01ABC..."
```

---

## Examples

Check out working examples in the [examples/](./examples/) directory:

- **FastAPI integration** — Full async API backend
- **Django integration** — Sync client with Django views
- **Batch processing** — Process thousands of documents
- **CLI tool** — Command-line memory processor

---

## Documentation

- [API Reference](https://docs.memoryintelligence.io/reference/python-sdk) — Full API docs
- [Quickstart Guide](./docs/quickstart.md) — Get started in 5 minutes
- [Enterprise Guide](./docs/enterprise.md) — Production deployment patterns
- [Encryption Guide](./docs/encryption.md) — End-to-end encryption setup

---

## Requirements

- Python 3.8+
- `httpx` (HTTP client)
- `pydantic` (data validation)

---

## Support

- **Documentation:** [docs.memoryintelligence.io](https://docs.memoryintelligence.io)
- **GitHub Issues:** [github.com/somewhere11/memoryintelligence-python-sdk/issues](https://github.com/somewhere11/memoryintelligence-python-sdk/issues)
- **Email:** [sdk@memoryintelligence.io](mailto:sdk@memoryintelligence.io)

---

## License

MIT — see [LICENSE](./LICENSE) for details.

---

Built with care by the somewhere team. We're building tools that make memory meaningful, private, and yours.
