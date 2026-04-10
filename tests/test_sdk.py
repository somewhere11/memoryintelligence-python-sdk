"""
Memory Intelligence SDK - Test Suite
=====================================

Comprehensive tests for SDK functionality and governance.

Run with:
    cd sdk/python && pytest tests/ -v

Coverage:
    1. Core Operations (6 methods)
    2. Governance Enforcement (scope, PII, retention)
    3. EdgeClient (HIPAA, air-gapped)
    4. Error Handling
"""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from dataclasses import asdict

# SDK imports
import sys
from pathlib import Path
sdk_path = Path(__file__).parent.parent / "memoryintelligence"
sys.path.insert(0, str(sdk_path.parent))

from memoryintelligence import (
    # Clients
    MemoryClient,
    EdgeClient,
    # Enums
    Scope,
    RetentionPolicy,
    PIIHandling,
    ProvenanceMode,
    ExplainLevel,
    # Types
    MeaningObject,
    SearchResponse,
    MatchResult,
    DeleteResult,
    VerifyResult,
    Explanation,
    # Errors
    MIError,
    AuthenticationError,
    ScopeViolationError,
    PIIViolationError,
)


# ============================================================================
# FIXTURES - Mock Data
# ============================================================================

@pytest.fixture
def mock_umo_response():
    """Standard UMO response from API."""
    return {
        "umo_id": "01HQWX5JKZM3N4P5Q6R7S8T9UV",
        "user_ulid": "01HQWX5JKZM3N4P5Q6R7S8T9AB",
        "entities": [
            {"text": "Sarah", "type": "PERSON", "confidence": 0.95},
            {"text": "budget", "type": "CONCEPT", "confidence": 0.88},
        ],
        "topics": [
            {"name": "finance", "confidence": 0.92},
            {"name": "approval", "confidence": 0.85},
        ],
        "svo_triples": [
            {"subject": "Sarah", "verb": "approved", "object": "budget", "confidence": 0.90},
        ],
        "key_phrases": ["budget approved", "Sarah said"],
        "summary": "Sarah approved the budget.",
        "embedding": [0.1, 0.2, 0.3] + [0.0] * 381,  # 384D vector
        "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
        "sentiment_label": "positive",
        "sentiment_score": 0.75,
        "timestamp": datetime.utcnow().isoformat(),
        "ingested_at": datetime.utcnow().isoformat(),
        "recency_score": 1.0,
        "quality_score": 0.85,
        "validation_status": "valid",
        "provenance": {
            "semantic_hash": "sha256:abc123...",
            "timestamp_anchor": datetime.utcnow().isoformat(),
            "hash_chain": "sha256:prev123...",
            "lineage": [],
            "model_version": "1.0.0",
        },
        "pii": {
            "detected": True,
            "types": ["PERSON"],
            "count": 1,
            "handling_applied": "extract_and_redact",
        },
        "scope": "user",
        "scope_id": None,
    }


@pytest.fixture
def mock_search_response(mock_umo_response):
    """Standard search response from API."""
    return {
        "results": [
            {
                "umo": mock_umo_response,
                "score": 0.92,
                "explain": {
                    "human": {
                        "summary": "High match based on budget topic and Sarah entity",
                        "key_reasons": ["Topic match: finance", "Entity match: Sarah"],
                    },
                    "audit": {
                        "semantic_score": 0.88,
                        "temporal_score": 0.95,
                        "entity_score": 0.90,
                        "graph_score": 0.75,
                        "topic_match": ["finance"],
                        "model_version": "1.0.0",
                        "hash_chain": "sha256:abc...",
                        "reproducible": True,
                    },
                },
            }
        ],
        "total_count": 1,
        "audit_proof": {"verified": True},
    }


@pytest.fixture
def mock_match_response():
    """Standard match response from API."""
    return {
        "score": 0.85,
        "match": True,
        "explain": {
            "human": {
                "summary": "Strong semantic alignment between user interests and content",
                "key_reasons": ["Shared topics", "Entity overlap"],
            },
            "audit": {
                "semantic_score": 0.85,
                "temporal_score": 0.90,
                "entity_score": 0.80,
                "graph_score": 0.70,
                "topic_match": ["finance", "technology"],
                "model_version": "1.0.0",
                "hash_chain": "sha256:def...",
                "reproducible": True,
            },
        },
    }


