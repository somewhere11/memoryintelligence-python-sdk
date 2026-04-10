# Changelog

## [2.0.1] - 2026-03-27

### Fixed
- Corrected all documentation and billing URLs from `memoryintelligence.dev` to `memoryintelligence.io`
- Updated default API base URL from `api.memoryintelligence.dev` to `api.memoryintelligence.io`
- Resolved dead links in error messages, edge client defaults, and PyPI package metadata


All notable changes to the Memory Intelligence Python SDK.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-02-27

### Breaking Changes

#### UMO Namespace Pattern
- **Changed:** All UMO operations moved to `mi.umo.*` namespace
  - `mi.process()` → `mi.umo.process()`
  - `mi.search()` → `mi.umo.search()`
  - `mi.match()` → `mi.umo.match()`
  - `mi.explain()` → `mi.umo.explain()`
  - `mi.delete()` → `mi.umo.delete()`

#### Mandatory Encryption
- **Changed:** Client-side AES-256-GCM encryption is now **mandatory**
- **Removed:** `enable_encryption` parameter (previously optional in v1)
- **Added:** Automatic encryption with ephemeral key if `MI_ENCRYPTION_KEY` not set
- **Added:** Warning logged when using ephemeral keys in production

#### User ID Format
- **Changed:** `user_id` parameter renamed to `user_ulid`
- **Changed:** Must use ULID format (26-character string: `01ABC...`)
- **Migration:** Generate ULIDs: `str(ULID())`

#### Dual Identity Pattern
- **Changed:** `user_ulid` no longer defaults from client constructor
- **Added:** `for_user(user_ulid)` method for scoped clients
- **Usage:**
  ```python
  # v2.0
  mi = MemoryClient()
  user_client = mi.for_user("01USER12345678901234567890")
  umo = user_client.umo.process("content")
  ```

#### Model Serialization
- **Changed:** Models converted from dataclasses to Pydantic BaseModel
- **Changed:** `asdict(umo)` → `umo.model_dump()`
- **Changed:** `json.dumps(asdict(umo))` → `umo.model_dump_json()`
- **Added:** Full Pydantic validation and serialization support

#### Error Classes
- **Renamed:** `AuthError` → `AuthenticationError`
- **Added:** New exception classes:
  - `LicenseError` - License validation and feature gating
  - `PIIViolationError` - PII detection violations (HTTP 451)
  - `PaymentRequiredError` - License required (HTTP 402)
  - `ConflictError` - Resource conflicts (HTTP 409)

### Added

#### EdgeClient
- **Added:** `EdgeClient` for on-premises deployment
- **Features:**
  - HIPAA mode (`hipaa_mode=True`)
  - Air-gapped deployment (`air_gapped=True`)
  - Federated aggregation (`aggregate()`)
  - PHI handling verification (`verify_phi_handling()`)
  - Audit log export (`export_audit_log()`)
- **License Required:** ENTERPRISE tier only

#### Async Support
- **Added:** `AsyncMemoryClient` for non-blocking operations
- **Features:**
  - Full async/await support
  - Connection pooling with `httpx.AsyncClient`
  - Same API as sync client

#### License System
- **Added:** License tier enforcement (TRIAL, STARTER, PROFESSIONAL, ENTERPRISE)
- **Added:** Feature gating:
  - STARTER: `process()`, `search()` only
  - PROFESSIONAL: All cloud features (`match()`, `explain()`)
  - ENTERPRISE: All features including EdgeClient
- **Added:** Grace periods:
  - Cloud: 14 days
  - Air-gapped: 30 days
- **Added:** License caching with 24-hour TTL
- **Added:** Background license revalidation

#### Encryption Enhancements
- **Added:** AES-256-GCM encryption with PBKDF2 (100,000 iterations)
- **Added:** User ULID binding via associated data
- **Added:** Key identification via SHA-256 hash
- **Added:** `EncryptedPayload` model for inspection

#### HTTP Transport
- **Added:** `SyncTransport` and `AsyncTransport` with retry logic
- **Added:** Exponential backoff with jitter
- **Added:** Retry on: 408, 429, 500, 502, 503, 504
- **Added:** ULID request IDs for tracing
- **Added:** Automatic error mapping from HTTP status codes

#### Models
- **Added:** Pydantic models for all API responses:
  - `MeaningObject`, `Entity`, `Topic`, `SVOTriple`
  - `SearchResponse`, `SearchResult`, `MatchResult`
  - `Explanation`, `HumanExplanation`, `AuditExplanation`
  - `Provenance`, `PIIInfo`, `DeleteResult`
- **Added:** Enum types:
  - `Scope` (USER, CLIENT, ORGANIZATION)
  - `PIIHandling` (EXTRACT_AND_REDACT, HASH, REJECT)
  - `RetentionPolicy` (FULL, MEANING_ONLY, NO_STORAGE)
  - `ProvenanceMode` (MINIMAL, STANDARD, AUDIT)
  - `LicenseType` (TRIAL, STARTER, PROFESSIONAL, ENTERPRISE)
  - `LicenseStatus` (ACTIVE, EXPIRED, REVOKED, SUSPENDED)

