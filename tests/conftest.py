"""Test configuration and fixtures.

This module provides pytest fixtures for testing the Memory Intelligence SDK.
All external HTTP calls are mocked using pytest-httpx.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Generator
from unittest.mock import Mock

import pytest
import pytest_httpx

from memoryintelligence import MemoryClient, EdgeClient
from memoryintelligence._license import LicenseType, LicenseStatus


# =============================================================================
# Environment Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def clear_env() -> None:
    """Clear environment variables before each test."""
    for key in list(os.environ.keys()):
        if key.startswith("MI_"):
            del os.environ[key]


# =============================================================================
# API Key Fixtures
# =============================================================================

@pytest.fixture
def api_key() -> str:
    """Valid test API key."""
    return "mi_sk_test_" + "a" * 40


@pytest.fixture
def api_key_starter() -> str:
    """Test API key for STARTER tier."""
    return "mi_sk_test_starter_" + "a" * 32


@pytest.fixture
def api_key_professional() -> str:
    """Test API key for PROFESSIONAL tier."""
    return "mi_sk_test_prof_" + "a" * 36


@pytest.fixture
def api_key_enterprise() -> str:
    """Test API key for ENTERPRISE tier."""
    return "mi_sk_test_enterprise_" + "a" * 28


# =============================================================================
# License Response Fixtures
# =============================================================================

@pytest.fixture
def license_response_active() -> dict[str, Any]:
    """Active PROFESSIONAL license response."""
    return {
        "status": "active",
        "tier": "professional",
        "revoked": False,
        "suspended": False,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
    }


@pytest.fixture
def license_response_starter() -> dict[str, Any]:
    """Active STARTER license response."""
    return {
        "status": "active",
        "tier": "starter",
        "revoked": False,
        "suspended": False,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
    }


@pytest.fixture
def license_response_enterprise() -> dict[str, Any]:
    """Active ENTERPRISE license response."""
    return {
        "status": "active",
        "tier": "enterprise",
        "revoked": False,
        "suspended": False,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
    }


@pytest.fixture
def license_response_revoked() -> dict[str, Any]:
    """Revoked license response."""
    return {
        "status": "active",
        "tier": "professional",
        "revoked": True,
        "suspended": False,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
    }


@pytest.fixture
def license_response_suspended() -> dict[str, Any]:
    """Suspended license response."""
    return {
        "status": "active",
        "tier": "professional",
        "revoked": False,
        "suspended": True,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
    }


@pytest.fixture
def license_response_expired_recent() -> dict[str, Any]:
    """Expired license (5 days ago) - within grace period."""
    return {
        "status": "expired",
        "tier": "professional",
        "revoked": False,
        "suspended": False,
        "expires_at": (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    }


@pytest.fixture
def license_response_expired_old() -> dict[str, Any]:
    """Expired license (20 days ago) - beyond grace period."""
    return {
        "status": "expired",
        "tier": "professional",
        "revoked": False,
        "suspended": False,
        "expires_at": (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
    }


# =============================================================================
# UMO Response Fixtures
# =============================================================================

@pytest.fixture
def mock_transport_response() -> dict[str, Any]:
    """Mock API response for MeaningObject."""
    return {
        "umo_id": "01ABC12345678901234567890",
        "user_ulid": "01DEF12345678901234567890",
        "entities": [
            {"text": "John Doe", "type": "PERSON", "confidence": 0.95, "start": 0, "end": 8}
        ],
        "topics": [
            {"name": "budget", "confidence": 0.88}
        ],
        "svo_triples": [],
        "key_phrases": ["budget approval"],
        "summary": "Budget approved for Q4",
        "embedding": None,
        "embedding_model": "",
        "sentiment_label": "positive",
        "sentiment_score": 0.85,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "recency_score": 1.0,
        "quality_score": 0.92,
        "validation_status": "validated",
        "provenance": {
            "semantic_hash": "sha256:abc123",
            "timestamp_anchor": datetime.now(timezone.utc).isoformat(),
            "hash_chain": "sha256:prev456",
            "lineage": [],
            "model_version": "v2.0.0"
        },
        "pii": {
            "detected": False,
            "types": [],
            "count": 0,
            "handling_applied": "extract_and_redact"
        },
        "scope": "user",
        "scope_id": None
    }


@pytest.fixture
def search_response() -> dict[str, Any]:
    """Mock API response for search."""
    return {
        "results": [
            {
                "umo": {
                    "umo_id": "01ABC12345678901234567890",
                    "user_ulid": "01DEF12345678901234567890",
                    "entities": [{"text": "John Doe", "type": "PERSON", "confidence": 0.95, "start": 0, "end": 8}],
                    "topics": [{"name": "budget", "confidence": 0.88}],
                    "svo_triples": [],
                    "key_phrases": ["budget approval"],
                    "summary": "Budget approved for Q4",
                    "embedding": None,
                    "embedding_model": "",
                    "sentiment_label": "positive",
                    "sentiment_score": 0.85,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                    "recency_score": 1.0,
                    "quality_score": 0.92,
                    "validation_status": "validated",
                    "provenance": {
                        "semantic_hash": "sha256:abc123",
                        "timestamp_anchor": datetime.now(timezone.utc).isoformat(),
                        "hash_chain": "sha256:prev456",
                        "lineage": [],
                        "model_version": "v2.0.0"
                    },
                    "pii": {"detected": False, "types": [], "count": 0, "handling_applied": "extract_and_retract"},
                    "scope": "user",
                    "scope_id": None
                },
                "score": 0.95
            }
        ],
        "total_count": 1
    }


@pytest.fixture
def match_response() -> dict[str, Any]:
    """Mock API response for match."""
    return {
        "score": 0.85,
        "match": True,
        "source_ulid": "01SOURCE12345678901234567890",
        "candidate_ulid": "01CANDIDATE12345678901234567890"
    }


@pytest.fixture
def match_response_with_explain() -> dict[str, Any]:
    """Mock API response for match with explanation."""
    return {
        "score": 0.85,
        "match": True,
        "source_ulid": "01SOURCE12345678901234567890",
        "candidate_ulid": "01CANDIDATE12345678901234567890",
        "explain": {
            "human": {"summary": "Strong match", "key_reasons": ["Topic match"]},
            "audit": {"semantic_score": 0.9, "reproducible": True}
        }
    }


@pytest.fixture
def explain_response() -> dict[str, Any]:
    """Mock API response for explain."""
    return {
        "human": {
            "summary": "This is relevant",
            "key_reasons": ["Topic match"]
        },
        "audit": {
            "semantic_score": 0.88,
            "reproducible": True
        }
    }


@pytest.fixture
def delete_response() -> dict[str, Any]:
    """Mock API response for delete."""
    return {
        "deleted_count": 5,
        "audit_proof": {
            "operation": "delete",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    }


# =============================================================================
# Client Fixtures
# =============================================================================

@pytest.fixture
def client(
    api_key: str,
    httpx_mock: pytest_httpx.HTTPXMock,
    license_response_active: dict[str, Any]
) -> Generator[MemoryClient, None, None]:
    """Create a MemoryClient with mocked transport (PROFESSIONAL tier)."""
    # Mock license validation endpoint
    httpx_mock.add_response(
        method="POST",
        url="https://api.memoryintelligence.io/v1/license/validate",
        json=license_response_active
    )

    client = MemoryClient(api_key=api_key)
    yield client
    client.close()


@pytest.fixture
def client_starter(
    api_key_starter: str,
    httpx_mock: pytest_httpx.HTTPXMock,
    license_response_starter: dict[str, Any]
) -> Generator[MemoryClient, None, None]:
    """Create a MemoryClient with STARTER tier license."""
    httpx_mock.add_response(
        method="POST",
        url="https://api.memoryintelligence.io/v1/license/validate",
        json=license_response_starter
    )

    client = MemoryClient(api_key=api_key_starter)
    yield client
    client.close()


@pytest.fixture
def client_enterprise(
    api_key_enterprise: str,
    httpx_mock: pytest_httpx.HTTPXMock,
    license_response_enterprise: dict[str, Any]
) -> Generator[MemoryClient, None, None]:
    """Create a MemoryClient with ENTERPRISE tier license."""
    httpx_mock.add_response(
        method="POST",
        url="https://api.memoryintelligence.io/v1/license/validate",
        json=license_response_enterprise
    )

    client = MemoryClient(api_key=api_key_enterprise)
    yield client
    client.close()


# =============================================================================
# Edge Client Fixtures
# =============================================================================

@pytest.fixture
def edge_endpoint() -> str:
    """Edge endpoint URL."""
    return "https://mi.internal.example.com"


@pytest.fixture
def edge_client_enterprise(
    edge_endpoint: str,
    api_key_enterprise: str,
    httpx_mock: pytest_httpx.HTTPXMock,
    license_response_enterprise: dict[str, Any]
) -> Generator[EdgeClient, None, None]:
    """Create an EdgeClient with ENTERPRISE license."""
    # Mock edge endpoint license validation
    httpx_mock.add_response(
        method="POST",
        url=f"{edge_endpoint}/v1/license/validate",
        json=license_response_enterprise
    )

    client = EdgeClient(
        endpoint=edge_endpoint,
        api_key=api_key_enterprise
    )
    yield client
    client.close()


@pytest.fixture
def aggregate_response() -> dict[str, Any]:
    """Mock API response for aggregate."""
    return {
        "results": [
            {"count": 100, "metric": "avg_score", "value": 0.85}
        ],
        "privacy_guarantee": "k-anonymity",
        "minimum_cohort_size": 50,
        "suppressed_results": 2
    }


@pytest.fixture
def phi_verify_response() -> dict[str, Any]:
    """Mock API response for PHI verification."""
    return {
        "umo_id": "01ABC12345678901234567890",
        "phi_detected": True,
        "phi_types": ["PATIENT_NAME", "MEDICAL_RECORD_NUMBER"],
        "handling_applied": "HASH",
        "raw_phi_stored": False,
        "raw_phi_transmitted": False,
        "audit_proof": "sha256:abc123"
    }


@pytest.fixture
def audit_log_response() -> dict[str, Any]:
    """Mock API response for audit log export."""
    return {
        "events": [
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "operation": "process",
                "user_ulid": "01USER123",
                "umo_id": "01ABC123"
            }
        ],
        "total_events": 1
    }


# =============================================================================
# Utility Fixtures
# =============================================================================

@pytest.fixture
def tmp_cache_dir(tmp_path):
    """Provide temporary directory for license cache testing."""
    cache_dir = tmp_path / ".mi_cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


@pytest.fixture
def mock_transport():
    """Create a mock transport for unit tests."""
    return Mock()


# =============================================================================
# License Cache Management
# =============================================================================

@pytest.fixture(autouse=True)
def clear_license_cache():
    """Clear license cache before each test to ensure fresh license validation."""
    from memoryintelligence._license import LICENSE_CACHE_FILE
    if LICENSE_CACHE_FILE.exists():
        LICENSE_CACHE_FILE.unlink()
    yield
    # Clean up after test
    if LICENSE_CACHE_FILE.exists():
        LICENSE_CACHE_FILE.unlink()


# =============================================================================
# pytest-httpx Configuration
# =============================================================================

@pytest.fixture(autouse=True)
def reset_httpx_mock(httpx_mock):
    """Reset httpx_mock after each test to prevent unused mock errors."""
    yield
    # httpx_mock.reset() is called automatically by pytest-httpx
