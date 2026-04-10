"""
Memory Intelligence SDK
=======================

The official Python SDK for Memory Intelligence — verifiable meaning infrastructure for AI.

Installation:
    pip install memoryintelligence

Quick Start:
    from memoryintelligence import MemoryClient

    mi = MemoryClient(api_key="mi_sk_...")

    # Process content → meaning (raw content discarded by default)
    umo = mi.umo.process("Important meeting notes", user_ulid="01ABC...")

    # Search with explanation
    results = mi.umo.search("What did we discuss?", user_ulid="01ABC...")

    # Multi-tenant pattern
    user = mi.for_user("01ABC...")
    umo = user.umo.process("Meeting notes")  # No user_ulid needed

Async Support:
    from memoryintelligence import AsyncMemoryClient

    async with AsyncMemoryClient(api_key="mi_sk_...") as mi:
        umo = await mi.umo.process("Content", user_ulid="01ABC...")
        results = await mi.umo.search("Query", user_ulid="01ABC...")

For regulated industries (HIPAA, legal, finance):
    from memoryintelligence import EdgeClient

    mi = EdgeClient(
        endpoint="https://mi.internal.yourcompany.com",
        api_key="mi_sk_...",
        hipaa_mode=True
    )

    # Process locally—data never leaves your infrastructure
    umo = mi.umo.process(clinical_note, patient_ulid="01ABC...")

Core Operations (via umo namespace):
    - mi.umo.process()  → Convert raw content to meaning
    - mi.umo.search()   → Find relevant memories
    - mi.umo.match()    → Compare memories for relevance
    - mi.umo.explain()  → Get explanation for any UMO
    - mi.umo.delete()   → Remove all user data (GDPR)

Version: 2.0.0
Author: Memory Intelligence Team
License: MIT
"""

# Import version from dedicated module
from ._version import __version__

__author__ = "Memory Intelligence Team"
__license__ = "MIT"

# ============================================================================
# Public API - Clients
# ============================================================================

# Sync clients
from ._client import MemoryClient
from ._edge_client import EdgeClient

# Async client
from ._client import AsyncMemoryClient

# ============================================================================
# Enums (Controlled Vocabularies)
# ============================================================================

from ._models import (
    Scope,
    RetentionPolicy,
    PIIHandling,
    ProvenanceMode,
    ExplainLevel,
)

# ============================================================================
# Response Types
# ============================================================================

from ._models import (
    EncryptedPayload,
    MeaningObject,
    SearchResponse,
    SearchResult,
    MatchResult,
    DeleteResult,
    VerifyResult,
    Explanation,
    ExplainHuman,
    ExplainAudit,
    Entity,
    Topic,
    SVOTriple,
    Provenance,
    PIIDetection,
)

# ============================================================================
# Config Types
# ============================================================================

from ._models import (
    ProcessConfig,
    SearchConfig,
    MatchConfig,
)

# ============================================================================
# Exceptions
# ============================================================================

from ._errors import (
    MIError,
    ConfigurationError,
    LicenseError,
    AuthenticationError,
    RateLimitError,
    ScopeViolationError,
    PIIViolationError,
    GovernanceError,
    ProvenanceError,
    ValidationError,
    NotFoundError,
    ServerError,
    ConnectionError,
    TimeoutError,
    ConflictError,
    PaymentRequiredError,
    EncryptionError,
    PermissionError,
)

# ============================================================================
# Convenience exports (__all__)
# ============================================================================

__all__ = [
    # Version
    "__version__",

    # Clients (sync)
    "MemoryClient",
    "EdgeClient",

    # Clients (async)
    "AsyncMemoryClient",

    # Enums
    "Scope",
    "RetentionPolicy",
    "PIIHandling",
    "ProvenanceMode",
    "ExplainLevel",

    # Response types
    "EncryptedPayload",
    "MeaningObject",
    "SearchResponse",
    "SearchResult",
    "MatchResult",
    "DeleteResult",
    "VerifyResult",
    "Explanation",
    "ExplainHuman",
    "ExplainAudit",
    "Entity",
    "Topic",
    "SVOTriple",
    "Provenance",
    "PIIDetection",

    # Config types
    "ProcessConfig",
    "SearchConfig",
    "MatchConfig",

    # Exceptions
    "MIError",
    "ConfigurationError",
    "LicenseError",
    "AuthenticationError",
    "PermissionError",
    "RateLimitError",
    "ScopeViolationError",
    "PIIViolationError",
    "GovernanceError",
    "ProvenanceError",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "PaymentRequiredError",
    "EncryptionError",
    "ServerError",
    "ConnectionError",
    "TimeoutError",
]
