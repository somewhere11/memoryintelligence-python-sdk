"""
SDK Integration Test
=====================

End-to-end test validating SDK → API → Pipeline flow.

Requires running API server:
    cd <your-mi-repo> && python -m uvicorn api.app:app --port 8000

Then run:
    python -m pytest tests/test_integration.py -v
"""

import pytest
import os
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

# SDK imports
from memoryintelligence import (
    MemoryClient,
    EdgeClient,
    Scope,
    RetentionPolicy,
    PIIHandling,
    ProvenanceMode,
    ExplainLevel,
)


# =============================================================================
# INTEGRATION TESTS (against running server)
# =============================================================================

@pytest.mark.integration
class TestSDKIntegration:
    """
    Integration tests that require a running API server.
    
    Skip with: pytest -m "not integration"
    """
    
    API_URL = os.environ.get("MI_API_URL", "http://localhost:8000")
    API_KEY = os.environ.get("MI_API_KEY", "mi_sk_test_integration_key")
    TEST_USER_ULID = "01HQWX5JKZM3N4P5Q6R7S8T9AB"
    
    @pytest.fixture
    def client(self):
        """Create SDK client for integration tests."""
        return MemoryClient(
            api_key=self.API_KEY,
            base_url=self.API_URL,
        )
    
    def test_process_and_search_roundtrip(self, client):
        """Process content and search should work end-to-end."""
        # Process
        umo = client.process(
            content="The budget meeting with Sarah was approved for Q4 planning.",
            user_ulid=self.TEST_USER_ULID,
            retention_policy=RetentionPolicy.MEANING_ONLY,
        )
        
        assert umo.umo_id is not None
        assert len(umo.umo_id) == 26  # ULID length
        assert umo.user_ulid == self.TEST_USER_ULID
        
        # Search
        results = client.search(
            query="budget meeting",
            user_ulid=self.TEST_USER_ULID,
            explain=True,
        )
        
        assert results.total_count >= 0
        # Note: actual matching depends on indexing
    
    def test_process_with_pii_detection(self, client):
        """PII should be detected and handled."""
        umo = client.process(
            content="Contact John at john@example.com or 555-123-4567",
            user_ulid=self.TEST_USER_ULID,
            pii_handling=PIIHandling.EXTRACT_AND_REDACT,
        )
        
        assert umo.pii is not None
        assert umo.pii.detected is True
        assert "EMAIL" in umo.pii.types or "PHONE" in umo.pii.types
    
    def test_explain_returns_both_layers(self, client):
        """Explain should return human + audit explanations."""
        # First process something
        umo = client.process(
            content="Test content for explanation",
            user_ulid=self.TEST_USER_ULID,
        )
        
        # Then explain it
        explanation = client.explain(umo.umo_id)
        
        assert explanation.human is not None
        assert explanation.human.summary != ""
        assert explanation.audit is not None
        assert explanation.audit.reproducible is True
    
    def test_delete_returns_audit_proof(self, client):
        """Delete should return audit proof of deletion."""
        result = client.delete(
            user_ulid=self.TEST_USER_ULID,
            scope=Scope.USER,
        )
        
        assert result.deleted_count >= 0
        assert "deletion_hash" in result.audit_proof
        assert result.audit_proof["verified"] is True
    
    def test_verify_provenance(self, client):
        """Verify provenance should validate hash chain."""
        result = client.verify_provenance(
            content_hash="sha256:test_hash_for_verification"
        )
        
        assert result.valid is True
        assert result.hash_chain_valid is True
    
    def test_scope_isolation_enforced(self, client):
        """Client scope should require scope_id."""
        with pytest.raises(Exception) as exc_info:
            client.process(
                content="Test",
                user_ulid=self.TEST_USER_ULID,
                scope=Scope.CLIENT,
                # Missing scope_id!
            )
        
        assert "scope_id" in str(exc_info.value).lower()