@pytest.fixture
def mock_delete_response():
    """Standard delete response from API."""
    return {
        "deleted_count": 42,
        "audit_proof": {
            "deletion_hash": "sha256:deleted...",
            "timestamp": datetime.utcnow().isoformat(),
            "verified": True,
        },
    }


@pytest.fixture
def mock_verify_response():
    """Standard provenance verification response."""
    return {
        "valid": True,
        "semantic_hash": "sha256:abc123...",
        "timestamp_anchor": datetime.utcnow().isoformat(),
        "original_author_ulid": "01HQWX5JKZM3N4P5Q6R7S8TABC",
        "first_published": (datetime.utcnow() - timedelta(days=30)).isoformat(),
        "hash_chain_valid": True,
        "audit_proof": {"chain_length": 5, "all_valid": True},
    }


# ============================================================================
# TEST 1: CLIENT INITIALIZATION
# ============================================================================

class TestClientInitialization:
    """Tests for client initialization and authentication."""
    
    def test_valid_api_key(self):
        """Valid API key should initialize client."""
        with patch('httpx.Client'):
            client = MemoryClient(api_key="mi_sk_test_abc123")
            assert client.api_key == "mi_sk_test_abc123"
    
    def test_invalid_api_key_format(self):
        """Invalid API key should raise AuthenticationError."""
        with pytest.raises(AuthenticationError) as exc_info:
            MemoryClient(api_key="invalid_key")
        assert "mi_sk_" in str(exc_info.value)
    
    def test_empty_api_key(self):
        """Empty API key should raise AuthenticationError."""
        with pytest.raises(AuthenticationError):
            MemoryClient(api_key="")
    
    def test_org_ulid_passed(self):
        """Organization ULID should be stored."""
        with patch('httpx.Client'):
            client = MemoryClient(
                api_key="mi_sk_test_abc123",
                org_ulid="01HQWX5JKZM3N4P5Q6R7S8TORG"
            )
            assert client.org_ulid == "01HQWX5JKZM3N4P5Q6R7S8TORG"
    
    def test_custom_base_url(self):
        """Custom base URL should be used."""
        with patch('httpx.Client') as mock_client:
            MemoryClient(
                api_key="mi_sk_test_abc123",
                base_url="https://custom.api.com"
            )
            mock_client.assert_called_once()
            assert "custom.api.com" in str(mock_client.call_args)


# ============================================================================
# TEST 2: CORE OPERATION - PROCESS
# ============================================================================

class TestProcessOperation:
    """Tests for mi.process() operation."""
    
    def test_process_basic(self, mock_umo_response):
        """Basic process should return MeaningObject."""
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_umo_response
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            client = MemoryClient(api_key="mi_sk_test_abc123")
            result = client.process(
                content="Sarah said budget is approved",
                user_ulid="01HQWX5JKZM3N4P5Q6R7S8T9AB"
            )
            
            assert isinstance(result, MeaningObject)
            assert result.umo_id == "01HQWX5JKZM3N4P5Q6R7S8T9UV"
            assert len(result.entities) == 2
            assert result.entities[0].text == "Sarah"
    
    def test_process_meaning_only_default(self, mock_umo_response):
        """Default retention policy should be meaning_only."""
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_umo_response
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            client = MemoryClient(api_key="mi_sk_test_abc123")
            client.process(
                content="Test content",
                user_ulid="01HQWX5JKZM3N4P5Q6R7S8T9AB"
            )
            
            # Verify the request was made with meaning_only
            call_args = mock_client.request.call_args
            payload = call_args[1]["json"]
            assert payload["retention_policy"] == "meaning_only"
    
    def test_process_with_client_scope(self, mock_umo_response):
        """Process with client scope requires scope_id."""
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_umo_response["scope"] = "client"
            mock_umo_response["scope_id"] = "01CLIENT123"
            mock_response.json.return_value = mock_umo_response
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            client = MemoryClient(api_key="mi_sk_test_abc123")
            result = client.process(
                content="Client meeting notes",
                user_ulid="01HQWX5JKZM3N4P5Q6R7S8T9AB",
                scope=Scope.CLIENT,
                scope_id="01CLIENT123"
            )
            
            assert result.scope == Scope.CLIENT
            assert result.scope_id == "01CLIENT123"