### Changed

#### Dependencies
- **Added:** `httpx>=0.27.0` (was `requests` in v1)
- **Added:** `pydantic>=2.5.0`
- **Added:** `cryptography>=42.0.0`
- **Added:** `python-ulid>=2.0.0`
- **Removed:** `requests` dependency

#### Configuration
- **Changed:** `MI_API_KEY` environment variable now the primary auth method
- **Changed:** `MI_ENCRYPTION_KEY` for persistent encryption keys
- **Added:** Validation for API key format (`mi_sk_` prefix)

#### Error Handling
- **Changed:** All errors now include `code` attribute
- **Changed:** `RateLimitError` includes `retry_after` seconds
- **Changed:** `ServerError` includes `request_id` for debugging
- **Changed:** `ValidationError` includes `field` for invalid parameters
- **Changed:** `LicenseError` includes `days_expired` and `renew_url`

### Removed

- **Removed:** Direct method calls on `MemoryClient` (use `mi.umo.*`)
- **Removed:** `enable_encryption` parameter (always enabled)
- **Removed:** `user_id` parameter (use `user_ulid`)
- **Removed:** `AuthError` exception (use `AuthenticationError`)

### Security

- **Added:** Mandatory client-side encryption for all content
- **Added:** User ULID binding prevents cross-user decryption
- **Added:** Authentication tags prevent tampering
- **Added:** PII detection with configurable handling
- **Added:** HIPAA mode for healthcare compliance
- **Added:** Audit logging for compliance reviews
- **Added:** Scope isolation (user/client/organization)

### Documentation

- **Added:** Quickstart guide (`docs/quickstart.md`)
- **Added:** Authentication guide (`docs/authentication.md`)
- **Added:** Encryption guide (`docs/encryption.md`)
- **Added:** Licensing guide (`docs/licensing.md`)
- **Added:** API reference (`docs/api_reference.md`)
- **Added:** Enterprise guide (`docs/enterprise.md`)
- **Added:** Migration guide (`docs/migration_v1_to_v2.md`)
- **Added:** FAQ (`docs/faq.md`)
- **Added:** OpenAPI specification (`docs/openapi.yaml`)

### Testing

- **Added:** Comprehensive test suite:
  - `tests/test_client.py` - UMONamespace methods
  - `tests/test_crypto.py` - Encryption/decryption
  - `tests/test_license.py` - License validation
  - `tests/test_edge_client.py` - EdgeClient functionality
  - `tests/test_errors.py` - HTTP status mapping
  - `tests/test_integration.py` - End-to-end workflows
- **Added:** pytest fixtures with mocked transport
- **Added:** Test coverage for all license tiers

---

## [1.0.1] - 2026-02-07

### Fixed
- Corrected `ProvenanceError` in `__all__` exports list (final typo fix)

## [1.0.0] - 2026-02-07 [YANKED]

### Added
- **MemoryClient** with 6 core operations: process, search, match, explain, delete, verify_provenance
- **EdgeClient** for on-premises HIPAA-compliant deployments
- Privacy-first architecture with meaning-only retention (default)
- Structured semantic extraction (entities, topics, SVO triples, key phrases)
- Explainable search results with human + audit explanations
- Cryptographic provenance tracking with hash chain verification
- ULID-based identity firewall for cryptographic tenant isolation
- Scope-based access control (user, team, client, organization)
- PII detection and configurable handling (extract_and_redact, hash, reject)
- Type-safe API with Pydantic models
- Comprehensive error handling (7 exception types)
- 30+ unit and integration tests

### Known Limitations
- Pagination not yet implemented (coming in v1.1.0)
- Streaming search results not yet available
- Temporal intelligence parameter present but not fully validated in tests

### Fixed
- Corrected `ProvenanceError` exception name (was misspelled as `ProvenenaceError`)

---

## Migration Guide

See [docs/migration_v1_to_v2.md](docs/migration_v1_to_v2.md) for detailed migration instructions.

### Quick Migration Checklist

- [ ] Update imports to use `mi.umo.*` namespace
- [ ] Rename `user_id` to `user_ulid` (use ULID format)
- [ ] Set `MI_ENCRYPTION_KEY` environment variable
- [ ] Update `asdict(umo)` to `umo.model_dump()`
- [ ] Rename `AuthError` to `AuthenticationError`
- [ ] Use `for_user()` for multi-user applications

---

## Support

- **Documentation:** [docs.memoryintelligence.dev](https://docs.memoryintelligence.dev)
- **Migration Help:** migration@memoryintelligence.dev
- **Issues:** [github.com/memoryintelligence/sdk-python/issues](https://github.com/memoryintelligence/sdk-python/issues)
- **Changelog:** This file

[2.0.0]: https://github.com/memoryintelligence/sdk-python/releases/tag/v2.0.0
[1.0.1]: https://github.com/memoryintelligence/sdk-python/releases/tag/v1.0.1
[1.0.0]: https://github.com/memoryintelligence/sdk-python/releases/tag/v1.0.0
[Unreleased]: https://github.com/memoryintelligence/sdk-python/compare/v2.0.0...HEAD
