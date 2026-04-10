# Memory Intelligence API

**Memory without meaning is just storage.**

This API turns raw content—text, conversations, images—into structured meaning. Searchable, explainable, provenance-tracked. No black box. No hallucinations.

**For Python backends:** FastAPI, Django, Flask, Lambda, Cloud Functions.

---

## Installation

```bash
pip install memoryintelligence
```

**Get your API key:** [memoryintelligence.io/beta](https://memoryintelligence.io/beta)

---

## Quick Start

```python
from memoryintelligence import MemoryClient
import os

mi = MemoryClient(api_key=os.getenv('MI_API_KEY'))

# Turn content into structured meaning
memory = mi.umo.process(
    content="Discussed pricing with ACME. They prefer quarterly billing.",
    user_id="user_01ABC",
    context={"source": "sales_call", "date": "2024-03-15"},
)

# Search with plain language
results = mi.umo.search(
    "What did ACME say about billing?",
    user_ulid="01GTXYZ123..."
)

# Explain why results matched
explanation = mi.umo.explain(results[0].umo_id)
print(explanation.why)  # "Matched: 'ACME', 'billing', 'quarterly'"
```

---

## What It Does

- **Processes** → Extracts entities, topics, relationships, sentiment
- **Searches** → Returns ranked results with explainability
- **Matches** → Compares memories for relevance/similarity
- **Explains** → Shows *why* results matched (semantic, temporal, graph)
- **Deletes** → GDPR-compliant data removal with audit trail

**No vector database setup. No chunking strategies. No embedding models to manage.**

---

## Security: API Keys Are Server-Only

Your API key grants full account access. Keep it server-side.

**✅ Backend (environment variable):**
```python
mi = MemoryClient(api_key=os.getenv('MI_API_KEY'))
```

**❌ Never hardcoded:**
```python
# Don't - visible in logs/code
mi = MemoryClient(api_key='mi_sk_live_...')
```

**For web apps:** Use your API key in the backend, build your own endpoints with your auth, let your frontend call those.

---

## What Makes This Different

| Others | Memory Intelligence |
|--------|---------------------|
| Store text, embed, hope | Extract meaning first |
| "Here are similar chunks" | "Here's why this matched" |
| No audit trail | Cryptographic provenance |
| Your data = their model training | Your data stays yours |

**Setting the standard for memory.**

---

## Core Operations

```python
# Process content → structured meaning
mi.umo.process(content, user_id, context)

# Search with explainability
results = mi.umo.search(query, user_ulid=ulid)

# Compare memories
match = mi.umo.match(umo_id_1, umo_id_2)

# Get explainability
why = mi.umo.explain(umo_id)

# Delete everything (GDPR)
mi.umo.delete_user_data(user_id)
```

---

## Async Support

```python
from memoryintelligence import AsyncMemoryClient

mi = AsyncMemoryClient(api_key=os.getenv('MI_API_KEY'))

async def search_memories(query: str):
    results = await mi.umo.search(query, user_ulid="01ABC...")
    return results
```

---

## Error Handling

```python
from memoryintelligence.errors import MemoryError, AuthError, ValidationError

try:
    results = mi.umo.search(query)
except AuthError:
    # API key invalid or expired
    pass
except ValidationError as e:
    # Request shape was wrong
    print(e.details)
except MemoryError as e:
    # General API error (includes status code)
    print(e.status_code, e.message)
```

---

## Typed Everywhere

Full Pydantic models. Type hints on every method. No `dict` soup.

```python
from memoryintelligence.types import UMO, SearchResult, ExplainResponse
```

---

## Examples & Docs

- **[Getting Started Guide](https://github.com/memoryintelligence/memoryintelligence-python-sdk/tree/main/docs/GETTING-STARTED.md)** — Full walkthrough
- **[FastAPI Integration](https://github.com/memoryintelligence/memoryintelligence-python-sdk/tree/main/examples/fastapi_app.py)** — Complete example
- **[Advanced Usage](https://github.com/memoryintelligence/memoryintelligence-python-sdk/tree/main/docs/ADVANCED.md)** — Batch processing, retry logic, custom configs

---

## Support

- **Docs:** [memoryintelligence.io/docs](https://memoryintelligence.io/docs)
- **Issues:** [github.com/memoryintelligence/memoryintelligence-python-sdk/issues](https://github.com/memoryintelligence/memoryintelligence-python-sdk/issues)
- **Beta:** [memoryintelligence.io/beta](https://memoryintelligence.io/beta)

---

**Memory Intelligence™** — Setting the standard for memory.

Built by [somewhere](https://somewheremedia.com)