# ============================================================================
# TEST 3: GOVERNANCE - SCOPE ISOLATION
# ============================================================================

class TestGovernanceScopes:
    """Tests for scope isolation enforcement."""
    
    def test_client_scope_requires_scope_id(self):
        """CLIENT scope without scope_id should raise ScopeViolationError."""
        with patch('httpx.Client'):
            client = MemoryClient(api_key="mi_sk_test_abc123")
            
            with pytest.raises(ScopeViolationError) as exc_info:
                client.process(
                    content="Test",
                    user_ulid="01USER123",
                    scope=Scope.CLIENT
                    # Missing scope_id!
                )
            
            assert "scope_id required" in str(exc_info.value)
    
    def test_project_scope_requires_scope_id(self):
        """PROJECT scope without scope_id should raise ScopeViolationError."""
        with patch('httpx.Client'):
            client = MemoryClient(api_key="mi_sk_test_abc123")
            
            with pytest.raises(ScopeViolationError):
                client.search(
                    query="Test query",
                    user_ulid="01USER123",
                    scope=Scope.PROJECT
                    # Missing scope_id!
                )
    
    def test_team_scope_requires_scope_id(self):
        """TEAM scope without scope_id should raise ScopeViolationError."""
        with patch('httpx.Client'):
            client = MemoryClient(api_key="mi_sk_test_abc123")
            
            with pytest.raises(ScopeViolationError):
                client.process(
                    content="Team doc",
                    user_ulid="01USER123",
                    scope=Scope.TEAM
                    # Missing scope_id!
                )
    
    def test_user_scope_no_scope_id_needed(self, mock_umo_response):
        """USER scope should not require scope_id."""
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_umo_response
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            client = MemoryClient(api_key="mi_sk_test_abc123")
            
            # Should NOT raise
            result = client.process(
                content="Personal note",
                user_ulid="01USER123",
                scope=Scope.USER
            )
            
            assert result is not None


# ============================================================================
# TEST 4: GOVERNANCE - PII HANDLING
# ============================================================================

class TestGovernancePII:
    """Tests for PII handling policies."""
    
    def test_pii_extract_and_redact_default(self, mock_umo_response):
        """Default PII handling should be extract_and_redact."""
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_umo_response
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            client = MemoryClient(api_key="mi_sk_test_abc123")
            client.process(
                content="Sarah's SSN is 123-45-6789",
                user_ulid="01USER123"
            )
            
            call_args = mock_client.request.call_args
            payload = call_args[1]["json"]
            assert payload["pii_handling"] == "extract_and_redact"
    
    def test_pii_hash_mode(self, mock_umo_response):
        """Hash mode should be passable."""
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_umo_response
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            client = MemoryClient(api_key="mi_sk_test_abc123")
            client.process(
                content="Medical record 12345",
                user_ulid="01USER123",
                pii_handling=PIIHandling.HASH
            )
            
            call_args = mock_client.request.call_args
            payload = call_args[1]["json"]
            assert payload["pii_handling"] == "hash"


# ============================================================================
# TEST 5: GOVERNANCE - RETENTION POLICIES
# ============================================================================

class TestGovernanceRetention:
    """Tests for retention policy enforcement."""
    
    def test_meaning_only_is_default(self, mock_umo_response):
        """meaning_only should be default retention policy."""
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_umo_response
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            client = MemoryClient(api_key="mi_sk_test_abc123")
            client.process("Test", user_ulid="01USER123")
            
            call_args = mock_client.request.call_args
            payload = call_args[1]["json"]
            assert payload["retention_policy"] == "meaning_only"
    
    def test_full_retention_explicit(self, mock_umo_response):
        """Full retention requires explicit override."""
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_umo_response
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            client = MemoryClient(api_key="mi_sk_test_abc123")
            client.process(
                "Test",
                user_ulid="01USER123",
                retention_policy=RetentionPolicy.FULL
            )
            
            call_args = mock_client.request.call_args
            payload = call_args[1]["json"]
            assert payload["retention_policy"] == "full"


