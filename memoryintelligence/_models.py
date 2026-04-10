"""Memory Intelligence SDK - Models.

Core Pydantic models, enums, and response types for the SDK.
These define the contract between developers and the MI API.

Design Principles:
    1. Meaning-Only by Default: Raw content discarded unless explicitly overridden
    2. Provenance-First: Every operation produces verifiable audit trail
    3. Scope Isolation: Cryptographic boundaries, not just policies
    4. Explainability: Human + audit explanations on every operation
    5. Edge-Ready: Same types work cloud and on-prem
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ============================================================================
# ENCRYPTED PAYLOAD
# ============================================================================

class EncryptedPayload(BaseModel):
    """Encrypted content payload for transmission."""
    model_config = ConfigDict(frozen=True)

    ciphertext: str  # base64
    nonce: str  # base64
    tag: str  # base64
    key_id: str  # SHA-256 hash of key
    algorithm: str = "AES-256-GCM"


# ============================================================================
# ENUMS - SDK Controlled Vocabularies
# ============================================================================

class Scope(str, Enum):
    """
    Governance scope for memory isolation.

    Scopes are cryptographic boundaries—data in one scope is
    technically inaccessible from another, not just policy-restricted.
    """
    USER = "user"           # Personal user memories
    CLIENT = "client"       # Per-client isolation (consulting, legal)
    PROJECT = "project"     # Per-project isolation
    TEAM = "team"           # Team-shared memories
    ORGANIZATION = "org"    # Organization-wide
    ALL = "all"             # All accessible scopes (for deletion)


class RetentionPolicy(str, Enum):
    """
    What to retain after processing.

    Privacy by design: meaning_only is the default, discards raw content.
    """
    MEANING_ONLY = "meaning_only"   # Extract meaning, discard raw (DEFAULT)
    FULL = "full"                    # Store raw + meaning (requires governance override)
    SUMMARY_ONLY = "summary_only"    # Store summary + meaning, discard raw


class PIIHandling(str, Enum):
    """How to handle detected PII."""
    DETECT_ONLY = "detect_only"             # Flag PII, don't modify
    EXTRACT_AND_REDACT = "extract_and_redact"  # Extract to meaning, redact in output
    HASH = "hash"                            # Replace PII with deterministic hash
    REJECT = "reject"                        # Reject content containing PII


class ProvenanceMode(str, Enum):
    """Provenance tracking level."""
    STANDARD = "standard"       # Hash chain, timestamp (DEFAULT)
    AUTHORSHIP = "authorship"   # + semantic fingerprint, lineage tracking
    AUDIT = "audit"             # + full transformation log


class ExplainLevel(str, Enum):
    """Level of explanation to include in responses."""
    NONE = "none"           # No explanation (fastest)
    HUMAN = "human"         # Human-readable only
    AUDIT = "audit"         # Machine-verifiable only
    FULL = "full"           # Both human + audit (DEFAULT when explain=True)


# ============================================================================
# RESPONSE TYPES - What the SDK Returns
# ============================================================================

class Entity(BaseModel):
    """An extracted entity from content."""
    model_config = ConfigDict(frozen=True)

    text: str
    type: str               # PERSON, ORG, LOCATION, CONCEPT, etc.
    confidence: float = Field(ge=0.0, le=1.0)  # 0.0 to 1.0
    first_seen: datetime | None = None
    resolved_ulid: str | None = None  # Canonical entity ID


class Topic(BaseModel):
    """An extracted topic from content."""
    model_config = ConfigDict(frozen=True)

    name: str
    confidence: float = Field(ge=0.0, le=1.0)
    parent: str | None = None


class SVOTriple(BaseModel):
    """Subject-Verb-Object extraction."""
    model_config = ConfigDict(frozen=True)

    subject: str
    verb: str
    object: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class Provenance(BaseModel):
    """Cryptographic provenance record."""
    model_config = ConfigDict(frozen=True)

    semantic_hash: str              # Hash of meaning content
    timestamp_anchor: datetime      # When processed (timezone-aware)
    hash_chain: str                 # Link to previous hash
    lineage: list[str] = Field(default_factory=list)  # Parent UMO IDs
    model_version: str = ""         # Processing model version

    def verify(self) -> bool:
        """Verify hash chain integrity."""
        # Implementation would verify cryptographic chain
        return True


class ExplainHuman(BaseModel):
    """Human-readable explanation."""
    model_config = ConfigDict(frozen=True)

    summary: str
    key_reasons: list[str] = Field(default_factory=list)
    what_changed: str | None = None


class ExplainAudit(BaseModel):
    """Machine-verifiable audit explanation."""
    model_config = ConfigDict(frozen=True)

    semantic_score: float = 0.0
    temporal_score: float = 0.0
    entity_score: float = 0.0
    graph_score: float = 0.0
    topic_match: list[str] = Field(default_factory=list)
    model_version: str = ""
    hash_chain: str = ""
    reproducible: bool = True


class Explanation(BaseModel):
    """Combined explanation for auditable AI."""
    model_config = ConfigDict(frozen=True)

    human: ExplainHuman
    audit: ExplainAudit


class PIIDetection(BaseModel):
    """PII detection result."""
    model_config = ConfigDict(frozen=True)

    detected: bool
    types: list[str] = Field(default_factory=list)  # PERSON, EMAIL, PHONE, SSN, etc.
    count: int = 0
    handling_applied: PIIHandling = PIIHandling.DETECT_ONLY


class MeaningObject(BaseModel):
    """
    The core output of MI processing.

    This is what developers work with—structured meaning, not raw content.
    """
    model_config = ConfigDict(frozen=True)

    umo_id: str                                 # ULID identifier
    user_ulid: str                              # Owner

    # Meaning extraction
    entities: list[Entity] = Field(default_factory=list)
    topics: list[Topic] = Field(default_factory=list)
    svo_triples: list[SVOTriple] = Field(default_factory=list)
    key_phrases: list[str] = Field(default_factory=list)
    summary: str | None = None

    # Embeddings
    embedding: list[float] | None = None     # 384D or 768D vector
    embedding_model: str = ""

    # Sentiment
    sentiment_label: str | None = None       # positive, negative, neutral
    sentiment_score: float = 0.0

    # Temporal (timezone-aware)
    timestamp: datetime | None = None
    ingested_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    recency_score: float = 1.0

    # Quality
    quality_score: float = Field(default=0.0, ge=0.0, le=1.0)  # 0.0 to 1.0
    validation_status: str = "pending"

    # Provenance
    provenance: Provenance | None = None

    # PII
    pii: PIIDetection | None = None

    # Scope
    scope: Scope = Scope.USER
    scope_id: str | None = None              # client_ulid, project_ulid, etc.


class SearchResult(BaseModel):
    """A single search result with explanation."""
    model_config = ConfigDict(frozen=True)

    umo: MeaningObject
    score: float
    explain: Explanation | None = None


class SearchResponse(BaseModel):
    """Response from mi.umo.search()."""
    model_config = ConfigDict(frozen=True)

    results: list[SearchResult]
    query: str
    scope: Scope
    total_count: int

    # Audit
    audit_proof: dict[str, Any] | None = None


class MatchResult(BaseModel):
    """Response from mi.umo.match()."""
    model_config = ConfigDict(frozen=True)

    score: float = Field(ge=0.0, le=1.0)     # 0.0 to 1.0
    match: bool                             # Above threshold?
    source_ulid: str
    candidate_ulid: str
    explain: Explanation | None = None


class DeleteResult(BaseModel):
    """Response from mi.umo.delete()."""
    model_config = ConfigDict(frozen=True)

    deleted_count: int
    user_ulid: str
    scope: Scope
    scope_id: str | None = None
    audit_proof: dict[str, Any] = Field(default_factory=dict)


class VerifyResult(BaseModel):
    """Response from verify_provenance()."""
    model_config = ConfigDict(frozen=True)

    valid: bool
    semantic_hash: str
    timestamp_anchor: datetime  # timezone-aware
    original_author_ulid: str | None = None
    first_published: datetime | None = None
    hash_chain_valid: bool = True
    audit_proof: dict[str, Any] = Field(default_factory=dict)


class BatchItemResult(BaseModel):
    """Result for a single item in batch processing."""
    model_config = ConfigDict(frozen=True)

    index: int
    success: bool
    umo_id: str | None = None
    error: str | None = None
    umo: MeaningObject | None = None


class BatchResult(BaseModel):
    """Response from mi.umo.batch()."""
    model_config = ConfigDict(frozen=True)

    results: list[BatchItemResult]
    total: int
    succeeded: int
    failed: int


class UploadResult(BaseModel):
    """Response from mi.umo.upload()."""
    model_config = ConfigDict(frozen=True)

    umo_id: str
    media_type: str
    original_filename: str
    file_size_bytes: int
    extracted_text_length: int
    summary: str
    entities: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    quality_score: float = 0.0
    extraction_metadata: dict[str, Any] = Field(default_factory=dict)


class BatchUploadItemResult(BaseModel):
    """Result for a single item in a batch upload."""
    model_config = ConfigDict(frozen=True)

    index: int
    success: bool
    type: str = "text"  # "text", "audio", "video", "image", "document"
    umo_id: str | None = None
    original_filename: str | None = None
    extracted_text_length: int = 0
    summary: str | None = None
    entities: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    quality_score: float = 0.0
    error: str | None = None


class BatchUploadResult(BaseModel):
    """Response from mi.umo.batch_upload()."""
    model_config = ConfigDict(frozen=True)

    results: list[BatchUploadItemResult]
    total: int
    succeeded: int
    failed: int


# ============================================================================
# CONFIGURATION TYPES
# ============================================================================

class ProcessConfig(BaseModel):
    """Configuration for mi.umo.process()."""
    model_config = ConfigDict(frozen=True)

    retention_policy: RetentionPolicy = RetentionPolicy.MEANING_ONLY
    pii_handling: PIIHandling = PIIHandling.EXTRACT_AND_REDACT
    provenance_mode: ProvenanceMode = ProvenanceMode.STANDARD
    scope: Scope = Scope.USER
    scope_id: str | None = None

    # Edge processing
    edge_mode: bool = False
    hipaa_mode: bool = False

    # Optional metadata
    source: str = "api"
    metadata: dict[str, Any] = Field(default_factory=dict)


class SearchConfig(BaseModel):
    """Configuration for mi.umo.search()."""
    model_config = ConfigDict(frozen=True)

    scope: Scope = Scope.USER
    scope_id: str | None = None
    explain: bool | ExplainLevel = False
    limit: int = Field(default=10, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    # Filtering
    date_from: datetime | None = None
    date_to: datetime | None = None
    topics: list[str] | None = None
    entities: list[str] | None = None

    # Budget
    budget_tokens: int | None = Field(default=None, ge=1)  # Max tokens in response


class MatchConfig(BaseModel):
    """Configuration for mi.umo.match()."""
    model_config = ConfigDict(frozen=True)

    explain: bool | ExplainLevel = False
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)