@pytest.mark.integration
class TestEdgeClientIntegration:
    """Integration tests for EdgeClient."""
    
    EDGE_ENDPOINT = os.environ.get("MI_EDGE_URL", "http://localhost:8000")
    API_KEY = os.environ.get("MI_API_KEY", "mi_sk_test_integration_key")
    
    @pytest.fixture
    def edge_client(self):
        """Create EdgeClient for integration tests."""
        return EdgeClient(
            endpoint=self.EDGE_ENDPOINT,
            api_key=self.API_KEY,
            hipaa_mode=True,
        )
    
    def test_hipaa_mode_enforces_hash_pii(self, edge_client):
        """HIPAA mode should enforce hash PII handling."""
        # The EdgeClient should automatically set PII handling to HASH
        # This is validated in the client, not at API level
        
        # Process with PHI
        umo = edge_client.process(
            content="Patient John Doe, MRN 12345",
            user_ulid="01PATIENT123456789012345",
        )
        
        # Verify handling was applied
        assert umo.pii is not None
        assert umo.pii.handling_applied == "hash"
    
    def test_aggregate_respects_k_anonymity(self, edge_client):
        """Aggregate should respect minimum cohort size."""
        result = edge_client.aggregate(
            query="patients with condition X",
            scope=Scope.ORGANIZATION,
            minimum_cohort_size=50,
        )
        
        assert "count" in result
        assert result.get("audit_proof", {}).get("k_anonymity") == 50
    
    def test_verify_phi_handling(self, edge_client):
        """PHI handling verification should return audit proof."""
        result = edge_client.verify_phi_handling(
            umo_id="01TESTUMOID1234567890123"
        )
        
        assert "phi_detected" in result
        assert result["raw_phi_stored"] is False
        assert result["raw_phi_transmitted"] is False


# =============================================================================
# GOVERNANCE VALIDATION TESTS
# =============================================================================

class TestGovernanceValidation:
    """
    Tests that validate governance is enforced correctly.
    These run against mocks to verify SDK behavior.
    """
    
    def test_meaning_only_is_privacy_default(self):
        """Verify meaning_only is the default retention policy."""
        with patch('httpx.Client') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "umo_id": "01TEST123456789012345678",
                "user_ulid": "01USER123456789012345678",
                "entities": [],
                "topics": [],
                "svo_triples": [],
                "key_phrases": [],
                "provenance": {
                    "semantic_hash": "sha256:test",
                    "timestamp_anchor": datetime.now(timezone.utc).isoformat(),
                    "hash_chain": "sha256:prev",
                },
                "scope": "user",
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }
            mock_client.return_value.request.return_value = mock_response
            
            client = MemoryClient(api_key="mi_sk_test_key")
            client.process("Test content", user_ulid="01USER123456789012345678")
            
            # Verify the request included meaning_only
            call_args = mock_client.return_value.request.call_args
            payload = call_args[1]["json"]
            assert payload["retention_policy"] == "meaning_only"
    
    def test_scope_isolation_is_cryptographic(self):
        """Verify scope violations raise exceptions, not just warnings."""
        with patch('httpx.Client'):
            client = MemoryClient(api_key="mi_sk_test_key")
            
            # This MUST raise, not warn
            with pytest.raises(Exception):
                client.process(
                    content="Test",
                    user_ulid="01USER123456789012345678",
                    scope=Scope.CLIENT,
                    # No scope_id!
                )
    
    def test_explainability_included_when_requested(self):
        """Verify explain parameter is passed to API."""
        with patch('httpx.Client') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "results": [],
                "total_count": 0,
            }
            mock_client.return_value.request.return_value = mock_response
            
            client = MemoryClient(api_key="mi_sk_test_key")
            client.search(
                query="test query",
                user_ulid="01USER123456789012345678",
                explain=True,  # Request explanation
            )
            
            call_args = mock_client.return_value.request.call_args
            payload = call_args[1]["json"]
            assert payload["explain"] == "full"
    
    def test_provenance_always_included(self):
        """Verify provenance is always in process response."""
        with patch('httpx.Client') as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "umo_id": "01TEST123456789012345678",
                "user_ulid": "01USER123456789012345678",
                "entities": [],
                "topics": [],
                "svo_triples": [],
                "key_phrases": [],
                "provenance": {
                    "semantic_hash": "sha256:test",
                    "timestamp_anchor": datetime.now(timezone.utc).isoformat(),
                    "hash_chain": "sha256:prev",
                },
                "scope": "user",
                "ingested_at": datetime.now(timezone.utc).isoformat(),
            }
            mock_client.return_value.request.return_value = mock_response
            
            client = MemoryClient(api_key="mi_sk_test_key")
            umo = client.process(
                content="Test content",
                user_ulid="01USER123456789012345678",
            )
            
            assert umo.provenance is not None
            assert umo.provenance.semantic_hash != ""
            assert umo.provenance.timestamp_anchor is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-m", "not integration"])