# ============================================================================
# TEST 6: SEARCH OPERATION
# ============================================================================

class TestSearchOperation:
    """Tests for mi.search() operation."""
    
    def test_search_basic(self, mock_search_response):
        """Basic search should return SearchResponse."""
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_search_response
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            client = MemoryClient(api_key="mi_sk_test_abc123")
            result = client.search(
                query="What do we know about budget?",
                user_ulid="01USER123"
            )
            
            assert isinstance(result, SearchResponse)
            assert len(result.results) == 1
            assert result.results[0].score == 0.92
    
    def test_search_with_explanation(self, mock_search_response):
        """Search with explain=True should include explanation."""
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_search_response
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            client = MemoryClient(api_key="mi_sk_test_abc123")
            result = client.search(
                query="budget",
                user_ulid="01USER123",
                explain=True
            )
            
            assert result.results[0].explain is not None
            assert "finance" in result.results[0].explain.human.key_reasons[0]


# ============================================================================
# TEST 7: MATCH OPERATION
# ============================================================================

class TestMatchOperation:
    """Tests for mi.match() operation."""
    
    def test_match_basic(self, mock_match_response):
        """Basic match should return MatchResult."""
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_match_response
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            client = MemoryClient(api_key="mi_sk_test_abc123")
            result = client.match(
                source_ulid="01USER123",
                candidate_ulid="01POST456"
            )
            
            assert isinstance(result, MatchResult)
            assert result.score == 0.85
            assert result.match is True


# ============================================================================
# TEST 8: DELETE OPERATION (GDPR)
# ============================================================================

class TestDeleteOperation:
    """Tests for mi.delete() GDPR compliance."""
    
    def test_delete_all_user_data(self, mock_delete_response):
        """Delete all should remove all user data."""
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_delete_response
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            client = MemoryClient(api_key="mi_sk_test_abc123")
            result = client.delete(user_ulid="01USER123")
            
            assert isinstance(result, DeleteResult)
            assert result.deleted_count == 42
            assert result.scope == Scope.ALL
    
    def test_delete_scoped(self, mock_delete_response):
        """Delete with scope should be scoped."""
        mock_delete_response["deleted_count"] = 5
        
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_delete_response
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            client = MemoryClient(api_key="mi_sk_test_abc123")
            result = client.delete(
                user_ulid="01USER123",
                scope=Scope.CLIENT,
                scope_id="01CLIENT789"
            )
            
            assert result.scope == Scope.CLIENT
            assert result.scope_id == "01CLIENT789"


# ============================================================================
# TEST 9: VERIFY PROVENANCE
# ============================================================================

class TestVerifyProvenance:
    """Tests for mi.verify_provenance() operation."""
    
    def test_verify_valid_provenance(self, mock_verify_response):
        """Valid provenance should return VerifyResult."""
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = mock_verify_response
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            client = MemoryClient(api_key="mi_sk_test_abc123")
            result = client.verify_provenance(content_hash="sha256:abc123...")
            
            assert isinstance(result, VerifyResult)
            assert result.valid is True
            assert result.original_author_ulid == "01HQWX5JKZM3N4P5Q6R7S8TABC"
            assert result.hash_chain_valid is True


# ============================================================================
# TEST 10: EDGE CLIENT
# ============================================================================

class TestEdgeClient:
    """Tests for EdgeClient (on-prem/HIPAA)."""
    
    def test_edge_requires_api_key_or_air_gapped(self):
        """Edge without api_key should require air_gapped=True."""
        with pytest.raises(AuthenticationError) as exc_info:
            EdgeClient(
                endpoint="https://mi.internal.hospital.com",
                # No api_key, not air_gapped
            )
        assert "air_gapped" in str(exc_info.value)
    
    def test_edge_air_gapped_no_api_key(self):
        """Air-gapped mode should work without API key."""
        with patch('httpx.Client'):
            client = EdgeClient(
                endpoint="https://mi.internal.hospital.com",
                air_gapped=True
            )
            assert client.air_gapped is True
            assert client.metering_enabled is False
    
    def test_edge_hipaa_mode(self):
        """HIPAA mode should enforce hash PII handling."""
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "umo_id": "01UMO123",
                "user_ulid": "01PATIENT123",
                "entities": [],
                "topics": [],
                "svo_triples": [],
                "key_phrases": [],
                "provenance": {
                    "semantic_hash": "sha256:abc",
                    "timestamp_anchor": datetime.utcnow().isoformat(),
                    "hash_chain": "sha256:prev",
                },
                "pii": {
                    "detected": True,
                    "types": ["PERSON", "DATE", "MRN"],
                    "count": 3,
                    "handling_applied": "hash",
                },
                "scope": "user",
            }
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            client = EdgeClient(
                endpoint="https://mi.internal.hospital.com",
                api_key="mi_sk_test_abc123",
                hipaa_mode=True
            )
            
            result = client.process(
                content="Patient John Doe, MRN 12345, DOB 1985-03-15",
                user_ulid="01PATIENT123"
            )
            
            # Verify HIPAA mode enforced hash handling
            call_args = mock_client.request.call_args
            payload = call_args[1]["json"]
            assert payload["pii_handling"] == "hash"
            assert payload["provenance_mode"] == "audit"
            assert payload["hipaa_mode"] is True


# ============================================================================
# TEST 11: ERROR HANDLING
# ============================================================================

class TestErrorHandling:
    """Tests for SDK error handling."""
    
    def test_auth_error_on_401(self):
        """401 response should raise AuthenticationError."""
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            client = MemoryClient(api_key="mi_sk_test_abc123")
            
            with pytest.raises(AuthenticationError):
                client.process("Test", user_ulid="01USER123")
    
    def test_scope_violation_on_403(self):
        """403 response should raise ScopeViolationError."""
        with patch('httpx.Client') as mock_client_class:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 403
            mock_response.json.return_value = {"detail": "Cross-scope access denied"}
            mock_client.request.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            client = MemoryClient(api_key="mi_sk_test_abc123")
            
            with pytest.raises(ScopeViolationError) as exc_info:
                client.search(
                    "test",
                    user_ulid="01USER123",
                    scope=Scope.CLIENT,
                    scope_id="01CLIENT999"
                )
            
            assert "denied" in str(exc_info.value)


# ============================================================================
# TEST 12: ENUMS
# ============================================================================

class TestEnums:
    """Tests for SDK enum values."""
    
    def test_scope_values(self):
        """Scope enum should have correct values."""
        assert Scope.USER.value == "user"
        assert Scope.CLIENT.value == "client"
        assert Scope.PROJECT.value == "project"
        assert Scope.TEAM.value == "team"
        assert Scope.ORGANIZATION.value == "org"
        assert Scope.ALL.value == "all"
    
    def test_retention_policy_values(self):
        """RetentionPolicy enum should have correct values."""
        assert RetentionPolicy.MEANING_ONLY.value == "meaning_only"
        assert RetentionPolicy.FULL.value == "full"
        assert RetentionPolicy.SUMMARY_ONLY.value == "summary_only"
    
    def test_pii_handling_values(self):
        """PIIHandling enum should have correct values."""
        assert PIIHandling.DETECT_ONLY.value == "detect_only"
        assert PIIHandling.EXTRACT_AND_REDACT.value == "extract_and_redact"
        assert PIIHandling.HASH.value == "hash"
        assert PIIHandling.REJECT.value == "reject"
    
    def test_provenance_mode_values(self):
        """ProvenanceMode enum should have correct values."""
        assert ProvenanceMode.STANDARD.value == "standard"
        assert ProvenanceMode.AUTHORSHIP.value == "authorship"
        assert ProvenanceMode.AUDIT.value == "audit"
    
    def test_explain_level_values(self):
        """ExplainLevel enum should have correct values."""
        assert ExplainLevel.NONE.value == "none"
        assert ExplainLevel.HUMAN.value == "human"
        assert ExplainLevel.AUDIT.value == "audit"
        assert ExplainLevel.FULL.value == "full"


# ============================================================================
# MAIN - Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
